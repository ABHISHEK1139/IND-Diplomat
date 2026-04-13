# PROJECT BLUEPRINT: FORENSIC RECONSTRUCTION
## Repository-Derived Architectural Audit (No External Docs)

**Audit Date**: 2026-02-23 UTC  
**Audit Basis**: Static + runtime execution from repository source only  
**Repository Root**: `DIP_3_0/`  
**Python Files Audited**: 471  
**Reachable From Audited Entrypaths**: 88  
**Unreachable/Detached Under Audited Entrypaths**: 365

---

## 1. GLOBAL SYSTEM DESCRIPTION

The repository behaves as a **hybrid geopolitical decision-support platform with multiple overlapping generations of pipeline code** rather than a single clean executable system.

Operationally, there are two concurrently present products in the same codebase:

1. A **Layer-4 council reasoning engine** (`Layer4_Analysis/coordinator.py`) consuming a Layer-3 `StateContext`, producing threat/risk narrative, confidence, and safety-gated output.
2. A **profile/tension service API** (`analysis_api/*`) that exposes country profile and timeline analytics from `CountryStateBuilder`.

The currently active council logic is computationally:

- L3 numeric state vectors are built from provider signals.
- A reliability layer converts numeric telemetry to fuzzy `SignalBelief` values (soft evidence).
- Ministers classify allowed signal ontology tokens via constrained LLM JSON outputs (with deterministic fallback).
- Coordinator scores hypotheses against graded belief support.
- A phase state machine performs conflict detection, red-team challenge, investigation loop, deterministic verification, and safety refusal/HITL checks.

Observed behavior under direct execution in this repo:

- Default programmatic path (`Config.pipeline.run_query`) is often blocked before council execution by scope/readiness gates.
- API v4 module imports successfully but has unresolved runtime symbols in endpoint bodies (`unified_pipeline`, `safeguard`, `provenance`) causing failure if those paths are hit.
- CLI path (`run_council.py`) seeds a dict instead of `StateContext`, causing runtime failure in coordinator when reading `state_context.evidence`.

Conclusion: the repository is architecturally rich but execution is **fragmented across active and legacy paths**, with the council engine itself functional when invoked directly with valid `StateContext`.

---

## 2. LAYER MAPPING

### Real Layer Stack (as implemented)

```text
User / Automation
  -> Entry Surface
     -> Intake Safety / Scope
        -> Layer-3 State Construction
           -> Reliability Interpretation (soft beliefs)
              -> Layer-4 Council Deliberation
                 -> Conflict / Red Team / Investigation
                    -> Verification
                       -> Safety Review (refusal + HITL)
                          -> Structured Output
```

### Folder-Level Layer Footprint

- `<root>`: 26 files, 3 reachable from audited entrypaths
- `AGENT_INTERFACE`: 3 files, 0 reachable from audited entrypaths
- `analysis_api`: 4 files, 3 reachable from audited entrypaths
- `API`: 4 files, 3 reachable from audited entrypaths
- `Config`: 4 files, 3 reachable from audited entrypaths
- `contracts`: 2 files, 0 reachable from audited entrypaths
- `Core`: 40 files, 3 reachable from audited entrypaths
- `Docs`: 1 files, 0 reachable from audited entrypaths
- `Frontend`: 1 files, 1 reachable from audited entrypaths
- `ind_diplomat`: 17 files, 0 reachable from audited entrypaths
- `LAYER1_COLLECTION`: 39 files, 20 reachable from audited entrypaths
- `layer2_extraction`: 2 files, 0 reachable from audited entrypaths
- `Layer2_Knowledge`: 66 files, 4 reachable from audited entrypaths
- `Layer3_Reasoning`: 6 files, 0 reachable from audited entrypaths
- `Layer3_StateModel`: 67 files, 26 reachable from audited entrypaths
- `Layer4_Analysis`: 59 files, 11 reachable from audited entrypaths
- `layer4_reasoning`: 8 files, 0 reachable from audited entrypaths
- `Layer5`: 2 files, 0 reachable from audited entrypaths
- `moltbot`: 2 files, 0 reachable from audited entrypaths
- `schemas`: 4 files, 0 reachable from audited entrypaths
- `Scripts`: 37 files, 4 reachable from audited entrypaths
- `Tests`: 55 files, 1 reachable from audited entrypaths
- `Utils`: 22 files, 6 reachable from audited entrypaths

### Active vs Legacy Paths

- Active council orchestration: `Layer4_Analysis/core/unified_pipeline.py` + `Layer4_Analysis/coordinator.py`.
- Parallel/legacy orchestration families still present:
  - `Core/orchestrator/*` (Layer1-2-3 legacy pipeline family)
  - `Layer4_Analysis/layer4_unified_pipeline.py` (alternate wrapper)
  - `analysis_api/*` (separate API surface)
- Result: multiple orchestration strata coexist, not a single canonical executable path.

---

## 3. ENTRY POINTS

### Enumerated Execution Starts

- `API/main.py`
  - `query()` path: `run_query()` -> `Layer4_Analysis.core.unified_pipeline.UnifiedPipeline.execute()` -> returns API JSON payload.
  - `query_v2()` path: intended `unified_pipeline.execute(...)` path, but symbol `unified_pipeline` is unresolved in module scope.
  - `query_stream()` path: scope gate + readiness gate + direct `llm_client.stream(...)`.
  - output: HTTP JSON/stream responses.
- `analysis_api/main.py`
  - `app` + router from `analysis_api/endpoints.py`.
  - output: `/api/v1/*` profile/tension/timeline JSON.
- `Config/pipeline.py`
  - `run_query()` (programmatic entry) -> `UnifiedPipeline.execute()` -> returns compatibility dict.
- `run_council.py`
  - CLI main -> `_seed_state_context()` -> `Coordinator.process_query()` -> stdout/JSON.
- `run_verify.py`
  - test-suite orchestrator -> subprocess test scripts -> `Tests/verification_final.txt`.
- `Scripts/cli.py`
  - Typer CLI (`ingest`, `persist`, `graph-load`, `search`, etc.) for ingestion/KB operations.
- `Scripts/data_feeder.py`
  - async feeder runner intended to call ingestion scheduler (import path currently mismatched: `feeder.scheduler`).
- `Scripts/run_evaluation.py`
  - scenario runner for `evaluation_scenarios/*.json`.
- `Tests/run_real_council.py`
  - manual async execution harness for real coordinator path.
- Background/daemon path
  - `LAYER1_COLLECTION/ingestion/feeder/scheduler.py::start_daemon()` -> periodic `run_all_sources()` with sleep loop.

### Execution Order Inference

Primary intended end-to-end order (programmatic/API):

1. `API.main` endpoint -> `Config.pipeline.run_query`
2. `Layer4_Analysis.core.unified_pipeline.UnifiedPipeline.execute`
3. scope gate (`check_question_scope`) and readiness gate (`build_analyst_input` / `evaluate_analysis_readiness`)
4. `Layer3_StateModel.interface.state_provider.build_initial_state`
5. `Layer4_Analysis.coordinator.CouncilCoordinator.process_query`
6. response serialization back to caller

Observed deviations:

- `/v2/query` references undefined `unified_pipeline` symbol in `API/main.py`.
- `/query` references undefined `safeguard` and `provenance` symbols.
- `run_council.py` passes a dict where `StateContext` object is expected.

---

## 4. RUNTIME EXECUTION TRACE

### Trace Query (requested): `"Assess likelihood of conflict"`

#### Trace A: Actual `Config.pipeline.run_query()` behavior for exact query

1. `Config.pipeline.run_query(query=...)` initializes layers.
2. Delegates to `Layer4_Analysis.core.unified_pipeline.UnifiedPipeline.execute`.
3. `check_question_scope("Assess likelihood of conflict")` runs.
4. Scope classification returns blocked/ambiguous (query not matching allowed explanatory patterns and conflict keyword is not in risk keyword list).
5. Pipeline returns early:
   - `layer4_allowed=False`
   - `trace_id='scope_blocked'`
   - answer is defer message, confidence `0.0`.
6. Council phases are never entered.

#### Trace B: Direct council execution with valid state object (bypass readiness blocker)

1. `state = build_initial_state("What factors indicate conflict ...", country_code='IND')`
2. `CouncilCoordinator.process_query(query, state_context=state)`
3. Phase transition sequence observed:
   - `INITIAL_DELIBERATION`
   - `INVESTIGATION`
   - `INITIAL_DELIBERATION`
   - `INVESTIGATION`
   - `VERIFICATION`
   - `SAFETY_REVIEW`
   - `FINALIZED`
4. During deliberation:
   - ministers produce predicted signals
   - `_evaluate_evidence` scores via soft beliefs (structural fuzzy support)
5. Investigation runs due missing/low-belief signals.
6. Verification score remained `0.0` in observed run.
7. Safety review returned refusal payload due black-swan/anomaly path.
8. Final response: refusal message, confidence `0.0`, no sources.

#### Trace C: CLI `run_council.py` observed failure

1. `run_council.py` seeds state as analyst-input dict.
2. Calls `Coordinator.process_query(..., state_context=dict)`.
3. Coordinator later accesses `session.state_context.evidence`.
4. Runtime error: `AttributeError: 'dict' object has no attribute 'evidence'`.

---

## 5. FILE-BY-FILE FORENSIC MAP

**FILE:** `__init__.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `AGENT_INTERFACE/__init__.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `AGENT_INTERFACE/moltbot_controller.py`
- **PURPOSE:** MoltBot Controller — The Operator Interface Brain
- **INPUT:** api_base, user_text, endpoint, payload, query, intent, profile, analysis, value
- **OUTPUT:** MoltBotController, Dict, str
- **CALLED BY:** Tests.test_comprehensive_audit, Tests.test_post_restructuring
- **CALLS:** AGENT_INTERFACE.question_parser
- **CRITICALITY:** unused

**FILE:** `AGENT_INTERFACE/question_parser.py`
- **PURPOSE:** Question Parser — Intent Classification
- **INPUT:** text
- **OUTPUT:** QuestionParser, Dict, list, str
- **CALLED BY:** AGENT_INTERFACE.moltbot_controller, Tests.test_comprehensive_audit, Tests.test_pipeline_status, Tests.test_post_restructuring
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `analysis_api/__init__.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `analysis_api/endpoints.py`
- **PURPOSE:** Analysis API Endpoints
- **INPUT:** country_code, request, dimension, limit
- **OUTPUT:** TensionResponse, TensionHistoryPoint, AnalysisRequest, AnalysisResponse, DimensionTimelinePoint, ConfidenceTimelinePoint
- **CALLED BY:** analysis_api.main
- **CALLS:** analysis_api.services
- **CRITICALITY:** core

**FILE:** `analysis_api/main.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** request, call_next
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** analysis_api.endpoints
- **CRITICALITY:** core

**FILE:** `analysis_api/services.py`
- **PURPOSE:** Analysis Engine - Core Intelligence Logic
- **INPUT:** country_code, date, analysis_type, dimension, limit, max_points, previous, current
- **OUTPUT:** AnalysisEngine, Dict, List
- **CALLED BY:** Tests.test_comprehensive_audit, Tests.test_post_restructuring, analysis_api.endpoints
- **CALLS:** Core.orchestrator.analysis_router, Layer3_StateModel.construction.country_state_builder, Layer3_StateModel.country_state_schema
- **CRITICALITY:** core

**FILE:** `API/__init__.py`
- **PURPOSE:** API Package - FastAPI endpoints and authentication.
- **INPUT:** name
- **OUTPUT:** APIRegistry, List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** API.auth, API.main, API.metrics, LAYER1_COLLECTION.app
- **CRITICALITY:** unused

**FILE:** `API/auth.py`
- **PURPOSE:** JWT Authentication for IND-Diplomat
- **INPUT:** token, password, plain_password, hashed_password, user, expires_delta, username, role, permission, pw
- **OUTPUT:** Role, User, JWTAuth, RBAC, Optional, str, bool, Dict
- **CALLED BY:** API, API.main, Tests.test_all_features
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `API/main.py`
- **PURPOSE:** IND-Diplomat API v4.0.0
- **INPUT:** app, api_key, bearer, permission, request, body, user, session_id, format, query, user_id, action
- **OUTPUT:** QueryRequest, TokenRequest, QueryResponse, HealthResponse, Optional
- **CALLED BY:** API, Scripts.test_api, Tests.test_all_features
- **CALLS:** API.auth, API.metrics, Config.config, Config.pipeline, Layer3_StateModel.construction.analysis_readiness, Layer4_Analysis.core.coordinator, Layer4_Analysis.core.llm_client, Layer4_Analysis.intake.question_scope_checker, Layer4_Analysis.safety.guard, Utils.audit, Utils.cache, Utils.logger, Utils.report_generator, Utils.session
- **CRITICALITY:** core

**FILE:** `API/metrics.py`
- **PURPOSE:** Prometheus Metrics for IND-Diplomat
- **INPUT:** collector, endpoint, method, status, latency, model, input_tokens, output_tokens, cache_type, hit, source, result_count
- **OUTPUT:** MetricsCollector, bool, bytes, str
- **CALLED BY:** API, API.main
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `check_db.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.database.models, Core.database.session
- **CRITICALITY:** unused

**FILE:** `check_dependencies.py`
- **PURPOSE:** Comprehensive Dependency & Software Availability Check
- **INPUT:** text, host, port, timeout, cmd, package_name, import_name, name
- **OUTPUT:** bool, Tuple
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** LAYER1_COLLECTION.api.moltbot_agent
- **CRITICALITY:** unused

**FILE:** `check_dependencies_simple.py`
- **PURPOSE:** Simplified Dependency & Software Availability Check
- **INPUT:** host, port, timeout, package_name
- **OUTPUT:** bool
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `check_ollama.py`
- **PURPOSE:** Check if Ollama is running
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `check_results.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Config/config.py`
- **PURPOSE:** IND-Diplomat Configuration
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** API.main, Layer3_StateModel.construction.country_state_builder, Layer4_Analysis.core.llm_client, Scripts.test_llm, test_comprehensive_system
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Config/esds_config.py`
- **PURPOSE:** Sovereign Scaling Configuration - ESDS Config
- **INPUT:** messages, config, model_override, environment, model_name, tokens, tee_profile, context
- **OUTPUT:** ModelProvider, ModelConfig, ESDSConfig, Dict, TEEConfig, ConfidentialComputing, str, Optional, bool, float, bytes
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Config/pipeline.py`
- **PURPOSE:** IND-Diplomat Pipeline Entry Point
- **INPUT:** query, user_id, session_id, country_code, use_red_team, use_mcts, max_investigation_loops, **flags, **kwargs
- **OUTPUT:** Dict
- **CALLED BY:** API.main, Layer4_Analysis.core.unified_pipeline, Scripts.test_e2e, test_architecture_validation, test_comprehensive_system
- **CALLS:** Layer2_Knowledge.knowledge_api, Layer2_Knowledge.retriever, Layer3_StateModel.interface.state_provider, Layer4_Analysis.coordinator, Layer4_Analysis.core.llm_client, Layer4_Analysis.core.unified_pipeline, layer1_sensors
- **CRITICALITY:** core

**FILE:** `Config/thresholds.py`
- **PURPOSE:** Centralized Configuration for Signal Thresholds.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** SignalThresholds
- **CALLED BY:** Layer3_StateModel.construction.country_state_builder, Layer4_Analysis.decision.verifier
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `contracts/__init__.py`
- **PURPOSE:** Shared contracts used across layers.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** LAYER1_COLLECTION.cleaning.deduplicator
- **CRITICALITY:** unused

**FILE:** `contracts/observation.py`
- **PURPOSE:** Observation contract exported for cross-layer use.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** Core.investigation.research_controller, Core.orchestrator.layer123_pipeline, LAYER1_COLLECTION.time_filter, Layer3_StateModel.construction.relationship_state_builder, Layer3_StateModel.credibility.contradiction_engine, Layer3_StateModel.credibility.corroboration_engine, Layer3_StateModel.credibility.source_weighting, Layer3_StateModel.scoring.confidence_calculator, Layer3_StateModel.temporal.freshness_model, Layer4_Analysis.support_models.country_model.intent_capability_model, Tests.run_layer123_behavioral_e2e, Tests.run_layer3_behavioral_sensitivity, system_stress_test
- **CALLS:** LAYER1_COLLECTION.cleaning.deduplicator, LAYER1_COLLECTION.observation
- **CRITICALITY:** unused

**FILE:** `core.py`
- **PURPOSE:** Compatibility package shim.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Tests.test_all_features, Tests.verify_pipeline
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Core/__init__.py`
- **PURPOSE:** Core package marker.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Core/case_management/__init__.py`
- **PURPOSE:** Case management package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.case_management.case, Core.case_management.case_manager, Core.case_management.case_store
- **CRITICALITY:** unused

**FILE:** `Core/case_management/case.py`
- **PURPOSE:** Case domain models.
- **INPUT:** question, actors, hypothesis, metadata
- **OUTPUT:** CaseStatus, CaseRecord
- **CALLED BY:** Core.case_management, Core.case_management.case_manager, Core.case_management.case_store, Core.orchestrator.investigation_loop, Tests.test_case_management
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Core/case_management/case_manager.py`
- **PURPOSE:** High-level case manager facade.
- **INPUT:** store, question, actors, hypothesis, metadata, case_id, status, confidence, missing_evidence, evidence_ids, query, indexes
- **OUTPUT:** CaseManager, CaseRecord, Optional, List
- **CALLED BY:** Core.case_management, Core.orchestrator.investigation_loop, Tests.test_case_management
- **CALLS:** Core.case_management.case, Core.case_management.case_store
- **CRITICALITY:** unused

**FILE:** `Core/case_management/case_store.py`
- **PURPOSE:** SQLite-backed storage for investigation cases.
- **INPUT:** db_path, record, case_id, limit, row
- **OUTPUT:** CaseStore, sqlite3.Connection, Optional, List, CaseRecord
- **CALLED BY:** Core.case_management, Core.case_management.case_manager, Tests.test_case_management
- **CALLS:** Core.case_management.case
- **CRITICALITY:** unused

**FILE:** `Core/context.py`
- **PURPOSE:** Pipeline Context - Shared context passed between modules.
- **INPUT:** query, user_id, session_id, **flags, key, default, value, source, score, components, **kwargs, flag_name
- **OUTPUT:** PipelineContext, Any, Dict, bool, ModuleResult, Optional
- **CALLED BY:** Core.module_base, Core.orchestrator.runtime, Core.orchestrator.wrappers, Core.wrappers, Layer2_Knowledge.sources.wrappers, Tests.test_all_features, Tests.test_layer4_runtime_gate
- **CALLS:** Core.module_base
- **CRITICALITY:** unused

**FILE:** `Core/database/__init__.py`
- **PURPOSE:** Database package exports.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.database.db, Core.database.evidence_registry
- **CRITICALITY:** unused

**FILE:** `Core/database/db.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** Core.database, Core.database.init_db, Core.database.models, Core.database.session, Layer2_Knowledge.sources.knowledge_ingestor, Tests.run_layer123_behavioral_e2e
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Core/database/evidence_registry.py`
- **PURPOSE:** Evidence Registry - Track Evidence Requirements and Fulfillment
- **INPUT:** requirement, analysis, doc_id, document, documents
- **OUTPUT:** RequirementStatus, EvidenceRequirement, SufficiencyResult, EvidenceRegistry, bool, List, Dict
- **CALLED BY:** Core.database, Core.orchestrator.investigation_loop
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Core/database/init_db.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.database.db, Core.database.models
- **CRITICALITY:** unused

**FILE:** `Core/database/models.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** Document, Statement, Event
- **CALLED BY:** Core.database.init_db, Core.investigation.research_controller, Layer2_Knowledge.sources.knowledge_ingestor, Tests.run_layer123_behavioral_e2e, check_db, debug_events, debug_statements, system_stress_test, test_insert
- **CALLS:** Core.database.db
- **CRITICALITY:** unused

**FILE:** `Core/database/session.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** Core.investigation.research_controller, Layer2_Knowledge.sources.knowledge_ingestor, Tests.run_layer123_behavioral_e2e, check_db, debug_events, debug_statements, system_stress_test, test_insert
- **CALLS:** Core.database.db
- **CRITICALITY:** unused

**FILE:** `Core/debug/pipeline_trace.py`
- **PURPOSE:** Simple runtime trace utility for pipeline stage visibility.
- **INPUT:** stage
- **OUTPUT:** None explicit
- **CALLED BY:** Core.orchestrator.layer123_pipeline, Tests.full_pipeline_execution
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Core/evidence/__init__.py`
- **PURPOSE:** Signal-level provenance helpers for evidence-backed reporting.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.evidence.provenance_tracker
- **CRITICALITY:** unused

**FILE:** `Core/evidence/provenance_tracker.py`
- **PURPOSE:** Signal-level provenance tracking.
- **INPUT:** value, signal, evidence, evidences, signals, data
- **OUTPUT:** Evidence, ProvenanceTracker, Dict, str, List
- **CALLED BY:** Core.evidence, Layer3_StateModel.interface.state_provider
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Core/evidence_db/__init__.py`
- **PURPOSE:** Evidence database package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.evidence_db.evidence_query, Core.evidence_db.evidence_store
- **CRITICALITY:** unused

