"""期間に依存する計算(詳細設計書 §5.6)。

集計は週ごとの値だけを持つ。期間(13・26・52週)に依存する計算はここで行う(D5)。
データのない週(``None``)は、平均・合計から外す。
"""

from __future__ import annotations

from dataclasses import dataclass

# 期間 → 「直近」の幅(基本設計書 §4.4)
RECENT_OF_WEEKS = {13: 2, 26: 4, 52: 8}
PERIODS = {"13w": 13, "26w": 26, "52w": 52}
DEFAULT_PERIOD = "13w"

SCOPES = ("all", "prime", "standard", "growth")
DEFAULT_SCOPE = "all"

# 業種の太字の対象(2026-09-26 確定。§5.6 の 6)
EMPHASIS_COUNT = 3


@dataclass(frozen=True)
class Window:
    """期間の切り出し方。"""

    period: str
    weeks: int
    recent: int

    @classmethod
    def of(cls, period: str | None) -> "Window":
        key = period if period in PERIODS else DEFAULT_PERIOD
        n = PERIODS[key]
        return cls(period=key, weeks=n, recent=RECENT_OF_WEEKS[n])


def normalize_scope(scope: str | None) -> str:
    return scope if scope in SCOPES else DEFAULT_SCOPE


def slice_weeks(week_ends: list[str], window: Window) -> list[str]:
    """最新の確定した週を右端に、N 週を切り出す。"""
    return week_ends[-window.weeks :] if window.weeks <= len(week_ends) else list(week_ends)


def values_for(series: dict[str, float | None], weeks: list[str]) -> list[float | None]:
    """週の並びに合わせた配列。無い週は None。"""
    return [series.get(w) for w in weeks]


def mean(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def ratio(recent: float | None, period: float | None) -> float | None:
    """直近の平均 ÷ 期間の平均。0 割りは None。"""
    if recent is None or period in (None, 0):
        return None
    return recent / period


def period_average_ratio(values: list[float | None], recent: int) -> float | None:
    """期間平均比 = 直近 R 週の平均 ÷ 期間の平均 − 1(基本設計書 §6.3)。"""
    whole = mean(values)
    last = mean(values[-recent:])
    r = ratio(last, whole)
    return None if r is None else (r - 1) * 100


def percentile(values: list[float | None]) -> int | None:
    """期間の中での位置。round(100 × (直近の週以下の週の数) ÷ 値のある週の数)。"""
    present = [v for v in values if v is not None]
    if not present or values[-1] is None:
        return None
    latest = values[-1]
    at_or_below = sum(1 for v in present if v <= latest)
    return round(100 * at_or_below / len(present))


def change_over_period(values: list[float | None]) -> float | None:
    """期間の最初と最後の「値のある週」どうしの差(§5.6 の 5)。"""
    present = [v for v in values if v is not None]
    return None if len(present) < 2 else present[-1] - present[0]


def change_pct_over_period(values: list[float | None]) -> float | None:
    """同じく、変化率(%)。"""
    present = [v for v in values if v is not None]
    if len(present) < 2 or present[0] == 0:
        return None
    return (present[-1] / present[0] - 1) * 100


def shares(series_by_key: dict[str, dict[str, float | None]], total: dict[str, float | None], weeks: list[str]) -> dict[str, list[float | None]]:
    """各キーの週ごとのシェア(%)。全体が 0 か None の週は None。"""
    out: dict[str, list[float | None]] = {}
    for key, series in series_by_key.items():
        row: list[float | None] = []
        for week in weeks:
            whole = total.get(week)
            part = series.get(week)
            row.append(None if not whole or part is None else part / whole * 100)
        out[key] = row
    return out


def emphasis_of(ratios: dict[str, float | None], count: int = EMPHASIS_COUNT) -> dict[str, str | None]:
    """期間平均比の上位 count と下位 count に "top"/"bottom" を付ける(§5.6 の 6)。"""
    ranked = sorted(((k, v) for k, v in ratios.items() if v is not None), key=lambda kv: -kv[1])
    marks: dict[str, str | None] = {k: None for k in ratios}
    for key, _ in ranked[:count]:
        marks[key] = "top"
    for key, _ in ranked[-count:] if len(ranked) > count else []:
        marks[key] = "bottom"
    return marks
