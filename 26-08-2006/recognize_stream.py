from flask import Flask, render_template_string
import cv2
import face_recognition
import pickle
import numpy as np
import sqlite3
import threading
import time
from datetime import datetime
from picamera2 import Picamera2

app = Flask(__name__)

with open("encodings.pkl", "rb") as f:
    data = pickle.load(f)
known_encodings = data["encodings"]
known_names = data["names"]

conn = sqlite3.connect("faces.db", check_same_thread=False)
db_lock = threading.Lock()
conn.execute('''
    CREATE TABLE IF NOT EXISTS access_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        timestamp TEXT,
        confidence REAL
    )
''')
conn.commit()

def log_recognition(name, confidence):
    with db_lock:
        conn.execute(
            "INSERT INTO access_log (name, timestamp, confidence) VALUES (?, ?, ?)",
            (name, datetime.now().isoformat(), confidence)
        )
        conn.commit()

picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(
    main={"format": "RGB888", "size": (640, 480)}
))
picam2.start()

latest_frame = None
frame_lock = threading.Lock()
RECOGNITION_THRESHOLD = 0.5
last_logged = {}
LOG_COOLDOWN_SECONDS = 10

def recognition_loop():
    global latest_frame
    frame_count = 0
    while True:
        frame = picam2.capture_array()
        frame_count += 1

        if frame_count % 3 == 0:
            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            face_locations = face_recognition.face_locations(small_frame, model="hog")
            face_encodings = face_recognition.face_encodings(small_frame, face_locations)

            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                distances = face_recognition.face_distance(known_encodings, face_encoding)
                name = "Unknown"
                confidence = 0.0

                if len(distances) > 0:
                    best_match_idx = np.argmin(distances)
                    if distances[best_match_idx] < RECOGNITION_THRESHOLD:
                        name = known_names[best_match_idx]
                        confidence = 1 - distances[best_match_idx]

                        now = time.time()
                        if name not in last_logged or (now - last_logged[name]) > LOG_COOLDOWN_SECONDS:
                            log_recognition(name, float(confidence))
                            last_logged[name] = now

                top, right, bottom, left = top*2, right*2, bottom*2, left*2
                color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                label = f"{name} ({confidence:.2f})" if name != "Unknown" else "Unknown"
                cv2.putText(frame, label, (left, top - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        with frame_lock:
            ret, buffer = cv2.imencode('.jpg', cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            latest_frame = buffer.tobytes()

recognition_thread = threading.Thread(target=recognition_loop, daemon=True)
recognition_thread.start()

@app.route('/')
def index():
    with db_lock:
        cursor = conn.execute("SELECT name, timestamp, confidence FROM access_log ORDER BY id DESC LIMIT 10")
        recent = cursor.fetchall()

    rows_html = ""
    for name, ts, conf in recent:
        rows_html += f"<tr><td>{name}</td><td>{ts}</td><td>{conf:.2f}</td></tr>"

    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Face Recognition Access System</title>
        <style>
            body { font-family: Arial; text-align: center; margin-top: 20px; background: #f0f0f0; }
            img { max-width: 90%; border: 2px solid #333; border-radius: 8px; }
            table { margin: 20px auto; border-collapse: collapse; }
            td, th { border: 1px solid #ccc; padding: 6px 12px; }
        </style>
    </head>
    <body>
        <h1>Real-Time Face Recognition</h1>
        <img src="/stream.mjpg" width="640" height="480" />
        <h3>Recent Recognitions</h3>
        <table>
            <tr><th>Name</th><th>Timestamp</th><th>Confidence</th></tr>
            ''' + rows_html + '''
        </table>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/stream.mjpg')
def stream():
    def generate():
        while True:
            with frame_lock:
                if latest_frame is not None:
                    frame_data = latest_frame
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n'
                           b'Content-Length: ' + str(len(frame_data)).encode() + b\r\n\r\n'
                           + frame_data + b'\r\n')
            time.sleep(0.03)
    return app.response_class(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    print(f"Loaded {len(known_names)} known face(s): {set(known_names)}")
    print("Server running at http://10.91.116.32:5000")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
