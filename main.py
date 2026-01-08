# main.py

from __future__ import annotations
import tkinter as tk
from app_window import AppWindow

def main() -> None:
    """
    Entry point for Webcam Recorder application.

    Initializes Tkinter root and launches AppWindow.
    """
    root = tk.Tk()
    app = AppWindow(root)
    root.mainloop()

if __name__ == "__main__":
    main()
