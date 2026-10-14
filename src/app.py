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
from flask import Flask, render_template_string, Response, request, jsonify, send_file

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


# HTML TEMPLATE (Modern Glassmorphic Dark UI)
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Real-Time Facial Recognition & Access Control System</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #090d16;
            --surface: rgba(18, 24, 38, 0.75);
            --surface-hover: rgba(28, 38, 58, 0.85);
            --border: rgba(255, 255, 255, 0.08);
            --border-accent: rgba(79, 140, 255, 0.25);
            --primary: #4f8cff;
            --primary-glow: rgba(79, 140, 255, 0.35);
            --accent: #00e5a3;
            --accent-glow: rgba(0, 229, 163, 0.35);
            --danger: #ff4757;
            --danger-glow: rgba(255, 71, 87, 0.35);
            --warning: #ffa502;
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
            --radius-sm: 8px;
            --radius-md: 14px;
            --radius-lg: 20px;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Plus Jakarta Sans', sans-serif;
            background: var(--bg);
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(79, 140, 255, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(0, 229, 163, 0.06) 0%, transparent 40%);
            color: var(--text-main);
            min-height: 100vh;
            padding: 24px;
            line-height: 1.5;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 24px;
        }

        /* HEADER */
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--surface);
            backdrop-filter: blur(16px);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 20px 28px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }

        .brand-section {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .brand-icon {
            width: 48px;
            height: 48px;
            border-radius: var(--radius-md);
            background: linear-gradient(135deg, var(--primary), var(--accent));
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            box-shadow: 0 0 20px var(--primary-glow);
        }

        .brand-titles h1 {
            font-size: 1.35rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            background: linear-gradient(120deg, #fff 0%, #94a3b8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .brand-titles p {
            font-size: 0.85rem;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.75rem;
            font-family: 'JetBrains Mono', monospace;
            padding: 4px 10px;
            border-radius: 20px;
            background: rgba(0, 229, 163, 0.12);
            border: 1px solid rgba(0, 229, 163, 0.3);
            color: var(--accent);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--accent);
            box-shadow: 0 0 8px var(--accent);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.95); opacity: 0.8; }
            50% { transform: scale(1.15); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.8; }
        }

        .header-actions {
            display: flex;
            gap: 12px;
        }

        .btn {
            font-family: inherit;
            font-size: 0.85rem;
            font-weight: 600;
            padding: 10px 18px;
            border-radius: var(--radius-sm);
            border: 1px solid var(--border);
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            text-decoration: none;
            color: var(--text-main);
            background: var(--surface);
        }

        .btn:hover {
            background: var(--surface-hover);
            border-color: var(--border-accent);
            transform: translateY(-1px);
        }

        .btn-primary {
            background: linear-gradient(135deg, var(--primary), #3b6bdc);
            border-color: transparent;
            box-shadow: 0 4px 16px var(--primary-glow);
        }

        .btn-primary:hover {
            box-shadow: 0 6px 20px rgba(79, 140, 255, 0.5);
            background: linear-gradient(135deg, #5b95ff, #4373eb);
        }

        /* METRIC CARDS */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 18px;
        }

        .metric-card {
            background: var(--surface);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 18px 22px;
            transition: all 0.25s ease;
            position: relative;
            overflow: hidden;
        }

        .metric-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--border-accent), transparent);
        }

        .metric-card:hover {
            transform: translateY(-2px);
            border-color: var(--border-accent);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
        }

        .metric-label {
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            font-weight: 600;
            margin-bottom: 6px;
        }

        .metric-value {
            font-size: 1.85rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            font-family: 'JetBrains Mono', monospace;
            color: #fff;
        }

        .metric-sub {
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-top: 4px;
        }

        .accent-green { color: var(--accent); }
        .accent-blue { color: var(--primary); }
        .accent-orange { color: var(--warning); }

        /* MAIN CONTENT GRID */
        .main-grid {
            display: grid;
            grid-template-columns: 7fr 5fr;
            gap: 24px;
        }

        @media (max-width: 1024px) {
            .main-grid { grid-template-columns: 1fr; }
        }

        .card-panel {
            background: var(--surface);
            backdrop-filter: blur(16px);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 24px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .panel-title {
            font-size: 1.1rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        /* VIDEO STREAM CONTAINER */
        .video-box {
            position: relative;
            width: 100%;
            background: #000;
            border-radius: var(--radius-md);
            overflow: hidden;
            aspect-ratio: 4 / 3;
            border: 1px solid rgba(255, 255, 255, 0.06);
            box-shadow: inset 0 0 40px rgba(0, 0, 0, 0.8);
        }

        .video-box img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            display: block;
        }

        .video-hud {
            position: absolute;
            top: 14px;
            left: 14px;
            right: 14px;
            display: flex;
            justify-content: space-between;
            pointer-events: none;
        }

        .hud-badge {
            background: rgba(10, 15, 26, 0.85);
            backdrop-filter: blur(8px);
            border: 1px solid rgba(255, 255, 255, 0.12);
            padding: 4px 10px;
            border-radius: var(--radius-sm);
            font-size: 0.75rem;
            font-family: 'JetBrains Mono', monospace;
            color: #fff;
        }

        /* AUDIT LOG TABLE */
        .table-wrap {
            overflow-x: auto;
            border-radius: var(--radius-sm);
            border: 1px solid rgba(255, 255, 255, 0.05);
            max-height: 440px;
            overflow-y: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
            text-align: left;
        }

        th {
            background: rgba(255, 255, 255, 0.04);
            padding: 12px 14px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            font-size: 0.7rem;
            letter-spacing: 0.05em;
            position: sticky;
            top: 0;
            backdrop-filter: blur(8px);
        }

        td {
            padding: 12px 14px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            color: #e2e8f0;
        }

        tr:hover td {
            background: rgba(255, 255, 255, 0.025);
        }

        .badge-verified {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            background: rgba(0, 229, 163, 0.15);
            color: var(--accent);
            font-size: 0.75rem;
            font-weight: 600;
        }

        .badge-rejected {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            background: rgba(255, 71, 87, 0.15);
            color: var(--danger);
            font-size: 0.75rem;
            font-weight: 600;
        }

        .time-col {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.78rem;
            color: var(--text-muted);
        }

        /* MODAL */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0, 0, 0, 0.75);
            backdrop-filter: blur(8px);
            z-index: 999;
            align-items: center;
            justify-content: center;
        }

        .modal-box {
            background: var(--surface);
            border: 1px solid var(--border-accent);
            border-radius: var(--radius-lg);
            padding: 28px;
            width: 100%;
            max-width: 500px;
            box-shadow: 0 20px 48px rgba(0, 0, 0, 0.5);
        }

        .form-group {
            display: flex;
            flex-direction: column;
            gap: 6px;
            margin-bottom: 16px;
        }

        .form-group label {
            font-size: 0.8rem;
            color: var(--text-muted);
            font-weight: 600;
        }

        .form-control {
            background: rgba(0, 0, 0, 0.35);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            padding: 10px 14px;
            color: #fff;
            font-family: inherit;
            font-size: 0.85rem;
        }

        .form-control:focus {
            outline: none;
            border-color: var(--primary);
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- HEADER -->
        <header>
            <div class="brand-section">
                <div class="brand-icon">👁️</div>
                <div class="brand-titles">
                    <h1>Real-Time Facial Recognition & Access System</h1>
                    <p>
                        Raspberry Pi 5 Architecture • OpenCV 128D Metric Learning • SQLite WAL
                        <span class="status-pill"><span class="status-dot"></span> LIVE PIPELINE</span>
                    </p>
                </div>
            </div>
            <div class="header-actions">
                <button class="btn" onclick="openReportModal()">📥 Export CSV Report</button>
                <input id="adminEnrollmentToken" type="password" placeholder="Administrator token" aria-label="Administrator enrollment token" autocomplete="off">
                <button class="btn btn-primary" onclick="triggerEnrollSample()">+ Enroll Identity</button>
            </div>
        </header>

        <!-- TELEMETRY CARDS -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Enrolled Identities</div>
                <div class="metric-value accent-blue" id="val-enrolled">Loading</div>
                <div class="metric-sub">Target: 50+ identities</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Classification Accuracy</div>
                <div class="metric-value accent-green" id="val-accuracy">Not measured</div>
                <div class="metric-sub">Vector Cosine Distance Metric</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Camera Capture Rate</div>
                <div class="metric-value" id="val-fps">Not measured</div>
                <div class="metric-sub">Measured camera capture rate</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Delivery-to-decision latency</div>
                <div class="metric-value accent-green" id="val-latency">Not measured</div>
                <div class="metric-sub">Target budget: &lt;300 ms</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Shared JPEG / Recognition FPS</div>
                <div class="metric-value" id="val-runtime-rates">Not measured</div>
                <div class="metric-sub" id="val-drops">Rates since startup; recognition counts committed frames</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">24h Authentications</div>
                <div class="metric-value" id="val-total-logs">0</div>
                <div class="metric-sub">Indexed SQLite transaction log</div>
            </div>
        </div>

        <!-- MAIN CONTENT -->
        <div class="main-grid">
            <!-- VIDEO FEED -->
            <div class="card-panel">
                <div class="panel-header">
                    <div class="panel-title">📹 Real-Time Edge Stream & Annotation</div>
                    <span class="status-pill">MJPEG 30 FPS</span>
                </div>
                <div class="video-box">
                    <img src="/stream.mjpg" alt="Live Camera Video Stream" id="videoFeed">
                    <div class="video-hud">
                        <div class="hud-badge">Pi Camera Module 3 (IMX708)</div>
                        <div class="hud-badge" id="hudStatus">ONLINE • 128D COSINE</div>
                    </div>
                </div>
            </div>

            <!-- ACCESS LOG AUDIT TRAIL -->
            <div class="card-panel">
                <div class="panel-header">
                    <div class="panel-title">🔐 Live Transaction Audit Log</div>
                    <button class="btn" style="padding:6px 12px;font-size:0.75rem" onclick="fetchAuditLogs()">↻ Refresh</button>
                </div>
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Identity</th>
                                <th>Confidence</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody id="logsTableBody">
                            <tr>
                                <td colspan="4" style="text-align:center;color:var(--text-muted);padding:24px">
                                    Listening for authentication events...
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <!-- DYNAMIC CSV EXPORT MODAL -->
    <div class="modal-overlay" id="reportModal" onclick="if(event.target === this) closeReportModal()">
        <div class="modal-box">
            <h2 style="margin-bottom:16px;font-size:1.2rem">Dynamic CSV Report Generation</h2>
            <div class="form-group">
                <label>Time Window</label>
                <select class="form-control" id="csvWindow">
                    <option value="24">Last 24 Hours</option>
                    <option value="168" selected>Last 7 Days</option>
                    <option value="720">Last 30 Days</option>
                </select>
            </div>
            <div class="form-group">
                <label>Filter by Name (Optional)</label>
                <input type="text" class="form-control" id="csvNameFilter" placeholder="e.g. Alexander or leave blank">
            </div>
            <div style="display:flex;justify-content:flex-end;gap:12px;margin-top:20px">
                <button class="btn" onclick="closeReportModal()">Cancel</button>
                <button class="btn btn-primary" onclick="downloadCsv()">Download CSV</button>
            </div>
        </div>
    </div>

    <script>
        function openReportModal() {
            document.getElementById('reportModal').style.display = 'flex';
        }
        function closeReportModal() {
            document.getElementById('reportModal').style.display = 'none';
        }
        function downloadCsv() {
            const hours = document.getElementById('csvWindow').value;
            const name = document.getElementById('csvNameFilter').value.trim();
            let url = `/api/csv?hours=${hours}`;
            if (name) url += `&name=${encodeURIComponent(name)}`;
            window.location.href = url;
            closeReportModal();
        }

        async function triggerEnrollSample() {
            const name = prompt("Enter full name to enroll:");
            if (!name) return;
            const token = document.getElementById('adminEnrollmentToken').value;
            if (!token) { alert("Enter your administrator token before enrolling."); return; }
            const res = await fetch('/api/enroll', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token},
                body: JSON.stringify({ name })
            });
            const data = await res.json();
            document.getElementById('adminEnrollmentToken').value = '';
            alert(data.message || "Enrolled successfully!");
            updateStats();
        }

        async function updateStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                if (data.status === 'success') {
                    document.getElementById('val-enrolled').innerText = data.identities_enrolled;
                    document.getElementById('val-fps').innerText = data.fps.toFixed(1) + ' FPS';
                    document.getElementById('val-runtime-rates').innerText = data.telemetry.unique_jpeg_fps.toFixed(1) + ' / ' + data.telemetry.recognition_fps.toFixed(1);
                    document.getElementById('val-drops').innerText = 'Dropped queue: ' + data.telemetry.counts.dropped + ', stale: ' + data.telemetry.counts.stale + ', out of order: ' + data.telemetry.counts.out_of_order;
                    document.getElementById('val-latency').innerText = data.avg_latency_ms == null ? 'Not measured' : data.avg_latency_ms + ' ms';
                    document.getElementById('val-total-logs').innerText = data.total_recognitions_24h;
                }
            } catch (e) {
                console.error(e);
            }
        }

        function escapeHtml(value) {
            const element = document.createElement('span');
            element.textContent = value == null ? '' : String(value);
            return element.innerHTML;
        }

        async function fetchAuditLogs() {
            try {
                const res = await fetch('/api/logs?limit=25');
                const data = await res.json();
                if (data.status === 'success' && data.logs.length > 0) {
                    const tbody = document.getElementById('logsTableBody');
                    tbody.innerHTML = data.logs.map(log => {
                        const isVerified = log.status === 'verified';
                        const badge = isVerified 
                            ? `<span class="badge-verified">VERIFIED</span>` 
                            : `<span class="badge-rejected">REJECTED</span>`;
                        const time = log.timestamp.split('T')[1] ? log.timestamp.split('T')[1].substring(0, 8) : log.timestamp;
                        return `<tr>
                            <td class="time-col">${time}</td>
                            <td><strong>${escapeHtml(log.name)}</strong></td>
                            <td>${(log.confidence * 100).toFixed(1)}%</td>
                            <td>${badge}<br>${escapeHtml(log.reason)}<br>${escapeHtml(log.action_outcome)}</td>
                        </tr>`;
                    }).join('');
                }
            } catch (e) {
                console.error(e);
            }
        }

        // Live refresh intervals
        setInterval(updateStats, 2000);
        setInterval(fetchAuditLogs, 3000);
        updateStats();
        fetchAuditLogs();
    </script>
</body>
</html>
"""


# ============================================================================
# WEB ROUTES
# ============================================================================

@app.route('/')
def index():
    initialize_pipeline()
    return render_template_string(DASHBOARD_HTML)


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


@app.route('/api/enroll', methods=['POST'])
def api_enroll():
    """Enroll a new identity."""
    configured_token = config.ADMIN_ENROLLMENT_TOKEN
    if not configured_token:
        return jsonify({'status': 'error', 'message': 'Administrator enrollment is not configured.'}), 503
    scheme, _, token = request.headers.get('Authorization', '').partition(' ')
    if scheme.lower() != 'bearer' or not hmac.compare_digest(token.encode('utf-8'), configured_token.encode('utf-8')):
        return jsonify({'status': 'error', 'message': 'Administrator authentication required.'}), 401, {'WWW-Authenticate': 'Bearer'}
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
