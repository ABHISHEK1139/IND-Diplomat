# Public Repo Map

## Source Module Breakdown

### Entry Points

| File | Lines | Role |
|---|---|---|
| `run.py` | 445 | Enhanced CLI entry point — Ollama pre-check, structured logging, full briefing output |
| `project_root.py` | ~100 | Single source of truth for all paths |
| `config.py` / `core.py` | shims | Compatibility shims routing to `Core.*` |

### Config/

Runtime configuration, pipeline setup, path conventions, thresholds, and runtime clock.

Key files: `config.py` (settings), `pipeline.py` (pipeline init + `run_query()`), `thresholds.py`, `runtime_clock.py`

### Core/

Shared infrastructure used across all layers:

| Submodule | Contents |
|---|---|
| `analysis/` | Evidence weighting |
| `case_management/` | Case lifecycle tracking |
| `database/` | SQLite persistence layer |
| `economic/` | Economic reasoner |
| `evidence/` | Corroboration engine |
| `evidence_db/` | Evidence database |
| `intelligence/` | MoltBot adapter, Priority Intelligence Requirements (PIR), Collection Plans, Belief Gaps |
| `investigation/` | Gap detection, investigation planning |
| `legal/` | Legal reasoner, treaty validation (26 files) |
| `orchestrator/` | Pipeline runtime, routing (22 files) |
| `signals/` | Signal ontology + normalizer |
| `verification/` | Claim corroboration engine |
| `wrappers.py` | 23KB of shared wrappers |

### Layer1_Collection/

Sensor data collection:
- `observation.py` (17KB) — Observation data model
- `moltbot_observation_extractor.py` (21KB) — MoltBot signal extraction
- `sensors/` — GDELT sensor, CAMEO mapper, relevance filter (12 files)
- `api/` — MoltBot agent interface

### Layer1_Sensors/

Lightweight sensor wrappers:
- `osint_sensor.py` — OSINT data source
- `moltbot_sensor.py` — MoltBot integration
- `observation_factory.py` (8KB) — Standard observation creation

### Layer2_Knowledge/

Knowledge management (139 files):

| Submodule | Contents |
|---|---|
| `access_api/` | Retrieval interface, information value scoring |
| `assimilation/` | Evidence assimilation pipeline |
| `normalization/` | Entity/source/signal deduplication |
| `parsing/` | Document chunking, classification |
| `signal_extraction/` | Claim + signal extraction (18 files) |
| `legal_signal_extractor/` | Legal signal dictionary + extraction |
| `sources/` | GDELT translator, event ingestors |
| `storage/` | Vector store, multi-index, engram store |
| `translators/` | Event translators |
| `retrieval/` | RAG retrieval pipeline |

### Layer3_StateModel/

State construction and temporal reasoning (175 files):

**Key Source Files:**

| File | Lines | Role |
|---|---|---|
| `conflict_state_model.py` | 733 | Bayesian 5-state model with adaptive transition matrices |
| `belief_accumulator.py` | 583 | Evidence → Observation → Belief epistemic chain |
| `signal_projection.py` | 505 | State context → observed signals with temporal decay |
| `temporal_memory.py` | 595 | Trend intelligence engine (momentum, persistence, spike) |
| `signal_registry.py` | 451 | Unified signal ontology with canonical names and aliases |
| `evidence_support.py` | 245 | Document-level evidence support scoring |
| `strategic_constraints.py` | 148 | Strategic constraint analysis |
| `causal_signal_mapper.py` | 155 | Signal-to-cause mapping |

**Submodules:**

| Submodule | Contents |
|---|---|
| `providers/` | **15+ data providers**: SIPRI, ATOP, V-Dem, OFAC, GDELT, WorldBank, Comtrade, Lowy, UCDP, EEZ, Leaders, Ports, Sanctions + baseline/intent-capability models (44 files) |
| `binding/` | Evidence binding, evidence graph |
| `construction/` | Country and relationship state builders |
| `credibility/` | Source weighting, contradiction detection |
| `reliability/` | Signal belief model |
| `scoring/` | Confidence calculator |
| `temporal/` | Timeline, escalation sync, precursor monitor (22 files) |
| `validation/` | Contradiction, freshness, consistency checks |
| `schemas/` | State context schema definitions |
| `interface/` | `state_provider.py` — main entry point |

