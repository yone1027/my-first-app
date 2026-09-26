"""日本をとりまく指標(詳細設計書 §6.8)。

**スプリント1の実装は保留している。** 財務省の CSV・日本銀行の時系列統計 API・
EIA の Open Data API v2 をどれも一度も取得しておらず、系列コード・CSV の形・
公表の時刻が**要確認**のままである(§12.4 の要確認 4・5)。

いまは空の結果を返し、``manifest.json`` の ``sources`` に理由を残す。
"""

from __future__ import annotations

# 出す指標(§6.8)
INDICATORS = ("jgb10y", "usdjpy", "wti")

NOT_BUILT_REASON = "not_implemented: 財務省・日本銀行・EIA を未取得(詳細設計書 §6.8・§12.4 の要確認 4・5)"


def aggregate(*_args, **_kwargs) -> list[dict]:
    return []
