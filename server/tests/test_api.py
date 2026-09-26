"""API の応答(§5)。実物のデータがある環境で確かめる。"""

from __future__ import annotations

import pytest


def test_health(client):
    assert client.get("/api/health").json() == {"ok": True}


def test_unknown_api_is_404(client):
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.json() == {"error": "not_found"}


def test_theme_is_served_from_the_config(client):
    theme = client.get("/api/theme").json()
    assert theme["buy_fg"] == "#B1442A"      # コントラスト比のため画面案から変えた値
    assert len(theme["investors"]) == 6


def test_status_reports_the_expected_week(client, needs_real_data):
    body = client.get("/api/status").json()
    assert body["delayed_after"] == "SAT 12:00"
    assert set(body["market"]) == {"data_week_end", "last_updated", "delayed"}
    assert set(body["weekly"]) >= {"latest_date", "last_updated", "delayed", "steps"}


def test_weekly_dates(client, needs_real_data):
    body = client.get("/api/weekly/dates").json()
    assert body["dates"], "基準日が返りません"
    first = body["dates"][0]
    assert first["date"] == body["latest"]
    assert set(first["has"]) == {"verdicts", "picks", "candidates"}


def test_verdicts_returns_every_row_and_no_score(client, needs_real_data):
    body = client.get("/api/weekly/latest/verdicts").json()
    assert len(body["rows"]) > 100
    assert [m["key"] for m in body["methods"]] == [
        "granville", "earnings-breakout", "flag-pennant", "bollinger-bands", "macd",
    ]
    # 合計点・総合判定・買い判定の数は返さない(D3)
    row = body["rows"][0]
    assert set(row) == {"code", "name", "market", "s33", "market_cap_oku", "v"}
    for banned in ("score", "total", "buy_count", "overall"):
        assert banned not in row


def test_verdict_detail_marks_provisional_bases(client, needs_real_data):
    rows = client.get("/api/weekly/latest/verdicts").json()["rows"]
    body = client.get(f"/api/weekly/latest/verdicts/{rows[0]['code']}").json()
    assert body["code"] == rows[0]["code"]
    for result in body["methods"].values():
        parts = result.values() if "verdict" not in result else [result]
        for part in parts:
            for signal in part["signals"]:
                assert signal["provisional"] == ("仮置き" in (signal["basis"] or ""))


def test_no_such_date_reports_the_latest(client, needs_real_data):
    r = client.get("/api/weekly/1999-01-01/verdicts")
    assert r.status_code == 404
    assert r.json()["error"] == "no_such_date"
    assert r.json()["latest"]


def test_search_normalises_full_width_letters(client, needs_real_data):
    hits = client.get("/api/search", params={"q": "三菱U"}).json()
    assert hits, "全角の社名に半角の入力が当たりません"
    assert all(set(h) == {"code", "name", "market", "in_universe"} for h in hits)
    assert len(hits) <= 10


def test_search_with_an_empty_query_returns_nothing(client):
    assert client.get("/api/search", params={"q": ""}).json() == []


# ---- 市場概況 ----

def market_or_skip(client, path):
    r = client.get(path)
    if r.status_code == 503:
        pytest.skip("市場概況の集計の結果がありません(aggregate を実行してください)")
    assert r.status_code == 200, r.text
    return r.json()


def test_japan_uses_13w_by_default(client):
    body = market_or_skip(client, "/api/market/japan")
    assert body["params"] == {"period": "13w", "weeks": 13, "recent": 2}
    assert len(body["weeks"]) == len(body["turnover"]["series"]) == 13


def test_bad_parameters_fall_back_to_the_defaults(client):
    body = market_or_skip(client, "/api/market/sectors?period=99w&scope=bogus")
    assert body["params"]["period"] == "13w"
    assert body["params"]["scope"] == "all"


def test_topix_decomposition_is_multiplicative(client):
    """TOPIX の騰落率 =(1+EPS の変化)×(1+PER の変化)− 1(基本設計書 §6.8)。"""
    body = market_or_skip(client, "/api/market/japan?period=52w")
    v = body["valuation"]
    if None in (v["topix_change_pct"], v["eps_change_pct"], v["per_change_pct"]):
        pytest.skip("期間の変化が計算できるデータがありません")
    expected = ((1 + v["eps_change_pct"] / 100) * (1 + v["per_change_pct"] / 100) - 1) * 100
    assert v["topix_change_pct"] == pytest.approx(expected, abs=0.1)


def test_segment_shares_add_up_to_about_a_hundred(client):
    body = market_or_skip(client, "/api/market/japan")
    total = sum(a["share_latest"] for a in body["allocation"] if a["share_latest"])
    assert total == pytest.approx(100.0, abs=0.01)


def test_sectors_lists_33_and_marks_three_at_each_end(client):
    body = market_or_skip(client, "/api/market/sectors?period=13w")
    assert len(body["sectors"]) == 33, "「その他」(9999)を除いた33業種であること"
    assert all(s["name"] for s in body["sectors"]), "業種の名前が付いていること"
    marks = [s["emphasis"] for s in body["sectors"]]
    assert marks.count("top") == 3 and marks.count("bottom") == 3
    # 並び順は期間平均比の大きい順
    ratios = [s["period_average_ratio"] for s in body["sectors"] if s["period_average_ratio"] is not None]
    assert ratios == sorted(ratios, reverse=True)


def test_heatmap_has_one_cell_per_week(client):
    body = market_or_skip(client, "/api/market/sectors?period=26w")
    assert all(len(s["heat"]) == len(body["weeks"]) for s in body["sectors"])


def test_investors_are_built_and_lag_by_at_least_a_week(client):
    """主体別売買動向は 2026-09-27 に実装した(§6.7)。"""
    body = market_or_skip(client, "/api/market/japan")
    investors = body["investors"]
    if not investors["subjects"]:
        pytest.skip("投資部門別情報の集計がありません(aggregate を実行してください)")
    assert investors["section"] == "all"
    assert [s["key"] for s in investors["subjects"]] == [
        "foreigners", "individuals", "investment_trusts",
        "business_cos", "trust_banks", "proprietary", "other",
    ]
    # 公表が1週以上遅れるので、右端の週は必ず空になる
    foreigners = next(s for s in investors["subjects"] if s["key"] == "foreigners")
    assert foreigners["series"][-1] is None
    # それでも要約は出る(値のある直近の週で作る)
    assert investors["summary"]["up"] and investors["summary"]["down"]
    assert investors["latest_published"]["pub_date"]


def test_each_indicator_says_which_source_is_missing(client):
    """取れていない指標は、その指標の取得元の理由を返す(§6.8)。"""
    body = market_or_skip(client, "/api/market/japan")
    by_key = {i["key"]: i for i in body["indicators"]}
    assert set(by_key) == {"jgb10y", "usdjpy", "wti"}

    # 10年国債利回りは実装済み(財務省の CSV)
    if by_key["jgb10y"]["latest"] is None:
        pytest.skip("10年国債利回りの集計がありません")
    assert by_key["jgb10y"]["not_built"] is None
    assert by_key["jgb10y"]["last_obs"]

    # ドル円と WTI は保留。理由はそれぞれの取得元のもの
    assert "ドル円の取得元が未定" in (by_key["usdjpy"]["not_built"] or "")
    assert "EIA_API_KEY" in (by_key["wti"]["not_built"] or "")
