# DIP_8 to DIP 2.0 Migration Guide

This guide explains how the next-generation DIP 2.0 stack maps from DIP_8 and how to migrate existing workflows.

## What Changed

DIP 2.0 keeps the analytical core but restructures the runtime around a safer, more durable advisory architecture:

- `AssessmentGoal` captures every run as a durable objective.
- `AssessmentBlackboard` records append-only phase events.
- `HeadOfStatePipelineGraph` provides a stable execution facade.
- `nextgen/oss_adapters.py` detects optional open-source replacements at runtime.
- `nextgen/observability.py` enables OpenTelemetry and MLflow only when requested.

## Direct Mappings

### 1. Council and minister reasoning

- DIP_8 council session logic maps to `layer4_reasoning/` in DIP 2.0.
- Minister roles are preserved as:
  - Security Minister
  - Strategy Minister
  - Diplomacy Minister
  - Economic Minister
  - Domestic Minister
  - Alliance Minister
  - Contrarian Minister

### 2. Durable execution and checkpoints

- DIP_8 checkpoint and resume behavior maps to `nextgen/assessment_graph.py`.
- Per-trace checkpoint files are stored under `data/checkpoints/`.
- Phase events are also written in append-only blackboard form for auditability.

### 3. SRE / risk modeling

- DIP_8 fuzzy escalation behavior maps to `nextgen/sre.py` and `core/schema.py`.
- The contract is preserved:
  - `StateContext`
  - `SignalBelief`
  - `ObservedSignal`
  - `SRE`
  - `risk`

### 4. Open-source replacements

When installed, DIP 2.0 prefers these optional replacements:

- LangGraph for durable graph execution
- Prefect for scheduling and audits
- OpenTelemetry for traces and metrics
- MLflow for experiment tracking
- Evidently for drift and quality monitoring
- Haystack for RAG post-processing
- STIX2 for intelligence object export
- NetworkX for actor and theater graphs

## Recommended Migration Steps

1. Point your entrypoints at `unified_pipeline.execute()`.
2. Keep using the current API endpoints and job store.
3. Enable optional dependencies only when needed.
4. Validate minister behavior with `FORCE_MINISTER_HEURISTIC=1` in offline CI.
5. Compare outputs against prior DIP_8 runs using the new blackboard and checkpoint files.

## Compatibility Notes

- Existing `api.py` job endpoints remain supported.
- Existing `nextgen_sre` output fields are preserved.
- Additional fields such as `goal`, `trace_id`, `blackboard_events`, `fuzzy_trace`, `learning_units`, `experiment_records`, `schema_matches`, and `promotion_status` are additive.

## OSS Recommendation

Prefer the optional open-source adapters when they are installed, but keep the custom geopolitical ontology and legal firewall in DIP 2.0. That combination preserves the unique intelligence logic while reducing bespoke infrastructure code.
