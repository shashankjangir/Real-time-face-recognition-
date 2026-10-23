"""History cursor remains stable when new decisions arrive or timestamps tie."""
import importlib
import unittest
from unittest.mock import patch
from src.database import DatabaseManager

web = importlib.import_module('src.app')


class HistoryPaginationTests(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseManager(':memory:')
        self.addCleanup(self.db.close)
        self.enterContext(patch.object(web, 'initialize_pipeline'))
        self.enterContext(patch.object(web, 'db_manager', self.db))
        self.client = web.app.test_client()

    def test_paging_beyond_200_with_new_arrivals(self):
        for i in range(205):
            self.db.log_recognition(None, 'Unknown', 0, status='rejected')
        first = self.client.get('/api/logs?limit=200').get_json()
        self.assertEqual(first['count'], 200)
        self.assertTrue(first['has_more'])
        self.db.log_recognition(None, 'New arrival', 0, status='rejected')
        second = self.client.get(f"/api/logs?limit=200&before_id={first['next_cursor']}").get_json()
        self.assertEqual(second['count'], 5)
        self.assertFalse(second['has_more'])
        ids = [row['id'] for row in first['logs'] + second['logs']]
        self.assertEqual(len(set(ids)), 205)

    def test_equal_timestamps_and_filter(self):
        for name in ('Alice','Bob','Alice','Alice'):
            self.db.log_recognition(None, name, 0, status='rejected')
        with self.db.pool.get_connection() as conn:
            conn.execute('UPDATE access_log SET timestamp=(SELECT MAX(timestamp) FROM access_log)')
        rows = self.db.get_recent_logs(limit=1, name='Alice')
        older = self.db.get_recent_logs(limit=10, name='Alice', before_id=rows[0]['id'])
        self.assertEqual(len(older), 2)
        self.assertTrue(all(row['id'] < rows[0]['id'] for row in older))

    def test_invalid_cursor_and_limit(self):
        for query in ('before_id=no','before_id=-1','limit=0','limit=201','hours=-1'):
            self.assertEqual(self.client.get('/api/logs?'+query).status_code, 400)