**FILE:** `Core/evidence_db/evidence_query.py`
- **PURPOSE:** Query helpers for evidence database.
- **INPUT:** db_path, actor, target, limit, document_id, row
- **OUTPUT:** EvidenceQuery, sqlite3.Connection, List, Dict
- **CALLED BY:** Core.evidence_db, Tests.test_evidence_db
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Core/evidence_db/evidence_store.py`
- **PURPOSE:** Evidence store: normalized persistence for document-level evidence units.
- **INPUT:** db_path, schema_path, document, documents, claim, event, statement, document_id, signal, signature, limit
- **OUTPUT:** EvidenceStore, sqlite3.Connection, str, List, bool, float, int
- **CALLED BY:** Core.evidence_db, Core.orchestrator.research_controller, Layer2_Knowledge.sources.knowledge_ingestor, Tests.test_evidence_db
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Core/investigation/__init__.py`
- **PURPOSE:** Investigation bridge between state modeling and external collection.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.investigation.gap_detector, Core.investigation.investigation_planner, Core.investigation.planner, Core.investigation_controller
- **CRITICALITY:** unused

**FILE:** `Core/investigation/gap_detector.py`
- **PURPOSE:** Gap detector for bridge-stage investigations (Layer-3 -> MoltBot).
- **INPUT:** question, country_state, relationship_state, states, state, container, keys, value, key, default, path
- **OUTPUT:** GapReport, List, str, int, float, bool, Any, Dict
- **CALLED BY:** Core.investigation, Core.investigation.research_controller, Tests.test_audit_verification, Tests.test_investigation_gap_detector
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Core/investigation/investigation_controller.py`
- **PURPOSE:** Compatibility wrapper for investigation controller naming.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.investigation.research_controller
- **CRITICALITY:** unused

**FILE:** `Core/investigation/investigation_planner.py`
- **PURPOSE:** Investigation planner for generating targeted research queries.
- **INPUT:** prompt, question, gaps, max_queries, raw
- **OUTPUT:** str, List
- **CALLED BY:** Core.investigation, Core.investigation.planner, Core.investigation.research_controller
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Core/investigation/planner.py`
- **PURPOSE:** Compatibility wrapper for planner naming.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** Core.investigation
- **CALLS:** Core.investigation.investigation_planner
- **CRITICALITY:** unused

**FILE:** `Core/investigation/research_controller.py`
- **PURPOSE:** Investigation controller bridge (state -> gap -> plan -> collection -> rebuild).
- **INPUT:** question, country_state, relationship_state, needed_information, countries, queries, required_evidence, missing_gaps, documents, state_update, value, label
- **OUTPUT:** InvestigationOutcome, InvestigationController, Dict, List, float, int, str
- **CALLED BY:** Core.investigation.investigation_controller
- **CALLS:** Core.database.models, Core.database.session, Core.investigation.gap_detector, Core.investigation.investigation_planner, Layer2_Knowledge.assimilation.investigation_ingestor, Layer3_Reasoning.investigation_outcome, Layer3_StateModel.analysis_readiness, Layer3_StateModel.country_state_builder, Layer3_StateModel.relationship_state_builder, Layer3_StateModel.validation.confidence_calculator, contracts.observation, ind_diplomat.state.state_builder, moltbot.search
- **CRITICALITY:** unused

**FILE:** `Core/investigation_controller.py`
- **PURPOSE:** Compatibility shim for `Core.orchestrator.investigation_controller`.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** Core.investigation
- **CALLS:** Core.orchestrator.investigation_controller
- **CRITICALITY:** unused

**FILE:** `Core/layer123_pipeline.py`
- **PURPOSE:** Compatibility shim for `Core.orchestrator.layer123_pipeline`.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.orchestrator.layer123_pipeline
- **CRITICALITY:** unused

**FILE:** `Core/module_base.py`
- **PURPOSE:** Core Module Base - Abstract base class for all pipeline modules.
- **INPUT:** ctx
- **OUTPUT:** ModuleStatus, ModuleResult, ModuleBase, str, List, bool, Dict
- **CALLED BY:** Core.context, Core.orchestrator.runtime, Core.orchestrator.wrappers, Core.registry, Core.wrappers, Layer2_Knowledge.sources.wrappers, Tests.test_all_features, Tests.test_layer4_runtime_gate
- **CALLS:** Core.context
- **CRITICALITY:** unused

**FILE:** `Core/orchestrator/__init__.py`
- **PURPOSE:** Core orchestration package.
- **INPUT:** query, user_id, session_id, **flags, module_name
- **OUTPUT:** PipelineResult
- **CALLED BY:** Tests.test_all_features, Tests.verify_pipeline
- **CALLS:** Core.orchestrator.runtime
- **CRITICALITY:** unused

**FILE:** `Core/orchestrator/analysis_router.py`
- **PURPOSE:** Analysis Router — Signal Selector
- **INPUT:** analysis_type, query
- **OUTPUT:** AnalysisType, AnalysisRouter, Dict, List
- **CALLED BY:** Tests.test_comprehensive_audit, Tests.test_post_restructuring, analysis_api.services
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Core/orchestrator/investigation_controller.py`
- **PURPOSE:** Investigation controller (orchestration layer).
- **INPUT:** controller, loop, query, analysis, plan, retriever, max_rounds, context
- **OUTPUT:** InvestigationController, QueryAnalysis, RetrievalPlan, EvidenceBundle, InvestigationResult
- **CALLED BY:** Core.investigation_controller, Core.orchestrator.wrappers
- **CALLS:** Core.orchestrator.investigation_loop, Core.orchestrator.research_controller
- **CRITICALITY:** unused

**FILE:** `Core/orchestrator/investigation_loop.py`
- **PURPOSE:** Investigation Loop - Iterative Retrieval Until Sufficiency
- **INPUT:** sufficiency_threshold, min_documents, max_documents, query, retriever, max_rounds, context, plan, gaps, status, documents, result
- **OUTPUT:** InvestigationStatus, InvestigationRound, InvestigationResult, InvestigationLoop, List, Dict
- **CALLED BY:** Core.orchestrator.investigation_controller
- **CALLS:** Core.case_management.case, Core.case_management.case_manager, Core.database.evidence_registry, Core.orchestrator.research_controller
- **CRITICALITY:** unused

**FILE:** `Core/orchestrator/knowledge_port.py`
- **PURPOSE:** Layer-3 Knowledge Port.
- **INPUT:** query, indexes, filters, time_filter, top_k, source, text, documents
- **OUTPUT:** KnowledgePort, KnowledgeResponse, float, Optional, Dict, List
- **CALLED BY:** Core.orchestrator.research_controller, Layer3_StateModel.credibility.source_weighting, Layer3_StateModel.providers.leaders_provider, Layer3_StateModel.providers.lowy_provider, Layer3_StateModel.providers.ofac_provider, Layer3_StateModel.providers.ports_provider, Layer3_StateModel.providers.ucdp_provider, Layer3_StateModel.scoring.confidence_calculator, Scripts.test_layer3, Tests.run_layer123_behavioral_e2e, system_stress_test
- **CALLS:** Layer2_Knowledge.knowledge_api
- **CRITICALITY:** core

**FILE:** `Core/orchestrator/knowledge_request.py`
- **PURPOSE:** Knowledge Request Loop — The "I Don't Know" Protocol
- **INPUT:** country, available_signals, date
- **OUTPUT:** GapType, GapPriority, KnowledgeGap, ConfidenceLevel, AssessmentConfidence, GapDetector, Dict, Tuple
- **CALLED BY:** Tests.test_audit_verification
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Core/orchestrator/layer123_pipeline.py`
- **PURPOSE:** Unified Layer 1 -> Layer 2 -> Layer 3 orchestration.
- **INPUT:** index_dir, raw_gdelt_events, country_a, country_b, start_date, end_date, query, worldbank_state, comtrade_state, observations, obs, action_type
- **OUTPUT:** Layer123Result, Layer123Pipeline, Dict, List, str
- **CALLED BY:** Core.layer123_pipeline, Tests.full_pipeline_execution, Tests.test_layer123_unified_pipeline
- **CALLS:** Core.debug.pipeline_trace, Layer2_Knowledge.entity_registry, Layer2_Knowledge.multi_index, Layer2_Knowledge.source_registry, Layer2_Knowledge.translators.gdelt_translator, Layer3_StateModel.analysis_readiness, Layer3_StateModel.evidence_gate, Layer3_StateModel.relationship_state_builder, contracts.observation
- **CRITICALITY:** unused

**FILE:** `Core/orchestrator/query_analyzer.py`
- **PURPOSE:** Query Analyzer — Intelligent Query Understanding
- **INPUT:** query, query_lower
- **OUTPUT:** QueryPlan, QueryAnalyzer, List, Optional, Tuple, str
- **CALLED BY:** Tests.test_layers_1_2, Tests.test_post_restructuring
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Core/orchestrator/research_controller.py`
- **PURPOSE:** Research Controller - Central Investigation Intelligence
- **INPUT:** llm_client, knowledge, gap_collector, query, query_lower, query_type, entities, required_evidence, temporal_context, analysis, plan, retriever
- **OUTPUT:** QueryType, EvidenceType, QueryAnalysis, RetrievalPlan, EvidenceBundle, ResearchController, List, Optional, str, Dict, float
- **CALLED BY:** Core.orchestrator.investigation_controller, Core.orchestrator.investigation_loop, Tests.test_layer3_verification_protocol
- **CALLS:** Core.evidence_db.evidence_store, Core.orchestrator.knowledge_port, Layer3_StateModel.evidence_gate
- **CRITICALITY:** unused

**FILE:** `Core/orchestrator/runtime.py`
- **PURPOSE:** Pipeline Orchestrator - Central execution engine.
- **INPUT:** query, user_id, session_id, **flags, module, module_name, event, callback, ctx
- **OUTPUT:** PipelineResult, Orchestrator, Dict, ModuleResult
- **CALLED BY:** Core.orchestrator
- **CALLS:** Core.context, Core.module_base, Core.registry
- **CRITICALITY:** unused

**FILE:** `Core/orchestrator/wrappers.py`
- **PURPOSE:** Research Module Wrappers - Pipeline Integration
- **INPUT:** ctx
- **OUTPUT:** ResearchControllerModule, InvestigationModule, EvidenceBinderModule, str, List, ModuleResult
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.context, Core.module_base, Core.orchestrator.investigation_controller, Layer3_StateModel.evidence_binder
- **CRITICALITY:** unused

**FILE:** `Core/registry.py`
- **PURPOSE:** Module Registry - Plugin-like registration and discovery of modules.
- **INPUT:** module, module_name, package_name, name
- **OUTPUT:** ModuleRegistry, bool, Optional, Dict, List
- **CALLED BY:** Core.orchestrator.runtime, Core.wrappers, Tests.test_all_features, Tests.verify_pipeline
- **CALLS:** Core.module_base
- **CRITICALITY:** unused

**FILE:** `Core/wrappers.py`
- **PURPOSE:** Module Wrappers - Wrap existing components with ModuleBase interface.
- **INPUT:** ctx
- **OUTPUT:** DossierModule, RetrievalModule, SafetyModule, CRAGModule, ConfidenceLedgerModule, TemporalBriefingModule, GenerationModule, CoVeModule, RedTeamModule, MCTSModule, CausalModule, ScenarioPlaybookModule
- **CALLED BY:** Tests.test_layer4_runtime_gate
- **CALLS:** Core.context, Core.module_base, Core.registry, Layer3_StateModel.analysis_readiness, Layer3_StateModel.temporal, Layer4_Analysis.core.llm_client, Layer4_Analysis.decision.refusal_engine, Layer4_Analysis.deliberation.cove, Layer4_Analysis.deliberation.crag, Layer4_Analysis.deliberation.red_team, Layer4_Analysis.hypothesis.causal, Layer4_Analysis.hypothesis.mcts, Layer4_Analysis.intake.playbooks, Layer4_Analysis.intake.question_scope_checker, Layer4_Analysis.safety.guard
- **CRITICALITY:** unused

**FILE:** `debug_events.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.database.models, Core.database.session
- **CRITICALITY:** unused

**FILE:** `debug_statements.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.database.models, Core.database.session
- **CRITICALITY:** unused

**FILE:** `Docs/Architecture/init_database.py`
- **PURPOSE:** Initialize the ingestion database with schema.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `fix_bom.py`
- **PURPOSE:** Fix BOM (Byte Order Mark) in Python files.
- **INPUT:** filepath
- **OUTPUT:** bool
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Frontend/server.py`
- **PURPOSE:** UI Server - Serve the explainability dashboard and proxy API requests.
- **INPUT:** request
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `generate_section5.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** filepath
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `ind_diplomat/__init__.py`
- **PURPOSE:** IND-Diplomat perception package (Layers 2-3 build track).
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `ind_diplomat/knowledge/__init__.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** Tests.test_pipeline_first, ind_diplomat.pipeline
- **CALLS:** ind_diplomat.knowledge.actor_mapper, ind_diplomat.knowledge.doc_classifier, ind_diplomat.knowledge.legal_extractor, ind_diplomat.knowledge.statement_extractor
- **CRITICALITY:** unused

**FILE:** `ind_diplomat/knowledge/actor_mapper.py`
- **PURPOSE:** Actor normalization and mention detection.
- **INPUT:** name, names, text, max_count
- **OUTPUT:** str, List
- **CALLED BY:** Tests.test_ind_diplomat_perception, ind_diplomat.knowledge, ind_diplomat.knowledge.legal_extractor, ind_diplomat.knowledge.statement_extractor
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `ind_diplomat/knowledge/doc_classifier.py`
- **PURPOSE:** Document classifier for Layer-2 knowledge structuring.
- **INPUT:** use_transformers, model_name, text, texts
- **OUTPUT:** ClassificationResult, DocumentClassifier, Dict, List
- **CALLED BY:** Tests.test_ind_diplomat_perception, ind_diplomat.knowledge
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `ind_diplomat/knowledge/legal_extractor.py`
- **PURPOSE:** Legal claim extractor.
- **INPUT:** use_ollama, ollama_model, ollama_url, timeout_seconds, strict_mode, text, actor_hint, texts, reason
- **OUTPUT:** LegalExtractor, Dict, List, Optional
- **CALLED BY:** Tests.test_ind_diplomat_perception, ind_diplomat.knowledge
- **CALLS:** ind_diplomat.knowledge.actor_mapper
- **CRITICALITY:** unused

**FILE:** `ind_diplomat/knowledge/statement_extractor.py`
- **PURPOSE:** Diplomatic statement extractor.
- **INPUT:** use_spacy, strict_attribution, text, texts, reason
- **OUTPUT:** StatementExtractor, Dict, List
- **CALLED BY:** Tests.test_ind_diplomat_perception, ind_diplomat.knowledge
- **CALLS:** ind_diplomat.knowledge.actor_mapper
- **CRITICALITY:** unused

**FILE:** `ind_diplomat/moltbot/__init__.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** ind_diplomat.moltbot.cleaner, ind_diplomat.moltbot.fetcher
- **CRITICALITY:** unused

**FILE:** `ind_diplomat/moltbot/chunker.py`
- **PURPOSE:** Chunker for cleaned text.
- **INPUT:** text, max_chars, overlap_chars, record
- **OUTPUT:** List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `ind_diplomat/moltbot/cleaner.py`
- **PURPOSE:** Text cleaner for fetched documents.
- **INPUT:** raw_text, record
- **OUTPUT:** str, Dict
- **CALLED BY:** ind_diplomat.moltbot, ind_diplomat.pipeline
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `ind_diplomat/moltbot/fetcher.py`
- **PURPOSE:** Basic MoltBot fetcher for raw document ingestion.
- **INPUT:** raw_dir, url, source_name, timeout, urls, record
- **OUTPUT:** MoltBotFetcher, Dict, List, Path
- **CALLED BY:** Scripts.debug_moltbot, Scripts.test_moltbot_fetcher, ind_diplomat.moltbot
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `ind_diplomat/moltbot/retriever.py`
- **PURPOSE:** Local retriever for processed documents/chunks.
- **INPUT:** text, a, b, processed_dir, docs, query, top_k
- **OUTPUT:** LocalRetriever, set, float, List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `ind_diplomat/pipeline.py`
- **PURPOSE:** Perception pipeline:
- **INPUT:** use_transformers, use_spacy, use_ollama, strict_analytical_signals, processed_dir, text, source, url, documents, trade_dependency, military_balance, output_path
- **OUTPUT:** PerceptionPipeline, Dict, List, Path
- **CALLED BY:** Tests.test_ind_diplomat_perception
- **CALLS:** ind_diplomat.knowledge, ind_diplomat.moltbot.cleaner, ind_diplomat.state
- **CRITICALITY:** unused

**FILE:** `ind_diplomat/sensors/__init__.py`
- **PURPOSE:** Sensor contracts for the perception pipeline.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** SensorDocument
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `ind_diplomat/state/__init__.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** ind_diplomat.pipeline
- **CALLS:** ind_diplomat.state.indicator_builder, ind_diplomat.state.state_builder, ind_diplomat.state.tone_detector
- **CRITICALITY:** unused

**FILE:** `ind_diplomat/state/indicator_builder.py`
- **PURPOSE:** Deterministic indicator builders (no model logic).
- **INPUT:** value, low, high, imports_from_partner, total_imports, spending_a, spending_b, events, scores, actors, recent_events, legal_signals
- **OUTPUT:** float, int, Dict
- **CALLED BY:** ind_diplomat.state, ind_diplomat.state.state_builder
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `ind_diplomat/state/state_builder.py`
- **PURPOSE:** State model builder and writer.
- **INPUT:** values, unavailable, total, actors, recent_events, legal_signals, tone_scores, trade_dependency, military_balance, evidence_sources, save, processed_docs
- **OUTPUT:** StateBuilder, List, str, Dict, Optional
- **CALLED BY:** Core.investigation.research_controller, ind_diplomat.state
- **CALLS:** ind_diplomat.state.indicator_builder, schemas.state_schema
- **CRITICALITY:** unused

**FILE:** `ind_diplomat/state/tone_detector.py`
- **PURPOSE:** Tone detector for diplomatic escalation scoring.
- **INPUT:** use_transformers, model_name, strict_mode, text, texts, label, reason
- **OUTPUT:** ToneDetector, Dict, List, tuple
- **CALLED BY:** Tests.test_ind_diplomat_perception, ind_diplomat.state
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `LAYER1_COLLECTION/__init__.py`
- **PURPOSE:** Layer 1 — Collection Package
- **INPUT:** countries, hours_back
- **OUTPUT:** Dict
- **CALLED BY:** Scripts.test_sensors
- **CALLS:** LAYER1_COLLECTION.api.GDELT.sensor, LAYER1_COLLECTION.api.comtrade.sensor, LAYER1_COLLECTION.api.worldbank.sensor, LAYER1_COLLECTION.cleaning.deduplicator, LAYER1_COLLECTION.observation
- **CRITICALITY:** unused

**FILE:** `LAYER1_COLLECTION/api/__init__.py`
- **PURPOSE:** Layer 1 API adapters and external collector agents.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `LAYER1_COLLECTION/api/comtrade/__init__.py`
- **PURPOSE:** UN Comtrade Supply Chain Leverage Sensor
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `LAYER1_COLLECTION/api/comtrade/client.py`
- **PURPOSE:** UN Comtrade API — HTTP Client
- **INPUT:** api_key, params, iso3, reporter, partner, year, hs_codes, hs_code, flow, raw
- **OUTPUT:** ComtradeClientError, ComtradeAuthError, ComtradeClient, bool, Any, int, List
- **CALLED BY:** LAYER1_COLLECTION.api.comtrade.sensor
- **CALLS:** LAYER1_COLLECTION.api.comtrade.config
- **CRITICALITY:** core

**FILE:** `LAYER1_COLLECTION/api/comtrade/config.py`
- **PURPOSE:** UN Comtrade Supply Chain Configuration & Reference Tables
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** LAYER1_COLLECTION.api.comtrade.client, LAYER1_COLLECTION.api.comtrade.sensor
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `LAYER1_COLLECTION/api/comtrade/sensor.py`
- **PURPOSE:** UN Comtrade Supply Chain Leverage Sensor — State Snapshot Producer
- **INPUT:** reporter, partner, year, api_key, cache_ttl_days, bilateral, flows, total_imports, total_exports, trade_balance, dependencies, leverage
- **OUTPUT:** ComtradeSensor, Dict, List, float, str
- **CALLED BY:** LAYER1_COLLECTION, layer1_sensors
- **CALLS:** LAYER1_COLLECTION.api.comtrade.client, LAYER1_COLLECTION.api.comtrade.config
- **CRITICALITY:** core

