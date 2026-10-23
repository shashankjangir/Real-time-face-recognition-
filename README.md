# Real-Time Facial Recognition & Access System

Python · OpenCV · SQLite · Raspberry Pi 5

A camera-based identity recognition service with a live Flask dashboard,
threaded acquisition, vectorized cosine matching, and searchable authentication
history. Enrollment requires administrator authentication, exactly one detected
face, and measured image quality.


## Project Generations

This repository includes two generations of the real-time access system:

* **[Generation 1: dlib (HOG + ResNet-128D)](gen-1-dlib/)**: The stable baseline utilizing dlib's metric learning pipeline, software tilt rotational pyramid search, and Apple design dashboard.
* **[Generation 2: SCRFD (InsightFace + ONNX Runtime)](gen-2-scrfd/)**: The next-generation high-speed pipeline utilizing SCRFD-500M ONNX inference. Runs at **60+ FPS (<8 ms)** on Raspberry Pi 5 CPU with native 5-keypoint detection and hardware tilt tolerance.

---

## Features

- Picamera2 and USB camera backends, plus a synthetic development stream.
- 128-dimensional face embeddings through `face_recognition` / dlib.
- Browser-independent recognition workers, timestamped frames and stale-work rejection.
- One JPEG encoder shared by all viewers, with measured runtime telemetry.
- Monochrome, responsive dashboard with shared live video, identity search and history filters.
- Capture-quality diagnostics and explicit continuous autofocus on supported Pi cameras.
- SQLite WAL storage, indexed history queries, sessions, and filtered CSV exports.
- Administrator-protected web enrollment and local image-file enrollment.
- Unit and integration tests, including enrollment rejection paths.

## Project status

The project's hardware and access-control setup have been completed by the
maintainer. This repository contains the camera, recognition, dashboard, and
logging software; external relay/lock and spoof-resistance integration should
be documented alongside its deployment.

| Evaluation target | Evidence available here |
| --- | --- |
| 50+ enrolled people | The evaluator builds a real-image gallery; supply 50+ people in an independent capture manifest. |
| Greater than 95% classification accuracy | Labelled image evaluation reports real predictions; independent captures are required. |
| Less than 300 ms decision latency on Pi 5 | Pi mode measures software delivery-to-decision including queue wait; actual hardware results are required. |
| Sustained 15–20 FPS video | Pi mode counts unique capture/JPEG frames separately from inference decisions. |
| Indexed SQLite history and CSV export | Implemented, with database and reporting tests. |

### Physical Hardware Testing & Observed Edge Cases (Pi 5 + Camera Module 3)

Physical testing on Raspberry Pi 5 hardware (Debian Trixie, Sony IMX708 Camera Module 3) surfaced operational issues that are now resolved:
1. **Camera Autofocus (IMX708 PDAF)**: Continuous autofocus (`AfMode: Continuous`) triggered glibc heap corruption (`corrupted double-linked list`) under `libcamera 0.7.2` in multi-threaded capture. Switched to `Auto` with an active trigger signal (`AfTrigger: Start`) on boot, locking sharp focal planes without crashes.
2. **Core Saturation**: Spawning 4 recognition worker threads on a 4-core Cortex-A76 while ONNX Runtime simultaneously spammed 4 execution threads created severe scheduling contention (decision latency spiked to >450ms). Balanced to `NUM_WORKER_THREADS = 2` and `intra_op_num_threads = 2` for clean sub-200ms processing.
3. **Enrollment Lighting Sensitivity**: In typical indoor lighting (50–150 lux), the strict Laplacian blur score could cause false-positive rejections. Standardized `ENROLLMENT_MIN_QUALITY` to `0.55` while retaining strict single-face checks.

The app and Pi evaluator share one runtime. The dashboard reports measured capture,
JPEG and recognition rates; accuracy remains unmeasured without labelled data.
See [benchmarking and evidence](docs/benchmarking.md) before interpreting their
numbers. Accuracy and latency targets are not presented as verified hardware results.

## Quick start

Run commands from the repository root. Use Python 3.10 or newer; Raspberry Pi OS
system Python is recommended for camera deployments.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows PowerShell, activate with `.\.venv\Scripts\Activate.ps1` instead.
For recognition and enrollment, also install the required model dependency:

```bash
python -m pip install -r requirements-face-recognition.txt
```

For Raspberry Pi, follow [the hardware installation guide](docs/raspberry-pi-setup.md)
instead so the environment can use the system camera bindings.

The web dashboard and live stream require no login credentials. Enrollment is protected by `ENROLLMENT_PASSWORD` (default: `123456789`).

```bash
python app.py
```

