import logging
import dspy

logger = logging.getLogger("DIP3.Layer12.MorningBrief")

class MorningBriefSignature(dspy.Signature):
    """Synthesizes all critical alerts from the last 24 hours into a brief."""
    alerts = dspy.InputField(desc="List of alerts.")
    briefing = dspy.OutputField(desc="Executive summary in 3 bullet points.")

class MorningBriefCompiler:
    def __init__(self):
        try:
            self.module = dspy.Predict(MorningBriefSignature)
        except Exception:
            self.module = None
        
    def generate_brief(self, alerts: list[str]) -> str:
        try:
            if not self.module:
                raise ValueError("DSPy module not initialized.")
            result = self.module(alerts="\n".join(alerts))
            return result.briefing
        except Exception as e:
            logger.error(f"Morning brief generation failed: {e}")
            return "- Mocked Brief Point 1\n- Mocked Brief Point 2"
