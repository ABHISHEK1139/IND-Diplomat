# Layer-4 Quick Reference Guide

## What Was Built

A **structured reasoning engine** with an execution contract that makes all agents communicate through a shared `CouncilSession` object.

---

## Files to Know

| File | Purpose | Key Change |
|------|---------|-----------|
| [EXECUTION_CONTRACT.md](EXECUTION_CONTRACT.md) | Complete specification | Read first for full understanding |
| [DATA_FLOW_REFERENCE.md](DATA_FLOW_REFERENCE.md) | Visual architecture & examples | Trace how data flows through stages |
| [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) | What was delivered | What changed and why |
| `schema.py` | Data structures | Added `Hypothesis` class |
| `council_session.py` | Shared state | Added 8 control fields |
| `ministers.py` | Agents | Added `produce_hypothesis()` |
| `coordinator.py` | Pipeline | Added 8-stage orchestration |
| `layer4_unified_pipeline.py` | Entry point | Complete orchestration |

---

## The 8-Stage Pipeline (Exact Order)

```
CONVENE → CONFLICTS → RED_TEAM → CRAG → SYNTHESIZE → VERIFY → REFUSE? → HITL? → OUTPUT
```

**Stage 1: CONVENE_COUNCIL**
- Ministers propose hypotheses
- Extract observed signals from StateContext
- Output: `session.hypotheses[]`

**Stage 2: DETECT_CONFLICTS**
- Check if ministers disagree (>0.5 gap)
- Output: `session.identified_conflicts[]`

**Stage 3: RED_TEAM**
- Challenge weak hypotheses (<0.5 confidence)
- Output: `session.red_team_report`

**Stage 4: INVESTIGATE (CRAG)**
- Collect missing signals
- Can iterate multiple times
- Output: `session.missing_signals[]`

**Stage 5: SYNTHESIZE_DECISION**
- Aggregate to threat level
- Output: `session.final_confidence`, `session.assessment_report`

**Stage 6: VERIFY_CLAIMS (CoVe)**
- Verify matched signals in evidence log
- Output: `session.verification_score` (0.0-1.0)

**Stage 7: REFUSE?**
- If `verification_score < 0.7` → REFUSE
- Output: "System cannot determine... Additional evidence required."

**Stage 8: HITL?**
- If (HIGH threat AND LOW verification) → Escalate
- Output: Flag for human review

---

## The 3 Critical Rules

### Rule 1: Everything Goes Through CouncilSession

```python
# ✓ CORRECT
def my_stage(session: CouncilSession) -> CouncilSession:
    session.evidence_log.append(new_signal)
    return session

# ✗ WRONG
def my_stage(session):
    self.private_state = ...
```

### Rule 2: No Document Reading in Layer-4

```python
# ✓ CORRECT
mobilization = state_context.military.mobilization_level

# ✗ WRONG
text = read_pdf("document.pdf")
```

### Rule 3: Verification Determines Responsibility

```python
if session.verification_score < 0.7:
    return "System cannot determine... Additional evidence required."
    # This is intelligence, not failure
```

---

## Key Outputs to Watch

### `verification_score` (0.0 - 1.0)
How grounded are your claims?
- **≥ 0.7** → Make claim with confidence
- **< 0.7** → REFUSE to claim

### `identified_conflicts` (List[str])
Do ministers disagree?
- Empty → Consensus
- Non-empty → Red team activated

### `red_team_report` (Dict)
Did red team find weaknesses?
- None → No challenges
- Has "contradictions" → Alternative explanations exist

### `missing_signals` (List[str])
What evidence gaps exist?
- Empty → All signals accounted for
- Non-empty → Would trigger CRAG next iteration

### `king_decision` (str)
Final threat assessment:
- "LOW", "GUARDED", "ELEVATED", "HIGH", "CRITICAL", "ANOMALY"

---

## Using the Pipeline

### Simple Usage
```python
from Layer4_Analysis.layer4_unified_pipeline import run_layer4_analysis
from Layer3_StateModel.interface.state_provider import build_initial_state

state = build_initial_state("Is conflict likely?")
result = await run_layer4_analysis("Is conflict likely?", state)

print(f"Decision: {result['council_session']['status']}")
print(f"Verification: {result['council_session']['verification_score']}")
print(f"Refused: {result.get('refused', False)}")
```

### Advanced Usage (All Flags)
```python
result = await run_layer4_analysis(
    query="Is conflict likely?",
    state_context=state,
    user_id="analyst_42",
    enable_red_team=True,        # Challenge hypotheses
    max_investigation_loops=2,   # Allow CRAG iteration
)
```

