# app_window.py

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import cv2
import numpy as np
from PIL import Image, ImageTk

from recorder_manager.recorder_manager import RecorderManager
from audio_capture.audio_capture_service import AudioCaptureService
from video_capture.video_capture_service import VideoCaptureService
from utils.settings_manager import SettingsManager


class AppWindow:
    """
    Main application window for the Webcam Recorder.

    Provides live preview, device selection, preview adjustments,
    and synchronized MKV recording using cached device information.
    """

    def __init__(self, root: tk.Tk) -> None:
        """
        Initialize the main application window.

        :param root: Tkinter root window
        :type root: tk.Tk
        """
        self.root = root
        self.root.title("Webcam Recorder")
        self.root.minsize(820, 640)

        # ---------- ICON ----------
        icon_path = Path(__file__).parent / "resources" / "icons" / "ico.ico"
        if icon_path.exists():
            self.root.iconbitmap(default=str(icon_path))

        # ---------- SETTINGS ----------
        self.settings = SettingsManager()

        # ---------- PATHS ----------
        self.ffmpeg_path = os.path.join(os.getcwd(), "ffmpeg", "ffmpeg.exe")
        if not os.path.exists(self.ffmpeg_path):
            raise FileNotFoundError(
                "FFmpeg executable not found. Place it in ./ffmpeg/ffmpeg.exe"
            )

        last_dir = self.settings.get("last_output_dir")
        videos_dir = Path(last_dir or Path.home() / "Videos")
        self.output_dir: str = str(
            videos_dir if videos_dir.exists() else Path.home()
        )

        # ---------- DEVICES ----------
        devices_cache = self.settings.get_devices_cache()
        self.cameras_info = devices_cache.get("cameras", [])
        self.microphones_info = devices_cache.get("microphones", [])

        if not self.cameras_info:
            raise RuntimeError("No cameras found in devices.json cache.")
        if not self.microphones_info:
            raise RuntimeError("No microphones found in devices.json cache.")

        self.cameras = [c["name"] for c in self.cameras_info]
        self.microphones = [m["name"] for m in self.microphones_info]

        # ---------- INITIAL SELECTION ----------
        self.selected_camera_name = self.settings.get(
            "camera", self.cameras[0]
        )
        self.selected_microphone = self.settings.get(
            "microphone", self.microphones[0]
        )

        camera_cache = next(
            c for c in self.cameras_info
            if c["name"] == self.selected_camera_name
        )
        self.selected_camera_index = camera_cache["index"]

        res_values = camera_cache.get("resolutions") or ["1280x720"]
        self.selected_resolution = self.settings.get(
            "resolution", res_values[0]
        )
        width, height = map(int, self.selected_resolution.split("x"))

        # ---------- SERVICES ----------
        self.audio_service = AudioCaptureService()
        self.audio_service.device_name = self.selected_microphone

        self.video_service = VideoCaptureService(self.selected_camera_index)
        self.video_service.resolution = (width, height)
        self.video_service.fps_target = 30

        # ---------- ADJUSTMENTS ----------
        self.brightness_var = tk.DoubleVar(
            value=self.settings.get("brightness", 1.0)
        )
        self.contrast_var = tk.DoubleVar(
            value=self.settings.get("contrast", 1.0)
        )
        self.saturation_var = tk.DoubleVar(
            value=self.settings.get("saturation", 1.0)
        )

        # ---------- RECORDER ----------
        self.recorder = RecorderManager(
            video_service=self.video_service,
            audio_service=self.audio_service,
            ffmpeg_path=self.ffmpeg_path
        )
        self.recorder.brightness = self.brightness_var.get()
        self.recorder.contrast = self.contrast_var.get()
        self.recorder.saturation = self.saturation_var.get()

        # ---------- STATE ----------
        self.tk_image: Optional[ImageTk.PhotoImage] = None

        # ---------- UI ----------
        self._build_ui()
        self.start_preview()

        self.root.protocol("WM_DELETE_WINDOW", self.close)

    # ================= SETTINGS =================

    def _save_settings(self) -> None:
        """
        Persist application settings to disk.
        """
        data = {
            "brightness": self.brightness_var.get(),
            "contrast": self.contrast_var.get(),
            "saturation": self.saturation_var.get(),
            "last_output_dir": self.output_dir,
            "camera": self.selected_camera_name,
            "microphone": self.selected_microphone,
            "resolution": self.selected_resolution,
            "fps": self.video_service.fps_target,
        }
        self.settings.save(data)

    # ================= UI =================

    def _build_ui(self) -> None:
        """Build main UI components using grid with controlled preview size."""

        # ================= ROOT GRID CONFIG =================
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = ttk.Frame(self.root)
        main.grid(row=0, column=0, sticky="nsew")

        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=3)  # PREVIEW (menor peso)
        main.rowconfigure(1, weight=0)  # CONTROLS
        main.rowconfigure(2, weight=0)  # SETTINGS
        main.rowconfigure(3, weight=0)  # ADJUSTMENTS
        main.rowconfigure(4, weight=0)  # STATUS

        # ================= PREVIEW =================
        preview_frame = ttk.Frame(main, width=970, height=550)
        preview_frame.grid(row=0, column=0, sticky="n", padx=10, pady=6)

        preview_frame.grid_propagate(False)

        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        self.video_label = ttk.Label(preview_frame)
        self.video_label.place(relx=0.5, rely=0.5, anchor="center")

        # ================= CONTROLS =================
        controls = ttk.Frame(main)
        controls.grid(row=1, column=0, sticky="w", padx=10, pady=6)

        self.btn_start = ttk.Button(controls, text="▶ Start", command=self.start_record)
        self.btn_start.pack(side="left", padx=6)

        self.btn_stop = ttk.Button(
            controls, text="■ Stop", command=self.stop_record, state="disabled"
        )
        self.btn_stop.pack(side="left", padx=6)

        ttk.Button(
            controls, text="📂 Open Folder", command=self.open_folder
        ).pack(side="left", padx=6)

        ttk.Button(
            controls, text="⚙ Choose Folder", command=self.choose_folder
        ).pack(side="left", padx=6)

        # ================= SETTINGS =================
        settings = ttk.LabelFrame(main, text="Settings")
        settings.grid(row=2, column=0, sticky="ew", padx=10, pady=6)
        settings.columnconfigure(1, weight=1)

        # Camera
        ttk.Label(settings, text="Camera").grid(row=0, column=0, padx=5, sticky="w")
        self.camera_var = tk.StringVar(value=self.selected_camera_name)
        self.camera_combo = ttk.Combobox(
            settings, values=self.cameras, textvariable=self.camera_var, state="readonly"
        )
        self.camera_combo.grid(row=0, column=1, padx=5, sticky="w")
        self.camera_combo.bind("<<ComboboxSelected>>", self._on_camera_change)

        # Microphone
        ttk.Label(settings, text="Microphone").grid(row=1, column=0, padx=5, sticky="w")
        self.mic_var = tk.StringVar(value=self.selected_microphone)
        self.mic_combo = ttk.Combobox(
            settings, values=self.microphones, textvariable=self.mic_var, state="readonly"
        )
        self.mic_combo.grid(row=1, column=1, padx=5, sticky="w")
        self.mic_combo.bind("<<ComboboxSelected>>", self._on_microphone_change)

        # Resolution
        ttk.Label(settings, text="Resolution").grid(row=2, column=0, padx=5, sticky="w")
        camera_cache = next(c for c in self.cameras_info if c["name"] == self.selected_camera_name)
        res_values = camera_cache.get("resolutions", []) or ["1280x720"]

        self.resolution_var = tk.StringVar(value=self.selected_resolution)
        self.resolution_combo = ttk.Combobox(
            settings, values=res_values, textvariable=self.resolution_var, state="readonly"
        )
        self.resolution_combo.grid(row=2, column=1, padx=5, sticky="w")
        self.resolution_combo.bind("<<ComboboxSelected>>", self._on_resolution_change)

        # ================= ADJUSTMENTS =================
        adjustments = ttk.LabelFrame(main, text="Preview Adjustments")
        adjustments.grid(row=3, column=0, sticky="ew", padx=10, pady=6)
        adjustments.columnconfigure(1, weight=1)

        ttk.Label(adjustments, text="Brightness").grid(row=0, column=0, padx=5, sticky="w")
        ttk.Scale(
            adjustments,
            from_=0.0,
            to=2.0,
            orient="horizontal",
            variable=self.brightness_var,
            command=self._on_brightness_change,
        ).grid(row=0, column=1, sticky="ew", padx=5)

        ttk.Label(adjustments, text="Contrast").grid(row=1, column=0, padx=5, sticky="w")
        ttk.Scale(
            adjustments,
            from_=0.0,
            to=3.0,
            orient="horizontal",
            variable=self.contrast_var,
            command=self._on_contrast_change,
        ).grid(row=1, column=1, sticky="ew", padx=5)

        ttk.Label(adjustments, text="Saturation").grid(row=2, column=0, padx=5, sticky="w")
        ttk.Scale(
            adjustments,
            from_=0.0,
            to=3.0,
            orient="horizontal",
            variable=self.saturation_var,
            command=self._on_saturation_change,
        ).grid(row=2, column=1, sticky="ew", padx=5)

        # ================= STATUS =================
        self.status = ttk.Label(
            main,
            text="Status: IDLE",
            font=("Helvetica", 12, "bold"),
            foreground="blue",
        )
        self.status.grid(row=4, column=0, sticky="w", padx=10, pady=4)

    # ================= PREVIEW =================

    def start_preview(self) -> None:
        """
        Start live video preview.
        """
        self.recorder.start_preview(self._update_preview)

    def _update_preview(self, frame: np.ndarray) -> None:
        """
        Update the preview image ensuring it always fits inside
        the fixed preview area (970x550) with preserved aspect ratio.
        """
        def _ui() -> None:
            if not self.video_label.winfo_exists():
                return

            # Apply brightness / contrast
            beta = int((self.brightness_var.get() - 1.0) * 50)
            adjusted = cv2.convertScaleAbs(
                frame,
                alpha=self.contrast_var.get(),
                beta=beta
            )

            src_h, src_w, _ = adjusted.shape
            target_w, target_h = 970, 550

            # 🔒 FORCE FIT (LETTERBOX)
            scale = min(target_w / src_w, target_h / src_h)
            new_w = int(src_w * scale)
            new_h = int(src_h * scale)

            resized = cv2.resize(
                adjusted,
                (new_w, new_h),
                interpolation=cv2.INTER_AREA
            )

            # Black canvas (preview box)
            canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)

            x_offset = (target_w - new_w) // 2
            y_offset = (target_h - new_h) // 2

            canvas[
                y_offset:y_offset + new_h,
                x_offset:x_offset + new_w
            ] = resized

            img = Image.fromarray(
                cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
            )
            self.tk_image = ImageTk.PhotoImage(img)
            self.video_label.configure(image=self.tk_image)

        self.root.after(0, _ui)


    # ================= RECORDING =================

    def start_record(self) -> None:
        """
        Start video and audio recording.
        """
        try:
            self.recorder.brightness = self.brightness_var.get()
            self.recorder.contrast = self.contrast_var.get()

            output_file = self.recorder.start_recording(self.output_dir)
            self.status.config(
                text=f"Status: RECORDING → {output_file}"
            )
            self.btn_start.config(state="disabled")
            self.btn_stop.config(state="normal")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def stop_record(self) -> None:
        """
        Stop recording asynchronously.
        """
        def _stop_thread() -> None:
            try:
                output_file = self.recorder.stop_recording()
                text = (
                    f"Saved: {output_file}"
                    if output_file else
                    "Recording stopped."
                )
                self.root.after(
                    0, lambda: self.status.config(text=text)
                )
            except Exception as exc:
                self.root.after(
                    0, lambda: messagebox.showerror("Error", str(exc))
                )
            finally:
                self.root.after(
                    0, lambda: self.btn_start.config(state="normal")
                )
                self.root.after(
                    0, lambda: self.btn_stop.config(state="disabled")
                )

        self.btn_stop.config(state="disabled")
        self.status.config(text="Processing video, please wait…")
        threading.Thread(target=_stop_thread, daemon=True).start()

    # ================= DEVICE CHANGES =================

    def _change_camera(self, new_camera_name: str) -> None:
        """
        Change active camera using cached device information.
        """
        def switch_camera() -> None:
            self.camera_combo.config(state="disabled")
            self.status.config(
                text=f"Changing camera to {new_camera_name}..."
            )

            self.recorder.video_service.stop_preview()

            camera = next(
                (c for c in self.cameras_info
                 if c["name"] == new_camera_name),
                None
            )

            if camera is None:
                self.status.config(text="Camera not found.")
                self.camera_combo.config(state="readonly")
                return

            self.selected_camera_name = camera["name"]
            self.selected_camera_index = camera["index"]
            self.recorder.video_service.camera_index = camera["index"]

            res_values = camera.get("resolutions") or ["1280x720"]
            self.resolution_combo["values"] = res_values

            self.selected_resolution = res_values[0]
            self.resolution_var.set(self.selected_resolution)

            width, height = map(
                int, self.selected_resolution.split("x")
            )
            self.recorder.video_service.resolution = (width, height)

            self.start_preview()
            self.status.config(text="Status: IDLE")
            self.camera_combo.config(state="readonly")

        threading.Thread(target=switch_camera, daemon=True).start()

    def _change_microphone(self, new_mic: str) -> None:
        """
        Change active microphone using cached device information.
        """
        def switch_mic() -> None:
            self.mic_combo.config(state="disabled")
            self.status.config(
                text=f"Changing microphone to {new_mic}..."
            )

            valid = [m["name"] for m in self.microphones_info]
            self.selected_microphone = (
                new_mic if new_mic in valid else valid[0]
            )
            self.recorder.audio_service.device_name = (
                self.selected_microphone
            )

            self.status.config(text="Status: IDLE")
            self.mic_combo.config(state="readonly")

        threading.Thread(target=switch_mic, daemon=True).start()

    def _change_resolution(self, new_res: str) -> None:
        """
        Change video resolution and restart preview.
        """
        def switch_res() -> None:
            self.resolution_combo.config(state="disabled")
            self.status.config(
                text=f"Changing resolution to {new_res}..."
            )

            self.selected_resolution = new_res
            width, height = map(int, new_res.split("x"))
            self.recorder.video_service.resolution = (width, height)

            self.recorder.video_service.stop_preview()
            self.start_preview()

            self.status.config(text="Status: IDLE")
            self.resolution_combo.config(state="readonly")

        threading.Thread(target=switch_res, daemon=True).start()

    def _on_camera_change(self, event=None) -> None:
        self._change_camera(self.camera_var.get())

    def _on_microphone_change(self, event=None) -> None:
        self._change_microphone(self.mic_var.get())

    def _on_resolution_change(self, event=None) -> None:
        self._change_resolution(self.resolution_var.get())

    # ================= ADJUSTMENTS =================

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
        """
        Open output directory in file explorer.
        """
        os.startfile(self.output_dir)

    def choose_folder(self) -> None:
        """
        Select output directory.
        """
        folder = filedialog.askdirectory(
            initialdir=self.output_dir
        )
        if folder:
            self.output_dir = folder

    # ================= EXIT =================

    def close(self) -> None:
        """
        Gracefully stop preview/recording and exit application.
        """
        def stop_and_exit() -> None:
            if self.recorder.recording:
                self.status.config(
                    text="Status: Stopping recording..."
                )
                self.recorder.stop_recording()

            if getattr(self.recorder.video_service, "previewing", False):
                self.recorder.video_service.stop_preview()

            self._save_settings()
            self.root.after(0, self.root.destroy)

        if self.recorder.recording:
            if not messagebox.askyesno(
                "Recording in progress",
                "Recording is active. Stop recording and exit?"
            ):
                return

        threading.Thread(
            target=stop_and_exit,
            daemon=True
        ).start()