**FILE:** `LAYER1_COLLECTION/api/GDELT/__init__.py`
- **PURPOSE:** GDELT Sensor Module
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `LAYER1_COLLECTION/api/GDELT/client.py`
- **PURPOSE:** GDELT HTTP Client
- **INPUT:** url, hours_back, timestamp
- **OUTPUT:** GDELTClientError, GDELTClient, bytes, str, Dict, List
- **CALLED BY:** LAYER1_COLLECTION.api.GDELT.sensor, Tests.manual_live_gdelt_validation, Tests.run_layer123_behavioral_e2e, Tests.run_layer3_behavioral_sensitivity
- **CALLS:** LAYER1_COLLECTION.api.GDELT.config
- **CRITICALITY:** core

**FILE:** `LAYER1_COLLECTION/api/GDELT/config.py`
- **PURPOSE:** GDELT Configuration & CAMEO Lookup Tables
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** LAYER1_COLLECTION.api.GDELT.client, LAYER1_COLLECTION.api.GDELT.parser, LAYER1_COLLECTION.api.GDELT.sensor
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `LAYER1_COLLECTION/api/GDELT/parser.py`
- **PURPOSE:** GDELT Record Parser
- **INPUT:** val, line, field_names, int_fields, float_fields, csv_text, tone_str, gcam_str, loc_str, counts_str, persons_str, orgs_str
- **OUTPUT:** Optional, List, Dict
- **CALLED BY:** LAYER1_COLLECTION.api.GDELT.sensor, Tests.manual_live_gdelt_validation, Tests.run_layer123_behavioral_e2e, Tests.run_layer3_behavioral_sensitivity
- **CALLS:** LAYER1_COLLECTION.api.GDELT.config
- **CRITICALITY:** core

**FILE:** `LAYER1_COLLECTION/api/GDELT/sensor.py`
- **PURPOSE:** GDELT Sensor — State Snapshot Producer
- **INPUT:** countries, hours_back, include_gkg, cache_ttl_minutes, events, avg_goldstein, quad_dist, root_codes, n, gkg_records, error, evs
- **OUTPUT:** GDELTSensor, Dict, str, bool, List
- **CALLED BY:** LAYER1_COLLECTION, layer1_sensors
- **CALLS:** LAYER1_COLLECTION.api.GDELT.client, LAYER1_COLLECTION.api.GDELT.config, LAYER1_COLLECTION.api.GDELT.parser
- **CRITICALITY:** core

**FILE:** `LAYER1_COLLECTION/api/moltbot_agent.py`
- **PURPOSE:** MoltBot Agent - Layer 1 external investigator.
- **INPUT:** collector_url, timeout, max_retries, backoff_seconds, failure_threshold, cooldown_seconds, archive_root, enable_web_fallback, enable_local_fallback, query, required_evidence, countries
- **OUTPUT:** MoltBotAgent, List, str, Optional, bool, int, Dict
- **CALLED BY:** Tests.test_layer12_validation_protocol, check_dependencies, moltbot.search
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `LAYER1_COLLECTION/api/worldbank/__init__.py`
- **PURPOSE:** World Bank Economic Pressure Sensor
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `LAYER1_COLLECTION/api/worldbank/client.py`
- **PURPOSE:** World Bank API v2 — HTTP Client
- **INPUT:** url, params, data, country_iso3, indicator_code, years_back, countries
- **OUTPUT:** WorldBankClientError, WorldBankClient, Any, List, Dict
- **CALLED BY:** LAYER1_COLLECTION.api.worldbank.sensor
- **CALLS:** LAYER1_COLLECTION.api.worldbank.config
- **CRITICALITY:** core

**FILE:** `LAYER1_COLLECTION/api/worldbank/config.py`
- **PURPOSE:** World Bank Economic Indicators — Configuration & Reference Tables
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** LAYER1_COLLECTION.api.worldbank.client, LAYER1_COLLECTION.api.worldbank.sensor
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `LAYER1_COLLECTION/api/worldbank/sensor.py`
- **PURPOSE:** World Bank Economic Pressure Sensor — State Snapshot Producer
- **INPUT:** country, years_back, compare_with, cache_ttl_hours, raw, records, indicators, value, threshold_key, primary, others, pressure
- **OUTPUT:** WorldBankSensor, Dict, str, int, float
- **CALLED BY:** LAYER1_COLLECTION, layer1_sensors
- **CALLS:** LAYER1_COLLECTION.api.worldbank.client, LAYER1_COLLECTION.api.worldbank.config
- **CRITICALITY:** core

**FILE:** `LAYER1_COLLECTION/app.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** value, directory, code, doc_id, name, existing_name, country, filename, field
- **OUTPUT:** str, List, Any
- **CALLED BY:** API, Scripts.test_api, Tests.test_all_features
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `LAYER1_COLLECTION/cleaning/__init__.py`
- **PURPOSE:** Layer-1 cleaning utilities.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** LAYER1_COLLECTION.cleaning.deduplicator
- **CRITICALITY:** unused

**FILE:** `LAYER1_COLLECTION/cleaning/deduplicator.py`
- **PURPOSE:** Layer-1 document deduplication.
- **INPUT:** documents, doc
- **OUTPUT:** DocumentDeduplicator, List, str
- **CALLED BY:** LAYER1_COLLECTION, LAYER1_COLLECTION.cleaning, contracts, contracts.observation
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `LAYER1_COLLECTION/ingestion/feeder/__init__.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** file_path, content, use_ocr, text, chunk_size, overlap, mode, semaphore, file_paths, concurrency
- **OUTPUT:** IngestionService, str, Dict, List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `LAYER1_COLLECTION/ingestion/feeder/change_detector.py`
- **PURPOSE:** Change Detector - SHA256-based Deduplication
- **INPUT:** db_path, content, metadata, content_hash, days_old
- **OUTPUT:** ContentRecord, ChangeDetector, str, bool, Optional, Dict
- **CALLED BY:** LAYER1_COLLECTION.ingestion.feeder.scheduler, Tests.test_pipeline_first
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `LAYER1_COLLECTION/ingestion/feeder/crawler.py`
- **PURPOSE:** Diplomatic Intelligence Crawler
- **INPUT:** sources, category, max_priority, url, headers, html, patterns, stealth, source, urls
- **OUTPUT:** SourceCategory, DataSource, DiplomaticCrawler, List, bool, Dict
- **CALLED BY:** LAYER1_COLLECTION.ingestion.feeder.scheduler, Scripts.seed_knowledge_base
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `LAYER1_COLLECTION/ingestion/feeder/document_record.py`
- **PURPOSE:** Document Record Writer
- **INPUT:** record, base_dir, doc_id, text
- **OUTPUT:** DocumentRecord, str
- **CALLED BY:** LAYER1_COLLECTION.ingestion.feeder.scheduler
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `LAYER1_COLLECTION/ingestion/feeder/metadata_extractor.py`
- **PURPOSE:** Metadata Extractor — Automatic Document Metadata Detection
- **INPUT:** text, source_config, url, text_lower, doc_type, topics
- **OUTPUT:** MetadataExtractor, Dict, List, str, Optional
- **CALLED BY:** LAYER1_COLLECTION.ingestion.feeder.normalizer, Tests.test_layers_1_2
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `LAYER1_COLLECTION/ingestion/feeder/normalizer.py`
- **PURPOSE:** Document Normalizer — Unified Normalization Pipeline
- **INPUT:** raw_content, content_type, url, source_config, doc, output_dir
- **OUTPUT:** DocumentNormalizer, Dict, list, str
- **CALLED BY:** Tests.test_layers_1_2
- **CALLS:** LAYER1_COLLECTION.ingestion.feeder.metadata_extractor, LAYER1_COLLECTION.ingestion.feeder.ocr_parser, LAYER1_COLLECTION.ingestion.feeder.parser, LAYER1_COLLECTION.ingestion.feeder.pdf_parser
- **CRITICALITY:** unused

**FILE:** `LAYER1_COLLECTION/ingestion/feeder/ocr_parser.py`
- **PURPOSE:** OCR Parser — Scanned Document Handling
- **INPUT:** pdf_bytes, url, img, first_page, text, msg
- **OUTPUT:** OCRParser, bool, Dict, Image.Image, str
- **CALLED BY:** LAYER1_COLLECTION.ingestion.feeder.normalizer, Tests.test_layers_1_2
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `LAYER1_COLLECTION/ingestion/feeder/parser.py`
- **PURPOSE:** Event Parser
- **INPUT:** text, soup, fallback_netloc, date_str, html, url
- **OUTPUT:** str, Optional, Dict
- **CALLED BY:** LAYER1_COLLECTION.ingestion.feeder.normalizer, LAYER1_COLLECTION.ingestion.feeder.scheduler
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `LAYER1_COLLECTION/ingestion/feeder/pdf_parser.py`
- **PURPOSE:** PDF Parser — Hierarchical Text Extraction
- **INPUT:** pdf_bytes, url, text, first_page, msg
- **OUTPUT:** PDFParser, bool, Dict, List, str
- **CALLED BY:** LAYER1_COLLECTION.ingestion.feeder.normalizer, Tests.test_layers_1_2
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `LAYER1_COLLECTION/ingestion/feeder/raw_archive.py`
- **PURPOSE:** Raw Archive - Immutable Evidence Vault
- **INPUT:** archive_path, content, source, url, extension, doc_id, metadata
- **OUTPUT:** RawArchive, str, Tuple
- **CALLED BY:** LAYER1_COLLECTION.ingestion.feeder.scheduler, Tests.test_pipeline_first
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `LAYER1_COLLECTION/ingestion/feeder/scheduler.py`
- **PURPOSE:** Ingestion Scheduler - Automated Collection Service
- **INPUT:** sources_file, data_dir, data, url, user_agent, listing_html, base_url, selector, source, link, errors, priority_filter
- **OUTPUT:** SourceConfig, CrawlResult, IngestionScheduler, Dict, List, bool
- **CALLED BY:** Scripts.data_feeder, Scripts.feeder_ui
- **CALLS:** LAYER1_COLLECTION.ingestion.feeder.change_detector, LAYER1_COLLECTION.ingestion.feeder.crawler, LAYER1_COLLECTION.ingestion.feeder.document_record, LAYER1_COLLECTION.ingestion.feeder.parser, LAYER1_COLLECTION.ingestion.feeder.raw_archive
- **CRITICALITY:** core

**FILE:** `LAYER1_COLLECTION/ingestion/feeder/service.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** file_path, content, use_ocr, text, chunk_size, overlap, chunks_list, content_list, mode, semaphore, file_paths, concurrency
- **OUTPUT:** IngestionService, str, Dict, List
- **CALLED BY:** Scripts.cli, Tests.test_all_features, Utils.verify_pipeline
- **CALLS:** LAYER1_COLLECTION.ingestion.feeder.utils.edge_cases
- **CRITICALITY:** core

**FILE:** `LAYER1_COLLECTION/ingestion/feeder/utils/__init__.py`
- **PURPOSE:** Premium Edge Case Utilities
- **INPUT:** user_id_param, is_heavy, timeout, fallback, param_name, key, default, config, bucket, user_id, max_age, coro
- **OUTPUT:** RateLimitConfig, RateLimitResult, SmartRateLimiter, TimeoutConfig, TimeoutHandler, ValidationConfig, InputValidator, MemoryConfig, MemoryManager, Dict, Any, str
- **CALLED BY:** Layer4_Analysis.evidence.provenance
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `LAYER1_COLLECTION/ingestion/feeder/utils/edge_cases.py`
- **PURPOSE:** Premium Edge Case Utilities
- **INPUT:** user_id_param, is_heavy, timeout, fallback, param_name, key, default, config, bucket, user_id, max_age, coro
- **OUTPUT:** RateLimitConfig, RateLimitResult, SmartRateLimiter, TimeoutConfig, TimeoutHandler, ValidationConfig, InputValidator, MemoryConfig, MemoryManager, Dict, Any, str
- **CALLED BY:** LAYER1_COLLECTION.ingestion.feeder.service
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `LAYER1_COLLECTION/observation.py`
- **PURPOSE:** Observation Record - Universal Sensor Output Format
- **INPUT:** score, event_code, root_code, events, source_confidence, state, d, observations
- **OUTPUT:** ActionType, SourceType, ObservationRecord, ObservationDeduplicator, Optional, float, List, str, Dict
- **CALLED BY:** LAYER1_COLLECTION, Tests.manual_live_gdelt_validation, Tests.test_audit_verification, Tests.test_layer12_validation_protocol, Tests.test_layer3_verification_protocol, Tests.test_reasoning_safety, contracts.observation, layer1_sensors, test_architecture_validation
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `LAYER1_COLLECTION/test_gdelt.py`
- **PURPOSE:** Quick verification script for the GDELT sensor module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `LAYER1_COLLECTION/test_gdelt_live.py`
- **PURPOSE:** Live test: fetch real GDELT data for India (last 1 hour) and save to file.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `LAYER1_COLLECTION/test_wb_comtrade.py`
- **PURPOSE:** Offline verification test for rebuilt World Bank and Comtrade sensors.
- **INPUT:** name, detail, e
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `LAYER1_COLLECTION/test_wb_live.py`
- **PURPOSE:** Live test for World Bank sensor.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `LAYER1_COLLECTION/time_filter.py`
- **PURPOSE:** Layer-1 temporal filtering helpers.
- **INPUT:** observations, start_date, end_date, recent_days, reference_date, text
- **OUTPUT:** List, Tuple
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** contracts.observation
- **CRITICALITY:** unused

**FILE:** `layer1_sensors.py`
- **PURPOSE:** Layer-1 Sensors Module (Compatibility Layer)
- **INPUT:** obs_id, source, source_type, event_date, report_date, actors, action_type, intensity, confidence, raw_data, **kwargs
- **OUTPUT:** Optional
- **CALLED BY:** Config.pipeline, test_comprehensive_system, test_import_debug
- **CALLS:** LAYER1_COLLECTION.api.GDELT.sensor, LAYER1_COLLECTION.api.comtrade.sensor, LAYER1_COLLECTION.api.worldbank.sensor, LAYER1_COLLECTION.observation
- **CRITICALITY:** core

**FILE:** `layer2_extraction/__init__.py`
- **PURPOSE:** Layer-2 Extraction Module
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** layer2_extraction.event_parser
- **CRITICALITY:** unused

**FILE:** `layer2_extraction/event_parser.py`
- **PURPOSE:** Event Parser
- **INPUT:** observation, events
- **OUTPUT:** EventParser, List, Dict
- **CALLED BY:** layer2_extraction, test_architecture_validation, test_comprehensive_system
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/__init__.py`
- **PURPOSE:** Layer-2 Knowledge System.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/access_api/__init__.py`
- **PURPOSE:** Layer2 phase package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/access_api/information_value.py`
- **PURPOSE:** Quantify investigation knowledge gain per extracted signal.
- **INPUT:** signal_date, domain, is_duplicate, signal, obj, key, value
- **OUTPUT:** float, Any
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/access_api/knowledge_api.py`
- **PURPOSE:** Layer-2 Knowledge API.
- **INPUT:** request, source, text, documents, indexes, docs, filters
- **OUTPUT:** KnowledgeRequest, KnowledgeResponse, KnowledgeAPI, float, Optional, Dict, List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.claim_extractor, Layer2_Knowledge.entity_registry, Layer2_Knowledge.legal_signal_extractor, Layer2_Knowledge.multi_index, Layer2_Knowledge.retrieval.time_selector, Layer2_Knowledge.source_registry, schemas.claim_schema
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/access_api/retriever.py`
- **PURPOSE:** Diplomatic Retriever — Layer-2 Memory Search
- **INPUT:** query, plan, as_of_date, top_k, results, k, documents, time_range, date_str
- **OUTPUT:** QueryPlan, DiplomaticRetriever, List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.vector_store, Layer3_StateModel.binding.graph_manager
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/access_api/time_selector.py`
- **PURPOSE:** Layer-2 time-aware document selection.
- **INPUT:** documents, time_filter, text
- **OUTPUT:** List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/action_mapper.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.signal_extraction.action_mapper.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Tests.run_layer123_behavioral_e2e, Tests.test_action_mapper
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/assimilation/__init__.py`
- **PURPOSE:** Knowledge assimilation compatibility package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/assimilation/investigation_ingestor.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.sources.investigation_ingestor.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Core.investigation.research_controller, Tests.test_assimilation_ingestor_path
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/chunker.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.parsing.chunker.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Layer2_Knowledge.storage.indexer
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/claim_extractor.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.signal_extraction.claim_extractor.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Layer2_Knowledge.access_api.knowledge_api, Layer2_Knowledge.sources.knowledge_ingestor
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/document_classifier.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.parsing.document_classifier.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Layer2_Knowledge.storage.indexer
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/engram_store.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.storage.engram_store.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/entity_registry.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.normalization.entity_registry.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Core.orchestrator.layer123_pipeline, Layer2_Knowledge.access_api.knowledge_api, Scripts.test_layer2, Tests.test_audit_verification, Tests.test_layer12_validation_protocol
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/indexer.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.storage.indexer.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/information_value.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.access_api.information_value.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Layer2_Knowledge.sources.knowledge_ingestor, Tests.test_information_value
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/knowledge_api.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.access_api.knowledge_api.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Config.pipeline, Core.orchestrator.knowledge_port, Scripts.test_layer2, Scripts.test_search
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Layer2_Knowledge/knowledge_ingestor.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.sources.knowledge_ingestor.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Layer2_Knowledge.sources.investigation_ingestor, Tests.test_knowledge_ingestor
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/legal_signal_dictionary.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.signal_extraction.legal_signal_dictionary.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Layer2_Knowledge.signal_extraction.legal_signal_extractor.extractor, Tests.test_legal_signal_extractor
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/legal_signal_extractor/__init__.py`
- **PURPOSE:** Compatibility package for legal signal extraction.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** Layer2_Knowledge.access_api.knowledge_api, Layer2_Knowledge.sources.knowledge_ingestor, Tests.run_layer123_behavioral_e2e
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/legal_signal_extractor/extractor.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.signal_extraction.legal_signal_extractor.extractor.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Tests.test_legal_signal_extractor
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/legal_signal_extractor/segmenter.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.parsing.segmenter.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Tests.test_legal_signal_extractor
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/legal_signal_extractor/signals.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.signal_extraction.legal_signal_extractor.signals.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Tests.test_legal_signal_extractor
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/multi_index.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.storage.multi_index.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Core.orchestrator.layer123_pipeline, Layer2_Knowledge.access_api.knowledge_api, Layer2_Knowledge.sources.knowledge_ingestor, Layer2_Knowledge.sources.wrappers, Scripts.test_layer2, Tests.test_layer12_validation_protocol
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/normalization/__init__.py`
- **PURPOSE:** Layer2 phase package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/normalization/entity_registry.py`
- **PURPOSE:** Entity Registry - Canonical Actor Resolution
- **INPUT:** entity, name, canonical_id, org_id, actors
- **OUTPUT:** ActorType, EntityRecord, EntityRegistry, Optional, str, bool, List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/normalization/signal_deduplicator.py`
- **PURPOSE:** Signal deduplication helpers for Layer-2 extraction.
- **INPUT:** text, country, signal_type, sentence
- **OUTPUT:** str
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/normalization/source_registry.py`
- **PURPOSE:** Source Registry — Provenance & Reliability System
- **INPUT:** weights, source, fact_date, confidence_time, confidence_consensus, source_url, corroborating, category
- **OUTPUT:** SourceCategory, EvidenceProvenance, SourceRegistry, float, List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/normalization/treaty_lifecycle.py`
- **PURPOSE:** Treaty Lifecycle Manager — Temporal Document Status Tracking
- **INPUT:** date, storage_path, record, treaty_id, *parties, parties, new_status, reason, replaced_by
- **OUTPUT:** TreatyStatus, TreatyRecord, TreatyLifecycleManager, bool, Dict, Optional, List, int
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/parsing/__init__.py`
- **PURPOSE:** Layer2 phase package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/parsing/chunker.py`
- **PURPOSE:** Intelligent Chunker — Section-Aware Document Splitting
- **INPUT:** target_tokens, overlap_tokens, document, sections, fallback_text, text, heading, prefix_heading, target_override
- **OUTPUT:** IntelligentChunker, List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/parsing/document_classifier.py`
- **PURPOSE:** Document Classifier - Automatic Document Type Detection
- **INPUT:** document, content, doc_type, documents
- **OUTPUT:** DocumentType, ClassificationResult, DocumentClassifier, Dict, bool
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/parsing/segmenter.py`
- **PURPOSE:** Clause segmenter for legal documents.
- **INPUT:** raw_text
- **OUTPUT:** List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/retrieval/__init__.py`
- **PURPOSE:** Layer-2 retrieval compatibility package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/retrieval/time_selector.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.access_api.time_selector.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Layer2_Knowledge.access_api.knowledge_api
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/retriever.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.access_api.retriever.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Config.pipeline, Layer3_StateModel.interface.state_provider, Layer3_StateModel.providers.state_provider, Scripts.test_layer2, Scripts.test_rag, Tests.test_post_restructuring, test_comprehensive_system
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Layer2_Knowledge/signal_deduplicator.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.normalization.signal_deduplicator.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Layer2_Knowledge.signal_extraction.legal_signal_extractor.extractor, Layer2_Knowledge.sources.knowledge_ingestor, Tests.test_signal_deduplicator
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/signal_extraction/__init__.py`
- **PURPOSE:** Layer2 phase package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/signal_extraction/action_mapper.py`
- **PURPOSE:** Layer-2 diplomatic action mapper.
- **INPUT:** event_code, event_root_code, default
- **OUTPUT:** str
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/signal_extraction/claim_extractor.py`
- **PURPOSE:** Layer-2 claim extraction.
- **INPUT:** document, documents, sentence, metadata
- **OUTPUT:** ClaimExtractor, List, str
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/signal_extraction/legal_signal_dictionary.py`
- **PURPOSE:** Geopolitical legal legitimacy phrase dictionary for Layer-2 extraction.
- **INPUT:** text
- **OUTPUT:** List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/signal_extraction/legal_signal_extractor/__init__.py`
- **PURPOSE:** Legal Signal Extractor package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.signal_extraction.signals
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/signal_extraction/legal_signal_extractor/extractor.py`
- **PURPOSE:** Legal signal extractor core.
- **INPUT:** documents, text, source, jurisdiction_level, actor_hint, hits, signal_type, clause_text, signal_meta, start, end, canonical_phrase
- **OUTPUT:** CitationSpan, LegalSignal, LegalSignalExtractor, PrecedenceEngine, Dict, List, float, str
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.legal_signal_dictionary, Layer2_Knowledge.signal_deduplicator, Layer2_Knowledge.signal_extraction.legal_signal_extractor.segmenter, Layer2_Knowledge.signal_extraction.legal_signal_extractor.signals, schemas.legal_signal_schema
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/signal_extraction/legal_signal_extractor/segmenter.py`
- **PURPOSE:** Compatibility bridge to parsing-stage segmenter implementation.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Layer2_Knowledge.signal_extraction.legal_signal_extractor.extractor
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/signal_extraction/legal_signal_extractor/signals.py`
- **PURPOSE:** Power-word signal definitions for legal micro-signal extraction.
- **INPUT:** clause_text, hits
- **OUTPUT:** List, str
- **CALLED BY:** Layer2_Knowledge.signal_extraction.legal_signal_extractor.extractor
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/signal_extraction/signals.py`
- **PURPOSE:** Geopolitical Signal Definitions
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** SignalType, BaseSignal, EventSignal, EconomicSignal, MilitarySignal, LegalSignal, LeadershipSignal
- **CALLED BY:** Layer2_Knowledge.signal_extraction.legal_signal_extractor
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/signals/__init__.py`
- **PURPOSE:** Signal model compatibility package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/signals/base.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.signal_extraction.signals.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Layer2_Knowledge.sources.base, Layer2_Knowledge.sources.gdelt_translator, Layer3_StateModel.schemas.state, Tests.test_comprehensive_audit, Tests.test_post_restructuring, Tests.test_signal_layer
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/source_registry.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.normalization.source_registry.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Core.orchestrator.layer123_pipeline, Layer2_Knowledge.access_api.knowledge_api, Layer2_Knowledge.sources.gdelt_translator, Scripts.test_layer2, Tests.test_audit_verification, Tests.test_post_restructuring
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/sources/__init__.py`
- **PURPOSE:** Layer2 phase package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/sources/base.py`
- **PURPOSE:** Translator Interface
- **INPUT:** records, signal
- **OUTPUT:** BaseTranslator, BaseSignal, bool
- **CALLED BY:** Layer2_Knowledge.sources.gdelt_translator
- **CALLS:** Layer2_Knowledge.signals.base
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/sources/gdelt_translator.py`
- **PURPOSE:** GDELT Translator
- **INPUT:** event_code, records
- **OUTPUT:** str, GDELTTranslator, EventSignal
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.signals.base, Layer2_Knowledge.source_registry, Layer2_Knowledge.sources.base
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/sources/investigation_ingestor.py`
- **PURPOSE:** Investigation document ingestor.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.knowledge_ingestor
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/sources/knowledge_ingestor.py`
- **PURPOSE:** Layer-2 knowledge ingestor.
- **INPUT:** documents, db, doc, url, content, source, actor, predicate, polarity
- **OUTPUT:** IngestionSummary, Dict, str, float
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.database.db, Core.database.models, Core.database.session, Core.evidence_db.evidence_store, Layer2_Knowledge.claim_extractor, Layer2_Knowledge.information_value, Layer2_Knowledge.legal_signal_extractor, Layer2_Knowledge.multi_index, Layer2_Knowledge.signal_deduplicator
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/sources/wrappers.py`
- **PURPOSE:** Knowledge Module Wrappers - Pipeline Integration
- **INPUT:** ctx
- **OUTPUT:** MultiIndexModule, str, List, ModuleResult
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.context, Core.module_base, Layer2_Knowledge.multi_index
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/storage/__init__.py`
- **PURPOSE:** Layer2 phase package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/storage/engram_store.py`
- **PURPOSE:** EngramStore for IND-Diplomat
- **INPUT:** data, persist_path, content, date_value, engram, remove, metadata, embedding, id, engram_id, start_date, end_date
- **OUTPUT:** Engram, EngramStore, Dict, str, datetime, Tuple, Optional, bool, List
- **CALLED BY:** Scripts.cli, Scripts.sync_vectors, Scripts.verify_rag
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Layer2_Knowledge/storage/indexer.py`
- **PURPOSE:** Knowledge Indexer — Ingest → Chunk → Embed → Store
- **INPUT:** **kwargs, normalized_dir, data_dir, index_record_path, doc_path, dir_path
- **OUTPUT:** KnowledgeIndexer, Dict
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.chunker, Layer2_Knowledge.document_classifier, Layer2_Knowledge.storage.vector_store
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/storage/multi_index.py`
- **PURPOSE:** Multi-Index Manager - Separate Knowledge Spaces
- **INPUT:** data_dir, document, space, documents, query, spaces, top_k, time_filter, filters, query_type, required_evidence
- **OUTPUT:** KnowledgeSpace, IndexConfig, MultiIndexManager, List, Dict
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.storage.vector_store
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/storage/vector_store.py`
- **PURPOSE:** Vector Store — Per-Space ChromaDB Collections
- **INPUT:** data_dir, space, chunks, documents, metadatas, ids, query, top_k, where
- **OUTPUT:** VectorStore, int, List, Dict, bool
- **CALLED BY:** Layer2_Knowledge.storage.indexer, Layer2_Knowledge.storage.multi_index
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/translators/__init__.py`
- **PURPOSE:** Layer-2 translator compatibility package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/translators/base.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.sources.base.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/translators/gdelt_translator.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.sources.gdelt_translator.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Core.orchestrator.layer123_pipeline, Scripts.fetch_gdelt, Tests.test_comprehensive_audit, Tests.test_layer12_validation_protocol, Tests.test_post_restructuring, Tests.test_signal_layer
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/treaty_lifecycle.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.normalization.treaty_lifecycle.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Tests.test_layer12_validation_protocol, Tests.test_post_restructuring
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer2_Knowledge/vector_store.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.storage.vector_store.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Layer2_Knowledge.access_api.retriever, Scripts.cli, Scripts.sync_vectors, Scripts.test_layer2, Scripts.verify_rag
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Layer2_Knowledge/wrappers.py`
- **PURPOSE:** Compatibility shim for Layer2_Knowledge.sources.wrappers.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_Reasoning/__init__.py`
- **PURPOSE:** Compatibility shim for Layer4_Analysis.support_models.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_Reasoning/context/__init__.py`
- **PURPOSE:** Compatibility shim for Layer4_Analysis.support_models.context.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_Reasoning/context/baseline_model.py`
- **PURPOSE:** Compatibility shim for Layer4_Analysis.support_models.context.baseline_model.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Tests.test_reasoning_safety
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_Reasoning/country_model/__init__.py`
- **PURPOSE:** Compatibility shim for Layer4_Analysis.support_models.country_model.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_Reasoning/country_model/intent_capability_model.py`
- **PURPOSE:** Compatibility shim for Layer4_Analysis.support_models.country_model.intent_capability_model.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Tests.test_layer3_verification_protocol, Tests.test_reasoning_safety
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_Reasoning/investigation_outcome.py`
- **PURPOSE:** Compatibility shim for Layer4_Analysis.support_models.investigation_outcome.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Core.investigation.research_controller, Tests.test_investigation_outcome
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/__init__.py`
- **PURPOSE:** Layer-3 State Model package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.interface.state_provider
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/analysis_readiness.py`
- **PURPOSE:** Compatibility shim for Layer3_StateModel.construction.analysis_readiness.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Core.investigation.research_controller, Core.orchestrator.layer123_pipeline, Core.wrappers, Tests.test_analysis_readiness
- **CALLS:** None
- **CRITICALITY:** safety

