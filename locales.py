# -*- coding: utf-8 -*-
"""UI strings for German and English (config / rule logic stays English keys in JSON)."""

from __future__ import annotations

from config_io import Action, Condition, IfType

LANG_DE = "de"
LANG_EN = "en"

STRINGS: dict[str, dict[str, str]] = {
    LANG_DE: {
        "win_title": "Download-Sortierer",
        "tab_profile": "Profil & Ordner",
        "tab_rules": "Regeln",
        "rules_tab_profile_caption": "Regeln gelten für Profil:",
        "help_show": "Hilfe anzeigen ▾",
        "help_hide": "Hilfe ausblenden ▴",
        "appearance_dark": "Dunkel",
        "appearance_light": "Hell",
        "hotkeys_hint": "Tasten: F5 = Ordner jetzt prüfen · Esc = alle Überwachungen stoppen",
        "watch_empty_hint": "Noch kein Ordner für dieses Profil — „Ordner wählen…“ nutzen.",
        "escape_stop_title": "Alle stoppen?",
        "escape_stop_message": "Alle aktiven Profile werden gestoppt.",
        "language": "Sprache",
        "watch_folder": "Überwachter Ordner:",
        "watch_folders_active": "Überwachte Ordner:",
        "browse_folder": "Ordner wählen…",
        "rule_help": (
            "Profile: Jedes Profil hat einen eigenen Überwachungsordner und eigene Regeln. Unter "
            "„Profil aktivieren“ wählst du, welche Profile bei „Ordner jetzt prüfen“ mitlaufen — das Häkchen startet "
            "die Überwachung noch nicht. Beim normalen Programmstart startet nichts automatisch; nur wenn die App "
            "mit Windows anmeldet (Option „Mit Windows starten“), werden angehakte Profile automatisch überwacht. "
            "Regeln: oben = höchste Priorität. "
            "Mit ↑/↓ die Reihenfolge ändern. Bereits liegende Dateien: Profile anhaken, dann "
            "„Ordner jetzt prüfen“. „+ ODER“ / „+ Kriterium (UND)“ wie zuvor."
        ),
        "add_rule": "Regel hinzufügen",
        "remove_last_rule": "Letzte Regel entfernen",
        "export_rules": "Regeln exportieren…",
        "import_rules": "Regeln importieren…",
        "rule_editor": "Regel-Editor",
        "start": "Start",
        "stop": "Stopp",
        "profile_label": "Profil:",
        "profile_name": "Name",
        "add_profile": "Profil hinzufügen",
        "remove_profile": "Profil entfernen",
        "watch_enable": "Überwachen",
        "profile_activate_section": "Profil aktivieren",
        "profile_editor_hint": "Du bearbeitest: {entry} — Ordner hier; Regeln im Tab „Regeln“. Häkchen = für Scan/Autostart vormerken; Überwachung startet mit „Ordner jetzt prüfen“.",
        "profile_activity_expand": "Profile anzeigen",
        "profile_activity_collapse": "Profile ausblenden",
        "stop_all": "Alle stoppen",
        "profile_observer_stopped": "Überwachung für „{name}“ gestoppt.",
        "remove_profile_blocked": "Mindestens ein Profil muss bleiben.",
        "status_active_names": "Aktiv: {names}",
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
        "manual_scan_need_start": "Überwachung konnte nicht gestartet werden (siehe Meldung unten / Log).",
        "manual_scan_need_select": "Kein Profil aktiviert oder kein gültiger Überwachungsordner — unter „Profil aktivieren“ Häkchen setzen und Ordner wählen, dann „Ordner jetzt prüfen“.",
        "err_watch_folder_profile": "Profil „{name}“: Kein gültiger Überwachungsordner.",
        "manual_scan_bad_folder": "Kein gültiger Überwachungsordner.",
        "manual_scan_done": "Scan: {n} Datei(en) eingereiht (siehe download_sorter.log).",
        "err_watch_folder": "Fehler: Bitte gültigen Überwachungsordner wählen.",
        "err_start": "Start fehlgeschlagen: {error}",
        "status_running": "Läuft – überwache: {path} (Log: {log})",
        "status_exported": "Regeln exportiert: {path}",
        "status_imported": "Regeln importiert aus: {path}",
        "autostart_win": "Mit Windows starten",
        "autostart_registry_error": "Autostart konnte nicht geändert werden:\n{error}",
        "autostart_no_folder": "Autostart: Kein gültiger Überwachungsordner in der Konfiguration.",
    },
    LANG_EN: {
        "win_title": "Download Sorter",
        "tab_profile": "Profile & folder",
        "tab_rules": "Rules",
        "rules_tab_profile_caption": "Rules apply to profile:",
        "help_show": "Show help ▾",
        "help_hide": "Hide help ▴",
        "appearance_dark": "Dark",
        "appearance_light": "Light",
        "hotkeys_hint": "Keys: F5 = scan folder now · Esc = stop all watchers",
        "watch_empty_hint": "No watch folder for this profile yet — use “Choose folder…”.",
        "escape_stop_title": "Stop all?",
        "escape_stop_message": "All active profiles will be stopped.",
        "language": "Language",
        "watch_folder": "Watch folder:",
        "watch_folders_active": "Watch folders:",
        "browse_folder": "Choose folder…",
        "rule_help": (
            "Profiles: Each profile has its own watch folder and rules. Under “Activate profiles” you choose "
            "which profiles take part in “Scan folder now” — ticking does not start watching yet. "
            "On a normal launch nothing starts automatically; only when the app runs at Windows login "
            "(“Start with Windows”) will ticked profiles begin watching automatically. "
            "Rules: top = highest priority. Use ↑/↓ to reorder. "
            "Files already in the folder: tick profiles, then “Scan folder now”. "
            "“+ OR” / “+ Criterion (AND)” as before."
        ),
        "add_rule": "Add rule",
        "remove_last_rule": "Remove last rule",
        "export_rules": "Export rules…",
        "import_rules": "Import rules…",
        "rule_editor": "Rule editor",
        "start": "Start",
        "stop": "Stop",
        "profile_label": "Profile:",
        "profile_name": "Name",
        "add_profile": "Add profile",
        "remove_profile": "Remove profile",
        "watch_enable": "Watch",
        "profile_activate_section": "Activate profiles",
        "profile_editor_hint": "You are editing: {entry} — folder here; rules in the “Rules” tab. Tick = queue for scan/autostart; watching starts with “Scan folder now”.",
        "profile_activity_expand": "Show profiles",
        "profile_activity_collapse": "Hide profiles",
        "stop_all": "Stop all",
        "profile_observer_stopped": "Stopped watching “{name}”.",
        "remove_profile_blocked": "At least one profile must remain.",
        "status_active_names": "Active: {names}",
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
        "manual_scan_need_start": "Could not start watching (see message below / log).",
        "manual_scan_need_select": "No profile activated or no valid watch folder — tick profiles under “Activate profiles”, set folders, then “Scan folder now”.",
        "err_watch_folder_profile": "Profile “{name}”: no valid watch folder.",
        "manual_scan_bad_folder": "No valid watch folder.",
        "manual_scan_done": "Scan: {n} file(s) queued (see download_sorter.log).",
        "err_watch_folder": "Error: choose a valid watch folder.",
        "err_start": "Start failed: {error}",
        "status_running": "Running — watching: {path} (log: {log})",
        "status_exported": "Rules exported: {path}",
        "status_imported": "Rules imported from: {path}",
        "autostart_win": "Start with Windows",
        "autostart_registry_error": "Could not change autostart:\n{error}",
        "autostart_no_folder": "Autostart: No valid watch folder in config.",
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
