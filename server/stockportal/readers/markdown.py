"""``picks_<基準日>.md`` のような Markdown を読む道具(詳細設計書 §7.2)。

``## `` の見出しで節に分け、節の中の最初の表を1行目を列名として読む。
数字の ``,`` と ``%`` は外して数にする。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

NUMBER = re.compile(r"^[+\-−]?[\d,]+(\.\d+)?%?$")


@dataclass
class Section:
    title: str
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def bullets(self) -> list[str]:
        return [line.lstrip("-* ").strip() for line in self.lines if line.lstrip().startswith(("- ", "* "))]

    def tables(self) -> list[list[dict[str, object]]]:
        return parse_tables(self.lines)

    def first_table(self) -> list[dict[str, object]]:
        tables = self.tables()
        return tables[0] if tables else []


def split_sections(text: str) -> tuple[Section, list[Section]]:
    """(見出しより前の部分, `## ` の節の一覧)。"""
    preamble = Section(title="")
    sections: list[Section] = []
    current = preamble
    for line in text.splitlines():
        if line.startswith("## "):
            current = Section(title=line[3:].strip())
            sections.append(current)
        elif line.startswith("# "):
            continue
        else:
            current.lines.append(line)
    return preamble, sections


def to_number(value: str) -> object:
    """表の値を数にする。数でなければ文字列のまま返す。"""
    text = value.strip()
    if not text or text in {"—", "-", "–"}:
        return None
    if NUMBER.match(text):
        cleaned = text.replace(",", "").replace("−", "-").rstrip("%")
        try:
            return float(cleaned) if "." in cleaned else int(cleaned)
        except ValueError:
            return text
    return text


def _cells(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [c.strip() for c in stripped.split("|")]


def _is_separator(line: str) -> bool:
    return bool(re.fullmatch(r"\|?[\s:|-]+\|?", line.strip())) and "-" in line


def parse_tables(lines: list[str]) -> list[list[dict[str, object]]]:
    """``|`` で始まる行のかたまりごとに、1つの表として読む。"""
    tables: list[list[dict[str, object]]] = []
    block: list[str] = []

    def flush() -> None:
        if len(block) < 2:
            block.clear()
            return
        header = _cells(block[0])
        body = block[2:] if _is_separator(block[1]) else block[1:]
        rows = []
        for line in body:
            cells = _cells(line)
            if len(cells) < len(header):
                cells += [""] * (len(header) - len(cells))
            rows.append({header[i]: to_number(cells[i]) for i in range(len(header))})
        if rows:
            tables.append(rows)
        block.clear()

    for line in lines:
        if line.strip().startswith("|"):
            block.append(line)
        else:
            flush()
    flush()
    return tables
