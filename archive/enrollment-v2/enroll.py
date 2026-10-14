"""
Efficient face enrollment for the Raspberry Pi 5 + Camera Module 3 pipeline.

Improvements over the original enroll.py:
  - Uses a persistent Picamera2 instance instead of spawning rpicam-still per
    capture (no ~1s+ subprocess/camera re-init cost per photo).
  - Auto-capture: a cheap Haar-cascade check runs on every preview frame to
    confirm a single, centered, well-sized face before anything expensive runs.
  - Captures several samples per person (small natural variation in pose/
    lighting) instead of one static photo, with outlier rejection for blinks
    or motion blur.
  - Stores each accepted sample as its own encoding (same name), which is
    fully compatible with recognize_stream.py's existing matching logic and
    performs better than averaging samples into a single vector.
"""

import os
import time
import pickle

import cv2
import numpy as np
import face_recognition
from picamera2 import Picamera2

KNOWN_FACES_DIR = "known_faces"
ENCODINGS_FILE = "encodings.pkl"

FRAME_WIDTH = 640
FRAME_HEIGHT = 480

SAMPLES_TO_CAPTURE = 12       # target number of accepted encoding samples per person
SAMPLE_INTERVAL = 0.25        # min seconds between two accepted samples
CENTER_TOLERANCE = 0.15       # face center must be within 15% of frame center (x and y)
MIN_FACE_RATIO = 0.15         # face width must be at least this fraction of frame width
MAX_FACE_RATIO = 0.55         # ...and at most this fraction (too close otherwise)
STABLE_FRAMES_REQUIRED = 8    # consecutive well-positioned frames before capturing starts
OUTLIER_THRESHOLD = 0.45      # reject samples whose encoding is farther than this from the median

os.makedirs(KNOWN_FACES_DIR, exist_ok=True)

_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


def _quick_face_box(gray_frame):
    """Cheap Haar-cascade check used purely for live centering feedback."""
    faces = _cascade.detectMultiScale(
        gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
    )
    if len(faces) != 1:
        return None
    return faces[0]  # (x, y, w, h)


def _is_well_positioned(box, frame_w, frame_h):
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    dx = abs(cx - frame_w / 2) / frame_w
    dy = abs(cy - frame_h / 2) / frame_h
    face_ratio = w / frame_w
    centered = dx < CENTER_TOLERANCE and dy < CENTER_TOLERANCE
    right_size = MIN_FACE_RATIO < face_ratio < MAX_FACE_RATIO
    return centered and right_size


def _load_encodings():
    if os.path.exists(ENCODINGS_FILE):
        with open(ENCODINGS_FILE, "rb") as f:
            return pickle.load(f)
    return {"encodings": [], "names": []}


def _save_encodings(data):
    with open(ENCODINGS_FILE, "wb") as f:
        pickle.dump(data, f)


def enroll_person(name, picam2):
    print(f"\n--- Enrolling '{name}' ---")
    print("Look at the camera. Capture happens automatically once you're centered.\n")

    stable_count = 0
    samples = []  # list of (rgb_frame, encoding)
    last_capture_time = 0.0

    while len(samples) < SAMPLES_TO_CAPTURE:
        frame = picam2.capture_array()  # RGB888
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        box = _quick_face_box(gray)

        if box is None:
            stable_count = 0
            print("\r  ...no single face detected          ", end="", flush=True)
            continue

        if not _is_well_positioned(box, FRAME_WIDTH, FRAME_HEIGHT):
            stable_count = 0
            print("\r  face found — please center / adjust distance   ", end="", flush=True)
            continue

        stable_count += 1
        print(f"\r  centered, holding steady... {stable_count}/{STABLE_FRAMES_REQUIRED}   ",
              end="", flush=True)

        if stable_count < STABLE_FRAMES_REQUIRED:
            continue

        now = time.time()
        if now - last_capture_time < SAMPLE_INTERVAL:
            continue
        last_capture_time = now

        # Only run the expensive dlib encoder on frames that already passed
        # the cheap positioning check.
        encodings = face_recognition.face_encodings(frame)
        if len(encodings) != 1:
            continue  # face moved between the two checks; skip this frame

        samples.append((frame.copy(), encodings[0]))
        print(f"\r  captured sample {len(samples)}/{SAMPLES_TO_CAPTURE}                        ",
              flush=True)

    print("\n  Filtering outliers (blinks / motion blur)...")
    vectors = np.array([enc for _, enc in samples])
    median_vec = np.median(vectors, axis=0)
    distances = np.linalg.norm(vectors - median_vec, axis=1)
    keep = [i for i, d in enumerate(distances) if d < OUTLIER_THRESHOLD]

    if len(keep) < 3:
        print("  Too many inconsistent samples — try again with steadier framing and even lighting.")
        return False

    kept_samples = [samples[i] for i in keep]
    print(f"  Kept {len(kept_samples)}/{len(samples)} samples after outlier rejection.")

    # Save one representative reference photo for your own records.
    ref_frame, _ = kept_samples[len(kept_samples) // 2]
    ref_bgr = cv2.cvtColor(ref_frame, cv2.COLOR_RGB2BGR)
    cv2.imwrite(os.path.join(KNOWN_FACES_DIR, f"{name}.jpg"), ref_bgr)

    data = _load_encodings()
    for _, enc in kept_samples:
        data["encodings"].append(enc)
        data["names"].append(name)
    _save_encodings(data)

    print(f"✓ Enrolled '{name}' with {len(kept_samples)} encoding samples. "
          f"Total encodings stored: {len(data['names'])}")
    return True


def main():
    print("=== Efficient Face Enrollment (auto-capture, multi-sample) ===")
    picam2 = Picamera2()
    picam2.configure(picam2.create_video_configuration(
        main={"format": "RGB888", "size": (FRAME_WIDTH, FRAME_HEIGHT)}
    ))
    picam2.start()
    time.sleep(1)  # let sensor settle / auto-exposure adjust

    try:
        while True:
            name = input("\nEnter name to enroll (or 'q' to quit): ").strip()
            if name.lower() == "q":
                break
            if name:
                enroll_person(name, picam2)
    finally:
        picam2.stop()


if __name__ == "__main__":
    main()
