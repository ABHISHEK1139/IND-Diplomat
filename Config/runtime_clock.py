"""
Runtime clock abstraction for deterministic historical replay.
"""

from __future__ import annotations

import datetime as _dt
from contextlib import contextmanager
from typing import Iterator, Optional, Union


DateLike = Union[_dt.date, _dt.datetime, str]


class RuntimeClock:
    _override: Optional[_dt.date] = None

    @classmethod
    def _parse(cls, value: DateLike) -> _dt.date:
        if isinstance(value, _dt.datetime):
            return value.date()
        if isinstance(value, _dt.date):
            return value
        token = str(value or "").strip()
        if not token:
            raise ValueError("empty date override")
        # Accept YYYY-MM-DD and full ISO datetime.
        return _dt.date.fromisoformat(token[:10])

    @classmethod
    def today(cls) -> _dt.date:
        return cls._override or _dt.date.today()

    @classmethod
    def now(cls, tz: Optional[_dt.tzinfo] = None) -> _dt.datetime:
        base = cls.today()
        if tz is None:
            return _dt.datetime.combine(base, _dt.time.min)
        return _dt.datetime.combine(base, _dt.time.min, tzinfo=tz)

    @classmethod
    def utcnow(cls) -> _dt.datetime:
        return cls.now(_dt.timezone.utc)

    @classmethod
    def set(cls, new_date: DateLike) -> None:
        cls._override = cls._parse(new_date)

    @classmethod
    def reset(cls) -> None:
        cls._override = None


@contextmanager
def frozen_date(new_date: DateLike) -> Iterator[None]:
    prev = RuntimeClock._override
    RuntimeClock.set(new_date)
    try:
        yield
    finally:
        RuntimeClock._override = prev


__all__ = ["RuntimeClock", "frozen_date"]
