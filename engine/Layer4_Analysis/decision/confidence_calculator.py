"""
Confidence Calculator.
Implements the "Grounded Confidence" formula:
Confidence = (Base Confidence * Evidence Coverage * Agreement)
"""
from typing import List
import statistics
from engine.Layer4_Analysis.council_session import MinisterReport

class ConfidenceCalculator:

    @staticmethod
    def _safe_float(value: object, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)
    
    @staticmethod
    def calculate(reports: List[MinisterReport], state_confidence: float = 0.5) -> float:
        """
        Calculates grounded confidence.
        Formula: State Confidence * Evidence Coverage * Agreement Factor
        """
        if not reports:
            return 0.0

        # Extract all matched signals from reports with their confidences
        all_signals = []
        for r in reports:
            matched = list(getattr(r, "matched_signals", []) or [])
            # Ideally each signal has a confidence or source reliability.
            # If not, we fall back to the report's overall base confidence.
            report_conf = max(0.0, min(1.0, ConfidenceCalculator._safe_float(getattr(r, "confidence", 0.0), 0.5)))
            for sig in matched:
                all_signals.append({"name": sig, "confidence": report_conf})
        
        if not all_signals:
            # Fallback if no signals are matched
            conf_values = [
                max(0.0, min(1.0, ConfidenceCalculator._safe_float(getattr(r, "confidence", 0.0), 0.0)))
                for r in reports
            ]
            return sum(conf_values) / len(conf_values) if conf_values else 0.0

        # Combine duplicates and assign weights
        signal_max_conf = {}
        for sig in all_signals:
            name = sig["name"]
            c = sig["confidence"]
            if name not in signal_max_conf or c > signal_max_conf[name]:
                signal_max_conf[name] = c

        # Filter out noisy/duplicate overlap (e.g., in Economic domain)
        # Normalize weights so sum = 1
        total_signals = len(signal_max_conf)
        weight = 1.0 / total_signals
        
        final_confidence = sum(weight * conf for conf in signal_max_conf.values())
        
        # Propagate base uncertainty
        stdev = 0.0
        conf_values = list(signal_max_conf.values())
        if len(conf_values) > 1:
            stdev = statistics.stdev(conf_values)
            
        uncertainty_penalty = stdev * 0.5
        final_confidence = final_confidence * state_confidence * (1.0 - uncertainty_penalty)

        return max(0.0, min(1.0, final_confidence))
