# -*- coding: utf-8 -*-
"""UI strings for German and English (config / rule logic stays English keys in JSON)."""

from __future__ import annotations

from config_io import Action, Condition, IfType

LANG_DE = "de"
LANG_EN = "en"

STRINGS: dict[str, dict[str, str]] = {
    LANG_DE: {
        "win_title": "Download-Sortierer",
        "language": "Sprache",
        "watch_folder": "Überwachter Ordner:",
        "browse_folder": "Ordner wählen…",
        "rule_help": (
            "Regeln: oben = höchste Priorität (erste passende Regel gewinnt). "
            "Mit ↑/↓ die Reihenfolge ändern. Bereits im Ordner liegende Dateien: nach „Start“ auf "
            "„Ordner jetzt prüfen“ klicken (Watchdog sieht nur neue Änderungen). "
            "„+ ODER“ / „+ Kriterium (UND)“ wie zuvor."
        ),
        "add_rule": "Regel hinzufügen",
        "remove_last_rule": "Letzte Regel entfernen",
        "export_rules": "Regeln exportieren…",
        "import_rules": "Regeln importieren…",
        "rule_editor": "Regel-Editor",
        "start": "Start",
        "stop": "Stopp",
        "scan_folder": "Ordner jetzt prüfen",
        "status_stopped": "Gestoppt",
        "when": "WENN",
        "and": "UND",
        "or": "ODER",
        "or_add": "+ ODER",
        "placeholder_ext": "z. B. .jpg",
        "placeholder_alt": "weitere Alternative",
        "add_criterion": "+ Kriterium (UND)",
        "action": "AKTION",
        "target_folder": "Zielordner…",
        "collapse": "Einklappen",
        "expand": "Ausklappen",
        "rule": "Regel",
        "preview_empty": "(leer)",
        "export_title": "Regeln exportieren",
        "export_failed": "Export fehlgeschlagen",
        "import_title": "Regeln importieren",
        "import_failed": "Import fehlgeschlagen",
        "import_read_error": "Datei konnte nicht gelesen werden:\n{error}",
        "import_no_rules": 'Die Datei enthält keine gültige „rules“-Liste.',
        "import_bad_entry": "Ungültiger Eintrag bei Regel {n}.",
        "import_corrupt_rule": "Regel {n} ist beschädigt:\n{error}",
        "import_watch_title": "Überwachungsordner",
        "import_watch_prompt": (
            "In der Datei ist dieser Ordner gespeichert:\n{path}\n\n"
            "Soll er als überwachter Ordner übernommen werden?"
        ),
        "ft_json": "JSON",
        "ft_all": "Alle Dateien",
        "export_description": "Download-Sortierer — Regeln",
        "export_default_name": "download_sorter_regeln.json",
        "manual_scan_need_start": "Zuerst „Start“ drücken, dann „Ordner jetzt prüfen“.",
        "manual_scan_bad_folder": "Kein gültiger Überwachungsordner.",
        "manual_scan_done": "Scan: {n} Datei(en) eingereiht (siehe download_sorter.log).",
        "err_watch_folder": "Fehler: Bitte gültigen Überwachungsordner wählen.",
        "err_start": "Start fehlgeschlagen: {error}",
        "status_running": "Läuft – überwache: {path} (Log: {log})",
        "status_exported": "Regeln exportiert: {path}",
        "status_imported": "Regeln importiert aus: {path}",
    },
    LANG_EN: {
        "win_title": "Download Sorter",
        "language": "Language",
        "watch_folder": "Watch folder:",
        "browse_folder": "Choose folder…",
        "rule_help": (
            "Rules: top = highest priority (first matching rule wins). "
            "Use ↑/↓ to reorder. Files already in the folder: after Start, click “Scan folder now” "
            "(the watcher only sees new changes). "
            "“+ OR” / “+ Criterion (AND)” as before."
        ),
        "add_rule": "Add rule",
        "remove_last_rule": "Remove last rule",
        "export_rules": "Export rules…",
        "import_rules": "Import rules…",
        "rule_editor": "Rule editor",
        "start": "Start",
        "stop": "Stop",
        "scan_folder": "Scan folder now",
        "status_stopped": "Stopped",
        "when": "IF",
        "and": "AND",
        "or": "OR",
        "or_add": "+ OR",
        "placeholder_ext": "e.g. .jpg",
        "placeholder_alt": "another alternative",
        "add_criterion": "+ Criterion (AND)",
        "action": "ACTION",
        "target_folder": "Target folder…",
        "collapse": "Collapse",
        "expand": "Expand",
        "rule": "Rule",
        "preview_empty": "(empty)",
        "export_title": "Export rules",
        "export_failed": "Export failed",
        "import_title": "Import rules",
        "import_failed": "Import failed",
        "import_read_error": "Could not read file:\n{error}",
        "import_no_rules": 'The file has no valid "rules" list.',
        "import_bad_entry": "Invalid entry for rule {n}.",
        "import_corrupt_rule": "Rule {n} is invalid:\n{error}",
        "import_watch_title": "Watch folder",
        "import_watch_prompt": (
            "The file contains this folder:\n{path}\n\n"
            "Use it as the watch folder?"
        ),
        "ft_json": "JSON",
        "ft_all": "All files",
        "export_description": "Download Sorter — rules",
        "export_default_name": "download_sorter_rules.json",
        "manual_scan_need_start": 'Press “Start” first, then “Scan folder now”.',
        "manual_scan_bad_folder": "No valid watch folder.",
        "manual_scan_done": "Scan: {n} file(s) queued (see download_sorter.log).",
        "err_watch_folder": "Error: choose a valid watch folder.",
        "err_start": "Start failed: {error}",
        "status_running": "Running — watching: {path} (log: {log})",
        "status_exported": "Rules exported: {path}",
        "status_imported": "Rules imported from: {path}",
    },
}

