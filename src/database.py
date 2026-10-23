"""
Database module for Real-Time Facial Recognition & Access System
Structured SQLite database with B-tree indexing, WAL concurrency, and transaction management.
"""

import sqlite3
import threading
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any
from contextlib import contextmanager
from queue import Queue
import os
import uuid
import numpy as np

try:
    from . import config
except (ImportError, ValueError):
    import config

logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE SCHEMA & STRATEGIC INDEXES
# ============================================================================
SCHEMA_SQL = """
-- Identities table: Enrolled individuals with 128D embedding vectors
CREATE TABLE IF NOT EXISTS identities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    encoding BLOB NOT NULL,
    enrollment_date TEXT NOT NULL,
    quality_score REAL DEFAULT 1.0,
    photo_path TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Enrollment history: Track re-enrollments and multi-sample embeddings
CREATE TABLE IF NOT EXISTS enrollment_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id INTEGER NOT NULL,
    photo_path TEXT,
    encoding BLOB NOT NULL,
    quality_score REAL,
    timestamp TEXT NOT NULL,
    status TEXT DEFAULT 'completed',
    notes TEXT,
    FOREIGN KEY (identity_id) REFERENCES identities(id) ON DELETE CASCADE
);

-- Access log: Real-time authentication transactions
CREATE TABLE IF NOT EXISTS access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id INTEGER,
    name TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    confidence REAL NOT NULL,
    frame_id INTEGER,
    detection_model TEXT DEFAULT 'hog',
    match_distance REAL,
    session_id TEXT,
    status TEXT DEFAULT 'verified',
    FOREIGN KEY (identity_id) REFERENCES identities(id) ON DELETE SET NULL
);

-- Sessions: Access control service execution sessions
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    start_time TEXT NOT NULL,
    end_time TEXT,
    total_recognitions INTEGER DEFAULT 0,
    unique_identities INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active'
);

-- System performance metrics: Hardware latency and throughput telemetry
CREATE TABLE IF NOT EXISTS performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    frame_latency_ms REAL,
    recognition_latency_ms REAL,
    fps REAL,
    queue_size INTEGER,
    memory_mb REAL,
    identities_count INTEGER,
    notes TEXT
);

-- ============================================================================
-- STRATEGIC B-TREE INDEXES FOR REAL-TIME TRANSACTIONS & REPORTING
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_identities_name ON identities(name);
CREATE INDEX IF NOT EXISTS idx_identities_created_at ON identities(created_at);

CREATE INDEX IF NOT EXISTS idx_enrollment_identity_id ON enrollment_history(identity_id);
CREATE INDEX IF NOT EXISTS idx_enrollment_timestamp ON enrollment_history(timestamp);

-- Access log indexes (Ensures <5ms query times across 100k+ access records)
CREATE INDEX IF NOT EXISTS idx_access_log_name ON access_log(name);
CREATE INDEX IF NOT EXISTS idx_access_log_timestamp ON access_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_access_log_confidence ON access_log(confidence);
CREATE INDEX IF NOT EXISTS idx_access_log_identity_id ON access_log(identity_id);
CREATE INDEX IF NOT EXISTS idx_access_log_session_id ON access_log(session_id);
CREATE INDEX IF NOT EXISTS idx_access_log_status ON access_log(status);

-- Composite indexes for high-frequency dashboard and CSV date-range queries
CREATE INDEX IF NOT EXISTS idx_access_log_name_time 
    ON access_log(name, timestamp);
CREATE INDEX IF NOT EXISTS idx_access_log_time_status 
    ON access_log(timestamp, status);

CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON sessions(start_time);
CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON performance_metrics(timestamp);
"""