**FILE:** `Layer3_StateModel/binding/__init__.py`
- **PURPOSE:** Layer3 phase package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/binding/evidence_binder.py`
- **PURPOSE:** Evidence Binder - Enforce Claim-to-Source Mapping
- **INPUT:** llm_client, strict_mode, answer, sentence, sources, claim, text, source, index, result, mode
- **OUTPUT:** BoundClaim, BindingResult, EvidenceBinder, str, List, bool, Tuple, Set, Dict
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/binding/graph_manager.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** max_retries, retry_delay, query_date, entity_name, start_entity, relationship_types, max_hops, name, entity_type, properties, from_entity, to_entity
- **OUTPUT:** GraphManager, bool, List, Dict, str, Optional
- **CALLED BY:** Layer2_Knowledge.access_api.retriever, Scripts.cli
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/construction/__init__.py`
- **PURPOSE:** Layer3 phase package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/construction/analysis_readiness.py`
- **PURPOSE:** Layer-3 analysis readiness lock.
- **INPUT:** country_state, relationship_state, confidence, states, container, path
- **OUTPUT:** AnalysisReadinessReport, bool, List, float, int, Any, Dict
- **CALLED BY:** API.main, Layer3_StateModel.interface.state_provider, Scripts.test_layer3
- **CALLS:** None
- **CRITICALITY:** safety

**FILE:** `Layer3_StateModel/construction/country_state_builder.py`
- **PURPOSE:** Country State Builder (Refactored).
- **INPUT:** config, country_code, date, country, signals, c, m, e, d, s, t, tension
- **OUTPUT:** CountryStateBuilder, CountryStateVector, Dict, DimensionScore, float, RiskLevel, List
- **CALLED BY:** Layer3_StateModel.interface.state_provider, Layer3_StateModel.providers.state_provider, Scripts.test_layer3, Tests.test_comprehensive_audit, analysis_api.services
- **CALLS:** Config.config, Config.thresholds, Layer3_StateModel.providers.atop_provider, Layer3_StateModel.providers.comtrade_provider, Layer3_StateModel.providers.eez_provider, Layer3_StateModel.providers.gdelt_provider, Layer3_StateModel.providers.leaders_provider, Layer3_StateModel.providers.lowy_provider, Layer3_StateModel.providers.ofac_provider, Layer3_StateModel.providers.ports_provider, Layer3_StateModel.providers.sanctions_provider, Layer3_StateModel.providers.sipri_provider, Layer3_StateModel.providers.ucdp_provider, Layer3_StateModel.providers.vdem_provider, Layer3_StateModel.providers.worldbank_provider
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/construction/relationship_state_builder.py`
- **PURPOSE:** Relationship State Builder - Structured pairwise assessment for Layer 3.
- **INPUT:** observations, country_a, country_b, start_date, end_date, reference_date
- **OUTPUT:** RelationshipState, RelationshipStateBuilder, Dict, float, List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.validation.confidence_calculator, contracts.observation
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/country_state_builder.py`
- **PURPOSE:** Compatibility shim for Layer3_StateModel.construction.country_state_builder.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Core.investigation.research_controller, Tests.run_layer123_behavioral_e2e, Tests.run_layer3_behavioral_sensitivity, Tests.test_country_state_builder_formulas, Tests.test_country_state_recent_shift, Tests.test_layer3_verification_protocol, Tests.test_pipeline_status, Tests.test_post_restructuring, Tests.test_temporal, system_stress_test, test_import
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/country_state_schema.py`
- **PURPOSE:** Compatibility shim for Layer3_StateModel.schemas.country_state_schema.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Tests.test_comprehensive_audit, Tests.test_country_state_builder_formulas, Tests.test_post_restructuring, analysis_api.services
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/credibility/__init__.py`
- **PURPOSE:** Layer3 phase package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/credibility/contradiction_engine.py`
- **PURPOSE:** Contradiction Engine — Detecting Conflicting Evidence
- **INPUT:** action, time_window_days, observations, claims, obs_a, obs_b, days_gap, date_a, date_b
- **OUTPUT:** SignalDirection, ContradictionType, Contradiction, ContradictionEngine, Dict, List, float
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** contracts.observation
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/credibility/corroboration_engine.py`
- **PURPOSE:** Corroboration Engine — Multi-Source Verification
- **INPUT:** min_for_signal, time_window_days, observations, claims, obs, all_observations, key_a, key_b, obs_a, obs_b, claim_key, obs_list
- **OUTPUT:** CorroborationResult, CorroborationEngine, Dict, List, str, bool, float
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** contracts.observation
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/credibility/source_weighting.py`
- **PURPOSE:** Source-weighted evidence scoring.
- **INPUT:** observations, reference_date
- **OUTPUT:** WeightedEvidence, SourceWeighting, List, float, Dict
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.orchestrator.knowledge_port, Layer3_StateModel.validation.corroboration_engine, Layer3_StateModel.validation.freshness_model, contracts.observation
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/evidence_binder.py`
- **PURPOSE:** Compatibility shim for Layer3_StateModel.binding.evidence_binder.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Core.orchestrator.wrappers, Tests.test_layer3_verification_protocol
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/evidence_gate.py`
- **PURPOSE:** Compatibility shim for Layer3_StateModel.scoring.evidence_gate.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Core.orchestrator.layer123_pipeline, Core.orchestrator.research_controller, Tests.run_layer123_behavioral_e2e, Tests.test_evidence_gate, system_stress_test
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/graph_manager.py`
- **PURPOSE:** Compatibility shim for Layer3_StateModel.binding.graph_manager.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Tests.test_audit_verification, Tests.test_layer12_validation_protocol
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/interface/__init__.py`
- **PURPOSE:** Layer-3 interface package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/interface/state_provider.py`
- **PURPOSE:** Single Layer-3 interface exposed to Layer-4.
- **INPUT:** value, default, text, limit, fallback, source_name, country_code, assessment_date, dimension_name, score_obj, tracker, evidences
- **OUTPUT:** float, str, List, StateContext, Dict, AnalysisReadinessReport, Tuple
- **CALLED BY:** Config.pipeline, Layer3_StateModel, Layer4_Analysis.core.unified_pipeline, Layer4_Analysis.intake.analyst_input_builder, Scripts.test_layer3, Scripts.test_router, test_architecture_validation, test_comprehensive_system, test_grounding_validation, test_state_machine, verify_state_machine
- **CALLS:** Core.evidence.provenance_tracker, Layer2_Knowledge.retriever, Layer3_StateModel.construction.analysis_readiness, Layer3_StateModel.construction.country_state_builder, Layer3_StateModel.reliability.signal_belief_model, Layer3_StateModel.schemas.state_context, Layer3_StateModel.temporal.precursor_monitor
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/precursor_monitor.py`
- **PURPOSE:** Compatibility shim for Layer3_StateModel.temporal.precursor_monitor.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Tests.test_layer4_risk_monitors
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/providers/atop_provider.py`
- **PURPOSE:** ATOP Alliance Data Provider.
- **INPUT:** data_dir, country_code, date, value
- **OUTPUT:** ATOPProvider, Optional
- **CALLED BY:** Layer3_StateModel.construction.country_state_builder
- **CALLS:** Layer3_StateModel.providers.base_provider
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/providers/base_provider.py`
- **PURPOSE:** Abstract Base Class for Layer 3 Data Providers.
- **INPUT:** data_dir, country_code, date, country, date_str, val
- **OUTPUT:** BaseProvider, Optional, str, int, float
- **CALLED BY:** Layer3_StateModel.providers.atop_provider, Layer3_StateModel.providers.comtrade_provider, Layer3_StateModel.providers.eez_provider, Layer3_StateModel.providers.gdelt_provider, Layer3_StateModel.providers.leaders_provider, Layer3_StateModel.providers.lowy_provider, Layer3_StateModel.providers.ofac_provider, Layer3_StateModel.providers.ports_provider, Layer3_StateModel.providers.sanctions_provider, Layer3_StateModel.providers.sipri_provider, Layer3_StateModel.providers.ucdp_provider, Layer3_StateModel.providers.vdem_provider, Layer3_StateModel.providers.worldbank_provider
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/providers/comtrade_provider.py`
- **PURPOSE:** UN Comtrade Data Provider.
- **INPUT:** data_dir, country_code, date, value
- **OUTPUT:** ComtradeProvider, Optional
- **CALLED BY:** Layer3_StateModel.construction.country_state_builder
- **CALLS:** Layer3_StateModel.providers.base_provider
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/providers/eez_provider.py`
- **PURPOSE:** EEZ Maritime Data Provider.
- **INPUT:** data_dir, country_code, date
- **OUTPUT:** EEZProvider, Optional
- **CALLED BY:** Layer3_StateModel.construction.country_state_builder
- **CALLS:** Layer3_StateModel.providers.base_provider
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/providers/gdelt_provider.py`
- **PURPOSE:** GDELT Tension Data Provider.
- **INPUT:** data_dir, tension_history_path, path, country_code, date
- **OUTPUT:** GDELTProvider, Optional
- **CALLED BY:** Layer3_StateModel.construction.country_state_builder
- **CALLS:** Layer3_StateModel.providers.base_provider, Layer3_StateModel.temporal.temporal_reasoner
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/providers/leaders_provider.py`
- **PURPOSE:** Archigos Leaders Data Provider.
- **INPUT:** data_dir, country_code, date, value
- **OUTPUT:** LeadersProvider, Optional
- **CALLED BY:** Layer3_StateModel.construction.country_state_builder
- **CALLS:** Core.orchestrator.knowledge_port, Layer3_StateModel.providers.base_provider
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/providers/lowy_provider.py`
- **PURPOSE:** Lowy Institute Global Diplomacy Index Provider.
- **INPUT:** data_dir, country_code, date
- **OUTPUT:** LowyProvider, Optional
- **CALLED BY:** Layer3_StateModel.construction.country_state_builder
- **CALLS:** Core.orchestrator.knowledge_port, Layer3_StateModel.providers.base_provider
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/providers/ofac_provider.py`
- **PURPOSE:** OFAC Sanctions Data Provider.
- **INPUT:** data_dir, country_code, date, row
- **OUTPUT:** OFACProvider, Optional, List
- **CALLED BY:** Layer3_StateModel.construction.country_state_builder
- **CALLS:** Core.orchestrator.knowledge_port, Layer3_StateModel.providers.base_provider
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/providers/ports_provider.py`
- **PURPOSE:** World Ports Data Provider.
- **INPUT:** data_dir, country_code, date, value
- **OUTPUT:** PortsProvider, Optional
- **CALLED BY:** Layer3_StateModel.construction.country_state_builder
- **CALLS:** Core.orchestrator.knowledge_port, Layer3_StateModel.providers.base_provider
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/providers/sanctions_provider.py`
- **PURPOSE:** Global Sanctions Data Provider.
- **INPUT:** data_dir, country_code, date, value
- **OUTPUT:** SanctionsProvider, Optional
- **CALLED BY:** Layer3_StateModel.construction.country_state_builder
- **CALLS:** Layer3_StateModel.providers.base_provider
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/providers/sipri_provider.py`
- **PURPOSE:** SIPRI Arms Transfer Data Provider.
- **INPUT:** data_dir, path, index, country_code, date, value, series, target_year, start_year, end_year
- **OUTPUT:** SIPRIProvider, Optional
- **CALLED BY:** Layer3_StateModel.construction.country_state_builder
- **CALLS:** Layer3_StateModel.providers.base_provider
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/providers/state_provider.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** subject_country, target_country, date, force_rag
- **OUTPUT:** StateProvider, StateContext
- **CALLED BY:** Scripts.test_system
- **CALLS:** Layer2_Knowledge.retriever, Layer3_StateModel.construction.country_state_builder, Layer3_StateModel.schemas.state_context
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/providers/ucdp_provider.py`
- **PURPOSE:** UCDP Conflict Data Provider.
- **INPUT:** data_dir, country_code, date, value
- **OUTPUT:** UCDPProvider, Optional
- **CALLED BY:** Layer3_StateModel.construction.country_state_builder
- **CALLS:** Core.orchestrator.knowledge_port, Layer3_StateModel.providers.base_provider
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/providers/vdem_provider.py`
- **PURPOSE:** V-Dem Democracy Data Provider.
- **INPUT:** data_dir, country_code, date, value
- **OUTPUT:** VDemProvider, Optional
- **CALLED BY:** Layer3_StateModel.construction.country_state_builder
- **CALLS:** Layer3_StateModel.providers.base_provider
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/providers/worldbank_provider.py`
- **PURPOSE:** World Bank Economic Data Provider.
- **INPUT:** data_dir, country_code, date, value, series, target_year
- **OUTPUT:** WorldBankProvider, Optional
- **CALLED BY:** Layer3_StateModel.construction.country_state_builder
- **CALLS:** Layer3_StateModel.providers.base_provider
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/relationship_state_builder.py`
- **PURPOSE:** Compatibility shim for Layer3_StateModel.construction.relationship_state_builder.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Core.investigation.research_controller, Core.orchestrator.layer123_pipeline, Tests.run_layer123_behavioral_e2e, Tests.run_layer3_behavioral_sensitivity, Tests.test_layer3_verification_protocol, system_stress_test
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/reliability/__init__.py`
- **PURPOSE:** Measurement reliability layer for Layer-3 state interpretation.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.reliability.signal_belief, Layer3_StateModel.reliability.signal_belief_model
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/reliability/membership_functions.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** value, x, a, b, c, d
- **OUTPUT:** float
- **CALLED BY:** Layer3_StateModel.reliability.signal_belief_model
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/reliability/signal_belief.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** value
- **OUTPUT:** float, SignalBelief
- **CALLED BY:** Layer3_StateModel.reliability, Layer3_StateModel.reliability.signal_belief_model, Layer3_StateModel.schemas.state_context
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/reliability/signal_belief_model.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** root, path, default, value, values, state, store, row, signal, belief
- **OUTPUT:** Any, float, SignalBeliefModel, List, SignalBelief
- **CALLED BY:** Layer3_StateModel.interface.state_provider, Layer3_StateModel.reliability
- **CALLS:** Layer3_StateModel.reliability.membership_functions, Layer3_StateModel.reliability.signal_belief
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/schemas/__init__.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.schemas.state_context
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/schemas/analysis_result.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** EvidenceReference, AnalysisResult, Dict
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/schemas/country_state_schema.py`
- **PURPOSE:** Country State Schema — The Analytical Vector
- **INPUT:** name
- **OUTPUT:** RiskLevel, DimensionScore, CountryStateVector, Dict, Optional
- **CALLED BY:** Layer3_StateModel.construction.country_state_builder
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/schemas/state.py`
- **PURPOSE:** Country State Profile
- **INPUT:** country_code, date, signal_type, signal
- **OUTPUT:** CountryState, Optional, Dict
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.signals.base
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/schemas/state_context.py`
- **PURPOSE:** Layer-3 -> Layer-4 state contract.
- **INPUT:** val, data
- **OUTPUT:** ActorsContext, MilitaryContext, DiplomaticContext, EconomicContext, DomesticContext, CapabilityIndicators, MetaContext, TemporalContext, EvidenceContext, StateContext, str, Dict
- **CALLED BY:** Layer3_StateModel.interface.state_provider, Layer3_StateModel.providers.state_provider, Layer3_StateModel.schemas, Layer4_Analysis.council_session, Layer4_Analysis.evidence.evidence_tracker, Layer4_Analysis.evidence.fuzzy_state_interpreter, Layer4_Analysis.evidence.signal_mapper, Layer4_Analysis.layer4_unified_pipeline, Layer4_Analysis.ministers, Scripts.debug_imports, Scripts.manual_test_anomaly, Scripts.run_anomaly_check, Scripts.run_evaluation, Scripts.run_validation_suite, Scripts.test_coordinator_anomaly
- **CALLS:** Layer3_StateModel.reliability.signal_belief
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/scoring/__init__.py`
- **PURPOSE:** Layer3 phase package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/scoring/confidence_calculator.py`
- **PURPOSE:** Confidence Calculator — The Master Gate
- **INPUT:** old_confidence, new_information, existing_information, weights, observations, reference_date, report
- **OUTPUT:** ConfidenceReport, ConfidenceCalculator, float, Dict, tuple, str, List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.orchestrator.knowledge_port, Layer3_StateModel.source_weighting, Layer3_StateModel.validation.contradiction_engine, Layer3_StateModel.validation.corroboration_engine, Layer3_StateModel.validation.freshness_model, contracts.observation
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/scoring/evidence_gate.py`
- **PURPOSE:** Evidence sufficiency gate.
- **INPUT:** documents, required_evidence, claims, claim_constraints, min_independent_sources, max_age_days, req, value, predicate, claim_text, constraints, docs
- **OUTPUT:** EvidenceGateResult, EvidenceGate, bool, Dict, str, List, float
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/source_weighting.py`
- **PURPOSE:** Compatibility shim for Layer3_StateModel.credibility.source_weighting.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Layer3_StateModel.scoring.confidence_calculator
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/state.py`
- **PURPOSE:** Compatibility shim for Layer3_StateModel.schemas.state.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Tests.test_comprehensive_audit, Tests.test_post_restructuring, Tests.test_signal_layer
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/temporal/__init__.py`
- **PURPOSE:** Layer3 phase package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** Core.wrappers, Tests.test_all_features, Tests.test_pipeline_first, Tests.verify_pipeline
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/temporal/freshness_model.py`
- **PURPOSE:** Freshness Model — Evidence Recency Weighting
- **INPUT:** half_lives, obs, reference_date, observations, min_score, score, event_date, source
- **OUTPUT:** FreshnessScore, FreshnessScorer, Dict, List, str, float
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** contracts.observation
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/temporal/precursor_monitor.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** state_context
- **OUTPUT:** PrecursorMonitor, Dict
- **CALLED BY:** Layer3_StateModel.interface.state_provider
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/temporal/temporal_reasoner.py`
- **PURPOSE:** Temporal Reasoner — The Time Engine
- **INPUT:** rules, source, days_ago, fact_date, reference_date, record, records, scores, timeline_points, metrics, threshold, observations
- **OUTPUT:** DocumentStatus, DecayRule, TemporalRecord, TemporalReasoner, float, bool, List, Dict
- **CALLED BY:** Layer3_StateModel.providers.gdelt_provider
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Layer3_StateModel/temporal/temporal_retriever.py`
- **PURPOSE:** Temporal Retriever - Time-Aware Retrieval System
- **INPUT:** query, documents, context, doc, date_str
- **OUTPUT:** TemporalScope, TemporalContext, TemporalRetriever, List, Optional, str, Dict
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/temporal/temporal_timeline.py`
- **PURPOSE:** Dynamic Temporal Memory - Timeline Integration for Neo4j
- **INPUT:** timestamp, reference, neo4j_driver, node, query, as_of_date, include_historical, node_id, sources, source, date_str, src1
- **OUTPUT:** TemporalStatus, TemporalNode, TemporalGraphManager, bool, float, str, Tuple, Optional, List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/temporal/timeline_manager.py`
- **PURPOSE:** Timeline Manager - Dynamic Event Units (DEU)
- **INPUT:** check_date, from_date, deu, text, event1, event2, query_date, jurisdiction, event_type, include_expired, topic, as_of_date
- **OUTPUT:** TemporalRelation, DynamicEventUnit, TimelineManager, bool, timedelta, str, Optional, List, Dict, Tuple
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/temporal_reasoner.py`
- **PURPOSE:** Compatibility shim for Layer3_StateModel.temporal.temporal_reasoner.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Tests.test_comprehensive_audit, Tests.test_layer3_verification_protocol, Tests.test_post_restructuring, Tests.test_temporal
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/temporal_retriever.py`
- **PURPOSE:** Compatibility shim for Layer3_StateModel.temporal.temporal_retriever.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/temporal_timeline.py`
- **PURPOSE:** Compatibility shim for Layer3_StateModel.temporal.temporal_timeline.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Tests.test_post_restructuring
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/timeline_manager.py`
- **PURPOSE:** Compatibility shim for Layer3_StateModel.temporal.timeline_manager.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/validation/__init__.py`
- **PURPOSE:** Validation components for Layer-3 state modeling.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/validation/confidence_calculator.py`
- **PURPOSE:** Compatibility shim for Layer3_StateModel.scoring.confidence_calculator.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Core.investigation.research_controller, Layer3_StateModel.construction.relationship_state_builder, Tests.test_confidence_update, Tests.test_confidence_update_benchmark, Tests.test_layer3_verification_protocol, Tests.test_reasoning_safety
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/validation/contradiction_engine.py`
- **PURPOSE:** Compatibility shim for Layer3_StateModel.credibility.contradiction_engine.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Layer3_StateModel.scoring.confidence_calculator, Layer4_Analysis.support_models.country_model.intent_capability_model, Tests.test_layer3_verification_protocol, Tests.test_reasoning_safety
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/validation/corroboration_engine.py`
- **PURPOSE:** Compatibility shim for Layer3_StateModel.credibility.corroboration_engine.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Layer3_StateModel.credibility.source_weighting, Layer3_StateModel.scoring.confidence_calculator, Tests.test_reasoning_safety
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer3_StateModel/validation/freshness_model.py`
- **PURPOSE:** Compatibility shim for Layer3_StateModel.temporal.freshness_model.
- **INPUT:** name
- **OUTPUT:** None explicit
- **CALLED BY:** Layer3_StateModel.credibility.source_weighting, Layer3_StateModel.scoring.confidence_calculator, Tests.test_reasoning_safety
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/__init__.py`
- **PURPOSE:** Layer4 Analysis — Council of Ministers
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** Layer4_Analysis.support_models
- **CALLS:** Layer4_Analysis.coordinator, Layer4_Analysis.council_session, Layer4_Analysis.report_generator
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/coordinator.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** Config.pipeline, Layer4_Analysis, Layer4_Analysis.core.coordinator, Layer4_Analysis.core.unified_pipeline, Layer4_Analysis.layer4_unified_pipeline, Scripts.debug_imports, Scripts.manual_test_anomaly, Scripts.run_anomaly_check, Scripts.run_evaluation, Scripts.run_validation_suite, Scripts.test_coordinator_anomaly, Scripts.test_phase4, Scripts.test_system, Scripts.test_validation_suite, Scripts.trace_generator
- **CALLS:** None
- **CRITICALITY:** reasoning

