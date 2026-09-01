"""
Introspection Engine (Layer 4)
==============================
Runs an after-action self-reflection on the Council's decision.
Grades the logic for bias and tracks minister performance.
"""

import os
import json
import logging
from datetime import datetime, timezone
from dip.pipeline.deliberation.reasoning.council_session import CouncilSession

logger = logging.getLogger("Layer4.introspection")
HISTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "introspection_history.json")


class PerformanceTracker:
    @staticmethod
    def analyze(session: CouncilSession) -> str:
        """
        Analyzes the council's performance based on the verification_score.
        Updates minister weights and records the session in a rolling history.
        Modifies the session's introspection_report attribute in-place.
        """
        if not session.hypotheses:
            report = "No hypotheses to analyze."
            session.introspection_report = report
            return report
            
        history = {}
        history_list = []
        minister_weights = {}
        
        # Load history
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        history_list = data.get("history", [])
                        minister_weights = data.get("minister_weights", {})
                    elif isinstance(data, list):
                        # Migrate from old list format
                        history_list = data
                        minister_weights = {}
            except Exception:
                pass
        
        # Default weights for new ministers
        for h in session.hypotheses:
            minister_name = getattr(h, "minister", getattr(h, "minister_name", getattr(h, "domain", "Minister")))
            if minister_name not in minister_weights:
                minister_weights[minister_name] = 1.0

        # Adjust weights based on verification_score
        weight_adjustments = {}
        for h in session.hypotheses:
            minister_name = getattr(h, "minister", getattr(h, "minister_name", getattr(h, "domain", "Minister")))
            conf = getattr(h, "confidence", 0.5)
            outcome_truth = (session.verification_score - 0.5) * 2.0 
            predicted_truth = (conf - 0.5) * 2.0
            
            # Match is positive if they align, negative if they diverge
            match_score = outcome_truth * predicted_truth
            
            # Adjust weight by a small learning rate (e.g., 0.1)
            adjustment = match_score * 0.1
            weight_adjustments[minister_name] = round(minister_weights[minister_name] + adjustment, 3)           
            # Keep weights within reasonable bounds, e.g. [0.1, 3.0]
            minister_weights[minister_name] = max(0.1, min(3.0, minister_weights[minister_name] + adjustment))
            weight_adjustments[minister_name] = adjustment

        # Calculate bias (like previous implementation)
        sec_conf = 0.0
        econ_conf = 0.0
        for h in session.hypotheses:
            minister_name = getattr(h, "minister", getattr(h, "minister_name", getattr(h, "domain", "Minister"))).lower()
            conf = getattr(h, "confidence", 0.5)
            if "security" in minister_name or "military" in minister_name:
                sec_conf = conf
            elif "economic" in minister_name:
                econ_conf = conf
                
        bias_score = sec_conf - econ_conf
        bias_label = "NEUTRAL"
        if bias_score > 0.3:
            bias_label = "HAWKISH_BIAS"
        elif bias_score < -0.3:
            bias_label = "DOVISH_BIAS"

        # Record entry
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query": session.query,
            "final_decision": session.final_decision,
            "verification_score": session.verification_score,
            "bias_label": bias_label,
            "bias_spread": round(bias_score, 2),
            "weight_adjustments": {m: round(adj, 3) for m, adj in weight_adjustments.items()}
        }
        
        history_list.append(entry)
        if len(history_list) > 100:
            history_list = history_list[-100:]
            
        # Save history
        with open(HISTORY_FILE, 'w') as f:
            json.dump({
                "minister_weights": minister_weights,
                "history": history_list
            }, f, indent=2)

        if bias_label != "NEUTRAL":
            logger.warning(f"Introspection Engine detected systemic bias: {bias_label} ({bias_score:+.2f})")

        # Generate report
        report_lines = [
            f"Introspection Report:",
            f"- Verification Score: {session.verification_score:.2f}",
            f"- Bias Detection: {bias_label}",
            "- Minister Weight Adjustments:"
        ]
        for m, adj in weight_adjustments.items():
            report_lines.append(f"  * {m}: {adj:+.3f} -> New Weight: {minister_weights[m]:.3f}")
            
        report = "\n".join(report_lines)
        session.introspection_report = report
        
        return report

# Keep backwards compatibility for any caller
def analyze_bias(session: CouncilSession) -> str:
    return PerformanceTracker.analyze(session)
