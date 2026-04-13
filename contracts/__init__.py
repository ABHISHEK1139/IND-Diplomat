"""
Shared contracts used across layers.

These contracts are intentionally framework-light so each layer can
exchange structured data without importing another layer's internals.
"""

from .observation import (
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
