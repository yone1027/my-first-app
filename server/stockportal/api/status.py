"""データの時点と「更新が遅れています」(詳細設計書 §5.7)。"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api", tags=["status"])

STEP_OF_SCREEN = {"verdicts": "screen", "picks": "weekly_picks", "candidates": "candidates"}


def _read_steps(status_dir: Path, date_str: str | None) -> dict[str, str]:
    """週次の後続の処理の実行状況(§4.6)。無ければ空。"""
    if not date_str:
        return {}
    path = status_dir / f"weekly_{date_str.replace('-', '')}.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    steps = payload.get("steps", {})
    return {k: (v.get("result") if isinstance(v, dict) else v) for k, v in steps.items()}


def _delayed_after(cfg, expected_week_end: str | None) -> datetime | None:
    """「``expected_week_end`` の週の土曜 12:00」(設定 ``delayed_after``)。"""
    if not expected_week_end:
        return None
    end = date.fromisoformat(expected_week_end)
    monday = end - timedelta(days=end.weekday())
    target = monday + timedelta(days=cfg.schedule.weekday)
    return datetime.combine(target, cfg.schedule.at)


@router.get("/status")
def status(request: Request) -> dict:
    svc = request.app.state.services
    cfg = svc.cfg
    now = datetime.now()

    try:
        expected = svc.calendar.expected_week_end(now)
    except Exception:  # カレンダーのキャッシュが無いこともある
        expected = None

    cutoff = _delayed_after(cfg, expected)
    past_cutoff = bool(cutoff and now >= cutoff)

    # 市場概況
    try:
        market = svc.market.read()
        market_week = market.manifest.get("latest_week_end")
        market_updated = market.manifest.get("generated_at")
    except Exception:
        market_week = market_updated = None
    market_delayed = bool(past_cutoff and expected and (market_week or "") < expected)

    # 週次の分析結果
    dates = svc.screen.dates()
    latest = dates[0] if dates else None
    updated = None
    for reader, has in ((svc.screen, True), (svc.picks, bool(latest and svc.picks.has(latest))), (svc.candidates, bool(latest and svc.candidates.has(latest)))):
        if latest and has:
            stamp = reader.last_updated(latest)
            if stamp:
                updated = max(updated or 0.0, stamp)

    steps = _read_steps(cfg.paths.status_dir, latest)
    step_failed = any(v in ("failed", "timeout") for v in steps.values())
    weekly_delayed = bool(past_cutoff and expected and (latest or "") < expected) or step_failed

    return {
        "now": now.astimezone().isoformat(timespec="seconds"),
        "expected_week_end": expected,
        "delayed_after": cfg.schedule.raw,
        "market": {"data_week_end": market_week, "last_updated": market_updated, "delayed": market_delayed},
        "weekly": {
            "latest_date": latest,
            "last_updated": datetime.fromtimestamp(updated).astimezone().isoformat(timespec="seconds") if updated else None,
            "delayed": weekly_delayed,
            "steps": steps,
        },
    }


@router.get("/theme")
def theme(request: Request) -> dict:
    """色と書体(基本設計書 §4.8)。画面が CSS 変数に流し込む。"""
    return dict(request.app.state.services.cfg.theme)


@router.get("/health")
def health() -> dict:
    return {"ok": True}
