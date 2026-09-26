"""週の一覧(詳細設計書 §6.3)。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from .jq import newest_by_to, rows_of
from pathlib import Path

BUSINESS = {"1", "2"}  # 1 = 営業日、2 = 半日立会(営業日に数える)
CUTOFF = time(17, 0)


def business_days(jquants_raw: Path) -> list[date]:
    path = newest_by_to(jquants_raw / "markets__calendar")
    if path is None:
        return []
    days = [date.fromisoformat(r["Date"]) for r in rows_of(path) if str(r.get("HolDiv")) in BUSINESS]
    return sorted(days)


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def build(jquants_raw: Path, now: datetime) -> list[dict]:
    """確定した週だけを、昇順で返す。"""
    buckets: dict[date, list[date]] = {}
    for day in business_days(jquants_raw):
        buckets.setdefault(week_start(day), []).append(day)

    weeks = []
    for monday in sorted(buckets):
        days = sorted(buckets[monday])
        end = days[-1]
        if datetime.combine(end, CUTOFF) > now:
            continue  # まだ確定していない週は出さない
        weeks.append(
            {
                "week_start": monday.isoformat(),
                "week_end": end.isoformat(),
                "days": len(days),
                "short": len(days) < 5,
                "_days": days,
            }
        )
    return weeks
