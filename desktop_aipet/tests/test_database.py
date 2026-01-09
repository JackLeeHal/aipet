import unittest
import os
import sqlite3
from desktop_aipet.src import database

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.test_db = 'test_aipet.db'
        database.init_db(self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_add_and_get_message(self):
        database.add_message('user', 'hello', self.test_db)
        history = database.get_history(db_path=self.test_db)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0][0], 'user')
        self.assertEqual(history[0][1], 'hello')

    def test_summary(self):
        date = '2023-10-27'
        summary = 'A good day.'
        database.save_summary(date, summary, self.test_db)
        fetched = database.get_summary(date, self.test_db)
        self.assertEqual(fetched, summary)

    def test_get_messages_for_date(self):
        database.add_message('user', 'msg1', self.test_db) # Today
        # Cannot easily mock CURRENT_TIMESTAMP in sqlite without custom function or passing time
        # So I will just check if it returns something
        import datetime
        today = datetime.date.today().strftime('%Y-%m-%d')
        msgs = database.get_messages_for_date(today, self.test_db)
        self.assertTrue(len(msgs) >= 1)

if __name__ == '__main__':
    unittest.main()
