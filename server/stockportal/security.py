"""接続元の制限(詳細設計書 §9.1)。

3段のうち、ポータルが受け持つのは 2(接続元の IP)と 3(Host ヘッダー)。
どちらも外れたら本文なしの 403 を返す。
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from collections.abc import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

log = logging.getLogger(__name__)

# 家のネットワークとみなす範囲(§9.1 の 2段目)
PRIVATE_NETWORKS = tuple(
    ipaddress.ip_network(n)
    for n in (
        "127.0.0.0/8",
        "::1/128",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "fe80::/10",
        "fd00::/8",
    )
)


def is_private_client(host: str | None) -> bool:
    """接続元の IP が家のネットワークの範囲かどうか。"""
    if not host:
        return False
    try:
        addr = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return False
    return any(addr in net for net in PRIVATE_NETWORKS)


def lan_addresses() -> set[str]:
    """この Mac の今の LAN の IP アドレス(§9.1 の 3段目で Host に許す)。"""
    found: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            found.add(info[4][0].split("%", 1)[0])
    except OSError as exc:  # 名前が引けないこともある
        log.warning("LAN の IP アドレスを取れませんでした: %s", exc)
    found.update({"127.0.0.1", "::1"})
    return found


def host_of(header: str | None) -> str:
    """Host ヘッダーからポート番号を落とした名前を返す。"""
    if not header:
        return ""
    value = header.strip()
    if value.startswith("["):  # IPv6 リテラル [::1]:8765
        return value[1 : value.index("]")] if "]" in value else value
    return value.rsplit(":", 1)[0] if value.count(":") == 1 else value


class LocalOnlyMiddleware(BaseHTTPMiddleware):
    """家の中からの接続だけを通す。"""

    def __init__(self, app, allowed_hosts: Iterable[str]):
        super().__init__(app)
        self._allowed = {h.lower() for h in allowed_hosts}
        self._lan = lan_addresses()

    def _host_ok(self, header: str | None) -> bool:
        name = host_of(header).lower()
        if not name:
            return False
        return name in self._allowed or name in self._lan

    async def dispatch(self, request: Request, call_next):
        client = request.client.host if request.client else None
        if not is_private_client(client):
            log.warning("家の外からの接続を断りました: client=%s path=%s", client, request.url.path)
            return Response(status_code=403)
        if not self._host_ok(request.headers.get("host")):
            log.warning("知らない Host を断りました: host=%r client=%s", request.headers.get("host"), client)
            return Response(status_code=403)
        return await call_next(request)
