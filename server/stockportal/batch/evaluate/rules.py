"""注文の結果の判定(詳細設計書 §6.11)。

J-Quants の ``swing/engine.py`` の ``simulate_one`` と同じ動きにする(指値買いだけ)。
環境が別なので import はせず、ここに移す。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

HOLD_DAYS = 20  # 約定後の最長保有(営業日)。md の「20 営業日目の終値で売る」


@dataclass(frozen=True)
class Bar:
    day: date
    o: float
    h: float
    l: float  # noqa: E741
    c: float
    adj: float = 1.0  # AdjFactor。1 以外は株式分割・併合の日


@dataclass
class Outcome:
    status: str  # ordering / unfilled / holding / win / lose / unknown
    reason: str | None = None  # target / stop / time(win・lose のとき)
    fill_date: date | None = None
    fill_price: float | None = None
    exit_date: date | None = None
    exit_price: float | None = None
    ret: float | None = None  # 決済の値段 ÷ 約定の値段 − 1(手数料は含めない)
    days_held: int | None = None
    last_date: date | None = None  # 保有中: 直近の終値の日
    last_close: float | None = None
    note: str | None = None  # unknown の理由
    extra: dict = field(default_factory=dict)


def simulate(
    bars: list[Bar],
    entry: float,
    stop: float,
    target: float,
    order_start: date,
    order_end: date,
    as_of: date,
    hold: int = HOLD_DAYS,
) -> Outcome:
    """``bars`` はその銘柄の日足(日付の昇順。値が付かなかった日は入れない)。

    ``as_of`` より後の足は使わない。
    同じ日に損切りと目標の両方に届いた場合は損切りとする(保守的)。約定日は目標を見ない。
    """
    bars = [b for b in bars if order_start <= b.day <= as_of]

    if any(b.adj != 1.0 for b in bars):
        return Outcome("unknown", note="期間中に株式分割・併合があったため評価できません")

    fill: Bar | None = None
    fill_price = 0.0
    for b in bars:
        if b.day > order_end:
            break
        if b.o <= entry:
            fill, fill_price = b, b.o
            break
        if b.l <= entry:
            fill, fill_price = b, entry
            break
    if fill is None:
        if as_of < order_end:
            return Outcome("ordering")
        if not any(b.day <= order_end for b in bars):
            return Outcome("unknown", note="注文の有効期間の日足がありません")
        return Outcome("unfilled")

    def settle(day: date, price: float, reason: str, held: int) -> Outcome:
        ret = price / fill_price - 1.0
        return Outcome(
            "win" if ret > 0 else "lose", reason, fill.day, fill_price, day, price, ret, held,
        )

    # 約定日: 損切りだけを見る(寄りで損切り水準より下なら寄りで約定し、そのまま損切り)
    if fill_price <= stop:
        return settle(fill.day, fill_price, "stop", 0)
    if fill.l <= stop:
        return settle(fill.day, stop, "stop", 0)

    held = 0
    last = fill
    for b in bars:
        if b.day <= fill.day:
            continue
        held += 1
        last = b
        if b.o <= stop:
            return settle(b.day, b.o, "stop", held)
        if b.o >= target:
            return settle(b.day, b.o, "target", held)
        if b.l <= stop:
            return settle(b.day, stop, "stop", held)
        if b.h >= target:
            return settle(b.day, target, "target", held)
        if held >= hold:
            return settle(b.day, b.c, "time", held)

    return Outcome(
        "holding",
        fill_date=fill.day,
        fill_price=fill_price,
        ret=last.c / fill_price - 1.0,
        days_held=held,
        last_date=last.day,
        last_close=last.c,
    )
