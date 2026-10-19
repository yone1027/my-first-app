"""Cloudflare Pages へ送り出す(詳細設計書 §13.3)。

``portal_data/cloud/project/`` に、wrangler がそのまま読める形をそろえてから ``wrangler pages deploy`` を動かす。

    project/
      wrangler.toml   … プロジェクト名と Access の設定(ここで書く)
      functions/      … リポジトリの cloud/functions
      lib/            … リポジトリの cloud/lib(functions から読む)
      site/           … web/build + cloud/public + _data(書き出した JSON)

変わっていないファイルは wrangler が送らないので、毎週送るのは新しい週の分だけになる。
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

from ... import config

log = logging.getLogger(__name__)

COMPATIBILITY_DATE = "2026-10-01"


class DeployError(Exception):
    pass


def read_env(path: Path) -> dict[str, str]:
    """``KEY=value`` の行だけを読む。値は表示しない。"""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def wrangler_toml(cfg: config.Config) -> str:
    def quote(value: str) -> str:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    return "\n".join(
        [
            f"name = {quote(cfg.cloud.project)}",
            'pages_build_output_dir = "site"',
            f'compatibility_date = "{COMPATIBILITY_DATE}"',
            "",
            "[vars]",
            f"ACCESS_TEAM = {quote(cfg.cloud.access_team)}",
            f"ACCESS_AUD = {quote(cfg.cloud.access_aud)}",
            "",
        ]
    )


def assemble(cfg: config.Config, data_dir: Path, project_dir: Path) -> Path:
    """送り出す形をそろえる。"""
    repo = config.REPO_ROOT
    web_build = repo / "web" / "build"
    if not (web_build / "index.html").is_file():
        raise DeployError(f"{web_build} がありません。web で npm run build を実行してください")
    if project_dir.exists():
        shutil.rmtree(project_dir)
    site = project_dir / "site"
    shutil.copytree(web_build, site)
    shutil.copytree(repo / "cloud" / "public", site, dirs_exist_ok=True)
    shutil.copytree(data_dir, site / "_data")
    shutil.copytree(repo / "cloud" / "functions", project_dir / "functions")
    shutil.copytree(repo / "cloud" / "lib", project_dir / "lib")
    (project_dir / "wrangler.toml").write_text(wrangler_toml(cfg), encoding="utf-8")
    return project_dir


def wrangler_bin() -> Path:
    path = config.REPO_ROOT / "cloud" / "node_modules" / ".bin" / "wrangler"
    if not path.exists():
        raise DeployError(f"{path} がありません。cloud で npm ci を実行してください")
    return path


def deploy(cfg: config.Config, project_dir: Path) -> None:
    secrets = read_env(cfg.cloud.env_file)
    missing = [k for k in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID") if not secrets.get(k)]
    if missing:
        raise DeployError(f"{cfg.cloud.env_file} に {', '.join(missing)} がありません")
    env = {**os.environ, **{k: secrets[k] for k in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID")}}
    env["WRANGLER_SEND_METRICS"] = "false"
    command = [str(wrangler_bin()), "pages", "deploy", "--project-name", cfg.cloud.project, "--branch", "main", "--commit-dirty=true"]
    log.info("送り出します: %s", " ".join(command))
    completed = subprocess.run(command, cwd=project_dir, env=env, capture_output=True, text=True, timeout=1800)
    # wrangler の出力にトークンは含まれない。そのままログに残す
    for line in (completed.stdout + completed.stderr).splitlines():
        log.info("wrangler: %s", line)
    if completed.returncode != 0:
        raise DeployError(f"wrangler pages deploy が終了コード {completed.returncode} で終わりました")