**FILE:** `Layer4_Analysis/core/__init__.py`
- **PURPOSE:** Layer4 phase package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/core/coordinator.py`
- **PURPOSE:** Backwards‑compatibility shim.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** API.main, Tests.run_counterfactual_grounding, Tests.test_counterfactual, Tests.test_layer4_council_sensitivity, Tests.test_layer4_risk_monitors, Tests.test_layer4_runtime_gate, run_council, test_architecture_validation
- **CALLS:** Layer4_Analysis.coordinator
- **CRITICALITY:** reasoning

**FILE:** `Layer4_Analysis/core/council_session.py`
- **PURPOSE:** Backwards‑compatibility shim.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** Tests.test_layer4_runtime_gate
- **CALLS:** Layer4_Analysis.council_session
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/core/llm_client.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** model, url, system_prompt, user_prompt, temperature, timeout, json_mode, query_type, prompt, n_samples, chunk_size
- **OUTPUT:** LocalLLM, AsyncLLMClient, str, float, Tuple, AsyncIterator, Dict
- **CALLED BY:** API.main, Config.pipeline, Core.wrappers, Layer4_Analysis.deliberation.red_team, Layer4_Analysis.hypothesis.mcts, Layer4_Analysis.hypothesis.perspective_agent, Layer4_Analysis.ministers, Layer4_Analysis.safety.guard, Scripts.test_llm, Tests.test_ollama
- **CALLS:** Config.config
- **CRITICALITY:** core

**FILE:** `Layer4_Analysis/core/unified_pipeline.py`
- **PURPOSE:** Unified Pipeline facade used by the API layer.
- **INPUT:** query, **kwargs, user_id, session_id, **flags, scope, flags
- **OUTPUT:** PipelineResult, UnifiedPipeline
- **CALLED BY:** Config.pipeline, test_architecture_validation, test_grounding_validation, test_user_query
- **CALLS:** Config.pipeline, Layer3_StateModel.interface.state_provider, Layer4_Analysis.coordinator, Layer4_Analysis.intake.analyst_input_builder, Layer4_Analysis.intake.question_scope_checker
- **CRITICALITY:** core

**FILE:** `Layer4_Analysis/council_session.py`
- **PURPOSE:** The Council Session.
- **INPUT:** report, hypothesis, phase
- **OUTPUT:** SessionStatus, MinisterReport, CouncilSession, Optional, str
- **CALLED BY:** Layer4_Analysis, Layer4_Analysis.core.council_session, Layer4_Analysis.decision.confidence_calculator, Layer4_Analysis.decision.threat_synthesizer, Layer4_Analysis.investigation.anomaly_sentinel, Layer4_Analysis.layer4_unified_pipeline, Layer4_Analysis.ministers, Layer4_Analysis.report_generator, Scripts.debug_imports, Scripts.manual_test_anomaly, Scripts.run_anomaly_check, Scripts.run_evaluation, Scripts.run_validation_suite, Scripts.test_coordinator_anomaly, Scripts.test_phase4
- **CALLS:** Layer3_StateModel.schemas.state_context, Layer4_Analysis.reasoning_phase, Layer4_Analysis.schema
- **CRITICALITY:** core

**FILE:** `Layer4_Analysis/decision/__init__.py`
- **PURPOSE:** Layer4 phase package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** reasoning

**FILE:** `Layer4_Analysis/decision/confidence_calculator.py`
- **PURPOSE:** Confidence Calculator.
- **INPUT:** reports, state_confidence
- **OUTPUT:** ConfidenceCalculator, float
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer4_Analysis.council_session
- **CRITICALITY:** reasoning

**FILE:** `Layer4_Analysis/decision/refiner.py`
- **PURPOSE:** Conflict Resolution & Refiner Agent
- **INPUT:** sources, content1, content2, src1, src2, conflicts
- **OUTPUT:** ConflictType, ConflictPair, RefinementResult, RefinerAgent, List, Optional, Dict, str
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** reasoning

**FILE:** `Layer4_Analysis/decision/refusal_engine.py`
- **PURPOSE:** Refusal & Uncertainty Manager - ICE Method Implementation
- **INPUT:** thresholds, query, sources, answer, retrieval_scores, faithfulness_score, temporal_conflicts, constraints, warnings, assessment, original_answer, reason
- **OUTPUT:** RefusalReason, EscalationLevel, ConfidenceAssessment, RefusalEngine, bool, float, Dict, str
- **CALLED BY:** Core.wrappers
- **CALLS:** None
- **CRITICALITY:** safety

**FILE:** `Layer4_Analysis/decision/threat_synthesizer.py`
- **PURPOSE:** Threat synthesizer driven by fused evidence (state signals + minister support).
- **INPUT:** sensor_score, rag_score, score, token, state_context, minister_reports, reports, observed_signals, status
- **OUTPUT:** StrategicStatus, str, ThreatSynthesizer, float, AssessmentReport, ThreatLevel
- **CALLED BY:** Scripts.test_threat_synthesis_unit
- **CALLS:** Layer4_Analysis.council_session, Layer4_Analysis.schema, layer4_reasoning.signal_ontology
- **CRITICALITY:** reasoning

**FILE:** `Layer4_Analysis/decision/verifier.py`
- **PURPOSE:** Groundedness Scoring & Verification Agent
- **INPUT:** llm_client, answer, sentence, claim, sources, text, hypothesis_details, state_context, signal, predicted_signals, path, default
- **OUTPUT:** Claim, VerificationResult, Verifier, FullVerifier, List, bool, Tuple, Dict, float
- **CALLED BY:** Scripts.debug_imports, Tests.test_layer4_council_sensitivity, test_architecture_validation, test_grounding_validation
- **CALLS:** Config.thresholds, Layer4_Analysis.evidence.signal_ontology, layer4_reasoning.signal_ontology
- **CRITICALITY:** verification

**FILE:** `Layer4_Analysis/deliberation/__init__.py`
- **PURPOSE:** Layer4 phase package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** reasoning

**FILE:** `Layer4_Analysis/deliberation/cove.py`
- **PURPOSE:** Chain-of-Verification (CoVe) Module - Industrial Grade
- **INPUT:** k, claim, source, confidence, threshold, text, retriever, llm_client, engram_store, query, initial_draft, sources
- **OUTPUT:** VerificationState, AtomicClaim, FactCheckQuestion, RRFScore, CoVeResult, EngramStore, ChainOfVerification, float, Tuple, List, str, Set
- **CALLED BY:** Core.wrappers
- **CALLS:** None
- **CRITICALITY:** verification

**FILE:** `Layer4_Analysis/deliberation/crag.py`
- **PURPOSE:** Corrective RAG (CRAG) Logic
- **INPUT:** query, documents, context, retriever, web_search, retrieved_docs, original_docs, docs
- **OUTPUT:** RetrievalQuality, CRAGAction, CRAGResult, CRAGEngine, Tuple, Optional, List, str, Dict
- **CALLED BY:** Core.wrappers
- **CALLS:** None
- **CRITICALITY:** reasoning

**FILE:** `Layer4_Analysis/deliberation/debate_orchestrator.py`
- **PURPOSE:** MADAM-RAG: Multi-Agent Debate for Ambiguity and Misinformation
- **INPUT:** retriever, llm_client, query, sources, perspectives, max_rounds, perspective, agents, source_partitions, previous_rounds, agent, pos1
- **OUTPUT:** DebateOutcome, GeopoliticalPerspective, DebateAgent, DebateRound, DebateOutcomeReport, MADAMRAGOrchestrator, List, Dict, str, bool, float
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** reasoning

**FILE:** `Layer4_Analysis/deliberation/red_team.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** state_context, draft_answer, draft, evidence, critique
- **OUTPUT:** RedTeamAgent, List, Tuple, str
- **CALLED BY:** Core.wrappers, test_architecture_validation
- **CALLS:** Layer4_Analysis.core.llm_client
- **CRITICALITY:** reasoning

