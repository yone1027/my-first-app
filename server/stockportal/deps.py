"""サーバーが持ち回るリーダー一式(詳細設計書 §5.1)。"""

from __future__ import annotations

from functools import cached_property

from .config import Config
from .readers.calendar import CalendarReader
from .readers.candidates import CandidatesReader
from .readers.market import MarketReader
from .readers.picks import PicksReader
from .readers.screen import ScreenReader
from .readers.sectors import SectorNames


class Services:
    """リーダーは1つずつ作り、キャッシュをまたいで使い回す(§5.5)。"""

    def __init__(self, cfg: Config):
        self.cfg = cfg

    @cached_property
    def screen(self) -> ScreenReader:
        return ScreenReader(self.cfg.paths.screen_dir)

    @cached_property
    def picks(self) -> PicksReader:
        return PicksReader(self.cfg.paths.selection_dir)

    @cached_property
    def candidates(self) -> CandidatesReader:
        return CandidatesReader(self.cfg.paths.candidates_dir)

    @cached_property
    def calendar(self) -> CalendarReader:
        return CalendarReader(self.cfg.paths.jquants_raw)

    @cached_property
    def market(self) -> MarketReader:
        return MarketReader(self.cfg.paths.market_dir)

    @cached_property
    def sectors(self) -> SectorNames:
        return SectorNames(self.cfg.paths.jquants_raw)
