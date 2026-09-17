# DIP 3.0 module catalog — real vs experimental vs stub

Generated 2026-09-17 by static scan (`*.py` per package; "substantial" =
non-`__init__` file over 15 lines). "On default path" means reachable from
`dip.unified_pipeline.execute` (the public API/CLI entrypoint) without
opt-in flags. Rule: **do not expand experimental/stub surface to match
README claims; promote modules only with tests + calibration evidence.**

| Package | Files | Substantial | Status | Notes |
|---|---|---|---|---|
| `pipeline/` | 246 | 167 | **Real (default path)** | Collection → knowledge → world_model → deliberation → forecasting → synthesis → memory. |
| `engines/` | 47 | 40 | **Real, mixed** | SRE, guardrails, contracts, exporters on default path. `langgraph_*`, `prefect_*`, `benchmark_harness`, `crisis_replay` are opt-in/experimental. |
| `core/` | 9 | 7 | **Real** | Schema, config, sanitize, atomic_json, fuzzy. |
| `api/` | 7 | 4 | **Real** | REST + WS + analyst store. |
| `runtime/control_loop/` | 26 pkg / 6 | 6 | **Real** | InvestigationController readiness loop (default path). Rest of `runtime/` (graph, langgraph, investigations) experimental. |
| `telemetry/` | 4 | 3 | **Real** | LLM tracer (litellm optional). |
| `layer0_planning/` | 6 | 6 | **Experimental** | Planner; not on default path. |
| `enterprise/` | 15 | 5 | **Experimental** | Audit/OTel tracers; mostly guarded shims. |
| `hitl/` | 2 | 1 | **Experimental** | Only used by the alternate `investigate.py` runtime. Default path uses `runtime/investigation/hitl.request_review` instead. |
| `adaptive/` | 12 | 2 | **Stub** | Empty `__init__`s + ~14-line placeholder classes. No default-path usage. |
| `collaboration/` | 22 | 1 | **Stub** | Same pattern; only `yjs_sync` (behind WS collab route) is live. |
| `ecosystem/` | 10 | 2 | **Stub** | Plugin SDK skeleton (`pluggy` top-level import is the only hard dep). |
| `data/` | 0 | 0 | **Empty** | Namespace dir; runtime data lives in project-root `data/` (see CFG-01). |

## Promotion policy

1. A stub becomes experimental only with a design note + at least one test.
2. Experimental becomes default-path only with offline fixture coverage
   (`tests/fixtures/`) + a calibration entry in `tests/test_offline_backtest.py`
   or the counterfactual suite.
3. Never add a new top-level package for a single caller; extend `pipeline/`
   or `engines/` first.
