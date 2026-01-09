# main.py

from __future__ import annotations

import tkinter as tk

from app_window import AppWindow
from utils.settings_manager import SettingsManager


def main() -> None:
    """
    Application entry point.

    Initializes the Tkinter root window and starts the main event loop.
    """

    # Force devices cache generation on startup
    SettingsManager()
    
    root = tk.Tk()
    AppWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
