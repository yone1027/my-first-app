"""取引カレンダー(詳細設計書 §7.4)。

``jquants_raw/markets__calendar/`` の ``to=`` がいちばん新しいファイルを読む。
"""

from __future__ import annotations

import gzip
import json
import logging
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path

from .cache import FileCache, FileNotFound

log = logging.getLogger(__name__)

# 1 銘柄だけのファイルが混ざるフォルダがあるので、名前の先頭から見る(§6.1)
TO_DATE = re.compile(r"^from=\S*?to=(\d{4}-\d{2}-\d{2})")
# HolDiv: 1 = 営業日、2 = 半日立会(営業日に数える。§6.3)
BUSINESS = {"1", "2"}
CUTOFF = time(17, 0)  # 17:00ルール


def newest_by_to(directory: Path) -> Path:
    """``to=`` がいちばん新しいファイル。無ければ FileNotFound。"""
    best: tuple[str, Path] | None = None
    if directory.is_dir():
        for child in directory.iterdir():
            m = TO_DATE.match(child.name)
            if m and (best is None or m.group(1) > best[0]):
                best = (m.group(1), child)
    if best is None:
        raise FileNotFound(directory)
    return best[1]


def load_rows(path: Path) -> list[dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as fh:
        payload = json.load(fh)
    return payload["data"] if isinstance(payload, dict) and "data" in payload else payload


def parse_calendar(path: Path) -> list[date]:
    """営業日の一覧(昇順)。"""
    days = []
    for row in load_rows(path):
        if str(row.get("HolDiv")) in BUSINESS:
            days.append(date.fromisoformat(row["Date"]))
    return sorted(days)


class CalendarReader:
    def __init__(self, jquants_raw: Path):
        self.directory = jquants_raw / "markets__calendar"
        self._cache = FileCache(max_entries=2)

    def business_days(self) -> list[date]:
        return self._cache.get(newest_by_to(self.directory), parse_calendar)

    def week_of(self, day: date) -> tuple[date, date]:
        """その日を含む月曜〜日曜の暦の週(§6.3)。"""
        monday = day - timedelta(days=day.weekday())
        return monday, monday + timedelta(days=6)

    def weeks(self) -> list[dict]:
        """営業日が1日以上ある週の一覧(昇順。§6.3)。"""
        buckets: dict[date, list[date]] = {}
        for day in self.business_days():
            buckets.setdefault(self.week_of(day)[0], []).append(day)
        weeks = []
        for monday in sorted(buckets):
            days = sorted(buckets[monday])
            weeks.append(
                {
                    "week_start": monday.isoformat(),
                    "week_end": days[-1].isoformat(),
                    "days": len(days),
                    "short": len(days) < 5,
                }
            )
        return weeks

    def settled_weeks(self, now: datetime) -> list[dict]:
        """``week_end`` の 17:00 を過ぎた週だけ(確定した週。§6.3)。"""
        return [w for w in self.weeks() if datetime.combine(date.fromisoformat(w["week_end"]), CUTOFF) <= now]

    def expected_week_end(self, now: datetime) -> str | None:
        """今の時刻より前に最終営業日の 17:00 を過ぎた、いちばん新しい週の最終営業日(§5.7)。"""
        settled = self.settled_weeks(now)
        return settled[-1]["week_end"] if settled else None

    def order_window(self, as_of: str) -> dict | None:
        """注文の有効期間: 基準日の翌営業日から、その週の最終営業日まで(§7.2)。"""
        try:
            days = self.business_days()
        except FileNotFound:
            return None
        base = date.fromisoformat(as_of)
        later = [d for d in days if d > base]
        if not later:
            return None  # カレンダーが基準日までしかない
        start = later[0]
        monday = self.week_of(start)[0]
        same_week = [d for d in later if self.week_of(d)[0] == monday]
        return {"start": start.isoformat(), "end": same_week[-1].isoformat(), "days": len(same_week)}

    def weekday_of(self, day: str) -> str:
        names = "月火水木金土日"
        return names[date.fromisoformat(day).weekday()]
