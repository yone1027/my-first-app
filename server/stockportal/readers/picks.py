"""来週の買い注文の候補を読む(詳細設計書 §7.2)。

``picks_<基準日>.csv`` は候補のカードの数値に、``picks_<基準日>.md`` は
指値の段・参考の上位10銘柄・検証の限界に使う。``plans_<基準日>.csv`` は読まない
(2026-09-26 決定)。
"""

from __future__ import annotations

import ast
import csv
import logging
import re
from pathlib import Path

from .cache import BadFormat, FileCache
from .markdown import Section, split_sections

log = logging.getLogger(__name__)

# 候補のカードに使う列(§7.2 の表)
CSV_COLUMNS = (
    "code", "name", "sector_name", "close", "entry", "stop", "target", "rr", "confluence",
    "p_fill", "p_target", "p_stop", "p_time", "ev_fill", "ev_order",
)

# 選定基準の札の文言(§7.2)。数値は辞書から入れる。
# 「効いていない」値のキーは札にしない(§7.2)。
INERT = {"min_ev_order": -9.0, "min_ev_fill": -9.0, "max_p_stop": 1.0}

SECTION_HEAD = re.compile(r"^(?P<rank>\d+)\.\s+(?P<code>[0-9A-Z]{4,5})\s+(?P<name>.+?)(?:\((?P<sector>.+)\))?$")
PREMISE = re.compile(r"前提.*?を満たした銘柄\s*([\d,]+).*?計画\s*([\d,]+)\s*件")
CRITERIA = re.compile(r"選定基準:\s*(\{.*\})")
CONFLUENCE_NAMES = re.compile(r"指値の根拠\(重なる支持線\s*(\d+)\s*本\)")
VALIDITY = re.compile(r"注文の有効期間:\s*(\d{4}-\d{2}-\d{2})〜(\d{4}-\d{2}-\d{2})")


def short_code(code: str) -> str:
    """5文字で末尾が 0 のときは末尾を落とす(``61780`` → ``6178``)。"""
    code = (code or "").strip()
    return code[:-1] if len(code) == 5 and code.endswith("0") else code


def _float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def parse_picks_csv(path: Path) -> list[dict]:
    """候補の行。約130列のうち §7.2 の表の列だけを使う。"""
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        missing = [c for c in CSV_COLUMNS if c not in header]
        if missing:
            raise BadFormat(path, f"列がありません: {missing}")
        rows = []
        for line in reader:
            rows.append(
                {
                    "code": short_code(line["code"]),
                    "name": line["name"].strip(),
                    "sector_name": line["sector_name"].strip(),
                    "close": _float(line["close"]),
                    "entry": _float(line["entry"]),
                    "stop": _float(line["stop"]),
                    "target": _float(line["target"]),
                    "rr": _float(line["rr"]),
                    "confluence": _float(line["confluence"]),
                    # p_* と ev_* は割合(0〜1)。実物で確認(2026-09-26。§7.2)。
                    "p_fill": _float(line["p_fill"]),
                    "p_target": _float(line["p_target"]),
                    "p_stop": _float(line["p_stop"]),
                    "p_time": _float(line["p_time"]),
                    "ev_fill": _float(line["ev_fill"]),
                    "ev_order": _float(line["ev_order"]),
                }
            )
        return rows


def criteria_badges(criteria: dict) -> list[str]:
    """選定基準の辞書を札の文言にする(§7.2 の表)。

    表にないキーは ``キー: 値`` のまま札にする。効いていない値は札にしない。
    """
    used: set[str] = set()
    badges: list[str] = []

    def take(*keys: str) -> bool:
        if all(k in criteria for k in keys):
            used.update(keys)
            return True
        return False

    def pct(key: str) -> str:
        """0.08 → "8"。割合を % の数だけにする。"""
        value = criteria[key] * 100
        return f"{value:g}"

    if take("min_reward_pct", "max_reward_pct"):
        badges.append(f"目標 +{pct('min_reward_pct')}〜{pct('max_reward_pct')}%")
    if take("min_rr", "max_rr"):
        badges.append(f"R:R {criteria['min_rr']:.1f}〜{criteria['max_rr']:.1f}")
    if take("limit_only") and criteria["limit_only"]:
        badges.append("指値のみ")
    if take("min_confluence"):
        badges.append(f"支持線の重なり{criteria['min_confluence']:g}本以上")
    if take("min_p_fill"):
        badges.append(f"約定確率{pct('min_p_fill')}%以上")
    if take("max_risk_pct"):
        badges.append(f"損切りまで{pct('max_risk_pct')}%以内")
    if take("max_picks", "one_per_sector"):
        label = f"最大{criteria['max_picks']:g}銘柄"
        badges.append(f"業種を分けて{label}" if criteria["one_per_sector"] else label)

    for key, value in criteria.items():
        if key in used or INERT.get(key) == value:
            continue
        badges.append(f"{key}: {value}")
    return badges


