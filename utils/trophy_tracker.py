from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TrophyChange:
    old_count: int
    new_count: int
    timestamp: datetime


class TrophyTracker:
    def __init__(self):
        self._daily_start: Optional[int] = None
        self._last_count: Optional[int] = None
        self._changes = []

    @property
    def daily_start(self) -> Optional[int]:
        return self._daily_start

    @property
    def last_count(self) -> Optional[int]:
        return self._last_count

    def set_daily_start(self, count: int):
        """Set the daily starting trophy count"""
        self._daily_start = count

    def update_count(self, count: int) -> Optional[TrophyChange]:
        """Update the trophy count and return the change if any"""
        if self._last_count is None:
            self._last_count = count
            return None

        if count != self._last_count:
            change = TrophyChange(
                old_count=self._last_count,
                new_count=count,
                timestamp=datetime.utcnow()
            )
            self._changes.append(change)
            self._last_count = count
            return change

        return None

    def get_daily_change(self) -> Optional[int]:
        """Get the trophy change since daily start"""
        if self._daily_start is None or self._last_count is None:
            return None
        return self._last_count - self._daily_start