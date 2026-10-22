"""
Compatibility launch entry point forwarding to app.py.
Preserved for backward compatibility with existing deployment scripts and documentation.
"""
from app import app, initialize_pipeline, config

if __name__ == '__main__':
    initialize_pipeline()
    print("\n" + "=" * 70)
    print(">>> REAL-TIME FACIAL RECOGNITION & ACCESS CONTROL SYSTEM (COMPATIBILITY LAUNCH)")
    print(f"   Web Dashboard: http://{config.WEB_HOST}:{config.WEB_PORT}")
    print("=" * 70 + "\n")

    app.run(
        host=config.WEB_HOST,
        port=config.WEB_PORT,
        debug=config.DEBUG_MODE,
        threaded=config.THREADED_MODE
    )
