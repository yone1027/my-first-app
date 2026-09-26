"""銘柄の検索(詳細設計書 §5.8)。"""

from __future__ import annotations

import csv
import unicodedata
from pathlib import Path

from fastapi import APIRouter, Query, Request

from ..batch.aggregate.jq import MasterIndex, rows_of, short_code
from ..readers.cache import FileCache

router = APIRouter(prefix="/api", tags=["search"])

EXCLUDED_MARKETS = {"0105", "0109"}
MARKETS = {"0111": "prime", "0112": "standard", "0113": "growth"}
LIMIT = 10

_cache = FileCache(max_entries=4)


def normalize(text: str) -> str:
    """NFKC で正規化し、英字は大文字にする(``Ｓａｎｓａｎ`` と ``Sansan`` を一致させる)。"""
    return unicodedata.normalize("NFKC", text or "").upper().strip()


def _load_master(path: Path) -> list[dict]:
    rows = []
    for row in rows_of(path):
        mkt = str(row.get("Mkt", "")).strip()
        if mkt in EXCLUDED_MARKETS:
            continue
        name = str(row.get("CoName", "")).strip()
        rows.append(
            {
                "code": short_code(str(row.get("Code", ""))),
                "name": name,
                "name_key": normalize(name),
                "market": MARKETS.get(mkt, mkt),
            }
        )
    return rows


def _load_universe(path: Path) -> set[str]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return {short_code((row.get("Code") or row.get("コード") or "").strip()) for row in csv.DictReader(fh)}


@router.get("/search")
def search(request: Request, q: str = Query(default="", max_length=64)) -> list[dict]:
    svc = request.app.state.services
    query = normalize(q)
    if not query:
        return []

    master = MasterIndex(svc.cfg.paths.jquants_raw / "equities__master")
    days = master.snapshot_days
    if not days:
        return []
    path = svc.cfg.paths.jquants_raw / "equities__master" / f"date={days[-1].isoformat()}.json.gz"
    rows = _cache.get(path, _load_master)

    universe: set[str] = set()
    dates = svc.screen.dates()
    if dates:
        universe_path = svc.screen.dir_for(dates[0]) / "universe.csv"
        if universe_path.exists():
            try:
                universe = _cache.get(universe_path, _load_universe)
            except Exception:
                universe = set()

    hits: list[tuple[int, int, dict]] = []
    # 入力が4〜5文字の英数字なら、コードの前方一致を先に並べる(§5.8)
    code_like = 4 <= len(query) <= 5 and query.isalnum()
    for row in rows:
        if code_like and row["code"].startswith(short_code(query)):
            hits.append((0, 0, row))
            continue
        position = row["name_key"].find(query)
        if position >= 0:
            hits.append((1, position, row))

    hits.sort(key=lambda h: (h[0], h[1], h[2]["code"]))
    return [
        {"code": r["code"], "name": r["name"], "market": r["market"], "in_universe": r["code"] in universe}
        for _, _, r in hits[:LIMIT]
    ]
