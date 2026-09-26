"""設定の読み込み(§3.3)。"""

from __future__ import annotations

import pytest

from stockportal import config


def test_example_config_is_valid():
    cfg = config.load(config.EXAMPLE_CONFIG)
    assert cfg.server.port == 8765
    assert "stockportal.local" in cfg.server.allowed_hosts
    assert cfg.aggregate.exclude_markets == ("0105", "0109")
    assert cfg.aggregate.recompute_weeks == 4


def test_theme_has_every_colour_the_screen_needs():
    """基本設計書 §4.8 の色が、設定に全部あること。"""
    theme = config.load(config.EXAMPLE_CONFIG).theme
    for key in (
        "bg", "surface", "text", "text_sub", "text_muted", "border", "font_family",
        "buy_bg", "buy_fg", "sell_bg", "sell_fg", "neutral_bg", "neutral_fg",
        "unknown_bg", "unknown_fg", "conflict_bg", "conflict_fg",
        "prime", "standard", "growth",
    ):
        assert key in theme, key
    assert len(theme["investors"]) == 6  # 主体は6つ


def test_delayed_after_is_parsed():
    cfg = config.load(config.EXAMPLE_CONFIG)
    assert cfg.schedule.weekday == 5  # 土曜
    assert (cfg.schedule.at.hour, cfg.schedule.at.minute) == (12, 0)


def test_bad_delayed_after_is_rejected(tmp_path):
    path = tmp_path / "c.toml"
    path.write_text(
        '[server]\n[paths]\nscreen_dir="/a"\ncandidates_dir="/a"\nselection_dir="/a"\n'
        'jquants_raw="/a"\nportal_data="/a"\n[schedule]\ndelayed_after="いつか"\n',
        encoding="utf-8",
    )
    with pytest.raises(config.ConfigError):
        config.load(path)


def test_missing_path_is_reported(tmp_path):
    path = tmp_path / "c.toml"
    path.write_text('[server]\n[paths]\nscreen_dir="/a"\n', encoding="utf-8")
    with pytest.raises(config.ConfigError, match="candidates_dir"):
        config.load(path)
