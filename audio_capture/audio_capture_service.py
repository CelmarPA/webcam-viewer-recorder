# audio_capture/audio_capture_service.py

import sounddevice as sd
import soundfile as sf
import numpy as np
from typing import Optional

class AudioCaptureService:
    """
    Handles microphone capture and WAV recording.
    """

    def __init__(self):
        self.device_name: Optional[str] = None
        self._recording = False
        self._audio_data: list[np.ndarray] = []
        self._samplerate = 44100
        self._channels = 2
        self._stream: Optional[sd.InputStream] = None

    def start_recording(self) -> None:
        """Start capturing audio."""
        if self._recording:
            return
        self._audio_data = []
        self._recording = True
        self._stream = sd.InputStream(
            samplerate=self._samplerate,
            channels=self._channels,
            device=self.device_name,
            callback=self._callback
        )
        self._stream.start()

    def _callback(self, indata, frames, time, status) -> None:
        if self._recording:
            self._audio_data.append(indata.copy())

    def stop_recording(self, output_path: str) -> None:
        """Stop recording and write to WAV."""
        if not self._recording:
            return
        self._recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if self._audio_data:
            data = np.concatenate(self._audio_data, axis=0)
            sf.write(output_path, data, self._samplerate)
            self._audio_data = []
