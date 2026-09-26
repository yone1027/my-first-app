"""週次の分析結果の API(詳細設計書 §5.4)。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..errors import NoData, NoSuchDate
from ..readers.cache import FileNotFound
from ..readers.candidates import METHOD_FILTERS
from ..readers.screen import METHODS

router = APIRouter(prefix="/api/weekly", tags=["weekly"])


def services(request: Request):
    return request.app.state.services


def resolve_date(svc, date: str) -> str:
    dates = svc.screen.dates()
    if not dates:
        raise NoData("screen")
    if date in ("latest", "", None):
        return dates[0]
    if date not in dates:
        raise NoSuchDate(dates[0])
    return date


@router.get("/dates")
def dates(request: Request) -> dict:
    """基準日の一覧と、その週にそろっているデータ(§7.1)。"""
    svc = services(request)
    out = []
    for date in svc.screen.dates():
        out.append(
            {
                "date": date,
                "weekday": svc.calendar.weekday_of(date),
                "has": {
                    "verdicts": True,
                    "picks": svc.picks.has(date),
                    "candidates": svc.candidates.has(date),
                },
            }
        )
    return {"dates": out, "latest": out[0]["date"] if out else None}


@router.get("/{date}/verdicts")
def verdicts(request: Request, date: str) -> dict:
    """判定表の全行。絞り込み・並べ替え・ページ送りは画面の中で行う(§8.6)。"""
    svc = services(request)
    date = resolve_date(svc, date)
    table = svc.screen.verdicts(date)

    try:
        index = svc.screen.results_index(date)
        failed = index.failed
    except FileNotFound:
        failed = []

    excluded = {row["code"] for row in failed}
    rows = [row for row in table.rows if row["code"] not in excluded]

    return {
        "date": date,
        "methods": [
            {"key": m["key"], "label": m["label"], "timeframe": table.timeframes.get(m["key"])}
            for m in METHODS
        ],
        "universe_count": svc.screen.universe_count(date) or len(rows),
        "sectors": [{"s33": c, "name": svc.sectors.name_of(c)} for c in sorted({r["s33"] for r in rows if r["s33"]})],
        "phases": _phases(rows),
        "rows": rows,
        "failed": failed,
    }


def _phases(rows: list[dict]) -> dict[str, list[str]]:
    """局面の選択肢は、その基準日の全行から集めて作る(§8.6)。"""
    found: dict[str, set[str]] = {m["key"]: set() for m in METHODS}
    for row in rows:
        for key, (_, phase) in row["v"].items():
            if phase:
                found[key].add(phase)
    return {k: sorted(v) for k, v in found.items()}


@router.get("/{date}/verdicts/{code}")
def verdict_detail(request: Request, date: str, code: str) -> dict:
    """根拠。``results.jsonl`` の中身をそのまま並べる(§5.4)。"""
    svc = services(request)
    date = resolve_date(svc, date)
    index = svc.screen.results_index(date)
    record = index.record(code) or index.record(f"{code}0")
    if record is None:
        raise NoData(f"verdicts/{code}")

    results = record.get("results", {})
    out: dict[str, object] = {}
    for method in METHODS:
        keys = method["results"]
        if len(keys) == 1:
            found = results.get(keys[0])
            if found:
                out[method["key"]] = _method_result(found)
        else:
            parts = {k: _method_result(results[k]) for k in keys if k in results}
            if parts:
                out[method["key"]] = parts
    return {"code": code, "name": record.get("name"), "methods": out}


def _method_result(found: dict) -> dict:
    """シグナルは日付の新しい順。``basis`` に「仮置き」があれば印を付ける(R4)。"""
    signals = []
    for signal in found.get("signals", []) or []:
        basis = signal.get("basis") or ""
        signals.append(
            {
                "date": signal.get("date"),
                "direction": signal.get("direction"),
                "name": signal.get("name"),
                "basis": basis,
                "provisional": "仮置き" in basis,
                "evidence": signal.get("evidence") or [],
            }
        )
    signals.sort(key=lambda s: s["date"] or "", reverse=True)
    return {
        "verdict": found.get("verdict"),
        "phase_label": found.get("phase_label"),
        "timeframe": found.get("timeframe"),
        "signals": signals,
        "notes": found.get("notes") or [],
    }


@router.get("/{date}/picks")
def picks(request: Request, date: str) -> dict:
    """来週の買い注文の候補(§7.2)。"""
    svc = services(request)
    date = resolve_date(svc, date)
    if not svc.picks.has(date):
        raise NoData("picks")
    data = svc.picks.read(date)
    # 注文の有効期間はカレンダーから出し、md と食い違ったら md を出す(§7.2)
    window = svc.calendar.order_window(date)
    validity = data["header"].get("validity") or {}
    if window and validity.get("start") and (window["start"], window["end"]) != (validity["start"], validity["end"]):
        data["header"]["validity_calendar"] = window
    elif window and not validity.get("start"):
        data["header"]["validity"] = {**validity, **window}
    return data


@router.get("/{date}/candidates")
def candidates(request: Request, date: str) -> dict:
    """買い候補(§7.3)。"""
    svc = services(request)
    date = resolve_date(svc, date)
    if not svc.candidates.has(date):
        raise NoData("candidates")
    rows = svc.candidates.read(date)
    return {
        "date": date,
        "method_filters": [{"key": m["key"], "label": m["label"]} for m in METHOD_FILTERS],
        "rows": rows,
    }
