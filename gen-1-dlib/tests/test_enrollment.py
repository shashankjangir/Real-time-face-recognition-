"""Enrollment rejects invalid captures and requires administrator credentials."""
import importlib
import unittest
from unittest.mock import Mock, patch

import numpy as np

from src import config
from src.camera import SyntheticBackend
from src.enroll import assess_face_quality, validate_enrollment_frame
from src.recognition_engine import FaceBox, RecognitionEngine

web = importlib.import_module('src.app')
recognition = importlib.import_module('src.recognition_engine')


class EnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.client = web.app.test_client()
        self.frame = np.random.RandomState(42).randint(70, 190, (160, 160, 3), dtype=np.uint8)
        self.box = FaceBox(10, 150, 150, 10)
        self.embedding = np.ones(128, dtype=np.float32) / np.sqrt(128)
        self.camera = Mock()
        self.camera.backend = object()
        self.camera.get_frame.return_value = self.frame
        self.engine = Mock()
        self.engine.detect_and_extract.return_value = [(self.box, self.embedding)]
        self.init = self.enterContext(patch.object(web, 'initialize_pipeline'))
        self.enterContext(patch.object(web, 'camera_manager', self.camera))
        self.enterContext(patch.object(web, 'recognition_engine', self.engine))
        self.enterContext(patch.object(config, 'ADMIN_ENROLLMENT_TOKEN', 'test-admin-token'))
        self.save = self.enterContext(patch('src.enroll.enroll_identity', return_value=7))

    def post(self, token='test-admin-token', payload=None):
        headers = {'Authorization': 'Bearer ' + token} if token is not None else {}
        return self.client.post('/api/enroll', json=payload or {'name': 'Alice'}, headers=headers)

    def test_missing_and_invalid_credentials_have_no_side_effects(self):
        for token in (None, '', 'wrong', 'non-ascii-\u00e9'):
            self.assertEqual(self.post(token).status_code, 401)
        self.init.assert_not_called()
        self.save.assert_not_called()

    def test_unconfigured_admin_disables_enrollment(self):
        with patch.object(config, 'ADMIN_ENROLLMENT_TOKEN', ''):
            self.assertEqual(self.post().status_code, 503)
        self.init.assert_not_called()

    def test_invalid_name(self):
        for name in (None, 123, [], '   '):
            self.assertEqual(self.post(payload={'name': name}).status_code, 400)
        self.save.assert_not_called()

    def test_missing_frame(self):
        self.camera.get_frame.return_value = None
        self.assertEqual(self.post().status_code, 422)
        self.save.assert_not_called()

    def test_missing_or_multiple_faces(self):
        for detections in ([], [(self.box, self.embedding)] * 2):
            self.engine.detect_and_extract.return_value = detections
            self.assertEqual(self.post().status_code, 422)
        self.save.assert_not_called()

    def test_low_quality(self):
        self.camera.get_frame.return_value = np.full((160, 160, 3), 128, dtype=np.uint8)
        self.assertEqual(self.post().status_code, 422)
        self.save.assert_not_called()

    def test_invalid_embeddings(self):
        for embedding in (np.zeros(128), np.ones(127), np.full(128, np.nan)):
            self.engine.detect_and_extract.return_value = [(self.box, embedding)]
            self.assertEqual(self.post().status_code, 422)
        self.save.assert_not_called()

    def test_success_persists_measured_quality(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        quality = assess_face_quality(self.frame, self.box)
        self.assertEqual(response.get_json()['quality_score'], quality)
        self.assertEqual(self.save.call_args.kwargs['quality_score'], quality)
        self.engine.detect_and_extract.assert_called_once_with(self.frame, strict=True)
        self.engine.reload_identities.assert_called_once()

    def test_synthetic_camera_is_rejected(self):
        self.camera.backend = SyntheticBackend()
        self.assertEqual(self.post().status_code, 503)
        self.save.assert_not_called()

    def test_model_failure(self):
        self.engine.detect_and_extract.side_effect = RuntimeError('Model unavailable')
        self.assertEqual(self.post().status_code, 503)
        self.save.assert_not_called()

    def test_strict_detector_never_uses_fallback(self):
        db = Mock()
        db.get_all_identities.return_value = []
        engine = RecognitionEngine(db)
        engine.opencv_extractor = Mock()
        with patch.object(recognition, 'HAS_FACE_RECOGNITION', False):
            with self.assertRaises(RuntimeError):
                engine.detect_and_extract(self.frame, strict=True)
        fake_model = Mock()
        with patch.object(recognition, 'HAS_FACE_RECOGNITION', True), patch.object(recognition, 'face_recognition', fake_model, create=True):
            for locations in ([], [(10, 150, 150, 10)] * 2):
                fake_model.face_locations.return_value = locations
                with self.assertRaises(ValueError):
                    engine.detect_and_extract(self.frame, strict=True)
            fake_model.face_encodings.assert_not_called()
        engine.opencv_extractor.detect_face_boxes.assert_not_called()

    def test_shared_validation_for_image_enrollment(self):
        with patch('src.enroll.os.path.exists', return_value=True), patch('src.enroll.cv2.imread', return_value=self.frame), patch('src.enroll.RecognitionEngine', return_value=self.engine):
            self.engine.detect_and_extract.return_value = []
            from src.enroll import enroll_from_image_file
            self.assertFalse(enroll_from_image_file('photo.jpg', 'Alice'))
        self.save.assert_not_called()


if __name__ == '__main__':
    unittest.main()
