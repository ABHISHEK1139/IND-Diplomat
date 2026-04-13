# Evidence And Proof Artifacts

This page points to concrete artifacts in the current repository that demonstrate:

- executable pipeline behavior
- structured analytical outputs
- reproducible evaluation commands
- explicit failure and withholding behavior

## 1) Structured Output Artifact

Example assessment output is available at:

- [examples/sample_assessment.md](../examples/sample_assessment.md)

This sample shows:

- escalation and risk framing
- confidence and epistemic confidence fields
- minister/council style reasoning traces
- evidence-linked narrative output

## 2) Core Model Evidence

The conflict-state model implementation is in:

- `engine/Layer3_StateModel/conflict_state_model.py`

It includes:

- explicit ordered conflict states
- transition-matrix based updates
- likelihood-driven posterior state estimation
- persistent prior behavior for continuity across runs

## 3) Pipeline Architecture Evidence

The orchestrated analysis stack is documented in:

- [architecture.md](architecture.md)
- [repo-map.md](repo-map.md)

High-level flow:

`Signals -> State Construction -> Council -> Verification -> Assessment Gate -> Report`

## 4) Reproducibility Surface

The repository exposes repeatable experiment commands:

```bash
python run.py --experiment replay
python run.py --experiment ablation
python run.py --experiment leadtime
```

## 5) Data Source Transparency

The project uses public OSINT/structured sources such as:

- SIPRI
- GDELT
- ATOP
- World Bank
- V-Dem
- UCDP
- OFAC
- Comtrade
- Lowy

## 6) Failure-Mode Visibility

Public outputs and replay artifacts expose withholding and uncertainty behavior, including:

- insufficient-evidence handling
- evidence gap reporting
- red-team challenge signals
- confidence penalties from weak or contradictory evidence

## 7) What These Artifacts Demonstrate

The current repository provides:

- a non-trivial mathematical state model
- executable end-to-end analysis paths
- inspectable output and diagnostics
- reproducible evaluation entry points

For roadmap and next-stage direction, see [phase2.md](phase2.md).
