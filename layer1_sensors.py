"""
Layer-1 Sensors Module (Compatibility Layer)

This module re-exports from LAYER1_COLLECTION for cleaner imports.
New code should import from here; old code that imports from LAYER1_COLLECTION still works.

Usage:
    from layer1_sensors import ObservationRecord, GDELTSensor
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

# Re-export key components from Layer1_Collection
try:
    from engine.Layer1_Collection import (
        ObservationRecord,
        ActionType,
        SourceType,
        ObservationDeduplicator,
        GDELTSensor,
        WorldBankSensor,
        ComtradeSensor,
    )
except ImportError as e:
    print(f"[WARNING] Could not import from Layer1_Collection: {e}")
    # Provide minimal stub if LAYER1_COLLECTION unavailable
    ObservationRecord = None
    ActionType = None
    SourceType = None
    ObservationDeduplicator = None
    GDELTSensor = None
    WorldBankSensor = None
    ComtradeSensor = None


# Helper function to create observations (since ObservationRecord has specific signature)
def create_observation(
    obs_id: str,
    source: str,
    source_type: str,
    event_date: str,
    report_date: str,
    actors: List[str] = None,
    action_type: str = "observation",
    intensity: float = 0.5,
    confidence: float = 0.5,
    raw_data: Dict[str, Any] = None,
    **kwargs
) -> Optional[Any]:
    """
    Create an ObservationRecord with proper signature.
    
    This is a factory function that handles the dataclass requirements.
    """
    if ObservationRecord is None:
        return None
    
    try:
        return ObservationRecord(
            obs_id=obs_id,
            source=source,
            source_type=source_type or SourceType.MOVEMENT,
            event_date=event_date,
            report_date=report_date,
            actors=actors or [],
            action_type=action_type,
            intensity=intensity,
            confidence=confidence,
            raw_data=raw_data or {},
            **{k: v for k, v in kwargs.items() if k in [
                'direction', 'confidence_source', 'raw_reference', 
                'mention_count', 'dedup_key', 'metadata', 'ingest_date'
            ]}
        )
    except Exception as e:
        print(f"[ERROR] Failed to create observation: {e}")
        return None


# Export public API
__all__ = [
    "ObservationRecord",
    "ActionType",
    "SourceType",
    "ObservationDeduplicator",
    "GDELTSensor",
    "WorldBankSensor",
    "ComtradeSensor",
    "create_observation",
]
