# Hardware bring-up checklist

[Hardware overview](README.md)

Perform these checks when software work is complete. Leave results unchecked
until observed on the physical device. Store dates and outcomes in a local copy
of [the deployment record](deployment.example.md).

## 1. Assembly and OS

- [ ] Record exact part models, power ratings and all connections.
- [ ] Check cable seating, polarity, mounts, cooling clearance and insulation.
- [ ] Boot 64-bit Raspberry Pi OS and complete [software installation](../docs/raspberry-pi-setup.md).
- [ ] Verify camera discovery with `rpicam-hello --list-cameras`.
- [ ] Check a preview for correct colours, focus, lighting and framing.
- [ ] Verify cooler operation and stable power.
- [ ] If using an I2C OLED, enable I2C and validate the selected display with its
      controller-specific driver before connecting it to application events.

## 2. Functional integration

- [ ] Install the real face-recognition model; use `CAMERA_BACKEND=picamera2`.
- [ ] Configure the administrator token outside Git.
- [ ] Run `python scripts/run_tests.py`; these tests do not validate physical GPIO.
- [ ] Start the app; confirm `/health` is healthy and the correct camera is used.
- [ ] Confirm recognition operates without an open browser stream.
- [ ] Verify an empty scene produces no invented face or access grant.
- [ ] Verify enrollment rejects missing/multiple faces, poor quality and invalid credentials.
- [ ] Verify enrolled and unknown faces produce consistent overlay and audit decisions.
- [ ] Connect and test the actual actuator callback with a harmless load first.
- [ ] Confirm shared cooldown, denied decisions and actual action outcomes in CSV/logs.
- [ ] Confirm multiple stream viewers do not cause duplicate actions.
- [ ] Confirm model/camera failure is reported and cannot silently enable simulation.
- [ ] Verify driver failure, process shutdown, restart and power-loss behavior.
- [ ] If a real door is involved, verify independent release and the installed
      spoof-resistance mechanism; recognition tests alone do not validate either.

## 3. Measurements last

After functional checks pass, follow [the evaluation protocol](../docs/benchmarking.md):

- [ ] Use independent labelled captures and a gallery containing 50+ real identities.
- [ ] Separate threshold tuning from the final evaluation set; include unknown people.
- [ ] Record classification results and false accepts/rejects.
- [ ] Measure latency and sustained throughput on the Pi 5 with deployment settings.
- [ ] Distinguish camera/display FPS from completed recognition decisions per second.
- [ ] Record thermal/power conditions, model versions and the software revision.
- [ ] Update CV claims only from actual results; do not publish biometric datasets.
