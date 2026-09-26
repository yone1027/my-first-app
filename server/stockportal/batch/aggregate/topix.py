"""TOPIX の週の終値と移動平均線(詳細設計書 §6.5)。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .jq import newest_by_to, rows_of, to_float

WINDOWS = (13, 26, 52)


def aggregate(jquants_raw: Path, weeks: list[dict], warnings: list[str]) -> list[dict]:
    """全履歴で移動平均線まで計算する(期間より前の週を使うため)。"""
    path = newest_by_to(jquants_raw / "indices__bars__daily__topix")
    if path is None:
        warnings.append("TOPIX のキャッシュがない")
        return []

    closes: dict[date, float] = {}
    for row in rows_of(path):
        value = to_float(row.get("C"))
        if value is not None:
            closes[date.fromisoformat(row["Date"])] = value

    rows: list[dict] = []
    series: list[float | None] = []
    for week in weeks:
        # その週の最終営業日の終値。無ければ、その週で値のあるいちばん新しい日。
        close = None
        for day in reversed(week["_days"]):
            if day in closes:
                close = closes[day]
                break
        series.append(close)
        entry: dict[str, object] = {"week_end": week["week_end"], "close": close}
        for window in WINDOWS:
            entry[f"ma{window}"] = _sma(series, window)
        rows.append(entry)
    return rows


def _sma(series: list[float | None], window: int) -> float | None:
    """その週を含む直近 window 週の単純移動平均。そろわない週は None。"""
    if len(series) < window:
        return None
    tail = series[-window:]
    if any(v is None for v in tail):
        return None
    return sum(tail) / window  # type: ignore[arg-type]