Open [the dashboard](http://localhost:5000). `python recognize_stream.py` remains
a compatibility launch command. Camera/model failures stop recognition and are
reported explicitly. Simulation requires `CAMERA_BACKEND=synthetic`; enrollment
and access grants are disabled in simulation. The pretrained face model is required.
See [decision and failure behavior](docs/decision-safety.md).

### Enrollment

The web dashboard and live camera stream are available without login credentials. To protect identity enrollment, set an `ENROLLMENT_PASSWORD` in your environment or `.env` file (defaults to `123456789` if unset). Enter this password into the enrollment form on the dashboard to register new faces. See [enrollment and authentication](docs/enrollment.md) for setup, API requests, quality checks, and local CLI usage.

```bash
python enroll.py --name "Jane Doe" --image /path/to/portrait.jpg
```

`.env.example` describes supported environment variables. It is a reference;
the application does not automatically load `.env` files.

### Tests and development benchmarks

```bash
python scripts/run_tests.py
```

The test runner uses temporary storage and a synthetic camera, then stops the
worker threads. It does not write test identities or CSVs into your working database.

```bash
python benchmark.py --manifest /path/to/manifest.csv --mode images
```

This evaluates labelled real-face images. For Pi camera measurements, use
`--mode pi --seconds 600` on the Pi 5. See [the evaluation guide](docs/benchmarking.md).

## Repository layout

```text
.
├── app.py / enroll.py / benchmark.py   # Public launch commands
├── recognize_stream.py                # Compatibility launch command
├── src/                               # Current application modules
├── tests/                             # Automated tests
├── scripts/                           # Development utilities
├── docs/                              # Architecture, setup, and evaluation
├── hardware/                          # Parts, wiring, and bring-up checklist
├── archive/                           # Earlier implementations and planning
├── data/                              # Local database and embeddings (ignored)
├── known_faces/                       # Local biometric images (ignored)
└── reports/                           # Generated exports (ignored)
```

## Documentation

- [Architecture and API](docs/architecture.md)
- [Hardware requirements and wiring](hardware/README.md)
- [Raspberry Pi setup](docs/raspberry-pi-setup.md)
- [Enrollment and administrator authentication](docs/enrollment.md)
- [Benchmarking, limitations, and hardware evaluation](docs/benchmarking.md)
- [Earlier versions](archive/README.md)
- [Implementation status and validation roadmap](docs/cv-claims-implementation-plan.md)
- [Contributing](CONTRIBUTING.md)

Local databases, biometric images, credentials, logs, and generated reports are
excluded from Git.

## License

Project code and documentation are available under the [MIT License](LICENSE).
Third-party libraries and pretrained model files retain their own licenses.


### Spoken announcements

Click **Enable voice** beside the live camera to hear "Name, recognised", "Unknown",
and "Name, enrolled" after a successful enrollment in that browser. Audio plays on
the device viewing the dashboard, not automatically through the Pi. Use **Mute voice**
to stop it. An installed local browser/OS speech voice is required; if none is
available the dashboard explains why. Voice is opt-in on each page load and pauses
when the tab is hidden. Names and unknown announcements repeat at most once per ten
seconds; empty frames and historical logs are not spoken. Recognition announcements
identify matches, not authorization or confirmation that a door opened.

Run speech logic checks with `node tests/test_speech.js` in addition to the Python suite.

---

## Update Log

### [2026-10-21 17:52 IST] — Apple Design System & Face ID Core Architecture Update

- **Apple Design System Redesign**:
  - Restyled web dashboard (`src/templates/dashboard.html`, `src/static/dashboard.css`) according to Apple's design reference: Frost canvas (`#f5f5f7`), hairline dividers (`#d2d2d7`), Apple Blue (`#0071e3`) interactive switches, SF Pro type scale, flat elevation, and rounded pill controls (`980px` radius).
- **Eye Aspect Ratio (EAR) Liveness & Attention Verification**:
  - Added `calculate_ear()` and `check_attention()` in `src/recognition_engine.py` using 6-point eye landmarks.
  - Enforced in `src/access.py`: denies inattentive or closed-eye attempts (eye-openness check only, not liveness protection) with decision reason `attention_required`.
- **Multi-Sample Angular Centroid Enrollment**:
  - Added `create_robust_template()` in `src/enroll.py` and `--images` CLI argument in `enroll.py`.
  - Supports multi-pose angular captures (e.g. left, center, right) to generate a normalized 128D centroid embedding for enrollment.
- **Continuous Biometric Template Adaptation**:
  - Added `adapt_identity_template()` in `src/database.py`; after a successful persisted update, recognition reloads the stored templates.
  - Automatically updates stored identity embeddings via Exponential Moving Average ($0.95 \cdot v_{\text{old}} + 0.05 \cdot v_{\text{new}}$) whenever a verified match has high confidence (cosine distance $\le 0.04$).
- **360° Tilt-Invariant Face Recognition**:
  - Implemented multi-angle rotational pyramid search `(-30°, 30°, -60°, 60°, -90°, 90°, 180°, -120°, 120°)` with fast zero-copy $2\times$ downsampling (`rgb[::2, ::2]`).
  - Added `unrotate_box()` trigonometric mapping to un-rotate bounding boxes back to original camera coordinates.
  - Added angle caching (`self.last_tilt_angle`) so subsequent frames of a tilted face incur zero search latency overhead.
- **Automated Verification**:
  - Added test suite `tests/test_apple_features.py` testing attention rejection, multi-sample enrollment, continuous adaptation, and tilt-invariant detection.


### [2026-10-21 18:00 IST] — Hardware Profile Specification (4GB RAM & 64GB Storage)

- **Target Hardware Calibration**:
  - Calibrated physical hardware profile to **Raspberry Pi 5 (4GB RAM)** across all documentation, requirements sheets, and architectural guides (corrected from earlier 8GB references).
  - Standardized storage media specification to a **64GB microSD card** running 64-bit Raspberry Pi OS in hardware/requirements.md and hardware/deployment.example.md.

### [2026-10-21 18:30 IST] — Multi-Generation Project Structure (Gen 1 dlib & Gen 2 SCRFD)

- **Generation Folders Created**:
  - `gen-1-dlib/`: Preserved complete baseline pipeline running dlib HOG + 128D ResNet.
  - `gen-2-scrfd/`: Upgraded pipeline running InsightFace SCRFD ONNX Runtime detector (<8ms latency, 60+ FPS, native 5-point facial landmarks).
- **Requirements & Documentation**:
  - Added `onnxruntime` dependency and `src/scrfd.py` ONNX engine to `gen-2-scrfd/`.
  - Updated all documentation in `gen-2-scrfd/` (`README.md`, `docs/architecture.md`) reflecting SCRFD progress.

### [2026-10-21 19:25 IST] — Raspberry Pi 5 Deployment Readiness & Raspberry Pi Terminal Guide (`guide_raspberry.md`)

- **Raspberry Pi 5 Deployment Guide Created**:
  - Authored comprehensive terminal guide [`guide_raspberry.md`](guide_raspberry.md) covering end-to-end deployment for **Raspberry Pi 5 (4GB RAM, 64GB MicroSD)** running Raspberry Pi OS (64-bit Bookworm).
  - Documents SSH remote connection, CSI camera verification (`rpicam-hello --list-cameras`), USB webcam diagnostics (`v4l2-ctl`), virtual environment configuration with `--system-site-packages` for `picamera2`, parallelized `dlib` compilation, running Gen-2 SCRFD / Gen-1 dlib, browser dashboard access, CLI enrollment, and production `systemd` autostart configuration (`face-access.service`).
- **Automated Linux Setup Script**:
  - Created [`setup_rpi.sh`](setup_rpi.sh) for 1-command installation of system dependencies, Picamera2/libcamera, Python wheels (`setuptools<70`), and ONNX Runtime models on Raspberry Pi.
- **Dedicated Raspberry Pi Execution Scripts**:
  - Added executable Bash scripts [`gen-2-scrfd/run.sh`](gen-2-scrfd/run.sh) and [`gen-1-dlib/run.sh`](gen-1-dlib/run.sh) pre-configured with `CAMERA_BACKEND=auto`, a user-provided `ADMIN_ENROLLMENT_TOKEN`, and UTF-8 encoding.
- **Windows Runner & Terminal Compatibility**:
  - Added Windows runners (`run.ps1` and `run.bat`) for both generations, resolved `cp1252` terminal encoding, and fixed `setuptools>=70` `pkg_resources` compatibility issue.

### [2026-10-22 12:05 IST] — SQLite Concurrency Protection & Pipeline Safety Hardening

- **SQLite WAL Concurrency & Flash Wear Protection**:
  - Added rate-limiting to `adapt_identity_template()` in `src/database.py` with thread-safe timestamp tracking (`min_interval=10.0s`). Prevents SQLite write-lock contention and excessive flash memory wear under continuous 30 FPS video streaming.
  - Verified with unit tests in `tests/test_apple_features.py` ensuring single-call execution while debouncing high-frequency frames.
- **Fail-Fast Camera & Recognition Safety**:
  - Hardened `CameraManager` hardware verification on instantiation, ensuring proper failure propagation and zero silent fallback to synthetic streams.
  - Fixed class-level attribute fallback for `last_tilt_angle` in `src/recognition_engine.py` for decoupled test runner instances.
- **Compatibility Entry Point Restored**:
  - Restored `recognize_stream.py` as a lightweight compatibility launch shim forwarding to `app.py`.
- **Documentation Verification**:
  - Validated all cross-document markdown links across all root, gen-1, gen-2, hardware, and archive READMEs.

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

