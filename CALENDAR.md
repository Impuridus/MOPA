# Calendar

Start MOPA with `python main.py`, then open **Daily → Calendar**.

- The month page contains navigation controls and the date grid. Use the month/year selectors, arrows, or Today to navigate.
- **Right-click a date** to create an event with a title, description, start date/time, and end date/time. Shift+F10 on a focused date also opens the editor.
- **Left-click a date** to open its hourly schedule. Timed events appear as translucent blocks; overlapping events use separate columns. Click a block to edit or delete it.
- Scroll the schedule to see all 24 hours. The Add event button and right-clicking an empty time slot also open the editor.
- Events can cross midnight or month boundaries and appear on each day they overlap. An event ending at midnight does not occupy the following day.
- Existing events without times remain all-day events at the top of the schedule. The editor also supports an All day option.
- Times use local wall-clock dates and times. Events do not create notifications or alarms.

## Calendar modes and holidays

Settings → Calendar switches between Gregorian/U.S. holidays and Chinese lunisolar/mainland China holidays. Events keep the same actual dates. Lunar mode uses true lunar months, including leap months, and shows the Gregorian month/day beneath each date.

Both modes support display years 1901–2098. At the boundary, switching modes can move to the nearest supported year. U.S. holidays include federal holidays and selected observances. China holidays include public holidays and selected traditional festivals. Holiday labels do not necessarily imply a day off; future official adjustments can change. Select a day to read its full holiday labels.

## Storage and setup

Events and preferences are saved in `%LOCALAPPDATA%\MOPA\settings.db`, outside Git. The timed-event update adds two nullable columns and preserves existing events. Calendar features work offline. No new libraries are required for the timed schedule update.

For a fresh clone, install `requirements.txt` in your virtual environment. New calendar controls remain in English while translation work is postponed.

## Code map

- `calendar_service.py`: conversions, holidays, event validation and SQLite storage.
- `UI/calendar.js`: month navigation, pop-up editor and hourly schedule.
- `UI/calendar.css`: calendar grid, dialogs and translucent blocks.
- `main.py`: Python methods exposed to JavaScript.

Run the tests from the repository root with `python -m unittest discover -s tests -v`.
