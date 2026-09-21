import unittest
import tempfile
import sqlite3
from datetime import date, timedelta
from calendar_service import CalendarService, months_for
from main import SettingsAPI


class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.database = self.folder.name + '/settings.db'
        self.service = CalendarService(self.database)

    def tearDown(self):
        self.folder.cleanup()

    def test_events_reopen_edit_delete_and_calendar_switch(self):
        event_id = self.service.save_event('2026-09-22', 'Biology exam', 'Room 22')
        reopened = CalendarService(self.database)
        for mode in ['gregorian', 'chinese']:
            report = reopened.month(mode, anchor='2026-09-22')
            day = next(d for d in report['days'] if d['date'] == '2026-09-22')
            self.assertEqual(day['events'][0]['title'], 'Biology exam')
        reopened.save_event('2026-09-22', 'Chemistry exam', 'Room 23', event_id)
        report = reopened.month('gregorian', 2026, '9')
        self.assertEqual(report['days'][21]['events'][0]['title'], 'Chemistry exam')
        reopened.delete_event(event_id)
        self.assertFalse(reopened.month('gregorian', 2026, '9')['days'][21]['events'])

    def test_leap_month_and_year_navigation(self):
        normal = self.service.month('chinese', 2025, '6')
        leap = self.service.month('chinese', 2025, '6L')
        self.assertEqual(normal['next']['month'], '6L')
        self.assertEqual(leap['next']['month'], '7')
        self.assertEqual(leap['days'][0]['date'], '2025-07-25')
        self.assertEqual(self.service.month('chinese', 2026, '6L')['month'], '6')
        self.assertEqual(self.service.month('gregorian', 2026, '12')['next'], {'year': 2027, 'month': '1'})
        self.assertIsNone(self.service.month('gregorian', 1901, '1')['previous'])
        self.assertIsNone(self.service.month('chinese', 2098, '12')['next'])

    def test_holidays_and_leap_day(self):
        lunar = self.service.month('chinese', 2026, '1')
        self.assertEqual(lunar['days'][0]['date'], '2026-02-17')
        self.assertIn('Chinese New Year', ' '.join(lunar['days'][0]['holidays']))
        self.assertIn('Lantern Festival', ' '.join(lunar['days'][14]['holidays']))
        us = self.service.month('gregorian', 2026, '7')
        self.assertIn('Independence Day', ' '.join(us['days'][3]['holidays']))
        self.assertEqual(len(self.service.month('gregorian', 2024, '2')['days']), 29)

    def test_settings_upgrade_and_validation(self):
        api = SettingsAPI(self.database)
        saved = api.get_settings()
        saved.update(language='ja', theme='light', calendar='chinese')
        api.save_settings(saved)
        self.assertEqual(SettingsAPI(self.database).get_settings(), saved)
        with self.assertRaises(ValueError): self.service.save_event('2026-02-30', 'Exam')
        with self.assertRaises(ValueError): self.service.save_event('2026-02-22', '   ')
        with self.assertRaises(ValueError): self.service.month('chinese', 2200, '1')

    def test_month_lengths_contiguous_across_full_supported_range(self):
        previous_end = None
        for year in range(1901, 2099):
            for month in months_for('chinese', year):
                if previous_end is not None:
                    self.assertEqual(month['start'], previous_end + timedelta(days=1))
                previous_end = month['start'] + timedelta(days=month['count'] - 1)


if __name__ == '__main__':
    unittest.main()
