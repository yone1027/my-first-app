"""設定ファイルの読み込み(詳細設計書 §3.3)。

パスや閾値をコードに直接書かない(要件 §6.1)。設定の場所は環境変数
``STOCKPORTAL_CONFIG`` で渡す。無ければリポジトリの見本を使う(開発用)。
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_CONFIG = REPO_ROOT / "config" / "config.example.toml"

# 曜日名 → Python の weekday()(月=0)
_WEEKDAYS = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}


class ConfigError(Exception):
    """設定ファイルが読めない、または項目が足りない。"""


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int
    allowed_hosts: tuple[str, ...]


@dataclass(frozen=True)
class PathsConfig:
    screen_dir: Path
    candidates_dir: Path
    selection_dir: Path
    jquants_raw: Path
    jquants_env: Path
    portal_data: Path
    logs: Path

    @property
    def market_dir(self) -> Path:
        """市場概況の集計の結果(§6.9)。"""
        return self.portal_data / "market"

    @property
    def raw_dir(self) -> Path:
        """集計が新しく取るデータのキャッシュ(§3.2)。"""
        return self.portal_data / "raw"

    @property
    def status_dir(self) -> Path:
        """週次の後続の処理の実行状況(§4.6)。"""
        return self.portal_data / "status"


@dataclass(frozen=True)
class BatchConfig:
    python_existing: str
    wait_screen_max_minutes: int
    wait_screen_poll_seconds: int
    step_timeout_minutes: dict[str, int]


@dataclass(frozen=True)
class AggregateConfig:
    exclude_markets: tuple[str, ...]
    recompute_weeks: int


@dataclass(frozen=True)
class ScheduleConfig:
    """``delayed_after`` は "SAT 12:00" の形(§5.7)。"""

    weekday: int
    at: time
    raw: str


@dataclass(frozen=True)
class ApiConfig:
    jquants_per_minute: int
    jquants_fins_per_minute: int


@dataclass(frozen=True)
class Config:
    server: ServerConfig
    paths: PathsConfig
    batch: BatchConfig
    aggregate: AggregateConfig
    theme: dict[str, object]
    schedule: ScheduleConfig
    api: ApiConfig
    source: Path = field(compare=False, default=EXAMPLE_CONFIG)


def config_path() -> Path:
    env = os.environ.get("STOCKPORTAL_CONFIG")
    return Path(env).expanduser() if env else EXAMPLE_CONFIG


def _require(table: dict, key: str, where: str):
    if key not in table:
        raise ConfigError(f"{where} に {key} がありません")
    return table[key]


def _parse_delayed_after(value: str) -> ScheduleConfig:
    parts = value.split()
    if len(parts) != 2 or parts[0].upper() not in _WEEKDAYS:
        raise ConfigError(f'[schedule] delayed_after は "SAT 12:00" の形にしてください(受け取った値: {value!r})')
    hhmm = parts[1].split(":")
    if len(hhmm) != 2 or not all(p.isdigit() for p in hhmm):
        raise ConfigError(f'[schedule] delayed_after の時刻が読めません: {value!r}')
    return ScheduleConfig(weekday=_WEEKDAYS[parts[0].upper()], at=time(int(hhmm[0]), int(hhmm[1])), raw=value)


def load(path: Path | None = None) -> Config:
    """設定を読む。項目が足りなければ ConfigError を投げる。"""
    path = path or config_path()
    if not path.exists():
        raise ConfigError(f"設定ファイルがありません: {path}")
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"設定ファイルの書式が読めません({path}): {exc}") from exc

    server = _require(data, "server", str(path))
    paths = _require(data, "paths", str(path))
    batch = data.get("batch", {})
    aggregate = data.get("aggregate", {})
    api = data.get("api", {})

    return Config(
        server=ServerConfig(
            host=str(server.get("host", "0.0.0.0")),
            port=int(server.get("port", 8765)),
            allowed_hosts=tuple(server.get("allowed_hosts", ["localhost", "127.0.0.1"])),
        ),
        paths=PathsConfig(
            screen_dir=Path(_require(paths, "screen_dir", "[paths]")).expanduser(),
            candidates_dir=Path(_require(paths, "candidates_dir", "[paths]")).expanduser(),
            selection_dir=Path(_require(paths, "selection_dir", "[paths]")).expanduser(),
            jquants_raw=Path(_require(paths, "jquants_raw", "[paths]")).expanduser(),
            jquants_env=Path(paths.get("jquants_env", "")).expanduser(),
            portal_data=Path(_require(paths, "portal_data", "[paths]")).expanduser(),
            logs=Path(paths.get("logs", "")).expanduser(),
        ),
        batch=BatchConfig(
            python_existing=str(batch.get("python_existing", "python3")),
            wait_screen_max_minutes=int(batch.get("wait_screen_max_minutes", 180)),
            wait_screen_poll_seconds=int(batch.get("wait_screen_poll_seconds", 60)),
            step_timeout_minutes=dict(batch.get("step_timeout_minutes", {})),
        ),
        aggregate=AggregateConfig(
            exclude_markets=tuple(aggregate.get("exclude_markets", ("0105", "0109"))),
            recompute_weeks=int(aggregate.get("recompute_weeks", 4)),
        ),
        theme=dict(data.get("theme", {})),
        schedule=_parse_delayed_after(str(data.get("schedule", {}).get("delayed_after", "SAT 12:00"))),
        api=ApiConfig(
            jquants_per_minute=int(api.get("jquants_per_minute", 100)),
            jquants_fins_per_minute=int(api.get("jquants_fins_per_minute", 60)),
        ),
        source=path,
    )
