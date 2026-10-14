# 🚀 QUICK START: Raspberry Pi 5 Deployment
## Advanced Facial Recognition System - 10 Step Deployment

---

## 📋 **QUICK REFERENCE CARD**

### **System Requirements**
- Raspberry Pi 5 (8GB RAM minimum)
- Pi Camera Module 3 (IMX708)
- Raspberry Pi OS (Bookworm 64-bit)
- 5.1V 5A USB-C power supply
- Wi-Fi or Ethernet connection

---

## **⚡ ULTRA-FAST DEPLOYMENT (For Experts)**

```bash
# On your LOCAL computer
scp -r C:\Real-time-face-recognition-\26-08-2006\* smartsnake@snakerobo.local:~/facial-recognition/

# On Raspberry Pi (SSH)
ssh smartsnake@snakerobo.local
cd ~/facial-recognition

# Install dependencies (30-40 minutes total)
sudo apt update && sudo apt upgrade -y
sudo apt install -y cmake build-essential libopenblas-dev liblapack-dev python3-dev libcamera-apps-dev

# Python packages (takes longest due to dlib compilation)
pip install --upgrade pip
pip install flask opencv-python numpy picamera2 face_recognition --break-system-packages

# Setup & test
python3 setup.py

# Enroll faces
python3 enroll.py

# Start recognition system
python3 recognize_stream.py

# Access at: http://snakerobo.local:5000
```

---

## **📝 STEP-BY-STEP DETAILED GUIDE**

### **STEP 1: Prepare Raspberry Pi**

#### 1.1 SSH Connection
```bash
# From your computer
ssh smartsnake@snakerobo.local
# Password: (your password)

# Alternative using IP
ssh smartsnake@10.91.116.32
```

#### 1.2 Verify Camera
```bash
# On Pi
rpicam-hello --list-cameras

# Expected output:
# Camera 0: imx708 [4608x2592 10-bit RGGB] (/base/soc/i2c0mux/i2c@1/imx708@1a)

# If not detected:
sudo raspi-config
# → Interface Options → Camera → Enable → Reboot
```

---

### **STEP 2: Transfer Code to Pi**

#### Option A: **SCP (Recommended - Fast)**
```bash
# On your LOCAL computer
# Navigate to where you have the files
scp -r "C:\Real-time-face-recognition-\26-08-2006\*" smartsnake@snakerobo.local:~/facial-recognition/

# Verify transfer
ssh smartsnake@snakerobo.local ls -la ~/facial-recognition/
```

#### Option B: **Git Clone**
```bash
# On Pi
git clone https://github.com/shashankjangir/Real-time-face-recognition-
cd Real-time-face-recognition-/26-08-2006
cp * ~/facial-recognition/
```

#### Option C: **USB Drive**
```bash
# On Pi
mkdir -p ~/facial-recognition
sudo mount /dev/sda1 /mnt
cp /mnt/*.py ~/facial-recognition/
sudo umount /mnt
```

---

### **STEP 3: Install System Dependencies (10-15 minutes)**

```bash
# On Raspberry Pi
sudo apt update
sudo apt upgrade -y

# Install build tools & libraries
sudo apt install -y \
  cmake build-essential \
  libopenblas-dev liblapack-dev \
  python3-dev python3-pip \
  libcamera-apps-dev libcamera0 \
  libatlas-base-dev \
  libharfbuzz0b libwebp6 libtiff5 \
  libhdf5-dev \
  tightvncserver git

# Verify
python3 --version  # Should be 3.11 or higher
pip3 --version
```

---

### **STEP 4: Install Python Packages (20-40 minutes)**

#### 4.1 Update pip
```bash
pip install --upgrade pip setuptools wheel
```

#### 4.2 Install Core Packages
```bash
pip install --no-cache-dir \
  flask==2.3.3 \
  opencv-python==4.8.0.74 \
  numpy==1.24.3 \
  Pillow==10.0.0 \
  picamera2==0.3.14 \
  imutils==0.5.4 \
  --break-system-packages
```

#### 4.3 Install face_recognition (SLOW - 20-30 minutes)
```bash
# This compiles dlib from source - takes longest
pip install face-recognition --no-cache-dir --break-system-packages

# Monitor progress in another terminal:
sudo watch -n 1 'top -bn1 | head -20'
```