# ============================================================================
# THREAD-SAFE CONNECTION POOL
# ============================================================================
class DatabasePool:
    """Thread-safe SQLite connection pool with WAL mode optimization."""

    def __init__(self, db_file: str, pool_size: int = 5):
        self.db_file = db_file
        self.pool_size = pool_size
        self.available: Queue = Queue(maxsize=pool_size)
        self.lock = threading.Lock()
        self.memory_uri = f"file:{uuid.uuid4().hex}?mode=memory&cache=shared"

        for _ in range(pool_size):
            conn = self._create_connection()
            self.available.put(conn)

    def _create_connection(self) -> sqlite3.Connection:
        if self.db_file == ":memory:":
            conn = sqlite3.connect(
                self.memory_uri,
                uri=True,
                timeout=config.DATABASE_TIMEOUT,
                isolation_level=config.DATABASE_ISOLATION_LEVEL,
                check_same_thread=False
            )
        else:
            conn = sqlite3.connect(
                self.db_file,
                timeout=config.DATABASE_TIMEOUT,
                isolation_level=config.DATABASE_ISOLATION_LEVEL,
                check_same_thread=False
            )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")

        # Enable Write-Ahead Logging (WAL) for concurrent read/write throughput
        if config.ENABLE_WAL_MODE and self.db_file != ":memory:":
            try:
                conn.execute("PRAGMA journal_mode = WAL;")
                conn.execute("PRAGMA synchronous = NORMAL;")
                conn.execute("PRAGMA busy_timeout = 5000;")
            except Exception as e:
                logger.warning(f"Could not enable WAL mode: {e}")

        return conn

    @contextmanager
    def get_connection(self):
        try:
            conn = self.available.get(timeout=config.DB_POOL_TIMEOUT)
        except Exception:
            raise RuntimeError(f"Database connection pool exhausted (size={self.pool_size}, timeout={config.DB_POOL_TIMEOUT}s)")
        try:
            yield conn
        finally:
            self.available.put(conn)

    def close_all(self):
        while not self.available.empty():
            try:
                conn = self.available.get_nowait()
                conn.close()
            except Exception:
                pass


