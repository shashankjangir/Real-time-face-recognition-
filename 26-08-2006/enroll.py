import face_recognition
import pickle
import os
import subprocess

KNOWN_FACES_DIR = "known_faces"
ENCODINGS_FILE = "encodings.pkl"

def capture_photo(name):
    """Capture a photo using rpicam-still and save it."""
    filepath = os.path.join(KNOWN_FACES_DIR, f"{name}.jpg")
    print(f"\nCapturing photo for {name} in 3 seconds... look at the camera")
    subprocess.run([
        "rpicam-still", "-t", "3000", "-o", filepath,
        "--width", "640", "--height", "480", "-n"
    ])
    return filepath

def enroll_person(name):
    filepath = capture_photo(name)
    image = face_recognition.load_image_file(filepath)
    encodings = face_recognition.face_encodings(image)

    if len(encodings) == 0:
        print(f"No face detected. Try again with better lighting.")
        os.remove(filepath)
        return False

    if len(encodings) > 1:
        print(f"Multiple faces detected. Make sure only {name} is in frame.")
        os.remove(filepath)
        return False

    if os.path.exists(ENCODINGS_FILE):
        with open(ENCODINGS_FILE, "rb") as f:
            data = pickle.load(f)
    else:
        data = {"encodings": [], "names": []}

    data["encodings"].append(encodings[0])
    data["names"].append(name)

    with open(ENCODINGS_FILE, "wb") as f:
        pickle.dump(data, f)

    print(f"✓ Enrolled {name} successfully. Total enrolled: {len(data['names'])}")
    return True

if __name__ == "__main__":
    print("=== Face Enrollment from Camera ===")
    while True:
        name = input("\nEnter name to enroll (or 'q' to quit): ").strip()
        if name.lower() == 'q':
            break
        if name:
            enroll_person(name)
