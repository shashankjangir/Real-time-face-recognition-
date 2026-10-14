import unittest
from unittest.mock import Mock, patch
import numpy as np
from src.access import DecisionCoordinator
from src.database import DatabaseManager
from src.recognition_engine import RecognizedFace, FaceBox

class GroupConfirmationTests(unittest.TestCase):
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

    def test_single_person_requires_three_and_action_once_then_cooldown(self):
        with patch('src.access.time.monotonic', return_value=100):
            for frame in (1,2):
                faces = self.faces()[:1]
                self.coordinator.apply_frame(faces, frame, 's')
                self.assertTrue(all(f.decision == 'deny' for f in faces))
            faces = self.faces()[:1]
            self.coordinator.apply_frame(faces,3,'s')
            self.assertTrue(all(f.decision == 'allow' for f in faces))
            self.assertTrue(all(f.action_outcome == 'succeeded' for f in faces))
            self.action.assert_called_once()
        with patch('src.access.time.monotonic', return_value=101):
            faces = self.faces()[:1]
            self.coordinator.apply_frame(faces,4,'s')
            self.assertTrue(all(f.action_outcome == 'cooldown_suppressed' for f in faces))
            self.assertEqual(faces[0].cooldown_remaining,9)
            self.action.assert_called_once()

    def test_unknown_absence_and_multiple_faces_reset_confirmation(self):
        for index, interrupt in enumerate(([], self.faces(True)[1:], self.faces())):
            c = DecisionCoordinator(self.db, self.action)
            session = str(index)
            c.apply_frame(self.faces()[:1],1,session)
            c.apply_frame(self.faces()[:1],2,session)
            c.apply_frame(interrupt,3,session)
            faces = self.faces()[:1]
            c.apply_frame(faces,4,session)
            self.assertEqual(faces[0].decision, 'deny')
            self.assertEqual(c.streak, 1)
        self.action.assert_not_called()

    def test_multiple_people_are_display_only_without_access_logs(self):
        for frame, unknown in enumerate((False, True, False, True), 1):
            faces = self.faces(unknown)
            self.coordinator.apply_frame(faces, frame, 's')
            self.assertTrue(all(f.decision == 'observe' for f in faces))
            self.assertTrue(all(f.reason == 'multiple_faces_display_only' for f in faces))
            self.assertEqual(self.coordinator.streak, 0)
        self.action.assert_not_called()
        self.assertEqual(self.db.get_recent_logs(), [])

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
        self.assertEqual(self.coordinator.streak,1)

    def test_gap_resets_and_cooldown_expires(self):
        for frame, stamp in ((1,100),(2,100.1),(3,100.2),(4,111),(5,111.1),(6,111.2)):
            with patch('src.access.time.monotonic',return_value=stamp):
                self.coordinator.apply_frame(self.faces()[:1],frame,'s')
        self.assertEqual(self.action.call_count,2)
