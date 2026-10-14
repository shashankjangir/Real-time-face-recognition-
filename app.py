"""
Real-Time Facial Recognition & Access System
Main Application Entry Point (Raspberry Pi 5 / Edge Architecture)
"""

import os
import sys

# Add src to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.app import app, initialize_pipeline
import src.config as config

if __name__ == '__main__':
    initialize_pipeline()
    print("\n" + "=" * 70)
    print("🎥 REAL-TIME FACIAL RECOGNITION & ACCESS CONTROL SYSTEM")
    print("   Architecture: Raspberry Pi 5 / Edge (128D Deep Metric Learning)")
    print(f"   Web Dashboard: http://{config.WEB_HOST}:{config.WEB_PORT}")
    print(f"   Database:      {config.DATABASE_FILE} (SQLite + WAL)")
    print(f"   Workers:       {config.NUM_WORKER_THREADS} Threads | Frame Skip: {config.FRAME_SKIP}")
    print("=" * 70 + "\n")

    app.run(
        host=config.WEB_HOST,
        port=config.WEB_PORT,
        debug=config.DEBUG_MODE,
        threaded=config.THREADED_MODE
    )
