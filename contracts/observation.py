"""
Observation contract exported for cross-layer use.

Current implementation re-exports Layer-1's canonical observation model so
all existing code paths keep enum/dataclass identity. This lets Layer-3 and
Layer-4 depend on a shared contract namespace (`contracts`) instead of
importing Layer-1 modules directly.
"""

from engine.Layer1_Collection.observation import (
    ActionType,
    SourceType,
    ObservationRecord,
    ObservationDeduplicator,
    deduplicator,
    gdelt_events_to_observations,
    worldbank_state_to_observations,
    comtrade_state_to_observations,
)

__all__ = [
    "ActionType",
    "SourceType",
    "ObservationRecord",
    "ObservationDeduplicator",
    "deduplicator",
    "gdelt_events_to_observations",
    "worldbank_state_to_observations",
    "comtrade_state_to_observations",
]
