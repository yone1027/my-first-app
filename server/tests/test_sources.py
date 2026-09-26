"""新しく取るデータの読み方(§6.7・§6.8)。ネットワークには出ない。"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from stockportal.batch.aggregate import indicators, investors
from stockportal.batch.aggregate.sources import mof


# ---- 財務省の CSV(§6.8)----

@pytest.mark.parametrize(
    "text,expected",
    [
        ("R8.9.25", date(2026, 9, 25)),
        ("R1.5.1", date(2019, 5, 1)),      # 令和元年の初日
        ("H31.4.30", date(2019, 4, 30)),   # 平成最後の日
        ("H1.1.8", date(1989, 1, 8)),      # 平成元年の初日
        ("S64.1.6", date(1989, 1, 6)),     # 昭和最後の年
        ("R8.13.1", None),                  # 13月は無い
        ("2026-09-25", None),               # 西暦は受け取らない
        ("", None),
    ],
)
def test_wareki_to_date(text, expected):
    assert mof.to_date(text) == expected


def test_jgb_csv_is_read_by_column_name():
    """列は名前で探す。列が増えても動く(§6.8)。"""
    csv = (
        "国債金利情報 (令和8年9月),,,,,,(単位 : %)\n"
        "基準日,1年,2年,5年,10年,20年,40年\n"
        "R8.9.24,1.5,1.8,2.3,3.073,3.9,4.1\n"
        "R8.9.25,-,-,-,-,-,-\n"
    ).encode("shift_jis")
    values = mof.parse(csv)
    assert values == {date(2026, 9, 24): 3.073}   # 「-」の行は落ちる


def test_jgb_csv_without_the_header_row_is_an_error():
    with pytest.raises(mof.FetchError, match="基準日"):
        mof.parse("なにかの表\n1,2,3\n".encode("shift_jis"))


def test_jgb_csv_without_the_ten_year_column_is_an_error():
    csv = "基準日,1年,2年\nR8.9.24,1.5,1.8\n".encode("shift_jis")
    with pytest.raises(mof.FetchError, match="10年"):
        mof.parse(csv)


def test_week_value_prefers_the_last_business_day():
    values = {date(2026, 9, 24): 3.073, date(2026, 9, 22): 3.0}
    week = [date(2026, 9, 21), date(2026, 9, 22), date(2026, 9, 24), date(2026, 9, 25)]
    # 最終営業日(25日)に値がないので、その週でいちばん新しい24日を使う
    assert indicators.week_value(values, week) == (3.073, date(2026, 9, 24))
    # 値が1つも無い週は None
    assert indicators.week_value({}, week) is None


# ---- 投資部門別(§6.7)----

def test_six_subjects_plus_other():
    assert investors.SUBJECTS == (
        "foreigners", "individuals", "investment_trusts",
        "business_cos", "trust_banks", "proprietary", "other",
    )
    # 画面に出すのは6つ。other はまとめ先
    assert investors.SUBJECT_FIELDS["other"] == ("InsCo", "Bank", "OthFin", "OthCo")


def test_tokyo_nagoya_is_the_official_total():
    """東証全体は TokyoNagoya をそのまま使う。3区分を足して作らない(§6.7)。"""
    assert investors.SECTION_OF["TokyoNagoya"] == "all"
    assert len(investors.SECTION_OF) == 8   # 実物で確認した8種類


def test_balance_sums_the_prefixes():
    row = {"InsCoBal": 100.0, "BankBal": -50.0, "OthFinBal": "", "OthCoBal": 25.0}
    assert investors._balance(row, investors.SUBJECT_FIELDS["other"]) == 75.0
    assert investors._balance({"FrgnBal": 42.0}, ("Frgn",)) == 42.0
    assert investors._balance({}, ("Frgn",)) is None            # 項目が無い
    assert investors._balance({"FrgnBal": "なにか"}, ("Frgn",)) is None  # 数でない


def test_values_are_converted_from_thousand_yen():
    """API は千円単位。出力は円(§6.7)。"""
    assert investors.THOUSAND_YEN == 1000


def test_subscription_range_is_read_from_the_error_body():
    """契約の範囲外のときの 400 から、開始日を読み取る(§6.7)。"""
    message = (
        "/equities/investor-types: HTTP 400 "
        '{"message": "Your subscription covers the following dates: 2016-09-27 ~ . '
        'If you want more data, please check other plans"}'
    )
    assert investors.COVERED_FROM.search(message).group(1) == "2016-09-27"
    assert investors.COVERED_FROM.search("HTTP 500") is None


def test_aggregate_without_a_config_returns_nothing():
    """呼び出し側が用意できていないときは空で返す(集計全体を止めない)。"""
    assert investors.aggregate() == []
    assert indicators.aggregate() == []


def test_usdjpy_and_wti_say_why_they_are_not_built():
    status = indicators.sources_status([{"indicator": "jgb10y", "week_end": "2026-09-25"}])
    assert status["mof"]["ok"] is True
    assert status["boj"]["ok"] is False and "not_implemented" in status["boj"]["error"]
    assert status["eia"]["ok"] is False and "EIA_API_KEY" in status["eia"]["error"]


def test_the_current_month_csv_is_always_fetched(monkeypatch, tmp_path):
    """全期間の CSV は前月までしか入っていない。当月は毎回取る(§6.8)。

    初回に全期間だけ取って当月を飛ばすと、今月の週が埋まらない(2026-09-27 に踏んだ)。
    """
    from datetime import date as _date

    calls: list[bool] = []

    def fake_fetch(full: bool, cache_dir):
        calls.append(full)
        return {_date(2026, 8, 31): 2.943} if full else {_date(2026, 9, 24): 3.073}

    monkeypatch.setattr(mof, "fetch", fake_fetch)
    monkeypatch.setattr(mof, "load_cache", lambda _d: {})

    class Paths:
        raw_dir = tmp_path

    class Cfg:
        paths = Paths()

    weeks = [{"week_end": "2026-09-25", "_days": [_date(2026, 9, 24), _date(2026, 9, 25)]}]
    rows = indicators.aggregate(Cfg(), weeks, datetime(2026, 9, 26, 13, 0), [], rebuild=False)

    assert calls == [True, False], "全期間のあとに当月も取ること"
    assert rows == [{"week_end": "2026-09-25", "indicator": "jgb10y", "value": 3.073, "obs_date": "2026-09-24"}]
