import asyncio

from dip.nextgen.observed_signal import ObservedSignal
from dip.nextgen.signal_belief import SignalBeliefModel
from dip.nextgen.domain_fusion import fuse_domains
from dip.nextgen.escalation_index import compute_escalation
from dip.nextgen.signal_projection import project_signals


def test_signal_belief_and_fusion():
    s1 = ObservedSignal(entity="CountryA", action="deploy_troops", intensity=0.8, confidence=0.9)
    s2 = ObservedSignal(entity="CountryA", action="sanction_trade", intensity=0.6, confidence=0.7)

    b1 = SignalBeliefModel.from_observed(s1)
    b2 = SignalBeliefModel.from_observed(s2)

    assert b1["belief_level"] in ("moderate", "strong")
    assert 0.0 <= b1["support_score"] <= 1.0

    dom = fuse_domains([s1, s2])
    assert set(dom.keys()) == {"capability", "intent", "stability", "cost"}

    esc = compute_escalation(dom)
    assert "escalation_score" in esc and 0.0 <= esc["escalation_score"] <= 1.0

    proj = project_signals([s1, s2], horizon_days=14)
    assert isinstance(proj, list) and len(proj) == 2
