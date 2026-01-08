# app_window.py

from __future__ import annotations
import os
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime
import subprocess
import numpy as np
import cv2
from typing import Optional
from PIL import Image, ImageTk

from recorder_manager import RecorderManager
from audio_capture.audio_capture_service import AudioCaptureService
from video_capture.video_capture_service import VideoCaptureService
from utils.settings_manager import SettingsManager
from utils.devices import list_cameras, list_microphones, map_opencv_to_ffmpeg, get_camera_capabilities_real


class AppWindow:
    """
    Main application window for Webcam Recorder.

    Handles UI, video preview, recording controls, settings management,
    and integrates RecorderManager to handle video + audio capture and merge.
    """

    def __init__(self, root: tk.Tk) -> None:
        """
        Initialize the main window, load cameras, microphones, and services.

        Loads user settings (brightness, contrast, last folder), builds UI,
        initializes RecorderManager, and starts live preview.

        :param root: Root Tkinter window.
        """
        self.root = root
        self.root.title("Webcam Recorder")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.minsize(900, 700)

        # ---------- SETTINGS MANAGER ----------
        self.settings = SettingsManager()

        # ---------- PATHS ----------
        self.ffmpeg_path = os.path.join(os.getcwd(), "ffmpeg", "ffmpeg.exe")

        print(os.path.exists(self.ffmpeg_path))
        if not os.path.exists(self.ffmpeg_path):
            raise FileNotFoundError("FFmpeg executable not found.")

        # Última pasta de saída ou padrão
        last_dir = self.settings.get("last_output_dir")
        videos_dir = Path(last_dir or Path.home() / "Videos")
        self.output_dir: str = str(videos_dir if videos_dir.exists() else Path.home())

        # ---------- CAMERA/MIC/RESOLUTION/FPS ----------
        # Câmeras
        self.cameras: list[str] = list_cameras()
        if not self.cameras:
            messagebox.showerror("Erro", "Nenhuma câmera detectada.")
            self.root.destroy()
            return
        self.camera_index_map: dict[str, int] = map_opencv_to_ffmpeg(self.cameras)
        self.selected_camera_name: str = self.settings.get("camera", self.cameras[0])
        if self.selected_camera_name not in self.camera_index_map:
            self.selected_camera_name = self.cameras[0]
        self.selected_camera_index: int = self.camera_index_map[self.selected_camera_name]

        # Microfones
        self.microphones: list[str] = list_microphones()
        if not self.microphones:
            messagebox.showerror("Erro", "Nenhum microfone detectado.")
            self.root.destroy()
            return
        self.selected_microphone: str = self.settings.get("microphone", self.microphones[0])
        if self.selected_microphone not in self.microphones:
            self.selected_microphone = self.microphones[0]

        # ---------- PREVIEW ADJUSTMENTS ----------
        self.brightness_var = tk.DoubleVar(value=self.settings.get("brightness", 1.0))
        self.contrast_var = tk.DoubleVar(value=self.settings.get("contrast", 1.0))

        # ---------- SERVICES ----------
        self.audio_service = AudioCaptureService()
        self.audio_service.device_name = self.selected_microphone

        self.video_service = VideoCaptureService(self.selected_camera_index)

        # Resolution/FPS default
        self.camera_caps = get_camera_capabilities_real(self.selected_camera_name, self.selected_camera_index)
        if self.camera_caps:
            res_list = sorted(self.camera_caps.keys(), reverse=True)
            self.selected_resolution = self.settings.get("resolution", f"{res_list[0][0]}x{res_list[0][1]}")
            fps_list = self.camera_caps.get(tuple(map(int, self.selected_resolution.split("x"))), [30])
            self.selected_fps = self.settings.get("fps", fps_list[0])
        else:
            self.selected_resolution = "1280x720"
            self.selected_fps = 30

        self.video_service.resolution = tuple(map(int, self.selected_resolution.split("x")))
        self.video_service.fps = self.selected_fps

        # ---------- RECORDER MANAGER ----------
        ffmpeg_path = os.path.join(os.getcwd(), "ffmpeg", "ffmpeg.exe")
        self.recorder = RecorderManager(self.video_service, self.audio_service, ffmpeg_path)

        # ---------- STATE ----------
        self.temp_video: Optional[str] = None
        self.temp_audio: Optional[str] = None
        self.tk_image: Optional[ImageTk.PhotoImage] = None

        # ---------- BUILD UI ----------
        self._build_ui()

        # Start preview
        self.start_preview()

    # ================= SETTINGS =================
    def _save_settings(self) -> None:
        """Save brightness, contrast, last output folder, camera, mic, resolution, FPS."""
        data = {
            "brightness": self.brightness_var.get(),
            "contrast": self.contrast_var.get(),
            "last_output_dir": self.output_dir,
            "camera": self.selected_camera_name,
            "microphone": self.selected_microphone,
            "resolution": self.selected_resolution,
            "fps": self.selected_fps
        }
        self.settings.save(data)

    # ================= UI =================
    def _build_ui(self) -> None:
        """
        Build main UI: video preview, controls, settings, preview adjustments.
        """
        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True)

        # VIDEO PREVIEW
        self.video_label = ttk.Label(main)
        self.video_label.pack(expand=True)

        # CONTROLS
        controls = ttk.Frame(main)
        controls.pack(pady=8)

        self.btn_start = ttk.Button(controls, text="▶ Start", command=self.start_record)
        self.btn_start.pack(side="left", padx=6)
        self.btn_stop = ttk.Button(controls, text="■ Stop", command=self.stop_record, state="disabled")
        self.btn_stop.pack(side="left", padx=6)
        ttk.Button(controls, text="📂 Open Folder", command=self.open_folder).pack(side="left", padx=6)
        ttk.Button(controls, text="⚙ Choose Folder", command=self.choose_folder).pack(side="left", padx=6)

        # SETTINGS
        settings = ttk.LabelFrame(main, text="Settings")
        settings.pack(fill="x", padx=10, pady=6)

        # Camera
        ttk.Label(settings, text="Camera").grid(row=0, column=0, padx=5, sticky="w")
        self.camera_var = tk.StringVar(value=self.selected_camera_name)
        self.camera_combo = ttk.Combobox(settings, values=self.cameras, textvariable=self.camera_var, state="readonly")
        self.camera_combo.grid(row=0, column=1, padx=5, sticky="w")
        self.camera_combo.bind("<<ComboboxSelected>>", self._on_camera_change)

        # Microphone
        ttk.Label(settings, text="Microphone").grid(row=1, column=0, padx=5, sticky="w")
        self.mic_var = tk.StringVar(value=self.selected_microphone)
        self.mic_combo = ttk.Combobox(settings, values=self.microphones, textvariable=self.mic_var, state="readonly")
        self.mic_combo.grid(row=1, column=1, padx=5, sticky="w")
        self.mic_combo.bind("<<ComboboxSelected>>", self._on_microphone_change)

        # Resolution
        ttk.Label(settings, text="Resolution").grid(row=2, column=0, padx=5, sticky="w")
        self.resolution_var = tk.StringVar(value=self.selected_resolution)
        self.resolution_combo = ttk.Combobox(settings, values=list(self.camera_caps.keys()), textvariable=self.resolution_var, state="readonly")
        self.resolution_combo.grid(row=2, column=1, padx=5, sticky="w")
        self.resolution_combo.bind("<<ComboboxSelected>>", self._on_resolution_change)

        # FPS
        ttk.Label(settings, text="FPS").grid(row=2, column=2, padx=5, sticky="w")
        self.fps_var = tk.IntVar(value=self.selected_fps)
        self.fps_combo = ttk.Combobox(settings, values=[10,20,30,60,120], textvariable=self.fps_var, state="readonly")
        self.fps_combo.grid(row=2, column=3, padx=5, sticky="w")
        self.fps_combo.bind("<<ComboboxSelected>>", self._on_fps_change)

        # PREVIEW ADJUSTMENTS
        adjustments = ttk.LabelFrame(main, text="Preview Adjustments")
        adjustments.pack(fill="x", padx=10, pady=6)

        ttk.Label(adjustments, text="Brightness").grid(row=0, column=0, padx=5, sticky="w")
        self.brightness_slider = ttk.Scale(adjustments, from_=0.0, to=2.0, orient="horizontal", variable=self.brightness_var)
        self.brightness_slider.grid(row=0, column=1, sticky="ew", padx=5)
        self.brightness_slider.config(command=lambda v: self.settings.set("brightness", float(v)))

        ttk.Label(adjustments, text="Contrast").grid(row=1, column=0, padx=5, sticky="w")
        self.contrast_slider = ttk.Scale(adjustments, from_=0.0, to=3.0, orient="horizontal", variable=self.contrast_var)
        self.contrast_slider.grid(row=1, column=1, sticky="ew", padx=5)
        self.contrast_slider.config(command=lambda v: self.settings.set("contrast", float(v)))

        adjustments.columnconfigure(1, weight=1)  # slider expande horizontalmente

        # Status
        self.status = ttk.Label(main, text="Status: IDLE")
        self.status.pack(anchor="w", padx=10, pady=4)

    # ================= PREVIEW =================
    def start_preview(self) -> None:
        """Start live preview via RecorderManager."""
        self.recorder.start_preview(self._update_preview)

    def _update_preview(self, frame: np.ndarray) -> None:
        """Update Tkinter label with frame, applying brightness/contrast and padding."""
        def _ui():
            if not self.video_label.winfo_exists():
                return
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            adjusted = np.clip(rgb * self.contrast_var.get() + (self.brightness_var.get() - 1)*128, 0, 255).astype(np.uint8)
            h, w, _ = adjusted.shape
            target_w, target_h = 1280, 720
            scale = min(target_w / w, target_h / h)
            new_w, new_h = int(w*scale), int(h*scale)
            resized = cv2.resize(adjusted, (new_w, new_h))
            canvas = np.zeros((target_h, target_w,3), dtype=np.uint8)
            x_offset = (target_w-new_w)//2
            y_offset = (target_h-new_h)//2
            canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
            img = Image.fromarray(canvas)
            self.tk_image = ImageTk.PhotoImage(img)
            self.video_label.configure(image=self.tk_image)
        self.root.after(0, _ui)

    # ================= RECORDING =================
    def start_record(self) -> None:
        """Start recording video + audio."""
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.temp_video = os.path.join(self.output_dir, f"temp_{ts}.avi")
            self.temp_audio = os.path.join(self.output_dir, f"temp_{ts}.wav")
            self.video_service.start_recording(self.temp_video)
            self.audio_service.start_recording()
            self.btn_start.config(state="disabled")
            self.btn_stop.config(state="normal")
            self.status.config(text="Status: RECORDING")
        except Exception as e:
            messagebox.showerror("Erro ao iniciar gravação", str(e))
            self.btn_start.config(state="normal")
            self.btn_stop.config(state="disabled")
            self.temp_video = None
            self.temp_audio = None

    def stop_record(self):
        """Stop recording video + audio and merge with FFmpeg (full debug)."""
        try:
            # Stop recording services
            self.video_service.stop_recording()
            self.audio_service.stop_recording(self.temp_audio)  # <-- Corrigido

            self.btn_start.config(state="normal")
            self.btn_stop.config(state="disabled")

            # Caminhos
            final_path = os.path.join(
                self.output_dir,
                f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            )
            ffmpeg_path = os.path.join(os.getcwd(), "ffmpeg", "ffmpeg.exe")

            cmd = [
                ffmpeg_path, "-y",
                "-i", self.temp_video,
                "-i", self.temp_audio,
                "-c:v", "libx264", "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                final_path
            ]

            print("=== FFmpeg Command ===")
            print(" ".join(cmd))
            print("=====================")

            # Executa FFmpeg capturando stdout e stderr
            result = subprocess.run(cmd, capture_output=True, text=True)

            print("=== FFmpeg STDOUT ===")
            print(result.stdout)
            print("=== FFmpeg STDERR ===")
            print(result.stderr)
            print("=====================")

            # Verifica se houve erro
            if result.returncode != 0:
                messagebox.showerror(
                    "Erro FFmpeg",
                    f"FFmpeg retornou código {result.returncode}\n\n"
                    f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
                )
                return

            # Remove arquivos temporários somente se FFmpeg rodou com sucesso
            try:
                os.remove(self.temp_video)
                os.remove(self.temp_audio)
            except Exception as e:
                print("Erro ao remover temporários:", e)

            self.temp_video = None
            self.temp_audio = None
            self.status.config(text=f"Salvo: {final_path}")

        except Exception as e:
            messagebox.showerror("Erro Stop Record", str(e))
            print("Exception stop_record:", e)




    # ================= DEVICE CHANGES =================
    def _on_camera_change(self, event=None) -> None:
        """Switch camera and restart preview."""
        self.selected_camera_name = self.camera_var.get()
        self.selected_camera_index = self.camera_index_map[self.selected_camera_name]
        self.recorder.video_service.camera_index = self.selected_camera_index
        if self.recorder.video_service.previewing:
            self.recorder.video_service.stop_preview()
            self.recorder.start_preview(self._update_preview)

    def _on_microphone_change(self, event=None) -> None:
        """Update microphone device in RecorderManager."""
        self.selected_microphone = self.mic_var.get()
        self.recorder.audio_service.device_name = self.selected_microphone

    def _on_resolution_change(self, event=None) -> None:
        """Update resolution in RecorderManager."""
        self.selected_resolution = self.resolution_var.get()
        w, h = map(int, self.selected_resolution.split("x"))
        self.recorder.video_service.resolution = (w, h)

    def _on_fps_change(self, event=None) -> None:
        """Update FPS in RecorderManager."""
        self.selected_fps = self.fps_var.get()
        self.recorder.video_service.fps = self.selected_fps

    # ================= FOLDER =================
    def open_folder(self) -> None:
        """Open current output directory in system file explorer."""
        os.startfile(self.output_dir)

    def choose_folder(self) -> None:
        """Allow user to select a new output directory."""
        folder = filedialog.askdirectory(initialdir=self.output_dir)
        if folder:
            self.output_dir = folder

    # ================= EXIT =================
    def close(self) -> None:
        """Stop preview/recording, save settings, close Tkinter window."""
        self._save_settings()
        if self.recorder.video_service.previewing:
            self.recorder.video_service.stop_preview()
        if self.recorder.recording:
            self.recorder.stop_recording()
        self.root.destroy()
