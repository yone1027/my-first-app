"""エラーの応答(詳細設計書 §5.9)。

例外はすべて1か所で受け、スタックトレースは応答に入れずログにだけ書く。
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .readers.cache import BadFormat, FileNotFound
from .readers.market import NotBuilt

log = logging.getLogger(__name__)


class NoData(Exception):
    """その基準日のファイルがない(404 / no_data)。"""

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class NoSuchDate(Exception):
    """存在しない基準日(404 / no_such_date)。"""

    def __init__(self, latest: str | None):
        super().__init__(str(latest))
        self.latest = latest


def install(app: FastAPI) -> None:
    @app.exception_handler(NoData)
    async def _no_data(_: Request, exc: NoData) -> JSONResponse:
        return JSONResponse({"error": "no_data", "detail": exc.detail}, status_code=404)

    @app.exception_handler(NoSuchDate)
    async def _no_such_date(_: Request, exc: NoSuchDate) -> JSONResponse:
        return JSONResponse({"error": "no_such_date", "latest": exc.latest}, status_code=404)

    @app.exception_handler(NotBuilt)
    async def _not_built(_: Request, exc: NotBuilt) -> JSONResponse:
        log.warning("市場概況の集計の結果が読めません: %s", exc)
        return JSONResponse({"error": "not_built"}, status_code=503)

    @app.exception_handler(FileNotFound)
    async def _missing(_: Request, exc: FileNotFound) -> JSONResponse:
        log.warning("ファイルがありません: %s", exc.path)
        return JSONResponse({"error": "no_data", "detail": exc.path.name}, status_code=404)

    @app.exception_handler(BadFormat)
    async def _bad_format(_: Request, exc: BadFormat) -> JSONResponse:
        log.error("ファイルの形が想定と違います: %s", exc)
        return JSONResponse({"error": "bad_format", "file": exc.path.name}, status_code=500)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("想定外の例外: %s", request.url.path)
        return JSONResponse({"error": "internal"}, status_code=500)
