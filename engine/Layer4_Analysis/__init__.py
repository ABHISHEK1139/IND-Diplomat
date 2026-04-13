"""
Layer4 Analysis — Council of Ministers
=======================================
This package contains the 9-phase analysis pipeline:
  core/          — Coordinator, LLM client, council session
  intake/        — Question scope checker, analyst input builder
  hypothesis/    — MCTS, causal reasoning
  evidence/      — Evidence tracker, gap analyzer
  deliberation/  — Red team, debate orchestrator, perspective agents
  decision/      — Refusal engine, refiner, optimizer
  investigation/ — Investigation controller
  safety/        — LlamaGuard, safeguards
  interfaces/    — External API adapters
"""

# Resilient imports — keeps working even if some deps are missing.
# New Modular Architecture Exports
try:
    from engine.Layer4_Analysis.coordinator import CouncilCoordinator
    from engine.Layer4_Analysis.council_session import CouncilSession
    from engine.Layer4_Analysis.report_generator import generate_assessment
except Exception as e:
    # Fallback or logging if needed
    CouncilCoordinator = None  # type: ignore
    CouncilSession = None     # type: ignore
    generate_assessment = None # type: ignore

__all__ = [
    "CouncilCoordinator", 
    "CouncilSession", 
    "generate_assessment"
]
