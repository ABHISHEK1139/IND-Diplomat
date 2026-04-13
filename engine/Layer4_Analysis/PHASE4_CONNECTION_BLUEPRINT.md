# Phase-4 Connection Blueprint (As-Is Runtime)

Generated on: 2026-02-23  
Scope: `Layer4_Analysis` module wiring based on current code (imports + executed call paths).

## 1) Runtime Entrypoints

| Entrypoint | Current status | Evidence |
|---|---|---|
| `Config.pipeline.run_query` | Active | `Config/pipeline.py:95`, `Config/pipeline.py:128`, `Config/pipeline.py:131` |
| `Layer4_Analysis.core.UnifiedPipeline.execute` | Active | `Layer4_Analysis/core/unified_pipeline.py:56` |
| `Layer4_Analysis.coordinator.CouncilCoordinator.process_query` | Active | `Layer4_Analysis/coordinator.py:502` |
| `Layer4_Analysis.layer4_unified_pipeline.Layer4UnifiedPipeline.execute` | Legacy-only wrapper, not referenced by main pipeline | `Layer4_Analysis/layer4_unified_pipeline.py:41` |
| `API /query` path -> `run_query` | Active API path | `API/main.py:268` |
| `API /v2/query` path -> `unified_pipeline.execute` | Broken wiring (symbol use without import in file) | `API/main.py:370` |

## 2) Live Runtime Call Graph

```
API /query
  -> Config.pipeline.run_query
     -> Layer4_Analysis.core.unified_pipeline.UnifiedPipeline.execute
        -> intake.question_scope_checker.check_question_scope
        -> Layer3 state_provider.build_initial_state
        -> intake.analyst_input_builder.build_analyst_input
        -> coordinator.process_query
           -> convene_council
              -> evidence.extract_signals_from_state
                 -> evidence.signal_mapper
              -> ministers.deliberate (Security/Economic/Domestic/Diplomatic)
                 -> core.llm_client.LocalLLM
           -> detect_conflicts
           -> anomaly_sentinel.check_for_anomaly (black swan branch)
           -> red-team stage (inline in coordinator)
           -> CRAG stage (inline in coordinator; placeholder)
           -> threat_synthesizer.synthesize
              -> confidence_calculator.calculate
           -> quick verify (inline claim-evidence check)
           -> optional full verify
              -> decision.verifier.verifier_agent.verify_answer
              -> deliberation.cove.cove_verifier.run_cove_loop
           -> refusal threshold (inline boolean gate)
           -> HITL threshold (inline boolean gate)
           -> generate_result
```

## 3) Stage Wiring (Coordinator)

| Stage | Connected implementation | Notes | Evidence |
|---|---|---|---|
| Stage 1 Deliberation | `convene_council` | Active | `Layer4_Analysis/coordinator.py:205`, `Layer4_Analysis/coordinator.py:546` |
| Stage 2 Conflict detection | `_detect_conflicts` | Active | `Layer4_Analysis/coordinator.py:240`, `Layer4_Analysis/coordinator.py:563` |
| Black Swan interrupt | `_should_trigger_black_swan_interrupt` + early return | Active short-circuit | `Layer4_Analysis/coordinator.py:190`, `Layer4_Analysis/coordinator.py:580`, `Layer4_Analysis/coordinator.py:593` |
| Stage 3 Red Team | `_should_trigger_red_team` + `_run_red_team` | Active, inline implementation | `Layer4_Analysis/coordinator.py:97`, `Layer4_Analysis/coordinator.py:257`, `Layer4_Analysis/coordinator.py:612` |
| Stage 4 CRAG investigation | `_investigate_missing_signals` | Active structure, retrieval is placeholder | `Layer4_Analysis/coordinator.py:286`, `Layer4_Analysis/coordinator.py:309` |
| Stage 5 Synthesis | `_synthesize_decision` -> `ThreatSynthesizer` | Active | `Layer4_Analysis/coordinator.py:323`, `Layer4_Analysis/decision/threat_synthesizer.py:11` |
| Stage 6 Verification | `_verify_claims` (quick) + conditional full verification | Active, full path conditional | `Layer4_Analysis/coordinator.py:360`, `Layer4_Analysis/coordinator.py:662`, `Layer4_Analysis/coordinator.py:673` |
| Stage 7 Refusal | `_check_refusal_threshold` | Active, inline | `Layer4_Analysis/coordinator.py:386`, `Layer4_Analysis/coordinator.py:694` |
| Stage 8 HITL | `_check_hitl_threshold` | Active gate only, no `HITLManager` integration | `Layer4_Analysis/coordinator.py:395`, `Layer4_Analysis/coordinator.py:729` |

## 4) Runtime-Reachable Layer4 Modules (15)

