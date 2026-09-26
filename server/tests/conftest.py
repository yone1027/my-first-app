"""テストの下ごしらえ(詳細設計書 §11)。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "server"))

from stockportal import config  # noqa: E402


@pytest.fixture(scope="session")
def dev_config_path() -> Path:
    """開発用の設定(集計の出力先だけをリポジトリの中に向けたもの)。"""
    path = REPO / ".dev" / "config.toml"
    if not path.exists():
        pytest.skip(".dev/config.toml がありません(README の手順で作ります)")
    return path


@pytest.fixture(scope="session")
def cfg(dev_config_path: Path) -> config.Config:
    return config.load(dev_config_path)


@pytest.fixture(scope="session")
def client(cfg: config.Config):
    from starlette.testclient import TestClient

    from stockportal.app import create_app

    # 家の中からの接続に見えるように、クライアントの IP を渡す(§9.1)
    return TestClient(create_app(cfg), base_url="http://localhost:8765", client=("127.0.0.1", 40000))


def has_real_data(cfg: config.Config) -> bool:
    return cfg.paths.screen_dir.is_dir() and bool(list(cfg.paths.screen_dir.glob("2*")))


@pytest.fixture(scope="session")
def needs_real_data(cfg: config.Config) -> None:
    if not has_real_data(cfg):
        pytest.skip("既存のプロジェクトの出力が無い環境なので飛ばします")
