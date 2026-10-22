# Raspberry Pi 5 Deployment & Terminal Guide
**Real-Time Facial Recognition & Access Control System**  
*Optimized for Raspberry Pi 5 (4GB RAM) & 64GB MicroSD Storage*

---

## 1. Hardware Checklist & Specifications

| Component | Specification | Notes |
| :--- | :--- | :--- |
| **SBC** | **Raspberry Pi 5 (4GB RAM)** | Quad-core ARM Cortex-A76 @ 2.4 GHz |
| **Storage** | **64GB MicroSD Card** (Class 10 / A2) | Minimum 15GB free recommended for database & frames |
| **OS** | **Raspberry Pi OS (64-bit Bookworm)** | Debian 12 based, Wayland/X11, kernel 6.6+ |
| **Power Supply** | **Official 27W USB-C PD (5.1V / 5.0A)** | Prevents under-voltage under multi-threaded load |
| **Cooling** | **Raspberry Pi Active Cooler** | Recommended to avoid thermal throttling during continuous inference |
| **Camera** | **Raspberry Pi Camera Module 3 / v2** OR **USB Webcam** | CSI ribbon connects to `CAM/DISP0` or `CAM/DISP1` |

---

## 2. Connecting to Raspberry Pi via Terminal

### Step 2.1: Find the Raspberry Pi IP Address
If connected to your local Wi-Fi or Ethernet network:
- From your laptop terminal:
  ```bash
  ping raspberrypi.local
  ```
- Or check your home Wi-Fi router's connected devices page.

### Step 2.2: SSH into the Pi
Replace `smartsnake` (or your chosen Pi username) and IP with your details:
```bash
ssh pi@raspberrypi.local
# Or by IP address:
ssh pi@192.168.1.100
```

---

## 3. Verify Hardware & Camera

Run these quick checks inside the Raspberry Pi terminal:

### Test CSI Camera (Camera Module 3 or v2):
```bash
rpicam-hello --list-cameras
```
*Expected output:*
```text
Available cameras:
0 : imx708 [4608x2592 10-bit RGGB] (/base/axi/pcie@120000/...)
```

### Test USB Webcam (if using USB instead of CSI ribbon):
```bash
ls -l /dev/video*
# Or detailed device list:
v4l2-ctl --list-devices
```

### Check Available Memory & Disk Space:
```bash
free -h
df -h /
```
Verify `Mem: ~4.0Gi` total and sufficient space on the 64GB root partition.

---

## 4. Transfer Project to Raspberry Pi

Choose **Option A** (Git clone) or **Option B** (SCP transfer):

### Option A: Via Git (Recommended)
Inside your Pi terminal:
```bash
cd ~
git clone https://github.com/shashankjangir/Real-time-face-recognition-.git face-access
cd face-access
```

### Option B: Via SCP from your Laptop
Run from PowerShell on your laptop:
```powershell
scp -r "c:\3. Real-time-face-recognition-" pi@raspberrypi.local:~/face-access
```

---

## 5. Automated 1-Script Setup

We provided an automated setup script that installs all system packages, builds `dlib` across all 4 Cortex-A76 cores, sets up a virtual environment with Picamera2 bindings, and verifies all ML models:

Inside the Pi terminal:
```bash
cd ~/face-access
chmod +x setup_rpi.sh
bash setup_rpi.sh
```

---

## 6. Manual Setup (Alternative Step-by-Step)

If you prefer to run commands manually instead of using `setup_rpi.sh`:

### Step 6.1: Update APT and Install System Libraries
```bash
sudo apt update
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-picamera2 \
    python3-libcamera \
    libcamera-apps \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libjpeg-dev \
    zlib1g-dev \
    git \
    v4l-utils
```

### Step 6.2: Create Virtual Environment with System Site Packages
> [!IMPORTANT]  
> The `--system-site-packages` flag is mandatory on Raspberry Pi OS Bookworm so that `python3-picamera2` and system `libcamera` bindings can be imported inside your virtual environment.

```bash
python3 -m venv --system-site-packages ~/face-access-env
source ~/face-access-env/bin/activate
pip install --upgrade pip
pip install "setuptools<70" wheel
```

### Step 6.3: Install dlib & Face Recognition
```bash
# Parallelized across 4 Pi 5 cores (~2 minutes)
CMAKE_BUILD_PARALLEL_LEVEL=4 pip install dlib
pip install face-recognition face-recognition-models
```

### Step 6.4: Install Gen-2 Requirements
```bash
cd ~/face-access/gen-2-scrfd
pip install -r ../requirements-pi.txt
```

---

## 7. Running the System on Raspberry Pi

