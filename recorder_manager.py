from __future__ import annotations
import os
import subprocess
import threading
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable

import cv2
import numpy as np

from video_capture.video_capture_service import VideoCaptureService
from audio_capture.audio_capture_service import AudioCaptureService


class RecorderManager:
    """Handles recording video + audio via FFmpeg and live preview."""

    def __init__(
        self,
        video_service: VideoCaptureService,
        audio_service: AudioCaptureService,
        ffmpeg_path: str
    ) -> None:
        self.video_service = video_service
        self.audio_service = audio_service
        self.ffmpeg_path = ffmpeg_path

        self.brightness: float = 1.0
        self.contrast: float = 1.0
        self.saturation: float = 1.0

        self.recording: bool = False
        self._ffmpeg_proc: Optional[subprocess.Popen] = None
        self._video_file: Optional[str] = None
        self._audio_file: Optional[str] = None

    # ================= PREVIEW =================
    def start_preview(self, callback: Callable[[np.ndarray], None]) -> None:
        """Starts the camera preview loop, calling callback(frame)."""
        self.video_service.start_preview(
            lambda frame: self._apply_adjustments(frame, callback)
        )

    def _apply_adjustments(self, frame: np.ndarray, callback: Callable[[np.ndarray], None]) -> None:
        """
        Applies brightness, contrast, and saturation to the frame before sending to preview.
        """
        # Brilho / contraste
        beta = int((self.brightness - 1.0) * 50)
        adjusted = cv2.convertScaleAbs(frame, alpha=self.contrast, beta=beta)

        # Saturação
        hsv = cv2.cvtColor(adjusted, cv2.COLOR_BGR2HSV).astype("float32")
        hsv[..., 1] *= self.saturation  # Multiplica canal S
        hsv[..., 1] = np.clip(hsv[..., 1], 0, 255)
        adjusted = cv2.cvtColor(hsv.astype("uint8"), cv2.COLOR_HSV2BGR)

        callback(adjusted)

    # ================= RECORDING =================
    def start_recording(self, output_dir: str) -> str:
        """
        Starts recording video + audio directly in the output_dir.

        :param output_dir: Directory to save the recording.
        :return: Full path to the output file (final MKV).
        """
        if self.recording:
            raise RuntimeError("Already recording.")

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._video_file = str(Path(output_dir) / f"video_{timestamp}.mp4")
        self._audio_file = str(Path(output_dir) / f"audio_{timestamp}.wav")
        final_output = str(Path(output_dir) / f"recording_{timestamp}.mkv")

        w, h = self.video_service.resolution
        fps = self.video_service.fps_target

        # FFmpeg command: only video to file
        ffmpeg_cmd = [
            self.ffmpeg_path,
            "-y",
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{w}x{h}",
            "-r", str(fps),
            "-i", "pipe:0",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            self._video_file
        ]

        # Start FFmpeg process
        self._ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

        # Start audio recording
        self.audio_service.start_recording(file_path=self._audio_file)

        self.recording = True
        threading.Thread(target=self._record_loop, daemon=True).start()
        return final_output

    def _record_loop(self) -> None:
        """Continuously send frames to FFmpeg stdin with correct resolution and brightness/contrast."""
        import time

        w, h = self.video_service.resolution

        while self.recording and self._ffmpeg_proc and self._ffmpeg_proc.stdin:
            frame = self.video_service.get_frame()
            if frame is None:
                time.sleep(0.001)
                continue

            # Resize
            if (frame.shape[1], frame.shape[0]) != (w, h):
                frame = cv2.resize(frame, (w, h))

            # Ensure 3 channels
            if frame.shape[2] != 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

            # Apply brightness / contrast
            beta = int((self.brightness - 1.0) * 50)
            adjusted = cv2.convertScaleAbs(frame, alpha=self.contrast, beta=beta)

            # Apply saturation
            hsv = cv2.cvtColor(adjusted, cv2.COLOR_BGR2HSV).astype("float32")
            hsv[..., 1] *= self.saturation
            hsv[..., 1] = np.clip(hsv[..., 1], 0, 255)
            adjusted = cv2.cvtColor(hsv.astype("uint8"), cv2.COLOR_HSV2BGR)

            try:
                self._ffmpeg_proc.stdin.write(adjusted.tobytes())
            except (BrokenPipeError, ValueError):
                break

            time.sleep(1 / self.video_service.fps_target)

    def stop_recording(self) -> Optional[str]:
        """Stops recording and merges audio + video in the same folder."""
        if not self.recording:
            return None

        self.recording = False
        self.audio_service.stop_recording()

        if self._ffmpeg_proc:
            if self._ffmpeg_proc.stdin:
                self._ffmpeg_proc.stdin.close()
            self._ffmpeg_proc.wait()
            self._ffmpeg_proc = None

        if self._video_file and self._audio_file:
            final_output = self._video_file.replace("video_", "recording_").replace(".mp4", ".mkv")
            merge_cmd = [
                self.ffmpeg_path,
                "-y",
                "-i", self._video_file,
                "-i", self._audio_file,
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                final_output
            ]
            subprocess.run(merge_cmd, check=True)

            # Remove intermediate files
            Path(self._video_file).unlink(missing_ok=True)
            Path(self._audio_file).unlink(missing_ok=True)

            self._video_file = None
            self._audio_file = None
            return f"Recording saved: {final_output}"

        return "Recording saved."