#### 4.4 Verify Installation
```bash
python3 -c "
import flask
import cv2
import numpy
import picamera2
import face_recognition
print('✓ All imports successful!')
"
```

---

### **STEP 5: Run Setup Script (Automated Validation)**

```bash
# On Pi
cd ~/facial-recognition
python3 setup.py

# This will:
# ✓ Check Python version
# ✓ Verify all dependencies
# ✓ Detect camera
# ✓ Initialize database (faces.db)
# ✓ Test database connectivity
# ✓ Create required directories
```

---

### **STEP 6: Enroll Known Faces**

#### 6.1 Interactive Single Enrollment
```bash
# On Pi
python3 enroll.py

# Menu:
# 1 = Enroll single face (camera)
# 2 = Batch enroll (from directory)
# 3 = List enrolled
# 4 = Delete identity
# 5 = Export to JSON
# 6 = Exit

# Select [1]
# Enter name: John Doe
# Stand in front of camera (3 second countdown)
# Good lighting is important!
```

#### 6.2 Batch Enrollment (Optional)
```bash
# Prepare directory on Pi
mkdir -p ~/batch_photos/John_Doe
mkdir -p ~/batch_photos/Jane_Smith

# Transfer photos from local computer
scp photos/john1.jpg smartsnake@snakerobo.local:~/batch_photos/John_Doe/
scp photos/jane1.jpg smartsnake@snakerobo.local:~/batch_photos/Jane_Smith/

# On Pi
python3 enroll.py
# Select [2]
# Path: /home/smartsnake/batch_photos
```

---

### **STEP 7: Start Recognition System**

#### 7.1 Run in Foreground (Testing)
```bash
# On Pi
python3 recognize_stream.py

# Expected output:
# ======================================================================
# 🎥 Real-Time Facial Recognition & Access System
# ======================================================================
# ✓ Loaded 5 known identities
# ✓ Recognition workers: 4
# ✓ Frame skip: Every 3rd frame
# ✓ Matching threshold: 0.50
# ======================================================================
# 🌐 Server running at http://0.0.0.0:5000
```

#### 7.2 Access Dashboard
```
URL: http://snakerobo.local:5000
OR: http://10.91.116.32:5000

You should see:
✓ Live camera feed (top left)
✓ System statistics (top right)
✓ Recognition history (bottom)
✓ Green box = recognized person
✓ Red box = unknown person
```

#### 7.3 Verify Recognition
- Stand in front of camera
- You should see bounding boxes
- Check dashboard for recognition entries
- Test different lighting conditions

---

### **STEP 8: Check Performance & Logs**

#### 8.1 Health Status
```bash
# From your computer
curl http://snakerobo.local:5000/health | python3 -m json.tool

# Expected:
# {
#   "status": "healthy",
#   "fps": 18,
#   "workers_active": 4,
#   "identities_loaded": 5
# }
```

#### 8.2 API Statistics
```bash
# From your computer
curl http://snakerobo.local:5000/api/stats | python3 -m json.tool

# Shows:
# - Recognition statistics
# - Performance metrics
# - Frame queue size
```

#### 8.3 View System Logs (On Pi)
```bash
# Terminal 1: Watch application logs
tail -f app.log

# Terminal 2: Monitor system resources
top
# Check: CPU %, Memory used
# Target: <80% CPU, <400MB memory
```

---

### **STEP 9: Run in Background (Production)**

#### 9.1 Start Background Process
```bash
# On Pi (Foreground server still running? Press CTRL+C first)
cd ~/facial-recognition
nohup python3 recognize_stream.py > server.log 2>&1 &

# This will:
# - Run in background
# - Log to server.log
# - Persist after terminal closes
```

#### 9.2 Verify Running
```bash
ps aux | grep recognize_stream
# You should see the process in the list
```

#### 9.3 View Logs
```bash
tail -f server.log
# Or check last 20 lines:
tail -20 server.log
```

#### 9.4 Stop Process (If Needed)
```bash
pkill -f recognize_stream
# Verify stopped:
ps aux | grep recognize_stream
```

---

### **STEP 10: Auto-Start on Boot (Optional)**

#### 10.1 Create Service File
```bash
# On Pi
sudo nano /etc/systemd/system/facial-recognition.service
```

