import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from calendar_service import CalendarService


class EventTimesTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.database = self.folder.name + '/settings.db'
        self.service = CalendarService(self.database)

    def tearDown(self):
        self.folder.cleanup()

    def test_migration_preserves_all_day_events(self):
        connection = sqlite3.connect(self.database)
        with connection:
            connection.execute("CREATE TABLE calendar_events (id INTEGER PRIMARY KEY, date TEXT NOT NULL, title TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '')")
            connection.execute("INSERT INTO calendar_events VALUES (7,'2026-09-22','Original exam','Original notes')")
        connection.close()
        with ThreadPoolExecutor(max_workers=2) as executor:
            reports = list(executor.map(lambda _: self.service.day('gregorian','2026-09-22'), range(2)))
        event = reports[0]['events'][0]
        self.assertEqual(event['id'], 7)
        self.assertEqual(event['notes'], 'Original notes')
        self.assertIsNone(event['starts_at'])
        self.assertIsNone(event['ends_at'])

    def test_timed_event_reopen_edit_and_delete(self):
        event_id = self.service.save_event('2026-09-22', 'Exam', 'Bring ID', None, '2026-09-22T09:00', '2026-09-22T10:30')
        reopened = CalendarService(self.database)
        event = reopened.day('gregorian','2026-09-22')['events'][0]
        self.assertEqual(event['starts_at'], '2026-09-22T09:00')
        self.assertEqual(event['ends_at'], '2026-09-22T10:30')
        self.assertEqual(reopened.day('chinese','2026-09-22')['events'][0], event)
        reopened.save_event('2026-09-22','Updated exam','Bring calculator',event_id,'2026-09-22T11:00','2026-09-22T12:00')
        self.assertEqual(reopened.day('gregorian','2026-09-22')['events'][0]['title'],'Updated exam')
        reopened.delete_event(event_id)
        self.assertFalse(reopened.day('gregorian','2026-09-22')['events'])

    def test_cross_month_and_midnight_end(self):
        self.service.save_event('2026-09-30','Overnight','',None,'2026-09-30T23:00','2026-10-01T01:00')
        self.assertEqual(len(self.service.month('gregorian',2026,'10')['days'][0]['events']),1)
        self.service.save_event('2026-09-30','Until midnight','',None,'2026-09-30T22:00','2026-10-01T00:00')
        self.assertEqual(len(self.service.day('gregorian','2026-10-01')['events']),1)

    def test_reject_invalid_time_ranges_without_overwriting(self):
        event_id = self.service.save_event('2026-09-22','Exam')
        for start,end in [('2026-09-22T10:00','2026-09-22T09:00'), ('2026-09-22T09:00','2026-09-22T09:00'),
                          ('2026-09-22T09:00',None), ('2026-09-22T09:00Z','2026-09-22T10:00Z'),
                          ('2026-09-23T09:00','2026-09-23T10:00')]:
            with self.subTest(start=start,end=end), self.assertRaises(ValueError):
                self.service.save_event('2026-09-22','Invalid','',event_id,start,end)
        self.assertEqual(self.service.day('gregorian','2026-09-22')['events'][0]['title'],'Exam')


if __name__ == '__main__':
    unittest.main()
