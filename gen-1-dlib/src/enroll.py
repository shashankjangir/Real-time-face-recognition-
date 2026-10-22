"""
Face Enrollment Module for Real-Time Facial Recognition & Access System
Extracts 128D metric embeddings with image quality validation and SQLite persistence.
"""

import os
import time

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


def face_quality_report(frame_bgr, box):
    """Explain the enrollment heuristic; not a calibrated recognition probability."""
    h, w = frame_bgr.shape[:2]
    t, r, b, l = max(0, box.top), min(w, box.right), min(h, box.bottom), max(0, box.left)
    if b <= t or r <= l:
        return dict(score=0.0, threshold=config.ENROLLMENT_MIN_QUALITY, ready=False,
                    components={}, guidance=['Face crop is outside the image.'])
    gray = cv2.cvtColor(frame_bgr[t:b, l:r], cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(np.mean(gray))
    sharpness_score = min(1.0, sharpness / 300.0)
    brightness_score = (1.0 if 70 <= brightness <= 190 else
                        max(0.2, 1.0-min(abs(brightness-70), abs(brightness-190))/70.0))
    size = min(r-l, b-t)
    size_score = min(1.0, size/100.0)
    score = round(.4*sharpness_score + .3*brightness_score + .3*size_score, 3)
    guidance = []
    if sharpness_score < .75:
        guidance.append('Sharpness is low. Hold still, keep your face near the centre, and give autofocus time to settle. Check the lens is clean.')
    if brightness < 70:
        guidance.append('Face is too dark. Use a steady, diffuse light in front of you.')
    elif brightness > 190:
        guidance.append('Face is too bright. Move direct light away; avoid pointing a phone flash at your face.')
    if size < 100:
        guidance.append('Face is small in the image. Move closer gradually while staying within focus range.')
    if not guidance:
        guidance.append('Capture conditions look suitable. Enrollment will check a fresh frame.')
    return dict(score=score, threshold=config.ENROLLMENT_MIN_QUALITY,
                ready=score >= config.ENROLLMENT_MIN_QUALITY,
                components=dict(sharpness=dict(score=round(sharpness_score,3), value=round(sharpness,1), unit='Laplacian variance', weight=.4),
                                brightness=dict(score=round(brightness_score,3), value=round(brightness,1), unit='mean / 255', weight=.3),
                                size=dict(score=round(size_score,3), value=size, unit='px, shortest side', weight=.3)),
                face_width=r-l, face_height=b-t, guidance=guidance)


def create_robust_template(embeddings: List[np.ndarray]) -> np.ndarray:
    """Compute normalized centroid template from multiple captures (Apple-style enrollment)."""
    if not embeddings:
        raise ValueError("At least one embedding is required.")
    stacked = np.array([normalize_vector(np.asarray(e, dtype=np.float64)) for e in embeddings], dtype=np.float64)
    centroid = np.mean(stacked, axis=0)
    return normalize_vector(centroid)


def assess_face_quality(frame_bgr, box):
    return face_quality_report(frame_bgr, box)['score']


def enroll_identity(name: str, encoding: np.ndarray, quality_score: float = 1.0,
                   photo_path: str = None, db_manager: DatabaseManager = None) -> int:
    """
    Persist enrolled identity into SQLite database and sync to encodings cache.
    """
    db = db_manager or get_db_manager()
    if isinstance(encoding, (list, tuple)) or (isinstance(encoding, np.ndarray) and encoding.ndim > 1):
        vec128 = create_robust_template(list(encoding))
    else:
        vec128 = normalize_vector(np.asarray(encoding, dtype=np.float64))
    raw_bytes = vec128.tobytes()

    ident_id = db.add_identity(
        name=name,
        encoding=raw_bytes,
        quality_score=quality_score,
        photo_path=photo_path,
        notes="Enrolled via automated access pipeline"
    )

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




def enroll_from_multiple_images(image_paths: List[str], name: str, db_manager: DatabaseManager = None) -> bool:
    """Enroll an identity from multiple angle image files (Apple multi-pose capture)."""
    embeddings = []
    qualities = []
    engine = RecognitionEngine(db_manager=db_manager)
    for p in image_paths:
        if not os.path.exists(p):
            continue
        frame = cv2.imread(p)
        if frame is None:
            continue
        try:
            emb, q = validate_enrollment_frame(frame, engine)
            embeddings.append(emb)
            qualities.append(q)
        except Exception:
            continue
    if not embeddings:
        print(f"Failed to extract valid faces from provided images for '{name}'.")
        return False
    avg_quality = float(np.mean(qualities))
    enroll_identity(name=name, encoding=embeddings, quality_score=avg_quality, photo_path=image_paths[0], db_manager=db_manager)
    print(f"Successfully enrolled '{name}' with {len(embeddings)} angular samples (Avg Quality: {avg_quality:.2f})")
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
