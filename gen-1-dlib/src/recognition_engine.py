from __future__ import annotations
"""
Recognition Engine Module for Real-Time Facial Recognition & Access System
Deep metric learning (128D embeddings), vectorized cosine-distance matching,
producer-consumer worker threads, and real-time video annotation overlay.
"""

import threading
import time
import logging
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from queue import Queue, Empty
import numpy as np
import cv2

try:
    from . import config
    from .database import get_db_manager, DatabaseManager
except (ImportError, ValueError):
    import config
    from database import get_db_manager, DatabaseManager

logger = logging.getLogger(__name__)

# Check for dlib / face_recognition availability
try:
    import face_recognition
    HAS_FACE_RECOGNITION = True
except ImportError:
    HAS_FACE_RECOGNITION = False
    face_recognition = None


def unrotate_box(box_coords: Tuple[int, int, int, int], angle: float, shape: Tuple[int, int]) -> FaceBox:
    """Transform (top, right, bottom, left) from rotated frame back to original frame space."""
    if angle == 0:
        return FaceBox(*box_coords)
    h, w = shape[:2]
    cx, cy = w / 2.0, h / 2.0
    rad = np.radians(angle)  # Inverse of OpenCV's image-coordinate rotation.
    c, s = np.cos(rad), np.sin(rad)
    top, right, bottom, left = box_coords
    xs = np.array([left, right, right, left], dtype=np.float32)
    ys = np.array([top, top, bottom, bottom], dtype=np.float32)
    orig_x = c * (xs - cx) - s * (ys - cy) + cx
    orig_y = s * (xs - cx) + c * (ys - cy) + cy
    return FaceBox(
        top=int(np.clip(orig_y.min(), 0, h)),
        right=int(np.clip(orig_x.max(), 0, w)),
        bottom=int(np.clip(orig_y.max(), 0, h)),
        left=int(np.clip(orig_x.min(), 0, w))
    )


def calculate_ear(eye_points: List[Tuple[int, int]]) -> float:
    """Compute Eye Aspect Ratio (EAR) from 6 landmark points."""
    if len(eye_points) < 6:
        return 0.0
    p = np.array(eye_points, dtype=np.float32)
    a = float(np.linalg.norm(p[1] - p[5]))
    b = float(np.linalg.norm(p[2] - p[4]))
    c = float(np.linalg.norm(p[0] - p[3]))
    return (a + b) / (2.0 * c) if c > 1e-6 else 0.0


@dataclass
class FaceBox:
    """Bounding box: (top, right, bottom, left) matching face_recognition convention."""
    top: int
    right: int
    bottom: int
    left: int

    @property
    def cv2_rect(self) -> Tuple[int, int, int, int]:
        """Convert to OpenCV format: (x, y, w, h)."""
        return self.left, self.top, self.right - self.left, self.bottom - self.top


@dataclass
class RecognizedFace:
    """Detection and matching result for a single face."""
    box: FaceBox
    encoding: np.ndarray  # 128D unit vector
    name: str
    confidence: float
    match_distance: float
    is_match: bool
    identity_id: Optional[int] = None
    inference_time_ms: float = 0.0
    decision: str = "deny"
    reason: str = "not_evaluated"
    action_outcome: str = "not_requested"
    is_attentive: bool = True
    ear: float = 0.0


# ============================================================================
# VECTORIZED COSINE DISTANCE MATCHING
# ============================================================================

def normalize_vector(v: np.ndarray) -> np.ndarray:
    """Project vector onto unit hypersphere (L2-norm = 1.0)."""
    norm = np.linalg.norm(v)
    if norm < 1e-10:
        return v
    return v / norm


