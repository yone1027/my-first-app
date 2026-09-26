"""買い候補(パターン)を読む(詳細設計書 §7.3)。"""

from __future__ import annotations

import csv
from pathlib import Path

from .cache import BadFormat, FileCache

# CSV の列 → API の項目(§7.3 の表)
COLUMNS: tuple[tuple[str, str], ...] = (
    ("コード", "code"),
    ("銘柄名", "name"),
    ("業種コード", "s33"),
    ("時価総額(億円)", "market_cap_oku"),
    ("手法", "method"),
    ("水準", "level"),
    ("成立した足", "formed_on"),
    ("想定の買値(基準日の終値)", "entry"),
    ("損切りの支持線", "stop_line"),
    ("損切り価格", "stop"),
    ("支持線の守った割合(%)", "hold_pct"),
    ("支持線に触れた回数", "touches"),
    ("リスク(%)", "risk_pct"),
    ("リワード(%)", "reward_pct"),
    ("リスクリワード", "rr"),
    ("詳細", "detail"),
)
NUMERIC = {"market_cap_oku", "entry", "stop", "hold_pct", "touches", "risk_pct", "reward_pct", "rr"}

# 手法の絞り込み(§7.3)。CSV の「手法」の値 → ボタンのキー
METHOD_FILTERS: tuple[dict[str, object], ...] = (
    {"key": "granville", "label": "グランビル", "values": ("グランビルの法則",)},
    {"key": "earnings-breakout", "label": "決算ブレイクアウト後の押し目", "values": ("決算ブレイクアウト",)},
    {"key": "flag-pennant", "label": "フラッグ・ペナントの上抜け", "values": ("フラッグ", "ペナント")},
    {"key": "bollinger-bands", "label": "ボリンジャーバンド", "values": ("ボリンジャーバンド",)},
)
FILTER_OF_VALUE = {v: m["key"] for m in METHOD_FILTERS for v in m["values"]}  # type: ignore[index]


def _number(value: str) -> float | None:
    text = (value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_candidates(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        missing = [src for src, _ in COLUMNS if src not in header]
        if missing:
            raise BadFormat(path, f"列がありません: {missing}")
        rows = []
        for line in reader:
            row: dict[str, object] = {}
            for src, dest in COLUMNS:
                raw = (line.get(src) or "").strip()
                row[dest] = _number(raw) if dest in NUMERIC else raw
            row["method_filter"] = FILTER_OF_VALUE.get(str(row["method"]))
            rows.append(row)

    # 並び順はリスクリワードの大きい順。順位はこの並びで1から振る(§7.3)。
    rows.sort(key=lambda r: (r["rr"] is None, -(r["rr"] or 0)))
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
    return rows


class CandidatesReader:
    def __init__(self, candidates_dir: Path):
        self.candidates_dir = candidates_dir
        self._cache = FileCache()

    def path_for(self, date: str) -> Path:
        return self.candidates_dir / date.replace("-", "") / "candidates.csv"

    def has(self, date: str) -> bool:
        return self.path_for(date).exists()

    def read(self, date: str) -> list[dict]:
        return self._cache.get(self.path_for(date), parse_candidates)

    def last_updated(self, date: str) -> float | None:
        path = self.path_for(date)
        return path.stat().st_mtime if path.exists() else None
