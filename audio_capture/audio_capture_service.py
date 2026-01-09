# audio_capture/audio_capture_service.py

from __future__ import annotations

import threading
import wave
from pathlib import Path
from typing import Optional, List

import numpy as np
import sounddevice as sd


class AudioCaptureService:
    """
    Handles audio capture using sounddevice and recording to WAV files.
    """

    def __init__(
        self,
        channels: int = 2,
        samplerate: int = 44100,
        dtype: str = "float32",
    ) -> None:
        """
        Initialize the audio capture service.

        :param channels: Number of audio channels (e.g., 2 for stereo)
        :type channels: int
        :param samplerate: Audio sample rate in Hz
        :type samplerate: int
        :param dtype: Audio data type (e.g., 'float32', 'int16')
        :type dtype: str
        """
        self.channels: int = channels
        self.samplerate: int = samplerate
        self.dtype: str = dtype

        self.device_name: Optional[str] = None

        self.recording: bool = False
        self._file_path: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        self._audio_frames: List[np.ndarray] = []

    def start_recording(self, file_path: str) -> None:
        """
        Start recording audio into a WAV file.

        :param file_path: Absolute or relative path to the output WAV file
        :type file_path: str
        :raises RuntimeError: If recording is already active
        """
        if self.recording:
            raise RuntimeError("Audio already recording.")

        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

        self._file_path = file_path
        self._audio_frames.clear()
        self.recording = True

        self._thread = threading.Thread(
            target=self._record_loop,
            daemon=True,
        )
        self._thread.start()

    def _record_loop(self) -> None:
        """
        Internal recording loop that continuously captures audio frames.
        """

        def callback(
            indata: np.ndarray,
            frames: int,
            time_info,
            status,
        ) -> None:
            if self.recording:
                self._audio_frames.append(indata.copy())

        device_index: Optional[int] = None

        if self.device_name:
            for index, device in enumerate(sd.query_devices()):
                if device["name"] == self.device_name:
                    device_index = index
                    break

        with sd.InputStream(
            device=device_index,
            channels=self.channels,
            samplerate=self.samplerate,
            dtype=self.dtype,
            callback=callback,
        ):
            while self.recording:
                sd.sleep(100)

    def stop_recording(self) -> None:
        """
        Stop recording and write the captured audio to the WAV file.
        """
        if not self.recording:
            return

        self.recording = False

        if self._thread:
            self._thread.join()
            self._thread = None

        if self._file_path and self._audio_frames:
            audio_data: np.ndarray = np.concatenate(self._audio_frames, axis=0)

            if self.dtype == "float32":
                audio_data = np.int16(audio_data * 32767)

            with wave.open(self._file_path, "wb") as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(2)  # int16
                wav_file.setframerate(self.samplerate)
                wav_file.writeframes(audio_data.tobytes())

        self._audio_frames.clear()
        self._file_path = None
