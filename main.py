# -*- coding: utf-8 -*-
"""
Download Sorter — GUI (customtkinter) and folder watching (watchdog).

Config: config.json next to this script. UI: German or English (see locales.py, ui_language in config).
"""

from __future__ import annotations

import json
import logging
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import customtkinter as ctk

from config_io import Action, AppConfig, Condition, IfType, Rule, RuleCriterion, load_config, save_config
from locales import (
    LANG_EN,
    LANG_MENU_LABELS,
    normalize_lang,
    pairs_action,
    pairs_cond,
    pairs_if,
    t,
)
from watch_service import WatchController

_LOG = logging.getLogger(__name__)


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

    def __init__(self) -> None:
        super().__init__()

        self._base_dir = Path(__file__).resolve().parent
        _setup_file_logging(self._base_dir)
        self._cfg = load_config(self._base_dir)
        self._lang = normalize_lang(self._cfg.ui_language)
        self._watch_folder_var = ctk.StringVar(value=self._cfg.watch_folder or "")
        self._rule_blocks: list[RuleBlockWidgets] = []
        self._config_after_id: Optional[Any] = None

        self._controller = WatchController()

        self.geometry("1000x700")
        self.minsize(880, 560)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._build_layout()
        self._load_rules_into_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_layout(self) -> None:
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=12, pady=(12, 6))

        self._lbl_watch = ctk.CTkLabel(top, text="")
        self._lbl_watch.pack(side="left", padx=(0, 8))
        self._watch_lbl = ctk.CTkLabel(top, textvariable=self._watch_folder_var, anchor="w")
        self._watch_lbl.pack(side="left", fill="x", expand=True, padx=(0, 8))

        lang_box = ctk.CTkFrame(top, fg_color="transparent")
        lang_box.pack(side="right", padx=(8, 4))
        self._lbl_lang = ctk.CTkLabel(lang_box, text="", width=72, anchor="e")
        self._lbl_lang.pack(side="left", padx=(0, 4))
        self._lang_menu = ctk.CTkOptionMenu(
            lang_box,
            values=list(LANG_MENU_LABELS),
            width=110,
            command=self._on_language_changed,
        )
        self._lang_menu.pack(side="left")
        self._btn_browse = ctk.CTkButton(top, text="", width=140, command=self._pick_watch_folder)
        self._btn_browse.pack(side="right")

        rule_header = ctk.CTkFrame(self)
        rule_header.pack(fill="x", padx=12, pady=(8, 0))
        self._lbl_rule_help = ctk.CTkLabel(
            rule_header,
            text="",
            anchor="w",
            wraplength=920,
            justify="left",
        )
        self._lbl_rule_help.pack(side="left")

        btn_row = ctk.CTkFrame(self)
        btn_row.pack(fill="x", padx=12, pady=6)
        self._btn_add_rule = ctk.CTkButton(btn_row, text="", command=self._add_rule_block)
        self._btn_add_rule.pack(side="left", padx=(0, 8))
        self._btn_remove_rule = ctk.CTkButton(btn_row, text="", command=self._remove_last_rule_block)
        self._btn_remove_rule.pack(side="left", padx=(0, 8))
        self._btn_export = ctk.CTkButton(btn_row, text="", width=150, command=self._export_rules_file)
        self._btn_export.pack(side="left", padx=(0, 8))
        self._btn_import = ctk.CTkButton(btn_row, text="", width=150, command=self._import_rules_file)
        self._btn_import.pack(side="left")

        self._rules_scroll = ctk.CTkScrollableFrame(self, label_text="")
        self._rules_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        ctrl = ctk.CTkFrame(self)
        ctrl.pack(fill="x", padx=12, pady=(6, 12))
        self._start_btn = ctk.CTkButton(
            ctrl, text="", fg_color="green", hover_color="#006400", command=self._toggle_watch
        )
        self._start_btn.pack(side="left", padx=(0, 8))
        self._btn_scan = ctk.CTkButton(ctrl, text="", width=140, command=self._manual_scan_folder)
        self._btn_scan.pack(side="left", padx=(0, 8))
        self._status = ctk.CTkLabel(ctrl, text="", anchor="w")
        self._status.pack(side="left", fill="x", expand=True)

        self._refresh_static_texts()

    def _refresh_static_texts(self) -> None:
        self.title(self._tr("win_title"))
        self._lbl_watch.configure(text=self._tr("watch_folder"))
        self._lbl_lang.configure(text=self._tr("language") + ":")
        self._lang_menu.set(LANG_MENU_LABELS[1] if self._lang == LANG_EN else LANG_MENU_LABELS[0])
        self._btn_browse.configure(text=self._tr("browse_folder"))
        self._lbl_rule_help.configure(text=self._tr("rule_help"))
        self._btn_add_rule.configure(text=self._tr("add_rule"))
        self._btn_remove_rule.configure(text=self._tr("remove_last_rule"))
        self._btn_export.configure(text=self._tr("export_rules"))
        self._btn_import.configure(text=self._tr("import_rules"))
        self._rules_scroll.configure(label_text=self._tr("rule_editor"))
        self._btn_scan.configure(text=self._tr("scan_folder"))
        if self._controller.is_running:
            self._start_btn.configure(text=self._tr("stop"), fg_color="#8B0000", hover_color="#5c0000")
        else:
            self._start_btn.configure(text=self._tr("start"), fg_color="green", hover_color="#006400")
        if not self._controller.is_running:
            self._status.configure(text=self._tr("status_stopped"))

    def _on_language_changed(self, choice: str) -> None:
        new_lang = LANG_EN if choice == LANG_MENU_LABELS[1] else "de"
        if new_lang == self._lang:
            return
        rules = self._collect_rules_from_ui()
        wf = self._watch_folder_var.get()
        self._lang = new_lang
        self._cfg.ui_language = self._lang
        self._refresh_static_texts()
        self._set_rules_in_ui(rules)
        self._watch_folder_var.set(wf)
        self._persist()
        self._refresh_all_rule_chrome()

    def _pick_watch_folder(self) -> None:
        initial = self._watch_folder_var.get() or str(Path.home() / "Downloads")
        path = filedialog.askdirectory(initialdir=initial if Path(initial).is_dir() else None)
        if path:
            self._watch_folder_var.set(path)

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
        block_frame.pack(fill="x", pady=(2, 6))

        header = ctk.CTkFrame(block_frame)
        header.pack(fill="x")

        prefix = self._tr("when") if row_index == 0 else self._tr("and")
        prefix_lbl = ctk.CTkLabel(header, text=prefix, width=36)
        prefix_lbl.grid(row=0, column=0, padx=(4, 2), pady=4, sticky="w")

        if_vals = [x[0] for x in self._pairs_if()]
        if_menu = ctk.CTkOptionMenu(header, values=if_vals, width=128)
        if_menu.set(_label_for_value(self._pairs_if(), criterion.if_type))
        if_menu.grid(row=0, column=1, padx=4, pady=4)

        cond_vals = [x[0] for x in self._pairs_cond()]
        cond_menu = ctk.CTkOptionMenu(header, values=cond_vals, width=108)
        cond_menu.set(_label_for_value(self._pairs_cond(), criterion.condition))
        cond_menu.grid(row=0, column=2, padx=4, pady=4)

        vals = list(criterion.values) if criterion.values else [""]
        first_text = vals[0] if vals else ""

        first_value_entry = ctk.CTkEntry(
            header,
            width=200,
            placeholder_text=self._tr("placeholder_ext"),
        )
        first_value_entry.insert(0, first_text)
        first_value_entry.grid(row=0, column=3, padx=4, pady=4, sticky="ew")
        header.grid_columnconfigure(3, weight=1)

        or_button = ctk.CTkButton(
            header,
            text=self._tr("or_add"),
            width=72,
            fg_color=("gray75", "gray30"),
        )
        or_button.grid(row=0, column=4, padx=(4, 2), pady=4)

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

        ctk.CTkLabel(row_f, text=self._tr("or"), width=36).grid(row=0, column=0, padx=(4, 2), pady=2, sticky="w")
        ctk.CTkLabel(row_f, text="", width=128).grid(row=0, column=1, padx=4, pady=2)
        ctk.CTkLabel(row_f, text="", width=108).grid(row=0, column=2, padx=4, pady=2)

        entry = ctk.CTkEntry(row_f, width=200, placeholder_text=self._tr("placeholder_alt"))
        entry.insert(0, initial)
        entry.grid(row=0, column=3, padx=4, pady=2, sticky="ew")
        row_f.grid_columnconfigure(3, weight=1)

        remove_btn = ctk.CTkButton(
            row_f,
            text="X",
            width=32,
            fg_color=("gray70", "gray35"),
        )
        remove_btn.grid(row=0, column=4, padx=(4, 2), pady=2)

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
                    width=32,
                    fg_color=("gray70", "gray35"),
                    command=lambda b=block, idx=i: self._remove_criterion_block(b, idx),
                )
                cb.and_remove_btn.grid(row=0, column=5, padx=4, pady=4)
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
        outer = ctk.CTkFrame(self._rules_scroll, fg_color=("gray92", "gray17"))

        title_row = ctk.CTkFrame(outer, fg_color="transparent")
        title_row.pack(fill="x", padx=6, pady=(8, 4))

        rule_index_lbl = ctk.CTkLabel(title_row, text=f"{self._tr('rule')} ?", width=72, anchor="w")
        try:
            rule_index_lbl.configure(font=ctk.CTkFont(weight="bold"))
        except Exception:
            pass
        rule_index_lbl.grid(row=0, column=0, padx=(4, 6), sticky="w")

        summary_lbl = ctk.CTkLabel(title_row, text="", anchor="w", text_color=("gray30", "gray65"))
        summary_lbl.grid(row=0, column=1, padx=4, sticky="ew")
        title_row.grid_columnconfigure(1, weight=1)

        collapse_btn = ctk.CTkButton(title_row, text=self._tr("collapse"), width=100)
        collapse_btn.grid(row=0, column=2, padx=(4, 2))

        up_btn = ctk.CTkButton(title_row, text="↑", width=36, fg_color=("gray75", "gray30"))
        up_btn.grid(row=0, column=3, padx=2)
        down_btn = ctk.CTkButton(title_row, text="↓", width=36, fg_color=("gray75", "gray30"))
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
            width=160,
            command=lambda b=block: self._add_criterion_to_block(b),
        )
        add_c_btn.pack(anchor="w", padx=8, pady=(0, 4))

        act_row = ctk.CTkFrame(body)
        act_row.pack(fill="x", padx=8, pady=(4, 8))

        ctk.CTkLabel(act_row, text=self._tr("action"), width=50).grid(row=0, column=0, padx=4, pady=4, sticky="w")
        act_vals = [x[0] for x in self._pairs_action()]
        action_menu = ctk.CTkOptionMenu(act_row, values=act_vals, width=130)
        action_menu.set(_label_for_value(self._pairs_action(), rule.action))
        action_menu.grid(row=0, column=1, padx=4, pady=4)

        target_btn = ctk.CTkButton(
            act_row,
            text=self._shorten(block.target_path) or self._tr("target_folder"),
            width=200,
            command=lambda: self._pick_target_for_block(block),
        )
        target_btn.grid(row=0, column=2, padx=4, pady=4, sticky="e")
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

    def _set_rules_in_ui(self, rules: list[Rule]) -> None:
        """Regel-Editor komplett durch die gegebene Liste ersetzen."""
        for b in self._rule_blocks:
            b.outer.destroy()
        self._rule_blocks.clear()
        if not rules:
            rules = [Rule()]
        for r in rules:
            self._rule_blocks.append(self._make_rule_block(r))
        self._repack_rule_blocks()

    def _load_rules_into_ui(self) -> None:
        self._set_rules_in_ui(self._cfg.rules or [])

    def _export_rules_file(self) -> None:
        """Regelsetz als JSON sichern (inkl. Überwachungsordner als Hinweis)."""
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
        self._persist()
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

    def _snapshot_config(self) -> AppConfig:
        """Aktueller Stand aus der GUI — nur im Tk-Hauptthread aufrufen."""
        return AppConfig(
            watch_folder=self._watch_folder_var.get().strip(),
            settle_delay_seconds=self._cfg.settle_delay_seconds,
            stable_poll_interval_seconds=self._cfg.stable_poll_interval_seconds,
            max_wait_seconds=self._cfg.max_wait_seconds,
            rules=self._collect_rules_from_ui(),
            ui_language=self._lang,
        )

    def _cancel_config_sync(self) -> None:
        if self._config_after_id is not None:
            try:
                self.after_cancel(self._config_after_id)
            except Exception:
                pass
            self._config_after_id = None

    def _schedule_config_sync(self) -> None:
        """Regelmäßig Regel-Snapshot vom Hauptthread in den Worker übernehmen."""
        if not self._controller.is_running:
            self._config_after_id = None
            return
        try:
            self._controller.set_runtime_config(self._snapshot_config())
        except Exception:
            _LOG.exception("Konfigurationssync fehlgeschlagen")
        self._config_after_id = self.after(400, self._schedule_config_sync)

    def _persist(self) -> None:
        self._cfg = AppConfig(
            watch_folder=self._watch_folder_var.get().strip(),
            settle_delay_seconds=self._cfg.settle_delay_seconds,
            stable_poll_interval_seconds=self._cfg.stable_poll_interval_seconds,
            max_wait_seconds=self._cfg.max_wait_seconds,
            rules=self._collect_rules_from_ui(),
            ui_language=self._lang,
        )
        save_config(self._cfg, self._base_dir)

    def _manual_scan_folder(self) -> None:
        """Vorhandene Dateien im Überwachungsordner einmal verarbeiten (nur wenn „Läuft“)."""
        if not self._controller.is_running:
            self._status.configure(text=self._tr("manual_scan_need_start"))
            return
        wf = self._watch_folder_var.get().strip()
        if not wf or not Path(wf).is_dir():
            self._status.configure(text=self._tr("manual_scan_bad_folder"))
            return
        n = self._controller.scan_folder_now(wf)
        self._status.configure(text=self._tr("manual_scan_done", n=str(n)))

    def _toggle_watch(self) -> None:
        if self._controller.is_running:
            self._cancel_config_sync()
            self._controller.stop()
            self._refresh_static_texts()
            self._status.configure(text=self._tr("status_stopped"))
            self._persist()
            return

        self._persist()
        wf = self._watch_folder_var.get().strip()
        if not wf or not Path(wf).is_dir():
            self._status.configure(text=self._tr("err_watch_folder"))
            return

        try:
            initial = self._snapshot_config().copy()
            self._controller.start(wf, initial)
        except Exception as e:
            self._status.configure(text=self._tr("err_start", error=str(e)))
            return

        self._schedule_config_sync()
        self._refresh_static_texts()
        self._status.configure(
            text=self._tr(
                "status_running",
                path=wf,
                log=str(self._base_dir / "download_sorter.log"),
            )
        )

    def _on_close(self) -> None:
        self._cancel_config_sync()
        if self._controller.is_running:
            self._controller.stop()
        self._persist()
        self.destroy()


def main() -> None:
    app = DownloadSorterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
