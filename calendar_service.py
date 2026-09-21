"""Offline calendar conversion, holidays, and persistent local-time events."""
import calendar
from contextlib import closing
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
import sqlite3

import holidays
from lunardate import LunarDate

MIN_YEAR, MAX_YEAR = 1901, 2098
MODES = {'gregorian', 'chinese'}


def _date(value):
    if not isinstance(value, str):
        raise ValueError('Choose a valid date.')
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value or not 1900 <= parsed.year <= 2100:
        raise ValueError('Choose a supported date.')
    return parsed


@lru_cache(maxsize=400)
def months_for(mode, year):
    if mode not in MODES or type(year) is not int or not MIN_YEAR <= year <= MAX_YEAR:
        raise ValueError(f'Choose a year from {MIN_YEAR} to {MAX_YEAR}.')
    months = []
    leap = LunarDate.leap_month_for_year(year) if mode == 'chinese' else None
    for month in range(1, 13):
        for is_leap in ([False, True] if month == leap else [False]):
            if mode == 'gregorian':
                start = date(year, month, 1)
                count = calendar.monthrange(year, month)[1]
                label = calendar.month_name[month]
            else:
                start = LunarDate(year, month, 1, is_leap).to_solar_date()
                try:
                    LunarDate(year, month, 30, is_leap).to_solar_date()
                    count = 30
                except ValueError:
                    count = 29
                label = f'{"Leap " if is_leap else ""}Month {month}'
            months.append({'key': f'{month}{"L" if is_leap else ""}', 'label': label,
                           'start': start, 'count': count})
    return months


@lru_cache(maxsize=400)
def holiday_year(mode, year):
    return holidays.country_holidays(
        'US' if mode == 'gregorian' else 'CN', years=year, language='en_US',
        categories=('public', 'unofficial') if mode == 'gregorian' else ('public',),
    )


def lunar_label(day):
    lunar = LunarDate.from_solar_date(day.year, day.month, day.day)
    return f'Lunar {lunar.year} · {"Leap " if lunar.is_leap_month else ""}{lunar.month}/{lunar.day}'


