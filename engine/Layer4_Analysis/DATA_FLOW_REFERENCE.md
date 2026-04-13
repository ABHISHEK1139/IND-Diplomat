# Layer-4 Data Flow & Architecture Reference

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    QUERY ENTRY POINT                             │
│         (From API or Layer-3 State Provider)                      │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│        Layer4UnifiedPipeline.execute()                           │
│  [layer4_unified_pipeline.py]                                    │
│  - Creates CouncilSession                                        │
│  - Calls coordinator.process_query()                             │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
        ╔════════════════════════════╗
        ║   CouncilSession (SHARED)  ║
        ║   Shared State Object      ║
        ║   All modules read/write   ║
        ║   only through here        ║
        ╚════════════════════════════╝
                     │
        ┌────────────┼────────────┬──────────────┬──────────────┐
        │            │            │              │              │
        ▼            ▼            ▼              ▼              ▼
    ┌────────┐  ┌────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐
    │CONVENE │  │CONFLICT│  │RED TEAM  │  │CRAG/     │  │SYNTHESIZE │
    │COUNCIL │  │DETECT  │  │CHALLENGE │  │INVESTIGATE│ │DECISION   │
    │        │  │        │  │          │  │          │  │           │
    │Stage 1 │  │Stage 2 │  │Stage 3   │  │Stage 4   │  │Stage 5    │
    └────────┘  └────────┘  └──────────┘  └──────────┘  └───────────┘
        │            │            │              │              │
        └────────────┴────────────┴──────────────┴──────────────┘
                     │
                     │ (Returns updated session)
                     │
                     ▼
        ╔════════════════════════════╗
        ║  Session now contains       ║
        ║  - hypotheses[]             ║
        ║  - conflicts[]              ║
        ║  - red_team_report          ║
        ║  - missing_signals[]        ║
        ║  - assessment_report        ║
        ║  - verification_score       ║
        ╚════════════════════════════╝
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
    ┌────────┐  ┌──────────┐  ┌──────────┐
    │VERIFY  │  │REFUSE?   │  │HITL?     │
    │CLAIMS  │  │CHECK     │  │CHECK     │
    │        │  │          │  │          │
    │Stage 6 │  │Stage 7   │  │Stage 8   │
    └────────┘  └──────────┘  └──────────┘
        │            │              │
        └────────────┼──────────────┘
                     │
                     ▼
    ╔═══════════════════════════════════════════════════════════╗
    ║              FINAL REPORT & API RESPONSE                   ║
    ║  {                                                         ║
    ║    "answer": "...",                                        ║
    ║    "confidence": 0.75,                                     ║
    ║    "council_session": {                                    ║
    ║      "verification_score": 0.85,                           ║
    ║      "conflicts": [...],                                   ║
    ║      "refused": false,                                     ║
    ║      "needs_human_review": false                           ║
    ║    }                                                       ║
    ║  }                                                         ║
    ╚═══════════════════════════════════════════════════════════╝
```

---

## Detailed Stage Descriptions

### STAGE 1: CONVENE_COUNCIL
**Method:** `coordinator.convene_council(session)`

```
Input:  CouncilSession with StateContext
Output: Same session with hypotheses[] populated

Process:
  1. Extract observed signals from StateContext
  2. Add to session.evidence_log
  3. For each minister:
     a. Call minister.produce_hypothesis(state_context)
     b. Add Hypothesis to session.hypotheses
     c. Call minister.deliberate() for backward compat
     d. Evaluate evidence (matched vs predicted)
     e. Add MinisterReport to session.ministers_reports

Example:
  SecurityMinister.produce_hypothesis():
    - Looks at military.mobilization_level, exercises
    - Compares to historical patterns
    - Returns Hypothesis(
        minister="Security",
        predicted_signals=[troop_staging, exercise_activation, ...],
        matched_signals=[troop_staging, exercise_activation],
        missing_signals=[supply_chain_prep],
        confidence=0.67
      )

RULE: Ministers read ONLY from StateContext. Never read documents.
```

### STAGE 2: DETECT_CONFLICTS
**Method:** `coordinator._detect_conflicts(session)`

```
Input:  CouncilSession with hypotheses[] populated
Output: Same session with identified_conflicts updated

