"""Start MOPA and store preferences outside the Git repository."""
import os
import sqlite3
from pathlib import Path
from weather import get_weather


DEFAULTS = {"language": "en", "temperature": "fahrenheit", "theme": "dark", "calendar": "gregorian"}
CHOICES = {
    "language": {"en", "zh-Hans", "zh-Hant", "ja", "ko", "es"},
    "temperature": {"fahrenheit", "celsius"},
    "theme": {"dark", "light"},
    "calendar": {"gregorian", "chinese"},
}


class SettingsAPI:
    def __init__(self, database_path):
        self._database = Path(database_path)

    def _connect(self):
        self._database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._database)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        return connection

    def get_calendar(self, mode, year=None, month=None, anchor=None):
        from calendar_service import CalendarService
        return CalendarService(self._database).month(mode, year, month, anchor)

    def get_calendar_day(self, mode, day):
        from calendar_service import CalendarService
        return CalendarService(self._database).day(mode, day)

    def save_calendar_event(self, day, title, notes='', event_id=None, starts_at=None, ends_at=None):
        from calendar_service import CalendarService
        return CalendarService(self._database).save_event(day, title, notes, event_id, starts_at, ends_at)

    def delete_calendar_event(self, event_id):
        from calendar_service import CalendarService
        return CalendarService(self._database).delete_event(event_id)

    def get_weather(self):
        self._database.parent.mkdir(parents=True, exist_ok=True)
        return get_weather(self._database)

    def get_settings(self):
        settings = DEFAULTS.copy()
        connection = self._connect()
        try:
            for name, value in connection.execute("SELECT name, value FROM settings"):
                if name in CHOICES and value in CHOICES[name]:
                    settings[name] = value
        finally:
            connection.close()
        return settings

    def save_settings(self, settings):
        if not isinstance(settings, dict) or set(settings) != set(DEFAULTS):
            raise ValueError("Invalid preferences")
        for name, value in settings.items():
            if not isinstance(value, str) or value not in CHOICES[name]:
                raise ValueError("Invalid preference value")
        connection = self._connect()
        try:
            with connection:
                connection.executemany(
                    "INSERT INTO settings(name, value) VALUES (?, ?) "
                    "ON CONFLICT(name) DO UPDATE SET value=excluded.value",
                    settings.items(),
                )
        finally:
            connection.close()
        return settings


if __name__ == "__main__":
    import webview

    data_folder = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "MOPA"
    api = SettingsAPI(data_folder / "settings.db")
    page = Path(__file__).resolve().parent / "UI" / "index.html"
    webview.create_window(
        title="MOPA", url=str(page), js_api=api,
        width=1000, height=700, min_size=(600, 450),
    )
    webview.start(http_server=True)
