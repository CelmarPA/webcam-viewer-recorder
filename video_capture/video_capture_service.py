# video_capture/video_capture_service.py

import cv2
import time
import threading
import numpy as np
from typing import Callable, Optional

class VideoCaptureService:
    """
    Handles webcam capture, preview, and video recording using OpenCV.
    """

    def __init__(self, camera_index: int = 0) -> None:
        self.camera_index = camera_index
        self.resolution = (1280, 720)
        self.fps = 30

        self.previewing = False
        self._recording = False
        self._capture: Optional[cv2.VideoCapture] = None
        self._writer: Optional[cv2.VideoWriter] = None
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[np.ndarray], None]] = None

    # ---------- PREVIEW ----------
    def start_preview(self, callback: Callable[[np.ndarray], None]) -> None:
        """Start live preview."""
        if self.previewing:
            return
        self._callback = callback
        self.previewing = True
        self._capture = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
        self._capture.set(cv2.CAP_PROP_FPS, self.fps)

        self._thread = threading.Thread(target=self._update_loop, daemon=True)
        self._thread.start()

    def _update_loop(self) -> None:
        last_time = time.time()
        frame_interval = 1 / self.fps

        while self.previewing and self._capture.isOpened():
            ret, frame = self._capture.read()
            if not ret:
                continue

            # envia frame para preview
            if self._callback:
                self._callback(frame)

            # grava respeitando FPS configurado
            if self._recording and self._writer:
                now = time.time()
                if now - last_time >= frame_interval:
                    self._writer.write(frame)
                    last_time = now

    def stop_preview(self) -> None:
        self.previewing = False
        if self._capture:
            self._capture.release()
            self._capture = None

    # ---------- RECORDING ----------
    def start_recording(self, file_path: str) -> None:
        """Start recording video to file."""
        if self._recording:
            return
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        self._writer = cv2.VideoWriter(file_path, fourcc, self.fps, self.resolution)
        if not self._writer.isOpened():
            raise RuntimeError(f"Não foi possível criar arquivo de vídeo: {file_path}")
        self._recording = True

    def stop_recording(self) -> None:
        """Stop recording video."""
        self._recording = False
        if self._writer:
            self._writer.release()
            self._writer = None
