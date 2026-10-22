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
- Added `run.sh` bash runner for native execution on Raspberry Pi 5 terminal (`CAMERA_BACKEND=auto`, `ADMIN_ENROLLMENT_TOKEN=admin123`).
- Added `run.ps1` and `run.bat` runners for local Windows verification.
- Added `from __future__ import annotations` to resolve typing forward references cleanly across Python 3.9+.
- Linked root terminal deployment guide [`guide_raspberry.md`](../guide_raspberry.md).
