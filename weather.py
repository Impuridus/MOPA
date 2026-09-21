"""Current conditions for Storrs Mansfield using Open-Meteo's public API."""
import json
import math
import sqlite3
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _validate(data):
    current = data['current']
    if not isinstance(current['time'], str):
        raise ValueError('Missing weather time')
    for key in ('temperature_2m', 'apparent_temperature', 'relative_humidity_2m',
                'weather_code', 'wind_speed_10m', 'wind_direction_10m'):
        value = current.get(key)
        if value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value)):
            raise ValueError('Invalid weather reading')
    if current.get('temperature_2m') is None:
        raise ValueError('Temperature unavailable')
    for key in ('time', 'temperature_2m_max', 'temperature_2m_min'):
        if not isinstance(data['daily'][key], list) or not data['daily'][key]:
            raise ValueError('Missing daily forecast')
    return data


def fetch_weather():
    params = {
        'latitude': 41.80843, 'longitude': -72.24952,
        'current': 'temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m,is_day',
        'daily': 'temperature_2m_max,temperature_2m_min',
        'temperature_unit': 'fahrenheit', 'wind_speed_unit': 'mph',
        'timezone': 'America/New_York', 'forecast_days': 1,
    }
    request = Request('https://api.open-meteo.com/v1/forecast?' + urlencode(params),
                      headers={'User-Agent': 'MOPA/1.0', 'Accept': 'application/json'})
    with urlopen(request, timeout=15) as response:
        return _validate(json.load(response))


def get_weather(database):
    """Reuse recent data; keep the last successful report for offline viewing."""
    cached = None
    connection = None
    try:
        connection = sqlite3.connect(database)
        connection.execute('CREATE TABLE IF NOT EXISTS weather_cache (id INTEGER PRIMARY KEY, payload TEXT, fetched REAL)')
        row = connection.execute('SELECT payload, fetched FROM weather_cache WHERE id=1').fetchone()
        if row:
            try:
                cached = {'data': _validate(json.loads(row[0])), 'fetched': row[1]}
            except (ValueError, KeyError, TypeError):
                pass
        if cached and 0 <= time.time() - cached['fetched'] < 600:
            return {**cached, 'stale': False, 'cache_saved': True}
        try:
            data = fetch_weather()
        except (OSError, ValueError, KeyError, TypeError):
            if cached:
                return {**cached, 'stale': True, 'cache_saved': True}
            raise RuntimeError('Weather unavailable. Check your connection and try again.') from None
        result = {'data': data, 'fetched': time.time(), 'stale': False, 'cache_saved': True}
        try:
            with connection:
                connection.execute('INSERT OR REPLACE INTO weather_cache VALUES (1, ?, ?)',
                                   (json.dumps(data), result['fetched']))
        except sqlite3.Error:
            result['cache_saved'] = False
        return result
    except sqlite3.Error:
        return {'data': fetch_weather(), 'fetched': time.time(), 'stale': False, 'cache_saved': False}
    finally:
        if connection is not None:
            connection.close()
