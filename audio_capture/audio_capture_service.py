from __future__ import annotations
import wave
import threading
from pathlib import Path
from typing import Optional
import numpy as np
import sounddevice as sd


class AudioCaptureService:
    """Handles audio capture using sounddevice and recording to WAV."""

    def __init__(self, channels: int = 2, samplerate: int = 44100, dtype: str = 'float32') -> None:
        """
        :param channels: Number of audio channels (default 2 for stereo)
        :param samplerate: Sample rate in Hz
        :param dtype: Data type ('float32', 'int16', etc.)
        """
        self.channels = channels
        self.samplerate = samplerate
        self.dtype = dtype
        self.device_name: Optional[str] = None

        self.recording: bool = False
        self._file_path: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        self._audio_frames: list[np.ndarray] = []

    def start_recording(self, file_path: str) -> None:
        """Starts recording audio to WAV file."""
        if self.recording:
            raise RuntimeError("Audio already recording.")

        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        self._file_path = file_path
        self._audio_frames = []
        self.recording = True

        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()

    def _record_loop(self) -> None:
        """Internal loop to capture audio frames continuously."""

        def callback(indata, frames, time_info, status):
            if self.recording:
                self._audio_frames.append(indata.copy())

        device = None
        if self.device_name:
            devices = sd.query_devices()
            for i, d in enumerate(devices):
                if d['name'] == self.device_name:
                    device = i
                    break

        with sd.InputStream(
            device=device,
            channels=self.channels,
            samplerate=self.samplerate,
            dtype=self.dtype,
            callback=callback
        ):
            while self.recording:
                sd.sleep(100)

    def stop_recording(self) -> None:
        """Stops recording and writes WAV file."""
        if not self.recording:
            return

        self.recording = False
        if self._thread:
            self._thread.join()
            self._thread = None

        if self._file_path and self._audio_frames:
            audio_data = np.concatenate(self._audio_frames, axis=0)

            if self.dtype == 'float32':
                audio_data = np.int16(audio_data * 32767)

            with wave.open(self._file_path, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)  # int16
                wf.setframerate(self.samplerate)
                wf.writeframes(audio_data.tobytes())

        self._audio_frames = []
        self._file_path = None
