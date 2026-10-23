"""
Camera Acquisition Module for Raspberry Pi 5 and Edge Devices
Multi-threaded frame acquisition supporting Picamera2 (IMX708), OpenCV VideoCapture, and explicit synthetic development mode.
"""

import threading
import time
import logging
from typing import Tuple, Optional
import numpy as np
import cv2

try:
    from . import config
except (ImportError, ValueError):
    import config

logger = logging.getLogger(__name__)


class CameraBackend:
    """Base interface for camera hardware backends."""
    def start(self): pass
    def read(self) -> Tuple[bool, Optional[np.ndarray]]: pass
    def stop(self): pass


class Picamera2Backend(CameraBackend):
    """Raspberry Pi Camera Module 3 (IMX708) driver using Picamera2."""
    def __init__(self, width: int = config.CAMERA_WIDTH, height: int = config.CAMERA_HEIGHT, fps: int = config.CAMERA_FPS):
        self.width = width
        self.height = height
        self.fps = fps
        self.picam2 = None
        self.autofocus_enabled = False

    def start(self):
        try:
            from picamera2 import Picamera2
            self.picam2 = Picamera2()
            cam_config = self.picam2.create_video_configuration(
                main={"format": "RGB888", "size": (self.width, self.height)},
                controls={"FrameRate": self.fps},
                buffer_count=6
            )
            self.picam2.configure(cam_config)
            # Camera Module 3 supports AF; older fixed-focus modules do not.
            self.autofocus_enabled = 'AfMode' in self.picam2.camera_controls
            # Explicitly request automatic exposure and white balance when supported.
            automatic = {key: True for key in ('AeEnable', 'AwbEnable')
                         if key in self.picam2.camera_controls}
            if automatic:
                self.picam2.set_controls(automatic)
            self.picam2.start()
            if self.autofocus_enabled:
                from libcamera import controls
                # Trigger autofocus sweep once camera stream is active so PDAF lens motor focuses
                af_ctrls = {'AfMode': controls.AfModeEnum.Auto}
                if hasattr(controls, 'AfTriggerEnum'):
                    af_ctrls['AfTrigger'] = controls.AfTriggerEnum.Start
                try:
                    self.picam2.set_controls(af_ctrls)
                except Exception as e:
                    logger.debug("AfTrigger initial sweep notice: %s", e)
            logger.info("Picamera2 (IMX708) started successfully.")
        except Exception as e:
            logger.error(f"Failed to start Picamera2 backend: {e}")
            raise

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self.picam2:
            return False, None
        try:
            arr = self.picam2.capture_array()
            if arr is None:
                return False, None
            if hasattr(arr, 'shape') and len(arr.shape) >= 2:
                if arr.shape[1] != self.width or arr.shape[0] != self.height:
                    self.width, self.height = int(arr.shape[1]), int(arr.shape[0])
            # Detach from libcamera circular DMA buffer pool via independent heap copy
            # to eliminate multi-threaded glibc memory corruption across workers.
            return True, np.ascontiguousarray(arr).copy()
        except Exception as e:
            logger.error(f"Picamera2 capture error: {e}")
            return False, None

    def stop(self):
        if self.picam2:
            try:
                self.picam2.stop()
                self.picam2.close()
            except Exception:
                pass
            self.picam2 = None


class OpenCVBackend(CameraBackend):
    """Standard OpenCV VideoCapture backend (USB webcams, V4L2 devices, RTSP)."""
    def __init__(self, index: int = config.CAMERA_INDEX, width: int = config.CAMERA_WIDTH,
                 height: int = config.CAMERA_HEIGHT, fps: int = config.CAMERA_FPS):
        self.index = index
        self.width = width
        self.height = height
        self.fps = fps
        self.cap = None

    def start(self):
        self.cap = cv2.VideoCapture(self.index)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera index {self.index}")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        act_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        act_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if act_w > 0 and act_h > 0:
            self.width, self.height = act_w, act_h
        logger.info(f"OpenCV VideoCapture({self.index}) opened at {self.width}x{self.height}.")

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self.cap or not self.cap.isOpened():
            return False, None
        ret, frame = self.cap.read()
        if ret and frame is not None and hasattr(frame, 'shape') and len(frame.shape) >= 2:
            if frame.shape[1] != self.width or frame.shape[0] != self.height:
                self.width, self.height = int(frame.shape[1]), int(frame.shape[0])
        return ret, frame

    def stop(self):
        if self.cap:
            self.cap.release()
            self.cap = None


