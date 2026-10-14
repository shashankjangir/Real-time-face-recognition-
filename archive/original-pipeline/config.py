"""
Configuration module for Real-Time Facial Recognition & Access System
Centralized settings for camera, recognition, database, and web server.
"""

# ============================================================================
# CAMERA & FRAME CAPTURE SETTINGS
# ============================================================================
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30
FRAME_SKIP = 3  # Process every Nth frame (trade-off between speed & accuracy)
FRAME_QUEUE_SIZE = 30  # Max frames in processing queue

# ============================================================================
# FACE RECOGNITION SETTINGS
# ============================================================================
# Cosine distance threshold for face matching (lower = stricter matching)
# Range: 0.0 (identical) to 2.0 (completely different)
# Recommended: 0.45-0.55 for high accuracy (>95%)
RECOGNITION_THRESHOLD = 0.50

# Fallback: Euclidean distance threshold (if using legacy matching)
EUCLIDEAN_THRESHOLD = 0.6

# Face detection model: "hog" (fast, CPU) or "cnn" (accurate, GPU)
FACE_DETECTION_MODEL = "hog"

# Minimum face confidence before processing encodings
MIN_FACE_SIZE = 20  # pixels

# ============================================================================
# DATABASE SETTINGS
# ============================================================================
DATABASE_FILE = "faces.db"
DATABASE_TIMEOUT = 30  # seconds
DATABASE_ISOLATION_LEVEL = None  # Autocommit mode for faster writes

# Connection pool settings
DB_POOL_SIZE = 5
DB_POOL_TIMEOUT = 10

# ============================================================================
# ACCESS LOGGING SETTINGS
# ============================================================================
LOG_COOLDOWN_SECONDS = 10  # Prevent duplicate logs within this window
LOG_CONFIDENCE_THRESHOLD = 0.5  # Only log if confidence >= this value

# ============================================================================
# WEB SERVER SETTINGS
# ============================================================================
WEB_HOST = "0.0.0.0"
WEB_PORT = 5000
DEBUG_MODE = False
THREADED_MODE = True

# MJPEG streaming settings
MJPEG_QUALITY = 80  # JPEG quality (1-100)
MJPEG_FRAME_RATE = 30  # Target frames per second in web UI

# ============================================================================
# FILE PATHS
# ============================================================================
KNOWN_FACES_DIR = "known_faces"
ENCODINGS_FILE = "encodings.pkl"
ENCODINGS_JSON_FILE = "encodings.json"  # Alternative human-readable format
REPORTS_DIR = "reports"

# ============================================================================
# PERFORMANCE & OPTIMIZATION
# ============================================================================
# Target latency per frame (milliseconds)
TARGET_LATENCY_MS = 300

# Enable performance metrics logging
ENABLE_METRICS = True
METRICS_FILE = "performance_metrics.log"

# Frame resizing for faster processing
RECOGNITION_FRAME_SCALE = 0.5  # 50% scale for faster face detection

# Batch verification settings (for CSV import, etc.)
MAX_BATCH_SIZE = 100
BATCH_TIMEOUT_SECONDS = 60

# ============================================================================
# ACCURACY & TESTING
# ============================================================================
# Target accuracy metrics
TARGET_ACCURACY = 0.95  # 95% classification accuracy
TARGET_FPS = 15  # Minimum sustained FPS
TARGET_IDENTITIES = 50  # Support 50+ enrolled identities

# ============================================================================
# LOGGING & DEBUGGING
# ============================================================================
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
LOG_FILE = "app.log"
LOG_MAX_BYTES = 5242880  # 5MB
LOG_BACKUP_COUNT = 5  # Keep 5 backup logs

# ============================================================================
# CSV REPORT SETTINGS
# ============================================================================
CSV_DELIMITER = ","
CSV_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
CSV_REPORT_FIELDS = ["timestamp", "person_name", "confidence", "identity_id"]

# ============================================================================
# DISPLAY & UI SETTINGS
# ============================================================================
# Bounding box colors (BGR format for OpenCV)
COLOR_KNOWN_FACE = (0, 255, 0)  # Green
COLOR_UNKNOWN_FACE = (0, 0, 255)  # Red
COLOR_BOX_THICKNESS = 2
TEXT_FONT_SCALE = 0.6
TEXT_THICKNESS = 2

# ============================================================================
# HARDWARE OPTIMIZATION FOR RASPBERRY PI
# ============================================================================
USE_GPU = False  # Set to True if using Coral TPU or other GPU
NUM_WORKER_THREADS = 4  # Number of recognition worker threads
MEMORY_LIMIT_MB = 500  # Max memory per worker thread (warn if exceeded)

# ============================================================================
# SECURITY SETTINGS
# ============================================================================
ENABLE_AUDIT_LOG = True  # Log all recognition attempts (successful & failed)
SESSION_TIMEOUT_MINUTES = 30  # Session timeout for web UI
MAX_LOGIN_ATTEMPTS = 5  # Consecutive failed attempts before lockout

# Print configuration on startup
if __name__ == "__main__":
    import pprint
    print("Current Configuration:")
    pprint.pprint({k: v for k, v in globals().items() if not k.startswith('_')})
