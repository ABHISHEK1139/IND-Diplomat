from types import SimpleNamespace

from engine.Layer4_Analysis.coordinator import CouncilCoordinator
from engine.Layer4_Analysis.council_session import CouncilSession


def _state_with_signal():
    return SimpleNamespace(
        signal_beliefs=[],
        signal_confidence={"SIG_MIL_MOBILIZATION": 0.67},
        projected_signals={},
        meta=None,
        temporal=None,
        risk_level="ELEVATED",
        capability_index=0.61,
        intent_index=0.66,
        stability_index=0.37,
        cost_index=0.29,
    )


def test_repeated_investigation_is_skipped_when_state_did_not_change():
    coordinator = CouncilCoordinator()
    state = _state_with_signal()
    session = CouncilSession(
        session_id="sess-1",
        question="What is driving the current crisis?",
        state_context=state,
    )

    signature = coordinator._state_material_signature(state, ["SIG_MIL_MOBILIZATION"])
    session.last_investigated_signal_set = ["SIG_MIL_MOBILIZATION"]
    session.last_investigation_state_signature = signature
    session.last_investigation_material_change = False

    should_skip, reason = coordinator._should_skip_repeated_investigation(
        session,
        ["SIG_MIL_MOBILIZATION"],
    )

    assert should_skip is True
    assert reason == "repeated_signal_set_without_material_change"
