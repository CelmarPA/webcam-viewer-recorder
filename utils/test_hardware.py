# test_hardware.py

from devices import list_cameras, map_opencv_to_ffmpeg, get_camera_capabilities_real, list_microphones


def test_cameras():
    print("=== CÂMERAS DETECTADAS ===")
    cameras = list_cameras()
    if not cameras:
        print("Nenhuma câmera detectada.")
        return

    mapping = map_opencv_to_ffmpeg(cameras)
    for cam in cameras:
        index = mapping[cam]
        print(f"\n{cam} (índice {index}):")
        caps = get_camera_capabilities_real(cam, index)
        if not caps:
            print("  Nenhuma resolução suportada detectada.")
            continue
        for res, fps_list in caps.items():
            res_str = f"{res[0]}x{res[1]}"
            fps_str = ", ".join(str(f) for f in fps_list)
            print(f"  Resolução: {res_str} | FPS: {fps_str}")

def test_microphones():
    print("\n=== MICROFONES DETECTADOS ===")
    microphones = list_microphones()
    if not microphones:
        print("Nenhum microfone detectado.")
        return
    for i, mic in enumerate(microphones):
        print(f"  {i+1}. {mic}")

if __name__ == "__main__":
    test_cameras()
    test_microphones()
