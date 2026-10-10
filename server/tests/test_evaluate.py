"""来週の買い注文の候補の成績(§6.11)。"""

from __future__ import annotations

from datetime import date, timedelta

from stockportal.batch.evaluate.rules import Bar, simulate
from stockportal.readers.evaluation import summarize

START = date(2026, 10, 5)  # 月曜
END = date(2026, 10, 9)
AS_OF = date(2026, 11, 30)


def bars(*ohlc, start: date = START) -> list[Bar]:
    """平日だけを順に並べる。"""
    out, day = [], start
    for o, h, l, c in ohlc:
        while day.weekday() >= 5:
            day += timedelta(days=1)
        out.append(Bar(day, o, h, l, c))
        day += timedelta(days=1)
    return out


def run(series, as_of=AS_OF, hold=20):
    return simulate(series, entry=100, stop=94, target=110, order_start=START, order_end=END, as_of=as_of, hold=hold)


def test_unfilled_when_the_low_never_reaches_the_limit():
    assert run(bars(*[(105, 106, 101, 104)] * 5)).status == "unfilled"


def test_ordering_while_the_order_is_still_open():
    assert run(bars((105, 106, 101, 104)), as_of=date(2026, 10, 5)).status == "ordering"


def test_fill_at_the_limit_then_target():
    out = run(bars((103, 104, 99, 101), (101, 111, 100, 109)))
    assert (out.status, out.reason, out.fill_price, out.exit_price, out.days_held) == ("win", "target", 100, 110, 1)
    assert out.fill_date == START and round(out.ret, 4) == 0.1


def test_gap_down_fills_at_the_open():
    out = run(bars((98, 99, 97, 98), (99, 112, 98, 111)))
    assert (out.fill_price, out.exit_price, out.status) == (98, 110, "win")


def test_fill_day_only_checks_the_stop():
    # 約定日に目標の高値があっても見ない。安値が損切り以下なら、その日に損切り
    out = run(bars((103, 120, 93, 100)))
    assert (out.status, out.reason, out.exit_date, out.exit_price, out.days_held) == ("lose", "stop", START, 94, 0)


def test_opening_below_the_stop_fills_and_stops_at_the_open():
    out = run(bars((92, 95, 91, 93)))
    assert (out.status, out.reason, out.fill_price, out.exit_price) == ("lose", "stop", 92, 92)


def test_both_touched_on_the_same_day_counts_as_the_stop():
    out = run(bars((103, 104, 99, 101), (101, 111, 93, 100)))
    assert (out.status, out.reason, out.exit_price) == ("lose", "stop", 94)


def test_gap_up_over_the_target_sells_at_the_open():
    out = run(bars((103, 104, 99, 101), (113, 114, 112, 113)))
    assert (out.reason, out.exit_price) == ("target", 113)


def test_time_exit_is_win_or_lose_by_the_sign():
    flat = [(101, 102, 99.5, 101)] * 3
    up = run(bars((103, 104, 99, 101), *flat[:2], (101, 102, 100, 103)), hold=3)
    assert (up.status, up.reason, up.exit_price, up.days_held) == ("win", "time", 103, 3)
    down = run(bars((103, 104, 99, 101), *flat[:2], (101, 102, 96, 97)), hold=3)
    assert (down.status, down.reason, down.exit_price) == ("lose", "time", 97)


def test_holding_reports_the_last_close():
    out = run(bars((103, 104, 99, 101), (101, 102, 100, 102)), as_of=date(2026, 10, 6))
    assert (out.status, out.last_close, out.days_held) == ("holding", 102, 1)
    assert round(out.ret, 4) == 0.02


def test_bars_after_as_of_are_not_used():
    series = bars((103, 104, 99, 101), (101, 111, 100, 109))
    assert run(series, as_of=START).status == "holding"


def test_split_during_the_period_is_not_evaluated():
    series = bars((103, 104, 99, 101))
    series.append(Bar(date(2026, 10, 6), 50, 51, 49, 50, adj=0.5))
    assert run(series).status == "unknown"


def test_summary_counts_without_scores():
    rows = [
        {"status": "win", "reason": "target", "ret": 0.1, "p_fill": 0.5, "p_target": 0.3, "p_stop": 0.4},
        {"status": "lose", "reason": "stop", "ret": -0.06, "p_fill": 0.5, "p_target": 0.3, "p_stop": 0.4},
        {"status": "unfilled", "p_fill": 0.5},
        {"status": "ordering", "p_fill": 0.5},
    ]
    s = summarize(rows)
    assert (s["total"], s["decided"], s["filled"], s["settled"]) == (4, 3, 2, 2)
    assert round(s["fill_rate"], 3) == 0.667 and round(s["mean_ret"], 3) == 0.02
    assert s["reasons"]["win"]["target"] == 1 and s["reasons"]["lose"]["stop"] == 1
    assert (s["actual_target"], s["actual_stop"]) == (0.5, 0.5)


def test_real_picks_are_all_evaluated(cfg, needs_real_data):
    from stockportal.batch.evaluate.__main__ import evaluate

    payload = evaluate(cfg, date(2026, 10, 9))
    rows = [r for r in payload["rows"] if r["date"] <= "2026-10-02"]
    assert rows and all(r["status"] != "unknown" for r in rows)
    assert all(r["entry"] and r["stop"] and r["target"] for r in rows)
