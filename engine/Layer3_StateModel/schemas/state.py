"""
Country State Profile
=====================
The central object for geopolitical reasoning.
Represents a snapshot of a country's status at a specific time.
"""

from typing import Dict, Optional, Any
from engine.Layer2_Knowledge.signals.base import (
    SignalType,
    BaseSignal,
    EventSignal,
    EconomicSignal,
    MilitarySignal,
)

class CountryState:
    """
    Unified snapshot of a country's geopolitical status.
    Aggregates signals from multiple sources (GDELT, WorldBank, etc.)
    """
    
    def __init__(self, country_code: str, date: str):
        self.country_code = country_code.upper()
        self.date = date  # ISO format "YYYY-MM-DD"
        
        # Core signals
        self.signals: Dict[SignalType, Optional[BaseSignal]] = {
            SignalType.EVENT: None,
            SignalType.ECONOMIC: None,
            SignalType.MILITARY: None,
            SignalType.LEGAL: None,
            SignalType.LEADERSHIP: None,
            SignalType.DIPLOMACY: None
        }
        
        # Raw data references (for traceability)
        self.evidence_refs: Dict[str, Any] = {}

    def update_signal(self, signal_type: SignalType, signal: BaseSignal):
        """Update a specific signal layer."""
        self.signals[signal_type] = signal

    def get_signal(self, signal_type: SignalType) -> Optional[BaseSignal]:
        """Retrieve a specific signal."""
        return self.signals.get(signal_type)

    def to_dict(self) -> Dict:
        """Serialize state for analysis agents."""
        return {
            "country": self.country_code,
            "date": self.date,
            "signals": {
                k.value: (v.__dict__ if v else None)
                for k, v in self.signals.items()
            }
        }

    def __repr__(self):
        active_signals = [k.value for k, v in self.signals.items() if v]
        return f"<CountryState(country={self.country_code}, date={self.date}, active={active_signals})>"
