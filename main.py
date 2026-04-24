# -*- coding: utf-8 -*-
"""
Download Sorter — GUI (customtkinter) and folder watching (watchdog).

Config: config.json next to this script. UI: German or English (see locales.py, ui_language in config).
"""

from __future__ import annotations

import argparse
import json
import logging
import threading
import uuid
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import customtkinter as ctk

import autostart_win

from config_io import (
    Action,
    AppConfig,
    Condition,
    IfType,
    Rule,
    RuleCriterion,
    WatchProfile,
    load_config,
    runtime_config_for_profile,
    save_config,
)
from locales import (
    LANG_EN,
    LANG_MENU_LABELS,
    normalize_lang,
    pairs_action,
    pairs_cond,
    pairs_if,
    t,
)
from paths import application_base_dir
from theme_palette import PALETTE_DARK, PALETTE_LIGHT
from watch_service import WatchController

_LOG = logging.getLogger(__name__)

BTN_RADIUS = 10
BTN_H = 34
FONT_APP_TITLE = ("Segoe UI Semibold", 17)
FONT_UI = ("Segoe UI", 13)
FONT_UI_SM = ("Segoe UI", 12)
FONT_HINT = ("Segoe UI", 11)
FONT_SECTION = ("Segoe UI Semibold", 14)
FONT_BTN = ("Segoe UI Semibold", 11)

# Kompaktere Regel-Editor-Widgets (customtkinter width=, Pixel)
UI_PREFIX_W = 28
UI_IF_W = 102
UI_COND_W = 88
UI_VALUE_W = 124
UI_OR_ADD_W = 64
UI_COLLAPSE_W = 88
UI_ACTION_W = 112
UI_TARGET_BTN_W = 148

# Performance: weniger UI-Blockaden und weniger I/O
CONFIG_SYNC_INTERVAL_MS = 900
PERSIST_SAVE_DEBOUNCE_MS = 280
WATCH_EMPTY_HINT_DEBOUNCE_MS = 80
# Kompakter Stopp pro Profilzeile (Höhe an Checkbox-Zeile angeglichen)
PROFILE_ROW_STOP_BTN_W = 28
PROFILE_ROW_STOP_BTN_H = 22


def _setup_file_logging(base_dir: Path) -> None:
    """Logdatei für die Hintergrund-Verarbeitung (siehe download_sorter.log)."""
    log_path = base_dir / "download_sorter.log"
    root = logging.getLogger()
    if getattr(root, "_download_sorter_logging", False):
        return
    setattr(root, "_download_sorter_logging", True)
    handler = logging.FileHandler(log_path, encoding="utf-8", mode="a")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(logging.INFO)

def _label_for_value(pairs: list[tuple[str, str]], value: str) -> str:
    for lab, v in pairs:
        if v == value:
            return lab
    return pairs[0][0]


def _value_for_label(pairs: list[tuple[str, str]], label: str) -> str:
    for lab, v in pairs:
        if lab == label:
            return v
    return pairs[0][1]


@dataclass
class OrValueRowWidgets:
    """Zusätzlicher Wert innerhalb eines Kriteriums (ODER-Alternative)."""

    frame: ctk.CTkFrame
    entry: ctk.CTkEntry
    remove_btn: ctk.CTkButton


@dataclass
class CriterionBlockWidgets:
    """
    Ein Kriterium für die Regel: Typ + Bedingung + ein oder mehrere Werte (ODER).

    „+ ODER“ fügt weitere Werte hinzu; mehrere solche Blöcke in einer Regel sind UND-verknüpft.
    """

    block_frame: ctk.CTkFrame
    header_frame: ctk.CTkFrame
    prefix_lbl: ctk.CTkLabel
    if_menu: ctk.CTkOptionMenu
    cond_menu: ctk.CTkOptionMenu
    first_value_entry: ctk.CTkEntry
    or_button: ctk.CTkButton
    and_remove_btn: Optional[ctk.CTkButton] = None
    or_rows: list[OrValueRowWidgets] = field(default_factory=list)


@dataclass
class RuleBlockWidgets:
    """
    Eine komplette Regel: Titelleiste (Priorität, Einklappen, Reihenfolge),
    darunter der einklappbare Inhalt (Kriterien, Aktion).
    """

    outer: ctk.CTkFrame
    title_row: ctk.CTkFrame
    rule_index_lbl: ctk.CTkLabel
    summary_lbl: ctk.CTkLabel
    collapse_btn: ctk.CTkButton
    up_btn: ctk.CTkButton
    down_btn: ctk.CTkButton
    body: ctk.CTkFrame
    criteria_box: ctk.CTkFrame
    criteria_rows: list[CriterionBlockWidgets] = field(default_factory=list)
    action_menu: Optional[ctk.CTkOptionMenu] = None
    target_btn: Optional[ctk.CTkButton] = None
    target_path: str = ""
    collapsed: bool = False


