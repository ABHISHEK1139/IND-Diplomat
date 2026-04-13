# Repo Map

This is a rough guide to what lives where in the codebase. Not exhaustive, but enough to orient you — whether you're picking up the project for the first time or trying to remember which layer handles what.

---

## Source Module Breakdown

### Entry Points

| File | Lines | Role |
|---|---|---|
| `run.py` | 445 | Main CLI entry — checks Ollama is running, sets up logging, runs the full briefing |
| `project_root.py` | ~100 | All path definitions live here. Don't hardcode paths elsewhere |
| `config.py` / `core.py` | shims | Compatibility shims that route calls to `Core.*` — nothing substantive here |

---

### Config/

Handles runtime settings, pipeline initialization, path conventions, thresholds, and the runtime clock.

Main files: `config.py` (app settings), `pipeline.py` (pipeline setup + `run_query()`), `thresholds.py`, `runtime_clock.py`

---

### Core/

The shared infrastructure everything else depends on. If something is used across multiple layers, it probably lives here.

| Submodule | What's in it |
|---|---|
| `analysis/` | Evidence weighting |
| `case_management/` | Case lifecycle tracking |
| `database/` | SQLite persistence |
| `economic/` | Economic reasoning |
| `evidence/` | Corroboration engine |
| `evidence_db/` | Evidence storage |
| `intelligence/` | MoltBot adapter, PIR handling, collection plans, belief gap detection |
| `investigation/` | Gap detection and investigation planning |
| `legal/` | Legal reasoning and treaty validation (26 files) |
| `orchestrator/` | Pipeline runtime and routing (22 files) |
| `signals/` | Signal ontology and normalization |
| `verification/` | Claim corroboration |
| `wrappers.py` | 23KB of shared wrappers used across the system |

---

### Layer1\_Collection/

Pulls in sensor data:

- `observation.py` (17KB) — data model for observations
- `moltbot_observation_extractor.py` (21KB) — extracts signals from MoltBot
- `sensors/` — GDELT sensor, CAMEO mapper, relevance filter (12 files)
- `api/` — MoltBot agent interface

---

### Layer1\_Sensors/

Lightweight wrappers around data sources:

- `osint_sensor.py` — OSINT data source
- `moltbot_sensor.py` — MoltBot integration
- `observation_factory.py` (8KB) — creates standardized observations

---

### Layer2\_Knowledge/

Knowledge management — 139 files total.

| Submodule | What's in it |
|---|---|
| `access_api/` | Retrieval interface + information value scoring |
| `assimilation/` | Evidence assimilation pipeline |
| `normalization/` | Deduplication for entities, sources, signals |
| `parsing/` | Document chunking and classification |
| `signal_extraction/` | Claim and signal extraction (18 files) |
| `legal_signal_extractor/` | Legal signal dictionary and extraction |
| `sources/` | GDELT translator, event ingestors |
| `storage/` | Vector store, multi-index, engram store |
| `translators/` | Event translators |
| `retrieval/` | RAG retrieval pipeline |

---

### Layer3\_StateModel/

State construction and temporal reasoning — 175 files.

**Key files:**

| File | Lines | What it does |
|---|---|---|
| `conflict_state_model.py` | 733 | Bayesian 5-state conflict model with adaptive transition matrices |
| `belief_accumulator.py` | 583 | Builds the Evidence → Observation → Belief chain |
| `signal_projection.py` | 505 | Maps state context to observable signals; includes temporal decay |
| `temporal_memory.py` | 595 | Tracks trends — momentum, persistence, spike detection |
| `signal_registry.py` | 451 | Unified signal ontology with canonical names and aliases |
| `evidence_support.py` | 245 | Scores evidence support at document level |
| `strategic_constraints.py` | 148 | Strategic constraint analysis |
| `causal_signal_mapper.py` | 155 | Maps signals back to their causes |

**Submodules:**

| Submodule | What's in it |
|---|---|
| `providers/` | 15+ data providers: SIPRI, ATOP, V-Dem, OFAC, GDELT, WorldBank, Comtrade, Lowy, UCDP, EEZ, Leaders, Ports, Sanctions + baseline/intent-capability models (44 files) |
| `binding/` | Evidence binding and evidence graph |
| `construction/` | Country and relationship state builders |
| `credibility/` | Source weighting and contradiction detection |
| `reliability/` | Signal belief model |
| `scoring/` | Confidence calculator |
| `temporal/` | Timeline, escalation sync, precursor monitor (22 files) |
| `validation/` | Checks for contradictions, staleness, consistency |
| `schemas/` | State context schema definitions |
| `interface/` | `state_provider.py` — main entry point for this layer |

