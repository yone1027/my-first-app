"""接続元の制限(§9.1)。"""

from __future__ import annotations

import pytest

from stockportal.security import host_of, is_private_client


@pytest.mark.parametrize(
    "address,allowed",
    [
        ("127.0.0.1", True),
        ("::1", True),
        ("192.168.14.12", True),
        ("10.1.2.3", True),
        ("172.16.0.1", True),
        ("172.32.0.1", False),   # 172.16/12 の外
        ("8.8.8.8", False),
        ("2400:4050::1", False),
        ("testclient", False),
        (None, False),
    ],
)
def test_private_client(address, allowed):
    assert is_private_client(address) is allowed


@pytest.mark.parametrize(
    "header,expected",
    [
        ("stockportal.local:8765", "stockportal.local"),
        ("localhost", "localhost"),
        ("[::1]:8765", "::1"),
        ("192.168.14.12:8765", "192.168.14.12"),
        (None, ""),
    ],
)
def test_host_of(header, expected):
    assert host_of(header) == expected


def test_unknown_host_is_refused(client):
    assert client.get("/api/health", headers={"host": "evil.example.com"}).status_code == 403


def test_write_methods_are_refused(client):
    assert client.post("/api/health").status_code == 405


def test_noindex_header(client):
    assert client.get("/api/health").headers["x-robots-tag"] == "noindex"
