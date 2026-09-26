"""J-Quants のキャッシュを読む道具(詳細設計書 §6.1)。

キャッシュは**読むだけ**。足りない日付があっても取りに行かない(D1)。
"""

from __future__ import annotations

import gzip
import json
import logging
import re
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)

# 全銘柄のスナップショットは "date=YYYY-MM-DD.json.gz"。
# 同じフォルダに 1 銘柄だけの "code=85080_date=YYYY-MM-DD.json.gz" が混ざっているので、
# 名前が date= で**始まる**ものだけを採る(2026-09-26 に実物で確認)。
DATE_FILE = re.compile(r"^date=(\d{4}-\d{2}-\d{2})")
TO_DATE = re.compile(r"^from=\S*?to=(\d{4}-\d{2}-\d{2})")


def rows_of(path: Path) -> list[dict]:
    """``{"data": [...]}`` か、素の配列のどちらでも読む。"""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as fh:
        payload = json.load(fh)
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload if isinstance(payload, list) else []


def by_date(directory: Path) -> dict[date, Path]:
    """``date=YYYY-MM-DD`` のファイルを日付で引ける形にする。"""
    found: dict[date, Path] = {}
    if not directory.is_dir():
        log.warning("キャッシュのフォルダがありません: %s", directory)
        return found
    for child in directory.iterdir():
        m = DATE_FILE.match(child.name)
        if m:
            found[date.fromisoformat(m.group(1))] = child
    return found


def newest_by_to(directory: Path) -> Path | None:
    """``to=`` がいちばん新しいファイル(TOPIX・カレンダー用)。"""
    best: tuple[str, Path] | None = None
    if not directory.is_dir():
        log.warning("キャッシュのフォルダがありません: %s", directory)
        return None
    for child in directory.iterdir():
        m = TO_DATE.match(child.name)
        if m and (best is None or m.group(1) > best[0]):
            best = (m.group(1), child)
    return best[1] if best else None


def short_code(code: str) -> str:
    """5文字で末尾が 0 のときは末尾を落とす。"""
    code = (code or "").strip()
    return code[:-1] if len(code) == 5 and code.endswith("0") else code


def to_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class MasterIndex:
    """上場銘柄一覧のスナップショット(§6.1)。

    各日について「その日以前でいちばん近い日付の一覧」を使う。
    """

    def __init__(self, directory: Path):
        self._paths = dict(sorted(by_date(directory).items()))
        self._days = sorted(self._paths)
        self._loaded: dict[date, dict[str, dict]] = {}

    @property
    def snapshot_days(self) -> list[date]:
        return list(self._days)

    def _load(self, day: date) -> dict[str, dict]:
        cached = self._loaded.get(day)
        if cached is not None:
            return cached
        table = {}
        for row in rows_of(self._paths[day]):
            table[str(row.get("Code", "")).strip()] = {
                "mkt": str(row.get("Mkt", "")).strip(),
                "s33": str(row.get("S33", "")).strip(),
                "name": str(row.get("CoName", "")).strip(),
            }
        # 直近の数スナップショットだけ持つ(全件持つと重い)
        if len(self._loaded) >= 4:
            self._loaded.pop(next(iter(self._loaded)))
        self._loaded[day] = table
        return table

    def snapshot_for(self, day: date) -> dict[str, dict]:
        """その日以前でいちばん近いスナップショット。無ければいちばん古いもの。"""
        if not self._days:
            return {}
        usable = [d for d in self._days if d <= day]
        return self._load(usable[-1] if usable else self._days[0])
