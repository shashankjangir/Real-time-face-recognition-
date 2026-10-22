import time
import threading
import unittest
from unittest.mock import Mock, patch
import numpy as np
from src import config
from src.database import DatabaseManager
from src.recognition_engine import RecognitionEngine, RecognizedFace, FaceBox
from src.runtime import RecognitionRuntime


class ManualCamera:
    backend = object()
    last_error = None
    def __init__(self):
        self.frame_count = 0
        self.frame = None
        self.delivered = None
        self.lock = threading.Lock()
    def start(self): pass
    def stop(self): pass
    def publish(self):
        with self.lock:
            self.frame_count += 1
            self.frame = np.zeros((50,50,3), dtype=np.uint8)
            self.delivered = time.monotonic()
    def get_snapshot(self, timestamped=False):
        with self.lock:
            return self.frame, self.frame_count, self.delivered


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseManager(':memory:')
        self.addCleanup(self.db.close)
        self.engine = RecognitionEngine(self.db)
        self.engine.ensure_model_available = Mock()
        self.engine.process_frame = Mock(return_value=[])
        self.camera = ManualCamera()
        self.runtime = RecognitionRuntime(self.engine, self.camera, record=True)
        self.addCleanup(self.runtime.stop)

    def wait_for(self, condition):
        deadline = time.monotonic()+3
        while not condition() and time.monotonic()<deadline:
            time.sleep(.005)
        self.assertTrue(condition())

    def test_headless_recognition_and_shared_encoding_for_viewers(self):
        with patch.object(config, 'FRAME_SKIP', 1), patch('src.runtime.cv2.imencode', wraps=__import__('cv2').imencode) as encode:
            self.runtime.start()
            self.camera.publish()
            self.wait_for(lambda: self.runtime.snapshot()['counts']['completed']==1 and self.runtime.jpeg is not None)
            viewers = [self.runtime.stream(), self.runtime.stream()]
            chunks = [next(viewer) for viewer in viewers]
            self.assertEqual(chunks[0], chunks[1])
            self.assertEqual(encode.call_count, 1)
            self.assertEqual(self.engine.process_frame.call_count, 1)
            self.camera.publish()
            self.wait_for(lambda: self.runtime.jpeg_id==2 and self.runtime.snapshot()['counts']['completed']==2)
            self.assertEqual(next(viewers[0]), next(viewers[1]))
            self.assertEqual(encode.call_count, 2)
            self.assertEqual(self.engine.process_frame.call_count, 2)
            for viewer in viewers: viewer.close()
            self.runtime.stop()
        for row in self.runtime.records:
            self.assertLessEqual(row['delivered_monotonic'], row['started_monotonic'])
            self.assertLessEqual(row['started_monotonic'], row['completed_monotonic'])

    def test_stale_and_old_completions_never_act(self):
        action = Mock()
        self.runtime.coordinator.action = action
        identity = self.db.add_identity('Alice', np.ones(128).tobytes())
        face = RecognizedFace(FaceBox(0,10,10,0), np.ones(128), 'Alice', 1, 0, True, identity)
        now = time.monotonic()
        self.runtime.complete(2, now, now, [])
        self.runtime.complete(1, now, now, [face])
        self.runtime.complete(3, now-config.MAX_FRAME_AGE_SECONDS-1, now, [face])
        self.assertEqual(self.runtime.latest_committed, 2)
        action.assert_not_called()
        self.assertEqual(self.db.get_recent_logs(), [])
        self.assertEqual(self.runtime.snapshot()['counts']['out_of_order'], 1)
        self.assertEqual(self.runtime.snapshot()['counts']['stale'], 1)

    def test_stale_queued_frame_skips_inference(self):
        with patch.object(config, 'FRAME_SKIP', 1):
            self.runtime.queue.put(np.zeros((2,2,3)), 1, time.monotonic()-10)
            self.runtime.start()
            self.wait_for(lambda: self.runtime.snapshot()['counts']['stale']==1)
            self.engine.process_frame.assert_not_called()

    def test_queue_keeps_newest_timestamped_work(self):
        for number in range(config.FRAME_QUEUE_SIZE+2):
            self.runtime.queue.put(None, number, float(number))
        self.assertEqual(self.runtime.queue.dropped_count, 2)
        self.assertEqual(self.runtime.queue.get()[1:], (2, 2.0))

    def test_idle_latency_is_unavailable(self):
        self.assertIsNone(self.runtime.snapshot()['delivery_to_decision_latency'])
        self.assertIsNone(self.runtime.snapshot()['face_delivery_to_decision_latency'])

    def test_encoder_failure_stops_stream_and_runtime(self):
        with patch('src.runtime.cv2.imencode', return_value=(False, None)):
            self.runtime.start()
            self.camera.publish()
            self.wait_for(lambda: self.runtime.error is not None)
            with self.assertRaises(RuntimeError): self.runtime.check_health()
            with self.assertRaises(StopIteration): next(self.runtime.stream())