class DownloadSorterApp(ctk.CTk):
    """Hauptfenster: Ordnerwahl, Regeln, Start/Stopp."""

    def _tr(self, key: str, **kwargs: Any) -> str:
        return t(self._lang, key, **kwargs)

    def _pairs_if(self) -> list[tuple[str, IfType]]:
        return pairs_if(self._lang)

    def _pairs_cond(self) -> list[tuple[str, Condition]]:
        return pairs_cond(self._lang)

    def _pairs_action(self) -> list[tuple[str, Action]]:
        return pairs_action(self._lang)

    def _button_kw(
        self,
        variant: str = "ghost",
        *,
        width: Optional[int] = None,
        height: int = BTN_H,
        font: Any = None,
    ) -> dict[str, Any]:
        p = self._pal
        kw: dict[str, Any] = dict(
            corner_radius=BTN_RADIUS,
            height=height,
            border_width=2,
            border_color=p["btn_rim"],
            font=font or FONT_BTN,
        )
        if width is not None:
            kw["width"] = width
        if variant == "ghost":
            kw.update(
                fg_color=p["panel_elev"],
                hover_color=p["border"],
                text_color=p["text"],
            )
        elif variant == "primary":
            kw.update(
                fg_color=p["cyan_dim"],
                hover_color=p["cyan"],
                text_color=p["text"],
                border_color=p["primary_border"],
            )
        elif variant == "danger":
            kw.update(
                fg_color=p["stop"],
                hover_color="#b71c1c",
                text_color="#ffffff",
                border_color="#5c0000",
            )
        return kw

    def _sync_appearance_segment(self) -> None:
        if self._seg_appearance is None:
            return
        d, l = self._tr("appearance_dark"), self._tr("appearance_light")
        self._seg_appearance.configure(values=(d, l))
        cur = getattr(self._cfg, "ui_appearance", "dark")
        self._seg_appearance.set(l if cur == "light" else d)

    def _on_appearance_segment(self, choice: str) -> None:
        light_l = self._tr("appearance_light")
        mode = "light" if choice == light_l else "dark"
        if mode == getattr(self._cfg, "ui_appearance", "dark"):
            return
        self._cfg.ui_appearance = mode
        ctk.set_appearance_mode("light" if mode == "light" else "dark")
        self._pal = dict(PALETTE_LIGHT if mode == "light" else PALETTE_DARK)
        self._cancel_scheduled_apply_palette()
        self._apply_palette()
        self._persist()

    def _on_main_tab_segment(self, choice: str) -> None:
        if self._frm_tab_profile is None or self._frm_tab_rules is None or self._frame_center is None:
            return
        if choice == self._str_tab_rules:
            self._active_main_tab = "rules"
            self._frm_tab_profile.grid_remove()
            self._frm_tab_rules.grid(row=1, column=0, sticky="nsew")
        else:
            self._active_main_tab = "profile"
            self._frm_tab_rules.grid_remove()
            self._frm_tab_profile.grid(row=1, column=0, sticky="nsew")

    def _toggle_rule_help(self) -> None:
        self._rule_help_expanded = not self._rule_help_expanded
        if self._frm_rule_help is None or self._btn_rule_help_toggle is None:
            return
        if self._rule_help_expanded:
            self._frm_rule_help.pack(fill="x", pady=(0, 8), after=self._btn_rule_help_toggle)
            self._btn_rule_help_toggle.configure(text=self._tr("help_hide"))
        else:
            self._frm_rule_help.pack_forget()
            self._btn_rule_help_toggle.configure(text=self._tr("help_show"))

    def _cancel_save_config_pending(self) -> None:
        if self._save_config_after_id is not None:
            try:
                self.after_cancel(self._save_config_after_id)
            except Exception:
                pass
            self._save_config_after_id = None

    def _schedule_save_config(self) -> None:
        """config.json schreiben leicht verzögert — viele schnelle Änderungen = ein Schreibvorgang."""

        def _run() -> None:
            self._save_config_after_id = None
            try:
                save_config(self._cfg, self._base_dir)
            except OSError:
                _LOG.exception("save_config fehlgeschlagen")

        self._cancel_save_config_pending()
        self._save_config_after_id = self.after(PERSIST_SAVE_DEBOUNCE_MS, _run)

    def _cancel_watch_empty_hint_pending(self) -> None:
        if self._watch_empty_after_id is not None:
            try:
                self.after_cancel(self._watch_empty_after_id)
            except Exception:
                pass
            self._watch_empty_after_id = None

    def _schedule_watch_empty_hint(self) -> None:
        def _run() -> None:
            self._watch_empty_after_id = None
            self._update_watch_empty_hint()

        self._cancel_watch_empty_hint_pending()
        self._watch_empty_after_id = self.after(WATCH_EMPTY_HINT_DEBOUNCE_MS, _run)

    def _update_watch_empty_hint(self) -> None:
        if self._frm_watch_empty is None or self._lbl_watch_empty is None:
            return
        active = self._active_running_profiles()
        cur_empty = not self._watch_folder_var.get().strip()
        if not active and cur_empty:
            self._lbl_watch_empty.configure(text=self._tr("watch_empty_hint"))
            self._frm_watch_empty.pack(fill="x", pady=(6, 0))
        else:
            self._frm_watch_empty.pack_forget()

    def _on_hotkey_f5(self, _event: Any = None) -> None:
        try:
            self._manual_scan_folder()
        except Exception:
            _LOG.exception("Hotkey F5 scan")

    def _on_hotkey_escape(self, _event: Any = None) -> Optional[str]:
        if self._running_watchers_count() == 0:
            return None
        if not messagebox.askyesno(
            self._tr("escape_stop_title"),
            self._tr("escape_stop_message"),
            parent=self,
        ):
            return "break"
        self._stop_all_watchers()
        return "break"

    def _cancel_scheduled_apply_palette(self) -> None:
        if self._palette_apply_after_id is not None:
            try:
                self.after_cancel(self._palette_apply_after_id)
            except Exception:
                pass
            self._palette_apply_after_id = None

    def _schedule_apply_palette(self) -> None:
        """Theming gebündelt (ein after_idle), vermeidet doppelte Läufe beim Start / Regel-Neuaufbau."""

        def _run() -> None:
            self._palette_apply_after_id = None
            self._apply_palette()

        self._cancel_scheduled_apply_palette()
        self._palette_apply_after_id = self.after_idle(_run)

    def _apply_palette(self) -> None:
        """Farben aus self._pal auf alle gespeicherten Widgets (Dark/Light)."""
        p = self._pal
        self.configure(fg_color=p["bg"])
        if self._frame_top is not None:
            self._frame_top.configure(fg_color=p["panel"])
        if self._frame_center is not None:
            self._frame_center.configure(fg_color=p["bg"])
        if self._frame_bottom is not None:
            self._frame_bottom.configure(fg_color=p["panel_elev"])
        if self._card_profile is not None:
            self._card_profile.configure(fg_color=p["panel_elev"], border_color=p["border"])
        if self._card_rules is not None:
            self._card_rules.configure(fg_color=p["panel_elev"], border_color=p["border"])
        if self._rules_loading_overlay is not None:
            self._rules_loading_overlay.configure(fg_color=p["panel_elev"])
        if self._lbl_title_top is not None:
            self._lbl_title_top.configure(text_color=p["text"])
        if self._lbl_lang is not None:
            self._lbl_lang.configure(text_color=p["text"])
        if self._lbl_hotkeys is not None:
            self._lbl_hotkeys.configure(text_color=p["muted"], text=self._tr("hotkeys_hint"))
        if self._lbl_profile_editor_hint is not None:
            self._lbl_profile_editor_hint.configure(text_color=p["muted"])
        if self._lbl_profile_activate_title is not None:
            self._lbl_profile_activate_title.configure(text_color=p["text"])
        if self._lbl_watch_empty is not None:
            self._lbl_watch_empty.configure(text_color=p["muted"])
        if self._lbl_rule_help is not None:
            self._lbl_rule_help.configure(text_color=p["muted"])
        if self._seg_appearance is not None:
            self._seg_appearance.configure(
                fg_color=p["panel"],
                selected_color=p["cyan_dim"],
                selected_hover_color=p["cyan"],
                unselected_color=p["panel_elev"],
                unselected_hover_color=p["border"],
                text_color=p["text"],
            )
        if self._seg_main_tab is not None:
            self._seg_main_tab.configure(
                fg_color=p["panel"],
                selected_color=p["cyan_dim"],
                selected_hover_color=p["cyan"],
                unselected_color=p["panel_elev"],
                unselected_hover_color=p["border"],
                text_color=p["text"],
            )
        om_kw = dict(
            fg_color=p["panel"],
            button_color=p["panel_elev"],
            button_hover_color=p["border"],
            dropdown_fg_color=p["panel_elev"],
            dropdown_hover_color=p["border"],
            text_color=p["text"],
        )
        if self._profile_menu is not None:
            self._profile_menu.configure(**om_kw)
        if self._profile_menu_rules is not None:
            self._profile_menu_rules.configure(**om_kw)
        if self._lbl_rules_tab_profile is not None:
            self._lbl_rules_tab_profile.configure(text_color=p["text"])
        if self._lang_menu is not None:
            self._lang_menu.configure(**om_kw)
        if self._entry_profile_name is not None:
            self._entry_profile_name.configure(fg_color=p["panel"], border_color=p["border"], text_color=p["text"])
        if self._btn_browse is not None:
            self._btn_browse.configure(**self._button_kw("primary", width=128))
        if self._btn_add_profile is not None:
            self._btn_add_profile.configure(**self._button_kw("ghost", width=130))
        if self._btn_remove_profile is not None:
            self._btn_remove_profile.configure(**self._button_kw("ghost", width=120))
        if self._btn_profile_activity_collapse is not None:
            self._btn_profile_activity_collapse.configure(**self._button_kw("ghost", width=140, height=26))
        if self._btn_rule_help_toggle is not None:
            self._btn_rule_help_toggle.configure(**self._button_kw("ghost", width=168, height=28))
        if self._btn_add_rule is not None:
            self._btn_add_rule.configure(**self._button_kw("ghost"))
        if self._btn_remove_rule is not None:
            self._btn_remove_rule.configure(**self._button_kw("ghost"))
        if self._btn_export is not None:
            self._btn_export.configure(**self._button_kw("ghost", width=150))
        if self._btn_import is not None:
            self._btn_import.configure(**self._button_kw("ghost", width=150))
        if self._btn_scan is not None:
            self._btn_scan.configure(**self._button_kw("primary", width=140))
        if self._btn_stop_all is not None:
            self._btn_stop_all.configure(**self._button_kw("danger", width=120))
        if self._status is not None:
            self._status.configure(text_color=p["text"])
        if self._rules_scroll is not None:
            self._rules_scroll.configure(fg_color=p["panel"], label_text_color=p["text"])
        if self._switch_autostart is not None:
            # configure() kann beim CTkSwitch den command auslösen — ohne Flag → Registry-Spam/Lag.
            prev_sw = self._autostart_switch_programmatic
            self._autostart_switch_programmatic = True
            try:
                self._switch_autostart.configure(
                    text_color=p["text"],
                    progress_color=p["cyan"],
                    button_color=p["panel"],
                    button_hover_color=p["panel_elev"],
                    fg_color=p["panel_elev"],
                )
            finally:
                self._autostart_switch_programmatic = prev_sw
        for cb in self._profile_run_widgets.values():
            # CTkCheckBox: kein fg_color="transparent" (ValueError je nach CTk-Version).
            cb.configure(
                fg_color=p["panel_elev"],
                text_color=p["text"],
                hover_color=p["border"],
            )
        for btn in self._profile_stop_buttons.values():
            kw = self._button_kw(
                "danger",
                width=PROFILE_ROW_STOP_BTN_W,
                height=PROFILE_ROW_STOP_BTN_H,
                font=("Segoe UI Semibold", 10),
            )
            kw["corner_radius"] = 6
            btn.configure(**kw)
        for block in self._rule_blocks:
            block.outer.configure(fg_color=p["panel_elev"], border_color=p["border"])
            block.summary_lbl.configure(text_color=p["muted"])
            block.collapse_btn.configure(**self._button_kw("ghost", width=UI_COLLAPSE_W))
            block.up_btn.configure(**self._button_kw("ghost", width=36))
            block.down_btn.configure(**self._button_kw("ghost", width=36))
        self._refresh_profile_status_indicators()

    def __init__(self, *, autostart_watch: bool = False) -> None:
        self._base_dir = application_base_dir()
        _setup_file_logging(self._base_dir)
        self._cfg = load_config(self._base_dir)
        self._lang = normalize_lang(self._cfg.ui_language)
        mode = getattr(self._cfg, "ui_appearance", "dark") or "dark"
        if mode not in ("dark", "light"):
            mode = "dark"
        self._cfg.ui_appearance = mode
        ctk.set_appearance_mode("light" if mode == "light" else "dark")
        self._pal: dict[str, str] = dict(PALETTE_LIGHT if mode == "light" else PALETTE_DARK)
        super().__init__(fg_color=self._pal["bg"])

        self._watch_folder_var = ctk.StringVar(value="")
        self._profile_name_var = ctk.StringVar(value="")
        self._current_profile_id: str = self._cfg.profiles[0].profile_id
        self._rule_blocks: list[RuleBlockWidgets] = []
        self._config_after_id: Optional[Any] = None
        self._autostart_watch = autostart_watch
        self._switch_autostart: Optional[ctk.CTkSwitch] = None
        self._autostart_switch_programmatic = False
        self._autostart_apply_after_id: Optional[Any] = None
        self._autostart_op_seq: int = 0
        self._watch_toggle_programmatic = False
        self._rule_help_expanded: bool = False
        self._str_tab_profile: str = ""
        self._str_tab_rules: str = ""
        self._active_main_tab: str = "profile"

        self._controllers: dict[str, WatchController] = {}
        self._profile_menu: Optional[ctk.CTkOptionMenu] = None
        self._profile_menu_rules: Optional[ctk.CTkOptionMenu] = None
        self._lbl_rules_tab_profile: Optional[ctk.CTkLabel] = None
        self._profile_run_widgets: dict[str, ctk.CTkCheckBox] = {}
        self._profile_status_dots: dict[str, ctk.CTkFrame] = {}
        self._profile_stop_buttons: dict[str, ctk.CTkButton] = {}
        self._frm_profile_activity: Optional[ctk.CTkFrame] = None
        self._lbl_profile_editor_hint: Optional[ctk.CTkLabel] = None
        self._frm_profile_run_body: Optional[ctk.CTkFrame] = None
        self._frm_profile_run_inner: Optional[ctk.CTkFrame] = None
        self._btn_profile_activity_collapse: Optional[ctk.CTkButton] = None
        self._lbl_profile_activate_title: Optional[ctk.CTkLabel] = None
        self._profile_activity_collapsed: bool = False
        self._frame_top: Optional[ctk.CTkFrame] = None
        self._frame_center: Optional[ctk.CTkFrame] = None
        self._frame_bottom: Optional[ctk.CTkFrame] = None
        self._seg_main_tab: Optional[ctk.CTkSegmentedButton] = None
        self._seg_appearance: Optional[ctk.CTkSegmentedButton] = None
        self._frm_tab_profile: Optional[ctk.CTkFrame] = None
        self._frm_tab_rules: Optional[ctk.CTkFrame] = None
        self._card_profile: Optional[ctk.CTkFrame] = None
        self._card_rules: Optional[ctk.CTkFrame] = None
        self._btn_rule_help_toggle: Optional[ctk.CTkButton] = None
        self._frm_rule_help: Optional[ctk.CTkFrame] = None
        self._frm_watch_empty: Optional[ctk.CTkFrame] = None
        self._frm_rules_btn_row: Optional[ctk.CTkFrame] = None
        self._frm_rules_scroll_host: Optional[ctk.CTkFrame] = None
        self._rules_loading_overlay: Optional[ctk.CTkFrame] = None
        self._palette_apply_after_id: Optional[Any] = None
        self._save_config_after_id: Optional[Any] = None
        self._watch_empty_after_id: Optional[Any] = None
        self._closing: bool = False

        self.geometry("940x700")
        self.minsize(800, 520)
        ctk.set_default_color_theme("blue")

        self._build_layout()
        self._load_current_profile_into_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        if self._autostart_watch:
            self.after(400, self._apply_autostart_watch)

    def _build_layout(self) -> None:
        p = self._pal
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._frame_top = ctk.CTkFrame(self, corner_radius=0, fg_color=p["panel"])
        self._frame_top.grid(row=0, column=0, sticky="ew")
        top_in = ctk.CTkFrame(self._frame_top, fg_color="transparent")
        top_in.pack(fill="x", padx=14, pady=10)

        self._lbl_title_top = ctk.CTkLabel(
            top_in, text="", font=FONT_APP_TITLE, fg_color="transparent"
        )
        self._lbl_title_top.pack(side="left", padx=(0, 16))

        self._seg_appearance = ctk.CTkSegmentedButton(
            top_in,
            values=(self._tr("appearance_dark"), self._tr("appearance_light")),
            width=168,
            command=self._on_appearance_segment,
            font=FONT_UI_SM,
        )
        self._seg_appearance.pack(side="left", padx=(0, 14))
        self._sync_appearance_segment()

        self._lbl_lang = ctk.CTkLabel(
            top_in, text="", width=72, anchor="e", fg_color="transparent", font=FONT_UI
        )
        self._lbl_lang.pack(side="left", padx=(0, 4))
        self._lang_menu = ctk.CTkOptionMenu(
            top_in,
            values=list(LANG_MENU_LABELS),
            width=100,
            command=self._on_language_changed,
            font=FONT_UI_SM,
        )
        self._lang_menu.pack(side="left")

        self._frame_center = ctk.CTkFrame(self, fg_color=p["bg"])
        self._frame_center.grid(row=1, column=0, sticky="nsew", padx=12, pady=(4, 6))
        self._frame_center.grid_columnconfigure(0, weight=1)
        self._frame_center.grid_rowconfigure(1, weight=1)

        tab_row = ctk.CTkFrame(self._frame_center, fg_color="transparent")
        tab_row.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        tab_row.grid_columnconfigure(1, weight=1)

        self._str_tab_profile = self._tr("tab_profile")
        self._str_tab_rules = self._tr("tab_rules")
        self._seg_main_tab = ctk.CTkSegmentedButton(
            tab_row,
            values=(self._str_tab_profile, self._str_tab_rules),
            font=FONT_UI_SM,
            command=self._on_main_tab_segment,
        )
        self._seg_main_tab.set(self._str_tab_profile)
        self._seg_main_tab.grid(row=0, column=0, sticky="w")

        self._lbl_hotkeys = ctk.CTkLabel(
            tab_row,
            text="",
            font=FONT_HINT,
            fg_color="transparent",
            anchor="e",
            justify="right",
        )
        self._lbl_hotkeys.grid(row=0, column=1, sticky="e", padx=(12, 0))

        self._frm_tab_profile = ctk.CTkFrame(self._frame_center, fg_color="transparent")
        self._frm_tab_profile.grid(row=1, column=0, sticky="nsew")
        self._frm_tab_profile.grid_columnconfigure(0, weight=1)
        self._frm_tab_profile.grid_rowconfigure(0, weight=1)

        self._card_profile = ctk.CTkFrame(
            self._frm_tab_profile,
            corner_radius=12,
            border_width=1,
            fg_color=p["panel_elev"],
            border_color=p["border"],
        )
        self._card_profile.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        prof_inner = ctk.CTkFrame(self._card_profile, fg_color="transparent")
        prof_inner.pack(fill="both", expand=True, padx=12, pady=12)

        row_prof = ctk.CTkFrame(prof_inner, fg_color="transparent")
        row_prof.pack(fill="x", pady=(0, 4))
        self._lbl_profile = ctk.CTkLabel(row_prof, text="", width=52, anchor="w", font=FONT_UI)
        self._lbl_profile.pack(side="left", padx=(0, 6))
        menu_vals = self._profile_menu_choices()
        self._profile_menu = ctk.CTkOptionMenu(
            row_prof,
            values=menu_vals if menu_vals else ("1.",),
            width=200,
            command=self._on_profile_menu_changed,
            font=FONT_UI_SM,
        )
        self._profile_menu.pack(side="left", padx=(0, 8))
        self._lbl_profile_name = ctk.CTkLabel(row_prof, text="", width=44, anchor="e", font=FONT_UI)
        self._lbl_profile_name.pack(side="left", padx=(0, 4))
        self._entry_profile_name = ctk.CTkEntry(
            row_prof, textvariable=self._profile_name_var, width=140, font=FONT_UI_SM
        )
        self._entry_profile_name.pack(side="left", padx=(0, 8))
        self._btn_add_profile = ctk.CTkButton(
            row_prof, text="", command=self._add_profile, **self._button_kw("ghost", width=130)
        )
        self._btn_add_profile.pack(side="left", padx=(0, 6))
        self._btn_remove_profile = ctk.CTkButton(
            row_prof, text="", command=self._remove_profile, **self._button_kw("ghost", width=120)
        )
        self._btn_remove_profile.pack(side="left")

        self._frm_profile_activity = ctk.CTkFrame(prof_inner, fg_color="transparent")
        self._frm_profile_activity.pack(fill="x", pady=(4, 6))
        self._lbl_profile_editor_hint = ctk.CTkLabel(
            self._frm_profile_activity,
            text="",
            anchor="w",
            justify="left",
            wraplength=860,
            font=FONT_HINT,
            fg_color="transparent",
        )
        self._lbl_profile_editor_hint.pack(fill="x", padx=2, pady=(0, 4))

        act_header = ctk.CTkFrame(self._frm_profile_activity, fg_color="transparent")
        act_header.pack(fill="x")
        self._lbl_profile_activate_title = ctk.CTkLabel(act_header, text="", anchor="w", font=FONT_UI)
        self._lbl_profile_activate_title.pack(side="left", padx=(0, 8))
        self._btn_profile_activity_collapse = ctk.CTkButton(
            act_header,
            text="",
            command=self._toggle_profile_activity_section,
            **self._button_kw("ghost", width=140, height=26),
        )
        self._btn_profile_activity_collapse.pack(side="left")

        self._frm_profile_run_body = ctk.CTkFrame(self._frm_profile_activity, fg_color="transparent")
        self._frm_profile_run_body.pack(fill="x", pady=(4, 0))
        self._frm_profile_run_inner = ctk.CTkFrame(self._frm_profile_run_body, fg_color="transparent")
        self._frm_profile_run_inner.pack(fill="x")

        row_watch = ctk.CTkFrame(prof_inner, fg_color="transparent")
        row_watch.pack(fill="x", pady=(6, 0))

        self._lbl_watch = ctk.CTkLabel(row_watch, text="", font=FONT_UI)
        self._lbl_watch.pack(side="left", padx=(0, 6))
        self._watch_lbl = ctk.CTkLabel(
            row_watch,
            text="",
            anchor="nw",
            justify="left",
            wraplength=520,
            font=FONT_UI_SM,
            fg_color="transparent",
        )
        self._watch_lbl.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._btn_browse = ctk.CTkButton(
            row_watch, text="", command=self._pick_watch_folder, **self._button_kw("primary", width=128)
        )
        self._btn_browse.pack(side="right")

        self._frm_watch_empty = ctk.CTkFrame(prof_inner, fg_color="transparent")
        self._lbl_watch_empty = ctk.CTkLabel(
            self._frm_watch_empty,
            text="",
            font=FONT_HINT,
            fg_color="transparent",
            anchor="w",
            justify="left",
            wraplength=820,
        )
        self._lbl_watch_empty.pack(anchor="w", padx=2)

        if autostart_win.is_windows():
            row_auto = ctk.CTkFrame(prof_inner, fg_color="transparent")
            row_auto.pack(fill="x", pady=(10, 0))
            self._switch_autostart = ctk.CTkSwitch(
                row_auto,
                text="",
                command=self._on_autostart_toggled,
                font=FONT_UI_SM,
            )
            self._switch_autostart.pack(side="left")
            self._autostart_switch_programmatic = True
            if autostart_win.autostart_enabled():
                self._switch_autostart.select()
            else:
                self._switch_autostart.deselect()

            def _clear_autostart_prog_flag() -> None:
                self._autostart_switch_programmatic = False

            self.after(0, _clear_autostart_prog_flag)

        self._frm_tab_rules = ctk.CTkFrame(self._frame_center, fg_color="transparent")
        self._frm_tab_rules.grid_columnconfigure(0, weight=1)
        self._frm_tab_rules.grid_rowconfigure(0, weight=1)

        self._card_rules = ctk.CTkFrame(
            self._frm_tab_rules,
            corner_radius=12,
            border_width=1,
            fg_color=p["panel_elev"],
            border_color=p["border"],
        )
        self._card_rules.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        rules_inner = ctk.CTkFrame(self._card_rules, fg_color="transparent")
        rules_inner.pack(fill="both", expand=True, padx=12, pady=12)

        row_rules_profile = ctk.CTkFrame(rules_inner, fg_color="transparent")
        row_rules_profile.pack(fill="x", pady=(0, 10))
        self._lbl_rules_tab_profile = ctk.CTkLabel(
            row_rules_profile,
            text="",
            font=FONT_UI,
            fg_color="transparent",
        )
        self._lbl_rules_tab_profile.pack(side="left", padx=(0, 8))
        menu_vals_rules = self._profile_menu_choices()
        self._profile_menu_rules = ctk.CTkOptionMenu(
            row_rules_profile,
            values=menu_vals_rules if menu_vals_rules else ("1.",),
            width=220,
            command=self._on_profile_menu_changed,
            font=FONT_UI_SM,
        )
        self._profile_menu_rules.pack(side="left")

        self._btn_rule_help_toggle = ctk.CTkButton(
            rules_inner,
            text="",
            command=self._toggle_rule_help,
            **self._button_kw("ghost", width=172, height=28),
        )
        self._btn_rule_help_toggle.pack(anchor="w", pady=(0, 4))

        self._frm_rule_help = ctk.CTkFrame(rules_inner, fg_color="transparent")
        self._lbl_rule_help = ctk.CTkLabel(
            self._frm_rule_help,
            text="",
            anchor="w",
            wraplength=880,
            justify="left",
            font=FONT_HINT,
            fg_color="transparent",
        )
        self._lbl_rule_help.pack(anchor="w", fill="x")

        btn_row = ctk.CTkFrame(rules_inner, fg_color="transparent")
        self._frm_rules_btn_row = btn_row
        btn_row.pack(fill="x", pady=(0, 8))
        self._btn_add_rule = ctk.CTkButton(
            btn_row, text="", command=self._add_rule_block, **self._button_kw("ghost")
        )
        self._btn_add_rule.pack(side="left", padx=(0, 8))
        self._btn_remove_rule = ctk.CTkButton(
            btn_row, text="", command=self._remove_last_rule_block, **self._button_kw("ghost")
        )
        self._btn_remove_rule.pack(side="left", padx=(0, 8))
        self._btn_export = ctk.CTkButton(
            btn_row, text="", command=self._export_rules_file, **self._button_kw("ghost", width=150)
        )
        self._btn_export.pack(side="left", padx=(0, 8))
        self._btn_import = ctk.CTkButton(
            btn_row, text="", command=self._import_rules_file, **self._button_kw("ghost", width=150)
        )
        self._btn_import.pack(side="left")

        self._frm_rules_scroll_host = ctk.CTkFrame(rules_inner, fg_color="transparent")
        self._frm_rules_scroll_host.pack(fill="both", expand=True)
        self._rules_scroll = ctk.CTkScrollableFrame(
            self._frm_rules_scroll_host, label_text="", corner_radius=10
        )
        self._rules_scroll.pack(fill="both", expand=True)
        self._rules_loading_overlay = ctk.CTkFrame(
            self._frm_rules_scroll_host,
            fg_color=p["panel_elev"],
            corner_radius=10,
        )

        self._frm_tab_rules.grid(row=1, column=0, sticky="nsew")
        self._frm_tab_rules.grid_remove()

        self._frame_bottom = ctk.CTkFrame(self, corner_radius=0, fg_color=p["panel_elev"])
        self._frame_bottom.grid(row=2, column=0, sticky="ew")
        bot_in = ctk.CTkFrame(self._frame_bottom, fg_color="transparent")
        bot_in.pack(fill="x", padx=14, pady=10)
        self._btn_stop_all = ctk.CTkButton(
            bot_in,
            text="",
            command=self._stop_all_watchers,
            **self._button_kw("danger", width=120),
        )
        self._btn_stop_all.pack(side="left", padx=(0, 8))
        self._btn_scan = ctk.CTkButton(
            bot_in, text="", command=self._manual_scan_folder, **self._button_kw("primary", width=140)
        )
        self._btn_scan.pack(side="left", padx=(0, 8))
        self._status = ctk.CTkLabel(
            bot_in, text="", anchor="nw", justify="left", wraplength=480, font=FONT_UI_SM, fg_color="transparent"
        )
        self._status.pack(side="left", fill="x", expand=True)

        self._watch_folder_var.trace_add("write", lambda *_: self._schedule_watch_empty_hint())

        self._refresh_static_texts()
        self._entry_profile_name.bind("<FocusOut>", self._on_profile_name_commit)
        self._entry_profile_name.bind("<Return>", self._on_profile_name_commit)
        self._rebuild_profile_run_ui()
        self._update_profile_editor_hint()
        self._update_watch_empty_hint()

        self.bind_all("<F5>", self._on_hotkey_f5)
        self.bind_all("<Escape>", self._on_hotkey_escape)

    def _profile_menu_choices(self) -> list[str]:
        return [f"{i + 1}. {p.name}" for i, p in enumerate(self._cfg.profiles)]

    def _current_profile(self) -> Optional[WatchProfile]:
        for p in self._cfg.profiles:
            if p.profile_id == self._current_profile_id:
                return p
        return self._cfg.profiles[0] if self._cfg.profiles else None

    def _profile_by_id(self, profile_id: str) -> Optional[WatchProfile]:
        for p in self._cfg.profiles:
            if p.profile_id == profile_id:
                return p
        return None

    def _running_watchers_count(self) -> int:
        return sum(1 for c in self._controllers.values() if c.is_running)

    def _active_running_profiles(self) -> list[WatchProfile]:
        """Profile, deren Observer gerade laufen (wirklich überwacht)."""
        out: list[WatchProfile] = []
        for p in self._cfg.profiles:
            ctrl = self._controllers.get(p.profile_id)
            if ctrl is not None and ctrl.is_running and p.watch_folder.strip():
                out.append(p)
        return out

    def _refresh_watch_folder_display(self) -> None:
        """Ordnerzeile: alle aktiven Überwachungen oder (sonst) Ordner des bearbeiteten Profils."""
        active = self._active_running_profiles()
        if self._lbl_watch is not None:
            self._lbl_watch.configure(
                text=self._tr("watch_folders_active") if active else self._tr("watch_folder"),
            )
        if self._watch_lbl is None:
            return
        if active:
            lines = [f"{p.name}: {self._shorten(p.watch_folder.strip(), 78)}" for p in active]
            self._watch_lbl.configure(text="\n".join(lines))
        else:
            cur = self._watch_folder_var.get().strip()
            self._watch_lbl.configure(text=cur or self._tr("preview_empty"))
        self._update_watch_empty_hint()

    def _flush_current_profile_from_ui(self) -> None:
        p = self._current_profile()
        if not p:
            return
        p.watch_folder = self._watch_folder_var.get().strip()
        p.rules = self._collect_rules_from_ui()
        name = self._profile_name_var.get().strip()
        if name:
            p.name = name
        if self._cfg.profiles:
            first = self._cfg.profiles[0]
            self._cfg.watch_folder = first.watch_folder
            self._cfg.rules = [Rule.from_dict(r.to_dict()) for r in first.rules]

    def _load_current_profile_into_ui(self) -> None:
        p = self._current_profile()
        if not p:
            return
        self._watch_folder_var.set(p.watch_folder or "")
        self._profile_name_var.set(p.name or "")
        self._set_rules_in_ui(p.rules or [])
        self._rebuild_profile_menu()
        self._update_profile_editor_hint()
        self._sync_profile_run_checkboxes_from_profiles()
        self._refresh_watch_folder_display()

    def _update_profile_editor_hint(self) -> None:
        if self._lbl_profile_editor_hint is None:
            return
        p = self._current_profile()
        if not p:
            self._lbl_profile_editor_hint.configure(text="")
            return
        labels = self._profile_menu_choices()
        try:
            idx = next(i for i, x in enumerate(self._cfg.profiles) if x.profile_id == p.profile_id)
            entry = labels[idx]
        except (StopIteration, ValueError, IndexError):
            entry = p.name
        self._lbl_profile_editor_hint.configure(text=self._tr("profile_editor_hint", entry=entry))

    def _rebuild_profile_run_ui(self) -> None:
        if self._frm_profile_run_inner is None:
            return
        for w in self._frm_profile_run_inner.winfo_children():
            w.destroy()
        self._profile_run_widgets.clear()
        self._profile_status_dots.clear()
        self._profile_stop_buttons.clear()
        n_prof = len(self._cfg.profiles)
        if self._btn_profile_activity_collapse is not None:
            if n_prof >= 4:
                self._btn_profile_activity_collapse.pack(side="left")
                self._btn_profile_activity_collapse.configure(
                    text=self._tr(
                        "profile_activity_expand"
                        if self._profile_activity_collapsed
                        else "profile_activity_collapse"
                    ),
                )
            else:
                self._btn_profile_activity_collapse.pack_forget()
                self._profile_activity_collapsed = False
        off = self._pal["status_dot_off"]
        for i, p in enumerate(self._cfg.profiles):
            label = f"{i + 1}. {p.name}"
            pid = p.profile_id
            row = ctk.CTkFrame(self._frm_profile_run_inner, fg_color="transparent")
            row.pack(anchor="w", fill="x", padx=4, pady=2)
            dot = ctk.CTkFrame(
                row,
                width=12,
                height=12,
                corner_radius=6,
                fg_color=off,
            )
            dot.pack(side="left", padx=(0, 8), pady=(2, 2))
            self._profile_status_dots[pid] = dot
            cb = ctk.CTkCheckBox(
                row,
                text=label,
                command=lambda p_id=pid: self._on_profile_run_clicked(p_id),
            )
            cb.pack(side="left", fill="x", expand=True, pady=0)
            self._profile_run_widgets[pid] = cb
            skw = self._button_kw(
                "danger",
                width=PROFILE_ROW_STOP_BTN_W,
                height=PROFILE_ROW_STOP_BTN_H,
                font=("Segoe UI Semibold", 10),
            )
            skw["corner_radius"] = 6
            stop_btn = ctk.CTkButton(
                row,
                text="\N{BLACK SQUARE}",
                command=lambda p_id=pid: self._on_profile_row_stop_clicked(p_id),
                **skw,
            )
            stop_btn.pack(side="left", padx=(6, 0), pady=0)
            self._profile_stop_buttons[pid] = stop_btn
        self._sync_profile_run_checkboxes_from_profiles()
        self._apply_profile_activity_collapse_layout()
        self._schedule_apply_palette()
        self._refresh_profile_status_indicators()

    def _apply_profile_activity_collapse_layout(self) -> None:
        if self._frm_profile_run_body is None:
            return
        if len(self._cfg.profiles) < 4:
            self._frm_profile_run_body.pack(fill="x", pady=(4, 0))
            return
        if self._profile_activity_collapsed:
            self._frm_profile_run_body.pack_forget()
        else:
            self._frm_profile_run_body.pack(fill="x", pady=(4, 0))

    def _toggle_profile_activity_section(self) -> None:
        if len(self._cfg.profiles) < 4:
            return
        self._profile_activity_collapsed = not self._profile_activity_collapsed
        self._apply_profile_activity_collapse_layout()
        if self._btn_profile_activity_collapse is not None:
            self._btn_profile_activity_collapse.configure(
                text=self._tr(
                    "profile_activity_expand"
                    if self._profile_activity_collapsed
                    else "profile_activity_collapse"
                ),
            )

    def _sync_profile_run_checkboxes_from_profiles(self) -> None:
        self._watch_toggle_programmatic = True
        try:
            for pid, cb in self._profile_run_widgets.items():
                prof = self._profile_by_id(pid)
                if prof is not None and prof.run_enabled:
                    cb.select()
                else:
                    cb.deselect()
        finally:
            self.after(0, lambda: setattr(self, "_watch_toggle_programmatic", False))

    def _profile_observer_running(self, profile_id: str) -> bool:
        ctrl = self._controllers.get(profile_id)
        return ctrl is not None and ctrl.is_running

    def _refresh_profile_status_indicators(self) -> None:
        """Grün = Überwachung aktiv, Rot = gestoppt; kleiner Stopp-Button nur bei laufender Überwachung."""
        if not self._profile_status_dots:
            return
        live = self._pal.get("status_dot_live", "#4caf50")
        off = self._pal.get("status_dot_off", "#e53935")
        for pid, dot in self._profile_status_dots.items():
            dot.configure(fg_color=live if self._profile_observer_running(pid) else off)
        for pid, btn in self._profile_stop_buttons.items():
            btn.configure(state="normal" if self._profile_observer_running(pid) else "disabled")

    def _on_profile_row_stop_clicked(self, profile_id: str) -> None:
        if not self._profile_observer_running(profile_id):
            return
        self._stop_profile_observer_async(profile_id)

    def _stop_profile_observer_async(self, profile_id: str) -> None:
        ctrl = self._controllers.pop(profile_id, None)
        if ctrl is None:
            return
        if not ctrl.is_running:
            if self._running_watchers_count() == 0:
                self._cancel_config_sync()
            self._update_multi_status()
            return

        def work() -> None:
            ctrl.stop()
            self.after(0, lambda: self._on_profile_observer_stop_finished(profile_id))

        threading.Thread(target=work, daemon=True).start()

    def _on_profile_observer_stop_finished(self, profile_id: str) -> None:
        if self._running_watchers_count() == 0:
            self._cancel_config_sync()
        self._update_multi_status()
        if self._status is not None:
            p = self._profile_by_id(profile_id)
            if p is not None:
                self._status.configure(text=self._tr("profile_observer_stopped", name=p.name))

    def _on_profile_run_clicked(self, profile_id: str) -> None:
        if self._watch_toggle_programmatic:
            return
        cb = self._profile_run_widgets.get(profile_id)
        if cb is None:
            return
        want = bool(cb.get())
        p = self._profile_by_id(profile_id)
        if p is None:
            return
        if profile_id == self._current_profile_id:
            self._flush_current_profile_from_ui()
        if want:
            wf = p.watch_folder.strip()
            if not wf or not Path(wf).is_dir():
                self._status.configure(text=self._tr("err_watch_folder_profile", name=p.name))
                self._watch_toggle_programmatic = True
                cb.deselect()
                self.after(0, lambda: setattr(self, "_watch_toggle_programmatic", False))
                p.run_enabled = False
                self._persist()
                return
            # Nur Vormerkung — Live-Überwachung und Einmal-Scan starten mit „Ordner jetzt prüfen“.
            p.run_enabled = True
            self._persist()
            self._update_multi_status()
        else:
            if profile_id == self._current_profile_id:
                self._flush_current_profile_from_ui()
            p.run_enabled = False
            self._stop_profile_controller(profile_id)
            self._persist()
            self._update_multi_status()

    def _rebuild_profile_menu(self) -> None:
        if self._profile_menu is None and self._profile_menu_rules is None:
            return
        labels = self._profile_menu_choices()
        vals = labels if labels else ("1.",)
        for m in (self._profile_menu, self._profile_menu_rules):
            if m is not None:
                m.configure(values=vals)
        cur = self._current_profile()
        if not cur:
            return
        try:
            idx = next(i for i, x in enumerate(self._cfg.profiles) if x.profile_id == cur.profile_id)
            sel = labels[idx]
        except (StopIteration, ValueError, IndexError):
            return
        for m in (self._profile_menu, self._profile_menu_rules):
            if m is not None:
                m.set(sel)

    def _on_profile_menu_changed(self, choice: str) -> None:
        labels = self._profile_menu_choices()
        try:
            idx = labels.index(choice)
        except ValueError:
            return
        if idx < 0 or idx >= len(self._cfg.profiles):
            return
        new_id = self._cfg.profiles[idx].profile_id
        if new_id == self._current_profile_id:
            return
        self._flush_current_profile_from_ui()
        self._current_profile_id = new_id
        self._load_current_profile_into_ui()
        self._persist()

    def _add_profile(self) -> None:
        self._flush_current_profile_from_ui()
        n = len(self._cfg.profiles) + 1
        np = WatchProfile(
            profile_id=str(uuid.uuid4()),
            name=f"Profil {n}",
            watch_folder="",
            rules=[Rule()],
            run_enabled=False,
        )
        self._cfg.profiles.append(np)
        self._current_profile_id = np.profile_id
        self._rebuild_profile_menu()
        self._load_current_profile_into_ui()
        self._persist()
        self._rebuild_profile_run_ui()

    def _remove_profile(self) -> None:
        if len(self._cfg.profiles) <= 1:
            messagebox.showinfo(self._tr("win_title"), self._tr("remove_profile_blocked"), parent=self)
            return
        self._flush_current_profile_from_ui()
        p = self._current_profile()
        if not p:
            return
        pid = p.profile_id
        self._stop_profile_controller(pid)
        self._cfg.profiles = [x for x in self._cfg.profiles if x.profile_id != pid]
        self._current_profile_id = self._cfg.profiles[0].profile_id
        self._rebuild_profile_menu()
        self._load_current_profile_into_ui()
        self._persist()
        self._rebuild_profile_run_ui()

    def _start_profile_controller(self, profile_id: str) -> bool:
        p = self._profile_by_id(profile_id)
        if not p:
            return False
        wf = p.watch_folder.strip()
        if not wf or not Path(wf).is_dir():
            self._status.configure(text=self._tr("err_watch_folder"))
            return False
        existing = self._controllers.get(profile_id)
        if existing is not None and existing.is_running:
            return True
        if existing is not None:
            self._stop_profile_controller(profile_id)
        ctrl = WatchController()
        try:
            snap = runtime_config_for_profile(self._cfg, p)
            ctrl.start(wf, snap)
        except Exception as e:
            self._status.configure(text=self._tr("err_start", error=str(e)))
            return False
        self._controllers[profile_id] = ctrl
        self._ensure_config_sync_scheduled()
        self._update_multi_status()
        return True

    def _stop_profile_controller(self, profile_id: str) -> None:
        ctrl = self._controllers.pop(profile_id, None)
        if ctrl is not None and ctrl.is_running:
            ctrl.stop()
        if self._running_watchers_count() == 0:
            self._cancel_config_sync()
        self._update_multi_status()

    def _stop_all_watchers(self) -> None:
        self._flush_current_profile_from_ui()
        self._cancel_config_sync()
        pairs: list[tuple[str, WatchController]] = []
        for pid in list(self._controllers.keys()):
            c = self._controllers.pop(pid, None)
            if c is not None:
                pairs.append((pid, c))
        if not pairs:
            self._on_stop_all_watchers_finished()
            return

        def work() -> None:
            for _pid, ctrl in pairs:
                if ctrl.is_running:
                    ctrl.stop()
            self.after(0, lambda: self._on_stop_all_watchers_finished())

        threading.Thread(target=work, daemon=True).start()

    def _on_stop_all_watchers_finished(self) -> None:
        self._persist()
        self._sync_profile_run_checkboxes_from_profiles()
        self._refresh_profile_status_indicators()
        self._update_multi_status()

    def _effective_profile_for_runtime(self, profile_id: str) -> WatchProfile:
        p = self._profile_by_id(profile_id)
        if p is None:
            return WatchProfile(profile_id=profile_id)
        if profile_id == self._current_profile_id:
            wf = self._watch_folder_var.get().strip()
            rules = self._collect_rules_from_ui()
            return WatchProfile(
                profile_id=p.profile_id,
                name=p.name,
                watch_folder=wf,
                rules=rules,
                run_enabled=p.run_enabled,
            )
        return WatchProfile(
            profile_id=p.profile_id,
            name=p.name,
            watch_folder=p.watch_folder,
            rules=[Rule.from_dict(r.to_dict()) for r in p.rules],
            run_enabled=p.run_enabled,
        )

    def _ensure_config_sync_scheduled(self) -> None:
        if self._config_after_id is not None:
            return
        if self._running_watchers_count() == 0:
            return
        self._config_after_id = self.after(CONFIG_SYNC_INTERVAL_MS, self._schedule_config_sync_all)

    def _schedule_config_sync_all(self) -> None:
        self._config_after_id = None
        if self._running_watchers_count() == 0:
            return
        self._flush_current_profile_from_ui()
        for pid, ctrl in list(self._controllers.items()):
            if not ctrl.is_running:
                continue
            prof = self._effective_profile_for_runtime(pid)
            try:
                ctrl.set_runtime_config(runtime_config_for_profile(self._cfg, prof))
            except Exception:
                _LOG.exception("Konfigurationssync fehlgeschlagen für Profil %s", pid)
        self._config_after_id = self.after(CONFIG_SYNC_INTERVAL_MS, self._schedule_config_sync_all)

    def _update_multi_status(self) -> None:
        self._refresh_watch_folder_display()
        self._refresh_profile_status_indicators()
        if self._status is None:
            return
        active = self._active_running_profiles()
        if not active:
            self._status.configure(text=self._tr("status_stopped"))
            return
        names = " · ".join(p.name for p in active)
        self._status.configure(text=self._tr("status_active_names", names=names))

    def _refresh_static_texts(self) -> None:
        self.title(self._tr("win_title"))
        if self._lbl_title_top is not None:
            self._lbl_title_top.configure(text=self._tr("win_title"))
        if self._lbl_hotkeys is not None:
            self._lbl_hotkeys.configure(text=self._tr("hotkeys_hint"))
        if self._seg_main_tab is not None:
            rules_tab = self._active_main_tab == "rules"
            self._str_tab_profile = self._tr("tab_profile")
            self._str_tab_rules = self._tr("tab_rules")
            self._seg_main_tab.configure(values=(self._str_tab_profile, self._str_tab_rules))
            self._seg_main_tab.set(self._str_tab_rules if rules_tab else self._str_tab_profile)
        self._lbl_profile.configure(text=self._tr("profile_label"))
        if self._lbl_rules_tab_profile is not None:
            self._lbl_rules_tab_profile.configure(text=self._tr("rules_tab_profile_caption"))
        self._lbl_profile_name.configure(text=self._tr("profile_name") + ":")
        self._btn_add_profile.configure(text=self._tr("add_profile"))
        self._btn_remove_profile.configure(text=self._tr("remove_profile"))
        self._lbl_watch.configure(text=self._tr("watch_folder"))
        if self._lbl_profile_activate_title is not None:
            self._lbl_profile_activate_title.configure(text=self._tr("profile_activate_section"))
        if self._btn_profile_activity_collapse is not None and len(self._cfg.profiles) >= 4:
            self._btn_profile_activity_collapse.configure(
                text=self._tr(
                    "profile_activity_expand"
                    if self._profile_activity_collapsed
                    else "profile_activity_collapse"
                ),
            )
        self._lbl_lang.configure(text=self._tr("language") + ":")
        self._lang_menu.set(LANG_MENU_LABELS[1] if self._lang == LANG_EN else LANG_MENU_LABELS[0])
        self._btn_browse.configure(text=self._tr("browse_folder"))
        self._lbl_rule_help.configure(text=self._tr("rule_help"))
        if self._btn_rule_help_toggle is not None:
            self._btn_rule_help_toggle.configure(
                text=self._tr("help_hide" if self._rule_help_expanded else "help_show")
            )
        self._btn_add_rule.configure(text=self._tr("add_rule"))
        self._btn_remove_rule.configure(text=self._tr("remove_last_rule"))
        self._btn_export.configure(text=self._tr("export_rules"))
        self._btn_import.configure(text=self._tr("import_rules"))
        self._rules_scroll.configure(label_text=self._tr("rule_editor"))
        self._btn_scan.configure(text=self._tr("scan_folder"))
        self._btn_stop_all.configure(text=self._tr("stop_all"))
        self._update_multi_status()
        if self._switch_autostart is not None:
            prev_sw = self._autostart_switch_programmatic
            self._autostart_switch_programmatic = True
            try:
                self._switch_autostart.configure(text=self._tr("autostart_win"))
            finally:
                self._autostart_switch_programmatic = prev_sw
        self._sync_appearance_segment()

    def _cancel_autostart_registry_pending(self) -> None:
        if self._autostart_apply_after_id is not None:
            try:
                self.after_cancel(self._autostart_apply_after_id)
            except Exception:
                pass
            self._autostart_apply_after_id = None

    def _on_autostart_toggled(self) -> None:
        if self._autostart_switch_programmatic or self._switch_autostart is None:
            return
        self._cancel_autostart_registry_pending()
        # after_idle: mehrere Switch-Events in einem Tick bündeln — ohne extra Wartezeit (kein after(120)).
        self._autostart_apply_after_id = self.after_idle(self._kick_autostart_registry_write)

    def _kick_autostart_registry_write(self) -> None:
        """Registry-Update im Hintergrund: UI-Thread blockiert nicht auf winreg/AV."""
        self._autostart_apply_after_id = None
        if self._switch_autostart is None or self._autostart_switch_programmatic:
            return
        if not autostart_win.is_windows():
            return
        want = bool(self._switch_autostart.get())
        self._autostart_op_seq += 1
        seq = self._autostart_op_seq

        def work() -> None:
            try:
                autostart_win.set_autostart(want)
            except OSError as e:
                self.after(0, lambda s=seq, err=e: self._autostart_registry_thread_failed(s, err))

        threading.Thread(target=work, daemon=True).start()

    def _autostart_registry_thread_failed(self, seq: int, err: OSError) -> None:
        if seq != self._autostart_op_seq or self._switch_autostart is None:
            return
        try:
            actual = autostart_win.autostart_enabled()
        except OSError:
            actual = False
        self._autostart_switch_programmatic = True
        if actual:
            self._switch_autostart.select()
        else:
            self._switch_autostart.deselect()
        self.after(0, lambda: setattr(self, "_autostart_switch_programmatic", False))
        messagebox.showerror(
            self._tr("win_title"),
            self._tr("autostart_registry_error", error=str(err)),
            parent=self,
        )

    def _apply_autostart_watch(self) -> None:
        """Nach Windows-Anmeldung (--autostart): alle mit run_enabled gestarteten Profile überwachen."""
        started = 0
        for p in self._cfg.profiles:
            if not p.run_enabled:
                continue
            wf = p.watch_folder.strip()
            if wf and Path(wf).is_dir():
                if self._start_profile_controller(p.profile_id):
                    started += 1
        self._load_current_profile_into_ui()
        if started > 0:
            self._update_multi_status()
            try:
                self.iconify()
            except Exception:
                pass
        else:
            self._update_multi_status()
            self._status.configure(text=self._tr("autostart_no_folder"))

    def _on_profile_name_commit(self, _evt: Any = None) -> None:
        self._flush_current_profile_from_ui()
        self._rebuild_profile_menu()
        self._rebuild_profile_run_ui()
        self._persist()

    def _on_language_changed(self, choice: str) -> None:
        new_lang = LANG_EN if choice == LANG_MENU_LABELS[1] else "de"
        if new_lang == self._lang:
            return
        self._flush_current_profile_from_ui()
        wf = self._watch_folder_var.get()
        self._lang = new_lang
        self._cfg.ui_language = self._lang
        self._refresh_static_texts()
        cur = self._current_profile()
        self._set_rules_in_ui(cur.rules if cur else [Rule()])
        self._watch_folder_var.set(wf)
        self._persist()
        self._refresh_all_rule_chrome()
        self._rebuild_profile_run_ui()

    def _pick_watch_folder(self) -> None:
        initial = self._watch_folder_var.get() or str(Path.home() / "Downloads")
        path = filedialog.askdirectory(initialdir=initial if Path(initial).is_dir() else None)
        if path:
            self._watch_folder_var.set(path)
            self._refresh_watch_folder_display()

    def _shorten(self, text: str, max_len: int = 48) -> str:
        t = text or ""
        if len(t) <= max_len:
            return t
        return "…" + t[-(max_len - 1) :]

    def _rule_block_preview(self, block: RuleBlockWidgets) -> str:
        """Kurztext für eingeklappte Regelkarte."""
        if not block.criteria_rows:
            return self._tr("preview_empty")
        parts: list[str] = []
        for i, cb in enumerate(block.criteria_rows):
            typ = cb.if_menu.get()
            vals = [cb.first_value_entry.get().strip()]
            vals.extend(o.entry.get().strip() for o in cb.or_rows)
            vals = [v for v in vals if v]
            vtxt = " ∨ ".join(self._shorten(v, 16) for v in vals[:5])
            if len(vals) > 5:
                vtxt += "…"
            and_p = f"{self._tr('and')} " if i else ""
            parts.append(f"{and_p}{typ} {vtxt}".strip() if vtxt else f"{and_p}{typ}")
        act = block.action_menu.get() if block.action_menu else "?"
        line = " · ".join(parts) + f" → {act}"
        if (
            block.target_path
            and block.action_menu
            and _value_for_label(self._pairs_action(), block.action_menu.get()) == "move"
        ):
            line += f" ({self._shorten(block.target_path, 28)})"
        return self._shorten(line, 120)

    def _update_rule_chrome(self, block: RuleBlockWidgets, index: int) -> None:
        """Regelnummer, ↑/↓, Einklappen-Text, Vorschau wenn zu."""
        n = len(self._rule_blocks)
        block.rule_index_lbl.configure(text=f"{self._tr('rule')} {index + 1}")
        block.up_btn.configure(state="disabled" if index <= 0 else "normal")
        block.down_btn.configure(state="disabled" if index >= n - 1 else "normal")
        if block.collapsed:
            block.summary_lbl.configure(text=self._rule_block_preview(block))
            block.collapse_btn.configure(text=self._tr("expand"))
        else:
            block.summary_lbl.configure(text="")
            block.collapse_btn.configure(text=self._tr("collapse"))

    def _refresh_all_rule_chrome(self) -> None:
        for i, b in enumerate(self._rule_blocks):
            self._update_rule_chrome(b, i)

    def _repack_rule_blocks(self) -> None:
        """Packt alle Regelkarten in der aktuellen Listenreihenfolge neu ein."""
        for b in self._rule_blocks:
            b.outer.pack_forget()
        for i, b in enumerate(self._rule_blocks):
            b.outer.pack(fill="x", pady=8, padx=2)
            self._update_rule_chrome(b, i)

    def _toggle_rule_collapse(self, block: RuleBlockWidgets) -> None:
        block.collapsed = not block.collapsed
        idx = self._rule_blocks.index(block)
        if block.collapsed:
            block.body.pack_forget()
        else:
            block.body.pack(fill="x", padx=0, pady=(0, 6), after=block.title_row)
        self._update_rule_chrome(block, idx)

    def _move_rule_block(self, block: RuleBlockWidgets, delta: int) -> None:
        idx = self._rule_blocks.index(block)
        new_i = idx + delta
        if new_i < 0 or new_i >= len(self._rule_blocks):
            return
        self._rule_blocks[idx], self._rule_blocks[new_i] = self._rule_blocks[new_i], self._rule_blocks[idx]
        self._repack_rule_blocks()

    def _make_criterion_block(
        self,
        block: RuleBlockWidgets,
        criterion: RuleCriterion,
        *,
        row_index: int,
    ) -> CriterionBlockWidgets:
        block_frame = ctk.CTkFrame(block.criteria_box)
        block_frame.pack(fill="x", pady=(2, 4))

        header = ctk.CTkFrame(block_frame)
        header.pack(fill="x")

        prefix = self._tr("when") if row_index == 0 else self._tr("and")
        prefix_lbl = ctk.CTkLabel(header, text=prefix, width=UI_PREFIX_W)
        prefix_lbl.grid(row=0, column=0, padx=(3, 2), pady=3, sticky="w")

        if_vals = [x[0] for x in self._pairs_if()]
        if_menu = ctk.CTkOptionMenu(header, values=if_vals, width=UI_IF_W)
        if_menu.set(_label_for_value(self._pairs_if(), criterion.if_type))
        if_menu.grid(row=0, column=1, padx=3, pady=3)

        cond_vals = [x[0] for x in self._pairs_cond()]
        cond_menu = ctk.CTkOptionMenu(header, values=cond_vals, width=UI_COND_W)
        cond_menu.set(_label_for_value(self._pairs_cond(), criterion.condition))
        cond_menu.grid(row=0, column=2, padx=3, pady=3)

        vals = list(criterion.values) if criterion.values else [""]
        first_text = vals[0] if vals else ""

        first_value_entry = ctk.CTkEntry(
            header,
            width=UI_VALUE_W,
            placeholder_text=self._tr("placeholder_ext"),
        )
        first_value_entry.insert(0, first_text)
        first_value_entry.grid(row=0, column=3, padx=3, pady=3, sticky="ew")
        header.grid_columnconfigure(3, weight=1)

        or_button = ctk.CTkButton(
            header,
            text=self._tr("or_add"),
            width=UI_OR_ADD_W,
            fg_color=("gray75", "gray30"),
        )
        or_button.grid(row=0, column=4, padx=(3, 2), pady=3)

        cb = CriterionBlockWidgets(
            block_frame=block_frame,
            header_frame=header,
            prefix_lbl=prefix_lbl,
            if_menu=if_menu,
            cond_menu=cond_menu,
            first_value_entry=first_value_entry,
            or_button=or_button,
            and_remove_btn=None,
            or_rows=[],
        )
        or_button.configure(command=lambda c=cb: self._add_or_alternative_row(c))

        for extra in vals[1:]:
            self._add_or_alternative_row(cb, initial=extra)

        return cb

    def _add_or_alternative_row(
        self,
        cb: CriterionBlockWidgets,
        *,
        initial: str = "",
    ) -> None:
        row_f = ctk.CTkFrame(cb.block_frame)
        row_f.pack(fill="x", pady=1)

        ctk.CTkLabel(row_f, text=self._tr("or"), width=UI_PREFIX_W).grid(
            row=0, column=0, padx=(3, 2), pady=2, sticky="w"
        )
        ctk.CTkLabel(row_f, text="", width=UI_IF_W).grid(row=0, column=1, padx=3, pady=2)
        ctk.CTkLabel(row_f, text="", width=UI_COND_W).grid(row=0, column=2, padx=3, pady=2)

        entry = ctk.CTkEntry(row_f, width=UI_VALUE_W, placeholder_text=self._tr("placeholder_alt"))
        entry.insert(0, initial)
        entry.grid(row=0, column=3, padx=3, pady=2, sticky="ew")
        row_f.grid_columnconfigure(3, weight=1)

        remove_btn = ctk.CTkButton(
            row_f,
            text="X",
            width=28,
            fg_color=("gray70", "gray35"),
        )
        remove_btn.grid(row=0, column=4, padx=(3, 2), pady=2)

        orw = OrValueRowWidgets(frame=row_f, entry=entry, remove_btn=remove_btn)
        remove_btn.configure(command=lambda c=cb, o=orw: self._remove_or_alternative_row(c, o))

        cb.or_rows.append(orw)

    def _remove_or_alternative_row(self, cb: CriterionBlockWidgets, orw: OrValueRowWidgets) -> None:
        if orw not in cb.or_rows:
            return
        cb.or_rows.remove(orw)
        orw.frame.destroy()

    def _refresh_and_remove_buttons(self, block: RuleBlockWidgets) -> None:
        """Bei mehreren Kriterien: je Block ein X zum Entfernen des UND-Kriteriums."""
        multi = len(block.criteria_rows) > 1
        for i, cb in enumerate(block.criteria_rows):
            if not multi:
                if cb.and_remove_btn is not None:
                    cb.and_remove_btn.destroy()
                    cb.and_remove_btn = None
                continue
            if cb.and_remove_btn is None:
                cb.and_remove_btn = ctk.CTkButton(
                    cb.header_frame,
                    text="X",
                    width=28,
                    fg_color=("gray70", "gray35"),
                    command=lambda b=block, idx=i: self._remove_criterion_block(b, idx),
                )
                cb.and_remove_btn.grid(row=0, column=5, padx=3, pady=3)
            else:
                cb.and_remove_btn.configure(
                    command=lambda b=block, idx=i: self._remove_criterion_block(b, idx),
                )

    def _relabel_criterion_prefixes(self, block: RuleBlockWidgets) -> None:
        for i, cb in enumerate(block.criteria_rows):
            cb.prefix_lbl.configure(text=self._tr("when") if i == 0 else self._tr("and"))

    def _add_criterion_to_block(self, block: RuleBlockWidgets) -> None:
        crit = RuleCriterion()
        idx = len(block.criteria_rows)
        cb = self._make_criterion_block(block, crit, row_index=idx)
        block.criteria_rows.append(cb)
        self._relabel_criterion_prefixes(block)
        self._refresh_and_remove_buttons(block)

    def _remove_criterion_block(self, block: RuleBlockWidgets, index: int) -> None:
        if len(block.criteria_rows) <= 1:
            return
        if index < 0 or index >= len(block.criteria_rows):
            return
        cb = block.criteria_rows.pop(index)
        cb.block_frame.destroy()
        self._relabel_criterion_prefixes(block)
        self._refresh_and_remove_buttons(block)

    def _make_rule_block(self, rule: Rule) -> RuleBlockWidgets:
        pal = self._pal
        outer = ctk.CTkFrame(
            self._rules_scroll,
            fg_color=pal["panel_elev"],
            border_width=1,
            border_color=pal["border"],
        )

        title_row = ctk.CTkFrame(outer, fg_color="transparent")
        title_row.pack(fill="x", padx=6, pady=(8, 4))

        rule_index_lbl = ctk.CTkLabel(title_row, text=f"{self._tr('rule')} ?", width=72, anchor="w")
        try:
            rule_index_lbl.configure(font=ctk.CTkFont(weight="bold"))
        except Exception:
            pass
        rule_index_lbl.grid(row=0, column=0, padx=(4, 6), sticky="w")

        summary_lbl = ctk.CTkLabel(title_row, text="", anchor="w", text_color=pal["muted"])
        summary_lbl.grid(row=0, column=1, padx=4, sticky="ew")
        title_row.grid_columnconfigure(1, weight=1)

        collapse_btn = ctk.CTkButton(
            title_row,
            text=self._tr("collapse"),
            **self._button_kw("ghost", width=UI_COLLAPSE_W),
        )
        collapse_btn.grid(row=0, column=2, padx=(4, 2))

        up_btn = ctk.CTkButton(title_row, text="↑", **self._button_kw("ghost", width=36))
        up_btn.grid(row=0, column=3, padx=2)
        down_btn = ctk.CTkButton(title_row, text="↓", **self._button_kw("ghost", width=36))
        down_btn.grid(row=0, column=4, padx=(2, 4))

        body = ctk.CTkFrame(outer, fg_color="transparent")

        criteria_box = ctk.CTkFrame(body)
        criteria_box.pack(fill="x", padx=8, pady=(4, 4))

        block = RuleBlockWidgets(
            outer=outer,
            title_row=title_row,
            rule_index_lbl=rule_index_lbl,
            summary_lbl=summary_lbl,
            collapse_btn=collapse_btn,
            up_btn=up_btn,
            down_btn=down_btn,
            body=body,
            criteria_box=criteria_box,
            target_path=rule.target_folder or "",
        )

        collapse_btn.configure(command=lambda b=block: self._toggle_rule_collapse(b))
        up_btn.configure(command=lambda b=block: self._move_rule_block(b, -1))
        down_btn.configure(command=lambda b=block: self._move_rule_block(b, 1))

        for i, c in enumerate(rule.criteria):
            cb = self._make_criterion_block(block, c, row_index=i)
            block.criteria_rows.append(cb)
        if not block.criteria_rows:
            block.criteria_rows.append(self._make_criterion_block(block, RuleCriterion(), row_index=0))

        self._relabel_criterion_prefixes(block)
        self._refresh_and_remove_buttons(block)

        add_c_btn = ctk.CTkButton(
            body,
            text=self._tr("add_criterion"),
            width=148,
            command=lambda b=block: self._add_criterion_to_block(b),
        )
        add_c_btn.pack(anchor="w", padx=8, pady=(0, 4))

        act_row = ctk.CTkFrame(body)
        act_row.pack(fill="x", padx=8, pady=(4, 8))

        ctk.CTkLabel(act_row, text=self._tr("action"), width=46).grid(row=0, column=0, padx=3, pady=3, sticky="w")
        act_vals = [x[0] for x in self._pairs_action()]
        action_menu = ctk.CTkOptionMenu(act_row, values=act_vals, width=UI_ACTION_W)
        action_menu.set(_label_for_value(self._pairs_action(), rule.action))
        action_menu.grid(row=0, column=1, padx=3, pady=3)

        target_btn = ctk.CTkButton(
            act_row,
            text=self._shorten(block.target_path) or self._tr("target_folder"),
            width=UI_TARGET_BTN_W,
            command=lambda: self._pick_target_for_block(block),
        )
        target_btn.grid(row=0, column=2, padx=3, pady=3, sticky="e")
        act_row.grid_columnconfigure(2, weight=1)

        def on_action_change(_: str = "") -> None:
            lbl = action_menu.get()
            internal = _value_for_label(self._pairs_action(), lbl)
            if internal == "move":
                target_btn.configure(state="normal")
            else:
                target_btn.configure(state="disabled")

        action_menu.configure(command=on_action_change)
        on_action_change()

        block.action_menu = action_menu
        block.target_btn = target_btn

        body.pack(fill="x", padx=0, pady=(0, 6), after=title_row)
        return block

    def _pick_target_for_block(self, block: RuleBlockWidgets) -> None:
        initial = block.target_path if block.target_path else self._watch_folder_var.get()
        path = filedialog.askdirectory(
            initialdir=initial if initial and Path(initial).is_dir() else None
        )
        if path and block.target_btn is not None:
            block.target_path = path
            block.target_btn.configure(text=self._shorten(path))

    def _add_rule_block(self) -> None:
        self._rule_blocks.append(self._make_rule_block(Rule()))
        self._repack_rule_blocks()

    def _remove_last_rule_block(self) -> None:
        if not self._rule_blocks:
            return
        b = self._rule_blocks.pop()
        b.outer.destroy()
        self._refresh_all_rule_chrome()

    def _set_rules_loading_mask(self, show: bool) -> None:
        """Vollflächige Abdeckung über dem Regel-Scrollbereich — kein sichtbares Stück-für-Stück-Aufbauen."""
        host = self._frm_rules_scroll_host
        ov = self._rules_loading_overlay
        if host is None or ov is None:
            return
        if show:
            ov.configure(fg_color=self._pal["panel_elev"])
            ov.place(relx=0, rely=0, relwidth=1, relheight=1)
            ov.lift()
        else:
            ov.place_forget()

    def _set_rules_in_ui(self, rules: list[Rule]) -> None:
        """Regel-Editor komplett durch die gegebene Liste ersetzen."""
        self._set_rules_loading_mask(True)
        try:
            for b in self._rule_blocks:
                b.outer.destroy()
            self._rule_blocks.clear()
            if not rules:
                rules = [Rule()]
            for r in rules:
                self._rule_blocks.append(self._make_rule_block(r))
            self._repack_rule_blocks()
        finally:
            host = self._frm_rules_scroll_host
            if host is not None:
                host.update_idletasks()
            else:
                self.update_idletasks()
            self._set_rules_loading_mask(False)
        self._schedule_apply_palette()

    def _export_rules_file(self) -> None:
        """Regelsetz als JSON sichern (inkl. Überwachungsordner als Hinweis)."""
        self._flush_current_profile_from_ui()
        ft_json = self._tr("ft_json")
        ft_all = self._tr("ft_all")
        path = filedialog.asksaveasfilename(
            parent=self,
            title=self._tr("export_title"),
            defaultextension=".json",
            filetypes=[(f"{ft_json} (*.json)", "*.json"), (f"{ft_all} (*.*)", "*.*")],
            initialdir=str(self._base_dir),
            initialfile=self._tr("export_default_name"),
        )
        if not path:
            return
        payload = {
            "export_version": 1,
            "description": self._tr("export_description"),
            "rules": [r.to_dict() for r in self._collect_rules_from_ui()],
            "watch_folder": self._watch_folder_var.get().strip(),
        }
        try:
            Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as e:
            messagebox.showerror(self._tr("export_failed"), str(e), parent=self)
            return
        self._status.configure(text=self._tr("status_exported", path=path))

    def _import_rules_file(self) -> None:
        """Regeln aus JSON laden und in der Oberfläche (und config.json) übernehmen."""
        ft_json = self._tr("ft_json")
        ft_all = self._tr("ft_all")
        path = filedialog.askopenfilename(
            parent=self,
            title=self._tr("import_title"),
            filetypes=[(f"{ft_json} (*.json)", "*.json"), (f"{ft_all} (*.*)", "*.*")],
            initialdir=str(self._base_dir),
        )
        if not path:
            return
        try:
            raw = Path(path).read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as e:
            messagebox.showerror(
                self._tr("import_failed"),
                self._tr("import_read_error", error=str(e)),
                parent=self,
            )
            return
        rules_raw = data.get("rules")
        if not isinstance(rules_raw, list) or not rules_raw:
            messagebox.showerror(
                self._tr("import_failed"),
                self._tr("import_no_rules"),
                parent=self,
            )
            return
        rules: list[Rule] = []
        for i, item in enumerate(rules_raw):
            if not isinstance(item, dict):
                messagebox.showerror(
                    self._tr("import_failed"),
                    self._tr("import_bad_entry", n=str(i + 1)),
                    parent=self,
                )
                return
            try:
                rules.append(Rule.from_dict(item))
            except Exception as e:
                messagebox.showerror(
                    self._tr("import_failed"),
                    self._tr("import_corrupt_rule", n=str(i + 1), error=str(e)),
                    parent=self,
                )
                return

        wf_import = data.get("watch_folder")
        if isinstance(wf_import, str) and wf_import.strip():
            if messagebox.askyesno(
                self._tr("import_watch_title"),
                self._tr("import_watch_prompt", path=wf_import.strip()),
                parent=self,
            ):
                self._watch_folder_var.set(wf_import.strip())

        self._set_rules_in_ui(rules)
        self._persist(immediate_disk=True)
        self._status.configure(text=self._tr("status_imported", path=path))

    def _collect_rules_from_ui(self) -> list[Rule]:
        out: list[Rule] = []
        for block in self._rule_blocks:
            if block.action_menu is None:
                continue
            criteria: list[RuleCriterion] = []
            for cb in block.criteria_rows:
                if_type = _value_for_label(self._pairs_if(), cb.if_menu.get())  # type: ignore[arg-type]
                condition = _value_for_label(self._pairs_cond(), cb.cond_menu.get())  # type: ignore[arg-type]
                values = [cb.first_value_entry.get()]
                values.extend(orw.entry.get() for orw in cb.or_rows)
                criteria.append(
                    RuleCriterion(
                        if_type=if_type,  # type: ignore[arg-type]
                        condition=condition,  # type: ignore[arg-type]
                        values=values,
                    )
                )
            action = _value_for_label(self._pairs_action(), block.action_menu.get())  # type: ignore[arg-type]
            out.append(
                Rule(
                    criteria=criteria,
                    action=action,  # type: ignore[arg-type]
                    target_folder=block.target_path if action == "move" else "",
                )
            )
        return out

    def _cancel_config_sync(self) -> None:
        if self._config_after_id is not None:
            try:
                self.after_cancel(self._config_after_id)
            except Exception:
                pass
            self._config_after_id = None

    def _persist(self, *, immediate_disk: bool = False) -> None:
        self._flush_current_profile_from_ui()
        self._cfg.ui_language = self._lang
        if self._seg_appearance is not None:
            sel = self._seg_appearance.get()
            self._cfg.ui_appearance = "light" if sel == self._tr("appearance_light") else "dark"
        if immediate_disk:
            self._cancel_save_config_pending()
            save_config(self._cfg, self._base_dir)
        else:
            self._schedule_save_config()

    def _manual_scan_folder(self) -> None:
        """Alle angehakten Profile mit gültigem Ordner: Überwachung starten, vorhandene Dateien einreihen."""
        self._flush_current_profile_from_ui()
        targets: list[WatchProfile] = []
        for pr in self._cfg.profiles:
            if not pr.run_enabled:
                continue
            wf = pr.watch_folder.strip()
            if wf and Path(wf).is_dir():
                targets.append(pr)
        if not targets:
            self._status.configure(text=self._tr("manual_scan_need_select"))
            return
        total = 0
        ok_any = False
        for pr in targets:
            pid = pr.profile_id
            if not self._start_profile_controller(pid):
                continue
            ctrl = self._controllers.get(pid)
            if ctrl is None or not ctrl.is_running:
                continue
            ok_any = True
            wf = pr.watch_folder.strip()
            total += ctrl.scan_folder_now(wf)
        self._update_multi_status()
        if not ok_any:
            self._status.configure(text=self._tr("manual_scan_need_start"))
            return
        self._status.configure(text=self._tr("manual_scan_done", n=str(total)))

    def _on_close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._cancel_save_config_pending()
        self._cancel_watch_empty_hint_pending()
        self._cancel_autostart_registry_pending()
        self._cancel_scheduled_apply_palette()
        self._cancel_config_sync()
        self._flush_current_profile_from_ui()
        pairs: list[tuple[str, WatchController]] = []
        for pid in list(self._controllers.keys()):
            c = self._controllers.get(pid)
            if c is not None:
                pairs.append((pid, c))
        if not pairs:
            self._controllers.clear()
            self._persist(immediate_disk=True)
            self.destroy()
            return

        def work() -> None:
            for _pid, ctrl in pairs:
                if ctrl.is_running:
                    ctrl.stop()
            self.after(0, self._finish_close_after_stops)

        threading.Thread(target=work, daemon=True).start()

    def _finish_close_after_stops(self) -> None:
        self._controllers.clear()
        self._persist(immediate_disk=True)
        self.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Sorter")
    parser.add_argument(
        "--autostart",
        action="store_true",
        help="Nach Anmeldung: Überwachung sofort starten (Windows-Autostart).",
    )
    args = parser.parse_args()
    app = DownloadSorterApp(autostart_watch=args.autostart)
    app.mainloop()


if __name__ == "__main__":
    main()
