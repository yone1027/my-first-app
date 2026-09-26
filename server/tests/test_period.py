"""期間に依存する計算(§5.6)。"""

from __future__ import annotations

import pytest

from stockportal.calc import period as P


def test_window_defaults_to_13w():
    assert P.Window.of(None).period == "13w"
    assert P.Window.of("99w").period == "13w"
    assert P.Window.of("52w") == P.Window("52w", 52, 8)


def test_recent_width_per_period():
    assert [P.Window.of(p).recent for p in ("13w", "26w", "52w")] == [2, 4, 8]


def test_missing_weeks_are_left_out_of_the_mean():
    assert P.mean([1.0, None, 3.0]) == 2.0
    assert P.mean([None, None]) is None


def test_period_average_ratio():
    # 期間の平均 2.0、直近2週の平均 3.0 → +50%
    assert P.period_average_ratio([1.0, 1.0, 3.0, 3.0], recent=2) == pytest.approx(50.0)


def test_percentile_counts_only_weeks_with_values():
    assert P.percentile([1.0, 2.0, None, 3.0]) == 100
    assert P.percentile([3.0, 2.0, 1.0]) == 33
    assert P.percentile([1.0, None]) is None  # 直近が無い


def test_change_uses_first_and_last_present_week():
    assert P.change_over_period([None, 10.0, None, 12.0, None]) == 2.0
    assert P.change_pct_over_period([None, 10.0, 12.0]) == pytest.approx(20.0)


def test_shares_are_none_when_the_total_is_missing():
    weeks = ["w1", "w2"]
    out = P.shares({"a": {"w1": 25.0}}, {"w1": 100.0, "w2": None}, weeks)
    assert out["a"] == [25.0, None]


def test_emphasis_marks_top_three_and_bottom_three():
    marks = P.emphasis_of({"a": 30.0, "b": 20.0, "c": 10.0, "d": 0.0, "e": -10.0, "f": -20.0, "g": None})
    assert [k for k, v in marks.items() if v == "top"] == ["a", "b", "c"]
    assert [k for k, v in marks.items() if v == "bottom"] == ["d", "e", "f"]
    assert marks["g"] is None
