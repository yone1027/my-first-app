"""市場概況の API(詳細設計書 §5.3)。

期間に依存する計算はここで行う(D5)。数値は丸めずに返す。
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from ..calc import period as P
from ..readers.market import Market
from ..readers.sectors import OTHER

router = APIRouter(prefix="/api/market", tags=["market"])

SEGMENTS = ("prime", "standard", "growth")


def load(request: Request) -> Market:
    return request.app.state.services.market.read()


def _weeks_payload(market: Market, weeks: list[str]) -> list[dict]:
    info = {w["week_end"]: w for w in market.weeks}
    return [
        {
            "start": info.get(w, {}).get("week_start"),
            "end": w,
            "days": info.get(w, {}).get("days"),
            "short": info.get(w, {}).get("short"),
        }
        for w in weeks
    ]


def _turnover_card(series: list[float | None], window: P.Window, ma13: list[float | None]) -> dict:
    latest = series[-1] if series else None
    avg = P.mean(series[-13:]) if len(series) >= 1 else None
    return {
        "latest": latest,
        "avg13": avg,
        "ratio13": P.ratio(latest, avg),
        "percentile": P.percentile(series),
        "series": series,
        "ma13": ma13,
    }


def _ma13_of(full: dict[str, float | None], all_weeks: list[str], weeks: list[str]) -> list[float | None]:
    """13週移動平均。期間より前の週も使って計算する(基本設計書 §5.1)。"""
    out: list[float | None] = []
    position = {w: i for i, w in enumerate(all_weeks)}
    values = [full.get(w) for w in all_weeks]
    for week in weeks:
        i = position.get(week)
        if i is None or i + 1 < 13:
            out.append(None)
            continue
        tail = values[i - 12 : i + 1]
        out.append(None if any(v is None for v in tail) else sum(tail) / 13)  # type: ignore[arg-type]
    return out


def _investors_payload(market: Market, section: str, weeks: list[str], window: P.Window) -> dict:
    from ..batch.aggregate.investors import SUBJECTS

    rows = market.investors_by_section(section)
    if not rows:
        # 集計が未実装のため空(§6.7)。画面はこのカードだけ「読み込めませんでした」にする。
        return {
            "section": section,
            "latest_published": None,
            "subjects": [],
            "summary": None,
            "not_built": market.manifest.get("sources", {}).get("investor_types", {}).get("error"),
        }

    by_subject: dict[str, dict[str, float | None]] = {s: {} for s in SUBJECTS}
    pub_dates: dict[str, str] = {}
    for row in rows:
        by_subject.setdefault(row["subject"], {})[row["week_end"]] = row["balance_yen"]
        if row["pub_date"]:
            pub_dates[row["week_end"]] = row["pub_date"]

    subjects = []
    deltas: dict[str, float | None] = {}
    for key in SUBJECTS:
        values = P.values_for(by_subject.get(key, {}), weeks)
        # 公表が1週以上遅れるので、期間の右端の数週はいつも空になる。
        # 「直近 R 週」は**値のある**最後の R 週で取る(2026-09-27 修正)。
        present = [v for v in values if v is not None]
        recent = P.mean(present[-window.recent :]) if present else None
        whole = P.mean(values)
        deltas[key] = None if recent is None or whole is None else recent - whole
        subjects.append(
            {
                "key": key,
                "series": values,
                "total": sum(v for v in values if v is not None) or None,
                "avg_recent": recent,
                "avg_period": whole,
            }
        )

    ranked = sorted(((k, v) for k, v in deltas.items() if v is not None), key=lambda kv: -kv[1])
    published = [w for w in weeks if w in pub_dates]
    latest = published[-1] if published else None
    return {
        "section": section,
        "latest_published": {"end": latest, "pub_date": pub_dates.get(latest)} if latest else None,
        "subjects": subjects,
        # 増えている上位2つ・減っている1つ(2026-09-26 確定。基本設計書 §6.7)
        "summary": {"up": [k for k, _ in ranked[:2]], "down": [k for k, _ in ranked[-1:]]},
    }


@router.get("/japan")
def japan(request: Request, period: str = Query(default=P.DEFAULT_PERIOD)) -> dict:
    """G-11 日本市場。"""
    market = load(request)
    window = P.Window.of(period)
    all_weeks = market.week_ends()
    weeks = P.slice_weeks(all_weeks, window)

    total_full = market.turnover_series("all", "ALL")
    total = P.values_for(total_full, weeks)
    topix = market.topix_by_week()
    valuation = market.valuation_by_week("all")

    allocation = []
    for segment in SEGMENTS:
        series = market.turnover_series(segment, "ALL")
        share = P.shares({segment: series}, total_full, weeks)[segment]
        allocation.append(
            {
                "segment": segment,
                "share_latest": share[-1] if share else None,
                "share_change_pt": P.change_over_period(share),
            }
        )

    per = [valuation.get(w, {}).get("per") for w in weeks]
    eps = [valuation.get(w, {}).get("eps") for w in weeks]
    close = [topix.get(w, {}).get("close") for w in weeks]
    latest_valuation = valuation.get(weeks[-1], {}) if weeks else {}

    # 指標ごとの取得元(manifest の sources のキー)。取れていないときの理由を出すのに使う。
    SOURCE_OF = {"jgb10y": "mof", "usdjpy": "boj", "wti": "eia"}
    indicators = []
    for key in ("jgb10y", "usdjpy", "wti"):
        series = market.indicator_series(key)
        values = [series.get(w, {}).get("value") for w in weeks]
        present = [w for w in weeks if series.get(w, {}).get("value") is not None]
        source = market.manifest.get("sources", {}).get(SOURCE_OF[key], {})
        indicators.append(
            {
                "key": key,
                "values": values,
                "latest": values[-1] if values else None,
                "change": P.change_over_period(values),
                "last_obs": series.get(present[-1], {}).get("obs_date") if present else None,
                "not_built": None if present else source.get("error"),
            }
        )

    return {
        "params": {"period": window.period, "weeks": window.weeks, "recent": window.recent},
        "as_of_week": {"start": _start_of(market, weeks[-1]) if weeks else None, "end": weeks[-1] if weeks else None},
        "weeks": _weeks_payload(market, weeks),
        "turnover": _turnover_card(total, window, _ma13_of(total_full, all_weeks, weeks)),
        "topix": {
            "close": close,
            "ma13": [topix.get(w, {}).get("ma13") for w in weeks],
            "ma26": [topix.get(w, {}).get("ma26") for w in weeks],
            "ma52": [topix.get(w, {}).get("ma52") for w in weeks],
        },
        "allocation": allocation,
        "investors": _investors_payload(market, "all", weeks, window),
        "valuation": {
            "per": per,
            "eps": eps,
            "n_target": latest_valuation.get("n_target"),
            "n_excluded_loss": latest_valuation.get("n_excluded_loss"),
            "per_change": P.change_over_period(per),
            "per_change_pct": P.change_pct_over_period(per),
            "eps_change_pct": P.change_pct_over_period(eps),
            "topix_change_pct": P.change_pct_over_period(close),
        },
        "indicators": indicators,
        "manifest": {"generated_at": market.manifest.get("generated_at"), "latest_week_end": market.manifest.get("latest_week_end")},
    }


def _start_of(market: Market, week_end: str) -> str | None:
    for week in market.weeks:
        if week["week_end"] == week_end:
            return week["week_start"]
    return None


@router.get("/segments")
def segments(request: Request, period: str = Query(default=P.DEFAULT_PERIOD)) -> dict:
    """G-12 市場区分。3区分分をまとめて返す(切り替えでは呼び直さない)。"""
    market = load(request)
    window = P.Window.of(period)
    weeks = P.slice_weeks(market.week_ends(), window)
    total_full = market.turnover_series("all", "ALL")

    out = []
    for segment in SEGMENTS:
        series = market.turnover_series(segment, "ALL")
        share = P.shares({segment: series}, total_full, weeks)[segment]
        valuation = market.valuation_by_week(segment)
        out.append(
            {
                "segment": segment,
                "share": share,
                "share_latest": share[-1] if share else None,
                "share_avg_period": P.mean(share),
                "share_avg_recent": P.mean(share[-window.recent :]),
                "period_average_ratio": P.period_average_ratio(share, window.recent),
                "turnover": P.values_for(series, weeks),
                "per": [valuation.get(w, {}).get("per") for w in weeks],
                "np_sum": [valuation.get(w, {}).get("np_sum") for w in weeks],
                "n_target": valuation.get(weeks[-1], {}).get("n_target") if weeks else None,
                "np_change_pct": P.change_pct_over_period([valuation.get(w, {}).get("np_sum") for w in weeks]),
                "investors": _investors_payload(market, segment, weeks, window),
            }
        )
    return {
        "params": {"period": window.period, "weeks": window.weeks, "recent": window.recent},
        "weeks": _weeks_payload(market, weeks),
        "segments": out,
    }


@router.get("/sectors")
def sectors(request: Request, period: str = Query(default=P.DEFAULT_PERIOD), scope: str = Query(default=P.DEFAULT_SCOPE)) -> dict:
    """G-13 業種。ヒートマップと一覧。"""
    market = load(request)
    window = P.Window.of(period)
    scope = P.normalize_scope(scope)
    weeks = P.slice_weeks(market.week_ends(), window)

    total_full = market.turnover_series(scope, "ALL")
    # 一覧に出すのは 33業種。「その他」(9999)は出さないが、全体(分母)には残る。
    codes = [c for c in market.sectors() if c != OTHER]
    names = request.app.state.services.sectors.names()
    series_by_code = {code: market.turnover_series(scope, code) for code in codes}
    share_by_code = P.shares(series_by_code, total_full, weeks)

    ratios = {code: P.period_average_ratio(share_by_code[code], window.recent) for code in codes}
    marks = P.emphasis_of(ratios)

    rows = []
    for code in codes:
        share = share_by_code[code]
        whole = P.mean(share)
        # ヒートマップのマス: その週のシェア ÷ 期間の平均シェア − 1(%)
        heat = [None if (v is None or not whole) else (v / whole - 1) * 100 for v in share]
        rows.append(
            {
                "s33": code,
                "name": names.get(code, code),
                "share_latest": share[-1] if share else None,
                "share_avg_period": whole,
                "period_average_ratio": ratios[code],
                "emphasis": marks.get(code),
                "heat": heat,
            }
        )
    rows.sort(key=lambda r: (r["period_average_ratio"] is None, -(r["period_average_ratio"] or 0)))

    ranked = [r for r in rows if r["period_average_ratio"] is not None]
    return {
        "params": {"period": window.period, "weeks": window.weeks, "recent": window.recent, "scope": scope},
        "weeks": _weeks_payload(market, weeks),
        "summary": {
            "up": [{"s33": r["s33"], "name": r["name"], "ratio": r["period_average_ratio"]} for r in ranked[:3]],
            "down": [{"s33": r["s33"], "name": r["name"], "ratio": r["period_average_ratio"]} for r in ranked[-3:]],
        },
        "sectors": rows,
    }
