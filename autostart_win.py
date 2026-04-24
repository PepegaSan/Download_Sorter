# -*- coding: utf-8 -*-
"""
Windows: Eintrag unter HKCU\\...\\Run für Autostart mit --autostart.

Nur unter Windows nutzbar; andere Plattformen ignorieren.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from paths import is_nuitka_compiled

REG_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "DownloadSorter"

# Einmal berechnen: .resolve() kann auf langsamen/Netz-Pfaden spürbar hängen.
_cached_launch_cmd: Optional[str] = None


def is_windows() -> bool:
    return sys.platform == "win32"


def launch_command_with_autostart_flag() -> str:
    """Kommandozeile, die die App mit --autostart startet (EXE oder python + Skript)."""
    global _cached_launch_cmd
    if _cached_launch_cmd is not None:
        return _cached_launch_cmd
    # absolute() statt resolve(): weniger I/O (OneDrive/Netzlaufwerke), für Run ausreichend.
    # Nuitka: kein sys.frozen — Start-.exe wie bei application_base_dir() über argv[0].
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).absolute()
        _cached_launch_cmd = f'"{exe}" --autostart'
    elif is_nuitka_compiled():
        exe = Path(sys.argv[0]).absolute()
        _cached_launch_cmd = f'"{exe}" --autostart'
    else:
        py = Path(sys.executable).absolute()
        script = Path(sys.argv[0]).absolute()
        _cached_launch_cmd = f'"{py}" "{script}" --autostart'
    return _cached_launch_cmd


def autostart_enabled() -> bool:
    """True, wenn der Run-Eintrag gesetzt ist."""
    if not is_windows():
        return False
    import winreg

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
        except OSError:
            return False
        finally:
            winreg.CloseKey(key)
    except OSError:
        return False


def set_autostart(enabled: bool) -> None:
    """Run-Eintrag setzen oder entfernen."""
    if not is_windows():
        raise OSError("Autostart nur unter Windows verfügbar.")
    import winreg

    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN, 0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
    try:
        if enabled:
            cmd = launch_command_with_autostart_flag()
            try:
                existing, typ = winreg.QueryValueEx(key, VALUE_NAME)
                if typ == winreg.REG_SZ and existing == cmd:
                    return
            except OSError:
                pass
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
    finally:
        winreg.CloseKey(key)
