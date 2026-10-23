import unittest
from unittest.mock import Mock, patch
import numpy as np
from src.access import DecisionCoordinator
from src.database import DatabaseManager
from src.recognition_engine import RecognizedFace, FaceBox

class FrameDecisionTests(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseManager(':memory:')
        self.addCleanup(self.db.close)
        self.ids = [self.db.add_identity(n, np.ones(128).tobytes()) for n in ('A','B')]
        self.action = Mock()
        self.coordinator = DecisionCoordinator(self.db, self.action)

    def faces(self, unknown=False):
        faces = [RecognizedFace(FaceBox(0,10,10,0), np.ones(128), name, 1, 0, True, ident)
                 for name, ident in zip(('A','B'), self.ids)]
        if unknown:
            faces[-1].is_match = False
            faces[-1].identity_id = None
            faces[-1].name = 'Unknown'
        return faces

    def test_single_person_is_immediate_without_cooldown(self):
        for frame in range(1, 5):
            faces = self.faces()[:1]
            self.coordinator.apply_frame(faces, frame, 's')
            self.assertEqual(faces[0].decision, 'allow')
            self.assertEqual(faces[0].action_outcome, 'succeeded')
            self.assertEqual(self.action.call_count, frame)

    def test_unknown_and_empty_frames_do_not_act(self):
        self.coordinator.apply_frame([], 1, 's')
        unknown = self.faces(True)[1:]
        self.coordinator.apply_frame(unknown, 2, 's')
        self.assertEqual(unknown[0].decision, 'deny')
        self.action.assert_not_called()
        known = self.faces()[:1]
        self.coordinator.apply_frame(known, 3, 's')
        self.assertEqual(known[0].decision, 'allow')
        self.action.assert_called_once()

    def test_multiple_people_are_display_only_without_access_logs(self):
        for frame, unknown in enumerate((False, True, False, True), 1):
            faces = self.faces(unknown)
            self.coordinator.apply_frame(faces, frame, 's')
            self.assertTrue(all(f.decision == 'observe' for f in faces))
            self.assertTrue(all(f.reason == 'multiple_faces_display_only' for f in faces))
        self.action.assert_not_called()
        self.assertEqual(self.db.get_recent_logs(), [])

    def test_multiple_unknown_faces_are_serialized_left_to_right(self):
        from src.recognition_engine import AnnotationOverlay
        u1 = RecognizedFace(FaceBox(0, 40, 40, 10), np.ones(128), 'Unknown', 0, 1, False, None)
        u2 = RecognizedFace(FaceBox(0, 90, 40, 60), np.ones(128), 'Unknown', 0, 1, False, None)
        overlay = AnnotationOverlay()
        overlay.update([u1, u2])
        with patch('src.recognition_engine.cv2.rectangle'), patch('src.recognition_engine.cv2.putText') as text:
            overlay.render(np.zeros((100, 100, 3), dtype=np.uint8))
        labels = [c.args[1] for c in text.call_args_list if c.args and 'Unknown' in str(c.args[1])]
        self.assertIn('Unknown 1', labels[0])
        self.assertIn('Unknown 2', labels[1])

    def test_multiple_face_overlay_colors_and_labels(self):
        from src.recognition_engine import AnnotationOverlay
        from src import config
        faces = self.faces(True)
        self.coordinator.apply_frame(faces, 1, 's')
        overlay = AnnotationOverlay()
        overlay.update(faces)
        with patch('src.recognition_engine.cv2.rectangle') as rectangle, patch('src.recognition_engine.cv2.putText') as text:
            overlay.render(np.zeros((100,100,3),dtype=np.uint8))
        self.assertEqual(rectangle.call_args_list[0].args[3], config.COLOR_KNOWN_FACE)
        self.assertEqual(rectangle.call_args_list[2].args[3], config.COLOR_UNKNOWN_FACE)
        self.assertEqual(text.call_args_list[0].args[1], 'A: RECOGNISED')
        self.assertEqual(text.call_args_list[1].args[1], 'Unknown')

    def test_duplicates_and_old_frames_do_not_confirm(self):
        faces = self.faces()[:1]*2
        for frame in range(1,5):
            self.coordinator.apply_frame(faces,frame,'s')
        self.action.assert_not_called()
        self.assertTrue(all(f.decision == 'observe' for f in faces))
        self.coordinator.apply_frame(self.faces()[:1],5,'s')
        self.coordinator.apply_frame(self.faces()[:1],5,'s')
        self.coordinator.apply_frame(self.faces()[:1],4,'s')
        self.action.assert_called_once()
