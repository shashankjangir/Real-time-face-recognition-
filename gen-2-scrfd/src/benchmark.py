"""Evaluate independent labelled face captures and measure a real Pi 5 camera."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version, PackageNotFoundError
import json
import platform
from pathlib import Path
import sys
import tempfile
import time

import cv2
import numpy as np

from . import config
from . import recognition_engine as recognition
from .camera import CameraManager
from .runtime import RecognitionRuntime
from .database import DatabaseManager
from .enroll import validate_enrollment_frame
from .recognition_engine import RecognitionEngine

UNKNOWN = "Unknown"


def device_model():
    path = Path("/proc/device-tree/model")
    return path.read_text().strip("\x00\n") if path.exists() else platform.machine()


def require_real_model():
    if not recognition.HAS_FACE_RECOGNITION:
        raise RuntimeError("Install requirements-face-recognition.txt; evaluation never uses synthetic embeddings or the OpenCV fallback.")


def load_manifest(path):
    """Require independent enrollment/test sessions and reject duplicate content."""
    path = Path(path).resolve()
    records, hashes, sessions = [], set(), {"enroll": set(), "test": set()}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not {"split", "name", "image", "session"}.issubset(reader.fieldnames or []):
            raise ValueError("Manifest requires split,name,image,session columns.")
        for number, row in enumerate(reader, 2):
            split, name, session = ((row.get(key) or "").strip() for key in ("split", "name", "session"))
            if split not in sessions or not name or not session or not (row.get("image") or "").strip():
                raise ValueError(f"Invalid manifest row {number}.")
            if split == "enroll" and name == UNKNOWN:
                raise ValueError("Unknown is reserved for unenrolled test people.")
            image = (path.parent / row["image"].strip()).resolve()
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            if digest in hashes:
                raise ValueError(f"Repeated image content at row {number}; enrollment and tests must be independent.")
            hashes.add(digest)
            sessions[split].add(session)
            records.append({"split": split, "name": name, "image": str(image), "session": session, "sha256": digest})
    if not all(sessions.values()) or sessions["enroll"] & sessions["test"]:
        raise ValueError("Enrollment and test captures must use separate session labels.")
    enrolled = {row["name"] for row in records if row["split"] == "enroll"}
    if len(enrolled) != sum(row["split"] == "enroll" for row in records):
        raise ValueError("Use one enrollment image per identity; the current matcher stores one active template.")
    tested = {row["name"] for row in records if row["split"] == "test"}
    if not enrolled.issubset(tested) or tested - enrolled - {UNKNOWN} or UNKNOWN not in tested:
        raise ValueError("Test every enrolled identity and include unenrolled people labelled Unknown.")
    return records


def read_image(row):
    frame = cv2.imread(row["image"])
    if frame is None:
        raise ValueError(f"Cannot decode image: {row['image']}")
    return frame


def build_gallery(records, db):
    engine = RecognitionEngine(db)
    for row in records:
        if row["split"] == "enroll":
            embedding, quality = validate_enrollment_frame(read_image(row), engine)
            # Write only to this evaluation's temporary database, never to the live cache.
            db.add_identity(row["name"], embedding.astype(np.float64).tobytes(), quality_score=quality)
    engine.reload_identities()
    return engine


def predict_frame(engine, frame, threshold):
    detections = engine.detect_and_extract(frame, strict=True)
    if len(detections) != 1:
        raise ValueError("Evaluation requires exactly one face per capture.")
    _, embedding = detections[0]
    if embedding.shape != (128,) or not np.isfinite(embedding).all() or np.linalg.norm(embedding) < 1e-10:
        raise ValueError("Invalid embedding from model.")
    matched, name, _, distance, _ = engine.match_embedding(embedding, threshold=threshold)
    return name if matched else UNKNOWN, distance


def latency_stats(values):
    if not values:
        return None
    return {"mean_ms": float(np.mean(values)), "median_ms": float(np.median(values)),
            "p95_ms": float(np.percentile(values, 95)), "max_ms": float(np.max(values))}


def summarize_predictions(rows, identities):
    known = [r for r in rows if r["expected"] != UNKNOWN]
    unknown = [r for r in rows if r["expected"] == UNKNOWN]
    correct = sum(r["correct"] for r in rows)
    known_correct = sum(r["correct"] for r in known)
    false_accepts = sum(r["valid_capture"] and r["predicted"] != UNKNOWN for r in unknown)
    false_rejects = sum(r["valid_capture"] and r["predicted"] == UNKNOWN for r in known)
    wrong_ids = sum(r["valid_capture"] and r["predicted"] not in (UNKNOWN, r["expected"]) for r in known)
    accuracy = correct / len(rows) if rows else None
    known_accuracy = known_correct / len(known) if known else None
    return {"enrolled_identities": identities, "test_captures": len(rows), "known_captures": len(known),
            "unknown_captures": len(unknown), "accuracy": accuracy,
            "known_identity_accuracy": known_accuracy,
            "unknown_rejection_rate": sum(r["correct"] for r in unknown) / len(unknown) if unknown else None,
            "false_acceptance_rate": false_accepts / len(unknown) if unknown else None,
            "false_rejection_rate": false_rejects / len(known) if known else None,
            "wrong_identity_predictions": wrong_ids,
            "invalid_captures": sum(not r["valid_capture"] for r in rows),
            "targets": {"identities_50_plus": identities >= 50,
                        "accuracy_above_95_percent": accuracy is not None and accuracy > 0.95,
                        "known_identity_accuracy_above_95_percent": known_accuracy is not None and known_accuracy > 0.95}}


def evaluate_images(records, engine, threshold):
    rows = []
    for record in records:
        if record["split"] != "test":
            continue
        frame = read_image(record)
        start = time.perf_counter()
        try:
            predicted, distance = predict_frame(engine, frame, threshold)
            valid, error = True, None
        except ValueError as exc:
            predicted, distance, valid, error = None, None, False, str(exc)
        # Model/runtime failures abort the run instead of masquerading as rejection.
        elapsed = (time.perf_counter() - start) * 1000
        rows.append({"image": record["image"], "sha256": record["sha256"], "session": record["session"],
                     "expected": record["name"], "predicted": predicted, "distance": distance,
                     "valid_capture": valid, "correct": valid and predicted == record["name"],
                     "processing_ms": elapsed, "error": error})
    report = summarize_predictions(rows, len(engine.known_names))
    report.update({"mode": "labelled_images", "predictions": rows,
                   "valid_capture_processing_latency": latency_stats([r["processing_ms"] for r in rows if r["valid_capture"]]),
                   "latency_scope": "Image decoding excluded; detection, embedding and matching included. Not capture-to-decision latency.",
                   "hardware_targets": None})
    return report


def measure_pi(engine, threshold, seconds):
    """Exercise the same producer, workers, audit and JPEG runtime as the app."""
    if "Raspberry Pi 5" not in device_model():
        raise RuntimeError("Pi measurement must run on a Raspberry Pi 5.")
    if not np.isfinite(seconds) or seconds <= 0:
        raise ValueError("Duration must be positive and finite.")
    engine.threshold = threshold
    camera = CameraManager(backend_type='picamera2')
    runtime = RecognitionRuntime(engine, camera, record=True)
    try:
        runtime.start()
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            runtime.check_health()
            runtime.stop_event.wait(min(.05, max(0, deadline-time.monotonic())))
    finally:
        runtime.stop()
    runtime.check_health()
    metrics = runtime.snapshot()
    rows = runtime.records
    latency = latency_stats([r['delivery_to_decision_ms'] for r in rows if r['decisions']])
    video_fps = metrics['unique_jpeg_fps']
    return {"mode": "pi_camera", "duration_seconds": metrics['duration_seconds'], "backend": "Picamera2",
            "enrolled_identities": len(engine.known_names), "unique_frames": metrics['counts'],
            "capture_fps": metrics['capture_fps'], "unique_jpeg_fps": video_fps,
            "valid_face_decisions": metrics['counts']['face_decisions'],
            "valid_face_decisions_per_second": metrics['face_decisions_per_second'],
            "recognition_fps": metrics['recognition_fps'], "runtime_metrics": metrics,
            "delivery_to_decision_latency": latency,
            "processing_latency": latency_stats([r['processing_ms'] for r in rows]),
            "latency_scope": "Monotonic camera delivery to committed decision, including queue wait, inference and SQLite audit; excludes sensor exposure and HTTP transport. No physical actuator configured.",
            "pipeline": "Shared RecognitionRuntime: configured worker pool, bounded stale-frame queue, one JPEG encoder, normal decision/audit path.",
            "action_mode": "not_configured", "accuracy": None, "decisions": rows,
            "targets": {"identities_50_plus": len(engine.known_names) >= 50,
                        "p95_delivery_to_decision_below_300_ms": None if latency is None else latency['p95_ms'] < 300,
                        "unique_jpeg_fps_at_least_15": video_fps >= 15}}


def run_full_benchmark(manifest, mode="images", threshold=None, seconds=600):
    threshold = config.RECOGNITION_THRESHOLD if threshold is None else threshold
    if not np.isfinite(threshold) or not 0 < threshold < 2:
        raise ValueError("Cosine threshold must be between 0 and 2.")
    records = load_manifest(manifest)
    require_real_model()
    with tempfile.TemporaryDirectory(prefix="face-evaluation-") as temporary:
        db = DatabaseManager(str(Path(temporary) / "gallery.db"))
        try:
            engine = build_gallery(records, db)
            report = evaluate_images(records, engine, threshold) if mode == "images" else measure_pi(engine, threshold, seconds)
        finally:
            db.close()
    report["environment"] = {"device_model": device_model(), "platform": platform.platform(),
                             "python": platform.python_version(), "opencv": cv2.__version__,
                             "numpy": np.__version__, "model": "face_recognition/dlib", "threshold": threshold,
                             "camera_resolution": [config.CAMERA_WIDTH, config.CAMERA_HEIGHT], "frame_skip": config.FRAME_SKIP}
    report["manifest_sha256"] = hashlib.sha256(Path(manifest).read_bytes()).hexdigest()
    report["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["schema_version"] = 2
    report["environment"]["model_package_versions"] = {}
    for package in ("face-recognition", "dlib"):
        try:
            report["environment"]["model_package_versions"][package] = version(package)
        except PackageNotFoundError:
            report["environment"]["model_package_versions"][package] = None
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="CSV with split,name,image,session columns")
    parser.add_argument("--mode", choices=("images", "pi"), default="images")
    parser.add_argument("--threshold", type=float, default=config.RECOGNITION_THRESHOLD)
    parser.add_argument("--seconds", type=float, default=600, help="Pi run duration (default: 600)")
    parser.add_argument("--output", type=Path, default=config.REPORTS_DIR / "evaluation.json")
    args = parser.parse_args(argv)
    try:
        report = run_full_benchmark(args.manifest, args.mode, args.threshold, args.seconds)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Evaluation unavailable: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in ("predictions", "decisions")}, indent=2))
    print(f"Detailed report: {args.output}")
    targets = report["targets"]
    return 0 if all(value is True for value in targets.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
