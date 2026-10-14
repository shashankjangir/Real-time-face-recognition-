"""
Face Enrollment Module for Real-Time Facial Recognition & Access System
Extracts 128D metric embeddings with image quality validation and SQLite persistence.
"""

import os
import time
import pickle
import argparse
import logging
from typing import Optional, Tuple, List
import numpy as np
import cv2

try:
    from . import config
    from .database import get_db_manager, DatabaseManager
    from .recognition_engine import RecognitionEngine, normalize_vector, HAS_FACE_RECOGNITION
    from .camera import CameraManager
except (ImportError, ValueError):
    import config
    from database import get_db_manager, DatabaseManager
    from recognition_engine import RecognitionEngine, normalize_vector, HAS_FACE_RECOGNITION
    from camera import CameraManager

if HAS_FACE_RECOGNITION:
    import face_recognition

logger = logging.getLogger(__name__)


def assess_face_quality(frame_bgr: np.ndarray, box) -> float:
    """
    Compute face quality score (0.0 to 1.0) based on resolution, sharpness, and brightness.
    """
    t, r, b, l = box.top, box.right, box.bottom, box.left
    h, w = frame_bgr.shape[:2]
    t, b = max(0, t), min(h, b)
    l, r = max(0, l), min(w, r)
    if b <= t or r <= l:
        return 0.0

    crop = frame_bgr[t:b, l:r]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    # Sharpness (Laplacian variance)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    sharpness_score = min(1.0, laplacian_var / 300.0)

    # Brightness (ideal range 70-190)
    mean_val = float(np.mean(gray))
    if 70 <= mean_val <= 190:
        brightness_score = 1.0
    else:
        dist = min(abs(mean_val - 70), abs(mean_val - 190))
        brightness_score = max(0.2, 1.0 - (dist / 70.0))

    # Resolution (minimum 80x80 for high fidelity)
    face_w, face_h = (r - l), (b - t)
    size_score = min(1.0, min(face_w, face_h) / 100.0)

    final_score = (sharpness_score * 0.4) + (brightness_score * 0.3) + (size_score * 0.3)
    return round(float(final_score), 3)


def enroll_identity(name: str, encoding: np.ndarray, quality_score: float = 1.0,
                   photo_path: str = None, db_manager: DatabaseManager = None) -> int:
    """
    Persist enrolled identity into SQLite database and sync to encodings cache.
    """
    db = db_manager or get_db_manager()
    # Normalize to 128D unit vector
    vec128 = normalize_vector(encoding.astype(np.float64))
    raw_bytes = vec128.tobytes()

    ident_id = db.add_identity(
        name=name,
        encoding=raw_bytes,
        quality_score=quality_score,
        photo_path=photo_path,
        notes="Enrolled via automated access pipeline"
    )

    # Sync to legacy encodings.pkl for full backward compatibility
    sync_to_pickle(db)
    logger.info(f"Enrolled identity: {name} (ID: {ident_id}, Quality: {quality_score:.2f})")
    return ident_id


def validate_enrollment_frame(frame_bgr, engine):
    """Require one real detected face, a valid embedding, and measured quality."""
    if frame_bgr is None or not isinstance(frame_bgr, np.ndarray) or frame_bgr.size == 0:
        raise ValueError("No camera frame is available. Please capture again.")
    detections = engine.detect_and_extract(frame_bgr, strict=True)
    if len(detections) != 1:
        raise ValueError("Exactly one face is required for enrollment.")
    box, embedding = detections[0]
    if embedding.shape != (128,) or not np.isfinite(embedding).all() or np.linalg.norm(embedding) < 1e-10:
        raise ValueError("Invalid face embedding. Please capture again.")
    quality = assess_face_quality(frame_bgr, box)
    if quality < config.ENROLLMENT_MIN_QUALITY:
        raise ValueError(
            f"Face quality {quality:.3f} is below the required {config.ENROLLMENT_MIN_QUALITY:.3f}. "
            "Improve lighting, focus, and face size, then capture again."
        )
    return embedding, quality