Paste this content:
```ini
[Unit]
Description=Real-Time Facial Recognition System
After=network.target

[Service]
Type=simple
User=smartsnake
WorkingDirectory=/home/smartsnake/facial-recognition
ExecStart=/usr/bin/python3 /home/smartsnake/facial-recognition/recognize_stream.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Save: `CTRL+O`, Enter, `CTRL+X`

#### 10.2 Enable Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable facial-recognition.service
sudo systemctl start facial-recognition.service

# Check status
sudo systemctl status facial-recognition.service
# Expected: Active (running)
```

#### 10.3 Test Auto-Start
```bash
# Reboot Pi
sudo reboot

# After restart, verify running
sudo systemctl status facial-recognition.service
curl http://localhost:5000/health
```

---

## **🔧 COMMON CONFIGURATION TWEAKS**

### **If FPS is Too Low (<15)**
```bash
# On Pi
nano config.py

# Change:
FRAME_SKIP = 5               # Increase from 3
NUM_WORKER_THREADS = 2       # Decrease from 4
CAMERA_WIDTH = 320           # Decrease from 640
CAMERA_HEIGHT = 240          # Decrease from 480
```

### **If Accuracy is Low (<95%)**
```bash
# On Pi
nano config.py

# Change:
RECOGNITION_THRESHOLD = 0.45  # Lower = stricter matching
```

### **If Out of Memory**
```bash
# On Pi
nano config.py

# Change:
FRAME_QUEUE_SIZE = 15        # Decrease from 30
```

---

## **🐛 TROUBLESHOOTING**

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: face_recognition` | Re-run: `pip install face-recognition --break-system-packages` |
| Camera not detected | `sudo raspi-config` → Enable Camera |
| Low FPS | Increase FRAME_SKIP or reduce resolution |
| Low accuracy | Re-enroll faces, better lighting, lower threshold |
| Out of memory | Reduce number of workers or frame queue size |
| Database locked | `pkill -f recognize_stream` then `rm faces.db` |
| Can't access dashboard | Check firewall: `sudo ufw allow 5000` |
| Installation hangs | Let it run! dlib compilation takes 30 minutes |

---

## **📊 PERFORMANCE TARGETS**

| Metric | Target | How to Check |
|--------|--------|--------------|
| **FPS** | 15-20 | `curl localhost:5000/health` |
| **Latency** | <300ms | Check `performance_metrics.log` |
| **Accuracy** | >95% | Check `api/stats` - avg_confidence |
| **Memory** | <500MB | `top` command on Pi |
| **CPU** | <80% | `top` command on Pi |
| **Enrolled Identities** | 50+ | `curl localhost:5000/api/stats` |

---

## **📚 USEFUL COMMANDS**

```bash
# View recent logs
tail -f app.log
tail -100 app.log

# Kill process
pkill -f recognize_stream

# Monitor resources
top -bn1 | head -20

# Check disk space
df -h

# Check memory
free -h

# Reboot Pi
sudo reboot

# Shutdown Pi (graceful)
sudo shutdown -h now

# Check system temperature
sudo vcgencmd measure_temp

# View active processes
ps aux | grep python
```

---

## **🎯 VERIFICATION CHECKLIST**

- [ ] Code transferred to ~/facial-recognition/
- [ ] All pip packages installed
- [ ] Camera detected and working
- [ ] setup.py ran successfully
- [ ] Database initialized (faces.db exists)
- [ ] At least one face enrolled
- [ ] Dashboard accessible at http://snakerobo.local:5000
- [ ] Recognition working (green/red boxes visible)
- [ ] Performance > 15 FPS
- [ ] Accuracy > 95%
- [ ] Health endpoint showing "healthy"
- [ ] Background service configured (if using auto-start)

---

## **📞 SUPPORT REFERENCE**

For detailed documentation, SSH into Pi and read:
```bash
cat README_ADVANCED.md
cat IMPLEMENTATION_SUMMARY.md
```

API Endpoints:
```
Dashboard: http://snakerobo.local:5000
Stats: http://snakerobo.local:5000/api/stats
Logs: http://snakerobo.local:5000/api/logs
CSV: http://snakerobo.local:5000/api/csv
Health: http://snakerobo.local:5000/health
```

---

**Last Updated**: May 2026  
**Status**: Ready for Production Deployment  
**Estimated Time**: 60-90 minutes (mostly waiting for installations)
