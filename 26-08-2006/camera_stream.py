from flask import Flask, render_template_string
import subprocess
import threading
import time

app = Flask(__name__)

# Start rpicam-vid streaming MJPEG to stdout
process = subprocess.Popen(
    ['rpicam-vid', '-t', '0', '--codec', 'mjpeg', '--width', '640', '--height', '480', '-o', '-'],
    stdout=subprocess.PIPE,
    bufsize=10
)

frame_buffer = b''
frame_lock = threading.Lock()

def read_stream():
    global frame_buffer
    boundary = b'\xff\xd9'  # JPEG end marker
    buffer = b''

    while True:
        try:
            chunk = process.stdout.read(1024)
            if not chunk:
                break
            buffer += chunk

            if boundary in buffer:
                idx = buffer.rfind(boundary) + 2
                frame = buffer[:idx]
                buffer = buffer[idx:]

                if frame.startswith(b'\xff\xd8'):  # JPEG start marker
                    with frame_lock:
                        frame_buffer = frame
        except:
            pass

reader_thread = threading.Thread(target=read_stream, daemon=True)
reader_thread.start()

@app.route('/')
def index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Pi Camera Stream</title>
        <style>
            body { font-family: Arial; text-align: center; margin-top: 20px; }
            img { max-width: 90%; border: 2px solid #333; border-radius: 8px; }
        </style>
    </head>
    <body>
        <h1>Raspberry Pi Camera Feed</h1>
        <img src="/stream.mjpg" width="640" height="480" />
    </body>
    </html>
    ''')

@app.route('/stream.mjpg')
def stream():
    def generate():
        while True:
            with frame_lock:
                if frame_buffer:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n'
                           b'Content-Length: ' + str(len(frame_buffer)).encode() + b'\r\n\r\n'
                           + frame_buffer + b'\r\n')
            time.sleep(0.03)

    return app.response_class(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    print("Server running at http://10.91.116.32:5000")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
