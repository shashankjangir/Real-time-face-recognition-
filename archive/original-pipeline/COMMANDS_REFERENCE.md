# 📋 COMPLETE COMMAND REFERENCE
## Raspberry Pi Deployment - Copy & Paste Commands

---

## **🔧 PART 1: INITIAL CONNECTION & SETUP**

### 1.1 SSH into Raspberry Pi
```bash
ssh smartsnake@snakerobo.local
# Password: (enter your password)

# Alternative (using IP address)
ssh smartsnake@10.91.116.32
```

### 1.2 Verify Camera
```bash
rpicam-hello --list-cameras

# Expected:
# Camera 0: imx708 [4608x2592 10-bit RGGB]

# If not showing:
sudo raspi-config
# → Interface Options → Camera → Enable → Save & Reboot
```

---

## **📦 PART 2: FILE TRANSFER (Choose ONE)**

### Option A: SCP (Recommended)
**Run on your LOCAL computer:**
```bash
# For Windows (PowerShell)
scp -r "C:\Real-time-face-recognition-\26-08-2006\*" smartsnake@snakerobo.local:~/facial-recognition/

# For Mac/Linux
scp -r /path/to/26-08-2006/* smartsnake@snakerobo.local:~/facial-recognition/
```

### Option B: Git Clone
**Run on Raspberry Pi:**
```bash
cd ~
git clone https://github.com/shashankjangir/Real-time-face-recognition-
cd Real-time-face-recognition-/26-08-2006
mkdir -p ~/facial-recognition
cp * ~/facial-recognition/
cd ~/facial-recognition
```

### Option C: USB Drive
**Run on Raspberry Pi:**
```bash
mkdir -p ~/facial-recognition
sudo mount /dev/sda1 /mnt
cp /mnt/*.py /mnt/*.md ~/facial-recognition/
sudo umount /mnt
```

### Verify Transfer
```bash
cd ~/facial-recognition
ls -lh *.py
# Should show: config.py, database.py, enroll.py, etc.
```

---

## **🛠️ PART 3: INSTALL SYSTEM DEPENDENCIES (10-15 minutes)**

**Run on Raspberry Pi:**

### 3.1 Update System
```bash
sudo apt update
sudo apt upgrade -y
```

### 3.2 Install Build Tools
```bash
sudo apt install -y \
  cmake \
  build-essential \
  git
```

### 3.3 Install Libraries
```bash
sudo apt install -y \
  libopenblas-dev \
  liblapack-dev \
  python3-dev \
  python3-pip
```

### 3.4 Install Camera & VNC
```bash
sudo apt install -y \
  libcamera-apps-dev \
  libcamera0 \
  tightvncserver
```

### 3.5 Verify Installation
```bash
python3 --version  # Should be 3.11+
pip3 --version
```

---

## **🐍 PART 4: INSTALL PYTHON PACKAGES (40+ minutes)**

**Run on Raspberry Pi:**

### 4.1 Update pip
```bash
pip install --upgrade pip setuptools wheel
```

### 4.2 Install Core Packages
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

### 4.3 Install face_recognition (LONGEST - 20-30 minutes)
```bash
# Single command - just let it run, it's compiling dlib
pip install face-recognition --no-cache-dir --break-system-packages
```

**Monitor progress in separate terminal:**
```bash
# Open another SSH terminal and run:
sudo watch -n 1 'ps aux | grep -i dlib'
# Or check CPU:
top -bn1 | head -5
```

### 4.4 Verify All Installations
```bash
python3 << 'EOF'
import flask
import cv2
import numpy
import picamera2
import face_recognition
print("✓ All Python modules imported successfully!")
EOF
```

---

## **🚀 PART 5: SETUP & VALIDATION**

**Run on Raspberry Pi:**

### 5.1 Prepare Directory
```bash
cd ~/facial-recognition
ls -la  # Verify all .py files are present
```

### 5.2 Make Setup Script Executable
```bash
chmod +x setup.py
```

