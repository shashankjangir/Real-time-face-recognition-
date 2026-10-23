#!/usr/bin/env bash
# Run Real-Time Face Recognition (Generation 1 - dlib) on Raspberry Pi 5
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Source virtual environment if present
if [ -d "$SCRIPT_DIR/.venv" ]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
elif [ -d "$HOME/face-access-env" ]; then
    source "$HOME/face-access-env/bin/activate"
fi

export CAMERA_BACKEND="${CAMERA_BACKEND:-auto}"
export CAMERA_INDEX="${CAMERA_INDEX:-0}"
export PYTHONIOENCODING="utf-8"

# Set enrollment password (dashboard and video streams require no login password)
if [ -z "$ENROLLMENT_PASSWORD" ] && [ -z "$ADMIN_ENROLLMENT_TOKEN" ]; then
    export ENROLLMENT_PASSWORD="123456789"
    export ADMIN_ENROLLMENT_TOKEN="$ENROLLMENT_PASSWORD"
    echo "=========================================================="
    echo "Dashboard access: Open (no login password required)"
    echo "Enrollment password set to: $ENROLLMENT_PASSWORD"
    echo "=========================================================="
fi

echo ">>> Starting Gen-1 dlib on Raspberry Pi 5..."
python3 app.py
