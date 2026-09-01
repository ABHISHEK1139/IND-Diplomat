import logging

try:
    import dspy
except ImportError:
    dspy = None
    logging.getLogger("Layer4.DSPy").warning("dspy library not found. Reasoners may fail if not mocked.")

if dspy:
    class ExpertAnalysis(dspy.Signature):
        """You are a domain expert analyzing an intelligence topic using knowledge graph beliefs."""
        
        topic = dspy.InputField(desc="The core intelligence topic being investigated")
        expert_role = dspy.InputField(desc="The specific role and expertise of the analyst")
        graph_context = dspy.InputField(desc="Context retrieved from the World Model knowledge graph")
        
        predicted_signals = dspy.OutputField(desc="Comma-separated list of events to expect next")
        matched_signals = dspy.OutputField(desc="Comma-separated list of claims confirming this view")
        missing_signals = dspy.OutputField(desc="Comma-separated list of conspicuously absent evidence")
        rationale = dspy.OutputField(desc="Brief explanation of the hypothesis")
        confidence = dspy.OutputField(desc="A float between 0.0 and 1.0 representing confidence")

    class DebateArbiter(dspy.Signature):
        """You are the Arbiter of the Intelligence Council synthesizing conflicting hypotheses into a consensus."""
        
        topic = dspy.InputField(desc="The core intelligence topic")
        debate_context = dspy.InputField(desc="The conflicting hypotheses from various experts")
        
        predicted_signals = dspy.OutputField(desc="Comma-separated list of synthesized events to expect")
        matched_signals = dspy.OutputField(desc="Comma-separated list of agreed upon claims")
        missing_signals = dspy.OutputField(desc="Comma-separated list of crucial missing evidence")
        rationale = dspy.OutputField(desc="Explanation of how conflicts were resolved")
        confidence = dspy.OutputField(desc="A float between 0.0 and 1.0 representing the consensus confidence")
else:
    class ExpertAnalysis:
        pass
    class DebateArbiter:
        pass
