import unittest
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch
import numpy as np
from src import recognition_engine as recognition
from src.recognition_engine import RecognitionEngine, RecognizedFace, FaceBox, RecognitionWorker, FrameQueue
from src.camera import CameraManager, Picamera2Backend
from src.database import DatabaseManager
from src.access import DecisionCoordinator


class PipelineSafetyTests(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseManager(':memory:')
        self.addCleanup(self.db.close)
        self.encoding = np.ones(128, dtype=np.float64)
        self.alice = self.db.add_identity('Alice', self.encoding.tobytes())

    def face(self, matched=True):
        return RecognizedFace(FaceBox(0, 10, 10, 0), self.encoding, 'Alice' if matched else 'Unknown',
                              .44, .40 if matched else .55, matched, self.alice if matched else None)

    def test_update_returns_actual_identity(self):
        self.db.add_identity('Bob', self.encoding.tobytes())
        self.assertEqual(self.db.add_identity('Alice', self.encoding.tobytes()), self.alice)
        with self.db.pool.get_connection() as conn:
            self.assertEqual(conn.execute('SELECT identity_id FROM enrollment_history ORDER BY id DESC').fetchone()[0], self.alice)

    def test_history_failure_rolls_back_update_and_insert(self):
        with self.db.pool.get_connection() as conn:
            conn.execute("CREATE TRIGGER reject_history BEFORE INSERT ON enrollment_history BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        for name in ('Alice', 'New'):
            with self.assertRaises(sqlite3.IntegrityError):
                self.db.add_identity(name, b'changed')
        self.assertEqual(self.db.get_identity_by_name('Alice')['encoding'], self.encoding.tobytes())
        self.assertIsNone(self.db.get_identity_by_name('New'))

    def test_foreign_keys_on_every_connection_and_delete_behavior(self):
        connections = [self.db.pool.available.get() for _ in range(self.db.pool.pool_size)]
        try:
            for conn in connections:
                self.assertEqual(conn.execute('PRAGMA foreign_keys').fetchone()[0], 1)
        finally:
            for conn in connections:
                self.db.pool.available.put(conn)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.log_recognition(999, 'Invalid', .5)
        self.db.log_recognition(self.alice, 'Alice', .8)
        self.db.delete_identity(self.alice)
        with self.db.pool.get_connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM enrollment_history').fetchone()[0], 0)
        self.assertIsNone(self.db.get_recent_logs()[0]['identity_id'])

    def test_no_face_returns_empty_without_encoding(self):
        model = Mock()
        model.face_locations.return_value = []
        with patch.object(recognition, 'HAS_FACE_RECOGNITION', True), patch.object(recognition, 'face_recognition', model):
            self.assertEqual(RecognitionEngine(self.db).detect_and_extract(np.zeros((20,20,3),dtype=np.uint8)), [])
        model.face_encodings.assert_not_called()

    def test_model_missing_and_failure_are_explicit(self):
        engine = RecognitionEngine(self.db)
        with patch.object(recognition, 'HAS_FACE_RECOGNITION', False), self.assertRaises(RuntimeError):
            engine.detect_and_extract(None)
        model = Mock()
        model.face_locations.side_effect = OSError('broken model')
        with patch.object(recognition, 'HAS_FACE_RECOGNITION', True), patch.object(recognition, 'face_recognition', model), self.assertRaises(RuntimeError):
            engine.detect_and_extract(np.zeros((20,20,3),dtype=np.uint8))

    def test_picamera_preserves_bgr_channels(self):
        backend = Picamera2Backend()
        backend.picam2 = Mock()
        expected = np.array([[[1,2,250]]], dtype=np.uint8)
        backend.picam2.capture_array.return_value = expected
        ok, actual = backend.read()
        self.assertTrue(ok)
        np.testing.assert_array_equal(actual, expected)

    def test_camera_failure_never_falls_back_to_simulation(self):
        with patch('src.camera.Picamera2Backend.start', side_effect=RuntimeError('missing')), patch('src.camera.OpenCVBackend.start', side_effect=RuntimeError('missing')), patch('src.camera.SyntheticBackend.start') as synthetic:
            for backend in ('auto', 'picamera2', 'opencv'):
                with self.assertRaises(RuntimeError):
                    CameraManager(backend)
            synthetic.assert_not_called()

    def test_runtime_camera_failure_clears_frame(self):
        backend = Mock()
        backend.read.return_value = (False, None)
        with patch.object(CameraManager, '_create_backend', return_value=backend):
            manager = CameraManager()
        manager.latest_frame = np.ones((2,2,3))
        manager.running = True
        manager._capture_loop()
        with self.assertRaises(RuntimeError):
            manager.get_frame()
        self.assertIsNone(manager.latest_frame)

    def test_shared_deduplication_without_cooldown(self):
        action = Mock()
        coordinator = DecisionCoordinator(self.db, action)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: coordinator.apply(self.face(), 1, 'test'), range(12)))
        coordinator.apply(self.face(), 2, 'test')
        self.assertEqual(action.call_count, 2)
        logs = self.db.get_recent_logs()
        self.assertEqual(len(logs), 2)
        self.assertEqual({x['action_outcome'] for x in logs}, {'succeeded'})
        self.assertTrue(all(x['decision']=='allow' for x in logs))
        engine = RecognitionEngine(self.db)
        workers = [RecognitionWorker(i, FrameQueue(), engine, self.db, 'test') for i in range(4)]
        self.assertTrue(all(w.coordinator is workers[0].coordinator for w in workers))

    def test_every_rejection_records_reason(self):
        coordinator = DecisionCoordinator(self.db, Mock())
        for frame_id in (1,2):
            result = coordinator.apply(self.face(False), frame_id, 'test')
            self.assertEqual(result.decision, 'deny')
        logs = self.db.get_recent_logs()
        self.assertEqual(len(logs), 2)
        self.assertTrue(all(x['reason']=='identity_not_matched' and x['action_outcome']=='not_requested' for x in logs))
        coordinator.action.assert_not_called()

    def test_multiple_faces_and_simulation_deny(self):
        action = Mock()
        coordinator = DecisionCoordinator(self.db, action)
        self.assertEqual(coordinator.apply(self.face(), 1, 'test', multiple_faces=True).reason, 'multiple_faces')
        coordinator.enabled = False
        self.assertEqual(coordinator.apply(self.face(), 2, 'test').decision, 'deny')
        action.assert_not_called()

    def test_failed_and_unconfigured_action_are_honest(self):
        coordinator = DecisionCoordinator(self.db, Mock(side_effect=OSError('relay disconnected')))
        self.assertEqual(coordinator.apply(self.face(), 1, 'test').action_outcome, 'failed')
        self.assertIn('relay disconnected', self.db.get_recent_logs()[0]['action_detail'])
        coordinator.action = None
        self.assertEqual(coordinator.apply(self.face(), 2, 'test').action_outcome, 'not_configured')

    def test_audit_failure_prevents_action(self):
        action = Mock()
        coordinator = DecisionCoordinator(self.db, action)
        with patch.object(self.db, 'log_recognition', side_effect=sqlite3.OperationalError('disk full')), self.assertRaises(sqlite3.OperationalError):
            coordinator.apply(self.face(), 1, 'test')
        action.assert_not_called()

    def test_health_reports_model_failure(self):
        from src import app as web
        with patch.object(web, 'pipeline_initialized', False), patch.object(RecognitionEngine, 'ensure_model_available', side_effect=RuntimeError('model missing')):
            response = web.app.test_client().get('/health')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()['status'], 'unhealthy')

    def test_fault_latches_deny_for_other_workers(self):
        action = Mock()
        coordinator = DecisionCoordinator(self.db, action)
        coordinator.fault(1, 'test', 'camera lost')
        face = coordinator.apply(self.face(), 2, 'test')
        self.assertEqual((face.decision, face.reason), ('deny', 'pipeline_failure'))
        action.assert_not_called()

    def test_old_schema_migration_preserves_records(self):
        import tempfile
        from pathlib import Path
        from src.database import SCHEMA_SQL
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'old.db')
            with sqlite3.connect(path) as conn:
                conn.executescript(SCHEMA_SQL)
                conn.execute("INSERT INTO access_log(name,timestamp,confidence,status) VALUES ('Old',datetime('now'),.5,'rejected')")
            conn.close()
            db = DatabaseManager(path)
            try:
                with db.pool.get_connection() as conn:
                    record = conn.execute('SELECT * FROM access_log').fetchone()
                    self.assertEqual(record['name'], 'Old')
                    self.assertIsNone(record['action_outcome'])
                    self.assertIn('event_key', record.keys())
            finally:
                db.close()

    def test_overlay_does_not_revert_to_older_frame(self):
        from src.recognition_engine import AnnotationOverlay
        overlay = AnnotationOverlay()
        overlay.update([], frame_id=2)
        overlay.update([self.face()], frame_id=1)
        self.assertEqual(overlay.get_active_faces(), [])

    def test_worker_uses_same_decision_for_overlay_and_log(self):
        engine = RecognitionEngine(self.db)
        engine.process_frame = Mock(return_value=[self.face(False)])
        queue = FrameQueue()
        worker = RecognitionWorker(1, queue, engine, self.db, 'worker-test')
        queue.get = Mock(side_effect=[(np.zeros((2,2,3)), 1), None])
        original_update = engine.overlay.update
        def update(*args, **kwargs):
            original_update(*args, **kwargs)
            worker.stop()
        engine.overlay.update = update
        worker.run()
        face = engine.overlay.get_active_faces()[0]
        log = self.db.get_recent_logs()[0]
        self.assertEqual((face.decision, face.reason, face.action_outcome),
                         (log['decision'], log['reason'], log['action_outcome']))