### Via API (Already Integrated)
The unified pipeline is integrated with [Layer4_Analysis/core/unified_pipeline.py](Layer4_Analysis/core/unified_pipeline.py)

```
POST /v2/query
{
    "query": "Is conflict likely?",
    "country_code": "XYZ",
    "enable_red_team": true,
    "max_investigation_loops": 1
}
```

---

## Result Structure

```python
{
    "answer": "ELEVATED threat level...",
    "confidence": 0.71,
    "sources": [...],
    
    "council_session": {
        "session_id": "l4_exec_abc123",
        "status": "CONCLUDED",  # or "REFUSED"
        "verification_score": 1.0,  # CRITICAL
        "conflicts": ["High disagreement between ministers"],
        "needs_human_review": False,
        "minister_reports": {
            "Security Minister": {
                "confidence": 0.67,
                "hypothesis": "Military readiness..."
            },
            ...
        }
    }
}
```

---

## When Things Happen

### Conflict Detection (Stage 2)
- Triggered automatically
- Activates red team if gap > 0.5

### Red Team Challenge (Stage 3)
- Activated if: conflicts OR weak hypotheses
- Marks problematic assumptions
- Doesn't reject, just notes

### CRAG Investigation (Stage 4)
- Triggered if: missing signals exist
- Can iterate up to `max_investigation_loops`
- Would retrieve new Layer-1/2 data each loop

### Refusal (Stage 7)
- Triggered if: `verification_score < 0.7`
- System outputs: "Cannot determine... Additional evidence required."
- This is **intentional and intelligent**

### HITL Escalation (Stage 8)
- Triggered if: (threat is HIGH or CRITICAL) AND (verification < 0.7)
- Flags for human expert review
- System doesn't refuse, but asks for human judgment

---

## Troubleshooting

### "System cannot determine... Additional evidence required."
**This is correct behavior.**
- `verification_score < 0.7`
- Claims aren't grounded enough
- Either: provide more evidence, or accept the uncertainty

### "Conflict detected"
**This is correct behavior.**
- Ministers disagree by > 0.5 confidence
- Red team checks for alternative explanations
- System doesn't average conflicts - it investigates them

### "Needs human review"
**This is correct behavior.**
- System claims HIGH/CRITICAL threat
- But can't verify it well (verification < 0.7)
- Too important to decide automatically

### Empty `red_team_report`
**This is correct behavior.**
- No weak hypotheses
- No significant conflicts
- Ministers agree

---

## Performance Notes

- **Convene:** O(n) where n = number of ministers (fixed: 4)
- **Conflicts:** O(m) where m = number of hypotheses (≤ 4)
- **Verify:** O(c) where c = claims to verify (typically 5-20)
- **Total:** Sub-second for typical analysis

---

## What's Different Now

### Before
- Modules ran independently
- No shared reasoning state
- Claims made without grounding
- No refusal capability
- All outputs treated equally

### After
- All stages coordinate through `CouncilSession`
- Conflicts automatically detected
- Every claim verified (`verification_score`)
- System refuses when uncertain
- Output includes confidence metadata

---

## The Golden Rule

```
If verification_score >= 0.7:
    → Confidence level = final_confidence
    → Make claim
    
If verification_score < 0.7:
    → Refuse to claim
    → Output: "System cannot determine... Additional evidence required."
```

This single rule prevents hallucination and enforces responsibility.

---

## Documentation Map

Start here → [EXECUTION_CONTRACT.md](EXECUTION_CONTRACT.md)
Then read → [DATA_FLOW_REFERENCE.md](DATA_FLOW_REFERENCE.md)  
Deep dive → [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)  
Reference → This document

---

## Quick Checklist

- [ ] Read EXECUTION_CONTRACT.md
- [ ] Understand CouncilSession as shared state
- [ ] Know the 8 stages in order
- [ ] Remember: verification_score determines responsibility
- [ ] Understand refusal is intelligence
- [ ] Know when HITL is triggered
- [ ] Test with your data

---

## That's It

Layer-4 is now a structured reasoning engine, not a collection of modules.

You have:
✓ Execution contract (CouncilSession)
✓ Structured hypothesis (Hypothesis class)
✓ 8-stage pipeline
✓ Verification grounding
✓ Refusal capability
✓ Human escalation

**Ready for production.**

Questions? See EXECUTION_CONTRACT.md for complete details.
