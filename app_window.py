from __future__ import annotations
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageTk
import threading

from recorder_manager import RecorderManager
from audio_capture.audio_capture_service import AudioCaptureService
from video_capture.video_capture_service import VideoCaptureService
from utils.settings_manager import SettingsManager
from utils.devices import list_cameras, list_microphones, map_opencv_to_ffmpeg, get_camera_capabilities_real


class AppWindow:
    """Main window for Webcam Recorder with live preview and MKV recording."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Webcam Recorder")
        self.root.minsize(900, 700)

        # ---------- SETTINGS ----------
        self.settings = SettingsManager()

        # ---------- PATHS ----------
        self.ffmpeg_path = os.path.join(os.getcwd(), "ffmpeg", "ffmpeg.exe")
        if not os.path.exists(self.ffmpeg_path):
            raise FileNotFoundError("FFmpeg executable not found. Place it in ./ffmpeg/ffmpeg.exe")

        last_dir = self.settings.get("last_output_dir")
        videos_dir = Path(last_dir or Path.home() / "Videos")
        self.output_dir: str = str(videos_dir if videos_dir.exists() else Path.home())

        # ---------- DEVICES ----------
        self.cameras: list[str] = list_cameras()
        if not self.cameras:
            messagebox.showerror("Error", "No camera detected.")
            self.root.destroy()
            return

        self.camera_index_map: dict[str, int] = map_opencv_to_ffmpeg(self.cameras)
        self.selected_camera_name: str = self.settings.get("camera", self.cameras[0])
        if self.selected_camera_name not in self.camera_index_map:
            self.selected_camera_name = self.cameras[0]
        self.selected_camera_index: int = self.camera_index_map[self.selected_camera_name]

        self.microphones: list[str] = list_microphones()
        if not self.microphones:
            messagebox.showerror("Error", "No microphone detected.")
            self.root.destroy()
            return
        self.selected_microphone: str = self.settings.get("microphone", self.microphones[0])
        if self.selected_microphone not in self.microphones:
            self.selected_microphone = self.microphones[0]

        # ---------- BRIGHTNESS / CONTRAST ----------
        self.brightness_var = tk.DoubleVar(value=self.settings.get("brightness", 1.0))
        self.contrast_var = tk.DoubleVar(value=self.settings.get("contrast", 1.0))
        self.saturation_var = tk.DoubleVar(value=self.settings.get("saturation", 1.0))

        # ---------- SERVICES ----------
        self.audio_service = AudioCaptureService()
        self.audio_service.device_name = self.selected_microphone

        self.video_service = VideoCaptureService(self.selected_camera_index)
        self.camera_caps = get_camera_capabilities_real(self.selected_camera_name, self.selected_camera_index)
        if self.camera_caps:
            res_list = sorted(self.camera_caps.keys(), reverse=True)
            w, h = res_list[0]
            self.selected_resolution = self.settings.get("resolution", f"{w}x{h}")
            try:
                res_tuple = tuple(int(x) for x in self.selected_resolution.lower().replace(" ", "x").split("x"))
            except ValueError:
                res_tuple = (w, h)
            fps_list = self.camera_caps.get(res_tuple, [30])
            self.selected_fps = self.settings.get("fps", fps_list[0])
        else:
            self.selected_resolution = "1280x720"
            self.selected_fps = 30

        w, h = map(int, self.selected_resolution.split("x"))
        self.video_service.resolution = (w, h)
        self.video_service.fps_target = self.selected_fps

        # ---------- RECORDER ----------
        self.recorder = RecorderManager(
            video_service=self.video_service,
            audio_service=self.audio_service,
            ffmpeg_path=self.ffmpeg_path
        )
        self.recorder.brightness = self.brightness_var.get()
        self.recorder.contrast = self.contrast_var.get()

        # ---------- STATE ----------
        self.tk_image: Optional[ImageTk.PhotoImage] = None

        # ---------- BUILD UI ----------
        self._build_ui()

        # Start preview
        self.start_preview()

        # Protocol
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    # ================= SETTINGS =================
    def _save_settings(self) -> None:
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
        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True)

        # Video preview
        self.video_label = ttk.Label(main)
        self.video_label.pack(expand=True)

        # Controls
        controls = ttk.Frame(main)
        controls.pack(pady=8)
        self.btn_start = ttk.Button(controls, text="▶ Start", command=self.start_record)
        self.btn_start.pack(side="left", padx=6)
        self.btn_stop = ttk.Button(controls, text="■ Stop", command=self.stop_record, state="disabled")
        self.btn_stop.pack(side="left", padx=6)
        ttk.Button(controls, text="📂 Open Folder", command=self.open_folder).pack(side="left", padx=6)
        ttk.Button(controls, text="⚙ Choose Folder", command=self.choose_folder).pack(side="left", padx=6)

        # Settings frame
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
        self.resolution_combo = ttk.Combobox(settings, values=[f"{w}x{h}" for w, h in self.camera_caps.keys()],
                                             textvariable=self.resolution_var, state="readonly")
        self.resolution_combo.grid(row=2, column=1, padx=5, sticky="w")
        self.resolution_combo.bind("<<ComboboxSelected>>", self._on_resolution_change)

        # FPS
        ttk.Label(settings, text="FPS").grid(row=2, column=2, padx=5, sticky="w")
        self.fps_var = tk.IntVar(value=self.selected_fps)
        self.fps_combo = ttk.Combobox(settings, values=[10, 20, 30, 60, 120], textvariable=self.fps_var, state="readonly")
        self.fps_combo.grid(row=2, column=3, padx=5, sticky="w")
        self.fps_combo.bind("<<ComboboxSelected>>", self._on_fps_change)

        # Brightness / Contrast sliders
        adjustments = ttk.LabelFrame(main, text="Preview Adjustments")
        adjustments.pack(fill="x", padx=10, pady=6)
        ttk.Label(adjustments, text="Brightness").grid(row=0, column=0, padx=5, sticky="w")
        self.brightness_slider = ttk.Scale(adjustments, from_=0.0, to=2.0, orient="horizontal", variable=self.brightness_var)
        self.brightness_slider.grid(row=0, column=1, sticky="ew", padx=5)
        self.brightness_slider.config(command=self._on_brightness_change)

        ttk.Label(adjustments, text="Contrast").grid(row=1, column=0, padx=5, sticky="w")
        self.contrast_slider = ttk.Scale(adjustments, from_=0.0, to=3.0, orient="horizontal", variable=self.contrast_var)
        self.contrast_slider.grid(row=1, column=1, sticky="ew", padx=5)
        self.contrast_slider.config(command=self._on_contrast_change)
        adjustments.columnconfigure(1, weight=1)

        # ================== Saturation ==================
        ttk.Label(adjustments, text="Saturation").grid(row=2, column=0, padx=5, sticky="w")
        self.saturation_var = tk.DoubleVar(value=self.settings.get("saturation", 1.0))
        self.saturation_slider = ttk.Scale(
            adjustments, from_=0.0, to=3.0, orient="horizontal", variable=self.saturation_var
        )
        self.saturation_slider.grid(row=2, column=1, sticky="ew", padx=5)
        self.saturation_slider.config(command=self._on_saturation_change)

        self.status = ttk.Label(main, text="Status: IDLE")
        self.status.pack(anchor="w", padx=10, pady=4)

    # ================= PREVIEW =================
    def start_preview(self) -> None:
        self.recorder.start_preview(self._update_preview)

    def _update_preview(self, frame: np.ndarray) -> None:
        """Update Tkinter preview with brightness/contrast applied."""
        def _ui():
            if not self.video_label.winfo_exists():
                return
            beta = int((self.brightness_var.get() - 1.0) * 50)
            adjusted = cv2.convertScaleAbs(frame, alpha=self.contrast_var.get(), beta=beta)
            h, w, _ = adjusted.shape
            target_w, target_h = 1280, 720
            scale = min(target_w / w, target_h / h)
            new_w, new_h = int(w * scale), int(h * scale)
            resized = cv2.resize(adjusted, (new_w, new_h))
            canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
            x_offset = (target_w - new_w) // 2
            y_offset = (target_h - new_h) // 2
            canvas[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized
            img = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
            self.tk_image = ImageTk.PhotoImage(img)
            self.video_label.configure(image=self.tk_image)
        self.root.after(0, _ui)

    # ================= RECORDING =================
    def start_record(self) -> None:
        try:
            self.recorder.brightness = self.brightness_var.get()
            self.recorder.contrast = self.contrast_var.get()
            output_file = self.recorder.start_recording(self.output_dir)
            self.status.config(text=f"Status: RECORDING → {output_file}")
            self.btn_start.config(state="disabled")
            self.btn_stop.config(state="normal")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def stop_record(self) -> None:
        try:
            output_file = self.recorder.stop_recording()
            if output_file:
                self.status.config(text=f"Saved: {output_file}")
            self.btn_start.config(state="normal")
            self.btn_stop.config(state="disabled")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ================= DEVICE CHANGES =================
    def _on_camera_change(self, event=None):
        self.selected_camera_name = self.camera_var.get()
        self.selected_camera_index = int(self.camera_index_map[self.selected_camera_name])
        self.recorder.video_service.stop_preview()
        self.recorder.video_service.camera_index = self.selected_camera_index
        self.start_preview()

    def _on_microphone_change(self, event=None) -> None:
        self.selected_microphone = self.mic_var.get()
        self.recorder.audio_service.device_name = self.selected_microphone

    def _on_resolution_change(self, event=None) -> None:
        self.selected_resolution = self.resolution_var.get()
        w, h = map(int, self.selected_resolution.split("x"))
        self.recorder.video_service.resolution = (w, h)

    def _on_fps_change(self, event=None) -> None:
        self.selected_fps = self.fps_var.get()
        self.recorder.video_service.fps_target = self.selected_fps

    def _on_brightness_change(self, value: str) -> None:
        self.recorder.brightness = float(value)
        self.settings.set("brightness", float(value))

    def _on_contrast_change(self, value: str) -> None:
        self.recorder.contrast = float(value)
        self.settings.set("contrast", float(value))

    def _on_saturation_change(self, value: str) -> None:
        self.recorder.saturation = float(value)
        self.settings.set("saturation", float(value))

    # ================= FOLDER =================
    def open_folder(self) -> None:
        os.startfile(self.output_dir)

    def choose_folder(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.output_dir)
        if folder:
            self.output_dir = folder

    # ================= EXIT =================
    def close(self) -> None:
        """
        Fecha a aplicação de forma segura.
        - Se houver gravação ativa, pergunta ao usuário e para em background.
        - Para o preview de vídeo.
        - Salva configurações antes de fechar.
        """
        def stop_and_exit():
            """Função rodando em thread separada para não travar a GUI."""
            # Para gravação se estiver ativa
            if getattr(self.recorder, "recording", False):
                self.status.config(text="Status: Parando gravação...")
                self.recorder.stop_recording()

            # Para preview de vídeo se estiver ativo
            if getattr(self.recorder.video_service, "previewing", False):
                self.recorder.video_service.stop_preview()

            # Salva configurações
            self._save_settings()

            # Fecha a janela no thread principal
            self.root.after(0, self.root.destroy)

        # Se estiver gravando, perguntar ao usuário
        if getattr(self.recorder, "recording", False):
            stop = messagebox.askyesno(
                "Gravação em andamento",
                "A gravação está ativa. Deseja parar a gravação e fechar a aplicação?"
            )
            if not stop:
                return  # Usuário cancelou, não fecha

        # Inicia thread para parar gravação / preview e fechar app
        threading.Thread(target=stop_and_exit, daemon=True).start()
