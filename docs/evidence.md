# Evidence And Proof Artifacts

This page summarizes the strongest public proof artifacts currently exposed by the `DIP_6` implementation that sits behind this documentation repo.

The goal is not to claim that every research question is solved, but to show concrete evidence that the system is executable, structured, and experimentally inspectable.

## 1. Experimental Results

The current packaged replay result files in `DIP_6/data/backtesting/results/` report:

- `n_scenarios = 2`
- `n_valid = 2`
- `avg_multiclass_brier = 0.1308`
- `avg_map_accuracy = 0.92`
- `avg_transition_accuracy_top1 = 0.4638`
- `avg_transition_accuracy_top2 = 0.8099`
- `calibration_tier = EXCELLENT`
- `verdict = PASS — Model well-calibrated across all conflict states`

Packaged scenarios currently present in the result index:

- Taiwan Strait Crisis 2022
- Crimea Annexation

Source artifact:

- `DIP_6/data/backtesting/results/index.json`

## 2. Real System Output

The repo includes a sanitized example assessment showing that the pipeline produces structured analytical output with:

- escalation index
- Bayesian conflict-state classification
- confidence and epistemic confidence
- minister-level deliberation
- red-team critique
- trajectory outlook

Public example:

- [examples/sample_assessment.md](../examples/sample_assessment.md)

## 3. Mathematical Model Evidence

The conflict-state model is not a prompt-only classifier. In `DIP_6/Layer3_StateModel/conflict_state_model.py`, the model is described as a Bayesian state estimator with:

- explicit ordered states: `PEACE -> CRISIS -> LIMITED_STRIKES -> ACTIVE_CONFLICT -> FULL_WAR`
- an expert-initialized transition matrix
- likelihood computation from signal-group profiles
- persistence of prior state probabilities across runs

Core update form:

`P_new(state_i) = normalise(sum_j [P_old(state_j) * T(j -> i)] * L(observations | state_i))`

Simplified interpretation:

`Posterior(state) ∝ Prior(state) × Likelihood(signals | state)`

Primary implementation source:

- `DIP_6/Layer3_StateModel/conflict_state_model.py`

## 4. Architecture Evidence

The public repo includes a pipeline diagram and architecture summary showing that the system is organized as a designed reasoning stack rather than a single script:

`Signals -> State Construction -> Council -> Verification -> Assessment Gate -> Report`

Relevant public docs:

- [architecture.md](architecture.md)
- [README.md](../README.md)

## 5. Reproducibility

The implementation exposes CLI commands for running both analysis and evaluation:

```bash
python run.py --experiment replay
python run.py --experiment ablation
python run.py --experiment leadtime
```

These commands are intended to make the evaluation surface inspectable and rerunnable from the implementation workspace.

## 6. Data Source Transparency

The documented implementation integrates publicly available OSINT and structured datasets, including:

- SIPRI
- GDELT
- ATOP
- World Bank
- V-Dem
- UCDP
- OFAC
- Comtrade
- Lowy

These sources are used as part of a broader multi-provider evidence stack rather than as a single proprietary dataset.

## 7. Failure Modes And Negative Evidence

The public artifacts also show where the system can fail or withhold judgment:

- sparse evidence can reduce confidence or trigger insufficient-evidence outcomes
- contradictory signals can survive into the deliberation stage and require red-team challenge
- gap groups are explicitly recorded in replay outputs
- the sample assessment notes evidence thinness and reduced robustness

Examples of visible failure evidence:

- `gap_groups` and `gaps` fields in replay outputs under `DIP_6/data/backtesting/results/*.json`
- red-team penalty and evidence thinness in [examples/sample_assessment.md](../examples/sample_assessment.md)

## 8. What This Proves

These artifacts together show that the project already provides:

- a mathematical core model
- executable experiments
- structured outputs
- explicit failure handling
- reproducible evaluation hooks

They do not yet prove that the full learning agenda is complete. That remains the purpose of the Phase-2 direction described in [phase2.md](phase2.md).