---

### Layer4\_Analysis/

The reasoning core — Council of Ministers pipeline, 234 files.

**Key files:**

| File | Lines | What it does |
|---|---|---|
| `coordinator.py` | 2646 | Drives the 8-stage reasoning pipeline — the main orchestrator |
| `conflict_state.py` | ~530 | Conflict state representation used during analysis |
| `curiosity_controller.py` | ~540 | Triggers investigation when knowledge gaps are found |
| `epistemic_needs.py` | ~460 | Works out what information is still missing |
| `counterfactual_engine.py` | ~150 | Runs "what if" scenarios |
| `groupthink_detector.py` | ~125 | Checks if the system is too agreeable with itself |
| `domain_fusion.py` | ~235 | Fuses signals across different domains |
| `escalation_index.py` | ~220 | Composite escalation scoring |
| `war_index.py` | ~140 | War probability index |
| `gap_engine.py` | ~270 | Identifies evidence gaps |

**Submodules:**

| Submodule | Key files |
|---|---|
| `ministers/` | 7 ministers: `security.py`, `diplomatic.py`, `economic.py`, `domestic.py`, `alliance.py`, `strategy.py`, `contrarian.py` + `base.py` (33KB base class) |
| `deliberation/` | `cove.py` (33KB), `crag.py` (14KB), `red_team.py` (18KB), `debate_orchestrator.py` (20KB) |
| `hypothesis/` | `mcts.py` (11KB), `causal.py` (9KB), `perspective_agent.py` (27KB), `hypothesis_expander.py` (11KB) |
| `decision/` | Confidence calculator, early warning, refusal engine (16 files) |
| `evidence/` | Evidence tracker, fuzzy state, signal ontology (20 files) |
| `investigation/` | Investigation controller, knowledge sufficiency (22 files) |
| `intake/` | Question scoping, epistemic readiness (10 files) |
| `pipeline/` | Output builder, synthesis engine, withheld recollection (12 files) |
| `safety/` | Guardrails (6 files) |
| `support_models/` | Baseline + intent-capability models (12 files) |
| `verifier/` | Grounding verifier, claim support (8 files) |

---

### Layer5\_Judgment/

This is where the system makes actual decisions — not scores, decisions. Rule-based, not probabilistic:

- `assessment_gate.py` (582 lines) — 5 hard rules: critical PIRs, capability coverage, stale military data, confidence floor, trend escalation
- `assessment_record.py` (15KB) — structured record of each assessment
- `report_formatter.py` (44KB) — formats the final report

---

### Layer5\_Reporting/

Generates the intelligence reports:

- `intelligence_report.py` (15KB) — IAR-format report generator

---

### Layer5\_Trajectory/

Forward-looking analysis — where is this heading:

- `trajectory_model.py` (15KB) — projects future state from current signals
- `acceleration_detector.py` (8KB) — catches when escalation is speeding up, not just high
- `black_swan_detector.py` (9KB) — 3-channel discontinuity detection: spike severity, velocity, systemic cascade
- `narrative_index.py` (6KB) — tracks how event narratives shift over time
- `gkg_ingest.py` (9KB) — GDELT GKG theme ingestion
- `trajectory_report.py` (6KB) — trajectory report output

---

### Layer6\_Presentation/

Briefing and view modules — 24 files:

- `briefing_builder.py` (10KB) — builds the full multi-section intelligence briefing
- `report_builder.py` (21KB) — assembles comprehensive reports
- `bias_detector.py` (6KB) — flags analytical bias
- `confidence_explainer.py` (3KB) — explains how confidence was arrived at
- `failure_modes.py` (6KB) — documents known failure modes of the system
- 5 view modules: `evidence_view.py`, `debate_view.py`, `legal_view.py` (8KB), `gap_view.py`, `redteam_view.py`

---

### Layer6\_Backtesting/

Replays historical crises to check calibration — 18 files:

- `replay_engine.py` (649 lines) — day-by-day Bayesian conflict state simulation
- `scenario_registry.py` (18KB) — crisis definitions: Ukraine 2022, Crimea 2014, Iran-US 2019, Karabakh 2020
- `multiclass_metrics.py` (25KB) — multi-state evaluation metrics
- `calibration_metrics.py` (7KB) — Brier scores and accuracy metrics
- `evaluator.py` (14KB) — runs experiments
- `evaluation_report.py` (15KB) — report generation
- `exporter.py` (15KB) — exports results
- `crisis_registry.py` (5KB) — crisis metadata

