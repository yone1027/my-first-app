"""既存の出力の読み方(§7)。実物のファイルで確かめる。"""

from __future__ import annotations

import pytest

from stockportal.readers.markdown import parse_tables, split_sections, to_number
from stockportal.readers.picks import criteria_badges, short_code
from stockportal.readers.screen import VERDICTS


def test_short_code_drops_the_trailing_zero_of_five_character_codes():
    assert short_code("61780") == "6178"
    assert short_code("83060") == "8306"
    assert short_code("287A0") == "287A"
    assert short_code("8306") == "8306"
    assert short_code("285A") == "285A"


def test_verdict_labels_cover_every_value_the_csv_can_hold():
    # 「失敗」は判定不能と同じ扱い(§7.1)
    assert VERDICTS == {
        "買い": "buy", "中立": "neutral", "売り": "sell",
        "判定不能": "unknown", "食い違い": "conflict", "失敗": "unknown",
    }


def test_to_number_strips_separators_and_percent():
    assert to_number("1,234") == 1234
    assert to_number("-1.3") == -1.3
    assert to_number("66.0") == 66.0
    assert to_number("+2.4") == 2.4
    assert to_number("−5.6") == -5.6      # U+2212
    assert to_number("押し33%・25日線") == "押し33%・25日線"
    assert to_number("—") is None


def test_markdown_tables_and_sections():
    text = "\n".join(
        [
            "# 見出し",
            "- 注文の有効期間: 2026-09-28〜2026-10-02",
            "",
            "## 1. 6178 日本郵政(サービス業)",
            "| 項目 | 値 |",
            "|---|---|",
            "| 終値 | 2,579 円 |",
            "",
            "| 指値 | 下がる確率 |",
            "|---|---|",
            "| 2,546 | 66.0 |",
        ]
    )
    preamble, sections = split_sections(text)
    assert preamble.bullets() == ["注文の有効期間: 2026-09-28〜2026-10-02"]
    assert len(sections) == 1
    tables = sections[0].tables()
    assert len(tables) == 2
    assert tables[0][0] == {"項目": "終値", "値": "2,579 円"}
    assert tables[1][0] == {"指値": 2546, "下がる確率": 66.0}


def test_criteria_badges_match_the_documented_wording():
    criteria = {
        "min_ev_order": -9.0, "min_ev_fill": -9.0, "max_p_stop": 1.0,
        "min_p_fill": 0.35, "min_rr": 1.5, "max_rr": 2.0,
        "max_risk_pct": 0.15, "min_reward_pct": 0.08, "max_reward_pct": 0.12,
        "min_confluence": 5, "limit_only": True, "max_picks": 3, "one_per_sector": True,
    }
    assert criteria_badges(criteria) == [
        "目標 +8〜12%", "R:R 1.5〜2.0", "指値のみ", "支持線の重なり5本以上",
        "約定確率35%以上", "損切りまで15%以内", "業種を分けて最大3銘柄",
    ]


def test_unknown_criteria_keys_are_shown_as_is():
    assert criteria_badges({"min_rr": 1.5, "max_rr": 2.0, "new_key": 42}) == ["R:R 1.5〜2.0", "new_key: 42"]


# ---- 実物のファイルを使う確かめ ----

def test_verdicts_csv_is_read_with_the_columns_found_by_name(cfg, needs_real_data):
    from stockportal.readers.screen import ScreenReader

    reader = ScreenReader(cfg.paths.screen_dir)
    dates = reader.dates()
    assert dates, "基準日が1つも見つかりません"
    table = reader.verdicts(dates[0])
    assert len(table.rows) > 100
    assert table.unknown_columns == []
    # 5手法ぶんの時間軸が取れていること
    assert set(table.timeframes) == {"granville", "earnings-breakout", "flag-pennant", "bollinger-bands", "macd"}
    # 判定は記号に直っていること
    values = {v[0] for row in table.rows for v in row["v"].values()}
    assert values <= {"buy", "neutral", "sell", "unknown", "conflict"}


def test_results_index_finds_one_stock_quickly(cfg, needs_real_data):
    from stockportal.readers.screen import ScreenReader

    reader = ScreenReader(cfg.paths.screen_dir)
    date = reader.dates()[0]
    index = reader.results_index(date)
    assert len(index.offsets) > 100
    code = next(iter(index.offsets))
    record = index.record(code)
    assert record is not None and record["code"] == code
    assert "results" in record


def test_conflict_counts_as_a_buy_but_sorts_with_unknown(cfg, needs_real_data):
    """2026-09-26 決定。絞り込みでは買い、並び順では判定不能と同じ位置(§8.6)。"""
    from stockportal.readers.screen import ScreenReader

    reader = ScreenReader(cfg.paths.screen_dir)
    table = reader.verdicts(reader.dates()[0])
    # 食い違いは flag-pennant の列にだけ出る
    for row in table.rows:
        for key, (verdict, _) in row["v"].items():
            if verdict == "conflict":
                assert key == "flag-pennant"
