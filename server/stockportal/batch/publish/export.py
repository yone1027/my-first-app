"""全 API の応答を JSON のファイルに書き出す(詳細設計書 §13.2)。

アプリをプロセスの中で呼ぶので、応答はローカルのポータルと同じになる。
クラウドの Pages Functions(``cloud/functions``)は、URL をここで決めたファイル名に対応させる。
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

from ... import config
from ...api.search import _load_master, _load_universe
from ...app import create_app
from ...calc import period as P
from ...readers.calendar import CUTOFF
from ..aggregate.jq import MasterIndex
from ..aggregate.sources.jquants import FetchError, fetch_pages, load_api_key

log = logging.getLogger(__name__)

# 取引カレンダーが無い先の週は、金曜を最終営業日とみなして足す(遅れの判定に使う)
FUTURE_WEEKS = 60


def market_files() -> dict[str, str]:
    """市場概況: ファイル名 → URL。``period``・``scope`` の全部の組み合わせ。"""
    out = {}
    for period in P.PERIODS:
        out[f"market/japan.{period}.json"] = f"/api/market/japan?period={period}"
        out[f"market/segments.{period}.json"] = f"/api/market/segments?period={period}"
        for scope in P.SCOPES:
            out[f"market/sectors.{period}.{scope}.json"] = f"/api/market/sectors?period={period}&scope={scope}"
    return out


def detail_shard(code: str) -> str:
    """根拠のファイルの分け方。コードの先頭2文字(1週あたり約90個、1つ約200KB)。

    クラウドではファイルを読んで1銘柄を取り出すので、1つのファイルを小さく保つ
    (無料プランの CPU 時間は1回 10ms まで)。ファイルの数は Pages の上限(2万)に収める。
    """
    return code[:2].upper() or "_"


class _Client:
    """アプリをプロセスの中で呼ぶ。接続元は 127.0.0.1(家の中からの接続として通す。§9.1)。"""

    def __init__(self, app):
        self.app = app
        self._loop = asyncio.new_event_loop()
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
        self._client = httpx.AsyncClient(transport=transport, base_url="http://localhost")

    def get(self, url: str) -> httpx.Response:
        return self._loop.run_until_complete(self._client.get(url))

    def close(self) -> None:
        self._loop.run_until_complete(self._client.aclose())
        self._loop.close()


class Exporter:
    def __init__(self, cfg: config.Config, out_dir: Path):
        self.cfg = cfg
        self.out = out_dir
        self.client = _Client(create_app(cfg))
        self.errors: dict[str, int] = {}
        self.count = 0

    def write(self, name: str, payload) -> None:
        path = self.out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        self.count += 1

    def get(self, name: str, url: str):
        """URL を呼んでファイルに書く。404 なども本文ごと書き、状態は errors.json に残す。"""
        response = self.client.get(url)
        body = response.json()
        if response.status_code != 200:
            self.errors[name] = response.status_code
        self.write(name, body)
        return body if response.status_code == 200 else None

    def run(self, now: datetime) -> dict:
        if self.out.exists():
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True)

        self.get("theme.json", "/api/theme")
        self.write("status_base.json", self.status_base(now))
        for name, url in market_files().items():
            self.get(name, url)
        self.get("weekly/evaluation.json", "/api/weekly/evaluation")
        dates = self.get("weekly/dates.json", "/api/weekly/dates") or {"dates": []}
        for entry in dates["dates"]:
            self.export_date(entry["date"])
        self.write("search.json", self.search_index(dates.get("latest")))
        self.write("errors.json", self.errors)
        self.client.close()
        log.info("書き出し: %d ファイル(エラーの応答 %d)→ %s", self.count, len(self.errors), self.out)
        return {"files": self.count, "errors": len(self.errors), "dates": len(dates["dates"])}

    def export_date(self, day: str) -> None:
        base = f"weekly/{day}"
        verdicts = self.get(f"{base}/verdicts.json", f"/api/weekly/{day}/verdicts")
        self.get(f"{base}/picks.json", f"/api/weekly/{day}/picks")
        self.get(f"{base}/candidates.json", f"/api/weekly/{day}/candidates")
        shards: dict[str, dict] = {}
        for row in (verdicts or {}).get("rows", []):
            code = str(row["code"])
            response = self.client.get(f"/api/weekly/{day}/verdicts/{code}")
            if response.status_code == 200:
                shards.setdefault(detail_shard(code), {})[code] = response.json()
        for shard, entries in shards.items():
            self.write(f"{base}/detail/{shard}.json", entries)

    def status_base(self, now: datetime) -> dict:
        """``/api/status`` のうち、時刻で変わらない部分と、遅れの判定に使う週の一覧(§13.5)。"""
        status = self.client.get("/api/status").json()
        return {
            "exported_at": now.astimezone().isoformat(timespec="seconds"),
            "delayed_after": status["delayed_after"],
            "schedule": {"weekday": self.cfg.schedule.weekday, "at": self.cfg.schedule.at.strftime("%H:%M")},
            "cutoff": CUTOFF.strftime("%H:%M"),
            "market": {k: status["market"][k] for k in ("data_week_end", "last_updated")},
            "weekly": {k: status["weekly"][k] for k in ("latest_date", "last_updated", "steps")},
            "week_ends": self.week_ends(now.date()),
        }

    def week_ends(self, today: date) -> list[str]:
        """週の最終営業日の一覧。キャッシュのカレンダーに、先の分を J-Quants から足す。"""
        svc = self.client.app.state.services
        days: set[date] = set()
        try:
            days |= set(svc.calendar.business_days())
        except Exception:  # キャッシュが無くても、先の分と金曜で補える
            pass
        try:
            key = load_api_key(self.cfg.paths.jquants_env)
            rows = fetch_pages(
                "/markets/calendar",
                {"from": (today - timedelta(days=21)).isoformat(), "to": (today + timedelta(days=400)).isoformat()},
                key,
                self.cfg.api.jquants_per_minute,
            )
            days |= {date.fromisoformat(r["Date"]) for r in rows if str(r.get("HolDiv")) in ("1", "2")}
        except (FetchError, OSError, KeyError) as exc:
            log.warning("先の取引カレンダーを取れませんでした。金曜を最終営業日とみなします: %s", exc)
        ends: dict[date, date] = {}
        for day in days:
            monday = day - timedelta(days=day.weekday())
            ends[monday] = max(ends.get(monday, day), day)
        last = max(ends) if ends else today - timedelta(days=today.weekday())
        for i in range(1, FUTURE_WEEKS + 1):
            monday = last + timedelta(weeks=i)
            ends.setdefault(monday, monday + timedelta(days=4))
        start = today - timedelta(weeks=60)
        return [ends[m].isoformat() for m in sorted(ends) if m >= start]

    def search_index(self, latest: str | None) -> dict:
        """検索の材料。``api/search.py`` と同じ銘柄一覧と、最新の基準日の対象銘柄(§13.2)。"""
        raw = self.cfg.paths.jquants_raw / "equities__master"
        master = MasterIndex(raw)
        rows = []
        if master.snapshot_days:
            rows = _load_master(raw / f"date={master.snapshot_days[-1].isoformat()}.json.gz")
        universe: list[str] = []
        if latest:
            path = self.client.app.state.services.screen.dir_for(latest) / "universe.csv"
            if path.exists():
                universe = sorted(_load_universe(path))
        return {"rows": rows, "universe": universe}
