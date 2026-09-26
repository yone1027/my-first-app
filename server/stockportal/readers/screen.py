"""一括分析の出力を読む(詳細設計書 §7.1)。

判定のラベルは ``verdicts.csv`` を正とする(2026-09-26 確定)。
``results.jsonl`` の ``verdict`` は使わず、根拠の表示にだけ使う。
"""

from __future__ import annotations

import csv
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from .cache import BadFormat, FileCache, FileNotFound, stamp

log = logging.getLogger(__name__)

DATE_DIR = re.compile(r"^\d{8}$")
COLUMN = re.compile(r"^(?P<name>.+)\((?P<timeframe>日足|週足)\)$")

# 画面の順(§7.1 の表。固定)
METHODS: tuple[dict[str, object], ...] = (
    {"key": "granville", "csv": "グランビルの法則", "label": "グランビル", "results": ("granville",)},
    {"key": "earnings-breakout", "csv": "決算ブレイクアウト", "label": "決算ブレイクアウト", "results": ("earnings-breakout",)},
    {"key": "flag-pennant", "csv": "フラッグ/ペナント", "label": "フラッグ/ペナント", "results": ("flag-pattern", "pennant")},
    {"key": "bollinger-bands", "csv": "ボリンジャーバンド", "label": "ボリンジャーバンド", "results": ("bollinger-bands",)},
    {"key": "macd", "csv": "MACD", "label": "MACD", "results": ("macd",)},
)
BY_CSV_NAME = {m["csv"]: m for m in METHODS}

# 判定の値の対応(§7.1)。知らない値は unknown にして警告を書く。
VERDICTS = {
    "買い": "buy",
    "中立": "neutral",
    "売り": "sell",
    "判定不能": "unknown",
    "食い違い": "conflict",
    "失敗": "unknown",
}
MARKETS = {"プライム": "prime", "スタンダード": "standard", "グロース": "growth"}

FIXED_COLUMNS = ("コード", "銘柄名", "市場", "業種コード", "時価総額(億円)")


@dataclass
class Verdicts:
    """``verdicts.csv`` を読んだ結果。"""

    date: str
    timeframes: dict[str, str]
    rows: list[dict] = field(default_factory=list)
    unknown_columns: list[str] = field(default_factory=list)


@dataclass
class ResultsIndex:
    """``results.jsonl`` の 銘柄コード → 最後の行の位置(§5.5)。"""

    path: Path
    offsets: dict[str, int]
    failed: list[dict]
    ok_count: int

    def record(self, code: str) -> dict | None:
        offset = self.offsets.get(code)
        if offset is None:
            return None
        with self.path.open("rb") as fh:
            fh.seek(offset)
            return json.loads(fh.readline())


