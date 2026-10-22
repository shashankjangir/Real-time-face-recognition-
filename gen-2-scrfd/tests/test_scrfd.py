"""
Unit tests for SCRFD ONNX Detector integration in Generation 2.
"""
import unittest
import sys
from unittest.mock import Mock, patch
import numpy as np

if 'cv2' not in sys.modules:
    sys.modules['cv2'] = Mock()

from src.scrfd import SCRFDDetector
from src.recognition_engine import RecognitionEngine, FaceBox


class TestSCRFD(unittest.TestCase):
    def test_anchor_generation(self):
        detector = SCRFDDetector(model_path="nonexistent.onnx")
        detector.input_size = (640, 640)
        detector._build_anchors()

        # Stride 8: (640//8) * (640//8) * 2 anchors = 80 * 80 * 2 = 12800 anchors
        self.assertIn(8, detector._anchor_centers)
        self.assertEqual(detector._anchor_centers[8].shape, (12800, 2))

        # Stride 16: 40 * 40 * 2 = 3200 anchors
        self.assertIn(16, detector._anchor_centers)
        self.assertEqual(detector._anchor_centers[16].shape, (3200, 2))

        # Stride 32: 20 * 20 * 2 = 800 anchors
        self.assertIn(32, detector._anchor_centers)
        self.assertEqual(detector._anchor_centers[32].shape, (800, 2))

    def test_mock_detection_parsing(self):
        detector = SCRFDDetector(model_path="nonexistent.onnx")
        detector.session = Mock()
        detector.input_name = "input"
        # 9 outputs: 3 strides for scores, 3 for bboxes, 3 for kps
        detector.output_names = [f"out_{i}" for i in range(9)]
        detector._use_kps = True
        detector.input_size = (640, 640)
        detector._build_anchors()

        # Create dummy outputs where one anchor in stride 8 has high score
        score_8 = np.zeros((12800, 1), dtype=np.float32)
        score_8[100] = 0.95
        score_16 = np.zeros((3200, 1), dtype=np.float32)
        score_32 = np.zeros((800, 1), dtype=np.float32)

        bbox_8 = np.ones((12800, 4), dtype=np.float32) * 5.0
        bbox_16 = np.zeros((3200, 4), dtype=np.float32)
        bbox_32 = np.zeros((800, 4), dtype=np.float32)

        kps_8 = np.ones((12800, 5, 2), dtype=np.float32) * 2.0
        kps_16 = np.zeros((3200, 5, 2), dtype=np.float32)
        kps_32 = np.zeros((800, 5, 2), dtype=np.float32)

        detector.session.run = Mock(return_value=[
            score_8, score_16, score_32,
            bbox_8, bbox_16, bbox_32,
            kps_8, kps_16, kps_32
        ])

        dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)

        with patch('src.scrfd.cv2.resize', return_value=np.zeros((640, 640, 3), dtype=np.uint8)), \
             patch('src.scrfd.cv2.dnn.NMSBoxes', return_value=np.array([[0]])):
            detections = detector.detect(dummy_img)

        self.assertEqual(len(detections), 1)
        box, conf, kps = detections[0]
        top, right, bottom, left = box
        self.assertGreaterEqual(conf, 0.9)
        self.assertIsNotNone(kps)
        self.assertEqual(kps.shape, (5, 2))


if __name__ == "__main__":
    unittest.main()
