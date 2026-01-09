# utils/devices.py

from __future__ import annotations

import json
import platform
import re
import subprocess
import threading
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import cv2

# ================================================
# PROJECT FOLDER CONFIGURATION
# ================================================

# FFmpeg path
if getattr(sys, "frozen", False):
    FFMPEG_PATH = Path(sys._MEIPASS) / "ffmpeg" / "ffmpeg.exe"
else:
    FFMPEG_PATH = Path.cwd() / "ffmpeg" / "ffmpeg.exe"

# User data folder (single BASE_DIR)
if platform.system() == "Windows":
    BASE_DIR = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "WebcamRecorder"
elif platform.system() == "Darwin":
    BASE_DIR = Path.home() / "Library/Application Support/WebcamRecorder"
else:
    BASE_DIR = Path.home() / ".webcam_recorder"

BASE_DIR.mkdir(parents=True, exist_ok=True)
DEVICES_JSON = BASE_DIR / "devices.json"
SETTINGS_JSON = BASE_DIR / "settings.json"

# ==================================================
# CACHE HELPERS
# ==================================================

def load_devices() -> dict:
    """
    Load devices cache from devices.json.

    :return: Cached devices dictionary
    :rtype: dict
    """
    if DEVICES_JSON.exists():
        try:
            return json.loads(DEVICES_JSON.read_text(encoding="utf-8"))
        except Exception:
            return {"cameras": [], "microphones": []}
    return {"cameras": [], "microphones": []}


def save_devices(devices: dict) -> None:
    """
    Save devices cache to devices.json.

    :param devices: Devices dictionary to persist
    :type devices: dict
    """
    try:
        DEVICES_JSON.write_text(
            json.dumps(devices, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


# ==================================================
# CAMERAS
# ==================================================

def detect_cameras(max_test: int = 10) -> List[dict]:
    """
    Detect physical cameras and their supported resolutions.

    :param max_test: Maximum camera indexes to probe
    :type max_test: int
    :return: List of detected cameras with resolutions
    :rtype: List[dict]
    """
    common_resolutions: List[Tuple[int, int]] = [
        (1920, 1080),
        (1280, 720),
        (1024, 576),
        (800, 600),
        (640, 480),
        (320, 240),
    ]

    cameras: List[dict] = []

    for index in range(max_test):
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW if platform.system() == "Windows" else 0)
        if not cap.isOpened():
            continue

        resolutions: List[str] = []

        for width, height in common_resolutions:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

            actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            if (actual_width, actual_height) == (width, height):
                resolutions.append(f"{width}x{height}")

        # 🔹 If no resolution is detected, add at least 1280x720
        if not resolutions:
            resolutions = ["1280x720"]

        cameras.append(
            {
                "name": f"Camera {index}",
                "index": index,
                "resolutions": resolutions,
            }
        )

        cap.release()

    return cameras


# ==================================================
# MICROPHONES
# ==================================================

def detect_microphones() -> List[dict]:
    """
    Detect active microphones using FFmpeg DirectShow.

    :return: List of detected microphones
    :rtype: List[dict]
    """
    if not FFMPEG_PATH.exists():
        return []

    result = subprocess.run(
        [str(FFMPEG_PATH), "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
        capture_output=True,
        text=True,
    )

    microphones: List[dict] = []

    for line in result.stderr.splitlines():
        match = re.search(r'"(.+)" \(audio\)', line)
        if match:
            microphones.append({"name": match.group(1)})

    return microphones


# ==================================================
# BACKGROUND UPDATE
# ==================================================

def update_devices_background(max_test: int = 10) -> None:
    """
    Update devices.json in background without blocking the application.

    :param max_test: Maximum camera indexes to probe
    :type max_test: int
    """
    devices = load_devices()

    cached_camera_names = {c["name"] for c in devices.get("cameras", [])}
    new_cameras = [
        cam for cam in detect_cameras(max_test)
        if cam["name"] not in cached_camera_names
    ]

    if new_cameras:
        devices["cameras"].extend(new_cameras)

    cached_microphone_names = {m["name"] for m in devices.get("microphones", [])}
    new_microphones = [
        mic for mic in detect_microphones()
        if mic["name"] not in cached_microphone_names
    ]

    if new_microphones:
        devices["microphones"].extend(new_microphones)

    save_devices(devices)


# ==================================================
# PUBLIC API
# ==================================================

def get_cameras(max_test: int = 10) -> List[dict]:
    """
    Return cached cameras immediately and refresh devices.json in background.

    :param max_test: Maximum camera indexes to probe
    :type max_test: int
    :return: Cached camera list
    :rtype: List[dict]
    """
    devices = load_devices()
    threading.Thread(
        target=update_devices_background,
        args=(max_test,),
        daemon=True,
    ).start()

    return devices.get("cameras", [])


def get_microphones() -> List[dict]:
    """
    Return cached microphones immediately and refresh devices.json in background.

    :return: Cached microphone list
    :rtype: List[dict]
    """
    devices = load_devices()
    threading.Thread(
        target=update_devices_background,
        daemon=True,
    ).start()

    return devices.get("microphones", [])
