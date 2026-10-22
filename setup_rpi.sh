#!/usr/bin/env bash
# ==============================================================================
# Automated Raspberry Pi 5 (4GB RAM) Setup Script
# Real-Time Face Recognition & Access System (Gen-2 SCRFD / Gen-1 dlib)
# ==============================================================================
set -e

echo "======================================================================"
echo "🍓 Setting up Real-Time Face Recognition on Raspberry Pi 5 (4GB RAM)"
echo "======================================================================"

# 1. Update APT packages
echo "[1/6] Updating system packages..."
sudo apt update

# 2. Install required system dependencies & Picamera2
echo "[2/6] Installing build tools, libraries, and camera bindings..."
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-picamera2 \
    python3-libcamera \
    libcamera-apps \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libjpeg-dev \
    zlib1g-dev \
    git \
    v4l-utils

# 3. Create virtual environment with system site packages (enables Picamera2 access)
VENV_PATH="$HOME/face-access-env"
if [ ! -d "$VENV_PATH" ]; then
    echo "[3/6] Creating virtual environment at $VENV_PATH with system site-packages..."
    python3 -m venv --system-site-packages "$VENV_PATH"
else
    echo "[3/6] Virtual environment already exists at $VENV_PATH."
fi

# 4. Activate virtual environment
source "$VENV_PATH/bin/activate"

# 5. Install Python dependencies
echo "[4/6] Installing Python dependencies (setuptools<70, wheels, onnxruntime)..."
pip install --upgrade pip
pip install "setuptools<70" wheel

# Install dlib (parallelized on Pi 5's 4 CPU cores)
echo "Installing dlib..."
CMAKE_BUILD_PARALLEL_LEVEL=4 pip install dlib

# Install face-recognition and models
echo "Installing face-recognition..."
pip install face-recognition face-recognition-models

# Install project requirements
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/gen-2-scrfd/requirements.txt" ]; then
    pip install -r "$SCRIPT_DIR/gen-2-scrfd/requirements.txt"
elif [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    pip install -r "$SCRIPT_DIR/requirements.txt"
fi

# 6. Verify environment and cameras
echo "[5/6] Verifying package imports..."
python3 -c "
import cv2
import flask
import onnxruntime
import dlib
import face_recognition
try:
    from picamera2 import Picamera2
    print('✅ Picamera2 is available!')
except ImportError:
    print('ℹ️ Picamera2 not found; OpenCV backend will be used.')
print('✅ Core ML packages imported successfully!')
"

# 7. Check camera detection
echo "[6/6] Checking connected cameras..."
if command -v rpicam-hello &> /dev/null; then
    echo "CSI Ribbon Cameras:"
    rpicam-hello --list-cameras || true
fi
if command -v v4l2-ctl &> /dev/null; then
    echo "V4L2 Video Devices:"
    v4l2-ctl --list-devices || true
fi

# Make run scripts executable
chmod +x "$SCRIPT_DIR/gen-2-scrfd/run.sh" 2>/dev/null || true
chmod +x "$SCRIPT_DIR/gen-1-dlib/run.sh" 2>/dev/null || true

echo "======================================================================"
echo "🎉 Setup complete! To launch Gen-2 SCRFD on your Raspberry Pi 5:"
echo "   cd $SCRIPT_DIR/gen-2-scrfd"
echo "   ./run.sh"
echo "======================================================================"
