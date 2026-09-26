"""主体別売買動向(詳細設計書 §6.7)。

J-Quants ``/equities/investor-types`` を取る。項目名は 2026-09-27 に実物で確認した。
各主体に ``Sell``(売り)・``Buy``(買い)・``Tot``(合計)・``Bal``(差引)があり、
画面で使うのは差引(``Bal``)。
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, time as clock, timedelta
from pathlib import Path

from .sources.jquants import FetchError, fetch_pages, load_api_key, load_cache, save_cache

log = logging.getLogger(__name__)

ENDPOINT = "/equities/investor-types"
CACHE_NAME = "investor_types.json"
CUTOFF = clock(17, 0)  # 17:00ルール。公表日の 17:00 より後にしか使えない

# API の金額は**千円**単位(2026-09-27 に実測で確定)。
# 同じ週・同じ区分について、投資部門別の TotTot(売り+買い)と、自前の売買代金×2 を
# 6組で突き合わせ、比が 873〜1002 になった(グロースは 988・1002)。
# プライムがやや低いのは、投資部門別が委託+自己で東京・名古屋の合計であるため。
THOUSAND_YEN = 1000

# 画面に出す6つの主体(§6.7 の表)。API の接頭辞は 2026-09-27 に実物で確認。
SUBJECT_FIELDS: dict[str, tuple[str, ...]] = {
    "foreigners": ("Frgn",),
    "individuals": ("Ind",),
    "investment_trusts": ("InvTr",),
    "business_cos": ("BusCo",),
    "trust_banks": ("TrstBnk",),
    "proprietary": ("Prop",),
    # 画面では出さない。生保・損保、都銀・地銀等、その他金融機関、その他法人の合計
    "other": ("InsCo", "Bank", "OthFin", "OthCo"),
}
SUBJECTS = tuple(SUBJECT_FIELDS)

# Section の値 → scope。8種類すべてを 2026-09-27 に実物で確認した。
#   TokyoNagoya  520件(2016-09-20〜。全期間)     = 東京・名古屋の合計。これを「東証全体」とする
#   TSEPrime/Standard/Growth  各232件(2022-04-04〜)
#   TSE1st/2nd/Mothers/JASDAQ 各288件(〜2022-04-01)
SECTION_OF = {
    "TokyoNagoya": "all",      # 公式の合計。3区分を足して作らない
    "TSEPrime": "prime",
    "TSEStandard": "standard",
    "TSEGrowth": "growth",
    "TSE1st": "legacy_1st",
    "TSE2nd": "legacy_2nd",
    "TSEMothers": "legacy_mothers",
    "TSEJASDAQ": "legacy_jasdaq",
}

# 契約の範囲外を指定したときの 400 の本文から、開始日を読み取る
COVERED_FROM = re.compile(r"subscription covers the following dates:\s*(\d{4}-\d{2}-\d{2})")

NOT_BUILT_REASON = "fetch_failed: /equities/investor-types を取れませんでした"


def _balance(row: dict, prefixes: tuple[str, ...]) -> float | None:
    """差引(``Bal``)の合計。1つでも取れれば返す。"""
    total = 0.0
    found = False
    for prefix in prefixes:
        value = row.get(f"{prefix}Bal")
        if value is None or value == "":
            continue
        try:
            total += float(value)
            found = True
        except (TypeError, ValueError):
            log.warning("%sBal が数になりません: %r", prefix, value)
    return total if found else None


def fetch(cfg, now: datetime, warnings: list[str], rebuild: bool) -> list[dict]:
    """API から取り、キャッシュに足す。取れなければ前回のキャッシュで続ける。"""
    cache = cfg.paths.raw_dir / "investor_types" / CACHE_NAME
    previous = load_cache(cache)

    # 前回のキャッシュの最後の週から取る(§6.7)。初回は契約が届くいちばん古い日から。
    # スタンダードプランは10年前まで。契約の範囲外を指定すると 400 が返り、
    # 本文に "Your subscription covers the following dates: YYYY-MM-DD ~" が入る
    # (2026-09-27 に確認)。その日付を読み取って、1回だけやり直す。
    start = (now.date() - timedelta(days=365 * 10 + 5)).isoformat()
    if previous and not rebuild:
        newest = max((r.get("EnDate") or "") for r in previous)
        if newest:
            start = newest

    try:
        key = load_api_key(cfg.paths.jquants_env)
    except FetchError as exc:
        log.warning("投資部門別情報: %s", exc)
        warnings.append(f"投資部門別情報を取れませんでした({exc})。前回のキャッシュで続けます")
        return previous

    for attempt in (1, 2):
        try:
            rows = fetch_pages(
                ENDPOINT,
                {"from": start, "to": now.date().isoformat()},
                key,
                cfg.api.jquants_per_minute,
            )
            break
        except FetchError as exc:
            covered = COVERED_FROM.search(str(exc))
            if attempt == 1 and covered:
                start = covered.group(1)
                log.info("投資部門別情報: 契約の範囲に合わせて %s から取り直します", start)
                continue
            log.warning("投資部門別情報を取れませんでした: %s", exc)
            warnings.append(f"投資部門別情報を取れませんでした({exc})。前回のキャッシュで続けます")
            return previous
        except Exception as exc:  # 接続の問題で集計全体を止めない
            message = f"{type(exc).__name__}: {exc}"
            log.warning("投資部門別情報を取れませんでした: %s", message)
            warnings.append(f"投資部門別情報を取れませんでした({message})。前回のキャッシュで続けます")
            return previous

    # 週と区分が同じ行は、新しく取れたものを採る
    merged = {(r.get("StDate"), r.get("Section")): r for r in previous}
    merged.update({(r.get("StDate"), r.get("Section")): r for r in rows})
    combined = sorted(merged.values(), key=lambda r: (r.get("StDate") or "", r.get("Section") or ""))
    save_cache(cache, combined)
    log.info("投資部門別情報: 取得 %d 行 / キャッシュ合計 %d 行", len(rows), len(combined))
    return combined


def aggregate(cfg=None, now: datetime | None = None, warnings: list[str] | None = None, rebuild: bool = False) -> list[dict]:
    """``investors.csv`` の行(``week_start, week_end, section, subject, balance_yen, pub_date``)。"""
    if cfg is None:  # 呼び出し側が用意できていないときは空(§6.7)
        return []
    now = now or datetime.now()
    warnings = warnings if warnings is not None else []

    rows = fetch(cfg, now, warnings, rebuild)
    out: list[dict] = []
    unknown_sections: set[str] = set()

    for row in rows:
        pub = row.get("PubDate")
        if not pub:
            continue
        # 17:00ルール: 公表日の 17:00 を過ぎていない週は、まだ使えない
        try:
            if datetime.combine(date.fromisoformat(pub), CUTOFF) > now:
                continue
        except ValueError:
            continue

        raw_section = str(row.get("Section") or "")
        section = SECTION_OF.get(raw_section)
        if section is None:
            unknown_sections.add(raw_section)
            continue

        for subject, prefixes in SUBJECT_FIELDS.items():
            balance = _balance(row, prefixes)
            if balance is None:
                continue
            out.append(
                {
                    "week_start": row.get("StDate"),
                    "week_end": row.get("EnDate"),
                    "section": section,
                    "subject": subject,
                    "balance_yen": round(balance * THOUSAND_YEN),
                    "pub_date": pub,
                }
            )

    if unknown_sections:
        log.info("知らない Section は飛ばしました: %s", sorted(unknown_sections))
        warnings.append(f"知らない Section: {sorted(unknown_sections)}")

    # 「東証全体」は TokyoNagoya(公式の合計)をそのまま使う。3区分を足して作らない。
    return sorted(out, key=lambda r: (r["week_end"] or "", r["section"], r["subject"]))
