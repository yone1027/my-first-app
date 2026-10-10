"""市場概況の集計の入口(詳細設計書 §6)。

``python -m stockportal.batch.aggregate [--rebuild] [--as-of YYYY-MM-DD]``
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

from ... import config
from . import indicators, investors, topix, turnover, valuation, weeks as weeks_mod

log = logging.getLogger("stockportal.aggregate")

SCHEMA_VERSION = 1

# ファイル名 → 列の順(§6.9)
COLUMNS: dict[str, tuple[str, ...]] = {
    "weeks.csv": ("week_start", "week_end", "days", "short"),
    "turnover.csv": ("week_end", "scope", "s33", "turnover_yen", "n_codes"),
    "topix.csv": ("week_end", "close", "ma13", "ma26", "ma52"),
    "valuation.csv": ("week_end", "scope", "mktcap_sum", "np_sum", "n_target", "n_excluded_loss", "per", "eps"),
    "investors.csv": ("week_start", "week_end", "section", "subject", "balance_yen", "pub_date"),
    "indicators.csv": ("week_end", "indicator", "value", "obs_date"),
}


def write_csv(path: Path, columns: tuple[str, ...], rows: list[dict]) -> None:
    """UTF-8(BOM なし)。値が None のときは空にする。"""
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: ("" if row.get(c) is None else row.get(c)) for c in columns})


def latest_week_end(rows: list[dict]) -> str | None:
    return max((r["week_end"] for r in rows), default=None)


def run(cfg: config.Config, now: datetime, rebuild: bool) -> dict:
    """集計して ``data/market/`` を入れ替える。manifest を返す。"""
    raw = cfg.paths.jquants_raw
    warnings: list[str] = []

    log.info("週の一覧を作ります")
    all_weeks = weeks_mod.build(raw, now)
    if not all_weeks:
        raise SystemExit("取引カレンダーのキャッシュが読めないため、集計できません")

    # 差分か全体か(§6.2)。差分でも topix は全履歴で作る(移動平均線のため)。
    target = all_weeks
    if not rebuild:
        keep = cfg.aggregate.recompute_weeks
        target = all_weeks[-keep:] if keep > 0 else all_weeks
        log.info("差分で集計します(最後の %d 週を作り直します)", keep)
    else:
        log.info("全期間を作り直します(%d 週)", len(all_weeks))

    log.info("TOPIX")
    topix_rows = topix.aggregate(raw, all_weeks, warnings)
    log.info("売買代金(%d 週)", len(target))
    turnover_rows = turnover.aggregate(raw, target, cfg.aggregate.exclude_markets, warnings)
    log.info("EPS・PER(%d 週)", len(target))
    valuation_rows = valuation.aggregate(raw, target, topix_rows, cfg.aggregate.exclude_markets, warnings)

    log.info("主体別売買動向")
    investor_rows = investors.aggregate(cfg, now, warnings, rebuild)
    log.info("日本をとりまく指標")
    indicator_rows = indicators.aggregate(cfg, all_weeks, now, warnings, rebuild)

    # 差分のときは、前回の結果に重ねる
    if not rebuild:
        turnover_rows = merge_by_week(cfg.paths.market_dir / "turnover.csv", turnover_rows, target)
        valuation_rows = merge_by_week(cfg.paths.market_dir / "valuation.csv", valuation_rows, target)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.astimezone().isoformat(timespec="seconds"),
        "as_of": all_weeks[-1]["week_end"],
        "latest_week_end": all_weeks[-1]["week_end"],
        "datasets": {
            "turnover": {"latest_week_end": latest_week_end(turnover_rows)},
            "valuation": {"latest_week_end": latest_week_end(valuation_rows)},
            "investors": {
                "latest_week_end": latest_week_end(investor_rows),
                "latest_pub_date": max((r["pub_date"] for r in investor_rows), default=None),
            },
            "indicators": {
                key: max((r["week_end"] for r in indicator_rows if r["indicator"] == key), default=None)
                for key in indicators.INDICATORS
            },
        },
        "sources": {
            "investor_types": (
                {"ok": True} if investor_rows else {"ok": False, "error": investors.NOT_BUILT_REASON}
            ),
            **indicators.sources_status(indicator_rows),
        },
        "warnings": warnings[:200],
    }

    publish(
        cfg.paths.portal_data,
        {
            "weeks.csv": [{k: v for k, v in w.items() if not k.startswith("_")} for w in all_weeks],
            "turnover.csv": turnover_rows,
            "topix.csv": topix_rows,
            "valuation.csv": valuation_rows,
            "investors.csv": investor_rows,
            "indicators.csv": indicator_rows,
        },
        manifest,
    )
    return manifest


def merge_by_week(previous: Path, fresh: list[dict], recomputed: list[dict]) -> list[dict]:
    """作り直した週は新しい値、それより前の週は前回の値を使う(§6.2)。"""
    if not previous.exists():
        return fresh
    redone = {w["week_end"] for w in recomputed}
    kept: list[dict] = []
    with previous.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["week_end"] not in redone:
                kept.append({k: (None if v == "" else _restore(v)) for k, v in row.items()})
    merged = kept + fresh
    merged.sort(key=lambda r: (r["week_end"], str(r.get("scope", "")), str(r.get("s33", ""))))
    return merged


def _restore(value: str):
    """CSV から読み戻すときに、数に見えるものは数にする。"""
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def publish(portal_data: Path, files: dict[str, list[dict]], manifest: dict) -> None:
    """一時フォルダに書いてから入れ替える(§6.10)。"""
    final = portal_data / "market"
    tmp = portal_data / "market.tmp"
    prev = portal_data / "market.prev"

    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    for name, rows in files.items():
        write_csv(tmp / name, COLUMNS[name], rows)
    (tmp / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 確かめる: 週が減っていないか(§6.10 の 2)
    if final.exists():
        problem = check_weeks(_read_weeks(final / "weeks.csv"), _read_weeks(tmp / "weeks.csv"))
        if problem:
            shutil.rmtree(tmp)
            raise SystemExit(f"{problem}。入れ替えを中止します")

    if prev.exists():
        shutil.rmtree(prev)
    if final.exists():
        final.rename(prev)
    tmp.rename(final)
    if prev.exists():
        shutil.rmtree(prev)
    log.info("%s を入れ替えました", final)


# 古い側の週が、新しく増えた週の数よりこれだけ多く減ってもよい
HEAD_SLACK = 2


def check_weeks(before: list[dict], after: list[dict]) -> str | None:
    """前回の weeks.csv と比べて、週が失われていないかを確かめる。問題があれば理由を返す。

    取引カレンダーのキャッシュは契約の範囲(10年)で先頭が毎週ずれていくので、
    いちばん古い週が落ちるのは正常(2026-10-10 に 521 → 520 で止まった)。
    落ちてよいのは先頭だけで、数は末尾に増えた週と同じくらいまで。
    """
    if not before:
        return None
    if not after:
        return f"週がなくなりました({len(before)} → 0)"
    if after[-1]["week_end"] < before[-1]["week_end"]:
        return f"いちばん新しい週が戻りました({before[-1]['week_end']} → {after[-1]['week_end']})"
    first = after[0]["week_start"]
    starts = {w["week_start"] for w in after}
    missing = [w["week_start"] for w in before if w["week_start"] >= first and w["week_start"] not in starts]
    if missing:
        return f"途中の週が抜けました({', '.join(missing[:5])} など {len(missing)} 週)"
    dropped = sum(1 for w in before if w["week_start"] < first)
    added = sum(1 for w in after if w["week_end"] > before[-1]["week_end"])
    if dropped > added + HEAD_SLACK:
        return f"古い週が {dropped} 週減りました(増えたのは {added} 週。{before[0]['week_start']} → {first})"
    return None


def _read_weeks(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="市場概況の集計(詳細設計書 §6)")
    parser.add_argument("--rebuild", action="store_true", help="全期間を作り直す")
    parser.add_argument("--as-of", help="この日時点として集計する(YYYY-MM-DD。既定は今)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = config.load()
    now = datetime.combine(date.fromisoformat(args.as_of), datetime.max.time()) if args.as_of else datetime.now()

    manifest = run(cfg, now, rebuild=args.rebuild)
    log.info("完了: 最新の週 %s / 警告 %d 件", manifest["latest_week_end"], len(manifest["warnings"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
