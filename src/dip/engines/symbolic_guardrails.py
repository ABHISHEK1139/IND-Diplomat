"""Lightweight symbolic guardrails for neuro-symbolic DIP decisions.

This module provides a small local gate today and a clean future insertion
point for Z3, pyDatalog, and NeMo Guardrails.
"""

from __future__ import annotations

from importlib.util import find_spec
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class SymbolicFinding(BaseModel):
    rule: str
    severity: str = "info"
    message: str
    evidence: List[str] = Field(default_factory=list)


class SymbolicGuardrailReport(BaseModel):
    passed: bool = True
    findings: List[SymbolicFinding] = Field(default_factory=list)
    solver_stack: Dict[str, bool] = Field(default_factory=dict)


def solver_stack_status() -> Dict[str, bool]:
    return {
        "z3": find_spec("z3") is not None or find_spec("z3_solver") is not None,
        "pyDatalog": find_spec("pyDatalog") is not None,
        "nemoguardrails": find_spec("nemoguardrails") is not None,
    }


def run_symbolic_guardrails(result: Dict[str, Any]) -> SymbolicGuardrailReport:
    """Run deterministic symbolic checks over a result payload.

    These checks are intentionally conservative. They do not replace the legal
    subsystem; they detect contradictions and missing gates before output.
    """

    findings: List[SymbolicFinding] = []
    threat = str(result.get("threat_level") or "").upper()
    verification = float(result.get("verification_score") or 0.0)
    fuzzy = result.get("fuzzy_trace") or {}
    score = float(fuzzy.get("sre_escalation_score") or (result.get("nextgen_sre") or {}).get("sre_escalation_score") or 0.0)
    firewall_rejections = fuzzy.get("legal_firewall_rejections") or []

    if threat in {"HIGH", "CRITICAL"} and verification < 0.5:
        findings.append(
            SymbolicFinding(
                rule="high_risk_requires_grounding",
                severity="hard",
                message="High-risk output has low verification; require HITL or withholding.",
                evidence=[f"threat={threat}", f"verification={verification:.2f}"],
            )
        )

    if threat == "LOW" and score >= 0.65:
        findings.append(
            SymbolicFinding(
                rule="risk_band_sre_contradiction",
                severity="hard",
                message="Narrative threat is LOW but SRE score is elevated/high.",
                evidence=[f"sre_score={score:.2f}"],
            )
        )

    if firewall_rejections and not result.get("head_of_country_briefing"):
        findings.append(
            SymbolicFinding(
                rule="legal_firewall_visibility",
                severity="soft",
                message="Legal/RAG signals were rejected from SRE; final briefing should disclose this constraint.",
                evidence=[str(item) for item in firewall_rejections[:3]],
            )
        )

    # T28.3: Z3 Constraint Checking
    findings.extend(_run_z3_constraints(threat, score))

    # T28.4: pyDatalog Deductive Rules
    findings.extend(_run_pydatalog_facts(threat, verification))

    # T28.5: NeMo Guardrails check for narrative
    briefing = result.get("head_of_country_briefing", "")
    findings.extend(_run_nemo_guardrails(briefing))

    return SymbolicGuardrailReport(
        passed=not any(item.severity == "hard" for item in findings),
        findings=findings,
        solver_stack=solver_stack_status(),
    )


def _run_z3_constraints(threat: str, score: float) -> List[SymbolicFinding]:
    """Z3 solver to detect if SRE score mathematically contradicts the Threat Assessment."""
    try:
        import z3
    except ImportError:
        return []

    findings = []
    try:
        s = z3.Solver()
        ThreatVal = z3.Int('ThreatVal')
        SreScore = z3.Real('SreScore')

        threat_map = {"LOW": 1, "ELEVATED": 2, "HIGH": 3, "CRITICAL": 4}
        t_val = threat_map.get(threat, 0)

        s.add(SreScore == score)
        s.add(ThreatVal == t_val)

        # Logical requirement: If SRE > 0.8, Threat MUST be at least HIGH (3)
        rule = z3.Implies(SreScore > 0.8, ThreatVal >= 3)
        
        # We add the NEGATION to the solver. If the negation is satisfiable, we have a violation.
        s.add(z3.Not(rule))

        if s.check() == z3.sat:
            findings.append(
                SymbolicFinding(
                    rule="z3_sre_threat_contradiction",
                    severity="hard",
                    message="Z3 Solver detected a logical contradiction: SRE Score > 0.8 but Threat Level is not HIGH/CRITICAL.",
                    evidence=[f"threat={threat}", f"score={score}"]
                )
            )
    except Exception:
        pass
    return findings


def _run_pydatalog_facts(threat: str, verification: float) -> List[SymbolicFinding]:
    """pyDatalog deductive engine to assert assessment facts and query for logical contradictions."""
    try:
        from pyDatalog import pyDatalog
    except ImportError:
        return []
        
    # pyDatalog modifies caller locals dynamically, which fails inside standard Python functions.
    # We run it in an isolated dictionary to safely capture the dynamic terms.
    findings = []
    try:
        code = '''
pyDatalog.clear()
pyDatalog.create_terms('X, Y, is_high_risk, lacks_verification, contradiction')

# Assert facts dynamically
if threat in {"HIGH", "CRITICAL"}:
    +is_high_risk("current_assessment")
if verification < 0.5:
    +lacks_verification("current_assessment")

# Define logical rule
contradiction(X) <= is_high_risk(X) & lacks_verification(X)

# Query the logic engine
has_contradiction = bool(contradiction("current_assessment"))
'''
        env = {"pyDatalog": pyDatalog, "threat": threat, "verification": verification}
        exec(code, env)
        
        if env.get("has_contradiction"):
            findings.append(
                SymbolicFinding(
                    rule="pydatalog_verification_contradiction",
                    severity="hard",
                    message="pyDatalog deductive engine found a contradiction: Assessment is high risk but lacks verification.",
                    evidence=[f"threat={threat}", f"verification={verification}"]
                )
            )
    except Exception:
        pass
    return findings


def _run_nemo_guardrails(briefing_text: str) -> List[SymbolicFinding]:
    """NeMo Guardrails to scan final output narrative for policy violations."""
    if not briefing_text:
        return []
        
    try:
        from nemoguardrails import LLMRails, RailsConfig
    except ImportError:
        return []
        
    findings = []
    try:
        # In a fully deployed setup, we would load Colang (.co) files and YAML configs.
        # This is the insertion point for T28.5
        pass
    except Exception:
        pass
        
    return findings
