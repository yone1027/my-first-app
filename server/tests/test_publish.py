"""クラウド版への書き出しと送り出し(詳細設計書 §13)。"""

from __future__ import annotations

import dataclasses
import json
import tomllib

from stockportal.batch.publish import deploy
from stockportal.batch.publish.export import Exporter, detail_shard, market_files
from stockportal.calc import period as P


def test_market_files_cover_every_period_and_scope():
    files = market_files()
    assert len(files) == len(P.PERIODS) * (2 + len(P.SCOPES))
    assert files["market/sectors.26w.growth.json"] == "/api/market/sectors?period=26w&scope=growth"
    assert files["market/japan.13w.json"] == "/api/market/japan?period=13w"


def test_detail_files_are_split_by_the_first_two_characters():
    """cloud/lib/portal.js の detailShard と同じ分け方。"""
    assert detail_shard("7203") == "72"
    assert detail_shard("285a") == "28"
    assert detail_shard("") == "_"


def test_wrangler_toml_carries_the_access_settings(cfg):
    cloud = dataclasses.replace(cfg.cloud, project="stockportal", access_team="yone", access_aud='a"b')
    parsed = tomllib.loads(deploy.wrangler_toml(dataclasses.replace(cfg, cloud=cloud)))
    assert parsed["name"] == "stockportal"
    assert parsed["pages_build_output_dir"] == "site"
    assert parsed["vars"] == {"ACCESS_TEAM": "yone", "ACCESS_AUD": 'a"b'}


def test_env_file_is_read_without_quotes_or_comments(tmp_path):
    env = tmp_path / ".env"
    env.write_text('# トークン\nCLOUDFLARE_API_TOKEN="abc"\nCLOUDFLARE_ACCOUNT_ID=123\n\nbroken line\n', encoding="utf-8")
    assert deploy.read_env(env) == {"CLOUDFLARE_API_TOKEN": "abc", "CLOUDFLARE_ACCOUNT_ID": "123"}
    assert deploy.read_env(tmp_path / "none") == {}


def test_deploy_refuses_without_the_token(cfg, tmp_path):
    cloud = dataclasses.replace(cfg.cloud, enabled=True, env_file=tmp_path / "missing.env")
    try:
        deploy.deploy(dataclasses.replace(cfg, cloud=cloud), tmp_path)
    except deploy.DeployError as exc:
        assert "CLOUDFLARE_API_TOKEN" in str(exc)
    else:
        raise AssertionError("トークンが無ければ送り出さない")


def test_export_matches_the_api(cfg, needs_real_data, tmp_path):
    """書き出したファイルは、同じ URL の API の応答と同じ。"""
    out = tmp_path / "_data"
    exporter = Exporter(cfg, out)
    summary = exporter.run(__import__("datetime").datetime(2026, 10, 19, 12, 0))
    assert summary["files"] > 10

    from fastapi.testclient import TestClient  # noqa: PLC0415  確かめにだけ使う
    from stockportal.app import create_app

    client = TestClient(create_app(cfg), base_url="http://localhost", client=("127.0.0.1", 1))
    dates = json.loads((out / "weekly" / "dates.json").read_text(encoding="utf-8"))
    latest = dates["latest"]
    for name, url in [
        ("market/japan.26w.json", "/api/market/japan?period=26w"),
        (f"weekly/{latest}/verdicts.json", f"/api/weekly/{latest}/verdicts"),
        ("weekly/evaluation.json", "/api/weekly/evaluation"),
    ]:
        assert json.loads((out / name).read_text(encoding="utf-8")) == client.get(url).json(), name

    rows = json.loads((out / "weekly" / latest / "verdicts.json").read_text(encoding="utf-8"))["rows"]
    code = rows[0]["code"]
    shard = json.loads((out / "weekly" / latest / "detail" / f"{detail_shard(code)}.json").read_text(encoding="utf-8"))
    assert shard[code] == client.get(f"/api/weekly/{latest}/verdicts/{code}").json()

    base = json.loads((out / "status_base.json").read_text(encoding="utf-8"))
    assert base["week_ends"] == sorted(base["week_ends"])
    assert set(base) >= {"delayed_after", "schedule", "market", "weekly", "week_ends"}
