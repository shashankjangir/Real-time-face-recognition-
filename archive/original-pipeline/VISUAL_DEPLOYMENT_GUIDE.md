# 🎯 Raspberry Pi Deployment Process - Visual Guide

---

## **DEPLOYMENT WORKFLOW**

```
┌─────────────────────────────────────────────────────┐
│  STEP 1: Prepare Raspberry Pi                       │
│  ✓ SSH Connection                                   │
│  ✓ Update system packages                          │
│  ✓ Verify camera is connected                      │
└────────────┬────────────────────────────────────────┘
			 │
			 ▼
┌─────────────────────────────────────────────────────┐
│  STEP 2: Transfer Code Files                        │
│  Option A: SCP (recommended)                        │
│  Option B: Git clone                                │
│  Option C: USB drive                                │
└────────────┬────────────────────────────────────────┘
			 │
			 ▼
┌─────────────────────────────────────────────────────┐
│  STEP 3: Install System Libraries (10-15 min)      │
│  ✓ cmake, build-essential                          │
│  ✓ libopenblas-dev, liblapack-dev                  │
│  ✓ libcamera-apps, python3-dev                     │
└────────────┬────────────────────────────────────────┘
			 │
			 ▼
┌─────────────────────────────────────────────────────┐
│  STEP 4: Install Python Packages (40+ min)         │
│  ✓ flask, opencv-python                            │
│  ✓ numpy, picamera2                                │
│  ✓ face-recognition (SLOW - dlib compile)          │
│  ⏱️  Takes longest (~30 minutes)                    │
└────────────┬────────────────────────────────────────┘
			 │
			 ▼
┌─────────────────────────────────────────────────────┐
│  STEP 5: Run Automated Setup Script                 │
│  python3 setup.py                                   │
│  ✓ Validates all requirements                      │
│  ✓ Initializes database                            │
│  ✓ Tests connectivity                              │
└────────────┬────────────────────────────────────────┘
			 │
			 ▼
┌─────────────────────────────────────────────────────┐
│  STEP 6: Enroll Known Faces                         │
│  python3 enroll.py                                  │
│  ✓ Single face: Interactive camera capture         │
│  ✓ Batch: Load multiple from directory             │
│  ✓ Quality validation built-in                     │
└────────────┬────────────────────────────────────────┘
			 │
			 ▼
┌─────────────────────────────────────────────────────┐
│  STEP 7: Start Recognition System                   │
│  python3 recognize_stream.py                        │
│  ✓ Server at http://snakerobo.local:5000           │
│  ✓ Live dashboard with video feed                  │
│  ✓ Multi-threaded recognition workers              │
└────────────┬────────────────────────────────────────┘
			 │
			 ▼
┌─────────────────────────────────────────────────────┐
│  STEP 8: Verify Performance                         │
│  ✓ Check health endpoint                           │
│  ✓ Monitor FPS (target: 15-20)                     │
│  ✓ Verify accuracy (target: >95%)                  │
│  ✓ Test system logs                                │
└────────────┬────────────────────────────────────────┘
			 │
			 ▼
┌─────────────────────────────────────────────────────┐
│  STEP 9: Run in Background (Production)             │
│  nohup python3 recognize_stream.py &                │
│  ✓ Persists after terminal close                   │
│  ✓ Monitor with: tail -f server.log                │
└────────────┬────────────────────────────────────────┘
			 │
			 ▼
┌─────────────────────────────────────────────────────┐
│  STEP 10: Auto-Start on Boot (Optional)             │
│  ✓ Create systemd service                          │
│  ✓ Enable automatic startup                        │
│  ✓ Verify after reboot                             │
└─────────────────────────────────────────────────────┘
```

---

## **TIME BREAKDOWN**

