# -*- coding: utf-8 -*-
"""Projekt- bzw. Installationsverzeichnis (wichtig für PyInstaller-EXE)."""

from __future__ import annotations

import sys
from pathlib import Path


def is_nuitka_compiled() -> bool:
    """Nuitka setzt kein sys.frozen; stattdessen __compiled__ im __main__-Modul."""
    m = sys.modules.get("__main__")
    if m is None:
        return False
    return "__compiled__" in getattr(m, "__dict__", ())


def application_base_dir() -> Path:
    """
    Ordner für config.json, Logdatei und Export-Dialog-Start.

    - Normal: Verzeichnis von main.py / diesem Paket
    - PyInstaller --onefile/--onedir: Ordner der .exe (schreibbar)
    - Nuitka: Ordner der Start-.exe (sys.argv[0], v. a. bei Onefile/DLL-Modus zuverlässiger als nur sys.executable)
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).absolute().parent
    if is_nuitka_compiled():
        return Path(sys.argv[0]).absolute().parent
    return Path(__file__).resolve().parent
