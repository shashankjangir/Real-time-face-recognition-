"""Exercise detector output with real OpenCV suppression, without model downloads."""
import unittest
from unittest.mock import Mock, patch
import numpy as np
from src.scrfd import SCRFDDetector
from src.recognition_engine import RecognitionEngine


class SCRFDRegressions(unittest.TestCase):
    def test_separate_faces_survive_suppression(self):
        detector = SCRFDDetector.__new__(SCRFDDetector)
        detector.input_size = (640, 640)
        detector.conf_threshold, detector.nms_threshold = .5, .4
        detector._feat_stride_fpn = [8, 16, 32]
        detector._anchor_centers = {}
        detector._use_kps = False
        detector._build_anchors()
        detector.input_name = 'input'
        detector.output_names = list(range(6))
        scores = [np.zeros((n, 1), np.float32) for n in (12800, 3200, 800)]
        boxes = [np.zeros((n, 4), np.float32) for n in (12800, 3200, 800)]
        for i, confidence in ((2*(27*80+27), .9), (2*(27*80+33), .8)):
            scores[0][i] = confidence
            boxes[0][i] = [2, 2, 3, 3]
        detector.session = Mock()
        detector.session.run.return_value = scores + boxes
        faces = detector.detect(np.zeros((640, 640, 3), np.uint8))
        self.assertEqual([face[0] for face in faces], [(200, 240, 240, 200), (200, 288, 240, 248)])

    def test_healthy_empty_result_does_not_use_dlib(self):
        engine = RecognitionEngine.__new__(RecognitionEngine)
        engine.ensure_model_available = Mock()
        engine.last_tilt_angle = 0
        engine.detector = Mock()
        engine.detector.detect.return_value = []
        with patch('src.recognition_engine.face_recognition') as model:
            model.face_locations.return_value = []
            self.assertEqual(engine.detect_and_extract(np.zeros((100, 100, 3), np.uint8)), [])
            model.face_locations.assert_not_called()
            with self.assertRaises(ValueError):
                engine.detect_and_extract(np.zeros((100, 100, 3), np.uint8), strict=True)

    def test_unavailable_detector_uses_dlib(self):
        engine = RecognitionEngine.__new__(RecognitionEngine)
        engine.ensure_model_available = Mock()
        engine.last_tilt_angle = 0
        engine.detector = Mock(session=None)
        with patch('src.recognition_engine.face_recognition') as model:
            model.face_locations.return_value = []
            self.assertEqual(engine.detect_and_extract(np.zeros((100, 100, 3), np.uint8)), [])
            self.assertGreater(model.face_locations.call_count, 0)
