"""市場概況の集計の結果を読む(詳細設計書 §5.5・§6.9)。

全部を読んでメモリに持つ(全履歴でも数MB)。``manifest.json`` の
``schema_version`` が知らない版なら ``NotBuilt`` にする(§5.9)。
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from .cache import BadFormat, FileCache, FileNotFound

log = logging.getLogger(__name__)

KNOWN_SCHEMA_VERSIONS = (1,)

NUMERIC = {
    "days", "turnover_yen", "n_codes", "close", "ma13", "ma26", "ma52",
    "mktcap_sum", "np_sum", "n_target", "n_excluded_loss", "per", "eps",
    "balance_yen", "value",
}
BOOLEAN = {"short"}


class NotBuilt(Exception):
    """集計の結果がない、または知らない版(§5.9 の not_built)。"""


def _value(column: str, raw: str):
    if raw == "":
        return None
    if column in BOOLEAN:
        return raw in ("True", "true", "1")
    if column in NUMERIC:
        try:
            return int(raw)
        except ValueError:
            try:
                return float(raw)
            except ValueError:
                return raw
    return raw


def read_table(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise BadFormat(path, "列名の行がありません")
        return [{c: _value(c, row.get(c) or "") for c in reader.fieldnames} for row in reader]


@dataclass
class Market:
    """集計の結果ひとまとめ。"""

    manifest: dict
    weeks: list[dict] = field(default_factory=list)
    turnover: list[dict] = field(default_factory=list)
    topix: list[dict] = field(default_factory=list)
    valuation: list[dict] = field(default_factory=list)
    investors: list[dict] = field(default_factory=list)
    indicators: list[dict] = field(default_factory=list)

    # ---- 引きやすい形 ----
    def week_ends(self) -> list[str]:
        return [w["week_end"] for w in self.weeks]

    def turnover_series(self, scope: str, s33: str) -> dict[str, float]:
        return {r["week_end"]: r["turnover_yen"] for r in self.turnover if r["scope"] == scope and r["s33"] == s33}

    def sectors(self) -> list[str]:
        return sorted({r["s33"] for r in self.turnover if r["s33"] != "ALL"})

    def topix_by_week(self) -> dict[str, dict]:
        return {r["week_end"]: r for r in self.topix}

    def valuation_by_week(self, scope: str) -> dict[str, dict]:
        return {r["week_end"]: r for r in self.valuation if r["scope"] == scope}

    def indicator_series(self, key: str) -> dict[str, dict]:
        return {r["week_end"]: r for r in self.indicators if r["indicator"] == key}

    def investors_by_section(self, section: str) -> list[dict]:
        return [r for r in self.investors if r["section"] == section]


class MarketReader:
    def __init__(self, market_dir: Path):
        self.market_dir = market_dir
        self._cache = FileCache(max_entries=16)

    def _load(self) -> Market:
        manifest_path = self.market_dir / "manifest.json"
        try:
            manifest = self._cache.get(manifest_path, lambda p: json.loads(p.read_text(encoding="utf-8")))
        except FileNotFound as exc:
            raise NotBuilt(f"{manifest_path} がありません") from exc
        version = manifest.get("schema_version")
        if version not in KNOWN_SCHEMA_VERSIONS:
            raise NotBuilt(f"知らない schema_version です: {version!r}")

        def table(name: str) -> list[dict]:
            try:
                return self._cache.get(self.market_dir / name, read_table)
            except FileNotFound:
                log.warning("%s がありません。空として扱います", name)
                return []

        return Market(
            manifest=manifest,
            weeks=table("weeks.csv"),
            turnover=table("turnover.csv"),
            topix=table("topix.csv"),
            valuation=table("valuation.csv"),
            investors=table("investors.csv"),
            indicators=table("indicators.csv"),
        )

    def read(self) -> Market:
        return self._load()
