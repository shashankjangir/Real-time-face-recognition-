"""Evaluation accounting and independence checks, using controlled test doubles."""
import csv
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import numpy as np

from src import benchmark


class BenchmarkTests(unittest.TestCase):
    def manifest(self, root, overlap=False, duplicate=False):
        images = ['enroll.jpg', 'known.jpg', 'unknown.jpg']
        for i, name in enumerate(images):
            (root / name).write_bytes(bytes([i if not duplicate else 0]))
        path = root / 'manifest.csv'
        with path.open('w', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(['split', 'name', 'image', 'session'])
            writer.writerow(['enroll', 'Alice', images[0], 'day1'])
            writer.writerow(['test', 'Alice', images[1], 'day1' if overlap else 'day2'])
            writer.writerow(['test', 'Unknown', images[2], 'day2'])
        return path

    def test_manifest_requires_independent_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'separate session'):
                benchmark.load_manifest(self.manifest(Path(directory), overlap=True))

    def test_manifest_rejects_identical_content(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'Repeated image'):
                benchmark.load_manifest(self.manifest(Path(directory), duplicate=True))

    def test_manifest_requires_unknown_and_known_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.manifest(Path(directory))
            self.assertEqual(len(benchmark.load_manifest(path)), 3)
            text = path.read_text().replace('test,Unknown', 'test,Bob')
            path.write_text(text)
            with self.assertRaisesRegex(ValueError, 'Test every'):
                benchmark.load_manifest(path)

    def test_accuracy_counts_wrong_identity_and_invalid_capture(self):
        rows = [
            dict(expected='Alice', predicted='Alice', valid_capture=True, correct=True),
            dict(expected='Alice', predicted='Bob', valid_capture=True, correct=False),
            dict(expected='Alice', predicted='Unknown', valid_capture=True, correct=False),
            dict(expected='Unknown', predicted='Alice', valid_capture=True, correct=False),
            dict(expected='Unknown', predicted=None, valid_capture=False, correct=False),
        ]
        result = benchmark.summarize_predictions(rows, 50)
        self.assertEqual(result['accuracy'], 0.2)
        self.assertEqual(result['wrong_identity_predictions'], 1)
        self.assertEqual(result['invalid_captures'], 1)
        self.assertEqual(result['false_acceptance_rate'], 0.5)
        self.assertAlmostEqual(result['false_rejection_rate'], 1 / 3)

    def test_exactly_95_percent_is_not_pass(self):
        rows = [dict(expected='Alice', predicted='Alice', valid_capture=True, correct=i < 19) for i in range(20)]
        result = benchmark.summarize_predictions(rows, 50)
        self.assertEqual(result['accuracy'], 0.95)
        self.assertFalse(result['targets']['accuracy_above_95_percent'])

    def test_missing_model_cannot_use_fallback(self):
        with patch.object(benchmark.recognition, 'HAS_FACE_RECOGNITION', False):
            with self.assertRaises(RuntimeError):
                benchmark.require_real_model()

    def test_pi_mode_refuses_other_computers(self):
        with patch.object(benchmark, 'device_model', return_value='Windows desktop'), patch.object(benchmark, 'CameraManager') as backend:
            with self.assertRaisesRegex(RuntimeError, 'Raspberry Pi 5'):
                benchmark.measure_pi(Mock(), 0.48, 1)
            backend.assert_not_called()

    def test_image_predictions_use_labels_and_strict_detection(self):
        engine = Mock()
        engine.known_names = ['Alice']
        engine.detect_and_extract.side_effect = [ValueError('No face'), [(None, np.ones(128))]]
        engine.match_embedding.return_value = (False, 'Unknown', 0.1, 0.9, None)
        records = [dict(split='test', name=name, image='image', sha256='hash', session='day2') for name in ('Alice', 'Unknown')]
        with patch.object(benchmark, 'read_image', return_value=np.zeros((10, 10, 3))):
            result = benchmark.evaluate_images(records, engine, 0.4)
        self.assertEqual(result['accuracy'], 0.5)
        self.assertEqual(result['invalid_captures'], 1)
        self.assertIsNone(result['hardware_targets'])
        self.assertTrue(all(call.kwargs['strict'] for call in engine.detect_and_extract.call_args_list))
        self.assertEqual(engine.match_embedding.call_args.kwargs['threshold'], 0.4)

    def test_pi_measurement_counts_unique_frames_and_no_face_is_unavailable(self):
        backend = Mock()
        def read():
            time.sleep(0.003)
            return True, np.zeros((20, 20, 3), dtype=np.uint8)
        backend.read.side_effect = read
        from src.database import DatabaseManager
        from src.recognition_engine import RecognitionEngine
        db = DatabaseManager(':memory:')
        self.addCleanup(db.close)
        engine = RecognitionEngine(db)
        with patch.object(benchmark, 'device_model', return_value='Raspberry Pi 5'), patch('src.camera.Picamera2Backend', return_value=backend), patch.object(engine, 'ensure_model_available'), patch.object(engine, 'detect_and_extract', return_value=[]), patch.object(benchmark.config, 'FRAME_SKIP', 1):
            report = benchmark.measure_pi(engine, 0.48, 0.3)
        self.assertGreater(report['unique_frames']['captured'], 0)
        self.assertLessEqual(report['unique_frames']['jpeg_encoded'], report['unique_frames']['captured'])
        ids = [row['frame_id'] for row in report['decisions']]
        self.assertGreater(len(ids), 0)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(report['runtime_metrics']['workers'], benchmark.config.NUM_WORKER_THREADS)
        self.assertIsNone(report['delivery_to_decision_latency'])
        self.assertIsNone(report['targets']['p95_delivery_to_decision_below_300_ms'])
        self.assertIsNone(report['accuracy'])
        backend.stop.assert_called_once()

    def test_unavailable_evaluation_does_not_write_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'result.json'
            with patch.object(benchmark, 'run_full_benchmark', side_effect=RuntimeError('No model')):
                self.assertEqual(benchmark.main(['--manifest', 'missing.csv', '--output', str(output)]), 2)
            self.assertFalse(output.exists())

    def test_failed_target_is_saved_and_returns_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'result.json'
            report = {'mode': 'images', 'targets': {'accuracy_above_95_percent': False}}
            with patch.object(benchmark, 'run_full_benchmark', return_value=report):
                self.assertEqual(benchmark.main(['--manifest', 'manifest.csv', '--output', str(output)]), 1)
            self.assertTrue(output.exists())

    def test_gallery_does_not_sync_live_cache(self):
        engine = Mock()
        db = Mock()
        records = [dict(split='enroll', name='Alice', image='photo')]
        embedding = np.ones(128, dtype=np.float32)
        with patch.object(benchmark, 'RecognitionEngine', return_value=engine), patch.object(benchmark, 'read_image', return_value=np.zeros((10, 10, 3))), patch.object(benchmark, 'validate_enrollment_frame', return_value=(embedding, 0.8)):
            self.assertIs(benchmark.build_gallery(records, db), engine)
        db.add_identity.assert_called_once()
        self.assertEqual(db.add_identity.call_args.kwargs['quality_score'], 0.8)
        engine.reload_identities.assert_called_once()


if __name__ == '__main__':
    unittest.main()
