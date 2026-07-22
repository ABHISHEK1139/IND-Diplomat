import pytest
from dip.nextgen.self_model import AgentSelfModel
from dip.nextgen.experiment_gate import ExperimentGate
from dip.nextgen.replay_consolidation import ReplayBuffer

@pytest.mark.unit
def test_self_model_initialization():
    sm = AgentSelfModel()
    assert hasattr(sm, "history")
    assert isinstance(sm.history, list)

@pytest.mark.unit
def test_experiment_gate_initialization():
    gate = ExperimentGate()
    assert hasattr(gate, "fuse_assessment")

@pytest.mark.unit
def test_replay_buffer_initialization():
    buffer = ReplayBuffer()
    assert hasattr(buffer, "record_replay")
