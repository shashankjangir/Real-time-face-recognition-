# Real-Time Face Recognition & Camera Streaming on Raspberry Pi 5

A complete, production-ready pipeline for camera streaming, face enrollment, and real-time facial recognition on the **Raspberry Pi 5** using **Raspberry Pi Camera Module 3 (IMX708)**, **OpenCV**, **dlib / face_recognition**, and a **Flask** web dashboard with SQLite access logging.

---

## 📌 Project Overview

This repository contains the setup, scripts, and session logs for:
- **Low-latency live camera streaming** over local Wi-Fi (MJPEG via Flask).
- **Interactive face enrollment** capturing live camera frames and generating 128-d face encodings.
- **Real-time multi-face recognition** with bounding boxes, names, confidence scores, and web UI.
- **Access logging database** recording timestamps and confidence scores in SQLite with cooldown throttling.

---

## 🛠️ Hardware & Environment Specifications

| Component | Specification / Value |
|---|---|
| **Board** | Raspberry Pi 5 (8GB / 4GB) |
| **Camera** | Raspberry Pi Camera Module 3 (Sensor: `imx708`, 4608x2592 10-bit RGGB) |
| **Default Hostname** | `snakerobo.local` |
| **Default IP** | `10.91.116.32` |
| **SSH User** | `smartsnake` |
| **OS** | Raspberry Pi OS (Debian Bookworm 64-bit) |
| **Web Server Port** | `5000` (`http://<PI_IP>:5000`) |
| **VNC Display** | `:1` (`<PI_IP>:1`) |

---

## 📂 Repository Structure

```text
.
├── 26-08-2006/
│   ├── camera_stream.py       # Standalone low-latency MJPEG video streaming server
│   ├── enroll.py              # Live camera face enrollment tool (saves to encodings.pkl)
│   └── recognize_stream.py    # Real-time recognition web server with SQLite access log
├── session_summary_guide.md   # Raw session logs & full historical troubleshooting guide
└── README.md                  # Project documentation & execution guide
```

---

## ⚡ Installation & Setup on Raspberry Pi

### 1. System Dependencies & Camera Tools

SSH into your Raspberry Pi:
```bash
ssh smartsnake@snakerobo.local
```

Update packages and install build tools and camera libraries:
```bash
sudo apt update
sudo apt install -y cmake build-essential libopenblas-dev liblapack-dev python3-dev libcamera-apps tightvncserver
```

> **Note:** On modern Raspberry Pi OS, the camera binary is `rpicam-hello` (replaces legacy `libcamera-hello`).

Verify camera detection:
```bash
rpicam-hello --list-cameras
```
Expected output: `Camera 0: imx708 [4608x2592 10-bit RGGB] ...`

---

### 2. Python Environment & Libraries

Install the required Python packages:
```bash
pip install flask opencv-python numpy picamera2 face_recognition --break-system-packages
```

> **Tip:** `dlib` will compile from source. If `face_recognition_models` (~100MB) encounters a network timeout, re-run the `pip install` command to resume.

---

## 🚀 Usage Guide

Navigate into the script folder:
```bash
cd 26-08-2006
```

### Step 1: Test Raw Live Camera Stream
Runs a Flask streaming server piping MJPEG from `rpicam-vid`:

```bash
python3 camera_stream.py
```
- Open in any browser on the same Wi-Fi: **`http://<PI_IP>:5000`** (e.g., `http://10.91.116.32:5000`)

---

### Step 2: Enroll Known Faces
Captures portrait photos using `rpicam-still`, computes 128-dimensional facial embeddings, and saves them into `encodings.pkl`:

```bash
python3 enroll.py
```
- Follow the prompt and enter the person's name.
- Look directly into the camera during the 3-second countdown.
- Photos are stored in `known_faces/<name>.jpg` and encodings are updated in `encodings.pkl`.

---

### Step 3: Run Real-Time Face Recognition & Access Logging
Starts the full recognition pipeline using `Picamera2`, OpenCV, and `face_recognition`:

```bash
python3 recognize_stream.py
```

#### Features:
- **Live Stream with HUD:** Green bounding boxes for recognized faces with confidence percentage; Red bounding boxes for unknown faces.
- **Web Dashboard:** Access logs table displayed right below the video stream at `http://<PI_IP>:5000`.
- **SQLite Database (`faces.db`):** Automatically stores recognized events in the `access_log` table:
  ```sql
  CREATE TABLE access_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT,
      timestamp TEXT,
      confidence REAL
  );
  ```
- **Logging Cooldown:** Configured with a 10-second cooldown per person to avoid duplicate log entries for the same continuous detection.

---

## ⚙️ Performance Tuning & Configuration

Inside [`recognize_stream.py`](file:///c:/Real-time-face-recognition-/26-08-2006/recognize_stream.py):

- **Recognition Accuracy Threshold:**
  ```python
  RECOGNITION_THRESHOLD = 0.5  # Lower (e.g. 0.45) = stricter match; Higher (e.g. 0.6) = looser match
  ```
- **Frame-Skip Interval (FPS Booster):**
  ```python
  if frame_count % 3 == 0:  # Detect every 3rd frame to maximize video FPS on Pi 5 CPU
  ```
- **Downscaling Factor:**
  ```python
  small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)  # Speeds up HOG face detection 4x
  ```

---

## 🖥️ Optional: Remote Desktop (VNC)

Start the VNC server on the Pi:
```bash
vncserver :1 -geometry 1024x768 -depth 24
```
Connect from your laptop using **RealVNC Viewer** to `10.91.116.32:1`.

---

## 📋 Summary of Key Files Generated at Runtime

| File | Purpose |
|---|---|
| `encodings.pkl` | Serialized dictionary containing face encodings and names |
| `known_faces/` | Directory storing raw reference images from enrollment |
| `faces.db` | SQLite database storing access history logs |
