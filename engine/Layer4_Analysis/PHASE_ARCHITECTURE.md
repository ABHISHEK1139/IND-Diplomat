# Layer-4 Phase Architecture

Layer-4 is organized by cognitive function, not coding history.

## Phase Layout

- `0_core`: runtime orchestration and shared execution spine.
- `1_intake`: question scope and analyst task shaping.
- `2_hypothesis`: hypothesis generation and search/planning of candidate explanations.
- `3_evidence`: evidence requirements, observed-signal extraction, and gap analysis.
- `4_deliberation`: debate and adversarial challenge between competing hypotheses.
- `5_decision`: verification, refinement, and final decision shaping/refusal.
- `6_investigation`: active evidence acquisition controls and anomaly/deception monitors.
- `7_safety`: guardrails and safety firewalls.
- `8_interfaces`: UI/CLI adapters and interaction surfaces.

## Compatibility Rule

Root modules in `Layer4_Analysis/*.py` are compatibility shims that re-export the moved implementations from phase folders. Existing imports such as:

`from Layer4_Analysis.coordinator import Coordinator`

remain valid.

## Support Models

`Layer4_Analysis/support_models/` contains legacy advisory models demoted from the old Layer-3 reasoning path. They are optional analytical aids and are not a parallel decision layer.

## Dependency Boundary Rule

Phase modules should not import later phases. Runtime flow is:

`1_intake -> 2_hypothesis -> 3_evidence -> 4_deliberation -> 5_decision`

with `6_investigation` feeding additional evidence into the loop.

`0_core` is allowed to coordinate across phases. `7_safety` should remain isolated except for `0_core` hooks.

## Layer-3 Boundary Rule

Layer-4 phase modules may import Layer-3 only via:

`Layer3_StateModel.interface.state_provider`

No direct Layer-3 internal imports are allowed in phase modules.
