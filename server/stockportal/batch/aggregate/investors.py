"""主体別売買動向(詳細設計書 §6.7)。

**スプリント1の実装は保留している。** J-Quants の ``/equities/investor-types``
を一度も取得しておらず、項目名・``Section`` の値・履歴の長さ・``PubDate`` の
曜日と時刻がどれも**要確認**のままである(§12.4 の要確認 1)。推測で項目名を
書くと、実物と食い違ったときに気づけないため、データを取ってから実装する。

いまは空の結果を返し、``manifest.json`` の ``sources`` に理由を残す。
サーバーはデータのない期間を ``null`` として扱い、画面はそのカードだけを
「データを読み込めませんでした」にする(§8.2 のカードごとの部分失敗)。
"""

from __future__ import annotations

# 画面に出す6つの主体(§6.7 の表。API の項目名は要確認)
SUBJECTS = ("foreigners", "individuals", "investment_trusts", "business_cos", "trust_banks", "proprietary")
SECTIONS = ("all", "prime", "standard", "growth")

NOT_BUILT_REASON = "not_implemented: /equities/investor-types を未取得(詳細設計書 §6.7・§12.4 の要確認 1)"


def aggregate(*_args, **_kwargs) -> list[dict]:
    return []
