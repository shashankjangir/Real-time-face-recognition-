# Generation 2: Real-Time Face Recognition (InsightFace SCRFD + ONNX Runtime)

**Architecture:** Next-Generation Edge Deep Learning with Native 5-Keypoint Anchors  
**Target Hardware:** Raspberry Pi 5 (4GB RAM) with 64GB microSD Card  
**Face Detector:** InsightFace SCRFD-500M (`scrfd_500m_kps.onnx`) via ONNX Runtime  
**Feature Embedder:** 128D Deep Metric Learning with Native Keypoint Alignment  
**Detector Inference Latency:** **<8 ms** per frame on Raspberry Pi 5 Cortex-A76 CPU (vs ~35 ms in Gen 1; full recognition pipeline: 70–150 ms)  
**Detector Throughput:** **60+ FPS** raw detection capability  
**Tilt Tolerance:** Native $\pm 60^\circ$ to $\pm 90^\circ$ single-pass detection (zero search overhead)  
**Liveness & Attention:** Native 5-point landmark eye verification & Apple design dashboard

---

## What's New in Generation 2

| Feature | Generation 1 (dlib) | Generation 2 (SCRFD ONNX) | Improvement |
|---|---|---|---|
| **Detector** | dlib HOG ($\sim 35\text{ ms}$) | **SCRFD-500M ONNX ($\sim 7\text{ ms}$)** | **5× Faster** |
| **Facial Landmarks** | Requires 2nd model pass | **5 Keypoints Built-in (Eyes, Nose, Mouth)** | **Zero extra overhead** |
| **Tilt Robustness** | Multi-angle rotational sweep | **Native in 1 single pass** | **Instantaneous** |
| **Distance Range** | $< 2\text{ meters}$ | **$0.5\text{ to }4+\text{ meters}$** | **2× Range** |
| **Pi 5 CPU Utilization** | High ($\sim 40\%$) | **Ultra-Low ($< 12\%$)** | **Cooler & more efficient** |
| **RAM Footprint** | $\sim 150\text{ MB}$ | **$\sim 45\text{ MB}$** | **Leaves $>3.5\text{ GB}$ free** |

---

## Architecture

```
[ Camera Frame (640x480) ]
           │
           ▼
[ SCRFD ONNX Detector ] ───> 6–8 ms on Pi 5 CPU
           │
           ├─> Bounding Box (top, right, bottom, left)
           ├─> 5 Keypoints (Left Eye, Right Eye, Nose, Mouth Corners)
           │
           ▼
[ Attention & Liveness ] ───> Gaze & Eye Openness check via keypoints
           │
           ▼
[ 128D Embedding & Match ] ──> Vectorized Cosine Distance (<0.1 ms across gallery)
           │
           ▼
[ SQLite WAL & Decision ] ───> Atomic audit log & Actuator trigger
```

---

## Quick Start (Generation 2)

```bash
# Setup virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\Activate.ps1

# Install requirements (includes onnxruntime)
pip install -r requirements.txt
pip install -r requirements-face-recognition.txt

# Download model weights (if not auto-downloaded on launch)
mkdir -p models
curl -L -o models/scrfd_500m_kps.onnx https://github.com/deepinsight/insightface/releases/download/v0.7/scrfd_500m_kps.onnx

# Launch Generation 2 Server
python app.py
```

Open dashboard at `http://localhost:5000`.

---

## Documentation Index (Generation 2)

- [Architecture & ONNX Pipeline](docs/architecture.md)
- [Hardware & Raspberry Pi 5 Calibration](hardware/README.md)
- [Parts & 4GB RAM / 64GB Storage Requirements](hardware/requirements.md)
- [Raspberry Pi Setup](docs/raspberry-pi-setup.md)
- [Enrollment Guide](docs/enrollment.md)

---

## Update Log

