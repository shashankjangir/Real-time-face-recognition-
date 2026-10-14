"""
Real-Time Facial Recognition & Access System - Flask Web Server
Production-grade recognition pipeline with frame queuing, multi-threaded processing,
and comprehensive web dashboard with statistics and reporting.
"""

import os
import sys

# Ensure src is on sys.path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(parent_dir, 'src')
sys.path.insert(0, src_dir)
sys.path.insert(0, parent_dir)

from src.app import app, initialize_pipeline
import src.config as config

if __name__ == '__main__':
    initialize_pipeline()
    print("\n" + "=" * 70)
    print("🎥 REAL-TIME FACIAL RECOGNITION & STREAMING SERVER")
    print(f"   Dashboard: http://{config.WEB_HOST}:{config.WEB_PORT}")
    print("=" * 70 + "\n")

    app.run(
        host=config.WEB_HOST,
        port=config.WEB_PORT,
        debug=config.DEBUG_MODE,
        threaded=config.THREADED_MODE
    )
