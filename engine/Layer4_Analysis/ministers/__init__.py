"""
The Council of Ministers — package entry point.
Re-exports all minister classes and shared symbols for backward compatibility.
"""

from engine.Layer4_Analysis.ministers.base import (
    ALLOWED_SIGNALS,
    BaseMinister,
    _as_float,
    _as_signal_token,
    _is_high_token,
    _pick,
)
from engine.Layer4_Analysis.ministers.security import SecurityMinister
from engine.Layer4_Analysis.ministers.economic import EconomicMinister
from engine.Layer4_Analysis.ministers.domestic import DomesticMinister
from engine.Layer4_Analysis.ministers.diplomatic import DiplomaticMinister
from engine.Layer4_Analysis.ministers.strategy import StrategyMinister
from engine.Layer4_Analysis.ministers.alliance import AllianceMinister
from engine.Layer4_Analysis.ministers.contrarian import ContrarianMinister  # Phase 8

__all__ = [
    "ALLOWED_SIGNALS",
    "BaseMinister",
    "SecurityMinister",
    "EconomicMinister",
    "DomesticMinister",
    "DiplomaticMinister",
    "StrategyMinister",
    "AllianceMinister",
    "ContrarianMinister",
]
