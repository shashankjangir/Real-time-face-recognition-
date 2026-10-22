"""Regression tests for open-set assignment, not accuracy benchmarks."""
import unittest
import numpy as np
from src.database import DatabaseManager
from src.recognition_engine import RecognitionEngine

class IdentityMatchingTests(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseManager(':memory:')
        self.addCleanup(self.db.close)
        self.first = np.zeros(128, dtype=np.float64)
        self.first[0] = 1
        self.first_id = self.db.add_identity('First', self.first.tobytes())

    def probe(self, cosine_distance):
        v = self.first.copy()
        v[0] = 1-cosine_distance
        v[1] = np.sqrt(1-v[0]**2)
        return v

    def test_unknown_is_not_assigned_to_only_entry(self):
        result = RecognitionEngine(self.db).match_embedding(self.probe(.20))
        self.assertFalse(result[0])
        self.assertEqual(result[1], 'Unknown')
        self.assertIsNone(result[4])

    def test_close_match_keeps_correct_id(self):
        result = RecognitionEngine(self.db).match_embedding(self.probe(.01))
        self.assertTrue(result[0])
        self.assertEqual(result[4], self.first_id)

    def test_duplicate_and_near_tied_entries_are_rejected(self):
        for distance in (0, .01):
            self.db.add_identity('Second', self.probe(distance).tobytes())
            result = RecognitionEngine(self.db).match_embedding(self.first)
            self.assertFalse(result[0])
            self.assertIsNone(result[4])

    def test_best_match_can_be_later_entry(self):
        second = self.probe(.3)
        ident = self.db.add_identity('Second', second.tobytes())
        result = RecognitionEngine(self.db).match_embedding(second)
        self.assertTrue(result[0])
        self.assertEqual(result[4], ident)

    def test_invalid_queries_and_database_rows_cannot_match(self):
        for v in (np.zeros(128), np.full(128, np.nan), np.ones(127)):
            self.assertFalse(RecognitionEngine(self.db).match_embedding(v)[0])
        self.db.add_identity('Broken', np.full(128, np.nan).tobytes())
        engine = RecognitionEngine(self.db)
        self.assertEqual(engine.known_names, ['First'])
        self.assertEqual(engine.match_embedding(self.first)[4], self.first_id)
