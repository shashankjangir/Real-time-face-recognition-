# Raspberry Pi setup

[Back to the project](../README.md)

## Hardware

See the [hardware folder](../hardware/README.md) for the complete parts list,
connection requirements, deployment template and bring-up checklist.

The maintainer has completed the hardware and access-control setup. For another
deployment, use a Raspberry Pi 5, a Camera Module 3 with the Pi 5 camera cable,
storage, stable lighting, suitable power, and active cooling. The official 27W
supply and Active Cooler are suitable starting choices.

Use 64-bit Raspberry Pi OS. Camera libraries should be installed through system
packages so Picamera2 and its libcamera bindings stay compatible.

## Installation

Run from the repository root:

```bash
sudo apt update
sudo apt install -y python3-venv python3-picamera2 python3-opencv python3-numpy python3-flask cmake build-essential python3-dev libopenblas-dev
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install onnxruntime
python -m pip install -r requirements-face-recognition.txt
rpicam-hello --list-cameras
```

The Pi setup uses system OpenCV, NumPy, and Flask rather than installing the
desktop `opencv-python` wheel over system camera packages. dlib installation can
require compilation; record the OS and package versions used for your deployment.

Configure enrollment as described in [the administrator guide](enrollment.md),
then launch:

```bash
export CAMERA_BACKEND=picamera2
python app.py
```

Open `http://<pi-address>:5000` on your local network. Explicit backend selection
fails if that camera cannot start. Auto mode tries Picamera2 and OpenCV only;
it never silently enters simulation. RGB888 capture arrays remain BGR for OpenCV.

## Deployment record

Document camera settings, power/cooling, relay or indicator wiring, access policy,
spoof-resistance behavior, and administrator configuration for your installation.
Keep credentials and personal face images out of the repository. Record test
results using [the evaluation protocol](benchmarking.md).

References: [Raspberry Pi 5](https://www.raspberrypi.com/products/raspberry-pi-5/)
and [Picamera2 installation guidance](https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf).
