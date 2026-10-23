# Generation 1: Real-Time Face Recognition (dlib HOG + ResNet-128D)

**Architecture:** Classic Computer Vision & Metric Learning  
**Target Hardware:** Raspberry Pi 5 (4GB RAM) with 64GB microSD Card  
**Face Detector:** dlib HOG / CNN Linear SVM Detector  
**Feature Embedder:** dlib 128D ResNet Deep Metric Learning  
**Liveness & Policy:** Eye Aspect Ratio (EAR) Attention Verification, Continuous Template Adaptation, Multi-Sample Enrollment  
**User Interface:** Apple Design System Dashboard (`#f5f5f7` Frost canvas, `#0071e3` Apple Blue switches, SF Pro scale)

---

## Overview

Generation 1 is the reference implementation using `face_recognition` and `dlib`. It establishes:
- 128-dimensional metric embeddings projected onto a unit hypersphere.
- Thread-safe producer-consumer video pipeline with bounded stale-frame dropping.
- SQLite WAL transactional logging with <5ms indexed queries.
- Web-based video streaming and live telemetric feedback.
- Software rotational search for 360° head tilt compensation.

## Quick Start (Generation 1)

```bash
# Setup virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\Activate.ps1

# Install core and model dependencies
pip install -r requirements.txt
pip install -r requirements-face-recognition.txt

# Start access control server
python app.py
```

Open dashboard at `http://localhost:5000`.

---

## Update Log

### [2026-10-21 18:30 IST] — Generation 1 Baseline Preservation
- Separated baseline implementation into dedicated `gen-1-dlib/` folder.
- Preserved dlib HOG detector, 128D ResNet embeddings, and Apple Design System UI.
- Standardized hardware specification to Raspberry Pi 5 (4GB RAM) with 64GB microSD storage.

### [2026-10-21 19:25 IST] — Raspberry Pi Terminal Deployment & Runner Setup
- Added `run.sh` bash runner for native execution on Raspberry Pi 5 terminal (`CAMERA_BACKEND=auto`, a user-provided `ADMIN_ENROLLMENT_TOKEN`).
- Added `run.ps1` and `run.bat` runners for local Windows verification.
- Added `from __future__ import annotations` to resolve typing forward references cleanly across Python 3.9+.
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
  - Syncs via `POST /api/config/quality`, dynamically updates `config.ENROLLMENT_MIN_QUALITY`, and persists to `localStorage`.
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
- **Heron AI Design System & Fluid Motion Animations**:
  - Transformed the dashboard interface with Heron AI's dark obsidian canvas (`#080c0e`), electric vermilion highlights (`#fa3600`), and sleek translucent glass bento cards.
  - Implemented Heron motion tokens (`200ms` instant, `300ms` fast, `400ms` normal) with fluid spring physics (`cubic-bezier(0.16, 1, 0.3, 1)`), pill geometry (`radius: 99px`), active press micro-interactions (`scale(0.97)`), and glowing live camera beacon.
- **Explicit Recognition Badges in Decision History**:
  - Every activity row in the decision history clearly displays whether the person was **`RECOGNISED`** (emerald badge) or **`NOT RECOGNISED`** (electric vermilion badge for unknown/unmatched faces), alongside detailed access subtitles and calendar timestamps.
- **Decoupled Voice Announcer Station Module**:
  - Removed voice controls from the live video stream bar, keeping the camera stream dedicated to video playback (`Pause view`, `Full screen`).
  - Voice Announcer now operates as an independent station audio module in the specifications sidebar, announcing access decisions and enrollment events without polling stream frames.
