"""日本をとりまく指標(詳細設計書 §6.8)。

| 指標 | 取り方 | 状態 |
|---|---|---|
| `jgb10y` | 財務省の CSV | **実装済み**(2026-09-27) |
| `usdjpy` | 未定 | **保留**。日本銀行は直接取れる CSV を公開しておらず、財務省にも日次の
  ドル円はない(2026-09-27 に確認)。取得元を決めてから実装する |
| `wti` | EIA API v2 `petroleum/pri/spt`、系列 `RWTC` | **保留**。無料の API キーが必要 |

週の値は、その週の最終営業日の値。なければ、その週の中でいちばん新しい日の値。
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from .sources import mof

log = logging.getLogger(__name__)

# 出す指標(§6.8)
INDICATORS = ("jgb10y", "usdjpy", "wti")

USDJPY_REASON = (
    "not_implemented: ドル円の取得元が未定。日本銀行は直接取れる CSV を公開しておらず"
    "(直近70営業日の PDF と、フォーム操作前提の検索サイトのみ)、財務省にも日次のドル円はない"
    "(2026-09-27 に確認。詳細設計書 §6.8)"
)
WTI_REASON = "not_implemented: EIA の API キーが未設定(/Users/yone/StockPortal/.env の EIA_API_KEY)"
NOT_BUILT_REASON = USDJPY_REASON  # 互換のため残す


def week_value(values: dict[date, float], week_days: list[date]) -> tuple[float, date] | None:
    """その週の最終営業日の値。なければ、その週で値のあるいちばん新しい日。"""
    for day in reversed(week_days):
        if day in values:
            return values[day], day
    return None


def aggregate(cfg=None, weeks: list[dict] | None = None, now: datetime | None = None,
              warnings: list[str] | None = None, rebuild: bool = False) -> list[dict]:
    """``indicators.csv`` の行(``week_end, indicator, value, obs_date``)。"""
    if cfg is None or not weeks:
        return []
    warnings = warnings if warnings is not None else []
    out: list[dict] = []

    # ---- jgb10y(財務省)----
    cache_dir = cfg.paths.raw_dir / "mof"
    try:
        values = mof.load_cache(cache_dir)
        # 全期間の CSV は、無いときと --rebuild のときだけ取る(重いので毎回は取らない)
        if not (cache_dir / "jgbcm_all.csv").exists() or rebuild:
            values.update(mof.fetch(full=True, cache_dir=cache_dir))
        # 当月の CSV は**毎回**取る。全期間の CSV は前月までしか入っていないため、
        # これを飛ばすと今月の週が埋まらない(2026-09-27 に踏んだ)。
        values.update(mof.fetch(full=False, cache_dir=cache_dir))
        log.info("10年国債利回り: %d 日分(いちばん新しい日 %s)", len(values), max(values) if values else "—")
    except mof.FetchError as exc:
        log.warning("10年国債利回りを取れませんでした: %s", exc)
        warnings.append(f"10年国債利回りを取れませんでした({exc})。前回のキャッシュで続けます")
        values = mof.load_cache(cache_dir)

    for week in weeks:
        found = week_value(values, week["_days"])
        if found is None:
            continue  # まだ公表されていない週は行を出さない(§6.8)
        value, obs = found
        out.append({"week_end": week["week_end"], "indicator": "jgb10y", "value": value, "obs_date": obs.isoformat()})

    # ---- usdjpy・wti は保留(上の表のとおり)----
    return out


def sources_status(built: list[dict]) -> dict:
    """``manifest.json`` の ``sources`` に書く内容(§6.9)。"""
    has_jgb = any(r["indicator"] == "jgb10y" for r in built)
    return {
        "mof": {"ok": has_jgb} if has_jgb else {"ok": False, "error": "10年国債利回りを取れませんでした"},
        "boj": {"ok": False, "error": USDJPY_REASON},
        "eia": {"ok": False, "error": WTI_REASON},
    }