1. `Layer4_Analysis.core.unified_pipeline`
2. `Layer4_Analysis.coordinator`
3. `Layer4_Analysis.council_session`
4. `Layer4_Analysis.ministers`
5. `Layer4_Analysis.core.llm_client`
6. `Layer4_Analysis.schema`
7. `Layer4_Analysis.intake.question_scope_checker`
8. `Layer4_Analysis.intake.analyst_input_builder`
9. `Layer4_Analysis.investigation.anomaly_sentinel`
10. `Layer4_Analysis.evidence.evidence_tracker`
11. `Layer4_Analysis.evidence.signal_mapper`
12. `Layer4_Analysis.decision.threat_synthesizer`
13. `Layer4_Analysis.decision.confidence_calculator`
14. `Layer4_Analysis.decision.verifier` (conditional full verification)
15. `Layer4_Analysis.deliberation.cove` (conditional full verification)

## 5) Legacy-Only Connected Module (1)

1. `Layer4_Analysis.layer4_unified_pipeline`

This module imports coordinator/session/schema and works as a wrapper, but main runtime does not call it.

## 6) External-Only Connected Modules (Not in Main Runtime Path)

| Module | Connected from | Status |
|---|---|---|
| `Layer4_Analysis.safety.guard` | `API.main` | Connected to API input safety, not integrated into Layer4 coordinator path |
| `Layer4_Analysis.evidence.gap_analyzer` | `Tests.test_layer4_kgi_engine` | Test-only connection |
| `Layer4_Analysis.investigation.investigation_controller` | `Tests.test_layer4_kgi_engine` | Test-only connection |
| `Layer4_Analysis.investigation.investigation_request` | `Tests.test_layer4_kgi_engine` | Test-only connection |
| `Layer4_Analysis.investigation.deception_monitor` | `Tests.test_layer4_risk_monitors` | Test-only connection |
| `Layer4_Analysis.report_generator` | `Scripts.test_phase4` | Script-only connection |

## 7) Fully Unmapped Modules (No Runtime Path, No External Caller)

1. `Layer4_Analysis.decision.refiner`
2. `Layer4_Analysis.decision.refusal_engine`
3. `Layer4_Analysis.deliberation.crag`
4. `Layer4_Analysis.deliberation.debate_orchestrator`
5. `Layer4_Analysis.deliberation.red_team`
6. `Layer4_Analysis.evidence.evidence_requirements`
7. `Layer4_Analysis.evidence.provenance`
8. `Layer4_Analysis.hypothesis.causal`
9. `Layer4_Analysis.hypothesis.mcts`
10. `Layer4_Analysis.hypothesis.optimizer`
11. `Layer4_Analysis.hypothesis.perspective_agent`
12. `Layer4_Analysis.intake.playbooks`
13. `Layer4_Analysis.investigation.hitl`
14. `Layer4_Analysis.investigation_request`
15. `Layer4_Analysis.safety.safeguards`
16. `Layer4_Analysis.support_models.context.baseline_model`
17. `Layer4_Analysis.support_models.country_model.intent_capability_model`
18. `Layer4_Analysis.support_models.investigation_outcome`

## 8) Connection Mismatches and Broken Links

| Issue | Impact | Evidence |
|---|---|---|
| API imports non-existent module path `Layer4_Analysis.core.coordinator` | `Coordinator` becomes `None` in API import block | `API/main.py:33` |
| `API /v2/query` calls `unified_pipeline.execute` without import in file | Endpoint path is unresolved at runtime when hit | `API/main.py:370` |
| `UnifiedPipeline` red-team flag mismatch | Caller passes `use_red_team`; execute reads `enable_red_team` | `Config/pipeline.py:136`, `Layer4_Analysis/core/unified_pipeline.py:116` |
| `Coordinator.process_query` receives `use_mcts/use_causal/use_multi_perspective` but does not consume them | Feature flags currently no-op in coordinator logic | `Layer4_Analysis/coordinator.py:502` |
| Core fallback imports non-existent top-level `pipeline.py` | Fallback branch fails if executed | `Layer4_Analysis/core/unified_pipeline.py:159` |
| CRAG retrieval hook is placeholder comment | Investigation loop does not fetch/rebuild state in current coordinator path | `Layer4_Analysis/coordinator.py:309` |

## 9) Duplicate / Parallel Artifacts

| Artifact pair | Observation |
|---|---|
| `Layer4_Analysis/investigation_request.py` and `Layer4_Analysis/investigation/investigation_request.py` | Duplicate concepts with different data contracts; neither is wired into coordinator runtime |
| Inline stage logic in `coordinator.py` vs dedicated modules (`deliberation.red_team`, `decision.refusal_engine`, `investigation.hitl`) | Dedicated modules exist but are bypassed by inline coordinator implementations |

## 10) Practical Wiring Summary

1. Your active Layer4 engine is currently `core/unified_pipeline.py -> coordinator.py`.
2. The coordinator is the true execution hub; many submodules are not yet integrated.
3. Black Swan, inline red-team, synthesis, quick verification, refusal gate, and HITL gate are connected.
4. Dedicated CRAG/red-team/refusal/HITL modules exist but are mostly parked.
5. Legacy and API-v2 paths contain unresolved wiring and should not be treated as authoritative runtime paths until fixed.