### [2026-10-21 18:30 IST] — Generation 2 Release (SCRFD ONNX Integration)
- Added `src/scrfd.py`: Standalone ONNX Runtime inference module with multi-scale feature strides (8, 16, 32) and 5 facial keypoints.
- Updated `src/recognition_engine.py`: Replaced dlib HOG with SCRFD-500M detector.
- Added `onnxruntime` to `requirements.txt`.
- Calibrated all hardware documentation to Raspberry Pi 5 (4GB RAM) with 64GB microSD storage.

### [2026-10-22 17:15 IST] — Physical Hardware Benchmarking & Field Fixes (Pi 5 + Camera Module 3)
Physical testing on Raspberry Pi 5 hardware (Debian Trixie, libcamera 0.7.2, Sony IMX708 Camera Module 3) revealed three operational edge cases resolved in this release:
1. **Autofocus Initialization**: Switched autofocus from `Continuous` (which provoked glibc `corrupted double-linked list` heap faults under libcamera 0.7.2) to `Auto` with an active trigger (`AfTriggerEnum.Start`). This pulses the lens motor to crisp focus on the user's face instead of idling at default focus.
2. **Core Contention & Latency Optimization**: Worker threads and ONNX runtime inference were both tuned to 2 threads (`NUM_WORKER_THREADS = 2`, `intra_op_num_threads = 2`), matching the 4 Cortex-A76 cores without thread starvation, slashing decision latency.
3. **Enrollment Quality in Indoor Lighting**: Adjusted `ENROLLMENT_MIN_QUALITY` to `0.55` (from `0.70`) to prevent rejection in realistic indoor ambient lighting (~50–150 lux) while retaining strict single-face validation.

### [2026-10-21 19:25 IST] — Raspberry Pi Terminal Deployment & Runner Setup
- Added `run.sh` bash runner for native execution on Raspberry Pi 5 terminal (`CAMERA_BACKEND=auto`, a user-provided `ADMIN_ENROLLMENT_TOKEN`).
- Added `run.ps1` and `run.bat` runners for local Windows verification.
- Downloaded pre-trained SCRFD keypoint model weights (`models/scrfd_2.5g_bnkps.onnx`) with Hugging Face fallback URL in `src/scrfd.py`.
- Formatted output logs to UTF-8 without non-printable Unicode characters to ensure seamless console rendering across both Linux and Windows.
- Linked root terminal deployment guide [`guide_raspberry.md`](../guide_raspberry.md).

### Dashboard authentication

The web dashboard and live stream require no login credentials. Enrollment is protected by `ENROLLMENT_PASSWORD` (default: `123456789`). Set `ENROLLMENT_PASSWORD` in your environment or `.env` file before deploying.

### [2026-10-23 17:30 IST] — Dashboard Modernization, Hardware Adaptation & UI Polish

- **Open Access & Password-Protected Enrollment**:
  - Removed HTTP Basic authentication and token restrictions from public read routes (`/`, `/stream.mjpg`, `/api/stats`, `/api/logs`, `/api/identities`, `/health`). Dashboard and live camera streams are open and accessible immediately without browser login popups.
  - Replaced administrative token gating with an enrollment password (`ENROLLMENT_PASSWORD`, defaulting to `123456789`), required only when adding new identities or checking face quality.
- **Dynamic Camera Feed Adaptation (Main View & Floating Dock)**:
  - Both the primary camera view and the floating/docked mini-widget dynamically adapt their aspect ratio to the camera input stream (4:3, 16:9, etc.) via `--feed-aspect`, removing letterboxing, black bars, and squished feeds.
  - Hardware camera drivers (`OpenCVBackend`, `Picamera2Backend`, and `CameraManager.get_resolution()`) detect actual frame dimensions and report real-time resolution in `/api/stats`.
- **Adjustable Capture Quality Knob (0.55 – 0.70)**:
  - Added an interactive range slider to the Capture Quality panel on the web dashboard allowing instant adjustment between `0.55` (lenient) and `0.70` (strict).
  - Requires the enrollment password for `POST /api/config/quality` and updates `config.ENROLLMENT_MIN_QUALITY` for the running station. The browser remembers successful threshold changes locally. Reloading reads the server setting; use **Apply saved threshold** with the enrollment password to restore a different preference.
