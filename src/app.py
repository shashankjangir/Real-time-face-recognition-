"""
Flask Web Dashboard & API Server for Real-Time Facial Recognition & Access System
Provides live MJPEG annotated video streaming, REST APIs, dynamic CSV reporting,
and real-time telemetry analytics.
"""

import os
import sys
import time
import uuid
import logging
import hmac
import threading
from datetime import datetime, timedelta
from typing import Optional
import cv2
import numpy as np
from flask import Flask, render_template, Response, request, jsonify, send_file

try:
    from . import config
    from .database import get_db_manager, DatabaseManager
    from .camera import CameraManager
    from .recognition_engine import RecognitionEngine, FrameQueue, RecognitionWorker
    from .utils import ReportGenerator, Analytics
except (ImportError, ValueError):
    import config
    from database import get_db_manager, DatabaseManager
    from camera import CameraManager
    from recognition_engine import RecognitionEngine, FrameQueue, RecognitionWorker
    from utils import ReportGenerator, Analytics

logger = logging.getLogger(__name__)

# Initialize Flask App
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Global Pipeline State
db_manager: DatabaseManager = None
camera_manager: CameraManager = None
recognition_engine: RecognitionEngine = None
frame_queue: FrameQueue = None
report_generator: ReportGenerator = None
workers = []
session_id = str(uuid.uuid4())
pipeline_initialized = False


pipeline_lock = threading.Lock()
runtime = None

@app.errorhandler(RuntimeError)
def unavailable(exc):
    return jsonify({'status': 'unhealthy', 'message': str(exc)}), 503


def initialize_pipeline():
    global db_manager, camera_manager, recognition_engine, frame_queue, report_generator
    global workers, pipeline_initialized, runtime, session_id
    with pipeline_lock:
        if pipeline_initialized:
            runtime.check_health()
            return
        from .runtime import RecognitionRuntime
        RecognitionEngine.ensure_model_available()
        db_manager = get_db_manager()
        recognition_engine = RecognitionEngine(db_manager=db_manager)
        report_generator = ReportGenerator(db_manager=db_manager)
        camera_manager = CameraManager()
        session_id = str(uuid.uuid4())
        runtime = RecognitionRuntime(recognition_engine, camera_manager, session_id,
                                     action=app.config.get('ACCESS_ACTION'))
        try:
            runtime.start()
        except Exception:
            runtime.stop()
            raise
        frame_queue, workers = runtime.queue, runtime.workers
        pipeline_initialized = True


def shutdown_pipeline():
    global pipeline_initialized
    if runtime:
        runtime.stop()
    pipeline_initialized = False


@app.route('/')
def index():
    return render_template("dashboard.html", quality_threshold=config.ENROLLMENT_MIN_QUALITY)


