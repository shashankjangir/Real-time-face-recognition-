# Real-Time Facial Recognition & Access System

Python · OpenCV · SQLite · Raspberry Pi 5

A camera-based identity recognition service with a live Flask dashboard,
threaded acquisition, vectorized cosine matching, and searchable authentication
history. Enrollment requires administrator authentication, exactly one detected
face, and measured image quality.

## Features

- Picamera2 and USB camera backends, plus a synthetic development stream.
- 128-dimensional face embeddings through `face_recognition` / dlib.
- Browser-independent recognition workers, timestamped frames and stale-work rejection.
- One JPEG encoder shared by all viewers, with measured runtime telemetry.
- Live bounding boxes and identity labels through an MJPEG dashboard.
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

```bash
python app.py
```

Open [the dashboard](http://localhost:5000). `python recognize_stream.py` remains
a compatibility launch command. Camera/model failures stop recognition and are
reported explicitly. Simulation requires `CAMERA_BACKEND=synthetic`; enrollment
and access grants are disabled in simulation. The pretrained face model is required.
See [decision and failure behavior](docs/decision-safety.md).

### Enrollment

Configure `ADMIN_ENROLLMENT_TOKEN` before starting the server, then enter it in
the dashboard's administrator token field. Web enrollment is disabled when the
variable is unset. See [enrollment and authentication](docs/enrollment.md) for
setup, API requests, quality checks, and local CLI usage.

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