class CalendarService:
    def __init__(self, database):
        self.database = Path(database)

    def _connect(self):
        self.database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            # Serialize the additive migration. Existing events remain all-day.
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('''CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL,
                title TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
                starts_at TEXT, ends_at TEXT)''')
            columns = {row['name'] for row in connection.execute('PRAGMA table_info(calendar_events)')}
            for column in ('starts_at', 'ends_at'):
                if column not in columns:
                    connection.execute(f'ALTER TABLE calendar_events ADD COLUMN {column} TEXT')
            connection.execute('CREATE INDEX IF NOT EXISTS calendar_event_dates ON calendar_events(date)')
            connection.commit()
        except Exception:
            connection.close()
            raise
        return connection

    def save_event(self, day, title, notes='', event_id=None, starts_at=None, ends_at=None):
        _date(day)
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 120:
            raise ValueError('Enter a title of 1–120 characters.')
        if not isinstance(notes, str) or len(notes) > 2000:
            raise ValueError('Notes must be 2,000 characters or fewer.')
        if event_id is not None and (type(event_id) is not int or event_id < 1):
            raise ValueError('Invalid event.')
        if starts_at is not None or ends_at is not None:
            def parse(value):
                if not isinstance(value, str):
                    raise ValueError('Choose both a start and an end time.')
                parsed = datetime.fromisoformat(value)
                if parsed.tzinfo is not None or parsed.isoformat(timespec='minutes') != value:
                    raise ValueError('Use local dates and times with minute precision.')
                _date(value[:10])
                return parsed
            start, end = parse(starts_at), parse(ends_at)
            if end <= start:
                raise ValueError('End must be after start.')
            if start.date().isoformat() != day:
                raise ValueError('The event date must match its start date.')
        with closing(self._connect()) as connection, connection:
            if event_id is None:
                cursor = connection.execute('INSERT INTO calendar_events(date,title,notes,starts_at,ends_at) VALUES (?,?,?,?,?)',
                                            (day, title.strip(), notes.strip(), starts_at, ends_at))
                event_id = cursor.lastrowid
            else:
                cursor = connection.execute('UPDATE calendar_events SET date=?,title=?,notes=?,starts_at=?,ends_at=? WHERE id=?',
                                            (day, title.strip(), notes.strip(), starts_at, ends_at, event_id))
                if not cursor.rowcount:
                    raise ValueError('This event no longer exists.')
        return event_id

    def delete_event(self, event_id):
        if type(event_id) is not int or event_id < 1:
            raise ValueError('Invalid event.')
        with closing(self._connect()) as connection, connection:
            connection.execute('DELETE FROM calendar_events WHERE id=?', (event_id,))
        return True

    def _events_between(self, start, end):
        with closing(self._connect()) as connection:
            return [dict(row) for row in connection.execute('''SELECT * FROM calendar_events WHERE
                (starts_at IS NULL AND date BETWEEN ? AND ?) OR (starts_at < ? AND ends_at > ?)
                ORDER BY starts_at, id''', (start.isoformat(), end.isoformat(),
                (end + timedelta(days=1)).isoformat() + 'T00:00', start.isoformat() + 'T00:00'))]

    def _day(self, mode, day, events, number=None):
        holiday = holiday_year(mode, day.year).get(day, '')
        names = holiday.split('; ') if holiday else []
        if mode == 'chinese':
            lunar = LunarDate.from_solar_date(day.year, day.month, day.day)
            festivals = {(1, 15): 'Lantern Festival', (7, 7): 'Qixi Festival',
                         (7, 15): 'Ghost Festival', (9, 9): 'Double Ninth Festival', (12, 8): 'Laba Festival'}
            festival = festivals.get((lunar.month, lunar.day)) if not lunar.is_leap_month else None
            if festival:
                names.append(f'{festival} (traditional observance)')
        lower, upper = day.isoformat() + 'T00:00', (day + timedelta(days=1)).isoformat() + 'T00:00'
        matching = [item for item in events if
                    (item['starts_at'] is None and item['date'] == day.isoformat()) or
                    (item['starts_at'] is not None and item['starts_at'] < upper and item['ends_at'] > lower)]
        return {'date': day.isoformat(), 'day': number or day.day,
                'secondary': f'{day.month}/{day.day}' if mode == 'chinese' else '',
                'lunar': lunar_label(day), 'holidays': names, 'today': day == date.today(), 'events': matching}

    def day(self, mode, day):
        if mode not in MODES:
            raise ValueError('Unknown calendar.')
        parsed = _date(day)
        if not date(1901, 1, 1) <= parsed <= date(2099, 12, 31):
            raise ValueError('Choose a supported date.')
        return self._day(mode, parsed, self._events_between(parsed, parsed))

    def month(self, mode, year=None, month=None, anchor=None):
        if mode not in MODES:
            raise ValueError('Unknown calendar.')
        anchor_date = _date(anchor) if anchor else date.today()
        if year is None:
            if mode == 'chinese':
                lunar = LunarDate.from_solar_date(anchor_date.year, anchor_date.month, anchor_date.day)
                year, month = lunar.year, f'{lunar.month}{"L" if lunar.is_leap_month else ""}'
            else:
                year, month = anchor_date.year, str(anchor_date.month)
            if not MIN_YEAR <= year <= MAX_YEAR:
                year, month = min(MAX_YEAR, max(MIN_YEAR, year)), '1'
        choices = months_for(mode, year)
        # A leap month does not exist in every year. Fall back to its regular month.
        if month not in {item['key'] for item in choices}:
            month = str(month).rstrip('L')
        index = next((i for i, item in enumerate(choices) if item['key'] == month), None)
        if index is None:
            raise ValueError('Choose a valid month.')
        selected = choices[index]
        start, count = selected['start'], selected['count']
        end = start + timedelta(days=count - 1)
        events = self._events_between(start, end)
        days = [self._day(mode, start + timedelta(days=offset), events, offset + 1) for offset in range(count)]
        def neighbor(direction):
            new_year, new_index = year, index + direction
            if new_index < 0:
                new_year -= 1
                if new_year < MIN_YEAR:
                    return None
                new_index = len(months_for(mode, new_year)) - 1
            elif new_index >= len(choices):
                new_year += 1
                new_index = 0
                if new_year > MAX_YEAR:
                    return None
            return {'year': new_year, 'month': months_for(mode, new_year)[new_index]['key']}
        return {'mode': mode, 'year': year, 'month': selected['key'],
                'title': f'{selected["label"]} {year}', 'today': date.today().isoformat(),
                'offset': (start.weekday() + 1) % 7, 'days': days,
                'months': [{'key': item['key'], 'label': item['label']} for item in choices],
                'previous': neighbor(-1), 'next': neighbor(1),
                'min_year': MIN_YEAR, 'max_year': MAX_YEAR}