@app.route('/stream.mjpg')
def video_stream():
    """MJPEG stream serving live frames with visual annotation overlays."""
    initialize_pipeline()

    return Response(runtime.stream(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/stats')
def api_stats():
    """Return JSON telemetry metrics."""
    initialize_pipeline()
    stats = db_manager.get_statistics(hours=24)
    telemetry = runtime.snapshot()
    latency = telemetry["delivery_to_decision_latency"]

    return jsonify({
        'status': 'success',
        'identities_enrolled': stats.get('total_enrolled', len(recognition_engine.known_names)),
        'classification_accuracy': None,
        'camera': {'backend': type(camera_manager.backend).__name__,
                   'autofocus': bool(getattr(camera_manager.backend, 'autofocus_enabled', False)),
                   'resolution': [config.CAMERA_WIDTH, config.CAMERA_HEIGHT]},
        'fps': telemetry['capture_fps'],
        'telemetry': telemetry,
        'avg_latency_ms': round(latency['mean_ms'], 1) if latency else None,
        'total_recognitions_24h': stats.get('total_recognitions', 0),
        'unique_identities_24h': stats.get('unique_identities', 0),
        'workers_active': sum(w.is_alive() for w in workers),
        'session_id': session_id
    })


@app.route('/api/logs')
def api_logs():
    """Query recent access logs using indexed timestamp search."""
    initialize_pipeline()
    limit = request.args.get('limit', default=50, type=int)
    name = request.args.get('name', default=None, type=str)
    hours = request.args.get('hours', default=24, type=int)

    logs = db_manager.get_recent_logs(limit=limit, name=name, hours=hours)
    return jsonify({
        'status': 'success',
        'count': len(logs),
        'logs': logs
    })


@app.route('/api/csv')
def api_csv():
    """Generate dynamic CSV transaction report and download file."""
    initialize_pipeline()
    hours = request.args.get('hours', default=168, type=int)
    name = request.args.get('name', default=None, type=str)

    start_date = (datetime.now() - timedelta(hours=hours)).isoformat()
    end_date = datetime.now().isoformat()

    filepath, content = report_generator.generate_access_log_csv(
        start_date=start_date,
        end_date=end_date,
        person_name=name
    )

    return Response(
        content,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=access_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
    )


@app.route('/api/identities')
def api_identities():
    """List all enrolled identities and quality scores."""
    initialize_pipeline()
    identities = db_manager.get_all_identities()
    clean = [{
        'id': r['id'],
        'name': r['name'],
        'quality_score': r['quality_score'],
        'enrollment_date': r['enrollment_date']
    } for r in identities]
    return jsonify({'status': 'success', 'identities': clean})


def require_administrator():
    configured_token = config.ADMIN_ENROLLMENT_TOKEN
    if not configured_token:
        return jsonify({'status': 'error', 'message': 'Administrator enrollment is not configured.'}), 503
    scheme, _, token = request.headers.get('Authorization', '').partition(' ')
    if scheme.lower() != 'bearer' or not hmac.compare_digest(token.encode('utf-8'), configured_token.encode('utf-8')):
        return jsonify({'status': 'error', 'message': 'Administrator authentication required.'}), 401, {'WWW-Authenticate': 'Bearer'}


@app.route('/api/enrollment/quality', methods=['POST'])
def enrollment_quality():
    auth_error = require_administrator()
    if auth_error is not None:
        return auth_error
    initialize_pipeline()
    from .camera import SyntheticBackend
    from .enroll import face_quality_report
    if isinstance(camera_manager.backend, SyntheticBackend):
        return jsonify(status='error', message='Quality checks require a real camera.'), 503
    frame = camera_manager.get_frame()
    if frame is None:
        return jsonify(status='error', message='No camera frame is available.'), 503
    detections = recognition_engine.detect_and_extract(frame)
    if len(detections) != 1:
        return jsonify(status='success', face_count=len(detections), ready=False,
                       score=None, threshold=config.ENROLLMENT_MIN_QUALITY, components={},
                       guidance=['No face detected. Face the camera and check the lighting.' if not detections
                                 else 'More than one face detected. Only one person should be in view.'])
    box, _ = detections[0]
    return jsonify(status='success', face_count=1, **face_quality_report(frame, box))


@app.route('/api/enroll', methods=['POST'])
def api_enroll():
    """Enroll a new identity."""
    auth_error = require_administrator()
    if auth_error is not None:
        return auth_error
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'status': 'error', 'message': 'A JSON object is required.'}), 400
    name = data.get('name')
    if not isinstance(name, str):
        return jsonify({'status': 'error', 'message': 'Name must be a string.'}), 400
    name = name.strip()
    if not name:
        return jsonify({'status': 'error', 'message': 'Name is required'}), 400
    initialize_pipeline()
    from .camera import SyntheticBackend
    if isinstance(camera_manager.backend, SyntheticBackend):
        return jsonify({'status': 'error', 'message': 'Enrollment requires a real camera.'}), 503
    frame = camera_manager.get_frame()
    from .enroll import enroll_identity, validate_enrollment_frame
    try:
        emb, quality = validate_enrollment_frame(frame, recognition_engine)
    except ValueError as exc:
        return jsonify({'status': 'error', 'message': str(exc)}), 422
    except RuntimeError as exc:
        return jsonify({'status': 'error', 'message': str(exc)}), 503
    ident_id = enroll_identity(name=name, encoding=emb, quality_score=quality, db_manager=db_manager)
    recognition_engine.reload_identities()

    return jsonify({
        'status': 'success',
        'message': f"Enrolled '{name}' with 128D embedding",
        'identity_id': ident_id,
        'quality_score': quality
    })


@app.route('/health')
def health():
    """Healthcheck endpoint."""
    initialize_pipeline()
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'hardware_target': 'Raspberry Pi 5',
        'fps_throughput': runtime.snapshot()['capture_fps'],
        'identities_loaded': len(recognition_engine.known_names),
        'workers_running': sum(w.is_alive() for w in workers),
        'database_status': 'connected'
    })


def create_app():
    initialize_pipeline()
    return app


if __name__ == '__main__':
    initialize_pipeline()
    print("\n" + "=" * 70)
    print("🎥 REAL-TIME FACIAL RECOGNITION & ACCESS CONTROL SYSTEM")
    print("   Serving at http://0.0.0.0:5000")
    print(f"   Target: Raspberry Pi 5 | Workers: {config.NUM_WORKER_THREADS} | DB: {config.DATABASE_FILE}")
    print("=" * 70 + "\n")

    app.run(
        host=config.WEB_HOST,
        port=config.WEB_PORT,
        debug=config.DEBUG_MODE,
        threaded=config.THREADED_MODE
    )
