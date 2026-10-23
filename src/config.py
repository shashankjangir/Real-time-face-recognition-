"""
Configuration module for Real-Time Facial Recognition & Access System
Edge-optimized settings for Raspberry Pi 5, OpenCV, and SQLite.
"""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Load local .env file if present
_env_file = BASE_DIR / ".env"
if _env_file.is_file():
    try:
        with open(_env_file, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip().strip("'\""))
    except Exception:
        pass

DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
KNOWN_FACES_DIR = BASE_DIR / "known_faces"

DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
KNOWN_FACES_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# CAMERA & FRAME CAPTURE SETTINGS (Raspberry Pi 5 / Edge)
# ============================================================================
CAMERA_BACKEND = os.getenv("CAMERA_BACKEND", "auto")  # "auto", "picamera2", "opencv", "synthetic"
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))     # USB camera index if using opencv
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30
FRAME_SKIP = 3  # Submit every Nth captured frame
FRAME_QUEUE_SIZE = 2  # Bound queued work; discard oldest under load
MAX_FRAME_AGE_SECONDS = 0.5  # Discard stale work before inference and before action

# ============================================================================
# FACE RECOGNITION & METRIC LEARNING (128D Embeddings)
# ============================================================================
# Cosine distance on normalized embeddings; not dlib's raw Euclidean tolerance.
# Conservative starting settings, requiring validation with real known/unknown captures.
RECOGNITION_THRESHOLD = 0.08
RECOGNITION_MIN_MARGIN = 0.02  # Runner-up must be farther away by at least this much.

# Face detection model: "hog" (fast, CPU optimized for Pi 5) or "cnn" (GPU/TPU)
FACE_DETECTION_MODEL = "hog"
MIN_FACE_SIZE = 20  # Minimum face size in pixels

# Password required for enrolling a face (via web dashboard or POST /api/enroll).
# Can be configured via ENROLLMENT_PASSWORD or ADMIN_ENROLLMENT_TOKEN.
ENROLLMENT_PASSWORD = os.getenv("ENROLLMENT_PASSWORD", os.getenv("ADMIN_ENROLLMENT_TOKEN", "123456789"))
ADMIN_ENROLLMENT_TOKEN = ENROLLMENT_PASSWORD
ENROLLMENT_MIN_QUALITY = 0.70

# Drawing / Annotation overlay on live video
ENABLE_VIDEO_OVERLAY = True
COLOR_KNOWN_FACE = (0, 220, 115)     # Bright Green (BGR)
COLOR_UNKNOWN_FACE = (0, 50, 240)    # Crimson Red (BGR)
COLOR_HIGHLIGHT = (255, 180, 50)     # Amber/Blue (BGR)
COLOR_BOX_THICKNESS = 2
TEXT_FONT_SCALE = 0.55
TEXT_THICKNESS = 2

# ============================================================================
# DATABASE & INDEXING SETTINGS (SQLite + WAL Mode)
# ============================================================================
DATABASE_FILE = str(DATA_DIR / "faces.db")
DATABASE_TIMEOUT = 30.0  # seconds
DATABASE_ISOLATION_LEVEL = None  # Autocommit mode for low write-latency
ENABLE_WAL_MODE = True  # Write-Ahead Logging for non-blocking concurrent reads/writes

# Connection pool settings
DB_POOL_SIZE = 5
DB_POOL_TIMEOUT = 10.0

# ============================================================================
# ACCESS LOGGING & THROTTLING
# ============================================================================

# ============================================================================
# WEB SERVER & MJPEG STREAMING
# ============================================================================
WEB_HOST = "0.0.0.0"
WEB_PORT = 5000
DEBUG_MODE = False
THREADED_MODE = True

# MJPEG streaming
MJPEG_QUALITY = 82  # JPEG quality (1-100)
MJPEG_FRAME_RATE = 25  # Target stream display FPS

# ============================================================================
# FILES & ENCODINGS CACHE
# ============================================================================
ENCODINGS_JSON_FILE = str(DATA_DIR / "encodings.json")

# ============================================================================
# CSV REPORT SETTINGS
# ============================================================================
CSV_DELIMITER = ","
CSV_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
CSV_REPORT_FIELDS = ["timestamp", "person_name", "confidence", "status", "match_distance", "identity_id"]

# ============================================================================
# EDGE INFERENCE PERFORMANCE TARGETS (Raspberry Pi 5 Verification)
# ============================================================================
TARGET_LATENCY_MS = 300.0   # Edge inference latency budget (<300 ms per identity)
TARGET_FPS = 15.0          # Minimum video throughput (15-20 FPS)
TARGET_IDENTITIES = 50     # Target enrolled identities
TARGET_ACCURACY = 0.95     # >95% classification accuracy

# Worker threads for multi-threaded inference pipeline
NUM_WORKER_THREADS = 2

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = str(DATA_DIR / "access_system.log")
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 3