```
Total Deployment Time: 60-90 minutes

Breakdown:
├─ Setup & SSH connexion:        5 min
├─ Code transfer:                5 min
├─ System libraries:             15 min
├─ Python packages:              40 min ⏳ (LONGEST)
│  └─ face-recognition dlib:    30 min (just be patient!)
├─ Setup script:                 5 min
├─ Face enrollment:              5 min
├─ Start & verify:               10 min
└─ Configuration (optional):      5 min
								─────
							   ~90 min TOTAL
```

---

## **INSTALLATION DEPENDENCY TREE**

```
Raspberry Pi 5 (4GB RAM)
│
├─ System Libraries
│  ├─ cmake, build-essential
│  ├─ libopenblas-dev, liblapack-dev
│  ├─ python3-dev, python3-pip
│  └─ libcamera-apps-dev
│
├─ Python Runtime
│  └─ Python 3.8+
│
├─ Python Packages
│  ├─ flask (web server)
│  ├─ numpy (math)
│  ├─ opencv-python (image processing)
│  ├─ picamera2 (camera control)
│  └─ face_recognition (face detection & encoding)
│     └─ dlib (compiles from source - slowest part)
│
├─ Application Code
│  ├─ config.py (settings)
│  ├─ database.py (SQLite)
│  ├─ recognition_engine.py (face matching)
│  ├─ recognize_stream.py (web server)
│  └─ enroll.py (enrollment tool)
│
└─ Runtime Data
   ├─ faces.db (SQLite database)
   ├─ known_faces/ (enrollment photos)
   └─ reports/ (CSV/JSON exports)
```

---

## **FILE TRANSFER OPTIONS COMPARISON**

```
┌─────────────────┬──────────────┬──────────────┬──────────────┐
│ Method          │ Speed        │ Ease         │ Best For     │
├─────────────────┼──────────────┼──────────────┼──────────────┤
│ SCP             │ ⚡ Fast      │ ⭐⭐⭐ Easy    │ Most users   │
│ Git Clone       │ ⚡ Fast      │ ⭐⭐ Medium   │ Version ctrl │
│ USB Drive       │ 🐢 Slow      │ ⭐ Hard      │ Offline mode │
│ ssh scp         │ ⚡ Fast      │ ⭐⭐⭐ Easy    │ Remote copy  │
└─────────────────┴──────────────┴──────────────┴──────────────┘
```

### **SCP Command Explained**
```
scp -r SOURCE DESTINATION

scp -r C:\Real-time-face-recognition-\26-08-2006\* smartsnake@snakerobo.local:~/facial-recognition/
 ▲    ▲                                              ▲                                    ▲
 │    │ Copy recursively -r                         │ User & host                        │ Destination path
 │    │                                              │ (your Pi)
 │ All files in this folder
 Copy from Windows to Pi
```

---

## **SYSTEM ARCHITECTURE - POST DEPLOYMENT**

```
┌──────────────────────────────────────────────────────────────┐
│  Raspberry Pi 5 (4GB RAM)                                    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Facial Recognition System                            │   │
│  │                                                       │   │
│  │ ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │   │
│  │ │ Picamera2   │  │ Frame Queue  │  │ Workers    │  │   │
│  │ │ (30 FPS)    │→→│ (Max 30)     │→→│ (4x)       │  │   │
│  │ │ 640x480     │  │ Every 3rd    │  │ Cosine     │  │   │
│  │ └─────────────┘  │ frame        │  │ distance   │  │   │
│  │                  └──────────────┘  └────────────┘  │   │
│  │                                         │            │   │
│  │                              ┌──────────▼─────────┐  │   │
│  │                              │ Database Logging   │  │   │
│  │                              │ (SQLite)           │  │   │
│  │                              │ faces.db           │  │   │
│  │                              └────────────────────┘  │   │
│  │                                        │             │   │
│  │                         ┌──────────────▼─────────┐  │   │
│  │                         │ Flask Web Server       │  │   │
│  │                         │ :5000                  │  │   │
│  │                         │ Dashboard + APIs       │  │   │
│  │                         └────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ systemd Service (auto-start)                         │   │
│  │ facial-recognition.service                           │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
		  │
		  ▼
┌──────────────────────────┐
│ Your Local Computer      │
│                          │
│ Browser:                 │
│ http://snakerobo.local:5000
│                          │
│ ✓ Live video feed       │
│ ✓ Recognition history   │
│ ✓ Statistics            │
│ ✓ API endpoints         │
└──────────────────────────┘
```

