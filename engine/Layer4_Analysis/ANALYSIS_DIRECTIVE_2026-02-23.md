# Layer-4 Architecture Directive (Analyzed and Locked)

**Date:** February 23, 2026  
**Source:** User architectural diagnosis and implementation blueprint  
**Intent:** Analysis capture only (no code changes in this step)

---

## 1) Core Assessment

The project is correctly framed as an **epistemic pipeline**, not a chatbot:

`Observation -> Signals -> StateContext -> Analysis -> Explanation`

Primary strengths to preserve:
- Council decomposition (intake, hypothesis, evidence, deliberation, decision, safety, investigation)
- Verifier separated from Analyst
- Refusal, gap analysis, investigation control, red-team logic
- Layer-3 state modeling as situational reality engine
- Layer-2 legal signals as pre-action legitimacy indicator

---

## 2) Critical Risk (Main Failure Mode)

The architecture has two potential knowledge paths:

- Path A (valid): `L1 -> L2 -> L3 -> L4`
- Path B (invalid): `L4 -> investigation -> documents -> L4 reasoning`

If Layer-4 reasons from documents instead of StateContext, grounding degrades into retrieval-dependent narrative generation.  
This converts "missing real-world signals" into "missing retrieval," causing unstable conclusions and potential infinite search loops.

---

## 3) Non-Negotiable Layer Contracts

Layer definitions are locked as follows:

- **Layer-1 (Observation):** raw observations only, no interpretation
- **Layer-2 (Knowledge):** structured signals extraction, no geopolitical conclusions
- **Layer-3 (Reality):** StateContext as single source of truth for world state
- **Layer-4 (Analysis):** explanation/justification only, no direct measurement

Boundary rule:
- Layer-4 may consume only:
1. `StateContext`
2. KGI coverage reports
3. provenance summaries (not raw text)

Layer-4 must not consume:
- raw documents
- PDF/article text
- direct claim snippets from retrieval results

---

## 4) Boundary Lock Requirement

Enforce import boundary:
- Layer-4 may import Layer-3 only via:
  `Layer3_StateModel/interface/state_provider.py`
- No direct Layer-2 imports from Layer-4
- No direct document reasoning inside Layer-4 deliberation/evidence stages

---

## 5) State-Only Investigation Mode

Required investigation cycle:

`documents -> Layer2 signal extraction -> Layer3 state rebuild -> updated StateContext -> Layer4 re-analysis`

Layer-4 should never parse or quote retrieved text directly.  
Investigation updates world state; it does not feed narrative evidence into council reasoning.

---

## 6) Layer-4 Execution Contract (Session-Centric)

Layer-4 must run through a shared `CouncilSession` lifecycle so all modules coordinate through one state object:

- hypotheses
- conflicts
- red-team output
- missing signals
- evidence log
- final decision
- verification score
- status

Any component bypassing `CouncilSession` should be considered contract violation.

---

## 7) Ordered Implementation Plan (Strict Sequence)

1. Define strict Layer-4 schema contract (`Hypothesis`, `AssessmentDecision`)
2. Enforce session-centric control flow with `CouncilSession`
3. Convert ministers to structured hypothesis testers
4. Coordinator collects hypotheses, evidence, and missing signals; detects disagreement
5. Red-team runs on conflict or low-confidence conditions
6. CRAG investigates missing signals and triggers state rebuild/re-run
7. Threat synthesizer creates decision from evidence-grounded confidence
8. CoVe decomposes atomic claims
9. Verifier checks claim support against evidence log
10. Refusal engine handles insufficient verification
11. HITL triggers on high-risk + low verification
12. Unified pipeline wires full lifecycle end-to-end

---

## 8) Scientific Validation Gate (Must-Have)

Implement counterfactual grounding harness:

- Change StateContext while keeping question constant
- Example interventions:
  - remove military buildup
  - add economic dependence
  - invert diplomatic hostility
- Re-run Layer-4 analysis

Pass criterion:
- Conclusion changes in response to state interventions

Fail criterion:
- Conclusion remains mostly invariant (indicates LLM prior dominance over state grounding)

---

## 9) Definition of "Done"

Layer-4 is considered valid only when:
- direct document-to-council reasoning path is eliminated
- all council stages operate through `CouncilSession`
- verification and refusal are active and enforceable
- counterfactual harness demonstrates state-sensitive reasoning behavior

Until these pass, system status is: **architecture-complete but scientifically unvalidated**.

