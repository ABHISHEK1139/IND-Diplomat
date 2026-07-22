# Changelog

## v3.0.0 (2026-07-06) — DIP 3.0 Enterprise Architecture Final
The system has been completely overhauled from a procedural heuristic script into an enterprise-grade, autonomous, multi-agent AI platform.

### Added
- **LangGraph Orchestrator (Phase 1/2):** Replaced procedural state tracking with a durable `StateGraph`.
- **Neo4j + Docling World Model (Phase 3):** Replaced naive string matching with an IBM Docling parsed Knowledge Graph.
- **DSPy Reasoning Council (Phase 4):** Replaced static prompt strings with self-optimizing `dspy.Signature` peer-review debates.
- **Mesa Simulation (Phase 5):** Added Agent-Based Modeling to simulate macroeconomic and geopolitical ripple effects.
- **Analyst Workspace (Phase 6):** Refactored output modularity for the intelligence dossier.
- **DeepEval Learning Loop (Phase 7):** Automated LLM judging for hallucinations and relevancy using RAGAS/DeepEval.
- **Yjs Collaboration (Phase 8):** Real-time CRDT WebSocket engine for multiplayer document editing.
- **Pluggy SDK Ecosystem (Phase 9):** Fully decoupled architecture allowing 3rd-party plugins.
- **Enterprise Gov/Sec (Phase 10):** Keycloak SSO, Casbin RBAC, OpenTelemetry Auditing, and LiteLLM Routing.
- **Autonomous Agent (Phase 11):** Closed-loop LangGraph agent that searches academic literature independently.
- **Digital Twin (Phase 12):** Kafka/Redis stream processing for 24x7 anomaly detection and alerting.

### Removed
- Legacy naive string extraction heuristics.
- Hardcoded analyst prompts (migrated to DSPy).


## v2.1.0 (2026-07-03) — DIP_8 Parity Upgrade

### Added
- **Assessment Gate (Layer 5):** Deterministic WITHHOLD/APPROVE with 5 rules, ported from DIP_8
- **Assessment Record:** Immutable JSONL audit log for every assessment
- **CSIS Framework:** ACH, Red Team, Scenario Planning, Devil's Advocacy
- **Prophet Forecaster:** Time-series trajectory with Prophet + numpy fallback
- **Online Drift Detector:** River + numpy zscore anomaly detection
- **ACH Hypothesis Tracker:** pgmpy Bayesian multi-hypothesis tracking
- **ChromaDB Vector Store:** Semantic search with sentence-transformers embeddings
- **Dynamic Source Reliability:** PyMC Bayesian Beta updating per source
- **Legal Treaty RAG:** Haystack/ChromaDB treaty-aware signal analysis
- **Signal-Legal Mapper:** Maps geopolitical signals to treaty articles (UN Charter, NPT, UNCLOS, Vienna Convention, bilateral treaties)
- **Confidence Recalibrator:** sklearn calibration_curve + Brier score
- **Self-Model Dashboard:** Tracks capabilities, uncertainties, minister performance
- **Safety Enforcer:** Runtime SafetyBoundary checks on all outputs
- **Experiment Gate:** No change without experiment evidence
- **Mesa Wargame Simulation:** Agent-based Monte Carlo strategic simulation
- **Cross-Theater Forecaster:** NetworkX contagion propagation
- **Presentation Views:** Debate, evidence, gap, legal, red team views
- **HTML Report Generator:** Standalone intelligence assessment reports
- **Minister Curriculum:** Per-minister targeted improvement plans
- **System Guardian:** Health monitoring + auto-repair
- **LangGraph Runtime:** Real durable execution with checkpointing
- **API Endpoints:** `/api/self-model`, `/api/v3/jobs/{id}/stix2`
- **OSS Adapters:** LangGraph, Prefect, STIX2, NetworkX, OpenTelemetry, MLflow
- **Frontend:** Explainable AI page
- **CI/CD:** GitHub Actions pipeline

### Changed
- All `datetime.utcnow()` → `datetime.now(timezone.utc)`
- All `.dict()` → `.model_dump()` (Pydantic V2)
- All `asyncio.get_event_loop()` → `asyncio.run()`
- Assessment Gate wired into unified_pipeline.execute()
- Minister base: heuristic fallback with `FORCE_MINISTER_HEURISTIC=1`

### Fixed
- DDGS context manager for clean transport closing
- SystemGuardian import chain unified

### Tests
- 84 tests passing (up from 26)
- 1 external warning (litellm)

## v2.0.0 — Initial Release
- 7-layer pipeline architecture
- 7-minister council with LLM + heuristic fallback
- Fuzzy SRE (domain fusion, escalation, triggers, legal firewall)
- HeadOfStatePipelineGraph + AssessmentBlackboard
- Async analyst API + WebSocket streaming
- Docker multi-service deployment
- OSS adapter registry