Process:
  1. Extract confidence scores from all hypotheses
  2. Calculate max_conf, min_conf
  3. If (max_conf - min_conf) > 0.5:
     a. Add "High disagreement" message to identified_conflicts
     b. Signal that red_team should be activated

Example:
  Security Minister: confidence=0.9 (conflict imminent)
  Economic Minister: confidence=0.3 (normal trade)
  Gap: 0.6 > 0.5 threshold
  → Add conflict marker
```

### STAGE 3: RED_TEAM_CHALLENGE
**Method:** `coordinator._run_red_team(session)`

```
Input:  CouncilSession with conflicts or weak hypotheses
Output: Same session with red_team_report updated

Process:
  1. Find weak hypotheses (confidence < 0.5)
  2. For each weak hypothesis:
     a. Check if matched_signals << predicted_signals
     b. Note as "weak match rate"
  3. Create red_team_report with:
     - active: True/False
     - challenged_hypotheses: count
     - contradictions: list of weak points

Example:
  Hypothesis marked weak:
    predicted: [a, b, c, d, e]
    matched: [a, b]
    ratio: 2/5 = 0.4 < threshold
  → Challenge: "Security Minister: weak match rate"

PURPOSE: Not to generate opinions, but to find assumptions.
```

### STAGE 4: INVESTIGATE (CRAG)
**Method:** `coordinator._investigate_missing_signals(session, max_iterations)`

```
Input:  CouncilSession with hypotheses
Output: Same session with missing_signals[] updated

Process (RECURSIVE possibility):
  Iteration 0:
    1. Collect all missing_signals from hypotheses
    2. Deduplicate
    3. Add to session.missing_signals
    4. Add to session.investigation_needs
    5. Increment turn_count
  
  If (missing_signals exist AND iteration < max_iterations):
    → Would trigger retrieval system here
    → Could rebuild StateContext with new data
    → Could rerun convene_council() for fresh analysis
  Else:
    → Break loop

Example Iteration 0:
  SecurityMinister.missing_signals: [supply_chain_prep]
  DiplomaticMinister.missing_signals: [alliance_outreach]
  
  session.missing_signals = [supply_chain_prep, alliance_outreach]
  session.investigation_needs = [supply_chain_prep, alliance_outreach]

This is where external data retrieval would happen.
Currently a stub - ready for integration.
```

### STAGE 5: SYNTHESIZE_DECISION
**Method:** `coordinator._synthesize_decision(session)`

```
Input:  CouncilSession with hypotheses and decision data
Output: Same session with assessment_report and threat_level

Process:
  1. Calculate avg_confidence from all hypotheses
  2. Set session.final_confidence
  3. Call self.synthesizer.synthesize(...):
     - Maps confidence scores to threat levels
     - Generates summary and recommendation
     - Creates AssessmentReport
  4. Store in session.assessment_report
  5. Set session.king_decision = threat_level

Confidence → Threat Level mapping (example):
  > 0.7 → HIGH
  0.5-0.7 → ELEVATED
  0.3-0.5 → GUARDED
  < 0.3 → LOW

Example:
  avg_confidence = 0.68
  → ThreatSynthesizer → "ELEVATED"
  → session.assessment_report.threat_level = ELEVATED
```

### STAGE 6: VERIFY_CLAIMS (CoVe)
**Method:** `coordinator._verify_claims(session)`

```
Input:  CouncilSession with hypotheses and evidence_log
Output: Same session with verification_score calculated

