"""
Database module for Real-Time Facial Recognition & Access System
Handles SQLite schema initialization, connection pooling, and transaction management.
"""

import sqlite3
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from contextlib import contextmanager
from queue import Queue

import config

# ============================================================================
# LOGGING SETUP
# ============================================================================
logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE SCHEMA
# ============================================================================
SCHEMA = """
-- Identities table: stores enrolled face information
CREATE TABLE IF NOT EXISTS identities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    encoding BLOB NOT NULL,  -- 128D embedding as binary
    enrollment_date TEXT NOT NULL,
    quality_score REAL,  -- 0.0-1.0: face image quality rating
    photo_path TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Enrollment history: track face re-enrollments and updates
CREATE TABLE IF NOT EXISTS enrollment_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id INTEGER NOT NULL,
    photo_path TEXT,
    encoding BLOB NOT NULL,
    quality_score REAL,
    timestamp TEXT NOT NULL,
    status TEXT DEFAULT 'completed',  -- 'completed', 'rejected', 'duplicate_detected'
    notes TEXT,
    FOREIGN KEY (identity_id) REFERENCES identities(id) ON DELETE CASCADE
);

-- Access log: transaction-based recognition logging
CREATE TABLE IF NOT EXISTS access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    confidence REAL NOT NULL,  -- 0.0-1.0: matching confidence
    frame_id INTEGER,  -- For linking to frame buffer if stored
    detection_model TEXT DEFAULT 'hog',  -- 'hog', 'cnn', etc.
    match_distance REAL,  -- Raw Euclidean or cosine distance
    session_id TEXT,  -- For grouping related recognitions
    status TEXT DEFAULT 'verified',  -- 'verified', 'low_confidence', 'duplicate_suppressed'
    FOREIGN KEY (identity_id) REFERENCES identities(id) ON DELETE SET NULL
);

-- Sessions table: logical grouping of access events
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    start_time TEXT NOT NULL,
    end_time TEXT,
    total_recognitions INTEGER DEFAULT 0,
    unique_identities INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active'  -- 'active', 'closed'
);

-- System performance metrics
CREATE TABLE IF NOT EXISTS performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    frame_latency_ms REAL,  -- Time to process one frame
    recognition_latency_ms REAL,  -- Time to recognize one face
    fps REAL,  -- Frames per second
    queue_size INTEGER,  -- Current frame queue depth
    memory_mb REAL,  -- Memory usage
    identities_count INTEGER,  -- Total enrolled identities
    notes TEXT
);

-- ============================================================================
-- INDEXES FOR QUERY OPTIMIZATION
-- ============================================================================

-- Identities indexes
CREATE INDEX IF NOT EXISTS idx_identities_name ON identities(name);
CREATE INDEX IF NOT EXISTS idx_identities_created_at ON identities(created_at);

-- Enrollment history indexes
CREATE INDEX IF NOT EXISTS idx_enrollment_identity_id ON enrollment_history(identity_id);
CREATE INDEX IF NOT EXISTS idx_enrollment_timestamp ON enrollment_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_enrollment_status ON enrollment_history(status);

-- Access log indexes (critical for fast queries)
CREATE INDEX IF NOT EXISTS idx_access_log_name ON access_log(name);
CREATE INDEX IF NOT EXISTS idx_access_log_timestamp ON access_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_access_log_confidence ON access_log(confidence);
CREATE INDEX IF NOT EXISTS idx_access_log_identity_id ON access_log(identity_id);
CREATE INDEX IF NOT EXISTS idx_access_log_session_id ON access_log(session_id);
CREATE INDEX IF NOT EXISTS idx_access_log_status ON access_log(status);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_access_log_name_timestamp 
    ON access_log(name, timestamp) WHERE status = 'verified';
CREATE INDEX IF NOT EXISTS idx_access_log_date_range 
    ON access_log(timestamp, confidence) WHERE status = 'verified';

-- Sessions indexes
CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON sessions(start_time);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);

-- Performance metrics indexes
CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON performance_metrics(timestamp);
"""

