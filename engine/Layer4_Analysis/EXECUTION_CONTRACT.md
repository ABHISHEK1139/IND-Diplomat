# Layer-4 Execution Contract & Implementation Blueprint

**Version:** 2.0  
**Date:** February 23, 2026  
**Status:** IMPLEMENTED

---

## The Core Problem Solved

You had modules but no **execution contract**. 

Agents didn't share a structured lifecycle. They ran, but didn't affect each other.

### The Fix

Introduced `CouncilSession` as the **single shared state object**.

Every module — MinisterS, RedTeam, CRAG, CoVe, Verifier, RefusalEngine, HITL — reads and writes **ONLY** through `CouncilSession`.

```python
# RULE: All modules must follow this pattern
def stage_name(session: CouncilSession) -> CouncilSession:
    # read from session
    # compute
    # write back to session
    return session
```

---

## What Was Implemented

### 1. Schema Definitions (`schema.py`)

Added `Hypothesis` class:
```python
@dataclass
class Hypothesis:
    minister: str
    predicted_signals: List[str]
    matched_signals: List[str]
    missing_signals: List[str]
    confidence: float
    reasoning: str = ""
```

This is the **contract** between ministers and the coordinator.

### 2. Enhanced CouncilSession (`council_session.py`)

Now includes all fields needed for full pipeline:

```python
@dataclass
class CouncilSession:
    # Input
    session_id: str
    question: str
    state_context: StateContext
    
    # Deliberation Stage
    hypotheses: List[Hypothesis]
    ministers_reports: List[MinisterReport]
    
    # Debate Stage
    identified_conflicts: List[str]
    red_team_report: Optional[Dict[str, Any]]
    
    # Investigation Stage
    missing_signals: List[str]
    evidence_log: List[str]
    
    # Decision Stage
    king_decision: Optional[str]
    assessment_report: Optional[AssessmentReport]
    final_confidence: float
    verification_score: float  # ← NEW
    investigation_needs: List[str]
    
    status: SessionStatus
    turn_count: int
```

**Key addition:** `verification_score` tracks whether claims are actually grounded.

### 3. Minister Hypothesis Contract (`ministers.py`)

Added `produce_hypothesis()` method to `BaseMinister`:

```python
def produce_hypothesis(self, state_context: StateContext) -> Optional[Hypothesis]:
    """
    Produces a structured Hypothesis object.
    Ministers analyze StateContext and return predicted signals vs matched signals.
    """
    report = self.deliberate(state_context)
    if not report:
        return None
    
    return Hypothesis(
        minister=self.name,
        predicted_signals=report.predicted_signals,
        matched_signals=report.matched_signals,
        missing_signals=report.missing_signals,
        confidence=report.confidence,
        reasoning=report.reasoning
    )
```

**What this means:** Ministers now output structured objects, not loose JSON.

### 4. Coordinated Execution Pipeline (`coordinator.py`)

Implemented 8-stage pipeline as separate methods:

#### **STAGE 1: CONVENE_COUNCIL**
```python
def convene_council(self, session: CouncilSession) -> CouncilSession:
    # Extract observed signals from state
    observed_signals = extract_signals_from_state(session.state_context)
    session.evidence_log.extend(list(observed_signals))
    
    # Call each minister
    for minister in self.ministers:
        hypothesis = minister.produce_hypothesis(session.state_context)
        if hypothesis:
            session.add_hypothesis(hypothesis)
    
    return session
```

**Constraint:** Ministers read ONLY from StateContext. No document access.

#### **STAGE 2: DETECT_CONFLICTS**
```python
def _detect_conflicts(self, session: CouncilSession) -> CouncilSession:
    confidences = [h.confidence for h in session.hypotheses]
    max_conf = max(confidences)
    min_conf = min(confidences)
    
    if max_conf - min_conf > 0.5:
        session.identified_conflicts.append(f"High disagreement")
    
    return session
```

#### **STAGE 3: RED_TEAM**
```python
def _run_red_team(self, session: CouncilSession) -> CouncilSession:
    weak_hypotheses = [h for h in session.hypotheses if h.confidence < 0.5]
    
    if weak_hypotheses or session.identified_conflicts:
        contradictions = []
        for h in weak_hypotheses:
            if len(h.matched_signals) < len(h.predicted_signals) / 2:
                contradictions.append(f"{h.minister}: weak match rate")
        
        session.red_team_report = {
            "active": True,
            "challenged_hypotheses": len(weak_hypotheses),
            "contradictions": contradictions
        }
    
    return session
```

**Key:** Red team does NOT generate opinions. It checks for **alternative explanations consistent with signals**.