**FILE:** `Layer4_Analysis/evidence/__init__.py`
- **PURPOSE:** Layer4 phase package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/evidence/evidence_requirements.py`
- **PURPOSE:** Canonical evidence requirements for Layer-4 hypothesis testing.
- **INPUT:** name, hypothesis
- **OUTPUT:** str, List
- **CALLED BY:** Layer4_Analysis.evidence.gap_analyzer
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/evidence/evidence_tracker.py`
- **PURPOSE:** Evidence Tracker Module.
- **INPUT:** signal_set, canonical, legacy, ctx, state_context_dict, signal_name
- **OUTPUT:** Set, bool
- **CALLED BY:** Scripts.debug_tracker, Tests.test_layer4_kgi_engine
- **CALLS:** Layer3_StateModel.schemas.state_context, Layer4_Analysis.evidence.fuzzy_state_interpreter, Layer4_Analysis.evidence.signal_mapper, Layer4_Analysis.evidence.signal_ontology
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/evidence/fuzzy_state_interpreter.py`
- **PURPOSE:** Fuzzy state interpreter for the Layer-4 evidence bridge.
- **INPUT:** value, default, state, score, keys
- **OUTPUT:** float, Optional, str, FuzzyStateInterpreter, Dict
- **CALLED BY:** Layer4_Analysis.evidence.evidence_tracker, Layer4_Analysis.evidence.signal_ontology
- **CALLS:** Layer3_StateModel.schemas.state_context, layer4_reasoning.fuzzy.geopolitical_sets
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/evidence/gap_analyzer.py`
- **PURPOSE:** Knowledge-gap analyzer for hypothesis evidence coverage.
- **INPUT:** hypothesis, observed_signals, coverage
- **OUTPUT:** GapAnalyzer, Dict, str
- **CALLED BY:** Tests.test_layer4_kgi_engine
- **CALLS:** Layer4_Analysis.evidence.evidence_requirements
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/evidence/provenance.py`
- **PURPOSE:** Provenance Manager - Industrial Grade
- **INPUT:** leaf_id, content, algorithm, data, signature_info, answer, sources, metadata, response, action, details, claim
- **OUTPUT:** ClaimProvenance, CausalNode, CausalChainDAG, ProvenanceManager, Dict, List, str, bool
- **CALLED BY:** Utils.verify_pipeline
- **CALLS:** LAYER1_COLLECTION.ingestion.feeder.utils
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/evidence/signal_mapper.py`
- **PURPOSE:** Signal Mapper Logic.
- **INPUT:** ctx, signal_name
- **OUTPUT:** bool
- **CALLED BY:** Layer4_Analysis.evidence.evidence_tracker
- **CALLS:** Layer3_StateModel.schemas.state_context, Layer4_Analysis.evidence.signal_ontology
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/evidence/signal_ontology.py`
- **PURPOSE:** Canonical Layer-4 signal ontology.
- **INPUT:** value, signal, interpreted_state, state, threshold, values, allowed, max_items, minister_name
- **OUTPUT:** float, Dict, bool, Optional, List, str
- **CALLED BY:** Layer4_Analysis.decision.verifier, Layer4_Analysis.evidence.evidence_tracker, Layer4_Analysis.evidence.signal_mapper, Layer4_Analysis.investigation.investigation_controller, Layer4_Analysis.investigation.investigation_request, layer4_reasoning.signal_ontology
- **CALLS:** Layer4_Analysis.evidence.fuzzy_state_interpreter
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/fuzzy.py`
- **PURPOSE:** Lightweight fuzzy membership helpers for Layer-4 signal interpretation.
- **INPUT:** x, a, b, c, d, low, high
- **OUTPUT:** float
- **CALLED BY:** layer4_reasoning.signal_ontology
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/hypothesis/__init__.py`
- **PURPOSE:** Layer4 phase package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/hypothesis/causal.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** graph_manager, query, intervention, target, start_node, end_node, max_hops, queries
- **OUTPUT:** CausalInferenceEngine, Optional, str, List
- **CALLED BY:** Core.wrappers
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/hypothesis/mcts.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** state, parent, action, exploration_weight, max_depth, state_context, node, reward, root, initial_query, iterations, depth
- **OUTPUT:** MCTSNode, MCTSRAGAgent, bool, float, List, str, Dict
- **CALLED BY:** Core.wrappers
- **CALLS:** Layer4_Analysis.core.llm_client
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/hypothesis/optimizer.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** train_examples, query, context
- **OUTPUT:** DiplomaticSignature, DSPyOptimizer, str
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/hypothesis/perspective_agent.py`
- **PURPOSE:** Multi-Perspective Simulation Agent - Mixture-of-Agents (MoA) Debate Loop
- **INPUT:** voice, llm_client, state_context, minister_prompts, allowed_signals, raw, value, payload, minister_ids, query, context, other_positions
- **OUTPUT:** Perspective, AgentVoice, DebatePoint, DebateResult, PerspectiveAgent, DebateOrchestrator, SimulationRunner, Dict, Optional, List, float, str
- **CALLED BY:** test_architecture_validation
- **CALLS:** Layer4_Analysis.core.llm_client
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/intake/__init__.py`
- **PURPOSE:** Layer4 phase package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/intake/analyst_input_builder.py`
- **PURPOSE:** Build structured Layer-4 analyst input from Layer-3 state objects.
- **INPUT:** question, country_state, relationship_state, confidence, state, value
- **OUTPUT:** AnalystInputBundle, Dict, str
- **CALLED BY:** Layer4_Analysis.core.unified_pipeline, Scripts.test_validation_suite, Tests.test_layer4_scope_and_input, run_council
- **CALLS:** Layer3_StateModel.interface.state_provider, Layer4_Analysis.intake.question_scope_checker
- **CRITICALITY:** core

**FILE:** `Layer4_Analysis/intake/playbooks.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** query, playbooks, answer
- **OUTPUT:** PlaybookStore, List, Dict
- **CALLED BY:** Core.wrappers
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/intake/question_scope_checker.py`
- **PURPOSE:** Layer-4 question scope control.
- **INPUT:** question
- **OUTPUT:** ScopeCheckResult, Dict
- **CALLED BY:** API.main, Core.wrappers, Layer4_Analysis.core.unified_pipeline, Layer4_Analysis.intake.analyst_input_builder, Tests.debug_scope, Tests.test_layer4_scope_and_input
- **CALLS:** None
- **CRITICALITY:** safety

**FILE:** `Layer4_Analysis/interfaces/__init__.py`
- **PURPOSE:** Layer4 phase package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/investigation/__init__.py`
- **PURPOSE:** Layer4 phase package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/investigation/anomaly_sentinel.py`
- **PURPOSE:** Anomaly Sentinel.
- **INPUT:** session, observed_signals, coverage
- **OUTPUT:** AnomalySentinel, bool
- **CALLED BY:** Tests.test_layer4_risk_monitors
- **CALLS:** Layer4_Analysis.council_session
- **CRITICALITY:** safety

**FILE:** `Layer4_Analysis/investigation/deception_monitor.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** state_context
- **OUTPUT:** DeceptionMonitor, Dict
- **CALLED BY:** Tests.test_layer4_risk_monitors
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/investigation/hitl.py`
- **PURPOSE:** Human-in-the-Loop (HITL) Intervention Layer
- **INPUT:** confidence_getter, min_confidence, config, query, proposed_response, confidence, sources, conflicts, intervention_type, reason, urgent, request_id
- **OUTPUT:** InterventionType, InterventionStatus, InterventionRequest, HITLConfig, HITLManager, InterventionRejectedException, tuple, bool, List, Optional, Dict
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/investigation/investigation_controller.py`
- **PURPOSE:** Knowledge-gap driven investigation controller (collection tasking mode).
- **INPUT:** retriever, extractor, gap_result, predicted_signals, belief_map, threshold, missing_signals, question, hypothesis, discriminatory_signals, max_queries, docs
- **OUTPUT:** InvestigationController, bool, List
- **CALLED BY:** Tests.test_layer4_kgi_engine
- **CALLS:** Layer4_Analysis.evidence.signal_ontology, Layer4_Analysis.investigation.investigation_request, layer4_reasoning.signal_queries
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/investigation/investigation_request.py`
- **PURPOSE:** Structured investigation task request emitted by Layer-4.
- **INPUT:** session, question, missing_signals, max_queries, reason
- **OUTPUT:** InvestigationReason, InvestigationRequest, List, Dict
- **CALLED BY:** Layer4_Analysis.investigation.investigation_controller, Tests.test_layer4_kgi_engine, test_architecture_validation
- **CALLS:** Layer4_Analysis.evidence.signal_ontology, layer4_reasoning.signal_queries
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/investigation_request.py`
- **PURPOSE:** The Investigation Request.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** InvestigationRequest
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/layer4_unified_pipeline.py`
- **PURPOSE:** Layer-4 Unified Execution Pipeline
- **INPUT:** query, state_context, **kwargs, user_id, enable_red_team, max_investigation_loops, session_id
- **OUTPUT:** Layer4UnifiedPipeline, Layer4PipelineFactory, Dict
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.schemas.state_context, Layer4_Analysis.coordinator, Layer4_Analysis.council_session, Layer4_Analysis.schema
- **CRITICALITY:** core

**FILE:** `Layer4_Analysis/ministers.py`
- **PURPOSE:** The Council of Ministers.
- **INPUT:** root, path, default, value, name, ctx, state_context, predicted, confidence, allowed_signals, raw, values
- **OUTPUT:** Any, float, str, bool, BaseMinister, SecurityMinister, EconomicMinister, DomesticMinister, DiplomaticMinister, StrategyMinister, AllianceMinister, Optional
- **CALLED BY:** Scripts.debug_imports, Tests.test_layer4_execution_contract
- **CALLS:** Layer3_StateModel.schemas.state_context, Layer4_Analysis.core.llm_client, Layer4_Analysis.council_session, Layer4_Analysis.schema, layer4_reasoning.signal_ontology
- **CRITICALITY:** reasoning

**FILE:** `Layer4_Analysis/reasoning_phase.py`
- **PURPOSE:** Deterministic Layer-4 reasoning phases.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** ReasoningPhase
- **CALLED BY:** Layer4_Analysis.council_session, test_state_machine
- **CALLS:** None
- **CRITICALITY:** reasoning

**FILE:** `Layer4_Analysis/report_generator.py`
- **PURPOSE:** Report Generator.
- **INPUT:** evidence, index, session, provenance, signals, score
- **OUTPUT:** str, Dict, Tuple
- **CALLED BY:** Layer4_Analysis, Scripts.test_phase4
- **CALLS:** Layer4_Analysis.council_session
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/safety/__init__.py`
- **PURPOSE:** Layer4 phase package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** safety

**FILE:** `Layer4_Analysis/safety/guard.py`
- **PURPOSE:** Llama Guard Integration for IND-Diplomat
- **INPUT:** content, role, response
- **OUTPUT:** SafetyCategory, LlamaGuard, Dict, bool
- **CALLED BY:** API.main, Core.wrappers, Tests.test_components
- **CALLS:** Layer4_Analysis.core.llm_client
- **CRITICALITY:** safety

**FILE:** `Layer4_Analysis/safety/safeguards.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** state_valid, anomaly_detected, user_input, draft_answer, ground_truth_db, answer, context, threshold, user_claim, internal_data, external_api_data, query
- **OUTPUT:** bool, SafeguardAgent, Tuple, str, float
- **CALLED BY:** Tests.test_components
- **CALLS:** None
- **CRITICALITY:** safety

**FILE:** `Layer4_Analysis/schema.py`
- **PURPOSE:** Layer-4 Analysis Schemas.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** ThreatLevel, Hypothesis, AssessmentReport
- **CALLED BY:** Layer4_Analysis.council_session, Layer4_Analysis.decision.threat_synthesizer, Layer4_Analysis.layer4_unified_pipeline, Layer4_Analysis.ministers, Scripts.manual_test_anomaly, Scripts.run_evaluation, Scripts.run_validation_suite, Scripts.test_coordinator_anomaly, Tests.test_layer4_execution_contract
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Layer4_Analysis/support_models/__init__.py`
- **PURPOSE:** Layer-4 support models.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer4_Analysis
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/support_models/context/__init__.py`
- **PURPOSE:** Context support models.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/support_models/context/baseline_model.py`
- **PURPOSE:** Baseline Model — Country Behavior Normalization
- **INPUT:** baselines, country, dimension, observed, observed_scores, min_level
- **OUTPUT:** AnomalyResult, BaselineModel, Dict, List, bool
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/support_models/country_model/__init__.py`
- **PURPOSE:** Country-model support models.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/support_models/country_model/intent_capability_model.py`
- **PURPOSE:** Intent vs Capability Model — The Dual-Channel Analyzer
- **INPUT:** obs, intent, capability, country, observations, date, legal_signal_pack, intent_obs, capability_obs, legitimacy, legal_signal_count
- **OUTPUT:** SignalChannel, IntentCapabilityProfile, str, IntentCapabilityModel, Dict, bool, tuple, float, Tuple
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.validation.contradiction_engine, contracts.observation
- **CRITICALITY:** unused

**FILE:** `Layer4_Analysis/support_models/investigation_outcome.py`
- **PURPOSE:** Investigation outcome classification for post-research updates.
- **INPUT:** new_information, contradictions, question
- **OUTPUT:** str, Dict
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `layer4_reasoning/__init__.py`
- **PURPOSE:** Layer-4 reasoning package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `layer4_reasoning/fuzzy/__init__.py`
- **PURPOSE:** Fuzzy logic helpers for Layer-4 geopolitical reasoning.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `layer4_reasoning/fuzzy/geopolitical_sets.py`
- **PURPOSE:** Geopolitical fuzzy membership sets.
- **INPUT:** x
- **OUTPUT:** float
- **CALLED BY:** Layer4_Analysis.evidence.fuzzy_state_interpreter
- **CALLS:** layer4_reasoning.fuzzy.membership
- **CRITICALITY:** unused

**FILE:** `layer4_reasoning/fuzzy/membership.py`
- **PURPOSE:** Core fuzzy membership primitives.
- **INPUT:** value, x, a, b, c, d
- **OUTPUT:** float, FuzzySet
- **CALLED BY:** layer4_reasoning.fuzzy.geopolitical_sets
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `layer4_reasoning/investigation/__init__.py`
- **PURPOSE:** Signal-driven investigation helpers.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `layer4_reasoning/investigation/signal_queries.py`
- **PURPOSE:** Compatibility shim for signal query mappings.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** layer4_reasoning.signal_queries
- **CRITICALITY:** unused

**FILE:** `layer4_reasoning/signal_ontology.py`
- **PURPOSE:** Layer-4 signal ontology with fuzzy (graded) signal strengths.
- **INPUT:** root, path, default, value, full_scale, state, output, predicted_signals, state_context
- **OUTPUT:** Any, float, Dict, str
- **CALLED BY:** Layer4_Analysis.decision.threat_synthesizer, Layer4_Analysis.decision.verifier, Layer4_Analysis.ministers
- **CALLS:** Layer4_Analysis.evidence.signal_ontology, Layer4_Analysis.fuzzy
- **CRITICALITY:** unused

**FILE:** `layer4_reasoning/signal_queries.py`
- **PURPOSE:** Signal-to-collection query mappings for investigation tasking.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** Layer4_Analysis.investigation.investigation_controller, Layer4_Analysis.investigation.investigation_request, layer4_reasoning.investigation.signal_queries
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Layer5/__init__.py`
- **PURPOSE:** Layer-5 explanation utilities.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer5.explainer
- **CRITICALITY:** unused

**FILE:** `Layer5/explainer.py`
- **PURPOSE:** Final explanation layer.
- **INPUT:** root, path, default, value, signals, status, state
- **OUTPUT:** Any, float, str
- **CALLED BY:** Layer5
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `merge_docs.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `moltbot/__init__.py`
- **PURPOSE:** MoltBot namespace package.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `moltbot/search.py`
- **PURPOSE:** MoltBot query task runner.
- **INPUT:** queries, required_evidence, countries, missing_gaps, per_query_limit
- **OUTPUT:** Dict
- **CALLED BY:** Core.investigation.research_controller
- **CALLS:** LAYER1_COLLECTION.api.moltbot_agent
- **CRITICALITY:** unused

**FILE:** `run_council.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** raw_sources, question, sources, result, args, query, top_k
- **OUTPUT:** _NoopRetriever, List, Dict, int, argparse.ArgumentParser
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer4_Analysis.core.coordinator, Layer4_Analysis.intake.analyst_input_builder
- **CRITICALITY:** core

**FILE:** `run_verify.py`
- **PURPOSE:** Unified verification runner for architecture, RAG memory, and MoltBot gates.
- **INPUT:** script, env, args, display_name, protocol_output, results, rag_gate, moltbot_gate, test_name
- **OUTPUT:** SuiteResult, tuple, int, bool
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `schemas/__init__.py`
- **PURPOSE:** Structured output schemas.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** schemas.claim_schema, schemas.legal_signal_schema, schemas.state_schema
- **CRITICALITY:** unused

**FILE:** `schemas/claim_schema.py`
- **PURPOSE:** Pydantic schema for extracted claims.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** ClaimRecord
- **CALLED BY:** Layer2_Knowledge.access_api.knowledge_api, schemas
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `schemas/legal_signal_schema.py`
- **PURPOSE:** Pydantic schema for legal signals.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** LegalSignalRecord
- **CALLED BY:** Layer2_Knowledge.signal_extraction.legal_signal_extractor.extractor, schemas
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `schemas/state_schema.py`
- **PURPOSE:** Pydantic schema for state model outputs.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** StateModelRecord
- **CALLED BY:** ind_diplomat.state.state_builder, schemas
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Scripts/check_dependencies.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Scripts/cli.py`
- **PURPOSE:** CLI Entrypoint for IND-Diplomat
- **INPUT:** path, recursive, use_ocr, persist, output_dir, neo4j_uri, neo4j_user, neo4j_password, query, jurisdiction, fuzzy, limit
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** LAYER1_COLLECTION.ingestion.feeder.service, Layer2_Knowledge.storage.engram_store, Layer2_Knowledge.vector_store, Layer3_StateModel.binding.graph_manager, Utils.tracing
- **CRITICALITY:** core

**FILE:** `Scripts/console_ui.py`
- **PURPOSE:** Knowledge Acquisition Console (Admin Panel)
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Scripts/data_feeder.py`
- **PURPOSE:** Lightweight data feeder runner.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** LAYER1_COLLECTION.ingestion.feeder.scheduler
- **CRITICALITY:** core

**FILE:** `Scripts/debug_imports.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.schemas.state_context, Layer4_Analysis.coordinator, Layer4_Analysis.council_session, Layer4_Analysis.decision.verifier, Layer4_Analysis.ministers
- **CRITICALITY:** unused

**FILE:** `Scripts/debug_moltbot.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** ind_diplomat.moltbot.fetcher
- **CRITICALITY:** unused

**FILE:** `Scripts/debug_sensors.py`
- **PURPOSE:** Debug: why WorldBank/Comtrade sensors fail to load via importlib.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Scripts/debug_tracker.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer4_Analysis.evidence.evidence_tracker
- **CRITICALITY:** unused

**FILE:** `Scripts/feeder_ui.py`
- **PURPOSE:** Lightweight Streamlit UI for the feeder pipeline.
- **INPUT:** data, limit, priority
- **OUTPUT:** Dict, List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** LAYER1_COLLECTION.ingestion.feeder.scheduler
- **CRITICALITY:** unused

**FILE:** `Scripts/fetch_gdelt.py`
- **PURPOSE:** GDELT Fetcher - Production Script
- **INPUT:** url, all_events
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.translators.gdelt_translator
- **CRITICALITY:** unused

**FILE:** `Scripts/fix_imports.py`
- **PURPOSE:** Batch-fix all remaining deleted-shim import paths.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Scripts/get_ollama_models.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Scripts/manual_test_anomaly.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.schemas.state_context, Layer4_Analysis.coordinator, Layer4_Analysis.council_session, Layer4_Analysis.schema
- **CRITICALITY:** unused

**FILE:** `Scripts/run_anomaly_check.py`
- **PURPOSE:** Fast Anomaly Check.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.schemas.state_context, Layer4_Analysis.coordinator, Layer4_Analysis.council_session
- **CRITICALITY:** unused

**FILE:** `Scripts/run_evaluation.py`
- **PURPOSE:** Surgical Evaluation Runner.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.schemas.state_context, Layer4_Analysis.coordinator, Layer4_Analysis.council_session, Layer4_Analysis.schema
- **CRITICALITY:** core

**FILE:** `Scripts/run_validation_suite.py`
- **PURPOSE:** Validation Suite.
- **INPUT:** name, scenario_file, check_func, session, result
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.schemas.state_context, Layer4_Analysis.coordinator, Layer4_Analysis.council_session, Layer4_Analysis.schema
- **CRITICALITY:** core

**FILE:** `Scripts/seed_knowledge_base.py`
- **PURPOSE:** Knowledge Base Seeding Script
- **INPUT:** output_dir, category, source, data, binary_url, max_priority, key, urls
- **OUTPUT:** KnowledgeBaseSeeder, Dict
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** LAYER1_COLLECTION.ingestion.feeder.crawler, Utils.trade_apis
- **CRITICALITY:** unused

**FILE:** `Scripts/sync_vectors.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.storage.engram_store, Layer2_Knowledge.vector_store
- **CRITICALITY:** unused

**FILE:** `Scripts/test_api.py`
- **PURPOSE:** Phase 6: Test API/main.py loads correctly.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** API.main, LAYER1_COLLECTION.app
- **CRITICALITY:** unused

**FILE:** `Scripts/test_coordinator_anomaly.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** MockSentinel, MockSynthesizer
- **OUTPUT:** TestCoordinatorAnomaly
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.schemas.state_context, Layer4_Analysis.coordinator, Layer4_Analysis.council_session, Layer4_Analysis.schema
- **CRITICALITY:** reasoning

**FILE:** `Scripts/test_e2e.py`
- **PURPOSE:** Phase 6: Full end-to-end pipeline test.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Config.pipeline
- **CRITICALITY:** unused

**FILE:** `Scripts/test_imports.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** label, stmt
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Scripts/test_layer2.py`
- **PURPOSE:** Phase 3: Layer 2 Knowledge Pipeline Verification.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.entity_registry, Layer2_Knowledge.knowledge_api, Layer2_Knowledge.multi_index, Layer2_Knowledge.retriever, Layer2_Knowledge.source_registry, Layer2_Knowledge.vector_store
- **CRITICALITY:** unused