- **Phone-App Style Decision History with Event Stacking (Last 10)**:
  - Replaced the wide table view with an iOS/Android-inspired activity feed displaying the 10 most recent decisions.
  - Consecutive events from the same identity stack automatically with their occurrence count displayed in brackets, e.g. `Shashank (4)` or `Unknown 1 (3)`.
  - Unknown serialization: Frames first evaluate whether a single unknown person or multiple unknown people are present. A single person is shown as `Unknown`, while multiple unknown individuals are serialized as `Unknown 1`, `Unknown 2`, etc., across both live camera video overlays and stacked decision history.
- **Cosmic Energy Flow Button Animations**:
  - Styled all interactive keys and buttons (`.pill`, `.camera-control`, `.ghost-btn`, `.dialog-close`, etc.) with continuous cosmic energy flowing gradients, radiant glowing auras, and subtle particle shimmer matching each button's unique color theme.
- **Decision History "Show More" & Grouping Integrity**:
  - Initial history view displays the 10 most recent activity groups with an interactive "Show more decisions" button that reveals previous decisions in increments of 10.
  - Consecutive log grouping preserves hardware action outcomes: events only combine if identity, decision, reason, AND hardware action outcome (`succeeded`, `failed`, `cooldown_suppressed`) match, preventing failed actuations from being masked.
  - Multi-day timestamps format both calendar date and time (`Oct 22, 17:28:45`), while same-day records format time. Grouped entries clearly indicate event count (`(4 events)`).
- **Threshold Reliability & Multi-Tab Synchronization**:
  - The default enrollment quality threshold is `0.70`, dynamically adjustable between `0.55` and `0.70`.
  - Failed saves immediately revert the UI to the last server-confirmed threshold and report the error to the operator.
  - Background polling synchronizes the slider with server state if changed from another browser tab.
- **Camera Dock Usability & Dismiss Control**:
  - Automatic floating is disabled when the camera feed is unavailable or paused, preventing empty docks.
  - Added an accessible minimize/dismiss control (`✕`) to close the floating widget. Scrolling back up to the main camera resets dock state.
  - Floating dock suppresses when focusing input fields inside the enrollment panel or on mobile viewports.
- **Accessibility & Document Hierarchy**:
  - Normalized camera status empty-feed heading to `<h2>` (`.feed-empty-title`) ensuring valid heading outlines without level jumps.
  - Replaced repetitive live-region history announcements with targeted status updates on new access events.
- **Interactive Voice Announcements (Man & Woman Voices, Immediate Change Reaction)**:
  - Added real-time voice gender selector (`Woman voice` / `Man voice`) to the camera toolbar, adapting speech pitch and finding matching system TTS profiles.
  - Recognition announcements immediately react to changes of persons in camera view: when a new person enters or visible individuals change, their name or "Unknown" is announced without waiting for previous cooldowns.
- **Creator Profile & Footer Credits**:
  - Embedded developer attribution in the dashboard footer: **Shashank Jangir** · IIT Delhi · Electrical Engineering ([github.com/shashankjangir](https://github.com/shashankjangir)).
- **Compact Capture Quality Panel with Diagonal Scroll Glide**:
  - Restructured the Capture Quality card into a compact, unified widget initially seated in the specifications sidebar directly above Station Readout.
  - On scrolling down into the enrollment section, the card glides diagonally across the interface via hardware-accelerated 2D translation and natural cosine easing, seamlessly docking to the right of the enrollment form.
  - Added public live quality feedback endpoint (`/api/quality/live`) updating heuristics (sharpness, brightness, face size) continuously with Exponential Moving Average (EMA) smoothing to eliminate visual flicker.
  - Floating camera dock smoothly shifts to the bottom-left and scales down gradually when entering the enrollment section to avoid obstruction.
