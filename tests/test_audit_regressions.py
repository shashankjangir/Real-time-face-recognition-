"""Regression cases from the repository safety audit."""
import importlib
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

from src import config
from src.access import DecisionCoordinator
from src.database import DatabaseManager
from src.recognition_engine import RecognitionEngine, RecognizedFace, FaceBox, normalize_vector, unrotate_box


class AuditRegressions(unittest.TestCase):
    def test_attention_rejects_closed_missing_and_failed_landmarks(self):
        engine = RecognitionEngine.__new__(RecognitionEngine)
        closed = [(0, 10), (5, 10), (15, 10), (20, 10), (15, 10), (5, 10)]
        opened = [(0, 10), (5, 5), (15, 5), (20, 10), (15, 15), (5, 15)]
        model = Mock()
        with patch('src.recognition_engine.face_recognition', model), patch('src.recognition_engine.HAS_FACE_RECOGNITION', True):
            for landmarks in ([], [{}], [{'left_eye': closed, 'right_eye': closed}]):
                model.face_landmarks.return_value = landmarks
                self.assertFalse(engine.check_attention(np.zeros((40, 40, 3)), FaceBox(0, 40, 40, 0))[0])
            model.face_landmarks.return_value = [{'left_eye': opened, 'right_eye': opened}]
            self.assertTrue(engine.check_attention(np.zeros((40, 40, 3)), FaceBox(0, 40, 40, 0))[0])
            model.face_landmarks.side_effect = RuntimeError('unavailable')
            self.assertFalse(engine.check_attention(np.zeros((40, 40, 3)), FaceBox(0, 40, 40, 0))[0])

    def test_unrotate_matches_opencv_inverse(self):
        corners = np.array([[60, 10, 1], [80, 10, 1], [80, 30, 1], [60, 30, 1]])
        for angle in (-90, -30, 30, 90, 180):
            inverse = cv2.invertAffineTransform(cv2.getRotationMatrix2D((50, 50), angle, 1))
            points = np.clip(corners @ inverse.T, 0, 100)
            expected = [points[:, 1].min(), points[:, 0].max(), points[:, 1].max(), points[:, 0].min()]
            actual = unrotate_box((10, 80, 30, 60), angle, (100, 100))
            np.testing.assert_allclose([actual.top, actual.right, actual.bottom, actual.left], expected, atol=1)

    def test_throttled_adaptation_keeps_memory_equal_to_database(self):
        db = DatabaseManager(':memory:')
        self.addCleanup(db.close)
        original = np.zeros(128); original[0] = 1
        capture = original.copy(); capture[1] = .1
        capture = normalize_vector(capture)
        identity = db.add_identity('Audit', original.tobytes())
        engine = RecognitionEngine(db)
        coordinator = DecisionCoordinator(db, engine=engine)
        for frame in (1, 2):
            face = RecognizedFace(FaceBox(0, 10, 10, 0), capture, 'Audit', .99, .01, True, identity)
            coordinator.apply(face, frame, 'audit')
            stored = np.frombuffer(db.get_identity_by_id(identity)['encoding'], dtype=np.float64)
            np.testing.assert_allclose(engine.known_matrix[0], stored, atol=1e-7)

    def test_private_routes_authenticate_before_pipeline_access(self):
        web = importlib.import_module('src.app')
        client = web.app.test_client()
        paths = ('/', '/stream.mjpg', '/api/recognition/live', '/api/stats', '/api/logs', '/api/csv', '/api/identities', '/health')
        with patch.object(config, 'ADMIN_ENROLLMENT_TOKEN', 'audit-token'), patch.object(web, 'initialize_pipeline') as init:
            for path in paths:
                for method in ('GET', 'HEAD'):
                    response = client.open(path, method=method)
                    self.assertEqual(response.status_code, 401, path)
                    self.assertIn('Basic', response.headers['WWW-Authenticate'])
            self.assertEqual(client.get('/', auth=('admin', 'wrong')).status_code, 401)
            self.assertEqual(client.get('/', auth=('other', 'audit-token')).status_code, 401)
            init.assert_not_called()
            self.assertEqual(client.get('/', auth=('admin', 'audit-token')).status_code, 200)
            self.assertEqual(client.get('/', headers={'Authorization': 'Bearer audit-token'}).status_code, 200)
            self.assertEqual(client.post('/api/enroll', auth=('admin', 'audit-token'), json={'name': 'Audit'}).status_code, 401)
        with patch.object(config, 'ADMIN_ENROLLMENT_TOKEN', ''):
            self.assertEqual(client.get('/').status_code, 503)

    def test_http_credentials_cover_dashboard_video_and_api(self):
        from threading import Thread
        from urllib.request import HTTPBasicAuthHandler, HTTPPasswordMgrWithDefaultRealm, build_opener
        from werkzeug.serving import make_server

        web = importlib.import_module('src.app')
        runtime = Mock()
        runtime.stream.return_value = iter([b'--frame\r\nContent-Type: image/jpeg\r\n\r\ntest-frame\r\n'])
        db = Mock()
        db.get_all_identities.return_value = []
        with patch.object(config, 'ADMIN_ENROLLMENT_TOKEN', 'audit-token'), patch.object(web, 'initialize_pipeline'), patch.object(web, 'runtime', runtime), patch.object(web, 'db_manager', db):
            server = make_server('127.0.0.1', 0, web.app)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = 'http://127.0.0.1:' + str(server.server_port)
                passwords = HTTPPasswordMgrWithDefaultRealm()
                passwords.add_password(None, base, 'admin', 'audit-token')
                client = build_opener(HTTPBasicAuthHandler(passwords))
                for path, expected in (('/', b'Check face quality'), ('/stream.mjpg', b'test-frame'), ('/api/identities', b'identities')):
                    with client.open(base + path, timeout=5) as response:
                        self.assertEqual(response.status, 200)
                        self.assertEqual(response.headers['Cache-Control'], 'no-store')
                        self.assertIn(expected, response.read())
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()