def _number(value: str) -> float | None:
    text = (value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_verdicts(path: Path) -> Verdicts:
    """BOM 付き UTF-8 の CSV を読む。列は名前で探す(順番に依存しない)。"""
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        missing = [c for c in FIXED_COLUMNS if c not in header]
        if missing:
            raise BadFormat(path, f"先頭の列がありません: {missing}(実際の列: {header[:6]})")

        timeframes: dict[str, str] = {}
        verdict_cols: dict[str, str] = {}
        unknown: list[str] = []
        for column in header:
            if column in FIXED_COLUMNS or column.endswith("_局面"):
                continue
            m = COLUMN.match(column)
            if not m:
                unknown.append(column)
                continue
            method = BY_CSV_NAME.get(m.group("name"))
            if method is None:
                unknown.append(column)
                continue
            verdict_cols[method["key"]] = column  # type: ignore[index]
            timeframes[method["key"]] = m.group("timeframe")  # type: ignore[index]

        rows: list[dict] = []
        for line in reader:
            values: dict[str, list[str | None]] = {}
            for method in METHODS:
                key = method["key"]
                column = verdict_cols.get(key)  # type: ignore[arg-type]
                if column is None:
                    values[key] = [None, None]  # type: ignore[index]
                    continue
                raw = (line.get(column) or "").strip()
                code = VERDICTS.get(raw)
                if code is None:
                    log.warning("%s: 知らない判定の値 %r(列 %s)", path.name, raw, column)
                    code = "unknown"
                values[key] = [code, (line.get(f"{method['csv']}_局面") or "").strip() or None]  # type: ignore[index]
            rows.append(
                {
                    "code": (line.get("コード") or "").strip(),
                    "name": (line.get("銘柄名") or "").strip(),
                    "market": MARKETS.get((line.get("市場") or "").strip(), (line.get("市場") or "").strip()),
                    "s33": (line.get("業種コード") or "").strip(),
                    "market_cap_oku": _number(line.get("時価総額(億円)", "")),
                    "v": values,
                }
            )

    if unknown:
        log.warning("%s: 知らない手法の列は読み飛ばしました: %s", path.name, unknown)
    return Verdicts(date="", timeframes=timeframes, rows=rows, unknown_columns=unknown)


def build_results_index(path: Path) -> ResultsIndex:
    """1行1銘柄の JSONL を1回だけ走査し、最後の行の位置を覚える。"""
    offsets: dict[str, int] = {}
    failed: list[dict] = []
    ok = 0
    offset = 0
    with path.open("rb") as fh:
        for line in fh:
            length = len(line)
            if line.strip():
                code = _code_of(line)
                if code is None:
                    log.warning("%s: code が読めない行を飛ばしました(位置 %d)", path.name, offset)
                else:
                    offsets[code] = offset
            offset += length

    # status が ok でない銘柄は判定表から外す(§7.1)。最後の行だけを見る。
    with path.open("rb") as fh:
        for code, pos in offsets.items():
            fh.seek(pos)
            record = json.loads(fh.readline())
            status = record.get("status")
            if status in (None, "ok"):
                ok += 1
            else:
                failed.append({"code": code, "name": record.get("name"), "reason": _reason_of(record)})
    return ResultsIndex(path=path, offsets=offsets, failed=failed, ok_count=ok)


def _code_of(line: bytes) -> str | None:
    """行頭付近の "code": "…" を安く取り出す。"""
    marker = line.find(b'"code"')
    if marker < 0:
        return None
    start = line.find(b'"', line.find(b":", marker) + 1)
    end = line.find(b'"', start + 1)
    if start < 0 or end < 0:
        return None
    return line[start + 1 : end].decode("utf-8")


def _reason_of(record: dict) -> str | None:
    """失敗の理由。項目名は実物で要確認(§12.4)なので、見つかったものを使う。"""
    for key in ("error", "reason", "message", "detail", "status_detail"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    status = record.get("status")
    return f"status={status}" if status else None


class ScreenReader:
    """基準日ごとの一括分析の出力。"""

    def __init__(self, screen_dir: Path):
        self.screen_dir = screen_dir
        self._verdicts = FileCache()
        self._index = FileCache()
        self._report = FileCache()
        self._universe = FileCache()

    # ---- 基準日の一覧 ----
    def dates(self) -> list[str]:
        """``verdicts.csv`` と ``report.md`` がそろったフォルダだけを基準日とする。"""
        if not self.screen_dir.is_dir():
            return []
        found = []
        for child in self.screen_dir.iterdir():
            if not child.is_dir() or not DATE_DIR.match(child.name):
                continue
            if (child / "verdicts.csv").exists() and (child / "report.md").exists():
                found.append(f"{child.name[:4]}-{child.name[4:6]}-{child.name[6:]}")
        return sorted(found, reverse=True)

    def dir_for(self, date: str) -> Path:
        return self.screen_dir / date.replace("-", "")

    def verdicts(self, date: str) -> Verdicts:
        result = self._verdicts.get(self.dir_for(date) / "verdicts.csv", parse_verdicts)
        result.date = date
        return result

    def results_index(self, date: str) -> ResultsIndex:
        return self._index.get(self.dir_for(date) / "results.jsonl", build_results_index)

    def universe_count(self, date: str) -> int | None:
        path = self.dir_for(date) / "universe.csv"
        try:
            return self._universe.get(path, _count_rows)
        except FileNotFound:
            return None

    def report_counts(self, date: str) -> dict[str, int]:
        try:
            return self._report.get(self.dir_for(date) / "report.md", _parse_report)
        except FileNotFound:
            return {}

    def last_updated(self, date: str) -> float | None:
        newest = None
        for name in ("verdicts.csv", "results.jsonl", "report.md"):
            path = self.dir_for(date) / name
            if path.exists():
                newest = max(newest or 0.0, path.stat().st_mtime)
        return newest


def _count_rows(path: Path) -> int:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return max(sum(1 for _ in fh) - 1, 0)


REPORT_COUNTS = re.compile(r"分析できた\s*(\d+)\s*/\s*失敗\s*(\d+)")


def _parse_report(path: Path) -> dict[str, int]:
    text = path.read_text(encoding="utf-8")
    m = REPORT_COUNTS.search(text)
    return {"analyzed": int(m.group(1)), "failed": int(m.group(2))} if m else {}