def sync_to_pickle(db_manager: DatabaseManager = None):
    """Sync all SQLite identities to encodings.pkl for legacy tool compatibility."""
    db = db_manager or get_db_manager()
    rows = db.get_all_identities()
    encodings = []
    names = []

    for r in rows:
        try:
            vec = np.frombuffer(r['encoding'], dtype=np.float64)
            if len(vec) == 128:
                encodings.append(vec)
                names.append(r['name'])
        except Exception:
            pass

    data = {"encodings": encodings, "names": names}
    try:
        with open(config.ENCODINGS_FILE, "wb") as f:
            pickle.dump(data, f)
    except Exception as e:
        logger.warning(f"Failed to sync encodings.pkl: {e}")


def enroll_from_image_file(image_path: str, name: str, db_manager: DatabaseManager = None) -> bool:
    """Enroll a person from an existing image file."""
    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        return False

    frame_bgr = cv2.imread(image_path)
    if frame_bgr is None:
        print(f"Could not read image: {image_path}")
        return False

    engine = RecognitionEngine(db_manager=db_manager)
    try:
        emb, q_score = validate_enrollment_frame(frame_bgr, engine)
    except (ValueError, RuntimeError) as exc:
        print(str(exc))
        return False

    # Check for duplicate
    is_match, matched_name, conf, dist, _ = engine.match_embedding(emb)
    if is_match and matched_name != name:
        print(f"Warning: Face closely matches existing enrolled identity '{matched_name}' (distance: {dist:.3f}).")

    enroll_identity(name=name, encoding=emb, quality_score=q_score, photo_path=image_path, db_manager=db_manager)
    print(f"Successfully enrolled '{name}' (Quality Score: {q_score:.2f})")
    return True


def enroll_synthetic_identities(count: int = 50, db_manager: DatabaseManager = None) -> List[str]:
    """
    Generate and enroll high-separation 128D synthetic facial embeddings.
    Used for automated benchmarking, pipeline stress testing, and verifying 50+ identities.
    """
    db = db_manager or get_db_manager()
    names = []
    rng = np.random.RandomState(1337)

    first_names = [
        "Alexander", "Beatrice", "Carlos", "Diana", "Elena", "Franklin", "Gabriel", "Helena",
        "Isaac", "Julian", "Kavita", "Liam", "Maya", "Nathan", "Olivia", "Patrick",
        "Qasim", "Rohan", "Sophia", "Tara", "Umar", "Valerie", "Wyatt", "Xavier",
        "Yasmin", "Zachary", "Aarav", "Bhavna", "Chirag", "Deepak", "Esha", "Farhan",
        "Gaurav", "Harsh", "Ishaan", "Jaya", "Karan", "Lavanya", "Manish", "Neha",
        "Omkar", "Pooja", "Rahul", "Shreya", "Tanvi", "Utkarsh", "Varun", "William",
        "Yash", "Zoya", "Arjun", "Ananya"
    ]

    for i in range(count):
        name = first_names[i] if i < len(first_names) else f"Identity_{i+1:03d}"
        # Generate base identity direction on 128D sphere
        base_vec = rng.randn(128).astype(np.float32)
        base_vec = normalize_vector(base_vec)

        q_score = round(float(0.85 + rng.uniform(0.0, 0.14)), 3)
        enroll_identity(name=name, encoding=base_vec, quality_score=q_score, db_manager=db)
        names.append(name)

    print(f"Successfully enrolled {count} distinct identities into SQLite database.")
    return names


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Real-Time Face Enrollment Utility")
    parser.add_argument("--name", type=str, help="Name of the person to enroll")
    parser.add_argument("--image", type=str, help="Path to image file for enrollment")
    parser.add_argument("--synthetic", type=int, default=0, help="Enroll N synthetic identities for benchmarking")
    args = parser.parse_args()

    if args.synthetic > 0:
        enroll_synthetic_identities(args.synthetic)
    elif args.name and args.image:
        enroll_from_image_file(args.image, args.name)
    else:
        print("Please provide --synthetic <N> or --name <Name> --image <Path>")
