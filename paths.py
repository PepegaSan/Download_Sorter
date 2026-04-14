# -*- coding: utf-8 -*-
"""Projekt- bzw. Installationsverzeichnis (wichtig für PyInstaller-EXE)."""

from __future__ import annotations

import sys
from pathlib import Path


def application_base_dir() -> Path:
    """
    Ordner für config.json, Logdatei und Export-Dialog-Start.

    - Normal: Verzeichnis von main.py
    - PyInstaller --onefile/--onedir: Ordner der .exe (schreibbar)
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent
