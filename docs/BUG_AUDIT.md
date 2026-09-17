# DIP 3.0 bug audit and repair tracker

Audit started: 2026-09-12. Scope: DIP 3.0 only.

This is a living inventory, not a claim that every bug has been found. Static findings are distinguished from runtime verification. No forecast accuracy or production-readiness claims follow from passing unit tests.

## Baseline and constraints

- Pre-existing modifications: `dashboard.py`, frontend investigation page and API client, `src/dip/api/rest_api.py`, WebSocket router, `src/dip/unified_pipeline.py`; untracked `scratch/generate_hybrid_ministers.py`. Preserve these changes.
- Editor diagnostics initially returned no errors; this does not prove runtime correctness.
- Full pytest collection started but had not completed at the initial 60-second checkpoint.
- Delegated audit requests failed due provider rate limits; audit continues directly.
- No live LLM calls, paid evaluations, or production deployments are authorized by this audit workflow.

## Confirmed issues

| ID | Priority | Status | Evidence / defect | Fix / validation target |
|---|---|---|---|---|
| API-01 | High | Fixed; regression passes | Initial diagnosis was stale: `rest_api.py` has one GET `/health` plus an `/api/v3/health` alias delegating to it. | One authoritative health handler; `test_single_health_route` in `test_repair_contracts.py`. |
| API-02 | High | Fixed; regression passes | CORS ignores `config.CORS_ALLOWED_ORIGINS` and combines wildcard origins with credentials. | Honor configured origins; wildcard mode must not permit credentials. Covered by `test_configured_cors`. |
| API-03 | Medium | Fixed; regression passes | STIX handler catches its own HTTPException(501) and replaces it with HTTPException(500). | Preserve HTTP exception status; `test_stix_http_status.py`. |
| API-04 | High | Fixed; regression passes | Assessment/analyst tasks created without application-owned references or shutdown cleanup. | Both endpoints now use `_schedule_job` (tracked in `app.state.background_tasks`, cancelled in lifespan); `test_lifespan_cancels_owned_tasks` + `test_api_v3_job_lifecycle` exercises the real runner. |
| API-05 | Medium | Fixed | API import deletes caller's `LITELLM_TIMEOUT` environment setting. | Import no longer mutates the environment; caller configuration respected. |
| JOB-01 | High | Fixed; focused regressions pass | Analyst runner used the nested `dip.pipeline.deliberation.ind_diplomat` package shim, which discards job_id, rather than the public wrapper. Import errors were outside the failure handler. | Use `dip.ind_diplomat` inside guarded runner. Verified wrapper selection and persisted import failure in `test_analyst_worker_regression.py`. Correction: the nested package exists; the initial nonexistent-import diagnosis was wrong. |
| JOB-04 | High | Fixed; focused regression passes | After selecting the public wrapper, its `PipelineError` result was incorrectly stored as COMPLETED. | Explicitly handle `PipelineError` as FAILED, preserving its error message. |
| JOB-02 | High | Fixed; regression passes | Both JSON job stores use non-atomic writes; analyst store silently suppresses persistence failures. | Both stores persist via atomic `dip.core.atomic_json.write_json`; load failures raise, write failures roll back. `test_corrupt_store_is_not_silently_discarded`, `test_analyst_write_failure_rolls_back`. |
| JOB-03 | High | Fixed; regression passes | Assessment store copies assessment outcome into job lifecycle status, while WS always reports COMPLETED. | Canonical lifecycle QUEUED→RUNNING→COMPLETED\|FAILED (uppercase, both stores, legacy normalized on load); assessment disposition stays in `result` (only pipeline ERROR fails the job); WS reports store status + `assessment_status`. New: `test_legacy_lowercase_statuses_are_normalized`, `test_ws_reports_store_status_not_hardcoded_complete`; updated `test_assessment_disposition_is_not_job_status`, cancellation test. |
| CFG-01 | High | Fixed | Config ROOT_DIR resolves to `src/dip/core`; configured data paths point inside source tree. | ROOT_DIR/DATA_DIR resolve to project root with `DIP_DATA_DIR` override; guardian agent moved off its in-package `data/` dir onto central `DATA_DIR`/`DIP_JOB_STORE` with atomic writes. `test_source_root`. No data deleted. |
| DEP-01 | High | Fixed; compose validates | Compose resides in `docker/` but uses `context: .`, root-relative frontend/deploy/data/.env paths. | All host-relative paths re-anchored with `../`; `docker compose -f docker/docker-compose.yml` validated with PyYAML (13 services). |
| DEP-02 | High | Fixed (static) | Dockerfile.web copies root `api.py`, `nextgen`, and layer directories; DIP 3 uses `src/dip/api`, `engines`, `pipeline`. | Rewritten package-based (`src/` + `pip install -e .`, ASGI `dip.api.rest_api:app`). Container build not run here — needs Docker daemon verification. |
| DEP-03 | High | Fixed (static) | Other Dockerfiles and Makefile retain old root entrypoints. | Audited each: worker→`scripts/analyst_worker.py`, scheduler→`python -m dip.orchestrator`, guardian→`scripts/guardian_runner.py`, all-in-one ASGI fixed, war_room documents its static-export precondition, Makefile paths/ASGI/CLI fixed. Container builds not run here. |
| DATA-01 | High | Fixed | `_safe_crag` in unified_pipeline fabricates corroboration text after an exception. | Records state-only gap confirmation, never manufactured evidence. Also removed the Layer-4→Layer-1/2 boundary leaks (`crag.py` ResearchPlanner import, ministers' `web_surfer`/`signal_extractor` imports, specialist raw-text injection). |
| DATA-02 | Medium | Fixed | Memory vault and forecast archive run before threat/result fields are populated in pipeline. | Final assessed fields (threat_level, verification, hypotheses, evidence) now populate right after briefing, before vault/learning/archive/self-model/contagion. Also added missing `import json` in `unified_pipeline.py` (was a latent NameError masked by `except Exception`). |
| UI-01 | High | Fixed (static) | RightPanel hardcodes confidence percentages and a fabricated future timeline under operational labels. | Timeline/metrics render pipeline props when present, badged demo fallbacks only in demo mode, honest unavailable states otherwise. Same treatment for CenterPanel dossier/hypotheses/sources/recommendations/scenarios/SRE/Nash defaults, DebateView cards, ForecastCharts series, EvidenceExplorer empty state. No frontend toolchain in this env — needs `npm run build` verification. |
| UI-02 | High | Fixed (static) | Prior inspection found synthetic demo jobs and mock workspace data on API failures. | Rechecked: no fake jobs are synthesized on API failure (errors surface via `setError`/polling). Mock entities/relationships/evidence/debate now gated behind explicit `demo-` ids; real jobs show empty + unavailable states. Needs `npm run build` verification. |
| TEST-01 | High | Fixed; regression passes | `test_api_v3.py` mock_execute omits job_id; test manually marks job complete, hiding runner failure. | Mock accepts `(query, country, job_id=None)` with job_id assertion; test polls the real background runner to completion. |
| TEST-02 | Medium | Fixed | GPU test catches every exception and passes; model execution is marked unit. | Split into deterministic `test_torch_cuda_probe` (unit) and `test_gliner_entity_extraction` (integration, `importorskip` — skips when absent, fails loudly when present-but-broken). |
| META-01 | Low | Fixed | pyproject is 3.1.0; package is 3.0.0; API is 2.5; CLI says 2.0. | Single source `dip.__version__` (3.0.0): pyproject aligned to 3.0.0, API already used it, CLI banners derive from it. Historical "DIP 2.0" docstrings left untouched (naming, not version claims). |

## Architecture / feature gaps (not automatically runtime bugs)

- Public API/CLI use `unified_pipeline.execute`; newer debate and investigation runtimes are not the default. Do not switch to unvalidated experimental orchestration merely to match README claims.
- Many collaboration, adaptive, forecasting, and research modules are stubs. Catalogue required behavior before implementing speculative features.
- Multiple job/memory stores lack a shared transactional/recovery model.
- README's numbered pipeline directories do not match actual package names.
- Requirements and pyproject disagree; heavyweight optional integrations need an installation audit.

## Verification log

- Initial static inspection completed for API, pipeline first 700 lines, configuration, job stores, WebSockets, Compose, Windows startup, and representative tests/frontend component.
- Existing default suite completed successfully with `python -m pytest -q -x` before patches (183 selected test outcomes, including skips; quiet configuration suppressed totals). This suite did not expose the worker defect.
- Focused baseline: assessment gate 15 passed; API v3 2 passed.
- Added three worker regressions. Observed failures in order: wrong wrapper/result, uncaught ImportError, PipelineError incorrectly marked COMPLETED. Each was fixed; final focused run: 3 passed, 1 third-party deprecation warning.
- The initial worker regression unexpectedly called the real pipeline via the nested shim, producing missing-local-model and disconnected-Neo4j warnings. Both pipeline entrypoints are now blocked in the fixture to prevent recurrence.
- Post-patch default suite: `python -m pytest -q -x` completed successfully, including the three new regressions. Existing skips, dependency deprecations, and an unclosed Neo4j driver warning remain. A separate rerun of `tests/test_analyst_worker_regression.py` also passed all three tests. Editor diagnostics found no errors in the modified worker or new regression file.
- Frontend build, container build, live integration availability, and predictive quality: not yet verified. The broader repair tracker remains open; passing the default suite is not a complete-project certification.

## Repair policy

Reproduce or establish concrete static evidence, patch narrowly, add regression tests, record exact validation. Mark untested fixes as implemented/unverified rather than resolved. Never erase user data, suppress failing tests merely to obtain green output, or report an incomplete audit as a complete project repair.

## Repair pass 2026-09-17 (all 14 open items addressed)

- Backend fixes verified by focused suites (FORCE_MINISTER_HEURISTIC=1 where the
  pipeline would otherwise call live LLMs/network):
  `test_repair_contracts.py`, `test_stix_http_status.py`, `test_api_v3.py`,
  `test_analyst_worker_regression.py`, `test_job_integration.py`,
  `test_layer4_pipeline.py`, `test_assessment_gate.py`, `test_rfi_loop.py`,
  `test_symbolic_rails.py`, `test_run.py`, `test_phase2_plus.py` — all green.
- Full default suite (`python -m pytest -q -x`) still hangs on live-network
  collection paths; mitigated with bounded timeouts (GDELT 15s, feed gather
  30s, DDGS 20s threaded, RSS 15s threaded, StateProvider 35s) but a full
  offline green run is NOT yet established. The counterfactual harness
  (`tests/counterfactual_harness.py`) requires live execution and was not run.
- Static-only (needs Docker daemon): DEP-02/DEP-03 image builds.
- Static-only (needs `npm run build` in frontend-next): UI-01/UI-02.
- Preserved pre-existing user modifications: `dashboard.py`, frontend
  investigation page + API client, `rest_api.py`, WS router,
  `unified_pipeline.py`, untracked `scratch/generate_hybrid_ministers.py`.
  No user data touched; no tests suppressed.

## Structural repair pass 2026-09-17 (the seven blockers)

1. Offline determinism: `tests/fixtures/offline_border_crisis.json` +
   `test_counterfactual_grounding.py` (design.txt Step 3, 4 tests, green) run
   the council with zero network/LLM. Full-suite-offline still pending
   (collection cassettes not yet recorded).
2. Calibration: `tests/test_offline_backtest.py` scores the 5 labeled crises
   through a deterministic offline pipeline. First honest numbers:
   directional_accuracy=1.0, threat_accuracy=0.2, brier=0.05, MAE=0.144.
   The heuristic over-predicts CRITICAL (military keyword -> 0.85) — tracked
   as a calibration gap, not hidden. Regression floor: directional >= 0.6.
3. Boundary enforcement: `tests/test_layer4_boundary.py` statically bans
   Layer-1/2 + retrieval imports and raw-text markers under deliberation/.
4. Prompt injection: new `dip.core.sanitize` trust boundary, wired into
   Layer-2 extraction (`signal_extractor.extract`/`extract_signals`) and
   minister prompt construction; `tests/test_sanitize.py` (12 cases, green).
5. Dependencies: pyproject split into minimal core + named extras + `all`;
   `requirements.txt` matches core; guarded `graph_manager` (neo4j),
   `morning_brief`/`goal_decomposer` (dspy), `retrieval/extractor`
   (trafilatura); `tests/test_optional_deps.py` pins lazy-failure behavior.
6. Store scale: Docker entrypoints pinned to `--workers 1` (JSON stores are
   single-process); migrate to Postgres/Redis before scaling out.
7. Scope: `docs/MODULE_CATALOG.md` classifies every package
   (real/experimental/stub) with a promotion policy. `adaptive/`,
   `collaboration/`, `ecosystem/` confirmed stubs; left untouched, not expanded.
- Verification this pass: 65 focused tests green (boundary, sanitize,
  counterfactual, optional-deps, repair-contracts, API v3, worker, layer-4,
  gate, RFI, symbolic) + `compileall` clean. Not yet verified: Docker image
  builds, `npm run build`, live-LLM behavior, full offline suite.

## Final verification pass 2026-09-17 (all four closed)

- Docker: `docker/Dockerfile.web` + `Dockerfile.worker` build clean;
  `politiq-ai:web` booted and served `GET /health 200`; container E2E
  `POST /api/v3/assess` -> QUEUED -> CRITICAL/WITHHELD (verif 0.736, 5
  hypotheses). Always-on guard: `tests/test_docker_context.py` (COPY paths,
  ASGI targets, single-worker rule, compose refs). Build caught one real
  defect on the way: undeclared `sqlalchemy` (default-path import) — now in
  core deps; extras completed (langchain-*, pandas/sklearn/statsmodels/
  prophet/pymc, chromadb, typing_extensions).
- Frontend: `npm install` (452 pkgs) + `npm run build` green (compile,
  typecheck, static pages). The build caught 5 real bugs, all fixed:
  2 TSX paren errors in CenterPanel fallbacks, dead "engines" tab (missing
  from state union), `expert_agreement` snake_case mismatch, missing
  `fuzzy_trace`/`symbolic_guardrails`/`nash_equilibrium` API types,
  `Scenario.description` type gap.
- Live-LLM: no keys and no Ollama in this env, so live execution stays
  impossible here — made verifiable instead: `tests/test_live_llm.py` runs
  the wire path when `DIP_LIVE_LLM=1` + key (skip-clean otherwise), and a
  unit test proves every failure mode degrades to None (never raise/hang).
- Full offline suite: `tests/cassette.py` + `tests/conftest.py`
  (`DIP_OFFLINE=1`) replace all collection network hops with deterministic
  fixtures. Result: **213 passed, 16 skipped, 1 deselected in 95s**.
  One transient stall during parallel Docker activity was resource
  contention, not a code hang (two clean full passes).

## Frontend explainability pass 2026-09-17

- New `DecisionTrail` ("Why?" tab): 5-stage trace — observed signals,
  minister hypotheses with confidences, red-team findings, verification vs
  the 70% gate + gate verdict, final decision — every line sourced from the
  result payload, with refusal reasons shown verbatim when present.
- Report tab: prominent withheld/refused banner (previously refusals were
  invisible); dynamic portfolio counts; judgments/recommendations bound to
  real data.
- Forecast tab: real trajectory direction + P(HIGH) 14/30/60d wired into
  charts; no fabricated series.
- Right panel: red-team findings section; debate commentary actually
  rendered (was accepted-but-never-displayed prop).
- Left panel: knowledge graph derived live from reported signals
  (entity → action → target); demo badge; empty-state notice.
- Evidence tab now shows the verbatim pipeline evidence log.
- `npm run build` green (compile + typecheck + static generation).

## Bug-hunt pass 2026-09-17 (6 new defects, all fixed)

1. Gate judged empty fields (High): `build_assessment_state` read
   `verification_score` (0.0) and `threat_level` ("LOW" default) because
   finalization ran after the gate — systematic WITHHOLD bias on every run.
   Finalization moved pre-gate; `test_pipeline_finalization.py` proves gate
   inputs populated via real offline `execute()`.
2. Dead contract keys (High): `recommendations`, `confidence_scores`,
   `timeline` were never set by `execute()` — frontend tabs permanently
   empty. Backend now sends verbatim recommendations + computed
   confidence metrics (documented formulas, nulls not placeholders) +
   forecast reliability after trajectory.
3. Infinite polling on failed jobs (High): page polled forever when a job
   FAILED (no terminal detection, WS ignored `job.failed`). Now stops with
   an error banner + phase errors + 10-min backstop.
4. Hardcoded phase details (Medium): `sources: 287, credibility: 91`
   replaced with values derived from the reported result.
5. Display bugs (Low): unused `debate` prop now rendered; hardcoded
   "7 Portfolios" now dynamic; trajectory log key `label` fixed to
   `trajectory_label`.
6. Scale mismatch (Medium): backend sends 0-1 fractions, ConfidencePanel
   charted them as 0-100 percentages (0.736 rendered as <1% bar). Panel now
   normalizes with null-safe "n/a" bars.
- Verification: full offline suite **214 passed, 16 skipped, 1 deselected**;
  `npm run build` green.

## Full sweep pass 2026-09-17 (9 more defects, all fixed)

1. Import-time filesystem writes (High): importing `dip.telemetry.llm_tracer`
   constructed `InvestigationMemory()` at module top, creating
   `investigations.db` + `investigations/` in whatever the CWD was.
   Tracer memory is now lazy; `test_data_paths.py::test_import_creates_no_files`
   proves clean imports in an isolated directory.
2. CWD-dependent data paths (High): `.env` overrides (`data/jobs.json`) and
   `DIP_DATA_DIR=./data` resolved against the process CWD; `data/`-prefixed
   values now anchor at ROOT_DIR, others at DATA_DIR. Legacy CWD files are
   copied forward once (originals kept, SQLite magic-checked).
3. Silent fake demo on launch failure (High, UI-02 recurrence):
   `new/page.tsx` routed to `demo-<timestamp>` when the backend was down.
   Now an error panel with retry + an explicit demo-preview button.
4. Broken standalone entrypoints (High): `scripts/analyst_worker.py`,
   `guardian_runner.py`, `wargame.py`, `deploy_prefect.py`,
   `run_validation_suite.py`, `run_10_cases.py`, `run_replay.py` imported
   `dip` without a usable sys.path (package not installed). All anchor
   `<root>/src` now; `tests/test_entrypoints.py` pins it. Stale
   `verify_live_dossier.py` (missing module) retired into an explanatory
   pointer with exit code 2.
5. Tracker phase mismatch (Medium): backend stages (council,
   cove_verification, briefing, ...) never mapped to tracker steps.
   `PHASE_MAP` added; `tests/test_frontend.py` upgraded from placeholder
   into a backend↔frontend phase-contract test.
6. Blank-request validation (Medium): empty queries ran the whole pipeline
   to a refusal. Shared `AssessRequest` validators return 422; HoC/Wargame
   models unified onto it (country normalized uppercase).
7. Source-tree audit log (Medium): `assessment_records.jsonl` moved to
   DATA_DIR with legacy copy-forward.
8. Neo4j driver leak + event-loop blocking (Medium): ripple-effects block
   now closes the driver in `finally` and runs in a bounded worker thread.
9. Dead imports flagged by ruff in touched files (Low): removed.
- Verification: full offline suite **222 passed, 16 skipped, 1 deselected**;
  `npm run build` green; eslint clean on touched components.

## Live-LLM pass with user OpenRouter key 2026-09-17 (3 defects, all fixed)

- Account balance covers ~281 tokens, so paid models 402. Used the 20
  available `:free` models instead (`google/gemma-4-31b-it:free`).
- Full live `execute("Assess border escalation risk", "IND")` in 145s:
  10 hypotheses (7 ministers LLM-refined: 0.765/0.935/0.835/0.378 + 3
  dynamic experts), 82 evidence items, 3 red-team findings, gate WITHHELD
  with real proposal CRITICAL (gate-ordering fix confirmed live),
  trajectory STABLE, LLM-written briefing + narrative. Verification 0.686
  exercised the refusal path end to end.
- Defects found live and fixed:
  1. LangChain fallback hardcodes `qwen3.5:4b` and never checks the Ollama
     model list — reachable host + missing model surfaced as late 404s.
     Now verifies the model via /api/tags, prefers the configured
     `LLM_MODEL`, adds an OpenRouter branch, and both OpenAI import paths
     tolerate the langchain-openai move (`langchain-openai` added to the
     reasoning extra).
  2. Junk gap tokens (`expect_this_indicator`, `expect_what_indicator`)
     leaked into gate verdicts and the UI. Heuristic tokenizer now drops
     filler stopwords; regression pinned in `test_langchain_llm.py`.
  3. Live test requested up to 1000 tokens (fails on near-empty balances);
     now capped at 250. `test_live_structured_completion` passes live.
- Verification: offline suite **224 passed, 17 skipped, 1 deselected**;
  live wire test green. Key used process-env-only, never written to disk.

## Live-log mining pass 2026-09-17 (6 defects, all fixed)

Mining the 145s live run exposed what unit tests could not:
1. Tracer masked primary errors (High): every litellm failure logged only
   the fallback's 404, hiding root causes (here: free-tier rate limits).
   Both tracer paths now log `primary + fallback` errors.
2. No hung-provider protection (High): 13 direct litellm call sites had no
   timeout — one wedged provider stalls a request forever. New
   `dip.core.llm_limits` sets a global `litellm.request_timeout` from
   `DIP_LLM_TIMEOUT` (default 60s); `tests/test_llm_rate_limits.py` pins it.
3. Hypothesis provenance dropped (High): `decision_mode` et al never left
   the session, so live LLM vs heuristic fallback was indistinguishable
   downstream. Finalization mapping extracted to testable
   `_hypothesis_to_dict` (provenance fields mandatory); UI shows
   heuristic / LLM·refined / LLM·bounded badges with hover detail.
4. Two more source-tree data paths (Medium): introspection history +
   temporal belief history moved to DATA_DIR with legacy copy-forward.
5. Dropped reasoning records (Medium): `dual_mode_assessment` and
   `introspection_report` now included in the auditable result.
6. Inconsistent mode vocabulary (Low): schema default `"heuristic"` vs
   rails `"heuristic_only"` unified on the resolution-action vocabulary.
- Verification: offline suite **229 passed, 17 skipped, 1 deselected**;
  `npm run build` green.