**FILE:** `Scripts/test_layer3.py`
- **PURPOSE:** Phase 4: Layer 3 State Model Verification.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.orchestrator.knowledge_port, Layer3_StateModel.construction.analysis_readiness, Layer3_StateModel.construction.country_state_builder, Layer3_StateModel.interface.state_provider, Layer3_StateModel.schemas.state_context
- **CRITICALITY:** unused

**FILE:** `Scripts/test_llm.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Config.config, Layer4_Analysis.core.llm_client
- **CRITICALITY:** unused

**FILE:** `Scripts/test_moltbot_fetcher.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** mock_requests
- **OUTPUT:** TestMoltBotFetcher
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** ind_diplomat.moltbot.fetcher
- **CRITICALITY:** unused

**FILE:** `Scripts/test_phase4.py`
- **PURPOSE:** Test Phase-4 Deliberative Reasoning Logic.
- **INPUT:** *args
- **OUTPUT:** MockTracker
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.schemas.state_context, Layer4_Analysis.coordinator, Layer4_Analysis.council_session, Layer4_Analysis.report_generator
- **CRITICALITY:** unused

**FILE:** `Scripts/test_rag.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.retriever
- **CRITICALITY:** unused

**FILE:** `Scripts/test_renames.py`
- **PURPOSE:** Verify all renamed imports work correctly after the 10/10 cleanup.
- **INPUT:** label, import_fn
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Scripts/test_router.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.interface.state_provider
- **CRITICALITY:** unused

**FILE:** `Scripts/test_search.py`
- **PURPOSE:** Phase 3: Layer 2 search verification.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.knowledge_api
- **CRITICALITY:** unused

**FILE:** `Scripts/test_sensors.py`
- **PURPOSE:** Verify all 3 sensors produce live data.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** LAYER1_COLLECTION
- **CRITICALITY:** unused

**FILE:** `Scripts/test_system.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.providers.state_provider, Layer4_Analysis.coordinator, Layer4_Analysis.council_session
- **CRITICALITY:** unused

**FILE:** `Scripts/test_threat_synthesis_unit.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** TestThreatSynthesizer
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer4_Analysis.council_session, Layer4_Analysis.decision.threat_synthesizer
- **CRITICALITY:** unused

**FILE:** `Scripts/test_validation_suite.py`
- **PURPOSE:** Validation Suite Runner
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.schemas.state_context, Layer4_Analysis.coordinator, Layer4_Analysis.council_session, Layer4_Analysis.intake.analyst_input_builder
- **CRITICALITY:** unused

**FILE:** `Scripts/trace_generator.py`
- **PURPOSE:** Trace Generator.
- **INPUT:** msg
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.schemas.state_context, Layer4_Analysis.coordinator, Layer4_Analysis.council_session
- **CRITICALITY:** unused

**FILE:** `Scripts/verify_rag.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.storage.engram_store, Layer2_Knowledge.vector_store
- **CRITICALITY:** unused

**FILE:** `system_stress_test.py`
- **PURPOSE:** Unified Integration Stress Test (Layer-1 + Layer-2 + Layer-3 only).
- **INPUT:** days, actor, event_type, intensity, event, score, country_a, country_b, events, country, actor_a, actor_b
- **OUTPUT:** StepResult, QAReporter, str, ActionType, ObservationRecord, bool, Dict, int
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.database.models, Core.database.session, Core.orchestrator.knowledge_port, Layer3_StateModel.country_state_builder, Layer3_StateModel.evidence_gate, Layer3_StateModel.relationship_state_builder, contracts.observation
- **CRITICALITY:** unused

**FILE:** `test_architecture_validation.py`
- **PURPOSE:** IND-DIPLOMAT ARCHITECTURE VALIDATION TEST SUITE
- **INPUT:** name, severity, func
- **OUTPUT:** TestResult, TestSuite
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Config.pipeline, LAYER1_COLLECTION.observation, Layer3_StateModel.interface.state_provider, Layer4_Analysis.core.coordinator, Layer4_Analysis.core.unified_pipeline, Layer4_Analysis.council_session, Layer4_Analysis.decision.verifier, Layer4_Analysis.deliberation.red_team, Layer4_Analysis.hypothesis.perspective_agent, Layer4_Analysis.investigation.investigation_request, layer2_extraction.event_parser
- **CRITICALITY:** unused

**FILE:** `test_comprehensive_system.py`
- **PURPOSE:** COMPREHENSIVE SYSTEM TEST SUITE
- **INPUT:** msg, title, verbose, stop_on_error, name, func, *args, **kwargs, root, filepath, module_name, class_name
- **OUTPUT:** Colors, TestManager, SyntaxTests, ImportTests, PipelineTests, LayerTests, StructureTests, ConfigTests, DependencyTests, EdgeCaseTests, List, Tuple
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Config.config, Config.pipeline, Layer2_Knowledge.retriever, Layer3_StateModel.interface.state_provider, Layer4_Analysis.coordinator, layer1_sensors, layer2_extraction.event_parser
- **CRITICALITY:** unused

**FILE:** `test_grounding_validation.py`
- **PURPOSE:** IND-DIPLOMAT GROUNDING VALIDATION TEST
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.interface.state_provider, Layer4_Analysis.core.unified_pipeline, Layer4_Analysis.decision.verifier
- **CRITICALITY:** unused

**FILE:** `test_import.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.country_state_builder
- **CRITICALITY:** unused

**FILE:** `test_import_debug.py`
- **PURPOSE:** Debug import issue with layer1_sensors.ObservationRecord
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** layer1_sensors
- **CRITICALITY:** unused

**FILE:** `test_insert.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.database.models, Core.database.session
- **CRITICALITY:** unused

**FILE:** `test_interceptor.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `test_state_machine.py`
- **PURPOSE:** Test State Machine Execution.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.interface.state_provider, Layer4_Analysis.coordinator, Layer4_Analysis.reasoning_phase
- **CRITICALITY:** unused

**FILE:** `test_user_query.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** query
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer4_Analysis.core.unified_pipeline
- **CRITICALITY:** unused

**FILE:** `Tests/__init__.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Tests/debug_scope.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer4_Analysis.intake.question_scope_checker
- **CRITICALITY:** unused

**FILE:** `Tests/full_pipeline_execution.py`
- **PURPOSE:** End-to-end execution trigger for Layer1 -> Layer2 -> Layer3 coverage tracing.
- **INPUT:** event_id, actor1, actor2, event_code, event_root, goldstein, sql_date
- **OUTPUT:** int
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.debug.pipeline_trace, Core.orchestrator.layer123_pipeline
- **CRITICALITY:** unused

**FILE:** `Tests/manual_live_gdelt_validation.py`
- **PURPOSE:** Generate a manual article-by-article validation sheet from live GDELT data.
- **INPUT:** raw_html, limit, countries, hours_back, events, sample_size, seed, rows, output_dir
- **OUTPUT:** str, List, Path, int
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** LAYER1_COLLECTION.api.GDELT.client, LAYER1_COLLECTION.api.GDELT.parser, LAYER1_COLLECTION.observation
- **CRITICALITY:** unused

**FILE:** `Tests/run_counterfactual_grounding.py`
- **PURPOSE:** Quick runner for counterfactual grounding test.
- **INPUT:** **kw, name, state
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer4_Analysis.core.coordinator
- **CRITICALITY:** unused

**FILE:** `Tests/run_layer123_behavioral_e2e.py`
- **PURPOSE:** Layer1->Layer3 behavioral end-to-end test (no Layer-4, no LLM).
- **INPUT:** days, sql_date, event, value, default, goldstein, min_events, db, raw_events, events, text, path
- **OUTPUT:** StepResult, TestLogger, str, float, Tuple, Dict, List, int
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.database.db, Core.database.models, Core.database.session, Core.orchestrator.knowledge_port, LAYER1_COLLECTION.api.GDELT.client, LAYER1_COLLECTION.api.GDELT.parser, Layer2_Knowledge.action_mapper, Layer2_Knowledge.legal_signal_extractor, Layer3_StateModel.country_state_builder, Layer3_StateModel.evidence_gate, Layer3_StateModel.relationship_state_builder, contracts.observation
- **CRITICALITY:** unused

**FILE:** `Tests/run_layer3_behavioral_sensitivity.py`
- **PURPOSE:** Layer-3 behavioral sensitivity validation.
- **INPUT:** days, events, left, right, country_code, all_events, path, line, title, idx, question, answer
- **OUTPUT:** CaseResult, Reporter, str, List, Dict, Tuple, int
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** LAYER1_COLLECTION.api.GDELT.client, LAYER1_COLLECTION.api.GDELT.parser, Layer3_StateModel.country_state_builder, Layer3_StateModel.relationship_state_builder, contracts.observation
- **CRITICALITY:** unused

**FILE:** `Tests/run_real_council.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** StateContext
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.schemas.state_context, Layer4_Analysis.coordinator, Layer4_Analysis.council_session
- **CRITICALITY:** core

**FILE:** `Tests/test_action_mapper.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** ActionMapperTest
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.action_mapper
- **CRITICALITY:** unused

**FILE:** `Tests/test_all_features.py`
- **PURPOSE:** IND-Diplomat: Comprehensive Feature Test Suite
- **INPUT:** name, func, is_async, reason, mn, cn
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** API.auth, API.main, Core.context, Core.module_base, Core.orchestrator, Core.registry, LAYER1_COLLECTION.app, LAYER1_COLLECTION.ingestion.feeder.service, Layer3_StateModel.temporal, Utils.apis, Utils.edge_cases, core
- **CRITICALITY:** unused

**FILE:** `Tests/test_analysis_readiness.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.analysis_readiness
- **CRITICALITY:** safety

**FILE:** `Tests/test_architecture_boundaries.py`
- **PURPOSE:** Architecture boundary guardrails.
- **INPUT:** path
- **OUTPUT:** Set, ArchitectureBoundariesTest
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Tests/test_assimilation_ingestor_path.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** AssimilationImportTest
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.assimilation.investigation_ingestor
- **CRITICALITY:** unused

**FILE:** `Tests/test_audit_verification.py`
- **PURPOSE:** Post-Implementation Verification Script
- **INPUT:** test_name, condition, detail
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.investigation.gap_detector, Core.orchestrator.knowledge_request, LAYER1_COLLECTION.observation, Layer2_Knowledge.entity_registry, Layer2_Knowledge.source_registry, Layer3_StateModel.graph_manager
- **CRITICALITY:** unused

**FILE:** `Tests/test_bug_fixes_2026.py`
- **PURPOSE:** Bug Fix Verification Tests (2026-02-23)
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Tests/test_case_management.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** CaseManagementTest
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.case_management.case, Core.case_management.case_manager, Core.case_management.case_store
- **CRITICALITY:** unused

**FILE:** `Tests/test_components.py`
- **PURPOSE:** Extended Unit Tests for IND-Diplomat
- **INPUT:** sample_engrams, sample_retrieval_results
- **OUTPUT:** TestEngramStore, TestRRFRetrieval, TestGuardrails, TestExecutorPaths, TestTracing
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer4_Analysis.safety.guard, Layer4_Analysis.safety.safeguards, Utils.tracing
- **CRITICALITY:** unused

**FILE:** `Tests/test_comprehensive_audit.py`
- **PURPOSE:** IND-Diplomat Comprehensive Audit
- **INPUT:** name, condition, detail
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** AGENT_INTERFACE.moltbot_controller, AGENT_INTERFACE.question_parser, Core.orchestrator.analysis_router, Layer2_Knowledge.signals.base, Layer2_Knowledge.translators.gdelt_translator, Layer3_StateModel.construction.country_state_builder, Layer3_StateModel.country_state_schema, Layer3_StateModel.state, Layer3_StateModel.temporal_reasoner, analysis_api.services
- **CRITICALITY:** unused

**FILE:** `Tests/test_confidence_update.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.validation.confidence_calculator
- **CRITICALITY:** unused

**FILE:** `Tests/test_confidence_update_benchmark.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.validation.confidence_calculator
- **CRITICALITY:** unused

**FILE:** `Tests/test_counterfactual.py`
- **PURPOSE:** Counterfactual Grounding Test
- **INPUT:** mobilization, clashes, exercises, hostility, negotiations, alliances, sanctions, trade_dependency, economic_pressure, regime_stability, unrest, protests
- **OUTPUT:** _NoopRetriever, List, Dict
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer4_Analysis.core.coordinator
- **CRITICALITY:** unused

**FILE:** `Tests/test_country_state_builder_formulas.py`
- **PURPOSE:** Deterministic formula checks for CountryStateBuilder.
- **INPUT:** name, condition, detail
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.country_state_builder, Layer3_StateModel.country_state_schema
- **CRITICALITY:** unused

**FILE:** `Tests/test_country_state_recent_shift.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.country_state_builder
- **CRITICALITY:** unused

**FILE:** `Tests/test_evidence_db.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** EvidenceDbTest
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.evidence_db.evidence_query, Core.evidence_db.evidence_store
- **CRITICALITY:** unused

**FILE:** `Tests/test_evidence_gate.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** EvidenceGateTest
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.evidence_gate
- **CRITICALITY:** unused

**FILE:** `Tests/test_ind_diplomat_perception.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** IndDiplomatPerceptionTest
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** ind_diplomat.knowledge.actor_mapper, ind_diplomat.knowledge.doc_classifier, ind_diplomat.knowledge.legal_extractor, ind_diplomat.knowledge.statement_extractor, ind_diplomat.pipeline, ind_diplomat.state.tone_detector
- **CRITICALITY:** unused

**FILE:** `Tests/test_information_value.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.information_value
- **CRITICALITY:** unused

**FILE:** `Tests/test_investigation_gap_detector.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** GapDetectorTest
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.investigation.gap_detector
- **CRITICALITY:** unused

**FILE:** `Tests/test_investigation_outcome.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_Reasoning.investigation_outcome
- **CRITICALITY:** unused

**FILE:** `Tests/test_knowledge_ingestor.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** KnowledgeIngestorTest
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.knowledge_ingestor
- **CRITICALITY:** unused

**FILE:** `Tests/test_layer123_unified_pipeline.py`
- **PURPOSE:** Unified Layer 1/2/3 integration tests.
- **INPUT:** event_id, actor1, actor2, event_code, event_root, goldstein, sql_date
- **OUTPUT:** Dict, Layer123UnifiedPipelineTest
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.orchestrator.layer123_pipeline
- **CRITICALITY:** unused

**FILE:** `Tests/test_layer12_validation_protocol.py`
- **PURPOSE:** Layer-1 + Layer-2 validation protocol.
- **INPUT:** event_id, actor1, actor2, event_code, event_root, goldstein, sql_date, date_added, source_url, action, observations, country_a
- **OUTPUT:** Dict, str, Layer12ValidationProtocolTest
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** LAYER1_COLLECTION.api.moltbot_agent, LAYER1_COLLECTION.observation, Layer2_Knowledge.entity_registry, Layer2_Knowledge.multi_index, Layer2_Knowledge.translators.gdelt_translator, Layer2_Knowledge.treaty_lifecycle, Layer3_StateModel.graph_manager
- **CRITICALITY:** unused

**FILE:** `Tests/test_layer2_cross_layer_boundaries.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** path
- **OUTPUT:** Iterable, List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Tests/test_layer3_layer2_boundary.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** path
- **OUTPUT:** List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Tests/test_layer3_verification_protocol.py`
- **PURPOSE:** Layer-3 verification protocol.
- **INPUT:** obs_id, actor1, actor2, action, event_date, source, source_type, intensity, confidence, signal_fixture, validation_obs, country
- **OUTPUT:** ObservationRecord, SyntheticCountryStateBuilder, EmptyRetriever, FakeMoltBot, Layer3VerificationProtocolTest, Dict, List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.orchestrator.research_controller, LAYER1_COLLECTION.observation, Layer3_Reasoning.country_model.intent_capability_model, Layer3_StateModel.country_state_builder, Layer3_StateModel.evidence_binder, Layer3_StateModel.relationship_state_builder, Layer3_StateModel.temporal_reasoner, Layer3_StateModel.validation.confidence_calculator, Layer3_StateModel.validation.contradiction_engine
- **CRITICALITY:** unused

**FILE:** `Tests/test_layer4_council_sensitivity.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** mobilization, clashes, exercises, hostility, negotiations, alliances, sanctions, trade_dependency, economic_pressure, regime_stability, unrest, protests
- **OUTPUT:** _NoopRetriever, List, Dict
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer4_Analysis.core.coordinator, Layer4_Analysis.decision.verifier
- **CRITICALITY:** unused

**FILE:** `Tests/test_layer4_execution_contract.py`
- **PURPOSE:** Layer-4 Execution Contract Validation Test
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer4_Analysis.coordinator, Layer4_Analysis.council_session, Layer4_Analysis.ministers, Layer4_Analysis.schema
- **CRITICALITY:** unused

**FILE:** `Tests/test_layer4_kgi_engine.py`
- **PURPOSE:** Layer-4 Knowledge-Gap Investigation (KGI) Engine Tests.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** Dict, StateContext
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.schemas.state_context, Layer4_Analysis.council_session, Layer4_Analysis.evidence.evidence_tracker, Layer4_Analysis.evidence.gap_analyzer, Layer4_Analysis.investigation.investigation_controller, Layer4_Analysis.investigation.investigation_request
- **CRITICALITY:** unused

**FILE:** `Tests/test_layer4_layer3_interface_boundary.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** path
- **OUTPUT:** List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Tests/test_layer4_phase_boundaries.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** module_name, path
- **OUTPUT:** Iterable, List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Tests/test_layer4_risk_monitors.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** query, top_k
- **OUTPUT:** _NoopRetriever, Dict, List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.precursor_monitor, Layer4_Analysis.core.coordinator, Layer4_Analysis.investigation.anomaly_sentinel, Layer4_Analysis.investigation.deception_monitor
- **CRITICALITY:** unused

**FILE:** `Tests/test_layer4_runtime_gate.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** count, prompt, system_prompt, query_type
- **OUTPUT:** _DummyLLM, str
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.context, Core.module_base, Core.wrappers, Layer4_Analysis.core.coordinator, Layer4_Analysis.core.council_session
- **CRITICALITY:** unused

**FILE:** `Tests/test_layer4_scope_and_input.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer4_Analysis.intake.analyst_input_builder, Layer4_Analysis.intake.question_scope_checker
- **CRITICALITY:** unused

**FILE:** `Tests/test_layers_1_2.py`
- **PURPOSE:** End-to-End Verification Tests — Layers 1 & 2
- **INPUT:** name, passed, detail
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.orchestrator.query_analyzer, LAYER1_COLLECTION.ingestion.feeder.metadata_extractor, LAYER1_COLLECTION.ingestion.feeder.normalizer, LAYER1_COLLECTION.ingestion.feeder.ocr_parser, LAYER1_COLLECTION.ingestion.feeder.pdf_parser
- **CRITICALITY:** unused

**FILE:** `Tests/test_legal_signal_extractor.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** LegalSignalExtractorTest
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.legal_signal_dictionary, Layer2_Knowledge.legal_signal_extractor.extractor, Layer2_Knowledge.legal_signal_extractor.segmenter, Layer2_Knowledge.legal_signal_extractor.signals
- **CRITICALITY:** unused

**FILE:** `Tests/test_moltbot.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Tests/test_ollama.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer4_Analysis.core.llm_client
- **CRITICALITY:** unused

**FILE:** `Tests/test_pipeline_first.py`
- **PURPOSE:** Pipeline-First Architecture - Integration Test
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** LAYER1_COLLECTION.ingestion.feeder.change_detector, LAYER1_COLLECTION.ingestion.feeder.raw_archive, Layer3_StateModel.temporal, ind_diplomat.knowledge
- **CRITICALITY:** unused

**FILE:** `Tests/test_pipeline_status.py`
- **PURPOSE:** IND-Diplomat Full Pipeline Status Check
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** AGENT_INTERFACE.question_parser, Layer3_StateModel.country_state_builder
- **CRITICALITY:** unused

**FILE:** `Tests/test_post_restructuring.py`
- **PURPOSE:** Post-Restructuring Verification
- **INPUT:** msg, name, condition, detail
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** AGENT_INTERFACE.moltbot_controller, AGENT_INTERFACE.question_parser, Core.orchestrator.analysis_router, Core.orchestrator.query_analyzer, Layer2_Knowledge.retriever, Layer2_Knowledge.signals.base, Layer2_Knowledge.source_registry, Layer2_Knowledge.translators.gdelt_translator, Layer2_Knowledge.treaty_lifecycle, Layer3_StateModel.country_state_builder, Layer3_StateModel.country_state_schema, Layer3_StateModel.state, Layer3_StateModel.temporal_reasoner, Layer3_StateModel.temporal_timeline, analysis_api.services
- **CRITICALITY:** unused

