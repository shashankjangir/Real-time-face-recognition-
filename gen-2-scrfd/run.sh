#!/usr/bin/env bash
# Run Real-Time Face Recognition (Generation 2 - SCRFD) on Raspberry Pi 5
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

# Prompt for admin credentials before server startup
if [ -z "$ADMIN_ENROLLMENT_TOKEN" ]; then
    echo "=========================================================="
    read -p "Enter admin username: " USERNAME_INPUT
    if [ "$USERNAME_INPUT" = "shashank" ]; then
        export ADMIN_ENROLLMENT_TOKEN="123456789"
        echo "Welcome Shashank (Admin). Password set to: 123456789"
    else
        read -s -p "Enter token password: " PASS_INPUT
        echo ""
        export ADMIN_ENROLLMENT_TOKEN="$PASS_INPUT"
    fi
    echo "=========================================================="
fi

echo ">>> Starting Gen-2 SCRFD on Raspberry Pi 5..."
python3 app.py