### Layer4_Analysis/

Council of Ministers + reasoning (234 files):

**Key Source Files:**

| File | Lines | Role |
|---|---|---|
| `coordinator.py` | 2646 | The King — 8-stage reasoning pipeline |
| `conflict_state.py` | ~530 | Conflict state for analysis |
| `curiosity_controller.py` | ~540 | Drives investigation when gaps detected |
| `epistemic_needs.py` | ~460 | Determines information requirements |
| `counterfactual_engine.py` | ~150 | "What if" scenario testing |
| `groupthink_detector.py` | ~125 | Consensus challenge detection |
| `domain_fusion.py` | ~235 | Cross-domain signal fusion |
| `escalation_index.py` | ~220 | Composite escalation scoring |
| `war_index.py` | ~140 | War probability index |
| `gap_engine.py` | ~270 | Evidence gap identification |

**Submodules:**

| Submodule | Key Files |
|---|---|
| `ministers/` | 7 ministers: `security.py`, `diplomatic.py`, `economic.py`, `domestic.py`, `alliance.py`, `strategy.py`, `contrarian.py` + `base.py` (33KB base class) |
| `deliberation/` | `cove.py` (33KB), `crag.py` (14KB), `red_team.py` (18KB), `debate_orchestrator.py` (20KB) |
| `hypothesis/` | `mcts.py` (11KB), `causal.py` (9KB), `perspective_agent.py` (27KB), `hypothesis_expander.py` (11KB) |
| `decision/` | Confidence calculator, early warning, refusal engine (16 files) |
| `evidence/` | Evidence tracker, fuzzy state, signal ontology (20 files) |
| `investigation/` | Investigation controller, knowledge sufficiency (22 files) |
| `intake/` | Question scope, epistemic readiness (10 files) |
| `pipeline/` | Output builder, synthesis engine, withheld recollection (12 files) |
| `safety/` | Guardrails (6 files) |
| `support_models/` | Baseline + intent-capability models (12 files) |
| `verifier/` | Grounding verifier, claim support (8 files) |

### Layer5_Judgment/

Assessment gate — deterministic judgment authority:
- `assessment_gate.py` (582 lines) — 5 rules: critical PIRs, capability coverage, stale military, confidence floor, trend escalation
- `assessment_record.py` (15KB) — Structured assessment record
- `report_formatter.py` (44KB) — Report formatting engine

### Layer5_Reporting/

Intelligence report generation:
- `intelligence_report.py` (15KB) — IAR-format report generator

### Layer5_Trajectory/

Trajectory analysis and early warning:
- `trajectory_model.py` (15KB) — Forward state projection
- `acceleration_detector.py` (8KB) — Escalation acceleration detection
- `black_swan_detector.py` (9KB) — 3-channel discontinuity detection (spike severity, velocity, systemic cascade)
- `narrative_index.py` (6KB) — Event narrative tracking
- `gkg_ingest.py` (9KB) — GDELT GKG theme ingestion
- `trajectory_report.py` (6KB) — Trajectory report generation

### Layer6_Presentation/

Briefing and view modules (24 files):
- `briefing_builder.py` (10KB) — Full multi-section intelligence briefing
- `report_builder.py` (21KB) — Comprehensive report assembly
- `bias_detector.py` (6KB) — Analytical bias detection
- `confidence_explainer.py` (3KB) — Confidence framing
- `failure_modes.py` (6KB) — System failure mode documentation
- 5 view modules: `evidence_view.py`, `debate_view.py`, `legal_view.py` (8KB), `gap_view.py`, `redteam_view.py`

