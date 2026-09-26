"""FastAPI の組み立て(詳細設計書 §5.1)。

1. 接続元の制限のミドルウェア(§9.1)
2. API のルーター(``/api/...``)。受け付けるのは GET だけ
3. 画面の配信。``web/build/`` の静的ファイル。当たらない URL には ``index.html``
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

from . import config, errors
from .api import market, search, status, weekly
from .deps import Services
from .security import LocalOnlyMiddleware

log = logging.getLogger(__name__)

WEB_BUILD = config.REPO_ROOT / "web" / "build"


def create_app(cfg: config.Config | None = None, web_build: Path | None = None) -> FastAPI:
    cfg = cfg or config.load()
    build_dir = web_build if web_build is not None else WEB_BUILD

    app = FastAPI(title="株価ポータル", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.services = Services(cfg)
    app.state.web_build = build_dir

    # 1. 家の中からの接続だけを通す
    app.add_middleware(LocalOnlyMiddleware, allowed_hosts=cfg.server.allowed_hosts)
    # 応答は gzip で圧縮する(1KB 以上)
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.middleware("http")
    async def only_get(request: Request, call_next):
        """API は GET だけ。書き込む API は作らない(§9.1)。"""
        if request.method not in ("GET", "HEAD"):
            return JSONResponse({"error": "method_not_allowed"}, status_code=405)
        response = await call_next(request)
        # すべての応答に付ける(基本設計書 §9)
        response.headers["X-Robots-Tag"] = "noindex"
        return response

    # 2. API
    app.include_router(status.router)
    app.include_router(market.router)
    app.include_router(weekly.router)
    app.include_router(search.router)
    errors.install(app)

    @app.get("/api/{rest:path}", include_in_schema=False)
    def unknown_api(rest: str) -> JSONResponse:
        return JSONResponse({"error": "not_found"}, status_code=404)

    # 3. 画面
    @app.get("/{rest:path}", include_in_schema=False)
    def spa(rest: str) -> Response:
        build = app.state.web_build
        if rest:
            candidate = (build / rest).resolve()
            try:
                candidate.relative_to(build.resolve())
            except ValueError:
                return JSONResponse({"error": "not_found"}, status_code=404)
            if candidate.is_file():
                return FileResponse(candidate)
        index = build / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse(
            {"error": "web_not_built", "detail": "web/build/ がありません。web で npm run build を実行してください"},
            status_code=503,
        )

    return app


def factory() -> FastAPI:
    """``uvicorn stockportal.app:factory --factory`` の入口。"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    return create_app()
