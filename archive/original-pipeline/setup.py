#!/usr/bin/env python3
"""
Setup & Migration Script for Advanced Facial Recognition System
Initializes database, migrates old data, validates environment.
"""

import os
import sys
import sqlite3
import subprocess
import json
from datetime import datetime
from pathlib import Path

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_step(step_num: int, title: str):
    """Print step header."""
    print(f"\n{Colors.BLUE}[Step {step_num}] {title}{Colors.RESET}")
    print("-" * 70)

def print_success(msg: str):
    """Print success message."""
    print(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")

def print_error(msg: str):
    """Print error message."""
    print(f"{Colors.RED}✗ {msg}{Colors.RESET}")

def print_warning(msg: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.RESET}")

def print_info(msg: str):
    """Print info message."""
    print(f"  → {msg}")

def check_python_version():
    """Verify Python 3.8+."""
    print_step(1, "Check Python Version")

    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print_error(f"Python 3.8+ required, found {version.major}.{version.minor}")
        return False

    print_success(f"Python {version.major}.{version.minor}.{version.micro} detected")
    return True

def check_dependencies():
    """Verify required Python packages."""
    print_step(2, "Check Dependencies")

    required = {
        'flask': 'Flask',
        'cv2': 'OpenCV',
        'numpy': 'NumPy',
        'face_recognition': 'face-recognition',
        'picamera2': 'Picamera2'
    }

    missing = []
    for module, package in required.items():
        try:
            __import__(module)
            print_success(f"{package} installed")
        except ImportError:
            print_error(f"{package} NOT found")
            missing.append(package)

    if missing:
        print(f"\n{Colors.YELLOW}Install missing packages:{Colors.RESET}")
        print(f"  pip install {' '.join(missing)} --break-system-packages")
        return False

    return True

def check_camera():
    """Verify camera is detected."""
    print_step(3, "Check Camera Detection")

    try:
        result = subprocess.run(['rpicam-hello', '--list-cameras'], 
                              capture_output=True, text=True, timeout=5)
        if 'imx708' in result.stdout or 'imx' in result.stdout.lower():
            print_success("Camera detected (Raspberry Pi Camera Module 3)")
            print_info(result.stdout.strip().split('\n')[0])
            return True
        else:
            print_warning("Camera may not be detected correctly")
            print_info("Output: " + result.stdout.strip())
            return True  # Non-blocking warning
    except Exception as e:
        print_warning(f"Could not verify camera: {e}")
        print_info("Run: sudo raspi-config to enable camera if needed")
        return True  # Non-blocking

def initialize_database():
    """Initialize SQLite database with schema."""
    print_step(4, "Initialize Database")

    try:
        from database import DatabaseManager
        db = DatabaseManager()
        print_success("Database initialized with schema")

        # Verify tables
        conn = sqlite3.connect('faces.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        print_info(f"Created {len(tables)} tables: {', '.join(tables)}")
        db.close()
        return True
    except Exception as e:
        print_error(f"Database initialization failed: {e}")
        return False

def migrate_old_encodings():
    """Migrate encodings from old .pkl format (if exists)."""
    print_step(5, "Migrate Old Data (if exists)")

    old_pkl = "encodings.pkl"
    if not os.path.exists(old_pkl):
        print_info("No legacy encodings.pkl found - fresh installation")
        return True

    try:
        import pickle
        import numpy as np
        from database import get_db_manager

        print_info(f"Found legacy {old_pkl} - migrating...")

        with open(old_pkl, 'rb') as f:
            data = pickle.load(f)

        encodings = data.get('encodings', [])
        names = data.get('names', [])

        if len(encodings) != len(names):
            print_error("Encoding/name mismatch in legacy data")
            return False

        db = get_db_manager()

        # Import each face
        for name, encoding in zip(names, encodings):
            if not isinstance(encoding, np.ndarray):
                encoding = np.array(encoding, dtype=np.float64)

            encoding_bytes = encoding.tobytes()

            try:
                db.add_identity(
                    name=name,
                    encoding=encoding_bytes,
                    quality_score=0.8,  # Legacy - unknown quality
                    notes=f"Migrated from legacy encodings.pkl at {datetime.now().isoformat()}"
                )
                print_success(f"Migrated: {name}")
            except ValueError:
                print_warning(f"Already exists: {name} (skipped)")

        print_success(f"Migrated {len(names)} identities")

        # Backup old file
        backup_name = f"encodings_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
        os.rename(old_pkl, backup_name)
        print_info(f"Backed up legacy file to: {backup_name}")

        db.close()
        return True

    except Exception as e:
        print_error(f"Migration failed: {e}")
        return False

def create_directories():
    """Create required directories."""
    print_step(6, "Create Required Directories")

    directories = [
        'known_faces',
        'reports',
        'logs'
    ]

    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print_success(f"Directory ready: {directory}/")

    return True

def generate_config_summary():
    """Generate configuration summary."""
    print_step(7, "Configuration Summary")

    try:
        import config

        essential_params = {
            'Recognition': {
                'RECOGNITION_THRESHOLD': config.RECOGNITION_THRESHOLD,
                'FACE_DETECTION_MODEL': config.FACE_DETECTION_MODEL,
                'NUM_WORKER_THREADS': config.NUM_WORKER_THREADS
            },
            'Performance': {
                'CAMERA_WIDTH': config.CAMERA_WIDTH,
                'CAMERA_HEIGHT': config.CAMERA_HEIGHT,
                'FRAME_SKIP': config.FRAME_SKIP,
                'TARGET_FPS': config.TARGET_FPS,
                'TARGET_LATENCY_MS': config.TARGET_LATENCY_MS
            },
            'Web Server': {
                'WEB_PORT': config.WEB_PORT,
                'WEB_HOST': config.WEB_HOST,
                'MJPEG_QUALITY': config.MJPEG_QUALITY
            },
            'Accuracy Targets': {
                'TARGET_ACCURACY': f"{config.TARGET_ACCURACY * 100:.0f}%",
                'TARGET_IDENTITIES': config.TARGET_IDENTITIES,
                'RECOGNITION_THRESHOLD': config.RECOGNITION_THRESHOLD
            }
        }

        for section, params in essential_params.items():
            print(f"\n  {Colors.BLUE}{section}:{Colors.RESET}")
            for key, value in params.items():
                print(f"    {key}: {value}")

        print_success("Configuration loaded from config.py")
        return True

    except Exception as e:
        print_error(f"Could not load config: {e}")
        return False

def test_database():
    """Test database connectivity and queries."""
    print_step(8, "Test Database Connectivity")

    try:
        from database import get_db_manager

        db = get_db_manager()

        # Test read
        identities = db.get_all_identities()
        print_success(f"Database query successful ({len(identities)} identities)")

        # Test stats
        stats = db.get_statistics(hours=24)
        print_info(f"24-hour recognitions: {stats['total_recognitions']}")
        print_info(f"Unique identities: {stats['unique_identities']}")

        db.close()
        return True

    except Exception as e:
        print_error(f"Database connectivity failed: {e}")
        return False

def validate_system():
    """Run comprehensive system validation."""
    print_step(9, "Validate Complete System")

    try:
        from database import get_db_manager
        from recognition_engine import RecognitionEngine

        db = get_db_manager()
        engine = RecognitionEngine(db_manager=db)

        print_success(f"Database: OK ({db.db_file})")
        print_success(f"Recognition engine: OK ({len(engine.known_names)} identities loaded)")

        db.close()
        return True

    except Exception as e:
        print_error(f"System validation failed: {e}")
        return False

def print_final_instructions():
    """Print final instructions and next steps."""
    print_step(10, "Setup Complete! Next Steps")

    print(f"""
{Colors.GREEN}✓ System is ready to use!{Colors.RESET}

{Colors.BLUE}1. Enroll faces:{Colors.RESET}
   python3 enroll.py
   Options: Single enrollment, batch import, list, delete, export

{Colors.BLUE}2. Start recognition system:{Colors.RESET}
   python3 recognize_stream.py
   Access dashboard at: http://localhost:5000

{Colors.BLUE}3. Optional - View camera stream only:{Colors.RESET}
   python3 camera_stream.py

{Colors.BLUE}4. Access web dashboard:{Colors.RESET}
   Open browser: http://<PI_IP>:5000
   View live video, statistics, recognition history

{Colors.BLUE}5. Generate reports:{Colors.RESET}
   Access logs: http://localhost:5000/api/logs
   Statistics: http://localhost:5000/api/stats
   CSV export: http://localhost:5000/api/csv
   System health: http://localhost:5000/health

{Colors.BLUE}6. Read documentation:{Colors.RESET}
   README_ADVANCED.md - Complete guide
   config.py - All configuration options

{Colors.YELLOW}Performance Targets:{Colors.RESET}
   • Recognition latency: <300ms per identity
   • Sustained throughput: 15-20 FPS
   • Classification accuracy: >95%
   • Enrolled identities: 50+
   • Database response: <50ms

{Colors.YELLOW}To run in background:{Colors.RESET}
   nohup python3 recognize_stream.py > server.log 2>&1 &

{Colors.YELLOW}To view logs:{Colors.RESET}
   tail -f app.log
   tail -f performance_metrics.log

{Colors.BLUE}Need help?{Colors.RESET}
   • Check README_ADVANCED.md for detailed guide
   • Review troubleshooting section
   • Check app.log for errors
""")

def main():
    """Run complete setup."""
    print("\n" + "="*70)
    print("Advanced Facial Recognition System - Setup & Migration")
    print("="*70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Python: {sys.version.split()[0]}")
    print("="*70)

    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Camera", check_camera),
        ("Database Initialization", initialize_database),
        ("Data Migration", migrate_old_encodings),
        ("Directories", create_directories),
        ("Configuration", generate_config_summary),
        ("Database Connectivity", test_database),
        ("System Validation", validate_system)
    ]

    passed = 0
    failed = 0

    for name, check_func in checks:
        try:
            result = check_func()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print_error(f"Unexpected error in {name}: {e}")
            failed += 1

    # Final summary
    print("\n" + "="*70)
    print(f"Setup Results: {Colors.GREEN}{passed} passed{Colors.RESET}, {Colors.RED}{failed} failed{Colors.RESET}")
    print("="*70)

    if failed == 0:
        print_final_instructions()
        return 0
    else:
        print_error("Setup incomplete. Please fix errors above and re-run.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