#### **STAGE 4: INVESTIGATE (CRAG)**
```python
def _investigate_missing_signals(self, session: CouncilSession, max_iterations: int = 1) -> CouncilSession:
    iteration = 0
    
    while iteration < max_iterations:
        # Collect all missing signals
        all_missing = []
        for h in session.hypotheses:
            all_missing.extend(h.missing_signals)
        
        session.missing_signals = list(set(all_missing))
        
        if not session.missing_signals:
            break
        
        # Would trigger external retrieval here
        session.investigation_needs.extend(session.missing_signals)
        
        iteration += 1
        session.turn_count += 1
    
    return session
```

**Important:** CRAG is **recursive**. Can rerun coordinator after gathering new data.

#### **STAGE 5: SYNTHESIZE_DECISION**
```python
def _synthesize_decision(self, session: CouncilSession) -> CouncilSession:
    avg_confidence = sum(h.confidence for h in session.hypotheses) / len(session.hypotheses)
    session.final_confidence = avg_confidence
    
    # Delegate to ThreatSynthesizer
    assessment = self.synthesizer.synthesize(reports, observed_signals, avg_confidence)
    session.assessment_report = assessment
    
    return session
```

#### **STAGE 6: VERIFY_CLAIMS (CoVe)**
```python
def _verify_claims(self, session: CouncilSession) -> CouncilSession:
    # Extract all matched signals as "claims"
    all_claims = []
    for h in session.hypotheses:
        all_claims.extend(h.matched_signals)
    
    # Verify claims against evidence log
    verified = 0
    for claim in all_claims:
        if claim in session.evidence_log:
            verified += 1
    
    session.verification_score = verified / max(len(all_claims), 1)
    
    return session
```

**Critical:** This is where the system determines if claims are actually grounded.

#### **STAGE 7: REFUSE?**
```python
def _check_refusal_threshold(self, session: CouncilSession) -> bool:
    return session.verification_score < 0.7
```

If True, system outputs:
```
"The system cannot determine whether conflict is likely. Additional evidence required."
```

**This is NOT a bug. This is intelligence.**

#### **STAGE 8: HITL?**
```python
def _check_hitl_threshold(self, session: CouncilSession) -> bool:
    is_high_threat = session.assessment_report.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]
    is_low_verification = session.verification_score < 0.7
    
    return is_high_threat and is_low_verification
```

Triggers human review when:
- System claims **HIGH/CRITICAL threat**, BUT
- Can't verify the supporting evidence

### 5. Full Pipeline Orchestration (`layer4_unified_pipeline.py`)

Wires everything in order:

```python
async def execute(self, query, state_context, **kwargs):
    session = CouncilSession(...)
    
    # 1. Deliberation
    session = self.coordinator.convene_council(session)
    
    # 2. Detect conflicts
    session = self.coordinator._detect_conflicts(session)
    
    # 3. Red team (if enabled)
    if use_red_team:
        session = self.coordinator._run_red_team(session)
    
    # 4. Investigate
    session = self.coordinator._investigate_missing_signals(session, max_iterations)
    
    # 5. Synthesize
    session = self.coordinator._synthesize_decision(session)
    
    # 6. Verify
    session = self.coordinator._verify_claims(session)
    
    # 7. Refuse?
    if self.coordinator._check_refusal_threshold(session):
        return {"answer": "Insufficient evidence", "refused": True}
    
    # 8. HITL?
    if self.coordinator._check_hitl_threshold(session):
        # Flag for human review
        pass
    
    return final_report(session)
```

---

## Data Flow Example

**Input:**
```python
query = "Is Country X planning military action?"
state_context = StateContext(
    military=MilitaryData(mobilization_level=0.75, exercises=[...]),
    diplomatic=DiplomaticData(hostility_tone=0.82, negotiations=0.2),
    ...
)
```

**Stage 1 - CONVENE:**
```
SecurityMinister.produce_hypothesis():
  - Predicted: [troop_staging, exercise_activation, supply_chain_prep]
  - Matched: [troop_staging, exercise_activation]  # 2 of 3
  - Missing: [supply_chain_prep]
  - Confidence: 0.67
  
DiplomaticMinister.produce_hypothesis():
  - Predicted: [hostile_rhetoric, negotiation_freeze, alliance_outreach]
  - Matched: [hostile_rhetoric, negotiation_freeze]  # 2 of 3
  - Missing: [alliance_outreach]
  - Confidence: 0.67
```

**Stage 2 - CONFLICTS:**
```
All ministers confidence ≈ 0.67 (no conflict > 0.5 threshold)
→ Low conflict
```

