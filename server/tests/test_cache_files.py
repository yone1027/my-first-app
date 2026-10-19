"""J-Quants のキャッシュから読むファイルの選び方(§6.1・§7.4)。"""

from __future__ import annotations

from stockportal.batch.aggregate.jq import newest_by_to as aggregate_newest
from stockportal.readers.calendar import newest_by_to as reader_newest


def test_the_longest_range_wins_among_files_with_the_same_end(tmp_path):
    """2026-10-19: 数週分だけの短いカレンダーが同じ to= で置かれ、週の一覧が5週になった。"""
    for name in (
        "from=2026-09-12_to=2026-10-16.json.gz",
        "from=2016-10-18_to=2026-10-16.json.gz",
        "from=2026-08-23_to=2026-10-16.json.gz",
        "from=2026-10-03_to=2026-10-15.json.gz",
    ):
        (tmp_path / name).write_bytes(b"")
    for newest in (aggregate_newest, reader_newest):
        assert newest(tmp_path).name == "from=2016-10-18_to=2026-10-16.json.gz"


def test_a_newer_end_still_wins(tmp_path):
    for name in ("from=2016-10-18_to=2026-10-16.json.gz", "from=2026-10-10_to=2026-10-23.json.gz"):
        (tmp_path / name).write_bytes(b"")
    for newest in (aggregate_newest, reader_newest):
        assert newest(tmp_path).name == "from=2026-10-10_to=2026-10-23.json.gz"
