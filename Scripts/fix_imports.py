"""Batch-fix all remaining deleted-shim import paths."""
import os

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

mappings = {
    "from Layer4_Analysis.intake.analyst_input_builder import": "from Layer4_Analysis.intake.analyst_input_builder import",
    "from Layer4_Analysis.investigation.anomaly_sentinel import": "from Layer4_Analysis.investigation.anomaly_sentinel import",
    "from Layer4_Analysis.core.council_session import": "from Layer4_Analysis.core.council_session import",
    "from Layer4_Analysis.deliberation.crag import": "from Layer4_Analysis.deliberation.crag import",
    "from Layer4_Analysis.investigation.deception_monitor import": "from Layer4_Analysis.investigation.deception_monitor import",
    "from Layer4_Analysis.evidence.evidence_tracker import": "from Layer4_Analysis.evidence.evidence_tracker import",
    "from Layer4_Analysis.evidence.evidence_requirements import": "from Layer4_Analysis.evidence.evidence_requirements import",
    "from Layer4_Analysis.evidence.gap_analyzer import": "from Layer4_Analysis.evidence.gap_analyzer import",
    "from Layer4_Analysis.investigation.investigation_request import": "from Layer4_Analysis.investigation.investigation_request import",
    "from Layer4_Analysis.investigation.investigation_controller import": "from Layer4_Analysis.investigation.investigation_controller import",
    "from Layer4_Analysis.hypothesis.perspective_agent import": "from Layer4_Analysis.hypothesis.perspective_agent import",
    "from Layer4_Analysis.decision.refusal_engine import": "from Layer4_Analysis.decision.refusal_engine import",
    "from Layer4_Analysis.decision.verifier import": "from Layer4_Analysis.decision.verifier import",
    "from Layer4_Analysis.intake.question_scope_checker import": "from Layer4_Analysis.intake.question_scope_checker import",
    "from Layer4_Analysis.core.coordinator import": "from Layer4_Analysis.core.coordinator import",
    "from Layer4_Analysis.deliberation.cove import": "from Layer4_Analysis.deliberation.cove import",
    "from Layer4_Analysis.safety.guard import": "from Layer4_Analysis.safety.guard import",
    "from Layer4_Analysis.deliberation.red_team import": "from Layer4_Analysis.deliberation.red_team import",
    "from Layer4_Analysis.hypothesis.mcts import": "from Layer4_Analysis.hypothesis.mcts import",
    "from Layer4_Analysis.safety.safeguards import": "from Layer4_Analysis.safety.safeguards import",
    "from Layer4_Analysis.core.unified_pipeline import": "from Layer4_Analysis.core.unified_pipeline import",
    "from Layer4_Analysis.evidence.provenance import": "from Layer4_Analysis.evidence.provenance import",
    "from Layer4_Analysis.deliberation.debate_orchestrator import": "from Layer4_Analysis.deliberation.debate_orchestrator import",
    "from Layer4_Analysis.core.llm_client import": "from Layer4_Analysis.core.llm_client import",
}

count = 0
for root, dirs, files in os.walk(base):
    dirs[:] = [d for d in dirs if d != "__pycache__" and d != ".git" and d != "node_modules"]
    for fn in files:
        if not fn.endswith(".py"):
            continue
        path = os.path.join(root, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue
        new = content
        for old, rep in mappings.items():
            new = new.replace(old, rep)
        if new != content:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new)
            count += 1
            print(f"Fixed: {os.path.relpath(path, base)}")

print(f"\nTotal: {count} files fixed")
