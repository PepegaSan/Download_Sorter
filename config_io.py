# -*- coding: utf-8 -*-
"""Laden und Speichern der Konfiguration (config.json)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

IfType = Literal["extension", "filename", "source_url"]
Condition = Literal["contains", "equals"]
Action = Literal["move", "delete", "ignore"]

CONFIG_FILENAME = "config.json"


@dataclass
class RuleCriterion:
    """
    Ein Filterkriterium: ein Typ + Bedingung, mehrere Werte = logisches ODER.

    Beispiel: Dateiendung „enthält“ mit Werten jpg und jpeg.
    """

    if_type: IfType = "extension"
    condition: Condition = "contains"
    values: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.values:
            self.values = [""]

    def to_dict(self) -> dict[str, Any]:
        return {"if_type": self.if_type, "condition": self.condition, "values": self.values}

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "RuleCriterion":
        vals = d.get("values")
        if isinstance(vals, list) and vals:
            value_list = [str(v) for v in vals]
        else:
            value_list = [str(d.get("value", ""))]
        if not value_list:
            value_list = [""]
        return RuleCriterion(
            if_type=_coerce_if_type(d.get("if_type", "extension")),
            condition=_coerce_condition(d.get("condition", "contains")),
            values=value_list,
        )


@dataclass
class Rule:
    """
    Regel mit einer Liste von Kriterien.

    Alle Kriterien müssen zur selben Datei passen (logisches UND).
    Mehrere Regeln in der Konfiguration: erste passende Regel gewinnt (ODER-Priorität).
    """

    criteria: list[RuleCriterion] = field(default_factory=list)
    action: Action = "move"
    target_folder: str = ""

    def __post_init__(self) -> None:
        if not self.criteria:
            self.criteria = [RuleCriterion()]

    def to_dict(self) -> dict[str, Any]:
        return {
            "criteria": [c.to_dict() for c in self.criteria],
            "action": self.action,
            "target_folder": self.target_folder,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Rule":
        crit_raw = d.get("criteria")
        if isinstance(crit_raw, list) and crit_raw:
            criteria = [RuleCriterion.from_dict(x) for x in crit_raw if isinstance(x, dict)]
            if not criteria:
                criteria = [RuleCriterion()]
        else:
            # Alte config.json: ein Kriterium aus den Top-Level-Feldern
            criteria = [
                RuleCriterion(
                    if_type=_coerce_if_type(d.get("if_type", "extension")),
                    condition=_coerce_condition(d.get("condition", "contains")),
                    values=[str(d.get("value", ""))],
                )
            ]
        return Rule(
            criteria=criteria,
            action=_coerce_action(d.get("action", "move")),
            target_folder=str(d.get("target_folder", "")),
        )


@dataclass
class AppConfig:
    watch_folder: str = ""
    settle_delay_seconds: float = 1.5
    stable_poll_interval_seconds: float = 0.4
    max_wait_seconds: float = 120.0
    rules: list[Rule] = field(default_factory=list)
    ui_language: str = "de"

    def to_dict(self) -> dict[str, Any]:
        return {
            "watch_folder": self.watch_folder,
            "settle_delay_seconds": self.settle_delay_seconds,
            "stable_poll_interval_seconds": self.stable_poll_interval_seconds,
            "max_wait_seconds": self.max_wait_seconds,
            "rules": [r.to_dict() for r in self.rules],
            "ui_language": self.ui_language,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "AppConfig":
        rules_raw = d.get("rules") or []
        rules = [Rule.from_dict(x) for x in rules_raw if isinstance(x, dict)]
        lang = str(d.get("ui_language", "de")).lower()
        if lang not in ("de", "en"):
            lang = "de"
        return AppConfig(
            watch_folder=str(d.get("watch_folder", "")),
            settle_delay_seconds=float(d.get("settle_delay_seconds", 1.5)),
            stable_poll_interval_seconds=float(d.get("stable_poll_interval_seconds", 0.4)),
            max_wait_seconds=float(d.get("max_wait_seconds", 120.0)),
            rules=rules,
            ui_language=lang,
        )

    def copy(self) -> "AppConfig":
        """Thread-sichere Kopie (über JSON-Dict-Roundtrip, keine Tk-Widgets)."""
        return AppConfig.from_dict(self.to_dict())


def config_path(base_dir: Path | None = None) -> Path:
    root = base_dir or Path(__file__).resolve().parent
    return root / CONFIG_FILENAME


def load_config(base_dir: Path | None = None) -> AppConfig:
    path = config_path(base_dir)
    if not path.is_file():
        return AppConfig()
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return AppConfig()
        return AppConfig.from_dict(data)
    except (OSError, json.JSONDecodeError):
        return AppConfig()


def save_config(cfg: AppConfig, base_dir: Path | None = None) -> None:
    path = config_path(base_dir)
    tmp = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2)
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    tmp.replace(path)


def _coerce_if_type(v: Any) -> IfType:
    s = str(v).lower()
    if s in ("extension", "filename", "source_url"):
        return s  # type: ignore[return-value]
    return "extension"


def _coerce_condition(v: Any) -> Condition:
    s = str(v).lower()
    if s in ("contains", "equals"):
        return s  # type: ignore[return-value]
    return "contains"


def _coerce_action(v: Any) -> Action:
    s = str(v).lower()
    if s in ("move", "delete", "ignore"):
        return s  # type: ignore[return-value]
    return "move"
