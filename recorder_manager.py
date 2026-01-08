# recorder_manager.py

from __future__ import annotations
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from video_capture.video_capture_service import VideoCaptureService
from audio_capture.audio_capture_service import AudioCaptureService


class RecorderManager:
    """
    Handles video and audio recording, preview, and final merge using FFmpeg.

    Flexible: can receive existing services or create its own internally.
    """

    def __init__(
        self,
        video_service: Optional[VideoCaptureService] = None,
        audio_service: Optional[AudioCaptureService] = None,
        camera_index: int = 0,
        audio_device: Optional[str] = None,
        ffmpeg_path: Optional[str] = None
    ) -> None:
        # Use provided services or create internally
        self.video_service = video_service or VideoCaptureService(camera_index)
        self.audio_service = audio_service or AudioCaptureService()
        if audio_device:
            self.audio_service.device_name = audio_device

        self.ffmpeg_path = ffmpeg_path or "ffmpeg"
        self.recording = False

        self.temp_video: Optional[str] = None
        self.temp_audio: Optional[str] = None

        self._preview_callback: Optional[Callable] = None

    # ================= PREVIEW =================
    def start_preview(self, callback: Callable) -> None:
        """Start live video preview with callback for frames."""
        self._preview_callback = callback
        # verifica se start_preview existe, senão usa start
        if hasattr(self.video_service, "start_preview"):
            self.video_service.start_preview(callback)
        elif hasattr(self.video_service, "start"):
            self.video_service.start(callback)
        else:
            raise AttributeError("O VideoCaptureService passado não possui método de preview.")

    # ================= RECORDING =================
    def start_recording(self, output_dir: Optional[str] = None) -> None:
        """Start recording video + audio to temporary files."""
        if self.recording:
            return

        self.recording = True
        output_dir = output_dir or os.getcwd()
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.temp_video = os.path.join(output_dir, f"temp_{timestamp}.avi")
        self.temp_audio = os.path.join(output_dir, f"temp_{timestamp}.wav")

        self.video_service.start_recording(self.temp_video)
        self.audio_service.start_recording()

    def stop_recording(self) -> str:
        """Stop recording, merge video+audio via FFmpeg, return final MP4 path."""
        if not self.recording:
            return ""

        self.recording = False
        self.video_service.stop_recording()
        self.audio_service.stop_recording(self.temp_audio)

        output_dir = os.path.dirname(self.temp_video)
        final_path = os.path.join(output_dir, f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")

        subprocess.run(
            [
                self.ffmpeg_path,
                "-y",
                "-i", self.temp_video,
                "-i", self.temp_audio,
                "-c:v", "libx264",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                "-async", "1",
                final_path,
            ],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )

        # Cleanup
        try:
            os.remove(self.temp_video)
            os.remove(self.temp_audio)
        except Exception:
            pass

        self.temp_video = None
        self.temp_audio = None
        return final_path