---

## **DATABASE SCHEMA - DEPLOYED**

```
┌─────────────────────────────────────────────────────────┐
│ faces.db (SQLite)                                       │
│                                                          │
│ ┌──────────────────┐                                    │
│ │ identities       │  (Enrolled faces)                  │
│ ├──────────────────┤                                    │
│ │ id (PK)          │  ← indexed                         │
│ │ name (UNIQUE)    │  ← indexed                         │
│ │ encoding (BLOB)  │  128D face embedding              │
│ │ quality_score    │  0.0-1.0                          │
│ │ enrollment_date  │                                    │
│ └──────────────────┘                                    │
│          │                                              │
│          ▼                                              │
│ ┌────────────────────────┐                             │
│ │ enrollment_history     │  (Re-enrollment tracking)   │
│ ├────────────────────────┤                             │
│ │ identity_id (FK)       │  ← indexed                  │
│ │ timestamp              │  ← indexed                  │
│ │ encoding               │                             │
│ │ quality_score          │                             │
│ │ status                 │                             │
│ └────────────────────────┘                             │
│                                                          │
│ ┌────────────────────────┐                             │
│ │ access_log             │  (Recognition events)       │
│ ├────────────────────────┤                             │
│ │ identity_id (FK)       │  ← indexed                  │
│ │ name                   │  ← indexed                  │
│ │ timestamp              │  ← indexed (CRITICAL)       │
│ │ confidence             │  ← indexed                  │
│ │ session_id             │  ← indexed                  │
│ │ status                 │                             │
│ │ match_distance         │                             │
│ └────────────────────────┘                             │
│                                                          │
│ ┌──────────────────────┐  ┌──────────────────────┐     │
│ │ sessions             │  │ performance_metrics  │     │
│ ├──────────────────────┤  ├──────────────────────┤     │
│ │ id (session_id)      │  │ timestamp (idx)      │     │
│ │ start_time           │  │ frame_latency_ms     │     │
│ │ end_time             │  │ fps                  │     │
│ │ status               │  │ memory_mb            │     │
│ └──────────────────────┘  └──────────────────────┘     │
└─────────────────────────────────────────────────────────┘
```

---

## **WEB DASHBOARD LAYOUT**

```
┌─────────────────────────────────────────────────────────────┐
│  🔐 Real-Time Facial Recognition & Access System           │
│  Advanced face recognition with cosine distance matching    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌───────────────────────────┐  ┌───────────────────────┐  │
│  │ 🎥 Live Camera Feed       │  │ 📊 System Statistics │  │
│  │                           │  │ (Last 24 hours)      │  │
│  │ [==========VIDEO==========]  │                       │  │
│  │ [==========STREAM=========]  │ Total Verifications: 152 │  │
│  │ [========================]  │ Unique Identities:   12  │  │
│  │                           │  │ Avg Confidence:    0.887  │  │
│  │ Green box = Known         │  │ Enrolled:            15  │  │
│  │ Red box = Unknown         │  └───────────────────────┘  │
│  └───────────────────────────┘                              │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 📝 Recent Recognition History (Last 20)              │  │
│  ├──────────┬──────────────────────┬──────────┬────────┤  │
│  │ Name     │ Timestamp            │ Conf.    │ Status │  │
│  ├──────────┼──────────────────────┼──────────┼────────┤  │
│  │ John Doe │ 2026-05-27 14:32:15  │  0.927   │ ✓      │  │
│  │ Jane S.  │ 2026-05-27 14:31:42  │  0.891   │ ✓      │  │
│  │ Unknown  │ 2026-05-27 14:30:18  │  0.381   │ ✗      │  │
│  │ Bob      │ 2026-05-27 14:29:05  │  0.915   │ ✓      │  │
│  └──────────┴──────────────────────┴──────────┴────────┘  │
│                                                              │
│  [📈 Stats API] [📥 CSV Report] [💚 Health Check]          │
└─────────────────────────────────────────────────────────────┘
```

