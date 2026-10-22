"""Dashboard delivery, diagnostic authorization and supported autofocus controls."""
import importlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import numpy as np
from src import config
from src.camera import Picamera2Backend, SyntheticBackend
from src.enroll import face_quality_report, assess_face_quality
from src.recognition_engine import FaceBox
web = importlib.import_module('src.app')


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.client = web.app.test_client()
        self.client.environ_base["HTTP_AUTHORIZATION"] = "Bearer test-token"
        self.frame = np.full((120,120,3), 128, dtype=np.uint8)
        self.box = FaceBox(0,120,120,0)
        self.camera = Mock(backend=object())
        self.camera.get_frame.return_value = self.frame
        self.engine = Mock()
        self.engine.detect_and_extract.return_value = [(self.box, np.ones(128))]
        self.init = self.enterContext(patch.object(web, 'initialize_pipeline'))
        self.enterContext(patch.object(web, 'camera_manager', self.camera))
        self.enterContext(patch.object(web, 'recognition_engine', self.engine))
        self.enterContext(patch.object(config, 'ADMIN_ENROLLMENT_TOKEN', 'test-token'))

    def quality(self, token='test-token'):
        return self.client.post('/api/enrollment/quality', headers={'Authorization':'Bearer '+token})

    def test_dashboard_renders_without_camera_and_assets_are_local(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.init.assert_not_called()
        self.assertIn(b'Check face quality', response.data)
        self.assertNotIn(b'fonts.googleapis.com', response.data)
        for path in ['/static/dashboard.css','/static/dashboard.js','/static/fonts/SpaceGrotesk.ttf']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            response.close()

    def test_quality_requires_administrator_before_camera_access(self):
        self.assertEqual(self.quality('wrong').status_code, 401)
        self.init.assert_not_called()
        with patch.object(config, 'ADMIN_ENROLLMENT_TOKEN', ''):
            self.assertEqual(self.quality().status_code, 503)

    def test_report_explains_blur_without_lowering_threshold(self):
        report = self.quality().get_json()
        self.assertEqual(report['score'], .6)
        self.assertEqual(report['threshold'], .7)
        self.assertFalse(report['ready'])
        self.assertEqual(report['components']['sharpness']['value'], 0)
        self.assertEqual(report['components']['brightness']['score'], 1)
        self.assertEqual(report['components']['size']['score'], 1)
        self.assertIn('Sharpness', report['guidance'][0])

    def test_report_uses_same_score_as_enrollment(self):
        frame = np.random.default_rng(4).integers(70,190,(120,120,3),dtype=np.uint8)
        report = face_quality_report(frame, self.box)
        self.assertEqual(report['score'], assess_face_quality(frame, self.box))
        self.assertTrue(report['ready'])

    def test_diagnostics_reject_missing_multiple_and_simulated_faces(self):
        for faces in ([], [(self.box,np.ones(128))]*2):
            self.engine.detect_and_extract.return_value = faces
            result = self.quality().get_json()
            self.assertFalse(result['ready'])
            self.assertIsNone(result['score'])
            self.assertEqual(result['face_count'], len(faces))
        self.camera.backend = SyntheticBackend()
        self.assertEqual(self.quality().status_code, 503)

    def test_missing_frame_and_model_failure_are_reported(self):
        self.camera.get_frame.return_value = None
        self.assertEqual(self.quality().status_code, 503)
        self.camera.get_frame.return_value = self.frame
        self.engine.detect_and_extract.side_effect = RuntimeError('Model failed')
        self.assertEqual(self.quality().status_code, 503)

    def test_brightness_and_size_guidance(self):
        for brightness in (10,250):
            report = face_quality_report(np.full((50,50,3),brightness,dtype=np.uint8),FaceBox(0,50,50,0))
            self.assertTrue(any('dark' in tip or 'bright' in tip for tip in report['guidance']))
            self.assertTrue(any('small' in tip for tip in report['guidance']))

    def test_continuous_focus_only_when_camera_supports_it(self):
        for supported in (True, False):
            camera = Mock()
            camera.camera_controls = {'AfMode': (0,2,0)} if supported else {}
            module = SimpleNamespace(Picamera2=Mock(return_value=camera))
            libcamera = SimpleNamespace(controls=SimpleNamespace(
                AfModeEnum=SimpleNamespace(Auto=1, Continuous=2),
                AfTriggerEnum=SimpleNamespace(Start=0)
            ))
            with patch.dict(sys.modules, {'picamera2':module, 'libcamera':libcamera}):
                backend = Picamera2Backend()
                backend.start()
                self.assertEqual(backend.autofocus_enabled, supported)
            if supported: camera.set_controls.assert_called_once_with({'AfMode':1, 'AfTrigger':0})
            else: camera.set_controls.assert_not_called()

    def test_camera_enables_supported_automatic_exposure_controls(self):
        camera = Mock()
        camera.camera_controls = {'AeEnable': (False,True,True), 'AwbEnable': (False,True,True)}
        module = SimpleNamespace(Picamera2=Mock(return_value=camera))
        with patch.dict(sys.modules, {'picamera2':module}):
            Picamera2Backend().start()
        camera.set_controls.assert_called_once_with({'AeEnable':True, 'AwbEnable':True})

    def test_live_announcements_use_fresh_faces_without_embeddings(self):
        from src.recognition_engine import AnnotationOverlay, RecognizedFace
        import time
        overlay = AnnotationOverlay()
        self.engine.overlay = overlay
        known = RecognizedFace(self.box, np.ones(128), 'Alice', 1, 0, True, 1)
        unknown = RecognizedFace(self.box, np.ones(128), 'Candidate', 0, 1, False, None)
        overlay.update([known, unknown])
        response = self.client.get('/api/recognition/live')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.get_json()['faces'], [
            dict(name='Alice', identity_id=1, recognized=True),
            dict(name='Unknown', identity_id=None, recognized=False)])
        overlay.timestamp = time.time()-2
        self.assertEqual(self.client.get('/api/recognition/live').get_json()['faces'], [])
