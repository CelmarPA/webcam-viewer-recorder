# video_capture/video_capture_service.py

from __future__ import annotations

import cv2
import time
import threading
import numpy as np
from typing import Callable, Optional, Tuple


class VideoCaptureService:
    """
    Handles webcam video capture with live preview, frame buffering,
    and real-time FPS measurement.
    """

    def __init__(
        self,
        camera_index: int = 0,
        width: int = 1280,
        height: int = 720,
        fps: int = 30
    ) -> None:
        """
        Initialize the video capture service.

        :param camera_index: Index of the camera device
        :type camera_index: int
        :param width: Target frame width
        :type width: int
        :param height: Target frame height
        :type height: int
        :param fps: Target frames per second
        :type fps: int
        """
        self.camera_index: int = camera_index
        self.resolution: Tuple[int, int] = (width, height)
        self.fps_target: int = fps

        self.previewing: bool = False
        self.recording: bool = False

        self._capture: Optional[cv2.VideoCapture] = None
        self._callback: Optional[Callable[[np.ndarray], None]] = None
        self._thread: Optional[threading.Thread] = None

        self.frames_captured: int = 0
        self.start_time: float = 0.0

        self._last_frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()

    def start_preview(self, callback: Callable[[np.ndarray], None]) -> None:
        """
        Start the live camera preview.

        :param callback: Function called for each captured frame
        :type callback: Callable[[np.ndarray], None]
        """
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
        """
        Internal loop responsible for grabbing frames from the camera
        and forwarding them to the preview callback.
        """
        while self.previewing and self._capture is not None and self._capture.isOpened():
            ret, frame = self._capture.read()
            if not ret:
                continue

            with self._lock:
                self._last_frame = frame.copy()

            self.frames_captured += 1

            if self._callback:
                self._callback(frame)

    def get_frame(self) -> Optional[np.ndarray]:
        """
        Return the most recently captured frame.

        :return: Last captured frame or None if unavailable
        :rtype: Optional[np.ndarray]
        """
        with self._lock:
            if self._last_frame is not None:
                return self._last_frame.copy()
            return None

    def stop_preview(self) -> None:
        """
        Stop the live preview and release camera resources.
        """
        self.previewing = False

        if self._thread:
            self._thread.join()
            self._thread = None

        if self._capture:
            self._capture.release()
            self._capture = None
