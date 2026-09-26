"""売買代金の集計(詳細設計書 §6.4)。

週・区分・業種ごとに ``Va``(円)を合計する。ETF・REIT(``0109``)と
TOKYO PRO MARKET(``0105``)は外す(2026-09-26 確定)。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date
from pathlib import Path

from .jq import MasterIndex, by_date, rows_of, to_float

log = logging.getLogger(__name__)

# Mkt → scope(§6.4)
SCOPE_OF_MKT = {"0111": "prime", "0112": "standard", "0113": "growth"}
# 2022年4月の市場再編より前の区分。新区分に読み替えず、別の値で保存する(§6.4)。
LEGACY_SCOPE_OF_MKT = {
    "0101": "legacy_1st",
    "0102": "legacy_2nd",
    "0104": "legacy_mothers",
    "0106": "legacy_jasdaq_standard",
    "0107": "legacy_jasdaq_growth",
    "0103": "legacy_other",
}
SCOPE_ALL = "all"   # 全体(§6.4 の表)
S33_ALL = "ALL"     # 業種を分けない


def aggregate(
    jquants_raw: Path,
    weeks: list[dict],
    exclude_markets: tuple[str, ...],
    warnings: list[str],
) -> list[dict]:
    """``turnover.csv`` の行(``week_end, scope, s33, turnover_yen, n_codes``)。"""
    bars = by_date(jquants_raw / "equities__bars__daily")
    master = MasterIndex(jquants_raw / "equities__master")
    excluded = set(exclude_markets)
    out: list[dict] = []

    for week in weeks:
        # (scope, s33) → [売買代金の合計, 銘柄数]
        sums: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0])
        unknown_codes = 0
        for day in week["_days"]:
            path = bars.get(day)
            if path is None:
                warnings.append(f"{day.isoformat()}: 株価のキャッシュがない")
                continue
            snapshot = master.snapshot_for(day)
            for row in rows_of(path):
                value = to_float(row.get("Va"))
                if not value:
                    continue
                info = snapshot.get(str(row.get("Code", "")).strip())
                if info is None:
                    unknown_codes += 1
                    continue
                mkt = info["mkt"]
                if mkt in excluded:
                    continue
                scope = SCOPE_OF_MKT.get(mkt) or LEGACY_SCOPE_OF_MKT.get(mkt)
                if scope is None:
                    unknown_codes += 1
                    continue
                s33 = info["s33"] or "9999"
                for key in ((SCOPE_ALL, S33_ALL), (SCOPE_ALL, s33), (scope, S33_ALL), (scope, s33)):
                    sums[key][0] += value
                    sums[key][1] += 1

        if unknown_codes:
            log.info("%s: 銘柄一覧に無い/区分が不明な行を %d 件飛ばしました", week["week_end"], unknown_codes)
        for (scope, s33), (total, count) in sorted(sums.items()):
            out.append(
                {
                    "week_end": week["week_end"],
                    "scope": scope,
                    "s33": s33,
                    "turnover_yen": round(total),
                    "n_codes": count,
                }
            )
    return out
