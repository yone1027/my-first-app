"""``python -m stockportal.batch.publish --as-of YYYY-MM-DD [--no-deploy] [--out DIR]``(詳細設計書 §13)。

全 API の応答を書き出し、Cloudflare Pages へ送り出す。終わったら ``status/publish_<基準日>.json`` を書く。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from ... import config
from .deploy import DeployError, assemble, deploy
from .export import Exporter

log = logging.getLogger("stockportal.publish")


def marker_path(cfg: config.Config, as_of: str) -> Path:
    return cfg.paths.status_dir / f"publish_{as_of.replace('-', '')}.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="クラウド版への書き出しと送り出し(詳細設計書 §13)")
    parser.add_argument("--as-of", required=True, help="基準日(YYYY-MM-DD)。終わった印の名前に使う")
    parser.add_argument("--no-deploy", action="store_true", help="書き出すだけで送らない(確かめ用)")
    parser.add_argument("--out", help="書き出し先(既定は portal_data/cloud)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = config.load()
    root = Path(args.out).expanduser() if args.out else cfg.paths.portal_data / "cloud"
    now = datetime.now()

    summary = Exporter(cfg, root / "_data").run(now)
    if args.no_deploy:
        log.info("--no-deploy のため送り出しません")
        return 0
    if not cfg.cloud.enabled:
        log.info("[cloud] enabled が false のため送り出しません")
        return 0
    try:
        project = assemble(cfg, root / "_data", root / "project")
        deploy(cfg, project)
    except DeployError as exc:
        log.error("送り出せませんでした: %s", exc)
        return 1

    marker = marker_path(cfg, args.as_of)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps({"as_of": args.as_of, "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"), **summary},
                   ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    log.info("送り出しました: %s", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
