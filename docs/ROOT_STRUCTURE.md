# Root Structure Guide

This repository is intentionally layered and service-oriented. The top-level folders are grouped by role below.

## Core runtime services

- API: auth + query API surface
- analysis_api: analysis service endpoints
- analyst_api: async analyst job service
- Frontend: web UI assets

## Intelligence engine (layered model)

- engine/Layer1_Collection
- engine/Layer1_Sensors
- engine/Layer2_Knowledge
- engine/Layer3_StateModel
- engine/Layer4_Analysis
- engine/layer4_reasoning
- engine/Layer5_Judgment
- engine/Layer5_Reporting
- engine/Layer5_Trajectory
- engine/Layer6_Backtesting
- engine/Layer6_Learning
- engine/Layer6_Presentation
- engine/Layer7_GlobalModel

## Shared foundations

- Config: environment and runtime configuration
- Core: orchestration, module system, contracts
- Utils: utility helpers
- contracts: schema-level interoperability helpers
- schemas: request/response schema definitions

## Supporting modules and evaluation

- analysis: experiment and replay analysis
- docs: documentation
- examples: sample outputs
- test: tests and smoke checks
- Scripts: setup, ingestion, tooling scripts
- system_bootstrap: bootstrap utilities
- SystemGuardian: runtime checks and guardrails

## Data root

- data/global_risk: canonical source bundle used by providers
- data/legal_memory: canonical legal corpus index files

## Navigation tips

- Start from run.py for CLI and app_server.py for unified web/API run.
- Use CONFIGURE_AND_RUN.md for first-run setup.
- Keep generated output folders out of root git tracking to avoid clutter.