PAIRS_IF: dict[str, list[tuple[str, IfType]]] = {
    LANG_DE: [
        ("Dateiendung", "extension"),
        ("Dateiname", "filename"),
        ("Quell-URL", "source_url"),
    ],
    LANG_EN: [
        ("File extension", "extension"),
        ("File name", "filename"),
        ("Source URL", "source_url"),
    ],
}

PAIRS_COND: dict[str, list[tuple[str, Condition]]] = {
    LANG_DE: [
        ("enthält", "contains"),
        ("ist gleich", "equals"),
    ],
    LANG_EN: [
        ("contains", "contains"),
        ("equals", "equals"),
    ],
}

PAIRS_ACTION: dict[str, list[tuple[str, Action]]] = {
    LANG_DE: [
        ("Verschieben nach", "move"),
        ("Löschen", "delete"),
        ("Ignorieren", "ignore"),
    ],
    LANG_EN: [
        ("Move to", "move"),
        ("Delete", "delete"),
        ("Ignore", "ignore"),
    ],
}

LANG_MENU_LABELS = ("Deutsch", "English")


def normalize_lang(code: str) -> str:
    c = str(code or "").lower().strip()
    if c in ("en", "english", LANG_EN):
        return LANG_EN
    return LANG_DE


def t(lang: str, key: str, **kwargs: str) -> str:
    s = STRINGS.get(lang, STRINGS[LANG_DE]).get(key)
    if s is None:
        s = STRINGS[LANG_DE].get(key, key)
    if kwargs:
        return s.format(**kwargs)
    return s


def pairs_if(lang: str) -> list[tuple[str, IfType]]:
    return PAIRS_IF.get(lang, PAIRS_IF[LANG_DE])


def pairs_cond(lang: str) -> list[tuple[str, Condition]]:
    return PAIRS_COND.get(lang, PAIRS_COND[LANG_DE])


def pairs_action(lang: str) -> list[tuple[str, Action]]:
    return PAIRS_ACTION.get(lang, PAIRS_ACTION[LANG_DE])
