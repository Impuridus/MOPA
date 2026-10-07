"""Start MOPA and store preferences outside the Git repository."""
import os
import sqlite3
from pathlib import Path
from weather import get_weather, search_cities
import ctypes
from ctypes import wintypes


DEFAULTS = {"language": "en", "temperature": "fahrenheit", "theme": "dark", "calendar": "gregorian"}
CHOICES = {
    "language": {"en", "zh-Hans", "zh-Hant", "ja", "ko", "es"},
    "temperature": {"fahrenheit", "celsius"},
    "theme": {"dark", "light"},
    "calendar": {"gregorian", "chinese"},
}

def set_title_bar_theme(window, theme):
    if window is None or window.native is None:
        return

    hwnd = wintypes.HWND(window.native.Handle.ToInt64())

    set_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
    set_attribute.argtypes = [
        wintypes.HWND,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    set_attribute.restype = ctypes.c_long

    is_dark = theme == "dark"

    dark_mode = wintypes.BOOL(is_dark)
    background = wintypes.DWORD(
        0x00171717 if is_dark else 0x00F5F5F5
    )
    text_color = wintypes.DWORD(
        0x00ECECEC if is_dark else 0x00202020
    )

    attributes = [
        (20, dark_mode),
        (35, background),
        (36, text_color),
    ]

    for attribute, value in attributes:
        result = set_attribute(
            hwnd,
            attribute,
            ctypes.byref(value),
            ctypes.sizeof(value),
        )

        if result != 0:
            print(f"Could not update title-bar attribute {attribute}: {result}")
    



class SettingsAPI:
    def __init__(self, database_path):
        self._database = Path(database_path)
        self._window = None

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

    def search_cities(self, query):
        return search_cities(query)
    
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
        set_title_bar_theme(self._window, settings["theme"])
        return settings


if __name__ == "__main__":
    import webview

    data_folder = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "MOPA"
    api = SettingsAPI(data_folder / "settings.db")
    page = Path(__file__).resolve().parent / "UI" / "index.html"
    window = webview.create_window(
        title="MOPA", url=str(page), js_api=api,
        width=1000, height=700, min_size=(600, 450),
    )
    api._window = window
    def apply_saved_title_bar_theme():
        save_settings = api.get_settings()
        set_title_bar_theme(window, save_settings["theme"])

    window.events.shown += apply_saved_title_bar_theme
    webview.start(http_server=True)
