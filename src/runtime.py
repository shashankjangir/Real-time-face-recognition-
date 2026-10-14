"""Shared capture-to-decision and single-encoder runtime for web and Pi evaluation."""
from collections import deque
import threading
import time
import uuid
import cv2
import numpy as np
from . import config
from .access import DecisionCoordinator
from .camera import SyntheticBackend
from .recognition_engine import FrameQueue, RecognitionWorker


def distribution(values):
    if not values:
        return None
    return dict(mean_ms=float(np.mean(values)), median_ms=float(np.median(values)),
                p95_ms=float(np.percentile(values, 95)), max_ms=float(max(values)))


class RecognitionRuntime:
    def __init__(self, engine, camera, session_id=None, action=None, record=False):
        self.engine, self.camera = engine, camera
        self.session_id = session_id or str(uuid.uuid4())
        self.queue = FrameQueue(config.FRAME_QUEUE_SIZE)
        self.coordinator = DecisionCoordinator(engine.db_manager, action,
            enabled=not isinstance(camera.backend, SyntheticBackend))
        engine.decision_coordinator = self.coordinator
        self.workers = [RecognitionWorker(i+1, self.queue, engine, engine.db_manager,
                         self.session_id, runtime=self) for i in range(config.NUM_WORKER_THREADS)]
        self.stop_event = threading.Event()
        self.commit_lock = threading.Lock()
        self.metrics_lock = threading.Lock()
        self.video = threading.Condition()
        self.jpeg = None
        self.jpeg_id = 0
        self.latest_committed = -1
        self.error = None
        self.started_at = None
        self.ended_at = None
        self.capture_baseline = camera.frame_count
        self.capture_end = None
        self.counts = dict(submitted=0, completed=0, face_decisions=0, jpeg_encoded=0,
                           stale=0, out_of_order=0)
        self.samples = deque(maxlen=10000)
        self.records = [] if record else None
        self.threads = []

    def start(self):
        self.engine.ensure_model_available()
        self.engine.db_manager.create_session(self.session_id)
        self.started_at = time.monotonic()
        self.camera.start()
        for worker in self.workers:
            worker.start()
        for name, target in [('FrameProducer', self._produce), ('SharedJPEGEncoder', self._encode)]:
            thread = threading.Thread(name=name, target=target, daemon=True)
            self.threads.append(thread)
            thread.start()
        return self

    def check_health(self):
        error = self.error or self.camera.last_error or next((w.last_error for w in self.workers if w.last_error), None)
        if error:
            raise RuntimeError(error)
        if self.started_at is not None and not self.stop_event.is_set():
            if any(not worker.is_alive() for worker in self.workers):
                raise RuntimeError('Recognition worker stopped unexpectedly')
            if any(thread.ident is not None and not thread.is_alive() for thread in self.threads):
                raise RuntimeError('Runtime producer or encoder stopped unexpectedly')

    def fail(self, message):
        with self.commit_lock:
            with self.video:
                if self.error:
                    return
                self.error = message
                self.stop_event.set()
                self.jpeg = None
                self.video.notify_all()
            for worker in self.workers:
                worker.stop()
            self.engine.overlay.update([])
            self.coordinator.fault(None, self.session_id, message)

    def _produce(self):
        previous = 0
        try:
            while not self.stop_event.wait(.002):
                self.check_health()
                frame, frame_id, delivered = self.camera.get_snapshot(timestamped=True)
                if frame is None or frame_id == previous:
                    continue
                previous = frame_id
                if frame_id % max(1, config.FRAME_SKIP) == 0:
                    self.queue.put(frame, frame_id, delivered)
                    with self.metrics_lock:
                        self.counts['submitted'] += 1
        except Exception as exc:
            self.fail(str(exc))

    def _encode(self):
        previous = 0
        try:
            while not self.stop_event.is_set():
                started = time.monotonic()
                frame, frame_id, delivered = self.camera.get_snapshot(timestamped=True)
                if frame is not None and frame_id != previous:
                    previous = frame_id
                    with self.engine.overlay.lock:
                        self.engine.overlay.fps = (self.camera.frame_count-self.capture_baseline) / max(time.monotonic()-self.started_at, 1e-9)
                    annotated = self.engine.overlay.render(frame)
                    ok, jpeg = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, config.MJPEG_QUALITY])
                    if not ok:
                        raise RuntimeError('JPEG encoding failed')
                    with self.video:
                        if self.stop_event.is_set():
                            return
                        self.jpeg, self.jpeg_id = jpeg.tobytes(), frame_id
                        self.video.notify_all()
                    with self.metrics_lock:
                        self.counts['jpeg_encoded'] += 1
                self.stop_event.wait(max(.001, 1/config.MJPEG_FRAME_RATE - (time.monotonic()-started)))
        except Exception as exc:
            self.fail(str(exc))

    def stream(self):
        previous = 0
        while not self.stop_event.is_set():
            with self.video:
                self.video.wait_for(lambda: self.jpeg_id > previous or self.stop_event.is_set(), timeout=1)
                if self.stop_event.is_set():
                    return
                if self.jpeg is None or self.jpeg_id <= previous:
                    continue
                previous, jpeg = self.jpeg_id, self.jpeg
            # Slow viewers skip cached frames; they never encode or enqueue work.
            yield (b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ' +
                   str(len(jpeg)).encode() + b'\r\n\r\n' + jpeg + b'\r\n')

    def discard_stale(self, delivered):
        stale = time.monotonic() - delivered > config.MAX_FRAME_AGE_SECONDS
        if stale:
            with self.metrics_lock:
                self.counts['stale'] += 1
        return stale

    def complete(self, frame_id, delivered, started, faces):
        # Serialize publication AND actions, so an older completion cannot act after
        # a newer frame has already committed its decision.
        with self.commit_lock:
            if self.stop_event.is_set():
                return
            if self.discard_stale(delivered):
                return
            if frame_id <= self.latest_committed:
                with self.metrics_lock:
                    self.counts['out_of_order'] += 1
                return
            for index, face in enumerate(faces):
                self.coordinator.apply(face, frame_id, self.session_id, index, len(faces)>1)
            finished = time.monotonic()
            elapsed = (finished-delivered)*1000
            processing = (finished-started)*1000
            self.latest_committed = frame_id
            self.engine.overlay.update(faces, latency_ms=elapsed, frame_id=frame_id)
            with self.metrics_lock:
                self.counts['completed'] += 1
                self.counts['face_decisions'] += len(faces)
                self.samples.append((elapsed, processing, len(faces)))
                if self.records is not None:
                    self.records.append(dict(frame_id=frame_id, delivered_monotonic=delivered,
                        started_monotonic=started, completed_monotonic=finished,
                        delivery_to_decision_ms=elapsed, processing_ms=processing,
                        decisions=[dict(name=f.name, decision=f.decision, reason=f.reason,
                                        action_outcome=f.action_outcome) for f in faces]))

    def snapshot(self):
        end = self.ended_at or time.monotonic()
        elapsed = max(end-(self.started_at or end), 1e-9)
        with self.metrics_lock:
            counts, samples = dict(self.counts), list(self.samples)
        captured = (self.capture_end if self.capture_end is not None else self.camera.frame_count)-self.capture_baseline
        return dict(duration_seconds=elapsed, counts=dict(counts, captured=captured,
                    dropped=self.queue.dropped_count), capture_fps=captured/elapsed,
                    unique_jpeg_fps=counts['jpeg_encoded']/elapsed,
                    recognition_fps=counts['completed']/elapsed,
                    face_decisions_per_second=counts['face_decisions']/elapsed,
                    delivery_to_decision_latency=distribution([x[0] for x in samples]),
                    face_delivery_to_decision_latency=distribution([x[0] for x in samples if x[2]]),
                    processing_latency=distribution([x[1] for x in samples]),
                    latency_sample_count=len(samples), latency_window='latest 10000 completed frames',
                    rate_window='since runtime start', queue_size=self.queue.qsize(),
                    workers=config.NUM_WORKER_THREADS, max_frame_age_seconds=config.MAX_FRAME_AGE_SECONDS,
                    frame_skip=config.FRAME_SKIP, queue_capacity=config.FRAME_QUEUE_SIZE,
                    threshold=self.engine.threshold)

    def stop(self):
        with self.commit_lock:
            if self.ended_at is None:
                self.ended_at = time.monotonic()
                self.capture_end = self.camera.frame_count
            self.stop_event.set()
        with self.video:
            self.video.notify_all()
        for worker in self.workers:
            worker.stop()
        for thread in self.threads + self.workers:
            if thread.ident is not None:
                thread.join(timeout=5)
        self.camera.stop()
        if any(t.is_alive() for t in self.threads + self.workers):
            raise RuntimeError('Runtime thread did not stop')
        self.engine.db_manager.close_session(self.session_id)
