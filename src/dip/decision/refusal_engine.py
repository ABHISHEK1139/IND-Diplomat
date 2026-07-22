"""
Refusal Engine: Gates output when verification fails.

If the council's assessment cannot be sufficiently verified against evidence,
the refusal engine blocks the output and sets the session status to REFUSED
with a structured explanation of why the assessment was not released.
"""

from typing import Dict, Any


def refuse(session) -> Dict[str, Any]:
    """
    Refuse to release the assessment. Sets session.status to 'REFUSED'.
    Returns a structured refusal message with details.
    """
    session.status = "REFUSED"

    # Determine the reason for refusal
    reasons = []

    if not session.hypotheses:
        reasons.append("No hypotheses were generated — insufficient intelligence signals.")

    if session.verification_score < 0.7:
        reasons.append(
            f"Verification score ({session.verification_score}) is below the 0.7 threshold. "
            f"Claims could not be adequately corroborated against evidence."
        )

    if not session.evidence_log:
        reasons.append("Evidence log is empty — no corroborating evidence available.")

    if session.red_team_report:
        critical_challenges = [
            c for c in session.red_team_report
            if "BIAS WARNING" in c.upper() or "EVIDENCE GAP" in c.upper()
        ]
        if critical_challenges:
            reasons.append(
                f"Red Team identified {len(critical_challenges)} critical concern(s) "
                f"that undermine assessment reliability."
            )

    refusal_message = {
        "status": "REFUSED",
        "verification_score": session.verification_score,
        "reasons": reasons if reasons else ["Assessment failed quality gates."],
        "recommendation": (
            "This assessment has been withheld from dissemination. "
            "Additional intelligence collection and analysis is required "
            "before a reliable assessment can be produced."
        ),
        "query": session.query,
        "country": session.state_context.country,
    }

    return refusal_message
