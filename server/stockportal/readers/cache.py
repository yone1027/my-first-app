"""ファイルの読み込みのキャッシュ(詳細設計書 §5.5)。

キーは「パス・更新時刻(mtime)・サイズ」。どれかが変われば読み直す。
基準日を切り替えて過去の週を見たときのために、直近 8 件まで持つ(LRU)。

``results.jsonl`` の中身はここに載せない(索引だけを持つ。§5.5)。
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")

DEFAULT_MAX_ENTRIES = 8


class FileNotFound(Exception):
    """読もうとしたファイルがない。"""

    def __init__(self, path: Path):
        super().__init__(str(path))
        self.path = path


class BadFormat(Exception):
    """ファイルの形が想定と違う(§5.9 の bad_format)。"""

    def __init__(self, path: Path, detail: str):
        super().__init__(f"{path}: {detail}")
        self.path = path
        self.detail = detail


def stamp(path: Path) -> tuple[str, int, int]:
    """キャッシュのキー。ファイルが無ければ FileNotFound。"""
    try:
        st = path.stat()
    except FileNotFoundError as exc:
        raise FileNotFound(path) from exc
    return (str(path), st.st_mtime_ns, st.st_size)


class FileCache:
    """パスごとに1つ、全体で最大 ``max_entries`` 件を持つ LRU。"""

    def __init__(self, max_entries: int = DEFAULT_MAX_ENTRIES):
        self._max = max_entries
        self._items: OrderedDict[str, tuple[tuple[str, int, int], object]] = OrderedDict()

    def get(self, path: Path, build: Callable[[Path], T]) -> T:
        key = str(path)
        current = stamp(path)
        hit = self._items.get(key)
        if hit is not None and hit[0] == current:
            self._items.move_to_end(key)
            return hit[1]  # type: ignore[return-value]
        value = build(path)
        self._items[key] = (current, value)
        self._items.move_to_end(key)
        while len(self._items) > self._max:
            self._items.popitem(last=False)
        return value

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)