# ============================================================================
# CONNECTION POOL CLASS
# ============================================================================
class DatabasePool:
    """Thread-safe SQLite connection pool."""

    def __init__(self, db_file: str, pool_size: int = 5):
        self.db_file = db_file
        self.pool_size = pool_size
        self.available = Queue(maxsize=pool_size)
        self.lock = threading.Lock()

        # Pre-populate pool
        for _ in range(pool_size):
            conn = self._create_connection()
            self.available.put(conn)

    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection."""
        conn = sqlite3.connect(
            self.db_file,
            timeout=config.DATABASE_TIMEOUT,
            isolation_level=config.DATABASE_ISOLATION_LEVEL,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def get_connection(self):
        """Context manager for getting a connection from pool."""
        conn = self.available.get(timeout=config.DB_POOL_TIMEOUT)
        try:
            yield conn
        finally:
            self.available.put(conn)

    def close_all(self):
        """Close all connections in pool."""
        while not self.available.empty():
            conn = self.available.get_nowait()
            conn.close()


# ============================================================================
# DATABASE MANAGER CLASS
# ============================================================================
class DatabaseManager:
    """High-level database operations for face recognition system."""

    def __init__(self, db_file: str = config.DATABASE_FILE):
        self.db_file = db_file
        self.pool = DatabasePool(db_file, pool_size=config.DB_POOL_SIZE)
        self._initialize_schema()

    def _initialize_schema(self):
        """Initialize database schema and indexes."""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            # Split schema into individual statements and execute
            statements = SCHEMA.split(';')
            for statement in statements:
                statement = statement.strip()
                if statement:
                    cursor.execute(statement)
            conn.commit()
            logger.info("Database schema initialized successfully")

    # ========================================================================
    # IDENTITY MANAGEMENT
    # ========================================================================

    def add_identity(self, name: str, encoding: bytes, quality_score: float = 1.0, 
                     photo_path: str = None, notes: str = None) -> int:
        """Add a new enrolled identity."""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO identities (name, encoding, enrollment_date, quality_score, photo_path, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (name, encoding, datetime.now().isoformat(), quality_score, photo_path, notes))
                conn.commit()
                identity_id = cursor.lastrowid
                logger.info(f"Added identity: {name} (ID: {identity_id})")
                return identity_id
            except sqlite3.IntegrityError:
                logger.warning(f"Identity '{name}' already exists")
                raise ValueError(f"Identity '{name}' already exists")

    def get_identity_by_name(self, name: str) -> Optional[Dict]:
        """Retrieve identity by name."""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM identities WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_identities(self) -> List[Dict]:
        """Retrieve all enrolled identities."""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, encoding, quality_score FROM identities ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]

    def delete_identity(self, identity_id: int) -> bool:
        """Delete an identity (cascades to enrollment history)."""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM identities WHERE id = ?", (identity_id,))
            conn.commit()
            return cursor.rowcount > 0

    def update_identity(self, identity_id: int, name: str = None, encoding: bytes = None, 
                       quality_score: float = None) -> bool:
        """Update identity information."""
        updates = []
        params = []

        if name:
            updates.append("name = ?")
            params.append(name)
        if encoding:
            updates.append("encoding = ?")
            params.append(encoding)
        if quality_score is not None:
            updates.append("quality_score = ?")
            params.append(quality_score)

        if not updates:
            return False

        params.append(identity_id)
        query = f"UPDATE identities SET {', '.join(updates)} WHERE id = ?"

        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0

    # ========================================================================
    # ENROLLMENT HISTORY
    # ========================================================================

    def log_enrollment(self, identity_id: int, encoding: bytes, quality_score: float, 
                       photo_path: str = None, status: str = 'completed', notes: str = None):
        """Log an enrollment attempt."""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO enrollment_history (identity_id, photo_path, encoding, quality_score, timestamp, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (identity_id, photo_path, encoding, quality_score, datetime.now().isoformat(), status, notes))
            conn.commit()

    def get_enrollment_history(self, identity_id: int, limit: int = 10) -> List[Dict]:
        """Get enrollment history for an identity."""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM enrollment_history 
                WHERE identity_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (identity_id, limit))
            return [dict(row) for row in cursor.fetchall()]

    # ========================================================================
    # ACCESS LOGGING
    # ========================================================================

    def log_recognition(self, identity_id: Optional[int], name: str, confidence: float, 
                       match_distance: float = None, session_id: str = None, 
                       status: str = 'verified', detection_model: str = 'hog') -> int:
        """Log a recognition event."""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO access_log 
                (identity_id, name, timestamp, confidence, match_distance, session_id, status, detection_model)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (identity_id, name, datetime.now().isoformat(), confidence, match_distance, session_id, status, detection_model))
            conn.commit()
            return cursor.lastrowid

    def get_recent_logs(self, limit: int = 50, name: str = None, 
                       hours: int = 24) -> List[Dict]:
        """Get recent access logs with optional filtering."""
        time_cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            if name:
                cursor.execute("""
                    SELECT * FROM access_log 
                    WHERE name = ? AND timestamp >= ? AND status = 'verified'
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (name, time_cutoff, limit))
            else:
                cursor.execute("""
                    SELECT * FROM access_log 
                    WHERE timestamp >= ? AND status = 'verified'
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (time_cutoff, limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_logs_by_date_range(self, start_date: str, end_date: str, 
                              name: str = None) -> List[Dict]:
        """Get logs within a date range."""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            if name:
                cursor.execute("""
                    SELECT * FROM access_log 
                    WHERE name = ? AND timestamp BETWEEN ? AND ? AND status = 'verified'
                    ORDER BY timestamp DESC
                """, (name, start_date, end_date))
            else:
                cursor.execute("""
                    SELECT * FROM access_log 
                    WHERE timestamp BETWEEN ? AND ? AND status = 'verified'
                    ORDER BY timestamp DESC
                """, (start_date, end_date))
            return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self, hours: int = 24) -> Dict:
        """Get recognition statistics."""
        time_cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

        with self.pool.get_connection() as conn:
            cursor = conn.cursor()

            # Total recognitions
            cursor.execute("""
                SELECT COUNT(*) as count FROM access_log 
                WHERE timestamp >= ? AND status = 'verified'
            """, (time_cutoff,))
            total = cursor.fetchone()['count']

            # Unique identities
            cursor.execute("""
                SELECT COUNT(DISTINCT name) as count FROM access_log 
                WHERE timestamp >= ? AND status = 'verified'
            """, (time_cutoff,))
            unique = cursor.fetchone()['count']

            # Average confidence
            cursor.execute("""
                SELECT AVG(confidence) as avg FROM access_log 
                WHERE timestamp >= ? AND status = 'verified'
            """, (time_cutoff,))
            avg_confidence = cursor.fetchone()['avg'] or 0.0

            # Top identities
            cursor.execute("""
                SELECT name, COUNT(*) as count FROM access_log 
                WHERE timestamp >= ? AND status = 'verified'
                GROUP BY name 
                ORDER BY count DESC 
                LIMIT 10
            """, (time_cutoff,))
            top_identities = [dict(row) for row in cursor.fetchall()]

            return {
                'total_recognitions': total,
                'unique_identities': unique,
                'avg_confidence': round(avg_confidence, 3),
                'top_identities': top_identities
            }

    # ========================================================================
    # SESSION MANAGEMENT
    # ========================================================================

    def create_session(self, session_id: str) -> str:
        """Create a new recognition session."""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sessions (id, start_time, status)
                VALUES (?, ?, 'active')
            """, (session_id, datetime.now().isoformat()))
            conn.commit()
            return session_id

    def close_session(self, session_id: str):
        """Close an active session."""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sessions 
                SET end_time = ?, status = 'closed'
                WHERE id = ?
            """, (datetime.now().isoformat(), session_id))
            conn.commit()

    # ========================================================================
    # PERFORMANCE METRICS
    # ========================================================================

    def log_metrics(self, frame_latency_ms: float, recognition_latency_ms: float = None,
                   fps: float = None, queue_size: int = None, memory_mb: float = None,
                   identities_count: int = None, notes: str = None):
        """Log performance metrics."""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO performance_metrics 
                (timestamp, frame_latency_ms, recognition_latency_ms, fps, queue_size, memory_mb, identities_count, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (datetime.now().isoformat(), frame_latency_ms, recognition_latency_ms, fps, queue_size, memory_mb, identities_count, notes))
            conn.commit()

    def get_metrics_summary(self, hours: int = 24) -> Dict:
        """Get performance metrics summary."""
        time_cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    AVG(frame_latency_ms) as avg_frame_latency,
                    MAX(frame_latency_ms) as max_frame_latency,
                    AVG(fps) as avg_fps,
                    MIN(fps) as min_fps,
                    AVG(memory_mb) as avg_memory
                FROM performance_metrics 
                WHERE timestamp >= ?
            """, (time_cutoff,))
            result = cursor.fetchone()
            return dict(result) if result else {}

    # ========================================================================
    # CLEANUP & MAINTENANCE
    # ========================================================================

    def cleanup_old_logs(self, days: int = 30):
        """Delete logs older than specified days."""
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM access_log WHERE timestamp < ?", (cutoff_date,))
            deleted = cursor.rowcount
            conn.commit()
            logger.info(f"Deleted {deleted} old access logs")
            return deleted

    def vacuum(self):
        """Optimize database file size."""
        with self.pool.get_connection() as conn:
            conn.execute("VACUUM")
            logger.info("Database vacuumed")

    def close(self):
        """Close all database connections."""
        self.pool.close_all()
        logger.info("Database connections closed")


# ============================================================================
# MODULE-LEVEL SINGLETON
# ============================================================================
_db_manager = None

def get_db_manager() -> DatabaseManager:
    """Get or create singleton database manager."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    db = DatabaseManager()
    stats = db.get_statistics()
    print(f"Database Statistics: {stats}")
    db.close()
