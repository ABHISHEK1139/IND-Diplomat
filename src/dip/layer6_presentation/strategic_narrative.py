import logging
from typing import Dict, Any, List

logger = logging.getLogger("DIP.Layer6.StrategicNarrative")

def _build_executive_summary(result: Dict[str, Any]) -> str:
    topic = result.get("query", "Unknown Topic")
    threat = result.get("threat_level", "UNKNOWN")
    return f"The autonomous system has completed a recursive investigation into '{topic}'. The verified strategic threat level is assessed as {threat}."

def _build_threat_assessment(session: Any, result: Dict[str, Any]) -> List[str]:
    assessments = []
    for h in result.get("hypotheses", []):
        minister = h.get("minister", "Unknown Minister")
        conf = h.get("confidence", 0.0)
        h_type = h.get("type", "unknown event")
        assessments.append(f"{minister} assessed {h_type} with {conf*100:.1f}% confidence.")
    return assessments if assessments else ["No clear threat hypotheses formed."]

def _build_evidence(result: Dict[str, Any]) -> List[str]:
    obs_count = result.get('observation_count', 0)
    score = result.get('verification_score', 0)
    return [
        f"Processed {obs_count} unique signals.",
        f"Verification Score (CoVe): {score*100:.1f}%"
    ]

def _build_counter_arguments(result: Dict[str, Any]) -> List[str]:
    red_team = result.get("red_team_report")
    if red_team and isinstance(red_team, list):
        return red_team
    return ["No significant counter arguments or biases detected during the Red Team phase."]

def _build_forecast(result: Dict[str, Any]) -> List[str]:
    traj = result.get("trajectory", {})
    if traj:
        return [f"Forecast: {traj.get('label', 'Stable')}", f"Key Driver: {traj.get('driver', 'None')}"]
    return ["Forecast trajectory remains stable based on current indicators."]

def _build_recommendations(result: Dict[str, Any]) -> List[str]:
    status = result.get("status", "UNKNOWN")
    if status == "HUMAN_OVERRIDE_REQUIRED":
        return ["CRITICAL: Investigation reached max RFI iterations without achieving readiness. Human intervention required to guide intelligence gathering."]
    elif status == "HUMAN_REVIEW":
        return ["CRITICAL: Final assessment failed safety/symbolic guardrails. Human review required."]
    return ["Continue monitoring indicators.", "Deploy automated sensors to track missing entities identified in the readiness report."]

def synthesize_narrative(session: Any, result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synthesizes the pipeline result into a modular strategic narrative.
    """
    logger.info("Synthesizing modular strategic narrative...")
    
    narrative = {
        "executive_summary": _build_executive_summary(result),
        "threat_assessment": _build_threat_assessment(session, result),
        "evidence": _build_evidence(result),
        "counter_arguments": _build_counter_arguments(result),
        "forecast": _build_forecast(result),
        "recommendations": _build_recommendations(result),
        "generation_mode": "modular_heuristic"
    }
    
    return narrative

def narrative_to_markdown(narrative: Dict[str, Any]) -> str:
    """Converts the narrative dictionary into a formatted Markdown string."""
    md = f"# Strategic Narrative\n\n"
    
    md += f"## Executive Summary\n{narrative.get('executive_summary', '')}\n\n"
    
    md += "## Threat Assessment\n"
    for item in narrative.get("threat_assessment", []):
        md += f"- {item}\n"
    md += "\n"
        
    md += "## Evidentiary Basis\n"
    for item in narrative.get("evidence", []):
        md += f"- {item}\n"
    md += "\n"
        
    md += "## Counter Arguments & Red Team\n"
    for item in narrative.get("counter_arguments", []):
        md += f"- {item}\n"
    md += "\n"
        
    md += "## Trajectory Forecast\n"
    for item in narrative.get("forecast", []):
        md += f"- {item}\n"
    md += "\n"
        
    md += "## Strategic Recommendations\n"
    for item in narrative.get("recommendations", []):
        md += f"- {item}\n"
    md += "\n"
        
    return md
