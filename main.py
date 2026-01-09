# main.py

from __future__ import annotations

import tkinter as tk

from app_window import AppWindow


def main() -> None:
    """
    Application entry point.

    Initializes the Tkinter root window and starts the main event loop.
    """
    root = tk.Tk()
    AppWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
