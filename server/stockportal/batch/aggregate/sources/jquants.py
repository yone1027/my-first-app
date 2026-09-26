"""J-Quants の API から取る(詳細設計書 §6.7)。

既存のキャッシュは読むだけだが、投資部門別情報だけはポータルが自分で取る
(既存のプロジェクトが取っていないため)。API キーは既存の ``.env`` を読み、
新しく置かない(§6.1)。
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

BASE_URL = "https://api.jquants.com/v2"
KEY_NAME = "JQUANTS_API_KEY"


class FetchError(Exception):
    """取れなかった。前回のキャッシュで続ける(§6.8)。"""


def load_api_key(env_file: Path) -> str:
    """既存の ``J-Quants/.env`` から読む。キーはログに書かない。"""
    if not env_file.exists():
        raise FetchError(f"{env_file} がありません")
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(f"{KEY_NAME}="):
            value = line.split("=", 1)[1].strip().strip("\"'")
            if value:
                return value
    raise FetchError(f"{env_file} に {KEY_NAME} がありません")


def fetch_pages(
    endpoint: str,
    params: dict,
    api_key: str,
    per_minute: int,
    max_pages: int = 100,
) -> list[dict]:
    """``pagination_key`` をたどって全ページ取る(§6.1 の流量の約束)。

    検索条件は変えずに ``pagination_key`` だけを足す(J-Quants の約束)。
    """
    interval = 60.0 / max(per_minute, 1)
    rows: list[dict] = []
    page: str | None = None
    with httpx.Client(base_url=BASE_URL, headers={"x-api-key": api_key}, timeout=60.0) as client:
        for attempt in range(max_pages):
            query = dict(params)
            if page:
                query["pagination_key"] = page
            response = client.get(endpoint, params=query)
            if response.status_code == 429:
                log.warning("%s: 流量の上限に当たりました。60秒待ちます", endpoint)
                time.sleep(60)
                continue
            if response.status_code != 200:
                raise FetchError(f"{endpoint}: HTTP {response.status_code} {response.text[:200]}")
            payload = response.json()
            rows.extend(payload.get("data") or [])
            page = payload.get("pagination_key")
            if not page:
                return rows
            time.sleep(interval)
    log.warning("%s: %d ページで打ち切りました", endpoint, max_pages)
    return rows


def cache_path(raw_dir: Path, name: str) -> Path:
    return raw_dir / name


def save_cache(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def load_cache(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("%s を読めません: %s", path, exc)
        return []