**FILE:** `Tests/test_reasoning_safety.py`
- **PURPOSE:** Phase 12 Verification - Reasoning Safety Mechanisms
- **INPUT:** msg, name, condition, detail, obs_id, source, actors, action, intensity, confidence, event_date, report_date
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** LAYER1_COLLECTION.observation, Layer3_Reasoning.context.baseline_model, Layer3_Reasoning.country_model.intent_capability_model, Layer3_StateModel.validation.confidence_calculator, Layer3_StateModel.validation.contradiction_engine, Layer3_StateModel.validation.corroboration_engine, Layer3_StateModel.validation.freshness_model
- **CRITICALITY:** unused

**FILE:** `Tests/test_signal_deduplicator.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.signal_deduplicator
- **CRITICALITY:** unused

**FILE:** `Tests/test_signal_layer.py`
- **PURPOSE:** Signal Layer Verification Test
- **INPUT:** event_signal
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer2_Knowledge.signals.base, Layer2_Knowledge.translators.gdelt_translator, Layer3_StateModel.state
- **CRITICALITY:** unused

**FILE:** `Tests/test_temporal.py`
- **PURPOSE:** Test the Temporal Reasoner and time-decayed builder.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.country_state_builder, Layer3_StateModel.temporal_reasoner
- **CRITICALITY:** unused

**FILE:** `Tests/verify_pipeline.py`
- **PURPOSE:** Deep Pipeline Connection Verification
- **INPUT:** name, func, message, mp, cn
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Core.orchestrator, Core.registry, Layer3_StateModel.temporal, core
- **CRITICALITY:** unused

**FILE:** `Utils/__init__.py`
- **PURPOSE:** Transformation Layer - PDF and OCR Pipeline.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Utils.parsers
- **CRITICALITY:** unused

**FILE:** `Utils/apis.py`
- **PURPOSE:** External API Clients & Aggregator
- **INPUT:** api_key, reporter, partner, year, member, economy, country_code, claim_text, country
- **OUTPUT:** WTOClient, UNCTADClient, ExternalAggregator, Dict, List
- **CALLED BY:** Tests.test_all_features
- **CALLS:** Utils.edge_cases
- **CRITICALITY:** unused

**FILE:** `Utils/audit.py`
- **PURPOSE:** Audit Trail for IND-Diplomat
- **INPUT:** entry, previous_hash, user_id, action, resource, details, ip_address, user_agent, request_id, response_status, start_date, end_date
- **OUTPUT:** AuditEntry, AuditTrail, str, List, Dict
- **CALLED BY:** API.main
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Utils/cache.py`
- **PURPOSE:** Redis Caching Layer for IND-Diplomat
- **INPUT:** prefix, *args, key, value, ttl, query, results, prompt, response, result
- **OUTPUT:** CacheService, bool, str, Optional, int, Dict
- **CALLED BY:** API.main
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Utils/clean_setup.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** path, names
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Utils/dpdp.py`
- **PURPOSE:** DPDP Act 2023 Compliance Module
- **INPUT:** text, categories, value, rule, data_principal_id, purpose, data_categories, expires_days, consent_id, data_category, right, request_details
- **OUTPUT:** DataCategory, ProcessingPurpose, DataPrincipalRight, ConsentRecord, DataMaskingRule, BreachRecord, DPDPCompliance, Tuple, str, Dict, bool
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Utils/edge_cases.py`
- **PURPOSE:** Premium Edge Case Utilities
- **INPUT:** user_id_param, is_heavy, timeout, fallback, param_name, key, default, config, bucket, user_id, max_age, coro
- **OUTPUT:** RateLimitConfig, RateLimitResult, SmartRateLimiter, TimeoutConfig, TimeoutHandler, ValidationConfig, InputValidator, MemoryConfig, MemoryManager, Dict, Any, str
- **CALLED BY:** Tests.test_all_features, Utils.apis
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Utils/file_manager.py`
- **PURPOSE:** File System Manager for IND-Diplomat
- **INPUT:** base_path, tz_offset_hours, dt, session_id, context_id, filename, source, content, user_id, session_folder, metadata, folder_path
- **OUTPUT:** FileRecord, FileSystemManager, Dict, datetime, str, Path, Tuple, List, Optional, int
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Utils/logger.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** logger, operation_name, name, correlation_id, level, message, extra_data, latency_ms, **kwargs, func, record, *args
- **OUTPUT:** StructuredLogger, JsonFormatter, str
- **CALLED BY:** API.main
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Utils/manager.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** base_path, name, query, profiles
- **OUTPUT:** DossierStore, Optional, List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Utils/observability.py`
- **PURPOSE:** Industrial Observability and Distributed Tracing
- **INPUT:** operation_name, trace_type, export_endpoint, query, session_id, user_id, trace_id, status, final_confidence, input_data, parent_span_id, tags
- **OUTPUT:** TraceType, TraceStatus, TraceSpan, Trace, ObservabilityManager, Dict, str, Optional, List
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Utils/parsers.py`
- **PURPOSE:** Transformation Layer - Multimodal PDF Pipeline
- **INPUT:** api_key, file_path, content, model_name, image_path, visual_context, pdf_path, extract_tables, result, chunk_size, overlap
- **OUTPUT:** ParsedChunk, DocumentParseResult, LlamaParseAdapter, DeepSeekOCRAdapter, TableExtractor, TransformationPipeline, List, str, Tuple
- **CALLED BY:** Utils
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Utils/rbac.py`
- **PURPOSE:** Multi-Tenant RBAC & Data Entitlements
- **INPUT:** permission, user_id, role_id, name, description, clearance, permissions, jurisdictions, document_types, username, email, organization
- **OUTPUT:** ClearanceLevel, Permission, Role, User, DocumentEntitlement, RBACManager, Optional, Set, tuple, List, Dict, EntitlementContext
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Utils/reliability.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** date_str, metadata, sources, query
- **OUTPUT:** ReliabilityScorer, float, Tuple
- **CALLED BY:** Core.wrappers
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Utils/report_generator.py`
- **PURPOSE:** Report Generator for IND-Diplomat
- **INPUT:** report_data, filename, format
- **OUTPUT:** ReportGenerator, Optional
- **CALLED BY:** API.main
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Utils/reset_and_copy.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** path, names
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Utils/search.py`
- **PURPOSE:** Reputational Filter for Trusted Internet Search
- **INPUT:** url, citation_count, days_old, results, min_threshold, max_results, query, search_provider, provider
- **OUTPUT:** DomainTier, SourceReliabilityScore, FilteredSearchResult, ReputationalSearch, float, Tuple, List, Dict
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Utils/session.py`
- **PURPOSE:** Session Memory for IND-Diplomat
- **INPUT:** data, user_id, initial_context, session_id, session, role, content, metadata, last_n, key, value
- **OUTPUT:** Message, Session, SessionManager, Dict, Optional, bool, List
- **CALLED BY:** API.main
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Utils/sync_to_aiiiii_dip.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Utils/tracing.py`
- **PURPOSE:** Structured Tracing for IND-Diplomat
- **INPUT:** operation, **tags, message, phase, **kwargs, span_id, span, tags, func, *args
- **OUTPUT:** TracePhase, TraceSpan, TracingContext, Tracer, Dict, str, Optional
- **CALLED BY:** Scripts.cli, Tests.test_components
- **CALLS:** None
- **CRITICALITY:** core

**FILE:** `Utils/trade_apis.py`
- **PURPOSE:** Multilateral Trade API Clients
- **INPUT:** indicator, **params, reporter, partner, year, country, flow_code, hs_code
- **OUTPUT:** TradeDataPoint, APIClient, WTOClient, UNCTADClient, ComtradeClient, WITSClient, MultilateralAPIHub, List, bool, Dict, Optional
- **CALLED BY:** Scripts.seed_knowledge_base
- **CALLS:** None
- **CRITICALITY:** unused

**FILE:** `Utils/verify_pipeline.py`
- **PURPOSE:** Undocumented module.
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** LAYER1_COLLECTION.ingestion.feeder.service, Layer4_Analysis.evidence.provenance
- **CRITICALITY:** unused

**FILE:** `verify_state_machine.py`
- **PURPOSE:** FINAL VERIFICATION: State Machine Execution with Logging
- **INPUT:** None explicit (module constants/side effects)
- **OUTPUT:** None explicit
- **CALLED BY:** None (entrypoint/isolated/or dynamically invoked)
- **CALLS:** Layer3_StateModel.interface.state_provider, Layer4_Analysis.coordinator
- **CRITICALITY:** unused


---

## 6. DATA FLOW ANALYSIS

### Object: `StateContext`

- Created in `Layer3_StateModel/interface/state_provider.py::build_initial_state`.
- Source inputs: `CountryStateBuilder.build()` outputs (`CountryStateVector`) + optional Layer-2 retrieval metadata.
- Enriched with:
  - `meta` confidence/freshness fields
  - `evidence.signal_provenance`
  - `temporal`
  - `signal_beliefs` via `SignalBeliefModel.build_all(...)`
- Consumed by:
  - ministers (`Layer4_Analysis/ministers.py`)
  - coordinator evidence scoring
  - threat synthesizer
  - verifier (`compute_signal_strengths`)
  - output citation assembly.

### Object: `Hypothesis`

- Created in `Layer4_Analysis/coordinator.py::convene_council` from each `MinisterReport`.
- Fields populated:
  - `predicted_signals`
  - `matched_signals` (belief >= 0.50)
  - `weak_signals` (0.35 <= belief < 0.50)
  - `missing_signals` (belief < 0.35)
  - blended confidence
- Updated through red-team and investigation cycle by session replacement/rebuild.
- Consumed by synthesizer and final report generation.

### Object: `Evidence`

- Provider-stage provenance generated in `state_provider.py` using `ProvenanceTracker` and `Evidence` dataclass.
- Stored in `StateContext.evidence.signal_provenance` and `source_uris`; raw `rag_documents` intentionally suppressed (`rag_documents=[]`) in Layer-4 contract payload.
- Consumed by coordinator for source output/citation indexing (`_collect_output_sources`, `_build_reference_bundle`).

### Object: `Signals`

- Two parallel representations exist:
  - hard extracted set: `extract_signals_from_state(...)` (legacy/deterministic boolean extraction)
  - soft beliefs: `StateContext.signal_beliefs` (new reliability layer)
- Runtime council scoring now uses belief map first; hard extraction remains in verification compatibility path.

### Object: `Verification Score`

- Stage 1: `_verify_claims` sets `session.verification_score = full_verifier.verify(predicted, state_context)`.
- Stage 2: `_run_full_verification` currently deterministic wrapper sets `verification_details.sensor_score` and may overwrite `session.verification_score` in `process_query`.
- Consumed in safety review and final session payload.

---

## 7. REASONING ENGINE ANALYSIS

### Minister Reasoning Mechanics

- Ministers are defined in `Layer4_Analysis/ministers.py`.
- Each minister receives only `StateContext` values (numeric/categorical state variables), not direct documents.
- LLM call path:
  - `LocalLLM.generate(system_prompt, user_prompt, temperature=0, json_mode=True)`.
  - Prompt enforces strict JSON and allowed signal vocabulary.
- Output controls:
  - `_parse_response_json` rejects malformed output.
  - `_normalize_predicted_signals` drops tokens outside ontology or disallowed list.
  - confidence normalized by count of allowed predicted tokens.
- Hallucination control:
  - closed-world signal list
  - deterministic fallback if LLM fails or JSON invalid (`_deterministic_fallback`)
  - downstream structural belief scoring dominates final confidence (65% weight).

### Deterministic Components

- Signal belief generation (`SignalBeliefModel`)
- Evidence matching (`_evaluate_evidence`)
- Conflict trigger threshold (`max-min > 0.5`)
- Investigation low-belief threshold (`<0.35`)
- Threat synthesis domain-weighted sensor fusion
- Safety refusal condition (`should_refuse`).

### Stochastic Components

- Minister raw predicted-signal selection via LLM.
- Potential red-team execution path if `RedTeamAgent` active.

### Net Result

The LLM is constrained to symbolic classification; most outcome control is deterministic and threshold-driven.

---

## 8. VERIFICATION AND SAFETY

### `verifier` (`Layer4_Analysis/decision/verifier.py`)

- `FullVerifier.verify(predicted_signals, state_context)` computes average fuzzy support from `compute_signal_strengths`.
- Activation point: coordinator `VERIFICATION` phase (`_verify_claims`).
- Purpose: deterministic grounding of signal claims against interpreted state.

### `cove` (`Layer4_Analysis/deliberation/cove.py`)

- Implements full chain-of-verification framework (atomic claims, RRF, revisions, refusal logic).
- In current coordinator path, this module is not directly wired into the executed verification flow.
- Classified as verification-capable but presently mostly dormant under audited entrypaths.

### `refusal_engine` equivalent

- Active refusal gate function is `Layer4_Analysis/safety/safeguards.py::should_refuse`.
- Trigger: invalid state or anomaly flag.
- Called via coordinator `_check_refusal_threshold` during `SAFETY_REVIEW` phase.

### Safeguards / safety guardrails

- Input safety: `Layer4_Analysis/safety/guard.py::llama_guard.classify_content` used in API endpoints.
- Scope guard: `Layer4_Analysis/intake/question_scope_checker.py` before runtime analysis.
- Readiness gate: `Layer3_StateModel/construction/analysis_readiness.py` via `build_analyst_input`.

### Anomaly detection

- `Layer4_Analysis/investigation/anomaly_sentinel.py`.
- Trigger condition: high signal volume (`>=4`) plus low coverage (`<0.25`) or contradiction+low coverage condition.
- Effect: marks `black_swan`, forces investigation, can force refusal payload.

### HITL escalation

- Coordinator `_check_hitl_threshold`.
- Trigger: predictive query + high-impact threat + low certainty.
- Output: `needs_human_review=True` in session payload.

---

## 9. INVESTIGATION LOOP

### Active investigation loop (Layer-4)

1. Missing/low-belief signals collected via `_collect_missing_signals`.
2. `InvestigationController.signals_needing_investigation(...)` selects predicted signals with belief `< 0.35`.
3. `_run_investigation_phase` executes:
   - optional CRAG quality check (`Layer4_Analysis.deliberation.crag`)
   - calls `Layer3_StateModel.interface.state_provider.investigate_and_update(...)`
4. `investigate_and_update`:
   - composes targeted query from missing signals
   - retrieves additional docs via `Layer2_Knowledge.retriever.DiplomaticRetriever.hybrid_search`
   - rebuilds `StateContext` with `build_initial_state`
5. Coordinator resets deliberation artifacts and re-enters `INITIAL_DELIBERATION`.
6. Loop bounded by `max_investigation_loops`.

### Parallel legacy investigation stack (present, mostly detached)

- `Core/investigation/research_controller.py`
- `Core/orchestrator/investigation_loop.py`
- `Core/investigation/gap_detector.py` and planner modules

These form a richer bridge stack but are not primary in audited active path.

---

## 10. DEAD CODE & RISK DETECTION

### Dead/Detached Indicators (import-graph + entrypath reachability)

- Audited `.py` files: 471
- Reachable from audited entrypaths: 88
- Not reachable from audited entrypaths: 383
- Modules with no local callers: 255
- Modules with no outgoing local imports: 245

### High-Risk Breakpoints (confirmed)

1. `API/main.py`
   - unresolved runtime symbols in endpoint logic: `unified_pipeline`, `safeguard`, `provenance`, `DiplomaticRetriever`.
   - consequence: endpoint runtime failures despite module import success.

2. `run_council.py`
   - seeds dict as `state_context`; coordinator expects object attributes.
   - consequence: runtime `AttributeError` during process execution.

3. `Layer3_StateModel/interface/state_provider.py`
   - `get_state_context()` references `StateContext.from_any` and `StateContext.from_layer3` not defined in current `state_context.py`.
   - consequence: these helper paths fail when invoked.

4. `LAYER1_COLLECTION/ingestion/feeder/scheduler.py`
   - `_process_article_link` contains typo `if notlink:` (undefined variable).
   - consequence: crawl-time `NameError` on invocation.

5. `Scripts/data_feeder.py`
   - imports `from feeder.scheduler import ingestion_scheduler`; package path mismatch with repo structure.
   - consequence: likely import failure unless environment-specific alias exists.

6. `Scripts/run_evaluation.py`
   - expects `session.king_decision` as formatted multiline string after only `convene_council`; current coordinator populates final decision in `process_query` flow.
   - consequence: stale assumptions and fragile evaluation outputs.

7. Gate interaction risk
   - `check_question_scope` does not classify "conflict" as risk keyword; common conflict questions can be blocked as ambiguous.
   - `build_analyst_input` readiness thresholds can block all analysis when relationship observations are not passed (default API path).

### Duplicate / Overlapping Logic Families

- Multiple pipeline facades:
  - `Config/pipeline.py`
  - `Layer4_Analysis/core/unified_pipeline.py`
  - `Layer4_Analysis/layer4_unified_pipeline.py`
  - `Core/orchestrator/layer123_pipeline.py`
- Multiple investigation frameworks:
  - Layer-4 investigation controller path
  - Core investigation loop path
- Multiple API surfaces:
  - `API/main.py`
  - `analysis_api/main.py`

Operational effect: behavior depends heavily on which entrypoint is used.

---

## 11. SYSTEM TYPE CLASSIFICATION

### Technical Classification

**Primary classification**: **Hybrid, gated, multi-agent decision-support architecture with deterministic evidence scoring**.

### Not pure RAG

- Retrieval exists, but council scoring is not rank-driven retrieval QA.
- Decision core works on interpreted state and symbolic signals.

### Not pure expert system

- LLM ministers provide stochastic classifications.
- Not a static rule-only inference engine.

### Not a single-agent LLM app

- Multiple minister agents plus deterministic coordinator phase machine.
- Separation between interpretation, deliberation, verification, and safety layers.

### What it is in practice

- A **state-driven geopolitical assessment engine** where LLM outputs are constrained and then subordinated to deterministic confidence, verification, and refusal gates.
- Current implementation status is **partially integrated** with legacy strata and runtime breakpoints on several top-level entrypoints.

---

## 12. FINAL ARCHITECTURE DIAGRAM (TEXTUAL)

```text
                                 +------------------------------+
                                 |          USERS / JOBS        |
                                 | API clients, CLI, tests, ops |
                                 +---------------+--------------+
                                                 |
                          +----------------------+----------------------+
                          |                                             |
                 +--------v---------+                         +---------v---------+
                 | API/main.py      |                         | analysis_api/main |
                 | /query /v2 /SSE  |                         | /api/v1 endpoints |
                 +--------+---------+                         +---------+---------+
                          |                                             |
                          |                                     +-------v--------+
                          |                                     | services.py     |
                          |                                     | Country profiles|
                          |                                     +----------------+
                          |
               +----------v-----------+
               | Config.pipeline      |
               | run_query()          |
               +----------+-----------+
                          |
               +----------v------------------------------+
               | Layer4_Analysis/core/unified_pipeline.py|
               | scope gate + readiness gate             |
               +----------+------------------------------+
                          |
               +----------v------------------------------+
               | Layer3_StateModel/interface/state_provider|
               | build_initial_state()                    |
               +----------+------------------------------+
                          |
        +-----------------v------------------+
        | CountryStateBuilder + providers     |
        | GDELT/WorldBank/... + provenance    |
        +-----------------+------------------+
                          |
        +-----------------v------------------+
        | SignalBeliefModel (reliability)     |
        | numeric -> fuzzy belief per signal   |
        +-----------------+------------------+
                          |
        +-----------------v------------------+
        | CouncilCoordinator.process_query()  |
        | Phase machine:                      |
        | DELIB -> CHALLENGE -> INVESTIGATE   |
        | -> VERIFY -> SAFETY -> FINALIZE     |
        +-----------------+------------------+
                          |
      +-------------------+-------------------+
      |                                       |
+-----v--------------------+      +-----------v----------------+
| ministers.py             |      | decision/verifier.py        |
| LLM JSON classification  |      | deterministic signal verify |
+-----------+--------------+      +-----------+----------------+
            |                                 |
            +---------------+-----------------+
                            |
                  +---------v------------------+
                  | safety/safeguards.py       |
                  | refusal + HITL escalation  |
                  +---------+------------------+
                            |
                  +---------v------------------+
                  | API response / CLI output  |
                  | answer,sources,confidence  |
                  +----------------------------+
```

---

## Appendix: Audit Metrics

- `forensic_map.json`: `reports/forensic/forensic_map.json`
- `forensic_map.csv`: `reports/forensic/forensic_map.csv`
- `section5_full.md`: `reports/forensic/section5_full.md`
- `calls_map.json`: `reports/forensic/calls_map.json`
- `called_by_map.json`: `reports/forensic/called_by_map.json`

### Criticality Distribution

- `core`: 82
- `reasoning`: 13
- `verification`: 2
- `safety`: 9
- `unused`: 365
