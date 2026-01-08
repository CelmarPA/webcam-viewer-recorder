# main.py
from __future__ import annotations
import os
import sys
import tkinter as tk
from pathlib import Path

from app_window import AppWindow

# ================= CONFIGURAÇÃO =================
# Caminho absoluto do FFmpeg
FFMPEG_PATH = Path(__file__).parent / "ffmpeg" / "ffmpeg.exe"
if not FFMPEG_PATH.exists():
    sys.exit("FFmpeg não encontrado. Coloque ffmpeg.exe na pasta ./ffmpeg/")

# Diretório padrão para salvar vídeos
OUTPUT_DIR = Path.home() / "Videos"
OUTPUT_DIR.mkdir(exist_ok=True)

# ================= RODA APLICATIVO =================
def main():
    root = tk.Tk()
    app = AppWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