---

## **API ENDPOINTS**

```
┌─────────────────────────────────────────────────────┐
│ REST API Endpoints (JSON Responses)                 │
├─────────────────────────────────────────────────────┤
│                                                      │
│ GET /                                               │
│ └─ Main dashboard with live video                  │
│                                                      │
│ GET /stream.mjpg                                    │
│ └─ MJPEG video stream (embeddable in <img> tag)   │
│                                                      │
│ GET /api/stats?hours=24                            │
│ ├─ Total recognitions                              │
│ ├─ Unique identities                               │
│ ├─ Average confidence                              │
│ └─ Performance metrics (FPS, latency)              │
│                                                      │
│ GET /api/logs?name=John&hours=24&limit=50         │
│ ├─ Filtered access logs                            │
│ ├─ Person name filter                              │
│ └─ Date range filter                               │
│                                                      │
│ GET /api/csv?start_date=2026-05-20&end_date=...   │
│ └─ CSV file download (Excel compatible)            │
│                                                      │
│ GET /health                                         │
│ ├─ System health status                            │
│ ├─ FPS vs target                                   │
│ └─ Worker status                                   │
└─────────────────────────────────────────────────────┘
```

---

## **PERFORMANCE MONITORING**

```
Real-time Metrics Dashboard
┌─────────────────────────────────────────┐
│ FPS: 18/20 ████████████░░░░ 90%         │
│ Lat: 245/300ms ███████░░░░░░░ 81%       │
│ Acc: 96.2% ██████████░░ EXCELLENT      │
│ Mem: 380/500 MB ████████░░░░░ 76%      │
│ CPU: 65% ██████░░░░░░░░░░ GOOD         │
│ Queu: 3/30 frames ░░░░░░░░░░░░░░░░░░  │
└─────────────────────────────────────────┘

Logs
├─ app.log              (Application logs)
├─ server.log           (Background process logs)
├─ performance_metrics.log
└─ reports/             (CSV/JSON exports)
```

---

## **TROUBLESHOOTING FLOWCHART**

```
System Not Working?
│
├─ Can't SSH to Pi?
│  └─ Check Wi-Fi connection
│     Check IP: ping snakerobo.local
│     Try: ssh -v for verbose output
│
├─ Camera not detected?
│  └─ Run: sudo raspi-config
│     Enable Camera in Interface Options
│     Reboot
│
├─ Low FPS (< 15)?
│  └─ Edit config.py:
│     - Increase FRAME_SKIP from 3 to 5
│     - Reduce CAMERA_WIDTH to 320
│     - Reduce NUM_WORKER_THREADS to 2
│
├─ Low Accuracy (< 95%)?
│  └─ Re-enroll faces
│     Better lighting
│     Lower RECOGNITION_THRESHOLD from 0.50 to 0.45
│
├─ Out of Memory?
│  └─ Edit config.py:
│     - Reduce FRAME_QUEUE_SIZE from 30 to 15
│     - Reduce NUM_WORKER_THREADS
│
├─ Database locked?
│  └─ Kill process: pkill -f recognize_stream
│     Reset: rm faces.db
│     Reinit: python3 database.py
│
└─ Other issues?
   └─ Check logs: tail -f app.log
	  Check space: df -h
	  Check temp: sudo vcgencmd measure_temp
```

---

**Visual Guide Complete!**  
Proceed with Step-by-Step Implementation using QUICK_START.md or RASPBERRY_PI_DEPLOYMENT_GUIDE.sh

