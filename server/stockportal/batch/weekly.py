"""週次の後続の処理(詳細設計書 §4)。

土曜 3:00 に launchd から `caffeinate -i -m -s` で包んで起動する(§10.1)。
一括分析の完了を待ってから、既存のスクリプト2本とポータルの集計を続けて動かす。
既存のコードには手を入れず、コマンドとして呼ぶだけにする(D1)。
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time as clock, timedelta
from pathlib import Path

from .. import config
from .aggregate import weeks as weeks_mod

log = logging.getLogger("stockportal.weekly")

CUTOFF = clock(17, 0)
STEPS = ("candidates", "weekly_picks", "aggregate")


@dataclass
class StepRecord:
    name: str
    status: str = "running"
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    log: str | None = None


@dataclass
class RunRecord:
    as_of: str
    started_at: str
    finished_at: str | None = None
    screen_ready_at: str | None = None
    steps: list[StepRecord] = field(default_factory=list)

    def step(self, name: str) -> StepRecord:
        for record in self.steps:
            if record.name == name:
                return record
        record = StepRecord(name=name)
        self.steps.append(record)
        return record


def now_text() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def decide_as_of(cfg: config.Config, now: datetime) -> str:
    """今日を含めず、最終営業日の 17:00 を過ぎた、いちばん新しい週の最終営業日(§4.2)。"""
    settled = weeks_mod.build(cfg.paths.jquants_raw, now)
    today = now.date()
    for week in reversed(settled):
        end = date.fromisoformat(week["week_end"])
        if end < today:
            return week["week_end"]
    if settled:
        return settled[-1]["week_end"]
    raise SystemExit("取引カレンダーのキャッシュが読めないため、基準日を決められません")


def write_status(cfg: config.Config, record: RunRecord) -> None:
    """一時ファイルに書いてから名前を変える(§4.6・§6.10)。"""
    folder = cfg.paths.status_dir
    folder.mkdir(parents=True, exist_ok=True)
    final = folder / f"weekly_{record.as_of.replace('-', '')}.json"
    tmp = final.with_suffix(".json.tmp")
    payload = asdict(record)
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(final)


def wait_for_screen(cfg: config.Config, as_of: str, record: RunRecord) -> bool:
    """`verdicts.csv` と `report.md` の両方がそろうまで待つ(§4.3)。"""
    folder = cfg.paths.screen_dir / as_of.replace("-", "")
    deadline = time.monotonic() + cfg.batch.wait_screen_max_minutes * 60
    poll = max(cfg.batch.wait_screen_poll_seconds, 5)
    while True:
        if (folder / "verdicts.csv").exists() and (folder / "report.md").exists():
            record.screen_ready_at = now_text()
            log.info("一括分析がそろいました: %s", folder)
            return True
        if time.monotonic() >= deadline:
            log.warning("一括分析を %d 分待ちましたがそろいませんでした", cfg.batch.wait_screen_max_minutes)
            return False
        time.sleep(poll)


def log_path(cfg: config.Config, as_of: str, name: str) -> Path:
    folder = cfg.paths.logs / "weekly"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{as_of.replace('-', '')}_{name}.log"


def run_step(cfg: config.Config, as_of: str, name: str, record: RunRecord) -> str:
    """1つの手順を動かして status を返す(§4.4)。"""
    step = record.step(name)
    step.status = "running"
    step.started_at = now_text()
    destination = log_path(cfg, as_of, name)
    step.log = str(destination)
    write_status(cfg, record)

    command, cwd = step_command(cfg, as_of, name)
    limit = cfg.batch.step_timeout_minutes.get(name, 120) * 60
    log.info("手順 %s を始めます: %s(作業フォルダ %s)", name, " ".join(command), cwd)

    with destination.open("w", encoding="utf-8") as fh:
        fh.write(f"開始 {step.started_at}\nコマンド: {' '.join(command)}\n作業フォルダ: {cwd}\n\n")
        fh.flush()
        try:
            completed = subprocess.run(command, cwd=cwd, stdout=fh, stderr=subprocess.STDOUT, timeout=limit, check=False)
            step.exit_code = completed.returncode
            step.status = "ok" if completed.returncode == 0 and step_succeeded(cfg, as_of, name) else "failed"
        except subprocess.TimeoutExpired:
            step.status = "timeout"
            fh.write(f"\n{limit // 60} 分を超えたため止めました\n")
        except OSError as exc:
            step.status = "failed"
            fh.write(f"\n起動できませんでした: {exc}\n")
        step.finished_at = now_text()
        fh.write(f"\n終了 {step.finished_at} 状態 {step.status} 終了コード {step.exit_code}\n")

    log.info("手順 %s: %s", name, step.status)
    write_status(cfg, record)
    return step.status


def step_command(cfg: config.Config, as_of: str, name: str) -> tuple[list[str], Path]:
    """手順ごとのコマンドと作業フォルダ(§4.4 の表)。"""
    if name == "candidates":
        root = cfg.paths.candidates_dir.parents[1]  # …/TechnicalAnalysis
        return ([cfg.batch.python_existing, "scripts/candidates.py", "--as-of", as_of], root)
    if name == "weekly_picks":
        root = cfg.paths.selection_dir.parents[1]  # …/J-Quants
        return ([cfg.batch.python_existing, "scripts/weekly_picks.py", "--as-of", as_of], root)
    if name == "aggregate":
        # ポータルの仮想環境の Python(自分と同じもの)で動かす
        return ([sys.executable, "-m", "stockportal.batch.aggregate", "--as-of", as_of], Path(__file__).resolve().parents[2])
    raise ValueError(name)


def step_succeeded(cfg: config.Config, as_of: str, name: str) -> bool:
    """終了コード 0 に加えて、出力ができているかも確かめる(§4.4)。"""
    compact = as_of.replace("-", "")
    if name == "candidates":
        return (cfg.paths.candidates_dir / compact / "candidates.csv").exists()
    if name == "weekly_picks":
        return (cfg.paths.selection_dir / f"picks_{compact}.md").exists()
    if name == "aggregate":
        path = cfg.paths.market_dir / "manifest.json"
        if not path.exists():
            return False
        try:
            return json.loads(path.read_text(encoding="utf-8")).get("latest_week_end") == as_of
        except (OSError, json.JSONDecodeError):
            return False
    return True


def lock_path(cfg: config.Config) -> Path:
    return cfg.paths.status_dir / "weekly.lock"


def take_lock(cfg: config.Config) -> bool:
    """二重起動を防ぐ(§4.1)。"""
    path = lock_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        log.warning("すでに動いています(%s があります)。何もせず終わります", path)
        return False
    with os.fdopen(fd, "w") as fh:
        fh.write(f"{os.getpid()} {now_text()}\n")
    return True


def release_lock(cfg: config.Config) -> None:
    lock_path(cfg).unlink(missing_ok=True)


def run(cfg: config.Config, as_of: str, only: str | None, wait: bool) -> RunRecord:
    record = RunRecord(as_of=as_of, started_at=now_text())
    targets = [only] if only else list(STEPS)

    # 一括分析を待つ。そろわなければ手順1・2 は skipped、手順3 だけ動かす(§4.1)
    ready = True
    if wait and not only:
        ready = wait_for_screen(cfg, as_of, record)
    write_status(cfg, record)

    for name in targets:
        if not ready and name in ("candidates", "weekly_picks"):
            step = record.step(name)
            step.status = "skipped"
            step.started_at = step.finished_at = now_text()
            log.warning("一括分析がそろわないため、手順 %s を飛ばします", name)
            write_status(cfg, record)
            continue
        # 前の手順が失敗しても、次の手順は動かす(要件 §6.1)
        run_step(cfg, as_of, name, record)

    record.finished_at = now_text()
    write_status(cfg, record)
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="週次の後続の処理(詳細設計書 §4)")
    parser.add_argument("--as-of", help="基準日(YYYY-MM-DD)。既定は取引カレンダーから決める")
    parser.add_argument("--only", choices=STEPS, help="この手順だけ動かす(やり直し用)")
    parser.add_argument("--no-wait", action="store_true", help="一括分析の完了を待たない")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = config.load()
    as_of = args.as_of or decide_as_of(cfg, datetime.now())
    log.info("基準日 %s", as_of)

    if not take_lock(cfg):
        return 0
    try:
        record = run(cfg, as_of, args.only, wait=not args.no_wait)
    finally:
        release_lock(cfg)

    statuses = {s.name: s.status for s in record.steps}
    log.info("完了: %s", statuses)
    # 1つでも失敗・時間切れがあれば 1 を返す(launchd のログで分かるように)
    return 1 if any(v in ("failed", "timeout") for v in statuses.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
