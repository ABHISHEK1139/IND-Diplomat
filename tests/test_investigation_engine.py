"""
Test Suite: Investigation Engine (Layer 0)
==========================================

Tests the state machine, folder persistence, timeline, and round-trip
serialization of the new Investigation root object.
"""

import json
import os
import shutil
import tempfile
import pytest
from datetime import datetime, timezone

from dip.core.schema import (
    Investigation,
    UserObjective,
    InvestigationScope,
    CollectionPlan,
    CollectionNeed,
    TimelineEvent,
    InvestigationAlert,
    VALID_TRANSITIONS,
    INVESTIGATION_STATES,
)
from dip.core.investigation_store import InvestigationStore, InvalidTransitionError


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def tmp_store(tmp_path):
    """Create a temporary InvestigationStore."""
    return InvestigationStore(root_dir=str(tmp_path / "investigations"))


@pytest.fixture
def sample_investigation():
    """Create a minimal valid Investigation."""
    now = datetime.now(timezone.utc).isoformat()
    return Investigation(
        investigation_id="INV-TEST-001",
        title="India AI Ecosystem",
        description="Assess India's capability to become a global AI leader.",
        original_query="Analyze India's AI ecosystem",
        owner="Abhishek",
        priority="High",
        tags=["AI", "India", "Economy"],
        status="CREATED",
        objective=UserObjective(
            objective="Can India become a top-3 AI economy by 2035?",
            decision_support_type="Government Policy",
            time_horizon="10 Years",
            depth="Research",
            output_format="Dossier",
            confidence_target=0.90,
        ),
        scope=InvestigationScope(
            countries=["India", "USA", "China"],
            domains=["AI", "Education", "Manufacturing", "Economy"],
            companies=["NVIDIA", "OpenAI", "Google", "Infosys", "TCS"],
            government_bodies=["MeitY", "DST", "NITI Aayog"],
            key_actors=["PM Modi", "Sam Altman"],
            keywords=["artificial intelligence", "semiconductors", "talent pipeline"],
        ),
        collection_plan=CollectionPlan(
            needs=[
                CollectionNeed(source_type="Government Reports", priority="Critical", description="MeitY AI strategy"),
                CollectionNeed(source_type="Academic Papers", priority="High", description="AI research output"),
                CollectionNeed(source_type="Patent Data", priority="High", description="AI patent filings"),
                CollectionNeed(source_type="News", priority="Medium", description="Industry coverage"),
            ],
            generated_at=now,
            total_sources_planned=4,
        ),
        created_at=now,
        updated_at=now,
    )


# ------------------------------------------------------------------
# State Machine Tests
# ------------------------------------------------------------------

class TestStateMachine:

    def test_all_states_defined(self):
        assert len(INVESTIGATION_STATES) == 9
        assert "CREATED" in INVESTIGATION_STATES
        assert "ARCHIVED" in INVESTIGATION_STATES

    def test_valid_transitions_cover_all_states(self):
        for state in INVESTIGATION_STATES:
            assert state in VALID_TRANSITIONS, f"Missing transitions for {state}"

    def test_valid_forward_transition(self, tmp_store, sample_investigation):
        tmp_store.create(sample_investigation)
        tmp_store.transition(sample_investigation, "PLANNING")
        assert sample_investigation.status == "PLANNING"

    def test_invalid_transition_raises(self, tmp_store, sample_investigation):
        tmp_store.create(sample_investigation)
        with pytest.raises(InvalidTransitionError):
            tmp_store.transition(sample_investigation, "REASONING")  # Can't jump

    def test_full_lifecycle(self, tmp_store, sample_investigation):
        """Walk through the entire lifecycle."""
        tmp_store.create(sample_investigation)
        path = [
            "PLANNING", "COLLECTING", "ANALYZING", "REASONING",
            "FORECASTING", "REPORTING", "MONITORING",
        ]
        for state in path:
            tmp_store.transition(sample_investigation, state)
            assert sample_investigation.status == state

    def test_monitoring_can_re_collect(self, tmp_store, sample_investigation):
        """MONITORING → COLLECTING is allowed for updates."""
        tmp_store.create(sample_investigation)
        for s in ["PLANNING", "COLLECTING", "ANALYZING", "REASONING",
                   "FORECASTING", "REPORTING", "MONITORING"]:
            tmp_store.transition(sample_investigation, s)
        tmp_store.transition(sample_investigation, "COLLECTING")
        assert sample_investigation.status == "COLLECTING"


# ------------------------------------------------------------------
# Persistence Tests
# ------------------------------------------------------------------

class TestPersistence:

    def test_create_folder_tree(self, tmp_store, sample_investigation):
        inv_dir = tmp_store.create(sample_investigation)
        assert inv_dir.exists()
        for sub in ["evidence", "reports", "hypotheses", "timeline",
                     "world_model", "feedback", "versions", "datasets"]:
            assert (inv_dir / sub).is_dir(), f"Missing: {sub}/"

    def test_metadata_round_trip(self, tmp_store, sample_investigation):
        tmp_store.create(sample_investigation)
        loaded = tmp_store.load("INV-TEST-001")
        assert loaded is not None
        assert loaded.investigation_id == "INV-TEST-001"
        assert loaded.title == "India AI Ecosystem"
        assert loaded.owner == "Abhishek"
        assert loaded.objective.objective == "Can India become a top-3 AI economy by 2035?"
        assert len(loaded.scope.countries) == 3
        assert len(loaded.collection_plan.needs) == 4

    def test_list_all(self, tmp_store, sample_investigation):
        tmp_store.create(sample_investigation)
        all_inv = tmp_store.list_all()
        assert len(all_inv) == 1
        assert all_inv[0].investigation_id == "INV-TEST-001"

    def test_version_snapshot(self, tmp_store, sample_investigation):
        tmp_store.create(sample_investigation)
        tmp_store.snapshot_version(sample_investigation)
        ver_file = tmp_store._inv_dir("INV-TEST-001") / "versions" / "v1.json"
        assert ver_file.exists()


# ------------------------------------------------------------------
# Timeline Tests
# ------------------------------------------------------------------

class TestTimeline:

    def test_timeline_append_only(self, tmp_store, sample_investigation):
        tmp_store.create(sample_investigation)
        # The create call itself logs a CREATED event
        events = tmp_store.read_timeline("INV-TEST-001")
        assert len(events) >= 1
        assert events[0].event_type == "CREATED"

    def test_state_transitions_logged(self, tmp_store, sample_investigation):
        tmp_store.create(sample_investigation)
        tmp_store.transition(sample_investigation, "PLANNING")
        tmp_store.transition(sample_investigation, "COLLECTING")
        events = tmp_store.read_timeline("INV-TEST-001")
        state_events = [e for e in events if e.event_type == "STATE_CHANGE"]
        assert len(state_events) == 2
        assert state_events[0].metadata["to"] == "PLANNING"
        assert state_events[1].metadata["to"] == "COLLECTING"


# ------------------------------------------------------------------
# Backward Compatibility Tests
# ------------------------------------------------------------------

class TestBackwardCompat:

    def test_goal_property(self, sample_investigation):
        """The .goal property should generate a valid InvestigationGoal from the new schema."""
        goal = sample_investigation.goal
        assert goal.topic == "India AI Ecosystem"
        assert goal.target_country == "India"
        assert goal.time_horizon == "10 Years"
        assert "AI" in goal.domains
        assert goal.confidence_target == 0.90
        assert len(goal.required_sources) == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