### 5.3 Run Automated Setup
```bash
python3 setup.py
# This will validate:
# ✓ Python version
# ✓ All dependencies
# ✓ Camera detection
# ✓ Database initialization
# ✓ Configuration
```

### 5.4 Verify Database Created
```bash
ls -lh faces.db
# Should show: faces.db file with size > 0
```

---

## **👤 PART 6: ENROLL FACES**

**Run on Raspberry Pi:**

### 6.1 Interactive Single Enrollment
```bash
python3 enroll.py

# Menu will show:
# 1 = Enroll single (camera)
# 2 = Batch enroll (directory)
# 3 = List enrolled
# 4 = Delete
# 5 = Export JSON
# 6 = Exit

# Type: 1
# Enter name: John Doe
# Wait for 3-second countdown
# Stand in front of camera, look at lens
# Good lighting is IMPORTANT!
```

### 6.2 Batch Enrollment (Optional)
```bash
# Step 1: Prepare directory structure
mkdir -p ~/batch_photos/John_Doe
mkdir -p ~/batch_photos/Jane_Smith
mkdir -p ~/batch_photos/Bob_Johnson

# Step 2: Transfer photos (from your computer)
scp ~/photos/john1.jpg smartsnake@snakerobo.local:~/batch_photos/John_Doe/
scp ~/photos/jane1.jpg smartsnake@snakerobo.local:~/batch_photos/Jane_Smith/

# Step 3: On Pi, run enroll.py
python3 enroll.py
# Type: 2
# Path: /home/smartsnake/batch_photos
# Select
```

### 6.3 List Enrolled Faces
```bash
python3 enroll.py
# Type: 3
# Shows: Name and quality score for each person
```

### 6.4 Check Database Directly
```bash
sqlite3 faces.db
> SELECT name, quality_score FROM identities;
> SELECT COUNT(*) FROM identities;
> .quit
```

---

## **🎬 PART 7: START RECOGNITION SYSTEM**

**Run on Raspberry Pi:**

### 7.1 Start in Foreground (Testing)
```bash
cd ~/facial-recognition
python3 recognize_stream.py

# Expected output:
# ======================================================================
# 🎥 Real-Time Facial Recognition & Access System
# ======================================================================
# ✓ Loaded 5 known identities
# ✓ Recognition workers: 4
# ✓ Frame skip: Every 3rd frame
# ✓ Matching threshold: 0.50
# ✓ Database: faces.db
# ✓ Camera: 640x480 @ 30 FPS
# ✓ Session ID: (random UUID)
# ======================================================================
# 🌐 Server running at http://0.0.0.0:5000
# ======================================================================
```

### 7.2 Access Dashboard
```
Open browser on your computer:
  http://snakerobo.local:5000
  OR
  http://10.91.116.32:5000

You should see:
✓ Live camera feed with face detection
✓ System statistics (24h data)
✓ Recognition history table
✓ Navigation links to APIs
```

### 7.3 Test Recognition
```
- Stand in front of camera
- Look at the lens
- You should see:
  ✓ Blue bounding box around face
  ✓ Name and confidence score (if recognized)
  ✓ Green box = known person
  ✓ Red box = unknown person
- Check dashboard for recognition entry
- Try different angles and lighting
```

---

## **⚙️ PART 8: PERFORMANCE VERIFICATION**

**On your LOCAL computer:**

### 8.1 Check Health Status
```bash
curl http://snakerobo.local:5000/health | python3 -m json.tool

# Expected output:
# {
#   "status": "healthy",
#   "fps": 18.5,
#   "fps_target_met": true,
#   "identities_loaded": 5,
#   "frame_queue_size": 2,
#   "workers_active": 4,
#   "database_ok": true,
#   "camera_ok": true
# }
```

### 8.2 Get API Statistics
```bash
curl http://snakerobo.local:5000/api/stats | python3 -m json.tool

# Shows:
# - Recognition statistics
# - Performance metrics
# - Available endpoints
```

