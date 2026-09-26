"""財務省の国債金利情報(詳細設計書 §6.8)。

``jgbcm_all.csv``(全期間)と ``jgbcm.csv``(当月)。Shift_JIS、日付は和暦。
キーも登録も不要(2026-09-27 に実物で確認)。
"""

from __future__ import annotations

import csv
import io
import logging
import re
from datetime import date
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

BASE = "https://www.mof.go.jp/jgbs/reference/interest_rate"
# 全期間は data/ の下にある(2026-09-27 に実物で確認。昭和49年〜)
ALL_URL = f"{BASE}/data/jgbcm_all.csv"   # 全期間(初回だけ)
MONTH_URL = f"{BASE}/jgbcm.csv"          # 当月(以後)
COLUMN = "10年"
ENCODING = "shift_jis"

# 和暦: R8.9.25(令和)/ H31.4.30(平成)/ S64.1.7(昭和)
WAREKI = re.compile(r"^([RHS])(\d+)\.(\d+)\.(\d+)$")
ERA_START = {"R": 2018, "H": 1988, "S": 1925}  # 元年 = 開始年 + 1


class FetchError(Exception):
    pass


def to_date(text: str) -> date | None:
    """和暦の日付を西暦にする。読めなければ None。"""
    m = WAREKI.match((text or "").strip())
    if not m:
        return None
    era, year, month, day = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
    try:
        return date(ERA_START[era] + year, month, day)
    except (KeyError, ValueError):
        return None


def to_float(text: str) -> float | None:
    text = (text or "").strip()
    if not text or text == "-":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse(body: bytes) -> dict[date, float]:
    """日付 → 10年利回り(%)。列は名前で探す(列の増減に強くする)。"""
    text = body.decode(ENCODING, errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    header_at = None
    for i, row in enumerate(rows[:10]):
        if row and row[0].strip() == "基準日":
            header_at = i
            break
    if header_at is None:
        raise FetchError("「基準日」の行が見つかりません")
    header = [c.strip() for c in rows[header_at]]
    if COLUMN not in header:
        raise FetchError(f"「{COLUMN}」の列がありません(実際の列: {header[:12]})")
    at = header.index(COLUMN)

    values: dict[date, float] = {}
    for row in rows[header_at + 1 :]:
        if not row or len(row) <= at:
            continue
        day = to_date(row[0])
        value = to_float(row[at])
        if day is not None and value is not None:
            values[day] = value
    if not values:
        raise FetchError("値のある行がありません")
    return values


def fetch(full: bool, cache_dir: Path) -> dict[date, float]:
    """取る。取れたら生のまま保存しておく(あとで形を確かめられるように)。"""
    url = ALL_URL if full else MONTH_URL
    try:
        response = httpx.get(url, timeout=60.0, follow_redirects=True)
    except httpx.HTTPError as exc:
        raise FetchError(f"{url}: {exc}") from exc
    if response.status_code != 200:
        raise FetchError(f"{url}: HTTP {response.status_code}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    name = "jgbcm_all.csv" if full else "jgbcm.csv"
    (cache_dir / name).write_bytes(response.content)
    return parse(response.content)


def load_cache(cache_dir: Path) -> dict[date, float]:
    """保存した CSV から読み直す(取れなかったときに使う)。"""
    values: dict[date, float] = {}
    for name in ("jgbcm_all.csv", "jgbcm.csv"):
        path = cache_dir / name
        if not path.exists():
            continue
        try:
            values.update(parse(path.read_bytes()))
        except FetchError as exc:
            log.warning("%s を読めません: %s", path, exc)
    return values