def compute_cosine_distance(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    Cosine distance between two 128D embeddings: 1.0 - (u . v) / (||u|| * ||v||).
    Range: 0.0 (identical) to 2.0 (opposite).
    """
    u = normalize_vector(vec1)
    v = normalize_vector(vec2)
    similarity = float(np.dot(u, v))
    return max(0.0, 1.0 - similarity)


def batch_cosine_distances(known_matrix: np.ndarray, query_vec: np.ndarray) -> np.ndarray:
    """
    Vectorized cosine distance matching across N enrolled identities.
    Uses NumPy matrix-vector multiplication.
    """
    if len(known_matrix) == 0:
        return np.array([], dtype=np.float32)

    # Normalize query
    q_norm = normalize_vector(query_vec)

    # Normalize rows of known matrix
    norms = np.linalg.norm(known_matrix, axis=1, keepdims=True)
    norms[norms < 1e-10] = 1.0
    known_norm = known_matrix / norms

    # Dot product similarity
    similarities = np.dot(known_norm, q_norm)
    similarities = np.clip(similarities, -1.0, 1.0)
    return 1.0 - similarities


class AnnotationOverlay:
    """
    Thread-safe visual overlay manager.
    Caches latest detected face boxes and recognition labels to render onto live video stream.
    """
    def __init__(self):
        self.faces: List[RecognizedFace] = []
        self.timestamp = 0.0
        self.frame_id = -1
        self.lock = threading.Lock()
        self.fps: float = 0.0
        self.latency_ms: float = 0.0

    def update(self, faces: List[RecognizedFace], latency_ms: float = 0.0, fps: float = 0.0, frame_id=None):
        with self.lock:
            if frame_id is not None:
                if frame_id < self.frame_id:
                    return
                self.frame_id = frame_id
            self.faces = faces
            self.timestamp = time.time()
            self.latency_ms = latency_ms
            if fps > 0:
                self.fps = fps

    def get_active_faces(self, max_age_seconds: float = 0.8) -> List[RecognizedFace]:
        with self.lock:
            if time.time() - self.timestamp > max_age_seconds:
                return []
            return list(self.faces)

    def render(self, frame: np.ndarray) -> np.ndarray:
        """Draw bounding boxes, recognized names, and telemetry HUD onto frame."""
        vis = frame.copy()
        faces = self.get_active_faces()

        # Decide if there is a single unknown person or multiple unknown people
        unknown_faces = [f for f in faces if not (f.is_match and f.identity_id is not None)]
        has_multiple_unknowns = len(unknown_faces) > 1
        unknown_names = {}
        if has_multiple_unknowns:
            sorted_unknowns = sorted(unknown_faces, key=lambda f: f.box.left if hasattr(f, 'box') and hasattr(f.box, 'left') else 0)
            for idx, uf in enumerate(sorted_unknowns, start=1):
                unknown_names[id(uf)] = f"Unknown {idx}"

        for face in faces:
            display_only = face.reason == 'multiple_faces_display_only'
            known = face.is_match and face.identity_id is not None
            green = known if display_only else face.decision == "allow"
            color = config.COLOR_KNOWN_FACE if green else config.COLOR_UNKNOWN_FACE
            b = face.box

            # Draw outer rectangle
            cv2.rectangle(vis, (b.left, b.top), (b.right, b.bottom), color, config.COLOR_BOX_THICKNESS)

            # Draw sleek label background
            action_label = {'not_configured': 'no hardware action configured',
                            'not_requested': 'no action requested',
                            'succeeded': 'action completed',
                            'failed': 'action failed',
                            'cooldown_suppressed': 'action cooldown'}.get(face.action_outcome, face.action_outcome)
            if face.reason == 'multiple_faces':
                action_label = "multiple faces"
            elif face.reason == 'attention_required':
                action_label = "attention required"

            if known:
                display_name = face.name
            elif has_multiple_unknowns:
                display_name = unknown_names.get(id(face), "Unknown")
            else:
                display_name = "Unknown"

            label = (f"{display_name}: RECOGNISED" if known else display_name) if display_only else f"{display_name}: {face.decision.upper()} / {action_label}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = config.TEXT_FONT_SCALE
            thickness = config.TEXT_THICKNESS

            (tw, th), baseline = cv2.getTextSize(label, font, scale, thickness)
            label_top = max(0, b.top - th - 10)
            cv2.rectangle(vis, (b.left, label_top), (b.left + tw + 12, label_top + th + 8), color, -1)
            cv2.putText(vis, label, (b.left + 6, label_top + th + 4), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)

        # Draw Telemetry HUD
        with self.lock:
            fps_val, lat_val = self.fps, self.latency_ms
        hud_text = f"FPS: {fps_val:.1f}  |  Edge Inference: {lat_val:.1f}ms"
        cv2.putText(vis, hud_text, (18, vis.shape[0] - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
        return vis


# ============================================================================
# CORE RECOGNITION ENGINE
# ============================================================================

class RecognitionEngine:
    """
    Optimized facial recognition engine supporting:
    - Pretrained dlib 128D face embeddings
    - Vectorized cosine-distance matrix matching
    - Accuracy and latency require real evaluation
    """

    def __init__(self, db_manager: DatabaseManager = None):
        self.db_manager = db_manager or get_db_manager()
        self.overlay = AnnotationOverlay()
        self.last_tilt_angle: int = 0
        self.threshold = config.RECOGNITION_THRESHOLD
        self.decision_coordinator = None

        self.known_encodings: List[np.ndarray] = []
        self.known_names: List[str] = []
        self.known_ids: List[int] = []
        self.known_matrix: np.ndarray = np.empty((0, 128), dtype=np.float32)

        self.lock = threading.Lock()
        self.reload_identities()

    def reload_identities(self):
        """Load enrolled identities from SQLite database into NumPy memory matrix."""
        with self.lock:
            identities = self.db_manager.get_all_identities()
            self.known_encodings.clear()
            self.known_names.clear()
            self.known_ids.clear()

            enc_list = []
            for row in identities:
                try:
                    raw_bytes = row['encoding']
                    vec = np.frombuffer(raw_bytes, dtype=np.float64)
                    if len(vec) == 128 and np.isfinite(vec).all() and np.linalg.norm(vec) > 1e-10:
                        vec32 = vec.astype(np.float32)
                        enc_list.append(normalize_vector(vec32))
                        self.known_names.append(row['name'])
                        self.known_ids.append(row['id'])
                except Exception as e:
                    logger.warning(f"Could not load encoding for {row.get('name')}: {e}")

            if enc_list:
                self.known_matrix = np.array(enc_list, dtype=np.float32)
            else:
                self.known_matrix = np.empty((0, 128), dtype=np.float32)

            logger.info(f"Loaded {len(self.known_names)} identities into vectorized matching matrix.")

    @staticmethod
    def ensure_model_available():
        if not HAS_FACE_RECOGNITION:
            raise RuntimeError("Recognition requires the face_recognition model; install requirements-face-recognition.txt.")

    def check_attention(self, rgb: np.ndarray, box: FaceBox) -> Tuple[bool, float]:
        """Apple-style attention check using Eye Aspect Ratio (EAR)."""
        if not HAS_FACE_RECOGNITION or not hasattr(face_recognition, 'face_landmarks'):
            return False, 0.0
        try:
            loc = [(box.top, box.right, box.bottom, box.left)]
            landmarks_list = face_recognition.face_landmarks(rgb, loc)
            if not landmarks_list:
                return False, 0.0
            lms = landmarks_list[0]
            left_ear = calculate_ear(lms.get('left_eye', []))
            right_ear = calculate_ear(lms.get('right_eye', []))
            if left_ear > 0 and right_ear > 0:
                ear = (left_ear + right_ear) / 2.0
                return ear >= 0.18, ear
        except Exception:
            pass
        return False, 0.0

    def detect_and_extract(self, frame_bgr, strict=False):
        self.ensure_model_available()
        try:
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        except Exception as exc:
            raise RuntimeError("Face detection failed") from exc

        h, w = rgb.shape[:2]
        center = (w / 2.0, h / 2.0)

        # 1. Primary check: try last detected tilt angle (default 0 deg)
        active_angle = self.last_tilt_angle
        active_rgb = rgb
        if active_angle != 0:
            M = cv2.getRotationMatrix2D(center, active_angle, 1.0)
            active_rgb = cv2.warpAffine(rgb, M, (w, h))

        try:
            locs = face_recognition.face_locations(active_rgb, model=config.FACE_DETECTION_MODEL)
        except Exception as exc:
            raise RuntimeError("Face detection failed") from exc

        # 2. If face moved away from previous angle, try upright (0 deg)
        if not locs and active_angle != 0:
            active_angle = 0
            active_rgb = rgb
            locs = face_recognition.face_locations(rgb, model=config.FACE_DETECTION_MODEL)

        # 3. Multi-tilt scan: if still not found, search rotational pyramid
        if not locs:
            # Candidate angles covering 360-degree head roll with +-15 deg HOG tolerance
            angles = (-30, 30, -60, 60, -90, 90, 180, -120, 120)
            small_rgb = rgb[::2, ::2]  # Zero-copy 2x downsample for fast angle scan (<35ms)
            small_h, small_w = small_rgb.shape[:2]
            small_center = (small_w / 2.0, small_h / 2.0)

            for cand in angles:
                try:
                    M_small = cv2.getRotationMatrix2D(small_center, cand, 1.0)
                    rot_small = cv2.warpAffine(small_rgb, M_small, (small_w, small_h))
                    cand_locs = face_recognition.face_locations(rot_small, model=config.FACE_DETECTION_MODEL)
                    if cand_locs:
                        active_angle = cand
                        M_full = cv2.getRotationMatrix2D(center, cand, 1.0)
                        active_rgb = cv2.warpAffine(rgb, M_full, (w, h))
                        locs = face_recognition.face_locations(active_rgb, model=config.FACE_DETECTION_MODEL)
                        break
                except Exception:
                    pass

        if strict and len(locs) != 1:
            raise ValueError("Exactly one face is required for enrollment; found %d." % len(locs))
        if not locs:
            self.last_tilt_angle = 0
            return []

        self.last_tilt_angle = active_angle

        try:
            encs = face_recognition.face_encodings(active_rgb, locs, num_jitters=1)
            if len(encs) != len(locs):
                raise RuntimeError("Missing face embeddings")
            faces = []
            for location, enc in zip(locs, encs):
                enc = np.asarray(enc, dtype=np.float32)
                if enc.shape != (128,) or not np.isfinite(enc).all() or np.linalg.norm(enc) <= 0:
                    raise RuntimeError("Invalid face embedding")
                orig_box = unrotate_box(location, active_angle, (h, w))
                faces.append((orig_box, normalize_vector(enc)))
            return faces
        except Exception as exc:
            raise RuntimeError("Face extraction failed") from exc

    def match_embedding(self, query_vec: np.ndarray, threshold: float = None) -> Tuple[bool, str, float, float, Optional[int]]:
        """
        Match 128D query vector against known enrolled matrix using Cosine Distance.
        Returns: (is_match, name, confidence, match_distance, identity_id)
        """
        threshold = self.threshold if threshold is None else threshold

        query_vec = np.asarray(query_vec, dtype=np.float32)
        if query_vec.shape != (128,) or not np.isfinite(query_vec).all() or np.linalg.norm(query_vec) <= 1e-10:
            return False, "Unknown", 0.0, 2.0, None
        if not np.isfinite(threshold) or not 0 < threshold < 2:
            raise ValueError("Cosine threshold must be between 0 and 2")

        with self.lock:
            if len(self.known_matrix) == 0:
                return False, "Unknown", 0.0, 2.0, None

            # Vector cosine distance calculation
            distances = batch_cosine_distances(self.known_matrix, query_vec)
            best_idx = int(np.argmin(distances))
            min_dist = float(distances[best_idx])

            # A nearest neighbour is only a candidate, never an automatic assignment.
            # Reject tied/near-tied identities regardless of database ordering.
            runner_up = float(np.partition(distances, 1)[1]) if len(distances) > 1 else float("inf")
            if min_dist <= threshold and runner_up - min_dist >= config.RECOGNITION_MIN_MARGIN:
                name = self.known_names[best_idx]
                ident_id = self.known_ids[best_idx]
                # Display score only; not a calibrated probability or a policy threshold
                confidence = max(0.0, min(1.0, 1.0 - (min_dist / (threshold * 1.5))))
                return True, name, confidence, min_dist, ident_id
            else:
                confidence = 0.0
                return False, "Unknown", confidence, min_dist, None

    def process_frame(self, frame_bgr: np.ndarray) -> List[RecognizedFace]:
        """Run full detection and verification pipeline on a frame."""
        t_start = time.monotonic()
        detections = self.detect_and_extract(frame_bgr)
        results: List[RecognizedFace] = []

        rgb = None
        for box, embedding in detections:
            is_match, name, conf, dist, ident_id = self.match_embedding(embedding)
            t_infer = (time.monotonic() - t_start) * 1000.0

            is_attentive, ear_val = False, 0.0
            if is_match:
                if rgb is None:
                    try:
                        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                    except Exception:
                        pass
                if rgb is not None:
                    is_attentive, ear_val = self.check_attention(rgb, box)

            results.append(RecognizedFace(
                box=box,
                encoding=embedding,
                name=name,
                confidence=conf,
                match_distance=dist,
                is_match=is_match,
                identity_id=ident_id,
                inference_time_ms=t_infer,
                is_attentive=is_attentive,
                ear=ear_val
            ))

        # Decide if frame has single or multiple unknown people and series them if multiple
        unknown_faces = [f for f in results if not f.is_match or f.identity_id is None]
        if len(unknown_faces) > 1:
            sorted_u = sorted(unknown_faces, key=lambda f: f.box.left if hasattr(f, 'box') and hasattr(f.box, 'left') else 0)
            for idx, uf in enumerate(sorted_u, start=1):
                uf.name = f"Unknown {idx}"
        elif len(unknown_faces) == 1:
            unknown_faces[0].name = "Unknown"

        total_latency = (time.monotonic() - t_start) * 1000.0
        return results


# ============================================================================
# MULTI-THREADED PRODUCER-CONSUMER QUEUE & WORKERS
# ============================================================================

class FrameQueue:
    """Thread-safe queue with drop-oldest policy to prevent latency buildup under load."""
    def __init__(self, maxsize: int = config.FRAME_QUEUE_SIZE):
        self.queue: Queue = Queue(maxsize=maxsize)
        self.lock = threading.Lock()
        self.dropped_count = 0

    def put(self, frame: np.ndarray, frame_id: int, delivered_at=None):
        with self.lock:
            if self.queue.full():
                try:
                    self.queue.get_nowait()
                    self.dropped_count += 1
                except Empty:
                    pass
            self.queue.put((frame, frame_id) if delivered_at is None else (frame, frame_id, delivered_at))

    def get(self, timeout: float = 0.2) -> Optional[Tuple[np.ndarray, int]]:
        try:
            return self.queue.get(timeout=timeout)
        except Empty:
            return None

    def qsize(self) -> int:
        return self.queue.qsize()


class RecognitionWorker(threading.Thread):
    """
    Dedicated worker thread consuming frames from FrameQueue.
    Executes inference and logs transactions into SQLite with cooldown throttling.
    """

    def __init__(self, worker_id: int, queue: FrameQueue, engine: RecognitionEngine,
                 db_manager: DatabaseManager, session_id: str, runtime=None):
        super().__init__(name=f"RecognitionWorker-{worker_id}", daemon=True)
        self.runtime = runtime
        self.worker_id = worker_id
        self.queue = queue
        self.engine = engine
        self.db_manager = db_manager
        self.session_id = session_id
        self.running = False
        self.last_error = None
        with engine.lock:
            if engine.decision_coordinator is None:
                from .access import DecisionCoordinator
                engine.decision_coordinator = DecisionCoordinator(db_manager)
            self.coordinator = engine.decision_coordinator

    def run(self):
        self.running = True
        logger.info(f"Recognition Worker {self.worker_id} started.")

        while self.running:
            item = self.queue.get(timeout=0.2)
            if item is None:
                continue

            frame, frame_id = item[:2]
            delivered_at = item[2] if len(item) > 2 else time.monotonic()
            if self.runtime and self.runtime.discard_stale(delivered_at):
                continue
            try:
                started = time.monotonic()
                results = self.engine.process_frame(frame)
                if self.runtime:
                    self.runtime.complete(frame_id, delivered_at, started, results)
                    continue
                self.coordinator.apply_frame(results, frame_id, self.session_id)
                self.engine.overlay.update(results, latency_ms=max((f.inference_time_ms for f in results), default=0), frame_id=frame_id)
                self.last_error = None
            except Exception as e:
                self.last_error = str(e)
                if self.runtime:
                    self.runtime.fail(str(e))
                    self.running = False
                    continue
                self.engine.overlay.update([])
                logger.exception("Worker %s failed on frame %s", self.worker_id, frame_id)
                try:
                    self.coordinator.fault(frame_id, self.session_id, str(e))
                except Exception:
                    logger.exception("Could not persist pipeline failure")
                # Continue on transient errors instead of dying permanently

    def stop(self):
        self.running = False
