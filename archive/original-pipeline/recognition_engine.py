"""
Recognition engine module for Real-Time Facial Recognition & Access System
Implements cosine distance matching, batch verification, and face detection optimization.
"""

import numpy as np
import face_recognition
import cv2
import time
import threading
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from queue import Queue, Empty
import logging

import config
from database import get_db_manager

logger = logging.getLogger(__name__)

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Face:
    """Represents a detected face."""
    location: Tuple[int, int, int, int]  # (top, right, bottom, left)
    encoding: np.ndarray  # 128D embedding
    confidence: float = 0.0
    name: str = "Unknown"
    match_distance: float = 1.0


@dataclass
class RecognitionResult:
    """Result of a single face recognition attempt."""
    face: Face
    is_match: bool
    confidence: float
    match_distance: float
    identity_id: Optional[int] = None
    processing_time_ms: float = 0.0


# ============================================================================
# COSINE DISTANCE & SIMILARITY METRICS
# ============================================================================

def cosine_distance(encoding1: np.ndarray, encoding2: np.ndarray) -> float:
    """
    Compute cosine distance between two 128D embeddings.

    Range: 0.0 (identical) to 2.0 (opposite)
    Recommended threshold: 0.45-0.55 for >95% accuracy

    Args:
        encoding1: First 128D embedding
        encoding2: Second 128D embedding

    Returns:
        Cosine distance (float)
    """
    # Normalize vectors
    enc1_norm = encoding1 / np.linalg.norm(encoding1)
    enc2_norm = encoding2 / np.linalg.norm(encoding2)

    # Compute cosine similarity: dot product of normalized vectors
    # Similarity in [-1, 1], convert to distance [0, 2]
    similarity = np.dot(enc1_norm, enc2_norm)
    distance = 1 - similarity  # Scale to [0, 2]

    return float(distance)


def euclidean_distance(encoding1: np.ndarray, encoding2: np.ndarray) -> float:
    """
    Compute Euclidean distance between two 128D embeddings.
    Legacy method; cosine distance preferred for better accuracy.

    Range: 0.0 to ~4.0 depending on normalization
    Recommended threshold: 0.6
    """
    return float(np.linalg.norm(encoding1 - encoding2))


def batch_cosine_distance(encodings: np.ndarray, test_encoding: np.ndarray) -> np.ndarray:
    """
    Efficiently compute cosine distances between one test encoding and multiple known encodings.

    Args:
        encodings: Array of shape (N, 128) with N known face encodings
        test_encoding: Single encoding of shape (128,)

    Returns:
        Array of N cosine distances
    """
    # Normalize vectors
    known_norms = np.linalg.norm(encodings, axis=1, keepdims=True)
    known_normalized = encodings / (known_norms + 1e-10)

    test_norm = np.linalg.norm(test_encoding)
    test_normalized = test_encoding / (test_norm + 1e-10)

    # Batch cosine similarity: matrix multiply
    similarities = np.dot(known_normalized, test_normalized)  # Shape: (N,)
    distances = 1 - similarities  # Convert to distances

    return distances


# ============================================================================
# RECOGNITION ENGINE CLASS
# ============================================================================