### Layer6_Backtesting/

Crisis replay and calibration (18 files):
- `replay_engine.py` (649 lines) — Day-by-day Bayesian conflict state simulation
- `scenario_registry.py` (18KB) — Historical crisis definitions (Ukraine 2022, Crimea 2014, Iran-US 2019, Karabakh 2020)
- `multiclass_metrics.py` (25KB) — Multi-state evaluation metrics
- `calibration_metrics.py` (7KB) — Brier scores, accuracy metrics
- `evaluator.py` (14KB) — Experiment orchestration
- `evaluation_report.py` (15KB) — Report generation
- `exporter.py` (15KB) — Results export
- `crisis_registry.py` (5KB) — Crisis metadata

### Layer6_Learning/

Confidence recalibration and self-improvement (14 files):
- `auto_adjuster.py` (11KB) — Automatic threshold tuning
- `calibration_engine.py` (5KB) — Confidence recalibration
- `forecast_archive.py` (6KB) — Historical forecast storage
- `forecast_resolution.py` (7KB) — Forecast outcome tracking
- `confidence_recalibrator.py` (2KB) — Confidence adjustment
- `learning_report.py` (6KB) — Learning cycle report

### Layer7_GlobalModel/

Multi-theater geopolitical analysis (12 files):
- `interdependence_matrix.py` (410 lines) — 150+ expert-defined coupling weights spanning 10 geopolitical regions
- `contagion_engine.py` (5KB) — Escalation propagation model
- `cross_theater_forecaster.py` (7KB) — Multi-theater risk projection
- `global_state.py` (12KB) — Unified global view
- `global_report.py` (6KB) — Global analysis report

### Supporting Modules

| Module | Role |
|---|---|
| `analysis/` | Experimental validation framework (backtester, actor network, experiments) |
| `Frontend/` | Web dashboard (HTML/JS/CSS + `server.py`) |
| `API/` | FastAPI surface (`main.py`) |
| `schemas/` | Claim, legal signal, state schemas |
| `contracts/` | Observation contract |
| `system_bootstrap/` | Environment setup + `requirements.txt` |
| `SystemGuardian/` | Operational health monitoring |
| `Utils/` | Shared utilities (cache, logging, APIs) — 44 files |

## What To Keep Out Of A Public Pack

- `data/` — Runtime data (Chroma DB, engrams, indexes) — 10,686 files
- `SAVED DATA/` — Source datasets (SIPRI, ATOP, V-Dem, WorldBank, OFAC) — 588 files
- `reports/` — Generated intelligence briefings
- `assessments/` — Council assessment JSONs
- `runtime/` — Continuous monitor state + alerts
- `knowledge/` — Event index archives
- `legal_memory/` — Treaty metadata + docs
- `logs/` — Application logs
- Local databases (`*.db`, `*.sqlite3`)
- Vector indexes, Chroma stores, caches, embeddings
- `__pycache__/`

## Recommended Public Packaging View

```text
IND-Diplomat/
  README.md
  docs/
  examples/
  Config/
  Core/
  Layer1_Collection/
  Layer1_Sensors/
  Layer2_Knowledge/
  Layer3_StateModel/
  Layer4_Analysis/
  Layer5_Judgment/
  Layer5_Reporting/
  Layer5_Trajectory/
  Layer6_Backtesting/
  Layer6_Learning/
  Layer6_Presentation/
  Layer7_GlobalModel/
  Frontend/
  API/
  analysis/
  schemas/
  contracts/
  system_bootstrap/
  .env.example
```

## Documentation Positioning

For a recruiter or collaborator, the public docs should center on:

- The Bayesian conflict-state model and epistemic reasoning chain
- The 8-stage council pipeline with explicit gates
- Evidence-based assessment with deterministic judgment rules
- Experiments, explainability, and validation with Brier scores
- Safety architecture (refusal, HITL, groupthink detection)
- Selected sample outputs demonstrating multi-signal reasoning