class SyntheticBackend(CameraBackend):
    """
    Synthetic frame generator for testing, development, and benchmarking.
    Generates realistic 30 FPS video with simulated faces, illumination shifts, and timestamp overlays.
    """
    def __init__(self, width: int = config.CAMERA_WIDTH, height: int = config.CAMERA_HEIGHT, fps: int = config.CAMERA_FPS):
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_idx = 0
        self.running = False
        self.last_time = time.time()

    def start(self):
        self.running = True
        logger.info("Synthetic Camera backend activated (Simulation/Dev mode).")

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self.running:
            return False, None

        # Pace to target FPS
        now = time.time()
        elapsed = now - self.last_time
        target_period = 1.0 / self.fps
        if elapsed < target_period:
            time.sleep(target_period - elapsed)
        self.last_time = time.time()
        self.frame_idx += 1

        # Render simulated laboratory / access gate camera frame
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        # Background gradient (dark modern slate)
        for y in range(self.height):
            v = int(24 + (y / self.height) * 35)
            frame[y, :] = (v + 5, v, v - 5)

        # Draw simulated security doorway frame
        cv2.rectangle(frame, (80, 40), (self.width - 80, self.height), (45, 45, 50), -1)
        cv2.rectangle(frame, (80, 40), (self.width - 80, self.height), (80, 80, 85), 2)

        # Simulated person motion (oscillating face position)
        cx = int(self.width / 2 + 70 * np.sin(self.frame_idx * 0.05))
        cy = int(self.height / 2 - 30 + 15 * np.cos(self.frame_idx * 0.04))

        # Face oval
        cv2.ellipse(frame, (cx, cy), (48, 64), 0, 0, 360, (185, 205, 235), -1)
        # Eyes
        cv2.circle(frame, (cx - 16, cy - 12), 5, (70, 70, 70), -1)
        cv2.circle(frame, (cx + 16, cy - 12), 5, (70, 70, 70), -1)
        # Mouth
        cv2.ellipse(frame, (cx, cy + 24), (14, 6), 0, 0, 180, (60, 60, 90), 2)

        # Status text
        ts_str = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, f"CAM01: ACCESS GATE [30 FPS]  {ts_str}", (20, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 220, 255), 1, cv2.LINE_AA)

        return True, frame

    def stop(self):
        self.running = False


class CameraManager:
    """
    Threaded Camera Manager that decouples frame acquisition from downstream processing.
    Captures frames in a background thread; actual throughput is hardware dependent.
    """

    def __init__(self, backend_type: str = None):
        self.backend_type = backend_type or config.CAMERA_BACKEND
        self.backend: CameraBackend = self._create_backend()

        self.latest_frame: Optional[np.ndarray] = None
        self.frame_lock = threading.Lock()
        self.running = False
        self.thread: Optional[threading.Thread] = None

        self.frame_count = 0
        self.delivered_at = None
        self.fps = 0.0
        self._fps_tracker = []
        self.last_error = None

    def _create_backend(self) -> CameraBackend:
        """Instantiate backend without starting it; start() opens the device."""
        choices = {'picamera2': Picamera2Backend, 'opencv': OpenCVBackend, 'synthetic': SyntheticBackend}
        if self.backend_type not in (*choices, 'auto'):
            raise RuntimeError(f"Unknown camera backend: {self.backend_type}")
        if self.backend_type == 'auto':
            # Probe in order; first that starts wins
            for name in ('picamera2', 'opencv'):
                backend = choices[name]()
                try:
                    backend.start()
                    return backend
                except Exception:
                    backend.stop()
            raise RuntimeError("Camera auto-detection failed: no working backend")
        return choices[self.backend_type]()

    def start(self):
        """Start camera backend and background acquisition thread."""
        if self.running:
            return
        # Start the device now (not in __init__) so the camera isn't held open before we're ready.
        if self.backend_type != 'auto':  # auto already started in _create_backend
            self.backend.start()
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, name="CameraAcquisitionThread", daemon=True)
        self.thread.start()
        logger.info("Threaded frame acquisition started.")

    def _capture_loop(self):
        last_t = time.time()
        while self.running:
            time.sleep(0.001)  # prevent 100% CPU spin when backend.read() returns instantly
            try:
                success, frame = self.backend.read()
                if not success or frame is None:
                    raise RuntimeError("Camera returned no frame")
            except Exception as exc:
                with self.frame_lock:
                    self.last_error = str(exc)
                    self.latest_frame = None
                self.running = False
                logger.error("Camera capture failed: %s", exc)
                break
            if success and frame is not None:
                now = time.time()
                dt = now - last_t
                last_t = now
                with self.frame_lock:
                    self.delivered_at = time.monotonic()
                    self.latest_frame = frame
                    self.frame_count += 1
                    if dt > 0:
                        self._fps_tracker.append(1.0 / dt)
                        if len(self._fps_tracker) > 30:
                            self._fps_tracker.pop(0)
                        self.fps = sum(self._fps_tracker) / len(self._fps_tracker)
            else:
                time.sleep(0.01)

    def get_frame(self) -> Optional[np.ndarray]:
        """Thread-safe instant read of latest captured frame (<0.1 ms latency)."""
        with self.frame_lock:
            if self.last_error:
                raise RuntimeError(self.last_error)
            return self.latest_frame.copy() if self.latest_frame is not None else None

    def get_snapshot(self, timestamped=False):
        with self.frame_lock:
            if self.last_error:
                raise RuntimeError(self.last_error)
            snapshot = (self.latest_frame.copy() if self.latest_frame is not None else None, self.frame_count)
            return (*snapshot, self.delivered_at) if timestamped else snapshot

    def get_resolution(self) -> Tuple[int, int]:
        with self.frame_lock:
            if self.latest_frame is not None and hasattr(self.latest_frame, 'shape') and len(self.latest_frame.shape) >= 2:
                return int(self.latest_frame.shape[1]), int(self.latest_frame.shape[0])
        return getattr(self.backend, 'width', config.CAMERA_WIDTH), getattr(self.backend, 'height', config.CAMERA_HEIGHT)

    def get_fps(self) -> float:
        with self.frame_lock:
            return round(self.fps, 1)

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        self.backend.stop()
        logger.info("Camera acquisition stopped.")
