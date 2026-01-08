from typing import List, Dict, Tuple
import platform
import cv2
import sounddevice as sd


def list_cameras(max_test: int = 10) -> List[str]:
    cameras = []
    for i in range(max_test):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW if platform.system() == "Windows" else 0)
        if cap.isOpened():
            cameras.append(f"Camera {i}")
            cap.release()
    return cameras


def map_opencv_to_ffmpeg(cameras: List[str]) -> Dict[str, int]:
    mapping = {}
    for cam in cameras:
        index = int(cam.replace("Camera ", ""))
        mapping[cam] = index
    return mapping


def get_camera_capabilities_real(camera_name: str, camera_index: int) -> Dict[Tuple[int, int], List[int]]:
    common_resolutions = [
        (1920, 1080), (1280, 720), (1024, 576),
        (800, 600), (640, 480), (320, 240)
    ]
    common_fps = [30, 60, 120]

    capabilities: Dict[Tuple[int, int], List[int]] = {}
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW if platform.system() == "Windows" else 0)
    if not cap.isOpened():
        return capabilities

    for w, h in common_resolutions:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if (actual_w, actual_h) == (w, h):
            supported_fps = []
            for fps in common_fps:
                cap.set(cv2.CAP_PROP_FPS, fps)
                actual_fps = int(cap.get(cv2.CAP_PROP_FPS))
                if actual_fps == fps:
                    supported_fps.append(fps)
            capabilities[(w, h)] = supported_fps or [30]

    cap.release()
    return capabilities


def list_microphones() -> List[str]:
    devices = sd.query_devices()
    return [d['name'] for d in devices if d['max_input_channels'] > 0]