def parse_picks_md(path: Path) -> dict:
    """md から、冒頭の前提・候補ごとの節・参考・検証の限界を取る。"""
    text = path.read_text(encoding="utf-8")
    preamble, sections = split_sections(text)
    bullets = preamble.bullets()

    header: dict[str, object] = {"settlement": None, "universe": None, "plans": None, "criteria": {}, "criteria_badges": [], "validity": None, "model": None}
    for line in bullets:
        if line.startswith("注文の有効期間"):
            m = VALIDITY.search(line)
            header["validity"] = {"start": m.group(1), "end": m.group(2), "text": line} if m else {"text": line}
        elif line.startswith("決済"):
            header["settlement"] = line.split(":", 1)[-1].strip()
        elif "選定基準" in line:
            m = PREMISE.search(line)
            if m:
                header["universe"] = int(m.group(1).replace(",", ""))
                header["plans"] = int(m.group(2).replace(",", ""))
            c = CRITERIA.search(line)
            if c:
                try:
                    criteria = ast.literal_eval(c.group(1))
                    header["criteria"] = criteria
                    header["criteria_badges"] = criteria_badges(criteria)
                except (ValueError, SyntaxError) as exc:
                    log.warning("%s: 選定基準の辞書が読めません: %s", path.name, exc)
        elif line.startswith("モデルの学習データ"):
            header["model"] = line

    picks: dict[str, dict] = {}
    reference: list[dict] = []
    limits: dict[str, object] = {"bullets": [], "table": []}
    for section in sections:
        m = SECTION_HEAD.match(section.title)
        if m:
            picks[short_code(m.group("code"))] = _pick_section(section, m)
        elif section.title.startswith("参考"):
            reference = section.first_table()
        elif "検証で分かっている限界" in section.title:
            limits = {"bullets": section.bullets(), "table": section.first_table()}

    return {"header": header, "picks": picks, "reference": reference, "limits": limits}


def _pick_section(section: Section, m: re.Match) -> dict:
    tables = section.tables()
    facts = {str(row.get("項目")): row.get("値") for row in (tables[0] if tables else [])}
    confluence_names = None
    for key, value in facts.items():
        if key and key.startswith("指値の根拠"):
            confluence_names = value
    return {
        "rank": int(m.group("rank")),
        "sector_name": (m.group("sector") or "").strip() or None,
        "confluence_names": confluence_names,
        "ladder": tables[1] if len(tables) > 1 else [],
    }


class PicksReader:
    """基準日ごとの買い注文の候補。"""

    def __init__(self, selection_dir: Path):
        self.selection_dir = selection_dir
        self._csv = FileCache()
        self._md = FileCache()

    def csv_path(self, date: str) -> Path:
        return self.selection_dir / f"picks_{date.replace('-', '')}.csv"

    def md_path(self, date: str) -> Path:
        return self.selection_dir / f"picks_{date.replace('-', '')}.md"

    def has(self, date: str) -> bool:
        return self.md_path(date).exists()

    def read(self, date: str) -> dict:
        """CSV の数値に md の情報を重ねて返す。"""
        md = self._md.get(self.md_path(date), parse_picks_md)
        try:
            rows = self._csv.get(self.csv_path(date), parse_picks_csv)
        except Exception as exc:  # 候補0件の週は CSV が無いこともある
            log.info("%s: picks の CSV を読めませんでした(%s)。md だけで続けます", date, exc)
            rows = []

        picks = []
        for row in rows:
            extra = md["picks"].get(row["code"], {})
            picks.append({**row, **{k: v for k, v in extra.items() if k != "rank"}, "rank": extra.get("rank")})
        picks.sort(key=lambda p: (p["rank"] is None, p["rank"] or 0))
        return {
            "date": date,
            "header": md["header"],
            "picks": picks,
            "reference": md["reference"],
            "limits": md["limits"],
        }

    def last_updated(self, date: str) -> float | None:
        newest = None
        for path in (self.csv_path(date), self.md_path(date)):
            if path.exists():
                newest = max(newest or 0.0, path.stat().st_mtime)
        return newest