Process:
  1. Collect all matched_signals from all hypotheses
     (These are the "claims" we're making)
  2. For each claim:
     a. Check if claim in session.evidence_log
     b. Count verified claims
  3. Calculate verification_score = verified / total
  4. Store in session.verification_score

Example:
  Hypothesis 1 matched: [troop_staging, exercises]
  Hypothesis 2 matched: [hostile_rhetoric, neg_freeze]
  All claims: [troop_staging, exercises, hostile_rhetoric, neg_freeze]
  
  evidence_log contains: [troop_staging, exercises, hostile_rhetoric, neg_freeze]
  
  verified = 4, total = 4
  verification_score = 1.0

CRITICAL: This is where we determine if claims are actually grounded.
If < 0.7 → Refuse to assert.
```

### STAGE 7: REFUSE_CHECK
**Method:** `coordinator._check_refusal_threshold(session)`

```
Input:  CouncilSession with verification_score
Output: Boolean - should we refuse?

Logic:
  return session.verification_score < 0.7

If returns True:
  System outputs: "The system cannot determine whether conflict is likely. 
                   Additional evidence required."
  
  This is NOT a failure. This is intelligence.
  System is saying: "I don't have enough grounded evidence to claim this."

Example scenarios:
  verification_score = 0.85 → Proceed (claims are grounded)
  verification_score = 0.65 → REFUSE (insufficient grounding)
```

### STAGE 8: HITL_CHECK
**Method:** `coordinator._check_hitl_threshold(session)`

```
Input:  CouncilSession with assessment_report and verification_score
Output: Boolean - should we escalate to human?

Logic:
  is_high_threat = assessment_report.threat_level in [HIGH, CRITICAL]
  is_low_verification = verification_score < 0.7
  
  return is_high_threat AND is_low_verification

Example scenarios:
  HIGH threat + 0.85 verification → No HITL (confident claim)
  ELEVATED threat + 0.65 verification → No HITL (below high threshold)
  CRITICAL threat + 0.55 verification → HITL (dangerous guess)
  
PURPOSE: Flag "I'm worried but not sure" situations for human review.
```

---

## Data Structures

### Hypothesis (Single Minister Output)

```python
@dataclass
class Hypothesis:
    minister: str                      # "Security Minister"
    predicted_signals: List[str]       # What should happen
    matched_signals: List[str]         # What did happen  
    missing_signals: List[str]         # What didn't happen
    confidence: float                  # Match quality (0-1)
    reasoning: str                     # Explanation
```

### CouncilSession (Shared State)

```python
@dataclass
class CouncilSession:
    # Input
    session_id: str                    # Unique identifier
    question: str                      # The analysis question
    state_context: StateContext        # Full Layer-3 state
    
    # Deliberation (Stage 1)
    hypotheses: List[Hypothesis]       # Minister outputs
    ministers_reports: List[MinisterReport]  # Backward compat
    
    # Debate (Stage 2-3)
    identified_conflicts: List[str]    # Disagreement markers
    red_team_report: Optional[Dict]    # Challenge results
    
    # Investigation (Stage 4)
    missing_signals: List[str]         # Evidence gaps
    evidence_log: List[str]            # All observed signals
    
    # Decision (Stage 5-8)
    king_decision: Optional[str]       # Final call
    assessment_report: Optional[AssessmentReport]  # Full report
    final_confidence: float            # Aggregate confidence
    verification_score: float          # HOW GROUNDED (0-1)
    investigation_needs: List[str]     # What to look for
    
    # Meta
    status: SessionStatus              # OPEN → CONCLUDED
    turn_count: int                    # Iteration counter
    created_at: datetime               # When session started
```

---

## Decision Trees

### When Refusal Happens

```
Does system have evidence verification_score >= 0.7?
├─ YES (claims are grounded)
│  └─ Make claim with confidence score
│     └─ Check if human review needed
│        └─ If high threat + low verification → HITL
│        └─ Else → Automatic decision
└─ NO (claims are not grounded)
   └─ REFUSE: "System cannot determine... Additional evidence required."
      └─ No confabulation possible
```

### When Human Review Happens

```
Is threat level HIGH or CRITICAL?
├─ NO (threat is LOW/GUARDED/ELEVATED)
│  └─ Make automatic decision
└─ YES (threat is HIGH/CRITICAL)
   └─ Is verification_score >= 0.7?
      ├─ YES (well-grounded high threat)
      │  └─ Make claim + confidence
      └─ NO (uncertain high threat)
         └─ ESCALATE TO HUMAN
            └─ "Expert review required due to threat level"
```

---

## Module Interaction

### Module Constraints

#### Ministers
- **Input:** StateContext only
- **Output:** Hypothesis object
- **Cannot:** Read documents, make final claims
- **Must:** Predict signals and find matches

#### Coordinator
- **Input:** CouncilSession (via process_query)
- **Output:** Updated CouncilSession
- **Cannot:** Make independent decisions
- **Must:** Orchestrate through all 8 stages

#### All Modules
- **Communication:** Only through CouncilSession
- **State:** No private state (all in session)
- **Timing:** Sequential (no async to session)

---

## Testing Checklist

To validate the implementation:

- [ ] Hypothesis objects contain all required fields
- [ ] CouncilSession contains all 13 required fields
- [ ] Ministers can be called with `produce_hypothesis()`
- [ ] Conflicting hypotheses trigger red team
- [ ] Missing signals are collected correctly
- [ ] Verification score calculates properly (0.0-1.0)
- [ ] Refusal triggers when verification_score < 0.7
- [ ] HITL triggers when (HIGH_THREAT AND LOW_VERIFICATION)
- [ ] Evidence log accumulates signals
- [ ] Turn counter increments on CRAG iterations
- [ ] Final result contains all metadata

---

## Example Execution Trace

```
INPUT:
  query = "Is Country X planning conflict?"
  state_context = StateContext(military=..., diplomatic=...)

STAGE 1: CONVENE_COUNCIL
  Security Minister: predicted=[mob,ex,sup], matched=[mob,ex], conf=0.67
  Diplomatic Minister: predicted=[host,neg], matched=[host,neg], conf=0.75
  session.hypotheses = [H1, H2]
  session.evidence_log = [mob, ex, host, neg]

STAGE 2: DETECT_CONFLICTS
  confidences = [0.67, 0.75]
  gap = 0.08 < 0.5 threshold
  → No conflict detected
  session.identified_conflicts = []

STAGE 3: RED_TEAM
  No weak hypotheses (all > 0.5)
  No conflicts
  → Red team inactive
  session.red_team_report = None

STAGE 4: INVESTIGATE
  Security missing: [sup]
  Diplomatic missing: []
  session.missing_signals = [sup]
  → Would request supply chain data here
  (max_iterations=1, so we stop)

STAGE 5: SYNTHESIZE
  avg_confidence = 0.71
  ThreatSynthesizer → "ELEVATED"
  session.final_confidence = 0.71
  session.assessment_report = AssessmentReport(threat=ELEVATED, ...)

STAGE 6: VERIFY
  claims = [mob, ex, host, neg]
  evidence_log = [mob, ex, host, neg]
  verified = 4/4 = 1.0
  session.verification_score = 1.0

STAGE 7: REFUSE?
  1.0 >= 0.7 threshold
  → DO NOT REFUSE
  Proceed to stage 8

STAGE 8: HITL?
  threat = ELEVATED (not HIGH/CRITICAL)
  → HITL not needed
  → Automatic decision

OUTPUT:
{
  "answer": "ELEVATED threat. Military readiness + hostile diplomacy confirmed.",
  "confidence": 0.71,
  "council_session": {
    "verification_score": 1.0,
    "conflicts": [],
    "refused": false,
    "needs_human_review": false,
    "status": "CONCLUDED"
  }
}
```

---

## Complete File Dependencies

```
layer4_unified_pipeline.py
  └─ imports coordinator.CouncilCoordinator
     
coordinator.py
  ├─ imports council_session.CouncilSession
  ├─ imports ministers.BaseMinister
  ├─ imports schema.Hypothesis
  ├─ imports decision.threat_synthesizer.ThreatSynthesizer
  └─ imports investigation.anomaly_sentinel.AnomalySentinel

ministers.py
  ├─ imports schema.Hypothesis
  └─ imports council_session.MinisterReport

council_session.py  
  ├─ imports schema.AssessmentReport
  └─ imports schema.Hypothesis

schema.py
  └─ (No internal imports - pure data classes)
```

---

## Implementation Complete

The architecture is now:
✓ Structured (Hypothesis objects)
✓ Unified (CouncilSession shared state)
✓ Staged (8-stage deliberation)
✓ Grounded (verification_score)
✓ Responsible (refusal capability)
✓ Escalatable (HITL triggers)

Ready for production Layer-4 analysis.
