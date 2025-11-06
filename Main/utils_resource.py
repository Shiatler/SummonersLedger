import os, sys

def resource_path(rel_path: str) -> str:
    """
    Works in dev and PyInstaller (onefile/onedir).
    In dev, base = folder of this file. In build, base = _MEIPASS.
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel_path)