class RecognitionEngine:
    """
    Core recognition engine with optimized face matching and batch processing.
    Handles face detection, encoding, and comparison against known faces.
    """

    def __init__(self, db_manager=None):
        self.db_manager = db_manager or get_db_manager()
        self.known_encodings = []
        self.known_names = []
        self.known_identity_ids = []
        self.lock = threading.Lock()

        # Load known faces
        self.reload_known_faces()

        logger.info(f"Recognition engine initialized with {len(self.known_names)} known identities")

    def reload_known_faces(self):
        """Load or refresh known face encodings from database."""
        with self.lock:
            self.known_encodings = []
            self.known_names = []
            self.known_identity_ids = []

            identities = self.db_manager.get_all_identities()
            for identity in identities:
                try:
                    # Load encoding from binary
                    encoding = np.frombuffer(identity['encoding'], dtype=np.float64)
                    # Ensure 128D
                    if len(encoding) == 128:
                        self.known_encodings.append(encoding)
                        self.known_names.append(identity['name'])
                        self.known_identity_ids.append(identity['id'])
                except Exception as e:
                    logger.error(f"Failed to load encoding for {identity['name']}: {e}")

            logger.info(f"Loaded {len(self.known_encodings)} identities for recognition")

    def detect_faces(self, frame: np.ndarray, model: str = None) -> List[Tuple]:
        """
        Detect faces in a frame.

        Args:
            frame: BGR image from OpenCV
            model: 'hog' (faster, CPU) or 'cnn' (accurate, slower)

        Returns:
            List of face locations (top, right, bottom, left)
        """
        model = model or config.FACE_DETECTION_MODEL

        # Convert BGR to RGB for face_recognition library
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        try:
            face_locations = face_recognition.face_locations(rgb_frame, model=model)
            return face_locations
        except Exception as e:
            logger.error(f"Face detection error: {e}")
            return []

    def extract_encodings(self, frame: np.ndarray, face_locations: List[Tuple],
                         num_jitters: int = 1) -> List[np.ndarray]:
        """
        Extract 128D embeddings for detected faces.

        Args:
            frame: BGR image
            face_locations: List of face locations
            num_jitters: Number of times to resample (1=fast, >1=accurate but slower)

        Returns:
            List of 128D encodings
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        try:
            encodings = face_recognition.face_encodings(
                rgb_frame, 
                face_locations,
                num_jitters=num_jitters
            )
            return encodings
        except Exception as e:
            logger.error(f"Encoding extraction error: {e}")
            return []

    def recognize_faces(self, frame: np.ndarray, use_cosine: bool = True,
                       threshold: float = None) -> List[RecognitionResult]:
        """
        Detect and recognize all faces in a frame.

        Args:
            frame: BGR image
            use_cosine: Use cosine distance (True) or Euclidean (False)
            threshold: Matching threshold (uses config if None)

        Returns:
            List of RecognitionResult objects
        """
        start_time = time.time()
        results = []

        threshold = threshold or config.RECOGNITION_THRESHOLD

        # Detect faces
        face_locations = self.detect_faces(frame, model=config.FACE_DETECTION_MODEL)
        if not face_locations:
            return results

        # Extract encodings
        encodings = self.extract_encodings(frame, face_locations, num_jitters=1)

        with self.lock:
            # Batch process all faces
            for face_location, encoding in zip(face_locations, encodings):
                result = self._match_face(
                    encoding, 
                    face_location,
                    use_cosine=use_cosine,
                    threshold=threshold
                )
                result.processing_time_ms = (time.time() - start_time) * 1000
                results.append(result)

        return results

    def _match_face(self, encoding: np.ndarray, face_location: Tuple,
                   use_cosine: bool = True, threshold: float = None) -> RecognitionResult:
        """
        Match a single face against known encodings.

        Args:
            encoding: 128D embedding of detected face
            face_location: Bounding box (top, right, bottom, left)
            use_cosine: Use cosine distance
            threshold: Matching threshold

        Returns:
            RecognitionResult with match status and confidence
        """
        threshold = threshold or config.RECOGNITION_THRESHOLD

        if not self.known_encodings:
            face = Face(
                location=face_location,
                encoding=encoding,
                name="Unknown",
                confidence=0.0
            )
            return RecognitionResult(
                face=face,
                is_match=False,
                confidence=0.0,
                match_distance=2.0  # Max distance
            )

        # Compute distances to all known encodings
        known_encodings_array = np.array(self.known_encodings)

        if use_cosine:
            distances = batch_cosine_distance(known_encodings_array, encoding)
        else:
            distances = face_recognition.face_distance(known_encodings_array, encoding)

        # Find best match
        best_idx = int(np.argmin(distances))
        best_distance = float(distances[best_idx])

        # Check if match is within threshold
        is_match = best_distance < threshold
        name = self.known_names[best_idx] if is_match else "Unknown"
        identity_id = self.known_identity_ids[best_idx] if is_match else None

        # Convert distance to confidence score (0-1)
        confidence = max(0.0, 1.0 - best_distance)

        face = Face(
            location=face_location,
            encoding=encoding,
            name=name,
            confidence=confidence,
            match_distance=best_distance
        )

        return RecognitionResult(
            face=face,
            is_match=is_match,
            confidence=confidence,
            match_distance=best_distance,
            identity_id=identity_id
        )

    def batch_verify_encodings(self, encodings: List[np.ndarray],
                              name: str = None, use_cosine: bool = True,
                              threshold: float = None) -> Dict:
        """
        Batch verify multiple encodings against all known faces.
        Used for enrollment duplicate detection, batch imports, etc.

        Args:
            encodings: List of 128D embeddings to verify
            name: If provided, check for duplicates of this person
            use_cosine: Use cosine distance
            threshold: Matching threshold

        Returns:
            Dict with verification results and statistics
        """
        threshold = threshold or config.RECOGNITION_THRESHOLD
        results = {
            'total_encoded': len(encodings),
            'matches': [],
            'duplicates': [],
            'status': 'success'
        }

        known_encodings_array = np.array(self.known_encodings) if self.known_encodings else None

        for i, encoding in enumerate(encodings):
            if known_encodings_array is None:
                continue

            if use_cosine:
                distances = batch_cosine_distance(known_encodings_array, encoding)
            else:
                distances = face_recognition.face_distance(known_encodings_array, encoding)

            best_idx = int(np.argmin(distances))
            best_distance = float(distances[best_idx])

            if best_distance < threshold:
                matched_name = self.known_names[best_idx]
                results['matches'].append({
                    'encoding_index': i,
                    'matched_name': matched_name,
                    'distance': best_distance,
                    'confidence': 1.0 - best_distance
                })

                # Check for duplicate of same person
                if name and matched_name == name:
                    results['duplicates'].append({
                        'encoding_index': i,
                        'distance': best_distance
                    })

        return results


# ============================================================================
# FRAME PROCESSING PIPELINE (PRODUCER-CONSUMER PATTERN)
# ============================================================================

class FrameQueue:
    """Thread-safe queue for frame processing pipeline."""

    def __init__(self, maxsize: int = config.FRAME_QUEUE_SIZE):
        self.queue = Queue(maxsize=maxsize)
        self.frame_count = 0
        self.lock = threading.Lock()

    def put(self, frame: np.ndarray, frame_id: int = None):
        """Add frame to queue."""
        if frame_id is None:
            with self.lock:
                self.frame_count += 1
                frame_id = self.frame_count

        try:
            self.queue.put((frame, frame_id), block=False)
        except:
            logger.warning("Frame queue full, dropping frame")

    def get(self, timeout: float = 1.0) -> Optional[Tuple[np.ndarray, int]]:
        """Get frame from queue."""
        try:
            return self.queue.get(timeout=timeout)
        except Empty:
            return None

    def qsize(self) -> int:
        """Get current queue size."""
        return self.queue.qsize()


class RecognitionWorker(threading.Thread):
    """
    Worker thread that processes frames from queue.
    Decouples frame capture from computationally expensive recognition.
    """

    def __init__(self, frame_queue: FrameQueue, engine: RecognitionEngine,
                 db_manager=None, daemon: bool = True):
        super().__init__(daemon=daemon)
        self.frame_queue = frame_queue
        self.engine = engine
        self.db_manager = db_manager or get_db_manager()
        self.running = False
        self.last_logged = {}  # Cooldown tracking

    def run(self):
        """Main worker loop."""
        self.running = True
        logger.info("Recognition worker started")

        while self.running:
            frame_data = self.frame_queue.get(timeout=0.5)
            if not frame_data:
                continue

            frame, frame_id = frame_data

            try:
                # Recognize faces
                results = self.engine.recognize_faces(frame, use_cosine=True)

                # Log verifications (with cooldown)
                current_time = time.time()
                for result in results:
                    if result.is_match and result.confidence >= config.LOG_CONFIDENCE_THRESHOLD:
                        name = result.face.name

                        # Apply cooldown to prevent log spam
                        if name not in self.last_logged or \
                           (current_time - self.last_logged[name]) > config.LOG_COOLDOWN_SECONDS:

                            self.db_manager.log_recognition(
                                identity_id=result.identity_id,
                                name=name,
                                confidence=result.confidence,
                                match_distance=result.match_distance,
                                status='verified',
                                detection_model=config.FACE_DETECTION_MODEL
                            )
                            self.last_logged[name] = current_time
                            logger.info(f"Logged: {name} (confidence: {result.confidence:.3f})")

                    elif not result.is_match:
                        # Optionally log failed recognitions
                        self.db_manager.log_recognition(
                            identity_id=None,
                            name="Unknown",
                            confidence=result.confidence,
                            match_distance=result.match_distance,
                            status='low_confidence' if result.confidence > 0.3 else 'unknown'
                        )

            except Exception as e:
                logger.error(f"Recognition error in worker: {e}")

    def stop(self):
        """Stop the worker thread."""
        self.running = False


# ============================================================================
# PERFORMANCE MONITORING
# ============================================================================

class PerformanceMonitor:
    """Monitor recognition pipeline performance metrics."""

    def __init__(self, db_manager=None, log_interval: int = 60):
        self.db_manager = db_manager or get_db_manager()
        self.log_interval = log_interval
        self.last_log_time = time.time()
        self.frame_times = []
        self.recognition_times = []
        self.lock = threading.Lock()

    def record_frame_time(self, latency_ms: float):
        """Record frame processing latency."""
        with self.lock:
            self.frame_times.append(latency_ms)
            if len(self.frame_times) > 1000:
                self.frame_times.pop(0)

    def record_recognition_time(self, latency_ms: float):
        """Record recognition latency."""
        with self.lock:
            self.recognition_times.append(latency_ms)
            if len(self.recognition_times) > 1000:
                self.recognition_times.pop(0)

    def get_stats(self) -> Dict:
        """Get current performance statistics."""
        with self.lock:
            if not self.frame_times:
                return {}

            frame_times = self.frame_times[-30:]  # Last 30 frames
            fps = 1000.0 / np.mean(frame_times) if frame_times else 0

            stats = {
                'avg_frame_latency_ms': float(np.mean(frame_times)),
                'max_frame_latency_ms': float(np.max(frame_times)),
                'min_frame_latency_ms': float(np.min(frame_times)),
                'fps': fps,
                'target_fps': config.TARGET_FPS,
                'meeting_target': fps >= config.TARGET_FPS
            }

            if self.recognition_times:
                rec_times = self.recognition_times[-30:]
                stats['avg_recognition_latency_ms'] = float(np.mean(rec_times))
                stats['max_recognition_latency_ms'] = float(np.max(rec_times))

            return stats

    def periodic_log(self, force: bool = False):
        """Periodically log metrics to database."""
        current_time = time.time()

        if not force and (current_time - self.last_log_time) < self.log_interval:
            return

        stats = self.get_stats()
        if stats:
            self.db_manager.log_metrics(
                frame_latency_ms=stats.get('avg_frame_latency_ms', 0),
                recognition_latency_ms=stats.get('avg_recognition_latency_ms'),
                fps=stats.get('fps', 0)
            )
            self.last_log_time = current_time


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # Test recognition engine
    engine = RecognitionEngine()
    print(f"Engine loaded with {len(engine.known_names)} identities")
    print(f"Known names: {engine.known_names}")
