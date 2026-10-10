"""来週の買い注文の候補の成績(詳細設計書 §6.11)。

``python -m stockportal.batch.evaluate [--as-of YYYY-MM-DD]``

過去のすべての ``picks_<基準日>.md`` の候補について、指値で買えたか・目標と損切りの
どちらに届いたかを、J-Quants の日足のキャッシュ(読むだけ)で判定し、
``portal_data/evaluation/picks.json`` に書く。決済済みのものも毎回計算し直す。
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from ... import config
from ...readers.picks import PicksReader
from ..aggregate.jq import by_date, rows_of, short_code, to_float
from .rules import Bar, Outcome, simulate

log = logging.getLogger("stockportal.evaluate")

PICKS_FILE = re.compile(r"^picks_(\d{4})(\d{2})(\d{2})\.md$")


def pick_dates(selection_dir: Path, as_of: date) -> list[str]:
    """``picks_YYYYMMDD.md`` の基準日のうち、``as_of`` 以前のもの(古い順)。"""
    found = []
    for child in selection_dir.glob("picks_*.md"):
        m = PICKS_FILE.match(child.name)
        if m:
            day = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            if date.fromisoformat(day) <= as_of:
                found.append(day)
    return sorted(found)


class DailyBars:
    """日付ごとの全銘柄の日足のファイルを、必要な日だけ読む。"""

    def __init__(self, jquants_raw: Path):
        self.files = by_date(jquants_raw / "equities__bars__daily")
        self._loaded: dict[date, dict[str, Bar]] = {}

    def _day(self, day: date) -> dict[str, Bar]:
        if day not in self._loaded:
            bars: dict[str, Bar] = {}
            for row in rows_of(self.files[day]):
                o, h, l, c = (to_float(row.get(k)) for k in ("O", "H", "L", "C"))
                if None in (o, h, l, c):
                    continue  # 値が付かなかった(売買停止など)
                adj = to_float(row.get("AdjFactor"))
                bars[short_code(str(row.get("Code")))] = Bar(day, o, h, l, c, 1.0 if adj is None else adj)
            self._loaded[day] = bars
        return self._loaded[day]

    def series(self, code: str, start: date, end: date) -> list[Bar]:
        out = []
        for day in sorted(d for d in self.files if start <= d <= end):
            bar = self._day(day).get(code)
            if bar:
                out.append(bar)
        return out


def evaluate(cfg: config.Config, as_of: date) -> dict:
    reader = PicksReader(cfg.paths.selection_dir)
    bars = DailyBars(cfg.paths.jquants_raw)
    rows = []
    for day in pick_dates(cfg.paths.selection_dir, as_of):
        data = reader.read(day)
        validity = data["header"].get("validity") or {}
        for pick in data["picks"]:
            rows.append(_evaluate_pick(day, validity, pick, bars, as_of))
    rows.sort(key=lambda r: (r["date"], r["rank"] is None, r["rank"] or 0), reverse=False)
    log.info("候補 %d 件を評価しました", len(rows))
    return {
        "as_of": as_of.isoformat(),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "rows": rows,
    }


def _evaluate_pick(day: str, validity: dict, pick: dict, bars: DailyBars, as_of: date) -> dict:
    # 値段は md の(実際に注文する)値段。無ければ CSV の値で代える
    entry = pick.get("entry_md") or pick.get("entry")
    stop = pick.get("stop_md") or pick.get("stop")
    target = pick.get("target_md") or pick.get("target")
    base = {
        "date": day,
        "code": pick["code"],
        "name": pick.get("name"),
        "sector_name": pick.get("sector_name"),
        "rank": pick.get("rank"),
        "entry": entry,
        "stop": stop,
        "target": target,
        "order_start": validity.get("start"),
        "order_end": validity.get("end"),
        "p_fill": pick.get("p_fill"),
        "p_target": pick.get("p_target"),
        "p_stop": pick.get("p_stop"),
    }
    if not (entry and stop and target and validity.get("start") and validity.get("end")):
        outcome = Outcome("unknown", note="注文の値段か有効期間が md から読めません")
    else:
        start = date.fromisoformat(validity["start"])
        end = date.fromisoformat(validity["end"])
        try:
            series = bars.series(pick["code"], start, as_of)
            outcome = simulate(series, entry, stop, target, start, end, as_of)
        except (OSError, ValueError) as exc:
            log.warning("%s %s: 日足を読めません: %s", day, pick["code"], exc)
            outcome = Outcome("unknown", note="日足を読めません")
    found = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in asdict(outcome).items() if k != "extra"}
    return {**base, **found}


def publish(portal_data: Path, payload: dict) -> Path:
    """一時ファイルに書いてから名前を変える(画面に書きかけを見せない)。"""
    folder = portal_data / "evaluation"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "picks.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="来週の買い注文の候補の成績(詳細設計書 §6.11)")
    parser.add_argument("--as-of", help="この日までの日足で判定する(YYYY-MM-DD。既定は今日)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = config.load()
    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()

    payload = evaluate(cfg, as_of)
    path = publish(cfg.paths.portal_data, payload)
    counts: dict[str, int] = {}
    for row in payload["rows"]:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    log.info("%s を書きました: %s", path, counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
