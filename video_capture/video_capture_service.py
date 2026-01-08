import cv2
import time
import threading
import numpy as np
from typing import Callable, Optional, Tuple


class VideoCaptureService:
    """Handles webcam video capture with live preview and FPS measurement."""

    def __init__(self, camera_index: int = 0, width: int = 1280, height: int = 720, fps: int = 30):
        self.camera_index = camera_index
        self.resolution: Tuple[int, int] = (width, height)
        self.fps_target: int = fps

        self.previewing = False
        self.recording = False

        self._capture: Optional[cv2.VideoCapture] = None
        self._callback: Optional[Callable[[np.ndarray], None]] = None
        self._thread: Optional[threading.Thread] = None

        self.frames_captured = 0
        self.start_time = 0

        self._last_frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()

    def start_preview(self, callback: Callable[[np.ndarray], None]) -> None:
        """Starts camera preview with callback(frame)."""
        if self.previewing:
            return
        self._callback = callback
        self.previewing = True
        self.frames_captured = 0
        self.start_time = time.perf_counter()

        self._capture = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
        self._capture.set(cv2.CAP_PROP_FPS, self.fps_target)

        self._thread = threading.Thread(target=self._update_loop, daemon=True)
        self._thread.start()

    def _update_loop(self) -> None:
        last_print = time.perf_counter()
        while self.previewing and self._capture.isOpened():
            ret, frame = self._capture.read()
            if not ret:
                continue

            with self._lock:
                self._last_frame = frame.copy()

            self.frames_captured += 1
            if self._callback:
                self._callback(frame)

            now = time.perf_counter()
            if now - last_print >= 1.0:
                elapsed = now - self.start_time
                fps_real = self.frames_captured / elapsed if elapsed > 0 else 0
                print(f"[DEBUG] Frames captured: {self.frames_captured}, FPS real: {fps_real:.2f}")
                last_print = now

    def get_frame(self) -> Optional[np.ndarray]:
        """Returns last captured frame."""
        with self._lock:
            if self._last_frame is not None:
                return self._last_frame.copy()
            return None

    def stop_preview(self) -> None:
        self.previewing = False
        if self._thread:
            self._thread.join()
            self._thread = None
        if self._capture:
            self._capture.release()
            self._capture = None
