"""週次の後続の処理(§4)。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from stockportal.batch import weekly


def test_as_of_is_the_last_settled_week_before_today(cfg, needs_real_data):
    """土曜 3:00 に動かせば、通常はその週の金曜(§4.2)。"""
    assert weekly.decide_as_of(cfg, datetime(2026, 9, 26, 3, 0)) == "2026-09-25"
    # 金曜の 20:00 は、その日を含めないので前の週
    assert weekly.decide_as_of(cfg, datetime(2026, 9, 25, 20, 0)) == "2026-09-18"


def test_step_commands_use_the_right_python_and_folder(cfg):
    """既存のスクリプトは anaconda、集計はポータルの仮想環境(§4.4)。"""
    candidates, cwd = weekly.step_command(cfg, "2026-09-25", "candidates")
    assert candidates[0] == cfg.batch.python_existing
    assert candidates[1:] == ["scripts/candidates.py", "--as-of", "2026-09-25"]
    assert cwd.name == "TechnicalAnalysis"

    picks, cwd = weekly.step_command(cfg, "2026-09-25", "weekly_picks")
    assert picks[0] == cfg.batch.python_existing
    assert cwd.name == "J-Quants"

    aggregate, cwd = weekly.step_command(cfg, "2026-09-25", "aggregate")
    assert aggregate[1:] == ["-m", "stockportal.batch.aggregate", "--as-of", "2026-09-25"]
    assert aggregate[0] != cfg.batch.python_existing  # ポータル側の Python


def test_step_timeouts_come_from_the_config(cfg):
    assert cfg.batch.step_timeout_minutes == {"candidates": 120, "weekly_picks": 180, "aggregate": 60}


def test_lock_prevents_a_second_run(cfg):
    weekly.release_lock(cfg)
    assert weekly.take_lock(cfg) is True
    try:
        assert weekly.take_lock(cfg) is False  # 2つめは入れない
    finally:
        weekly.release_lock(cfg)
    assert weekly.take_lock(cfg) is True  # 消したら入れる
    weekly.release_lock(cfg)


def test_status_is_written_atomically_and_readable(cfg):
    record = weekly.RunRecord(as_of="1999-12-31", started_at="1999-12-31T00:00:00+09:00")
    record.step("candidates").status = "ok"
    weekly.write_status(cfg, record)
    path = cfg.paths.status_dir / "weekly_19991231.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["as_of"] == "1999-12-31"
        assert payload["steps"][0] == {
            "name": "candidates", "status": "ok", "started_at": None,
            "finished_at": None, "exit_code": None, "log": None,
        }
        assert not path.with_suffix(".json.tmp").exists()  # 一時ファイルは残らない
    finally:
        path.unlink(missing_ok=True)


def test_steps_one_and_two_are_skipped_when_the_screen_is_not_ready(cfg, tmp_path, monkeypatch):
    """一括分析がそろわなければ手順1・2 は skipped、手順3 だけ動かす(§4.1)。

    本物の集計を走らせると開発用の出力を上書きしてしまうので、出力先を
    一時フォルダに向け、手順の実行そのものは差し替えて確かめる。
    """
    import dataclasses

    sandbox = dataclasses.replace(cfg, paths=dataclasses.replace(cfg.paths, portal_data=tmp_path, logs=tmp_path / "logs"))
    object.__setattr__(sandbox.batch, "wait_screen_max_minutes", 0)

    ran: list[str] = []

    def fake_step(_cfg, _as_of, name, record):
        ran.append(name)
        step = record.step(name)
        step.status = "ok"
        return "ok"

    monkeypatch.setattr(weekly, "run_step", fake_step)
    record = weekly.run(sandbox, "2011-01-07", only=None, wait=True)

    statuses = {s.name: s.status for s in record.steps}
    assert statuses["candidates"] == "skipped"
    assert statuses["weekly_picks"] == "skipped"
    assert statuses["aggregate"] == "ok"
    assert ran == ["aggregate"], "飛ばした手順は動かさない"
    assert record.screen_ready_at is None


def test_success_needs_the_output_file_not_just_exit_zero(cfg):
    """終了コード 0 だけでは成功としない(§4.4)。"""
    assert weekly.step_succeeded(cfg, "1999-12-31", "candidates") is False
    assert weekly.step_succeeded(cfg, "1999-12-31", "weekly_picks") is False


def test_status_api_reads_the_steps_written_by_this_batch(cfg, client):
    """§4.6 で書く形を、§5.7 の API がそのまま読めること(取り違えの防止)。"""
    record = weekly.RunRecord(as_of="1999-12-31", started_at="1999-12-31T00:00:00+09:00")
    record.step("candidates").status = "ok"
    record.step("weekly_picks").status = "failed"
    weekly.write_status(cfg, record)
    path = cfg.paths.status_dir / "weekly_19991231.json"
    try:
        from stockportal.api.status import _read_steps

        assert _read_steps(cfg.paths.status_dir, "1999-12-31") == {"candidates": "ok", "weekly_picks": "failed"}
    finally:
        path.unlink(missing_ok=True)