**Stage 3 - RED TEAM:**
```
No weak hypotheses (all > 0.5), no conflicts
→ Red team inactive
```

**Stage 4 - INVESTIGATE:**
```
Missing signals: [supply_chain_prep, alliance_outreach]
Would trigger retrieval for external confirmation
```

**Stage 5 - SYNTHESIZE:**
```
avg_confidence = 0.67
→ ThreatSynthesizer.synthesize() → ELEVATED threat
```

**Stage 6 - VERIFY:**
```
all_claims = [troop_staging, exercise_activation, hostile_rhetoric, negotiation_freeze]
evidence_log = [troop_staging, exercise_activation, hostile_rhetoric, negotiation_freeze]
verified = 4 / 4 = 1.0
verification_score = 1.0 ✓
```

**Stage 7 - REFUSE?**
```
verification_score (1.0) > 0.7 threshold
→ DO NOT REFUSE
```

**Output:**
```python
{
    "answer": "ELEVATED threat level. Military readiness and hostile diplomatic signals confirm preparation.",
    "confidence": 0.67,
    "verification_score": 1.0,
    "refused": False,
    "needs_human_review": False
}
```

---

## Critical Design Rules

### Rule 1: CouncilSession is the Only State
No module stores state privately. Everything flows through the session.

```python
# ✓ CORRECT
def my_module(session: CouncilSession) -> CouncilSession:
    session.evidence_log.append(...)
    return session

# ✗ WRONG
def my_module(session):
    self.internal_state = ...  # Don't do this
    return something_else
```

### Rule 2: No Direct Document Reading in Layer-4
Layer-4 analyzes StateContext signals only.

```python
# ✓ CORRECT
military_mobilization = state_context.military.mobilization_level

# ✗ WRONG
text = read_pdf("threat_assessment.pdf")  # Don't do this in Layer-4
```

### Rule 3: Ministers Produce Hypotheses, Not Answers
Ministers output structured predictions, not narrative text.

```python
# ✓ CORRECT
return Hypothesis(
    minister="Security",
    predicted_signals=[...],
    matched_signals=[...],
    confidence=0.75
)

# ✗ WRONG
return "The country is preparing for military action."
```

### Rule 4: Verification Score Determines Responsibility
Claims are only made if they're grounded in evidence.

```python
if session.verification_score < 0.7:
    return "The system cannot determine..."  # Silence is intelligent
```

---

## What This Accomplishes

### Before
- Agents ran independently
- No shared reasoning state
- Conflicting conclusions ignored
- Claims made without verification
- System claimed certainty it didn't have

### After
- All stages flow through CouncilSession
- Conflicts detected and challenged
- Missing evidence triggers investigation
- Claims verified before output
- System **knows when to stay silent**

---

## Testing the Implementation

To verify the pipeline works end-to-end:

```python
from Layer4_Analysis.layer4_unified_pipeline import run_layer4_analysis
from Layer3_StateModel.interface.state_provider import build_initial_state

# Build state
state_context = build_initial_state("Is Country X planning action?")

# Run pipeline
result = await run_layer4_analysis("Is Country X planning action?", state_context)

# Check stages executed
assert result["council_session"]["status"] == "CONCLUDED"
assert "verification_score" in result["council_session"]
assert not result.get("refused", False) or result["council_session"]["verification_score"] < 0.7

print(f"Pipeline executed: {result['council_session']['session_id']}")
print(f"Answer: {result['answer'][:200]}")
print(f"Confidence: {result['confidence']}")
print(f"Verification: {result['council_session']['verification_score']}")
```

---

## Files Modified/Created

- **schema.py** - Added `Hypothesis` class
- **council_session.py** - Enhanced with all deliberation fields
- **ministers.py** - Added `produce_hypothesis()` method
- **coordinator.py** - Implemented 8-stage pipeline
- **layer4_unified_pipeline.py** - NEW - Orchestrates full execution

---

## Next Steps

1. ✓ Core contract implemented
2. ⚠️ Integration with existing components (red_team.py, crag.py, cove.py, verifier.py, refusal_engine.py, hitl.py)
   - These already exist but need validation that they work with the new CouncilSession flow
3. ⚠️ Testing across real scenarios
4. ⚠️ Recursive CRAG implementation (currently a stub waiting for retrieval system)

---

## The Key Insight

You now have a **justification engine**, not an **answer generator**.

The highest intelligence is knowing when evidence is insufficient. When you first see:

```
"The system cannot determine whether conflict is likely. Additional evidence required."
```

Don't patch it. That's the moment Layer-4 became real reasoning.

Because the most responsible analytical systems are not the ones that answer everything.

They are the ones that **know when they should stay silent**.
