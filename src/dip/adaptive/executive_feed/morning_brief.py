import logging

try:
    import dspy
except ImportError:  # optional dependency; fail only on actual use
    dspy = None

logger = logging.getLogger("DIP3.Layer12.MorningBrief")

if dspy is not None:
    class MorningBriefSignature(dspy.Signature):
        """Synthesizes all critical alerts from the last 24 hours into a brief."""
        alerts = dspy.InputField(desc="List of alerts.")
        briefing = dspy.OutputField(desc="Executive summary in 3 bullet points.")
else:  # pragma: no cover - minimal installs without dspy
    MorningBriefSignature = None

class MorningBriefCompiler:
    def __init__(self):
        if dspy is None or MorningBriefSignature is None:
            raise ImportError("dspy is not installed. pip install 'politiq-ai[reasoning]'")
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
