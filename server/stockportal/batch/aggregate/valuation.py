"""市場全体の EPS・PER(詳細設計書 §6.6)。

単位: ``MktCap`` は百万円、``FNP``/``NxFNp`` は円の文字列(2026-09-26 確定)。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, time
from pathlib import Path

from .jq import MasterIndex, by_date, rows_of, to_float
from .turnover import LEGACY_SCOPE_OF_MKT, SCOPE_OF_MKT, S33_ALL, SCOPE_ALL

log = logging.getLogger(__name__)

CUTOFF = time(17, 0)
MKTCAP_YEN = 1_000_000  # MktCap(百万円) → 円

# 本決算は翌期の予想 NxFNp、それ以外は当期の予想 FNP(2026-09-26 確認。§6.6)
FY_PREFIX = "FYFinancialStatements"
# 配当だけの修正は、どちらの項目も空なので読み飛ばす
SKIP_DOCTYPES = {"DividendForecastRevision", "REITEarnForecastRevision"}

# 株数(MktCap ÷ 終値)がこの倍率を超えて変わったら、分割の調整係数と合っているかを確かめる
SHARES_JUMP = 1.5


def _consistent(shares: float, expected: float) -> bool:
    return expected > 0 and 1 / SHARES_JUMP < shares / expected < SHARES_JUMP


class SplitGuard:
    """J-Quants の ``MktCap`` が、株式分割の数日後に分割の比率をもう一度かけた値になることへの備え。

    2026-09-29 の分割(東京エレクトロン 1:5 など)で、10/1〜10/5 の ``MktCap`` が5倍になっていた
    (J-Quants から取り直しても同じ。10/9 には直っている)。前の週の株数を、間の日の ``AdjFactor`` で
    割り戻した株数と比べ、合わなければその株数で計算し直す。直すのは間に分割があった銘柄だけで、
    分割と同じ時期に株数が本当に変わったときも、2週続けて同じ株数なら J-Quants の値を正とする。
    """

    def __init__(self, bars: dict[date, Path]):
        self._bars = bars
        self._days = sorted(bars)
        self._adj: dict[date, dict[str, float]] = {}
        self._shares: dict[str, tuple[float, date]] = {}   # 銘柄 → (株数, その日)
        self._pending: dict[str, float] = {}               # 前の週に直した銘柄 → J-Quants の株数
        self.fixed: list[tuple[date, str]] = []

    def _adj_of(self, day: date) -> dict[str, float]:
        if day not in self._adj:
            found = {}
            for row in rows_of(self._bars[day]):
                factor = to_float(row.get("AdjFactor"))
                if factor and factor != 1.0:
                    found[str(row.get("Code", "")).strip()] = factor
            self._adj[day] = found
        return self._adj[day]

    def _adj_product(self, code: str, after: date, upto: date) -> float:
        product = 1.0
        for day in self._days:
            if after < day <= upto:
                product *= self._adj_of(day).get(code, 1.0)
        return product

    def mktcap(self, code: str, mktcap: float, close: float | None, day: date) -> float:
        """その日の時価総額(百万円)。株数が分割の調整と合わなければ直した値。"""
        if not close or close <= 0:
            return mktcap
        shares = mktcap / close
        ref = self._shares.get(code)
        if ref is not None and not _consistent(shares, ref[0]):
            product = self._adj_product(code, ref[1], day)
            expected = ref[0] / product
            # 分割が無いのに株数が変わったのは、第三者割当などの本当の変化(2026-09-09 の日本板硝子)
            if product != 1.0 and not _consistent(shares, expected):
                seen = self._pending.get(code)
                if seen is None or not _consistent(shares, seen):
                    self._pending[code] = shares
                    self.fixed.append((day, code))
                    self._shares[code] = (expected, day)
                    return expected * close
        self._pending.pop(code, None)
        self._shares[code] = (shares, day)
        return mktcap


def _disclosed_at(row: dict) -> datetime | None:
    day = str(row.get("DiscDate") or "").strip()
    if not day:
        return None
    clock = str(row.get("DiscTime") or "").strip() or "00:00:00"
    try:
        parts = [int(p) for p in clock.split(":")]
        while len(parts) < 3:
            parts.append(0)
        return datetime.combine(date.fromisoformat(day), time(*parts[:3]))
    except ValueError:
        return None


def _forecast_of(row: dict) -> float | None:
    """その開示から使う予想の当期純利益(円)。無ければ None。"""
    doc_type = str(row.get("DocType") or "")
    if doc_type in SKIP_DOCTYPES:
        return None
    field = "NxFNp" if doc_type.startswith(FY_PREFIX) else "FNP"
    return to_float(row.get(field))


def load_disclosures(jquants_raw: Path) -> list[tuple[datetime, str, float]]:
    """(開示の日時, 銘柄コード, 予想の当期純利益)を日時の順に並べて返す。"""
    found: list[tuple[datetime, str, float]] = []
    for path in by_date(jquants_raw / "fins__summary").values():
        for row in rows_of(path):
            at = _disclosed_at(row)
            profit = _forecast_of(row)
            if at is None or profit is None:
                continue
            found.append((at, str(row.get("Code", "")).strip(), profit))
    found.sort(key=lambda x: x[0])
    return found


def aggregate(
    jquants_raw: Path,
    weeks: list[dict],
    topix_rows: list[dict],
    exclude_markets: tuple[str, ...],
    warnings: list[str],
) -> list[dict]:
    """``valuation.csv`` の行。週 × (all + 3区分)。"""
    disclosures = load_disclosures(jquants_raw)
    if not disclosures:
        warnings.append("決算短信のキャッシュがない")
        return []

    bars = by_date(jquants_raw / "equities__bars__daily")
    master = MasterIndex(jquants_raw / "equities__master")
    guard = SplitGuard(bars)
    excluded = set(exclude_markets)
    topix_close = {r["week_end"]: r["close"] for r in topix_rows}

    # 週を進めながら「その週の 17:00 までに開示された最後の1件」を持ち回す
    latest: dict[str, float] = {}
    cursor = 0
    out: list[dict] = []

    for week in weeks:
        deadline = datetime.combine(date.fromisoformat(week["week_end"]), CUTOFF)
        while cursor < len(disclosures) and disclosures[cursor][0] <= deadline:
            _, code, profit = disclosures[cursor]
            latest[code] = profit
            cursor += 1

        # その週の最終営業日の時価総額
        last_day = None
        for day in reversed(week["_days"]):
            if day in bars:
                last_day = day
                break
        if last_day is None:
            warnings.append(f"{week['week_end']}: 時価総額のもとになる株価のキャッシュがない")
            continue
        snapshot = master.snapshot_for(last_day)

        # scope → [時価総額の合計(円), 利益の合計(円), 対象銘柄, 赤字で除いた銘柄]
        sums: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0, 0])
        for row in rows_of(bars[last_day]):
            code = str(row.get("Code", "")).strip()
            mktcap = to_float(row.get("MktCap"))
            if mktcap is None:
                continue
            mktcap = guard.mktcap(code, mktcap, to_float(row.get("C")), last_day)
            info = snapshot.get(code)
            if info is None or info["mkt"] in excluded:
                continue
            scope = SCOPE_OF_MKT.get(info["mkt"]) or LEGACY_SCOPE_OF_MKT.get(info["mkt"])
            if scope is None:
                continue
            profit = latest.get(code)
            if profit is None:
                continue  # 会社予想を出していない銘柄は数えない
            keys = (SCOPE_ALL, scope)
            if profit > 0:
                for key in keys:
                    sums[key][0] += mktcap * MKTCAP_YEN
                    sums[key][1] += profit
                    sums[key][2] += 1
            else:
                for key in keys:
                    sums[key][3] += 1  # 赤字予想は分子からも分母からも外す

        for scope, (mktcap_sum, np_sum, n_target, n_loss) in sorted(sums.items()):
            per = mktcap_sum / np_sum if np_sum > 0 else None
            close = topix_close.get(week["week_end"])
            eps = (close / per) if (per and scope == SCOPE_ALL and close) else None
            out.append(
                {
                    "week_end": week["week_end"],
                    "scope": scope,
                    "mktcap_sum": round(mktcap_sum),
                    "np_sum": round(np_sum),
                    "n_target": n_target,
                    "n_excluded_loss": n_loss,
                    "per": per,
                    "eps": eps,
                }
            )
    if guard.fixed:
        log.info("時価総額を株数の食い違いで直した: %d 件(例: %s)", len(guard.fixed),
                 ", ".join(f"{d} {c}" for d, c in guard.fixed[-5:]))
    return out
