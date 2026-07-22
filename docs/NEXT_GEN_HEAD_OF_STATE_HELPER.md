# DIP 2.0 Next-Gen Head-of-State Helper

## Goal

Build DIP 2.0 as a strategic decision-support system for a head of state or
national security principal. It should not act autonomously on policy. It should
produce evidence-backed situation pictures, options, second-order effects,
uncertainty, red-team critique, and explicit human decision points.

## Open-Source Replacements

- LangGraph: durable assessment graph, checkpoints, streaming state, and
  human-in-the-loop pauses.
- Prefect: scheduled ingestion, backtesting, forecast resolution, calibration,
  and guardian audits.
- OpenTelemetry: traces, metrics, and logs for every assessment phase.
- MLflow: experiment tracking, prompt/threshold versions, model registry, and
  promotion governance.
- Evidently: data quality, source drift, signal drift, and fuzzy-threshold drift.
- Haystack: modular RAG pipelines for post-gate legal and evidence retrieval.
- STIX2/OpenCTI-style modeling: intelligence entities, indicators, reports,
  relationships, provenance, and export bundles.
- NetworkX: actor graphs, causal paths, theater contagion, and centrality.

## DIP-Specific Brain

Keep these custom because they are the unique intelligence layer:

- geopolitical fuzzy signal ontology;
- `StateContext -> SignalBelief -> ObservedSignal -> SRE -> risk` contract;
- SRE domain fusion and escalation scoring;
- legal/RAG firewall;
- minister roles and debate policy;
- deterministic assessment gate;
- country/theater calibration and crisis replay benchmarks.

## First Implementation Slice

1. Create `AssessmentGoal` for every query.
2. Create an append-only `AssessmentBlackboard` for every trace.
3. Route phases through a durable graph facade:
   `goal_intake -> collection -> fuzzy_projection -> sre -> council ->
   investigation -> gate -> report -> learning`.
4. Detect available OSS adapters at runtime and prefer them over custom glue.
5. Add output fields without breaking old APIs:
   `goal`, `trace_id`, `blackboard_events`, `fuzzy_trace`, `learning_units`,
   `experiment_records`, `schema_matches`, `promotion_status`.

## Safety Boundaries

- The system advises; accountable humans decide.
- Evidence, inference, forecast, and recommendation are separate.
- No covert action planning, deception planning, or unlawful operations.
- Legal, treaty, humanitarian, and democratic oversight flags are mandatory.
- Low confidence and contradictory evidence must be shown, never hidden.

## Internet Sources Checked

- LangGraph: durable execution, persistence, and human-in-the-loop patterns.
- Prefect: Python workflow orchestration with state tracking, scheduling, and
  failure handling.
- OpenTelemetry: vendor-neutral traces, metrics, and logs for Python.
- MLflow: experiment tracking and model registry.
- Haystack: production RAG and agent pipelines.
- OpenCTI/STIX: knowledge-graph and structured intelligence object patterns.
- NetworkX: complex network representation and algorithms.
