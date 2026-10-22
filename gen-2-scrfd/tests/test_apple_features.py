"""
Unit tests verifying Apple Face ID architectural features:
1. EAR Liveness / Attention check
2. Multi-sample centroid template enrollment
3. Continuous template adaptation on confident match
"""
import unittest
import sys
from unittest.mock import Mock, patch

# Mock cv2 if running on a host environment without opencv installed
if 'cv2' not in sys.modules:
    sys.modules['cv2'] = Mock()

import numpy as np

from src import config
from src.database import DatabaseManager
from src.recognition_engine import (
    calculate_ear, normalize_vector, RecognitionEngine, RecognizedFace, FaceBox
)
from src.enroll import create_robust_template, enroll_identity
from src.access import DecisionCoordinator


class AppleFeaturesTest(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseManager(":memory:")
        self.addCleanup(self.db.close)

    def test_ear_calculation_and_attention(self):
        # Open eye coordinates (aspect ratio > 0.25)
        open_eye = [(0, 10), (5, 5), (15, 5), (20, 10), (15, 15), (5, 15)]
        ear_open = calculate_ear(open_eye)
        self.assertGreater(ear_open, 0.25)

        # Closed eye coordinates (almost flat vertically)
        closed_eye = [(0, 10), (5, 10), (15, 10), (20, 10), (15, 10), (5, 10)]
        ear_closed = calculate_ear(closed_eye)
        self.assertLess(ear_closed, 0.15)

    def test_attention_required_blocks_access(self):
        ident_id = self.db.add_identity("Alice", np.ones(128).tobytes())
        action = Mock()
        coordinator = DecisionCoordinator(self.db, action)

        # Matched identity with attention (eyes open)
        attentive_face = RecognizedFace(
            box=FaceBox(0, 10, 10, 0),
            encoding=np.ones(128),
            name="Alice",
            confidence=0.9,
            match_distance=0.03,
            is_match=True,
            identity_id=ident_id,
            is_attentive=True
        )
        coordinator.apply(attentive_face, frame_id=1, session_id="test")
        self.assertEqual(attentive_face.decision, "allow")
        self.assertEqual(attentive_face.reason, "identity_matched")
        action.assert_called_once()

        action.reset_mock()

        # Matched identity without attention (eyes closed / photo)
        inattentive_face = RecognizedFace(
            box=FaceBox(0, 10, 10, 0),
            encoding=np.ones(128),
            name="Alice",
            confidence=0.9,
            match_distance=0.03,
            is_match=True,
            identity_id=ident_id,
            is_attentive=False
        )
        coordinator.apply(inattentive_face, frame_id=2, session_id="test")
        self.assertEqual(inattentive_face.decision, "deny")
        self.assertEqual(inattentive_face.reason, "attention_required")
        action.assert_not_called()

    def test_multi_sample_angular_enrollment(self):
        rng = np.random.RandomState(42)
        # Simulate 5 angular captures of the same person with small deviations
        base = normalize_vector(rng.randn(128))
        samples = [normalize_vector(base + rng.randn(128) * 0.05) for _ in range(5)]

        template = create_robust_template(samples)
        self.assertEqual(template.shape, (128,))
        self.assertAlmostEqual(float(np.linalg.norm(template)), 1.0, places=4)

        # Enrolling with a list of samples produces a valid database identity
        ident_id = enroll_identity("Bob", samples, quality_score=0.95, db_manager=self.db)
        bob = self.db.get_identity_by_id(ident_id)
        self.assertEqual(bob["name"], "Bob")
        stored_vec = np.frombuffer(bob["encoding"], dtype=np.float64)
        np.testing.assert_allclose(stored_vec, template, atol=1e-5)

    def test_continuous_template_adaptation(self):
        rng = np.random.RandomState(101)
        original = normalize_vector(rng.randn(128))
        ident_id = self.db.add_identity("Charlie", original.tobytes())

        # Highly confident match (< threshold / 2) with slight deviation
        fresh_capture = normalize_vector(original + rng.randn(128) * 0.02)
        action = Mock()
        coordinator = DecisionCoordinator(self.db, action)

        face = RecognizedFace(
            box=FaceBox(0, 10, 10, 0),
            encoding=fresh_capture,
            name="Charlie",
            confidence=0.95,
            match_distance=0.02,  # Well below 0.04
            is_match=True,
            identity_id=ident_id,
            is_attentive=True
        )
        coordinator.apply(face, frame_id=1, session_id="test")

        # Verify the template adapted towards fresh_capture
        row = self.db.get_identity_by_id(ident_id)
        adapted_vec = np.frombuffer(row["encoding"], dtype=np.float64)

        # Expected: 0.95 * original + 0.05 * fresh_capture
        expected = normalize_vector(0.95 * original + 0.05 * fresh_capture)
        np.testing.assert_allclose(adapted_vec, expected, atol=1e-5)

    def test_sqlite_protection_rate_limiting(self):
        rng = np.random.RandomState(42)
        original = normalize_vector(rng.randn(128))
        ident_id = self.db.add_identity("RateLimitUser", original.tobytes())
        fresh1 = normalize_vector(original + rng.randn(128) * 0.01)
        fresh2 = normalize_vector(original + rng.randn(128) * 0.02)

        # First adaptation writes to SQLite
        self.assertTrue(self.db.adapt_identity_template(ident_id, fresh1, min_interval=10.0))

        # Immediate second adaptation is throttled to protect SQLite
        self.assertFalse(self.db.adapt_identity_template(ident_id, fresh2, min_interval=10.0))

        # Explicit min_interval=0 overrides throttling
        self.assertTrue(self.db.adapt_identity_template(ident_id, fresh2, min_interval=0.0))

    def test_tilt_invariant_detection(self):
        engine = RecognitionEngine(self.db)
        engine.ensure_model_available = Mock()

        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        loc = (100, 300, 250, 150)
        emb = np.ones(128, dtype=np.float32) / np.sqrt(128)

        # Simulate face_locations only detecting face when rotated by 45 deg
        def fake_locations(img, model='hog'):
            # Return face box when angle was applied
            return [loc] if engine.last_tilt_angle != 0 or getattr(img, 'is_tilted', False) else []

        mock_fr = Mock()
        mock_fr.face_locations = Mock(side_effect=fake_locations)
        mock_fr.face_encodings = Mock(return_value=[emb])

        with patch('src.recognition_engine.face_recognition', mock_fr), \
             patch('src.recognition_engine.HAS_FACE_RECOGNITION', True), \
             patch('src.recognition_engine.cv2.cvtColor', side_effect=lambda f, c: f), \
             patch('src.recognition_engine.cv2.getRotationMatrix2D', return_value=np.eye(2, 3, dtype=np.float32)), \
             patch('src.recognition_engine.cv2.warpAffine', side_effect=lambda img, m, s: img):
            mock_fr.face_locations = Mock(side_effect=[[], [loc], [loc]])

            faces = engine.detect_and_extract(dummy_frame)
            self.assertEqual(len(faces), 1)
            box, vec = faces[0]
            self.assertEqual(vec.shape, (128,))
            self.assertEqual(engine.last_tilt_angle, -30)  # First angle in candidates that succeeded

            # Second pass: uses cached last_tilt_angle directly on pass 1 (0ms search penalty)
            mock_fr.face_locations = Mock(return_value=[loc])
            faces_pass2 = engine.detect_and_extract(dummy_frame)
            self.assertEqual(len(faces_pass2), 1)
            self.assertEqual(engine.last_tilt_angle, -30)
            mock_fr.face_locations.assert_called_once()


if __name__ == "__main__":
    unittest.main()
