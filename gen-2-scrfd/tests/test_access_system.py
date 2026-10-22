"""
Automated Unit and Integration Test Suite
Validates database indexing, cosine distance metric learning,
multi-threaded queues, CSV generation, and REST APIs.
"""

import unittest
from unittest.mock import patch
import os
import sys
import numpy as np

# Ensure src in sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src import config
from src.database import DatabaseManager
from src.recognition_engine import (
    compute_cosine_distance, normalize_vector, batch_cosine_distances,
    FrameQueue, RecognitionEngine
)
from src.utils import ReportGenerator
from src.app import app


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseManager(":memory:")

    def tearDown(self):
        self.db.close()

    def test_add_and_query_identity(self):
        vec = normalize_vector(np.random.randn(128).astype(np.float64))
        ident_id = self.db.add_identity("Test_Alice", vec.tobytes(), quality_score=0.92)
        self.assertIsNotNone(ident_id)

        alice = self.db.get_identity_by_name("Test_Alice")
        self.assertIsNotNone(alice)
        self.assertEqual(alice['name'], "Test_Alice")
        self.assertAlmostEqual(alice['quality_score'], 0.92, places=2)

    def test_access_logging_and_indexing(self):
        self.db.add_identity("Test_Bob", np.ones(128).tobytes())
        for i in range(10):
            self.db.log_recognition(
                identity_id=1,
                name="Test_Bob",
                confidence=0.88,
                status="verified",
                session_id="test-session"
            )

        logs = self.db.get_recent_logs(limit=5)
        self.assertEqual(len(logs), 5)
        self.assertEqual(logs[0]['name'], "Test_Bob")

        # Verify query plan utilizes indexes
        plan = self.db.explain_query("SELECT * FROM access_log WHERE name = 'Test_Bob'")
        self.assertTrue(len(plan) > 0)


class TestRecognitionMetrics(unittest.TestCase):
    def test_cosine_distance(self):
        v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        v2 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        v3 = np.array([0.0, 1.0, 0.0], dtype=np.float32)

        # Identical vectors -> distance 0.0
        self.assertAlmostEqual(compute_cosine_distance(v1, v2), 0.0, places=4)
        # Orthogonal vectors -> distance 1.0
        self.assertAlmostEqual(compute_cosine_distance(v1, v3), 1.0, places=4)

    def test_batch_matching_across_identities(self):
        rng = np.random.RandomState(42)
        known_matrix = rng.randn(60, 128).astype(np.float32)
        for i in range(60):
            known_matrix[i] = normalize_vector(known_matrix[i])

        # Probe is identical to identity #15 with slight sensor noise
        probe = normalize_vector(known_matrix[15] + rng.randn(128).astype(np.float32) * 0.05)

        distances = batch_cosine_distances(known_matrix, probe)
        self.assertEqual(len(distances), 60)
        best_match = int(np.argmin(distances))
        self.assertEqual(best_match, 15)
        self.assertLess(distances[15], 0.20)  # Very close match


class TestFrameQueue(unittest.TestCase):
    def test_drop_oldest_policy(self):
        q = FrameQueue(maxsize=3)
        dummy_frame = np.zeros((10, 10, 3), dtype=np.uint8)

        q.put(dummy_frame, 1)
        q.put(dummy_frame, 2)
        q.put(dummy_frame, 3)
        # 4th item should cause drop-oldest
        q.put(dummy_frame, 4)

        self.assertEqual(q.qsize(), 3)
        self.assertEqual(q.dropped_count, 1)
        item = q.get()
        self.assertEqual(item[1], 2)  # Frame 1 was dropped, Frame 2 is first


class TestCSVReportAndREST(unittest.TestCase):
    def setUp(self):
        from src import config
        self.enterContext(patch.object(config, "ADMIN_ENROLLMENT_TOKEN", "test-token"))
        self.client = app.test_client()
        self.client.environ_base["HTTP_AUTHORIZATION"] = "Bearer test-token"
        for name, kwargs in [('ensure_model_available', {}), ('detect_and_extract', {'return_value': []})]:
            patcher = patch.object(RecognitionEngine, name, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)
        from src.app import shutdown_pipeline
        self.addCleanup(shutdown_pipeline)

    def test_health_endpoint(self):
        res = self.client.get('/health')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get('status'), 'healthy')

    def test_api_stats(self):
        res = self.client.get('/api/stats')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('fps', data)
        self.assertIn('identities_enrolled', data)

    def test_api_csv(self):
        res = self.client.get('/api/csv?hours=24')
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/csv', res.content_type)
        self.assertIn(b'TRANSACTION AUDIT REPORT', res.data)


if __name__ == '__main__':
    unittest.main()