Generate a token once with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`.
Export it as `ADMIN_ENROLLMENT_TOKEN` before running either launcher. Replace every
`<your-generated-token>` placeholder below with that value. The browser login uses
username `admin` and this token as the password; use HTTPS for network access.


### Option 1: Run Generation 2 (SCRFD - Recommended for Edge)
Provides 60+ FPS face detection, native 5-point landmark keypoints, and tolerance to face roll/tilt:

```bash
cd ~/face-access/gen-2-scrfd
chmod +x run.sh
./run.sh
```

Or manually:
```bash
source ~/face-access-env/bin/activate
cd ~/face-access/gen-2-scrfd
export ADMIN_ENROLLMENT_TOKEN="<your-generated-token>"
export CAMERA_BACKEND="auto"
python3 app.py
```

### Option 2: Run Generation 1 (dlib HOG Baseline)
If you want to benchmark against the baseline:

```bash
cd ~/face-access/gen-1-dlib
chmod +x run.sh
./run.sh
```

---

## 8. Accessing the Web Dashboard

Once started, the server outputs:
```text
>>> REAL-TIME FACIAL RECOGNITION & ACCESS CONTROL SYSTEM
   Architecture: Raspberry Pi 5 / Edge (128D Deep Metric Learning)
   Web Dashboard: http://0.0.0.0:5000
   Database:      faces.db (SQLite + WAL)
   Workers:       4 Threads | Frame Skip: 3
 * Serving Flask app 'src.app'
 * Running on http://127.0.0.1:5000
 * Running on http://192.168.1.xxx:5000
```

1. Open a browser on your laptop or smartphone connected to the same Wi-Fi.
2. Navigate to: **`http://<RASPBERRY_PI_IP>:5000`** (e.g. `http://192.168.1.105:5000`).
3. You will see the Apple-inspired real-time dashboard:
   - Live annotated video feed
   - Access event logs (granted/denied)
   - Real-time FPS, worker queue latency, and database status
   - Admin face enrollment modal (use token `<your-generated-token>`)

---

## 9. Enrolling New Faces on the Pi

### Method A: Via Web UI
1. Click **Enroll Face** on the web dashboard.
2. Enter the Admin Token (`<your-generated-token>`).
3. Provide the user's name, role, and department.
4. Capture 3-5 images directly from the live camera stream or upload photo files.
5. Click **Save Enrollment**. Vector embeddings are instantly indexed in SQLite WAL.

### Method B: Via CLI Script
```bash
source ~/face-access-env/bin/activate
cd ~/face-access/gen-2-scrfd
python3 enroll.py --name "John Doe" --role "Engineer" --department "Robotics" --photos photo1.jpg photo2.jpg
```

---

## 10. Optional: Autostart on Boot (Systemd Service)

To make the Raspberry Pi automatically boot into the face recognition system without needing an active SSH terminal:

### Step 1: Create systemd unit file
```bash
sudo nano /etc/systemd/system/face-access.service
```

Paste the following configuration:
```ini
[Unit]
Description=Real-Time Facial Recognition & Access Control System
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/face-access/gen-2-scrfd
Environment="ADMIN_ENROLLMENT_TOKEN=<your-generated-token>"
Environment="CAMERA_BACKEND=auto"
Environment="PYTHONIOENCODING=utf-8"
ExecStart=/home/pi/face-access-env/bin/python3 app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Step 2: Enable and start service
```bash
sudo systemctl daemon-reload
sudo systemctl enable face-access.service
sudo systemctl start face-access.service
```

### Step 3: Check status & logs
```bash
sudo systemctl status face-access.service
# Follow live logs:
journalctl -u face-access.service -f
```

---

## 11. Troubleshooting & Diagnostics

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| **`No module named 'picamera2'`** | Virtualenv missing system packages | Re-create virtualenv with `--system-site-packages`: `python3 -m venv --system-site-packages ~/face-access-env` |
| **Camera not detected** | Ribbon cable loose or inserted backwards | Power off Pi. Blue tab on ribbon must face Ethernet/USB ports. Ensure `rpicam-hello --list-cameras` lists camera. |
| **USB webcam index wrong** | USB camera assigned to `/dev/video1` | Run `v4l2-ctl --list-devices`. Set `export CAMERA_INDEX="1"` before running `app.py`. |
| **High CPU temperature (>75°C)** | Continuous inference load | Run `vcgencmd measure_temp`. Install the official Raspberry Pi Active Cooler. |
| **High latency / frame drops** | Camera resolution too high | The system defaults to 640x480 @ 30 FPS with `FRAME_SKIP=3`, maintaining <100ms end-to-end response on Pi 5. |
| **`database is locked`** | Concurrent SQLite writes | Handled automatically via SQLite WAL mode (`PRAGMA journal_mode=WAL`). |