# ============================================================================
# DATABASE MANAGER
# ============================================================================
class DatabaseManager:
    """High-level database operations for face recognition access control."""

    def __init__(self, db_file: str = None):
        self.db_file = db_file or config.DATABASE_FILE
        # Ensure parent directory exists
        if self.db_file != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_file)), exist_ok=True)
            
        self.pool = DatabasePool(self.db_file, pool_size=config.DB_POOL_SIZE)
        self._initialize_schema()
        self._adaptation_lock = threading.Lock()
        self._last_adaptation: Dict[int, float] = {}

    def _initialize_schema(self):
        """Execute DDL statements and create indexes."""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            for stmt in SCHEMA_SQL.split(';'):
                stmt = stmt.strip()
                if stmt:
                    cursor.execute(stmt)
            columns = {row['name'] for row in conn.execute("PRAGMA table_info(access_log)")}
            for name in ('decision', 'reason', 'action_outcome', 'action_detail', 'event_key'):
                if name not in columns:
                    conn.execute(f"ALTER TABLE access_log ADD COLUMN {name} TEXT")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_access_event ON access_log(event_key)")
            conn.commit()
            logger.info("Database schema and indexes verified.")

    # ========================================================================
    # IDENTITY MANAGEMENT
    # ========================================================================
    def add_identity(self, name: str, encoding: bytes, quality_score: float = 1.0,
                     photo_path: str = None, notes: str = None) -> int:
        """Enroll or update a person's 128D facial representation."""
        now = datetime.now().isoformat()
        with self.pool.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = conn.cursor()
                # Upsert into identities
                cursor.execute("""
                    INSERT INTO identities (name, encoding, enrollment_date, quality_score, photo_path, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        encoding = excluded.encoding,
                        enrollment_date = excluded.enrollment_date,
                        quality_score = excluded.quality_score,
                        photo_path = COALESCE(excluded.photo_path, identities.photo_path),
                        notes = COALESCE(excluded.notes, identities.notes)
                """, (name, encoding, now, quality_score, photo_path, notes))
    
                identity_id = conn.execute("SELECT id FROM identities WHERE name = ?", (name,)).fetchone()["id"]
    
                # Add to enrollment history
                if identity_id:
                    cursor.execute("""
                        INSERT INTO enrollment_history (identity_id, photo_path, encoding, quality_score, timestamp, status, notes)
                        VALUES (?, ?, ?, ?, ?, 'completed', ?)
                    """, (identity_id, photo_path, encoding, quality_score, now, notes))
    
                conn.commit()
                return identity_id
            except Exception:
                conn.rollback()
                raise

    def get_identity_by_name(self, name: str) -> Optional[Dict]:
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM identities WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_identity_by_id(self, identity_id: int) -> Optional[Dict]:
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM identities WHERE id = ?", (identity_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_identities(self) -> List[Dict]:
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, encoding, enrollment_date, quality_score, photo_path, notes, created_at FROM identities ORDER BY name ASC")
            return [dict(row) for row in cursor.fetchall()]

    def delete_identity(self, name_or_id) -> bool:
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            if isinstance(name_or_id, int) or (isinstance(name_or_id, str) and name_or_id.isdigit()):
                cursor.execute("DELETE FROM identities WHERE id = ?", (int(name_or_id),))
            else:
                cursor.execute("DELETE FROM identities WHERE name = ?", (str(name_or_id),))
            conn.commit()
            return cursor.rowcount > 0

    def get_identity_count(self) -> int:
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS total FROM identities")
            return cursor.fetchone()['total']

    # ========================================================================
    # ACCESS LOGGING & TRANSACTIONS
    # ========================================================================
    def log_recognition(self, identity_id: Optional[int], name: str, confidence: float,
                        match_distance: float = 0.0, status: str = 'verified',
                        frame_id: Optional[int] = None, session_id: Optional[str] = None,
                        detection_model: str = 'hog', decision=None, reason=None,
                        action_outcome=None, action_detail=None, event_key=None) -> int:
        """Insert access record with transaction timestamp."""
        now = datetime.now().isoformat()
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO access_log (
                    identity_id, name, timestamp, confidence, frame_id,
                    detection_model, match_distance, session_id, status,
                    decision, reason, action_outcome, action_detail, event_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (identity_id, name, now, confidence, frame_id, detection_model, match_distance, session_id, status,
                  decision, reason, action_outcome, action_detail, event_key))
            conn.commit()
            return cursor.lastrowid

    def update_action_outcome(self, log_id, outcome, detail=None):
        with self.pool.get_connection() as conn:
            conn.execute("UPDATE access_log SET action_outcome=?, action_detail=? WHERE id=?",
                         (outcome, detail, log_id))
            conn.commit()

    def adapt_identity_template(self, identity_id: int, new_encoding, alpha: float = 0.95, min_interval: float = 10.0) -> bool:
        """Gradually blend confident new captures into the enrolled template (Apple momentum update).
        Rate-limited per identity (default 10s min_interval) to protect SQLite from lock contention
        and flash storage wear during continuous 30 FPS video streaming.
        """
        now = time.monotonic()
        with self._adaptation_lock:
            if min_interval > 0:
                last = self._last_adaptation.get(identity_id, 0.0)
                if now - last < min_interval:
                    return False
                self._last_adaptation[identity_id] = now

        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT encoding FROM identities WHERE id = ?", (identity_id,))
            row = cursor.fetchone()
            if not row:
                return False
            old_vec = np.frombuffer(row['encoding'], dtype=np.float64)
            stacked = alpha * old_vec + (1.0 - alpha) * np.asarray(new_encoding, dtype=np.float64)
            norm = np.linalg.norm(stacked)
            updated = stacked / norm if norm > 1e-10 else stacked
            cursor.execute("UPDATE identities SET encoding = ? WHERE id = ?", (updated.tobytes(), identity_id))
            conn.commit()
            return True

    def get_recent_logs(self, limit: int = 50, name: str = None, hours: int = 24, before_id: int = None) -> List[Dict]:
        """Fetch latest authentication records using indexed timestamp lookup."""
        since_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        query = "SELECT * FROM access_log WHERE timestamp >= ?"
        params: List[Any] = [since_time]

        if name:
            query += " AND name = ?"
            params.append(name)

        if before_id is not None:
            query += " AND (timestamp, id) < (SELECT timestamp, id FROM access_log WHERE id = ?)"
            params.append(before_id)
        query += " ORDER BY timestamp DESC, id DESC LIMIT ?"
        params.append(limit)

        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_logs_by_date_range(self, start_date: str, end_date: str,
                               name: str = None, status: str = None,
                               min_confidence: float = 0.0) -> List[Dict]:
        """Query access logs across date range leveraging composite index."""
        query = "SELECT * FROM access_log WHERE timestamp >= ? AND timestamp <= ?"
        params: List[Any] = [start_date, end_date]

        if name:
            query += " AND name = ?"
            params.append(name)
        if status:
            query += " AND status = ?"
            params.append(status)
        if min_confidence > 0.0:
            query += " AND confidence >= ?"
            params.append(min_confidence)

        query += " ORDER BY timestamp ASC"

        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    # ========================================================================
    # STATISTICAL AGGREGATION & SESSIONS
    # ========================================================================
    def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Compute aggregate system metrics over specified time window."""
        since_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT 
                    COUNT(*) as total_recognitions,
                    COUNT(DISTINCT name) as unique_identities,
                    AVG(confidence) as avg_confidence,
                    AVG(match_distance) as avg_match_distance,
                    SUM(CASE WHEN status = 'verified' THEN 1 ELSE 0 END) as verified_count,
                    SUM(CASE WHEN status != 'verified' THEN 1 ELSE 0 END) as rejected_count
                FROM access_log
                WHERE timestamp >= ?
            """, (since_time,))
            row = cursor.fetchone()

            total = row['total_recognitions'] or 0
            unique = row['unique_identities'] or 0
            avg_conf = row['avg_confidence'] or 0.0
            avg_dist = row['avg_match_distance'] or 0.0
            verified = row['verified_count'] or 0
            rejected = row['rejected_count'] or 0

            cursor.execute("SELECT COUNT(*) as total_enrolled FROM identities")
            enrolled = cursor.fetchone()['total_enrolled']

            return {
                'hours_window': hours,
                'total_recognitions': total,
                'unique_identities': unique,
                'avg_confidence': round(avg_conf, 3),
                'avg_match_distance': round(avg_dist, 3),
                'verified_count': verified,
                'rejected_count': rejected,
                'total_enrolled': enrolled,
                'verification_rate': round(verified / total * 100, 1) if total > 0 else 100.0
            }

    def create_session(self, session_id: str) -> str:
        now = datetime.now().isoformat()
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO sessions (id, start_time, status)
                VALUES (?, ?, 'active')
            """, (session_id, now))
            conn.commit()
            return session_id

    def close_session(self, session_id: str):
        now = datetime.now().isoformat()
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sessions 
                SET end_time = ?, status = 'closed',
                    total_recognitions = (SELECT COUNT(*) FROM access_log WHERE session_id = ?),
                    unique_identities = (SELECT COUNT(DISTINCT name) FROM access_log WHERE session_id = ?)
                WHERE id = ?
            """, (now, session_id, session_id, session_id))
            conn.commit()

    def log_performance_metric(self, frame_latency_ms: float, recognition_latency_ms: float,
                               fps: float, queue_size: int, memory_mb: float = 0.0,
                               identities_count: int = 0, notes: str = None):
        now = datetime.now().isoformat()
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO performance_metrics (
                    timestamp, frame_latency_ms, recognition_latency_ms,
                    fps, queue_size, memory_mb, identities_count, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (now, frame_latency_ms, recognition_latency_ms, fps, queue_size, memory_mb, identities_count, notes))
            conn.commit()

    def explain_query(self, query: str, params: Tuple = ()) -> List[Dict]:
        """Explain query plan to verify SQLite index utilization."""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"EXPLAIN QUERY PLAN {query}", params)
            return [dict(row) for row in cursor.fetchall()]

    def close(self):
        self.pool.close_all()


# Global Singleton
_db_manager_instance = None
_db_lock = threading.Lock()

def get_db_manager(db_file: str = None) -> DatabaseManager:
    global _db_manager_instance
    with _db_lock:
        if _db_manager_instance is None or (db_file and _db_manager_instance.db_file != db_file):
            _db_manager_instance = DatabaseManager(db_file=db_file)
        return _db_manager_instance

def reset_db_manager():
    """Reset the global singleton. Use in tests for isolation."""
    global _db_manager_instance
    with _db_lock:
        if _db_manager_instance is not None:
            _db_manager_instance.close()
            _db_manager_instance = None
