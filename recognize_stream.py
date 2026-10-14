"""
Real-Time Facial Recognition & Streaming Server
Backward-compatible root entry point for recognize_stream.py
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
    print("🎥 REAL-TIME FACIAL RECOGNITION & STREAMING SERVER")
    print(f"   Dashboard: http://{config.WEB_HOST}:{config.WEB_PORT}")
    print("=" * 70 + "\n")

    app.run(
        host=config.WEB_HOST,
        port=config.WEB_PORT,
        debug=config.DEBUG_MODE,
        threaded=config.THREADED_MODE
    )
