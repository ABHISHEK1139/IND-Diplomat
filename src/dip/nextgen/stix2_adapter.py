from __future__ import annotations
from dip.Config.config import config
"""STIX2/OpenCTI export adapter for intelligence sharing.

When stix2 is installed, this provides export of assessments as STIX bundles.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Optional import
try:
    import stix2
    STIX2_AVAILABLE = True
except Exception:
    STIX2_AVAILABLE = False

from .contracts import AssessmentGoal, HeadOfStateBriefing


class STIX2ExportAdapter:
    """Export Politiq AI assessments as STIX 2.1 bundles."""

    def __init__(self):
        if not STIX2_AVAILABLE:
            raise RuntimeError("stix2 not installed. Install with: pip install stix2")

    def create_identity(self, name: str, identity_class: str = "organization") -> stix2.Identity:
        """Create a STIX Identity object."""
        return stix2.Identity(
            id=stix2.Identity.generate_id(name=name, identity_class=identity_class),
            name=name,
            identity_class=identity_class,
            created=datetime.now(timezone.utc),
            modified=datetime.now(timezone.utc),
        )

    def create_indicator(self, pattern: str, labels: List[str], valid_from: datetime) -> stix2.Indicator:
        """Create a STIX Indicator object."""
        return stix2.Indicator(
            id=stix2.Indicator.generate_id(pattern=pattern),
            pattern_type="stix",
            pattern=pattern,
            labels=labels,
            valid_from=valid_from,
            created=datetime.now(timezone.utc),
            modified=datetime.now(timezone.utc),
        )

    def create_report(self, goal: AssessmentGoal, briefing: HeadOfStateBriefing) -> stix2.Report:
        """Create a STIX Report from an assessment."""
        now = datetime.now(timezone.utc)
        name = f"Politiq AI Assessment: {goal.objective[:100]}"
        return stix2.Report(
            id=stix2.Report.generate_id(name=name, published=now),
            name=name,
            description=briefing.executive_summary,
            published=now,
            report_types=["threat-report"],
            object_refs=[],  # Will be populated with indicators, etc.
            created=datetime.now(timezone.utc),
            modified=datetime.now(timezone.utc),
        )

    def create_relationship(self, source_ref: str, target_ref: str, relationship_type: str) -> stix2.Relationship:
        """Create a STIX Relationship object."""
        return stix2.Relationship(
            id=stix2.Relationship.generate_id(source_ref=source_ref, target_ref=target_ref, relationship_type=relationship_type),
            relationship_type=relationship_type,
            source_ref=source_ref,
            target_ref=target_ref,
            created=datetime.now(timezone.utc),
            modified=datetime.now(timezone.utc),
        )

    def export_assessment(self, goal: AssessmentGoal, briefing: HeadOfStateBriefing, 
                          result: Dict[str, Any]) -> stix2.Bundle:
        """Export a full assessment as a STIX Bundle."""
        objects = []

        # Create identity for DIP 2.0
        identity = self.create_identity("Politiq AI Intelligence System")
        objects.append(identity)

        # Create indicators from signals
        sre = result.get("nextgen_sre", {})
        projected_signals = sre.get("projected_signals", [])
        
        for signal in projected_signals:
            if signal.get("excluded_from_sre"):
                continue
            pattern = f"[x-dip2-signal:signal_code = '{signal.get('signal_code', '')}']"
            indicator = self.create_indicator(
                pattern=pattern,
                labels=["threat-actor", "malicious-activity"],
                valid_from=datetime.now(timezone.utc),
            )
            objects.append(indicator)

        # Create report
        report = self.create_report(goal, briefing)
        objects.append(report)

        # Create relationships
        new_objects = []
        for obj in objects:
            if hasattr(obj, 'id') and obj.id != identity.id:
                rel = self.create_relationship(identity.id, obj.id, "created-by")
                new_objects.append(rel)
        objects.extend(new_objects)

        return stix2.Bundle(objects=objects)

    def export_to_file(self, bundle: stix2.Bundle, filepath: str) -> None:
        """Export STIX bundle to JSON file."""
        with open(filepath, "w") as f:
            f.write(bundle.serialize(pretty=True))


def create_stix2_adapter() -> Optional[STIX2ExportAdapter]:
    """Factory to create STIX2 adapter if available."""
    if not STIX2_AVAILABLE:
        return None
    if not config.DIP_STIX2_ENABLED:
            return None
    return STIX2ExportAdapter()