### 8.3 Get Access Logs
```bash
curl http://snakerobo.local:5000/api/logs?limit=10 | python3 -m json.tool

# Shows last 10 recognition entries
```

### 8.4 Download CSV Report
```bash
# Last 7 days
curl http://snakerobo.local:5000/api/csv > report.csv

# Specific person
curl 'http://snakerobo.local:5000/api/csv?name=John' > john_report.csv

# Date range
curl 'http://snakerobo.local:5000/api/csv?start_date=2026-05-20&end_date=2026-05-27' > week_report.csv
```

### 8.5 Monitor on Raspberry Pi
```bash
# Terminal 1: Watch application logs
tail -f ~/facial-recognition/app.log

# Terminal 2: Monitor system resources
top
# Check: CPU %, Memory
# Target: <80% CPU, <400MB memory, no swap used

# Terminal 3: Check performance logs
tail -f ~/facial-recognition/performance_metrics.log
```

---

## **🔄 PART 9: RUN IN BACKGROUND (Production)**

**Run on Raspberry Pi:**

### 9.1 Stop Current Foreground Process
```bash
# In the terminal running recognize_stream.py:
CTRL+C
```

### 9.2 Start Background Process
```bash
cd ~/facial-recognition
nohup python3 recognize_stream.py > server.log 2>&1 &

# This will:
# - Run in background
# - Output redirected to server.log
# - Won't stop when terminal closes
```

### 9.3 Verify Running
```bash
ps aux | grep recognize_stream
# You should see one python process

# Get process ID
pgrep -f recognize_stream
```

### 9.4 Monitor Logs
```bash
# View last 20 lines
tail -20 ~/facial-recognition/server.log

# Follow in real-time
tail -f ~/facial-recognition/server.log

# Search for errors
grep ERROR ~/facial-recognition/server.log
```

### 9.5 Stop Background Process
```bash
pkill -f recognize_stream
# OR
kill <PID>  # Replace with actual PID from ps aux
```

### 9.6 Restart Background Process
```bash
# Kill
pkill -f recognize_stream

# Restart
cd ~/facial-recognition
nohup python3 recognize_stream.py > server.log 2>&1 &
```

---

## **🤖 PART 10: AUTO-START ON BOOT (Optional)**

**Run on Raspberry Pi:**

### 10.1 Create Systemd Service File
```bash
sudo tee /etc/systemd/system/facial-recognition.service > /dev/null << 'EOF'
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
EOF
```

### 10.2 Enable Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable facial-recognition.service
sudo systemctl start facial-recognition.service
```

### 10.3 Check Status
```bash
sudo systemctl status facial-recognition.service

# Expected:
# ● facial-recognition.service - Real-Time Facial Recognition System
#    Loaded: loaded
#    Active: active (running)
```

### 10.4 View Service Logs
```bash
sudo journalctl -u facial-recognition.service -f

# Or to see last 50 lines:
sudo journalctl -u facial-recognition.service -n 50
```

### 10.5 Test Auto-Start
```bash
# Reboot
sudo reboot

# After restart, check:
sudo systemctl status facial-recognition.service
curl http://localhost:5000/health
```

### 10.6 Manage Service
```bash
# Start
sudo systemctl start facial-recognition.service

# Stop
sudo systemctl stop facial-recognition.service

# Restart
sudo systemctl restart facial-recognition.service

