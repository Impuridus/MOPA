// Month grid, event editor, and hourly schedule. Times use local wall-clock time.
const calendarUI = (() => {
    const el = id => document.getElementById(id);
    const mode = () => preferences.calendar || 'gregorian';
    let view = null, selected = null, dayData = null, editingId = null;
    let busy = false, saving = false, dirty = false;
    let lastToday = '';
    const dayDialog = el('calendar-day-dialog');
    const editor = el('calendar-event-dialog');
    function node(tag, text, className) {
        const result = document.createElement(tag);
        if (text != null) result.textContent = text;
        if (className) result.className = className;
        return result;
    }
    function error(message = '') {
        el('calendar-status').textContent = message;
        el('calendar-error').hidden = !message;
    }
    function editorError(message = '') {
        el('event-error').textContent = message;
        el('event-error').hidden = !message;
    }
    function allowLeave() {
        if (saving) return false;
        if (dirty && !window.confirm('Discard the unsaved event changes?')) return false;
        dirty = false;
        return true;
    }
    function lockMonth(value) {
        busy = value;
        el('calendar-panel').setAttribute('aria-busy', String(value));
        el('calendar-content').querySelectorAll('button,select').forEach(item => { item.disabled = value; });
        if (!value && view) {
            el('calendar-previous').disabled = !view.previous;
            el('calendar-next').disabled = !view.next;
        }
    }
    function toggleAllDay() {
        const allDay = el('event-all-day').checked;
        el('event-times').hidden = allDay;
        el('event-date-row').hidden = !allDay;
        for (const id of ['event-start', 'event-end']) {
            el(id).required = !allDay;
            el(id).disabled = allDay || saving;
        }
        el('event-date').required = allDay;
        el('event-date').disabled = !allDay || saving;
    }
    function lockEditor(value) {
        saving = value;
        editor.querySelectorAll('button,input,textarea').forEach(item => { item.disabled = value; });
        el('event-save').textContent = value ? 'Saving…' : 'Save event';
        toggleAllDay();
    }
    const dateTitle = day => new Date(`${day}T12:00:00`).toLocaleDateString(preferences.language, {
        weekday: 'long', month: 'long', day: 'numeric', year: 'numeric', calendar: 'gregory',
    });
    const clockText = value => new Date(value).toLocaleTimeString(preferences.language, {hour:'numeric',minute:'2-digit'});
    function eventTime(event) {
        if (!event.starts_at) return 'All day';
        if (event.starts_at.slice(0,10) === event.ends_at.slice(0,10)) return `${clockText(event.starts_at)} – ${clockText(event.ends_at)}`;
        return `${event.starts_at.replace('T',' ')} – ${event.ends_at.replace('T',' ')}`;
    }
    function selectDay(day) {
        selected = day;
        el('calendar-grid').querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed',String(button.dataset.date === selected)));
    }
    function renderMonth() {
        el('calendar-content').hidden = false;
        el('calendar-grid').setAttribute('aria-label', `${view.title}, ${view.mode === 'chinese' ? 'Chinese lunisolar' : 'Gregorian'} calendar`);
        el('calendar-month').replaceChildren(...view.months.map(item => {
            const option = node('option',item.label); option.value=item.key; return option;
        }));
        el('calendar-month').value=view.month;
        el('calendar-year').replaceChildren();
        for(let year=view.min_year;year<=view.max_year;year++) {
            const option=node('option',String(year)); option.value=year; el('calendar-year').append(option);
        }
        el('calendar-year').value=view.year;
        const grid=el('calendar-grid'); grid.replaceChildren();
        for(let index=0;index<view.offset;index++) {
            const blank=node('div');blank.setAttribute('aria-hidden','true');grid.append(blank);
        }
        for(const day of view.days) {
            const button=node('button',null,'calendar-day'); button.type='button'; button.dataset.date=day.date;
            button.setAttribute('aria-label',`${day.date}, ${day.lunar}${day.today?', today':''}. ${day.holidays.join('. ')}. ${day.events.map(event => event.title).join('; ') || 'No events'}.`);
            button.title='Click to view day · Right-click to add an event';
            if(day.today)button.setAttribute('aria-current','date');
            button.append(node('span',String(day.day),'calendar-day-number'));
            if(day.secondary)button.append(node('small',day.secondary,'calendar-secondary'));
            if(day.holidays.length)button.append(node('span',day.holidays[0],'calendar-holiday-badge'));
            for (const event of day.events) {
                const label = node('span', event.title, 'calendar-event-badge');
                label.title = event.title;
                button.append(label);
            }
            button.addEventListener('click',()=>openDay(day));
            button.addEventListener('contextmenu',event=>{event.preventDefault();openEditor(day.date);});
            button.addEventListener('keydown',event=>{
                if(event.key==='ContextMenu'||(event.shiftKey&&event.key==='F10')) {
                    event.preventDefault();openEditor(day.date);
                }
            });
            grid.append(button);
        }
        selectDay(selected);
    }
    function openEditor(day,event=null,minute=540) {
        if(saving || busy || !allowLeave())return;
        selectDay(day);
        editingId=event?.id??null;
        el('event-form').reset();editorError();
        el('event-dialog-title').textContent=event?'Edit event':'New event';
        el('event-title').value=event?.title??'';
        el('event-notes').value=event?.notes??'';
        const hhmm = value => `${String(Math.floor(value/60)).padStart(2,'0')}:${String(value%60).padStart(2,'0')}`;
        const nextDay=new Date(`${day}T12:00:00`);nextDay.setDate(nextDay.getDate()+1);
        const nextISO=`${nextDay.getFullYear()}-${String(nextDay.getMonth()+1).padStart(2,'0')}-${String(nextDay.getDate()).padStart(2,'0')}`;
        const endMinute=minute+60;
        el('event-start').value=event?.starts_at??`${day}T${hhmm(minute)}`;
        el('event-end').value=event?.ends_at??`${endMinute>=1440?nextISO:day}T${hhmm(endMinute%1440)}`;
        el('event-date').value=event?.date??day;
        el('event-all-day').checked=Boolean(event&&!event.starts_at);
        el('event-delete').hidden=!event;
        dirty=false;lockEditor(false);
        if(!editor.open)editor.showModal();
        el('event-title').focus();
    }
    // Lay out overlapping events in separate columns within each overlap group.
    function eventSegments(events,day) {
        const minutes=value=>Number(value.slice(11,13))*60+Number(value.slice(14,16));
        const segments=events.filter(event=>event.starts_at).map(event=>({event,
            start:event.starts_at.slice(0,10)<day?0:minutes(event.starts_at),
            end:event.ends_at.slice(0,10)>day?1440:minutes(event.ends_at),
        })).sort((a,b)=>a.start-b.start||b.end-a.end);
        let group=[],limit=0;
        function place() {
            const ends=[];
            for(const segment of group) {
                let col=ends.findIndex(end=>end<=segment.start);
                if(col<0)col=ends.length;
                ends[col]=segment.end;segment.column=col;
            }
            group.forEach(segment=>segment.columns=ends.length);
        }
        for(const segment of segments) {
            if(group.length&&segment.start>=limit){place();group=[];limit=0;}
            group.push(segment);limit=Math.max(limit,segment.end);
        }
        place();return segments;
    }
    function renderSchedule() {
        if(!dayData)return;
        el('day-title').textContent=dateTitle(dayData.date);
        el('day-subtitle').textContent=dayData.lunar;
        const banners=el('day-banners');banners.replaceChildren();
        if(dayData.holidays.length)banners.append(node('p',dayData.holidays.join(' · '),'day-holiday'));
        for(const event of dayData.events.filter(event=>!event.starts_at)) {
            const button=node('button',`${event.title} · All day`,'day-all-day');button.type='button';
            button.addEventListener('click',()=>openEditor(dayData.date,event));banners.append(button);
        }
        const hours=el('day-hours');hours.replaceChildren();
        for(let hour=0;hour<24;hour++) {
            const row=node('div',null,'day-hour');row.style.top=`${hour*64}px`;
            row.append(node('span',new Date(2000,0,1,hour).toLocaleTimeString(preferences.language,{hour:'numeric',minute:'2-digit'})));
            hours.append(row);
        }
        const layer=el('day-events');layer.replaceChildren();
        for(const segment of eventSegments(dayData.events,dayData.date)) {
            const event=segment.event;
            const button=node('button',null,'day-event-block');button.type='button';button.dataset.eventId=event.id;
            const label=`${event.title}, ${eventTime(event)}${event.notes?`. ${event.notes}`:''}`;
            button.setAttribute('aria-label',label);button.title=label;
            button.style.top=`${segment.start*64/60}px`;
            button.style.height=`${Math.max(2,(segment.end-segment.start)*64/60)}px`;
            button.style.left=`calc(${segment.column*100/segment.columns}% + 2px)`;
            button.style.width=`calc(${100/segment.columns}% - 4px)`;
            if(segment.end-segment.start<24)button.classList.add('short-event');
            button.append(node('strong',event.title),node('small',eventTime(event)),node('small',event.notes));
            button.addEventListener('click',()=>openEditor(dayData.date,event));layer.append(button);
        }
    }
    function openDay(day) {
        if(busy || !allowLeave())return;
        selectDay(day.date);dayData=day;renderSchedule();
        if(!dayDialog.open)dayDialog.showModal();
        const first=eventSegments(day.events,day.date)[0];
        el('day-scroll').scrollTop=Math.max(0,((first?.start??480)-60)*64/60);
    }
    async function load(year=null,month=null,anchor=selected) {
        if(busy)return;
        if(!window.pywebview?.api||!initialized)return;
        lockMonth(true);error();
        try {
            view=await window.pywebview.api.get_calendar(mode(),year,month,anchor);
            selected=view.days.some(day=>day.date===anchor)?anchor:view.days.find(day=>day.today)?.date??view.days[0].date;
            renderMonth();
        } catch(problem) {
            console.error(problem);error(`Could not load the calendar: ${problem.message||problem}`);
        } finally {lockMonth(false);}
    }
    async function refreshAfterSave() {
        lockMonth(true);
        try {
            view=await window.pywebview.api.get_calendar(mode(),view.year,view.month,selected);
            renderMonth();
            if(dayDialog.open&&dayData) {
                dayData=await window.pywebview.api.get_calendar_day(mode(),dayData.date);
                renderSchedule();
            }
            error();
        } catch(problem) {
            error(`Your change was saved, but the view could not refresh: ${problem.message||problem}`);
        } finally {lockMonth(false);}
    }
    async function open() {
        if(!view||view.mode!==mode())return load();
        renderMonth();lockMonth(false);
    }
    function closeEditor() {
        if(allowLeave())editor.close();
    }
    editor.addEventListener('cancel',event=>{event.preventDefault();closeEditor();});
    el('event-close').addEventListener('click',closeEditor);
    el('event-cancel').addEventListener('click',closeEditor);
    el('event-form').addEventListener('input',()=>{dirty=true;editorError();});
    el('event-all-day').addEventListener('change',toggleAllDay);
    el('event-form').addEventListener('submit',async event=>{
        event.preventDefault();if(saving)return;
        const title=el('event-title').value.trim();
        const allDay=el('event-all-day').checked;
        const start=allDay?null:el('event-start').value;
        const end=allDay?null:el('event-end').value;
        const day=allDay?el('event-date').value:start.slice(0,10);
        if(!title){editorError('Enter an event title.');return;}
        if(!allDay&&(!start||!end||end<=start)){editorError('End must be after start.');return;}
        lockEditor(true);editorError();
        try {
            await window.pywebview.api.save_calendar_event(day,title,el('event-notes').value,editingId,start,end);
            dirty=false;editor.close();await refreshAfterSave();
        } catch(problem) {
            editorError(`Could not save: ${problem.message||problem}`);
        } finally {lockEditor(false);}
    });
    el('event-delete').addEventListener('click',async()=>{
        if(saving||editingId===null||!window.confirm('Delete this event?'))return;
        lockEditor(true);editorError();
        try {
            await window.pywebview.api.delete_calendar_event(editingId);
            dirty=false;editor.close();await refreshAfterSave();
        } catch(problem) {editorError(`Could not delete: ${problem.message||problem}`);}
        finally{lockEditor(false);}
    });
    el('day-close').addEventListener('click',()=>dayDialog.close());
    el('day-add').addEventListener('click',()=>openEditor(dayData.date));
    el('day-timeline').addEventListener('contextmenu',event=>{
        if(event.target.closest('.day-event-block'))return;
        event.preventDefault();
        const y=event.clientY-el('day-timeline').getBoundingClientRect().top;
        openEditor(dayData.date,null,Math.min(1425,Math.max(0,Math.floor(y/64*4)*15)));
    });
    el('calendar-month').addEventListener('change',()=>load(view.year,el('calendar-month').value));
    el('calendar-year').addEventListener('change',()=>load(Number(el('calendar-year').value),view.month));
    for(const direction of ['previous','next'])el(`calendar-${direction}`).addEventListener('click',()=>{
        if(view?.[direction])load(view[direction].year,view[direction].month);
    });
    el('calendar-today').addEventListener('click',()=>load(null,null,null));
    el('calendar-retry').addEventListener('click',()=>load(view?.year??null,view?.month??null));
    setInterval(()=>{
        const today=new Date().toDateString();
        if(view&&lastToday&&lastToday!==today) {
            const now=new Date();
            const iso=`${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
            view.days.forEach(day=>{day.today=day.date===iso;});
            if(!el('calendar-panel').hidden&&!editor.open)renderMonth();
        }
        lastToday=today;
    },30000);
    return {open,allowLeave,settingsChanged:()=>{if(!el('calendar-panel').hidden&&!editor.open&&!dayDialog.open)open();}};
})();
