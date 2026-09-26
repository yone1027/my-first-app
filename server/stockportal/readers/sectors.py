"""33業種のコード → 名前(詳細設計書 §6.4 の補助)。

集計の出力(``turnover.csv``)は業種コードだけを持つ。画面に出す名前は、
最新の銘柄一覧(``S33``/``S33Nm``)から引く。
"""

from __future__ import annotations

from pathlib import Path

from ..batch.aggregate.jq import MasterIndex, rows_of
from .cache import FileCache

# 「その他」。33業種に含めない(一覧に出さないが、全体の分母には残す)
OTHER = "9999"

_cache = FileCache(max_entries=2)


def _load(path: Path) -> dict[str, str]:
    names: dict[str, str] = {}
    for row in rows_of(path):
        code = str(row.get("S33", "")).strip()
        name = str(row.get("S33Nm", "")).strip()
        if code and name:
            names.setdefault(code, name)
    return names


class SectorNames:
    def __init__(self, jquants_raw: Path):
        self._dir = jquants_raw / "equities__master"

    def names(self) -> dict[str, str]:
        days = MasterIndex(self._dir).snapshot_days
        if not days:
            return {}
        return _cache.get(self._dir / f"date={days[-1].isoformat()}.json.gz", _load)

    def name_of(self, code: str) -> str:
        return self.names().get(code, code)
