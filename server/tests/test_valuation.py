"""市場全体の PER の時価総額(§6.6)。株式分割の直後の J-Quants の MktCap の食い違い。"""

from __future__ import annotations

import gzip
import json
from datetime import date

from stockportal.batch.aggregate.valuation import SplitGuard


def _bars(tmp_path, days: dict[str, list[dict]]):
    found = {}
    for day, rows in days.items():
        path = tmp_path / f"date={day}.json.gz"
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            json.dump({"data": rows}, fh)
        found[date.fromisoformat(day)] = path
    return found


def _row(code: str, adj: float = 1.0) -> dict:
    return {"Code": code, "AdjFactor": adj}


def test_split_ratio_applied_twice_is_corrected(tmp_path):
    """2026-09-29 の東京エレクトロン(1:5)。10/2 の MktCap は5倍になっていた。"""
    bars = _bars(tmp_path, {
        "2026-09-25": [_row("80350")],
        "2026-09-29": [_row("80350", 0.2)],
        "2026-10-02": [_row("80350")],
        "2026-10-09": [_row("80350")],
    })
    guard = SplitGuard(bars)
    assert guard.mktcap("80350", 26_453_210, 56_520, date(2026, 9, 25)) == 26_453_210
    # J-Quants の株数は 11,700(正しくは 2,340)
    fixed = guard.mktcap("80350", 141_579_902, 12_100, date(2026, 10, 2))
    assert abs(fixed - 26_453_210 / 56_520 / 0.2 * 12_100) < 1e-6 * fixed
    assert guard.fixed == [(date(2026, 10, 2), "80350")]
    # 翌週は J-Quants が正しい値に戻っている
    assert guard.mktcap("80350", 29_123_337, 12_445, date(2026, 10, 9)) == 29_123_337
    assert len(guard.fixed) == 1


def test_a_normal_split_is_left_as_is(tmp_path):
    bars = _bars(tmp_path, {
        "2026-09-25": [_row("1")],
        "2026-09-29": [_row("1", 0.5)],
        "2026-10-02": [_row("1")],
    })
    guard = SplitGuard(bars)
    guard.mktcap("1", 1000.0, 100.0, date(2026, 9, 25))
    assert guard.mktcap("1", 1100.0, 55.0, date(2026, 10, 2)) == 1100.0
    assert guard.fixed == []


def test_a_real_change_in_shares_without_a_split_is_left_as_is(tmp_path):
    """第三者割当などで株数が本当に変わったとき(2026-09-09 の日本板硝子)。分割が無ければ直さない。"""
    bars = _bars(tmp_path, {d: [_row("1")] for d in ("2026-09-04", "2026-09-11")})
    guard = SplitGuard(bars)
    guard.mktcap("1", 1000.0, 100.0, date(2026, 9, 4))
    assert guard.mktcap("1", 3600.0, 100.0, date(2026, 9, 11)) == 3600.0
    assert guard.fixed == []


def test_a_real_change_at_a_split_is_accepted_the_second_week(tmp_path):
    """分割と同じ時期に株数が本当に変わったときは、2週続けば J-Quants の値を正とする。"""
    bars = _bars(tmp_path, {
        "2026-09-25": [_row("1")],
        "2026-09-29": [_row("1", 0.5)],
        "2026-10-02": [_row("1")],
        "2026-10-09": [_row("1")],
    })
    guard = SplitGuard(bars)
    guard.mktcap("1", 1000.0, 100.0, date(2026, 9, 25))
    assert guard.mktcap("1", 3000.0, 50.0, date(2026, 10, 2)) == 1000.0
    assert guard.mktcap("1", 3000.0, 50.0, date(2026, 10, 9)) == 3000.0