# Disable auto-start (keep running until manual stop)
sudo systemctl disable facial-recognition.service
```

---

## **📊 PART 11: CONFIGURATION TWEAKS**

**Edit on Raspberry Pi:**

### 11.1 Edit Configuration
```bash
cd ~/facial-recognition
nano config.py
# Make changes as needed
# Save: CTRL+O, Enter, CTRL+X
```

### 11.2 Common Tweaks

**If FPS is too low (< 15):**
```python
FRAME_SKIP = 5              # Was 3 (process fewer frames)
NUM_WORKER_THREADS = 2      # Was 4 (fewer threads)
CAMERA_WIDTH = 320          # Was 640 (smaller resolution)
CAMERA_HEIGHT = 240         # Was 480
```

**If accuracy is too low (< 95%):**
```python
RECOGNITION_THRESHOLD = 0.45  # Was 0.50 (stricter matching)
```

**If out of memory:**
```python
FRAME_QUEUE_SIZE = 15          # Was 30 (smaller queue)
NUM_WORKER_THREADS = 2         # Was 4
CAMERA_WIDTH = 320             # Was 640
```

**If CPU usage is high:**
```python
FRAME_SKIP = 5              # Was 3
NUM_WORKER_THREADS = 2      # Was 4
```

### 11.3 Restart After Changes
```bash
# If running in foreground:
CTRL+C

# Then restart:
python3 recognize_stream.py

# If running as background process:
pkill -f recognize_stream
nohup python3 recognize_stream.py > server.log 2>&1 &
```

---

## **🔍 PART 12: DEBUGGING & LOGS**

**Run on Raspberry Pi:**

### 12.1 View All Logs
```bash
# Application logs
cat app.log
tail -50 app.log
grep ERROR app.log

# Background process logs
cat server.log
tail -f server.log

# Performance metrics
cat performance_metrics.log
```

### 12.2 System Information
```bash
# CPU & Memory
free -h
df -h
top -bn1 | head -20

# Temperature
sudo vcgencmd measure_temp

# Network
ip addr
ping google.com

# Processes
ps aux | grep python
ps aux | grep recognize
```

### 12.3 Database Inspection
```bash
sqlite3 faces.db

# Inside sqlite3:
> SELECT COUNT(*) FROM identities;
> SELECT name, quality_score FROM identities;
> SELECT COUNT(*) FROM access_log;
> SELECT * FROM access_log LIMIT 5;
> SELECT * FROM access_log WHERE name='John' LIMIT 3;
> .quit
```

### 12.4 Test Camera Directly
```bash
# Show live feed for 5 seconds
rpicam-hello -t 5000

# Capture single image
rpicam-still -o test.jpg

# List available
rpicam-hello --list-cameras
```

---

## **🚨 TROUBLESHOOTING COMMANDS**

### Issue: Database locked
```bash
pkill -f recognize_stream
rm ~/facial-recognition/faces.db
cd ~/facial-recognition
python3 database.py
python3 recognize_stream.py
```

### Issue: Python import errors
```bash
pip install face-recognition --break-system-packages
pip list | grep -i dlib
pip list | grep -i opencv
```

### Issue: Camera not working
```bash
rpicam-hello --list-cameras
sudo raspi-config  # Enable camera
sudo reboot
```

### Issue: Low disk space
```bash
df -h
du -sh ~/facial-recognition
rm -rf ~/facial-recognition/reports/*.csv  # Delete old reports
rm -f ~/facial-recognition/*.log  # Delete old logs
```

### Issue: High CPU/Memory
```bash
top -n1
ps aux | sort -nrk 3,3 | head -n 3  # Top CPU
ps aux | sort -nrk 4,4 | head -n 3  # Top Memory
```

---

## **🎯 VERIFICATION CHECKLIST**

```bash
# 1. Files transferred
ls -lh ~/facial-recognition/*.py

# 2. Dependencies installed
python3 -c "import face_recognition; print('✓')"

# 3. Database initialized
ls -lh ~/facial-recognition/faces.db

# 4. Setup completed
python3 ~/facial-recognition/setup.py

# 5. Faces enrolled
sqlite3 ~/facial-recognition/faces.db "SELECT COUNT(*) FROM identities;"

# 6. Server running
curl http://localhost:5000/health

# 7. Performance good
curl http://localhost:5000/health | grep fps

# 8. Dashboard accessible
# Open browser: http://snakerobo.local:5000
```

---

**Copy & Paste these commands directly into your terminal!**  
Save this file for future reference. 📌

