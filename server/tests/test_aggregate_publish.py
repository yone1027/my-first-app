"""入れ替え前の週の確かめ(§6.10 の 2)。"""

from __future__ import annotations

from datetime import date, timedelta

from stockportal.batch.aggregate.__main__ import check_weeks


def weeks(first: str, n: int) -> list[dict]:
    monday = date.fromisoformat(first)
    return [
        {"week_start": (monday + timedelta(weeks=i)).isoformat(),
         "week_end": (monday + timedelta(weeks=i, days=4)).isoformat()}
        for i in range(n)
    ]


def test_oldest_week_falling_out_of_the_window_is_fine():
    # 2026-10-10 に実際に止まった形: 先頭が1週落ち、末尾は増えていない
    before = weeks("2016-10-03", 521)
    assert check_weeks(before, before[1:]) is None


def test_window_sliding_by_a_week():
    before = weeks("2016-10-03", 521)
    assert check_weeks(before, weeks("2016-10-10", 521)) is None


def test_first_run_has_nothing_to_compare():
    assert check_weeks([], weeks("2016-10-03", 3)) is None


def test_empty_result_is_rejected():
    assert "なくなりました" in check_weeks(weeks("2016-10-03", 3), [])


def test_latest_week_going_back_is_rejected():
    before = weeks("2016-10-03", 521)
    assert "戻りました" in check_weeks(before, before[:-1])


def test_hole_in_the_middle_is_rejected():
    before = weeks("2016-10-03", 521)
    assert "抜けました" in check_weeks(before, before[:100] + before[101:])


def test_large_loss_at_the_head_is_rejected():
    # キャッシュが短くなった(例: 3年分しかない)ときは止める
    before = weeks("2016-10-03", 521)
    assert "古い週" in check_weeks(before, before[-156:])