---

### Layer6\_Learning/

Self-improvement loop — recalibrates confidence over time, 14 files:

- `auto_adjuster.py` (11KB) — tunes thresholds automatically based on outcomes
- `calibration_engine.py` (5KB) — recalibrates confidence estimates
- `forecast_archive.py` (6KB) — stores historical forecasts
- `forecast_resolution.py` (7KB) — tracks how forecasts actually resolved
- `confidence_recalibrator.py` (2KB) — adjusts confidence
- `learning_report.py` (6KB) — learning cycle report

---

### Layer7\_GlobalModel/

Multi-theater geopolitical analysis — 12 files:

- `interdependence_matrix.py` (410 lines) — 150+ expert-defined coupling weights across 10 geopolitical regions
- `contagion_engine.py` (5KB) — models how escalation spreads between theaters
- `cross_theater_forecaster.py` (7KB) — projects risk across multiple theaters simultaneously
- `global_state.py` (12KB) — unified global view
- `global_report.py` (6KB) — global analysis report

---

### Supporting Modules

| Module | Role |
|---|---|
| `analysis/` | Experimental validation (backtester, actor network, experiments) |
| `Frontend/` | Web dashboard (HTML/JS/CSS + `server.py`) |
| `API/` | FastAPI surface (`main.py`) |
| `schemas/` | Claim, legal signal, state schemas |
| `contracts/` | Observation contract |
| `system_bootstrap/` | Environment setup + `requirements.txt` |
| `SystemGuardian/` | Operational health monitoring |
| `Utils/` | Shared utilities — caching, logging, API helpers (44 files) |

---

## What To Keep Out Of A Public Release

Don't include any of the following in a public pack — most of this is either runtime state, source datasets, or generated output that has no place in the repo:

- `data/` — runtime data: Chroma DB, engrams, indexes (10,686 files)
- `SAVED DATA/` — source datasets: SIPRI, ATOP, V-Dem, WorldBank, OFAC (588 files)
- `reports/` — generated intelligence briefings
- `assessments/` — council assessment JSONs
- `runtime/` — continuous monitor state and alerts
- `knowledge/` — event index archives
- `legal_memory/` — treaty metadata and docs
- `logs/` — application logs
- Local databases (`*.db`, `*.sqlite3`)
- Vector indexes, Chroma stores, caches, embeddings
- `__pycache__/`

---

## Recommended Public Structure


## Recommended Public Packaging View

```text
IND-Diplomat/
  README.md
  docs/
  examples/
  Config/
  Core/
  engine/Layer1_Collection/
  engine/Layer1_Sensors/
  engine/Layer2_Knowledge/
  engine/Layer3_StateModel/
  engine/Layer4_Analysis/
  engine/Layer5_Judgment/
  engine/Layer5_Reporting/
  engine/Layer5_Trajectory/
  engine/Layer6_Backtesting/
  engine/Layer6_Learning/
  engine/Layer6_Presentation/
  engine/Layer7_GlobalModel/
  Frontend/
  API/
  analysis/
  schemas/
  contracts/
  system_bootstrap/
  .env.example
```


---

## What's Worth Looking At

If you're going through the docs (especially for the first time), some parts are way more important than others. These are the ones you should focus on:

- **The conflict-state model** (`conflict_state_model.py`)  
  This is the core of the system. It’s a Bayesian 5-state model with adaptive transitions, and it basically defines how everything thinks and evolves. If you’re trying to understand the system, start here.

- **The council pipeline** (`coordinator.py`, 2646 lines)  
  This is where most of the reasoning happens. It runs through 8 structured stages with clear decision gates. It’s not just calling an LLM — there’s real control and flow behind how conclusions are formed.

- **Layer5_Judgment**  
  This is an important part that many systems skip. The final decision here is rule-based and deterministic. Evidence goes in, strict rules decide the outcome — no vague reasoning or last-minute guesswork.

- **The backtesting layer**  
  This is what checks if the system actually works. It uses real historical crises and evaluates performance using Brier scores. This is what separates a system that sounds good from one that is actually reliable.

- **Groupthink detection and red-teaming**  
  The system actively questions itself. `groupthink_detector.py` and `red_team.py` work together to catch weak reasoning and challenge conclusions instead of blindly agreeing.

- **Examples (`examples/`)**  
  If you’re new, start here. These show the full system running end-to-end and make it much easier to understand what’s going on.
