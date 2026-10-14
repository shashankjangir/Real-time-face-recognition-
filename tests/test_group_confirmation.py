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

    def test_group_requires_three_and_action_once_then_cooldown(self):
        with patch('src.access.time.monotonic', return_value=100):
            for frame in (1,2):
                faces = self.faces()
                self.coordinator.apply_frame(faces, frame, 's')
                self.assertTrue(all(f.decision == 'deny' for f in faces))
            faces = self.faces()
            self.coordinator.apply_frame(faces,3,'s')
            self.assertTrue(all(f.decision == 'allow' for f in faces))
            self.assertTrue(all(f.action_outcome == 'succeeded' for f in faces))
            self.action.assert_called_once()
        with patch('src.access.time.monotonic', return_value=101):
            faces = self.faces()
            self.coordinator.apply_frame(faces,4,'s')
            self.assertTrue(all(f.action_outcome == 'cooldown_suppressed' for f in faces))
            self.assertEqual(faces[0].cooldown_remaining,9)
            self.action.assert_called_once()

    def test_unknown_absence_and_group_change_reset_confirmation(self):
        for interrupt in ([], self.faces(True), self.faces()[:1]):
            c = DecisionCoordinator(self.db, self.action)
            c.apply_frame(self.faces(),1,str(id(c)))
            c.apply_frame(self.faces(),2,str(id(c)))
            c.apply_frame(interrupt,3,str(id(c)))
            faces = self.faces()
            c.apply_frame(faces,4,str(id(c)))
            self.assertTrue(all(f.decision == 'deny' for f in faces))
        self.action.assert_not_called()

    def test_duplicates_and_old_frames_do_not_confirm(self):
        faces = self.faces()[:1]*2
        for frame in range(1,5):
            self.coordinator.apply_frame(faces,frame,'s')
        self.action.assert_not_called()
        self.assertTrue(all(f.decision == 'deny' for f in faces))
        self.coordinator.apply_frame(self.faces(),5,'s')
        self.coordinator.apply_frame(self.faces(),5,'s')
        self.coordinator.apply_frame(self.faces(),4,'s')
        self.assertEqual(self.coordinator.streak,1)

    def test_gap_resets_and_cooldown_expires(self):
        for frame, stamp in ((1,100),(2,100.1),(3,100.2),(4,111),(5,111.1),(6,111.2)):
            with patch('src.access.time.monotonic',return_value=stamp):
                self.coordinator.apply_frame(self.faces(),frame,'s')
        self.assertEqual(self.action.call_count,2)
