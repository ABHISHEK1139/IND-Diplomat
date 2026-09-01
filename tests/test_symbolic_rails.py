import pytest
from dip.engines.symbolic_guardrails import run_symbolic_guardrails, _run_z3_constraints, _run_pydatalog_facts

@pytest.mark.unit
def test_symbolic_guardrails_pass():
    # A normal, non-contradictory result
    result = {
        "threat_level": "ELEVATED",
        "verification_score": 0.8,
        "fuzzy_trace": {
            "sre_escalation_score": 0.4
        }
    }
    report = run_symbolic_guardrails(result)
    assert report.passed is True
    assert len(report.findings) == 0

@pytest.mark.unit
def test_symbolic_guardrails_high_risk_requires_grounding():
    # High risk but low verification
    result = {
        "threat_level": "HIGH",
        "verification_score": 0.3,
        "fuzzy_trace": {
            "sre_escalation_score": 0.7
        }
    }
    report = run_symbolic_guardrails(result)
    assert report.passed is False
    assert any(f.rule == "high_risk_requires_grounding" for f in report.findings)

@pytest.mark.unit
def test_symbolic_guardrails_sre_contradiction():
    # LOW threat but high SRE score
    result = {
        "threat_level": "LOW",
        "verification_score": 0.8,
        "fuzzy_trace": {
            "sre_escalation_score": 0.85
        }
    }
    report = run_symbolic_guardrails(result)
    assert report.passed is False
    assert any(f.rule == "risk_band_sre_contradiction" for f in report.findings)

@pytest.mark.unit
def test_z3_sre_threat_contradiction():
    # If SRE > 0.8, Threat MUST be >= HIGH (3)
    # Test violation: SRE = 0.9, Threat = ELEVATED (2)
    findings = _run_z3_constraints("ELEVATED", 0.9)
    try:
        import z3
        assert len(findings) == 1
        assert findings[0].rule == "z3_sre_threat_contradiction"
    except ImportError:
        assert len(findings) == 0

@pytest.mark.unit
def test_z3_sre_threat_ok():
    # SRE = 0.9, Threat = HIGH (3)
    findings = _run_z3_constraints("HIGH", 0.9)
    assert len(findings) == 0

@pytest.mark.unit
def test_pydatalog_contradiction():
    # Assessment is HIGH risk but verification < 0.5
    findings = _run_pydatalog_facts("HIGH", 0.2)
    try:
        from pyDatalog import pyDatalog
        assert len(findings) == 1
        assert findings[0].rule == "pydatalog_verification_contradiction"
    except ImportError:
        assert len(findings) == 0

@pytest.mark.unit
def test_pydatalog_ok():
    # Assessment is HIGH risk and verification >= 0.5
    findings = _run_pydatalog_facts("HIGH", 0.8)
    assert len(findings) == 0
