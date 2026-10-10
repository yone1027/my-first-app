"""来週の買い注文の候補の成績を読む(詳細設計書 §6.11・§5.4)。

``portal_data/evaluation/picks.json`` は週次のバッチの手順4 が書く。
集計は件数を数えるだけにして、点数や順位は作らない(R1・R2・R5)。
"""

from __future__ import annotations

import json
from pathlib import Path

from .cache import FileCache, FileNotFound

SETTLED = ("win", "lose")
REASONS = ("target", "stop", "time")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def summarize(rows: list[dict]) -> dict:
    """件数・約定率・勝ち負けの内訳・平均リターン、予測と実際。"""
    count = {s: 0 for s in ("ordering", "unfilled", "holding", "win", "lose", "unknown")}
    reasons = {s: {r: 0 for r in REASONS} for s in SETTLED}
    for row in rows:
        count[row["status"]] = count.get(row["status"], 0) + 1
        if row["status"] in SETTLED and row.get("reason") in REASONS:
            reasons[row["status"]][row["reason"]] += 1

    # 約定したかどうかが決まったもの(注文中と評価できないものを除く)
    decided = [r for r in rows if r["status"] in ("unfilled", "holding", *SETTLED)]
    filled = [r for r in decided if r["status"] != "unfilled"]
    settled = [r for r in rows if r["status"] in SETTLED]
    return {
        "total": len(rows),
        "count": count,
        "reasons": reasons,
        "decided": len(decided),
        "filled": len(filled),
        "fill_rate": len(filled) / len(decided) if decided else None,
        "settled": len(settled),
        "mean_ret": _mean([r["ret"] for r in settled if r.get("ret") is not None]),
        # 予測と実際(同じ母集団で並べる)
        "predicted_fill": _mean([r["p_fill"] for r in decided if r.get("p_fill") is not None]),
        "predicted_target": _mean([r["p_target"] for r in settled if r.get("p_target") is not None]),
        "predicted_stop": _mean([r["p_stop"] for r in settled if r.get("p_stop") is not None]),
        "actual_target": sum(1 for r in settled if r.get("reason") == "target") / len(settled) if settled else None,
        "actual_stop": sum(1 for r in settled if r.get("reason") == "stop") / len(settled) if settled else None,
    }


class EvaluationReader:
    def __init__(self, portal_data: Path):
        self.path = portal_data / "evaluation" / "picks.json"
        self._cache = FileCache()

    def read(self) -> dict | None:
        """まだ一度もバッチが動いていなければ None。"""
        try:
            return self._cache.get(self.path, _load)
        except FileNotFound:
            return None

    def outcome(self, date: str, code: str) -> dict | None:
        data = self.read()
        if not data:
            return None
        return next((r for r in data["rows"] if r["date"] == date and r["code"] == code), None)
