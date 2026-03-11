# Sample Assessment

This is a sanitized example derived from a real saved assessment artifact. It shows the output format produced by the IND-Diplomat pipeline; it is not presented as a live forecast.

## Scenario

Persian Gulf escalation risk with emphasis on Iran-related nuclear tensions.

## Run Context

- **Query:** Assess the current risk of military escalation in the Persian Gulf region with focus on Iran nuclear program tensions
- **Country:** IRN
- **Report timestamp:** 05 March 2026, 01:58 UTC
- **Assessment status:** APPROVED

## Summary

```
RISK LEVEL:      ELEVATED
ESCALATION:      ██████████████░░░░░░░░░░░░░░░░ 47.3%
CONFIDENCE:      LOW (63.1%)
EPISTEMIC:       84.8% (evidence base quality)
```

## Conflict State (Bayesian Classification)

The Bayesian conflict-state model classified the current state as **ACTIVE CONFLICT** at 48.0% posterior probability:

```
Current State Posterior:
  PEACE                5.4%  ||
  CRISIS              11.7%  ||||
  LIMITED STRIKES     14.6%  |||||
  ACTIVE CONFLICT     48.0%  ||||||||||||||||||| <<<
  FULL WAR            20.3%  ||||||||

14-Day State Forecast:
  P(ACTIVE_CONFLICT or FULL_WAR in 14d): 74.7%
```

## Observed Signal Groups

Belief accumulation produced the following signal confidences:

| Signal Group | Confidence |
|---|---|
| economic_pressure | 1.000 |
| coercive | 0.950 |
| hostility | 0.950 |
| diplomacy_active | 0.950 |
| wmd_risk | 0.950 |
| cyber | 0.825 |
| alliance | 0.513 |
| force_posture | 0.425 |
| instability | 0.380 |
| mobilization | 0.150 |
| mil_escalation | 0.150 |

## Strategic Risk Engine Decomposition

```
Escalation Index = 0.35×Capability + 0.30×Intent + 0.20×Stability + 0.15×Cost + Trend Bonus

  Capability:     0.710  ×0.35  = 0.248
  Intent:         0.306  ×0.30  = 0.092
  Stability:      0.127  ×0.20  = 0.025
  Cost:           0.450  ×0.15  = 0.067
  ────────────────────────────────────────
  Base score:                    0.433
  Trend bonus:                  +0.040
  ESCALATION INDEX:              0.473
```

## Trajectory Forecast (14-day outlook)

```
Probability of HIGH in 14 days:   49%
Probability of LOW in 14 days:    15%
Probability of STABLE:            36%

Collection Expansion:   MEDIUM
Pre-War Early Warning:  INACTIVE
Acceleration Watch:     INACTIVE
```

## Black Swan Monitoring

```
Status: NO DISCONTINUITY DETECTED
All three detection channels clear.

Channel 1 (Spike Severity):           CLEAR
Channel 2 (Structural Discontinuity): CLEAR
Channel 3 (Rare High-Impact Signal):  CLEAR
```

## Council Deliberation

| Minister | Confidence | Key Signals |
|---|---|---|
| Security | 22% | SIG_MIL_MOBILIZATION, SIG_FORCE_POSTURE, SIG_LOGISTICS_PREP |
| Economic | 71% | SIG_ECONOMIC_PRESSURE, SIG_ALLIANCE_SHIFT |
| Domestic | 30% | SIG_DECEPTION_ACTIVITY, SIG_FORCE_POSTURE |
| Diplomatic | 50% | SIG_DIPLOMACY_ACTIVE, SIG_NEGOTIATION_BREAKDOWN, SIG_COERCIVE_BARGAINING |
| Contrarian | 73% | SIG_DIPLOMACY_ACTIVE, SIG_ALLIANCE_ACTIVATION |

## Red Team Challenge

- **Result:** Assessment found NOT ROBUST (penalty: −6.0%)
- **Evidence thinness:** Only 2 sources available — conclusions based on sparse evidence may be unreliable
- **Contradictory signals:** SIG_DIPLOMACY_ACTIVE=0.95 and SIG_DIP_HOSTILITY=0.95 are both elevated — analytically contradictory. Consider whether coercive diplomacy or dual-track signaling explains the pattern.

## Confidence Decomposition

```
confidence = 0.30×sensor + 0.20×verification + 0.15×logic + 0.20×meta + 0.15×document − red_team_penalty
```

| Component | Raw Score | Weight | Contribution |
|---|---|---|---|
| Sensor Fusion | 0.631 | 30% | 0.1894 |
| CoVe Verification | 0.816 | 20% | 0.1632 |
| Logic Consistency | 1.000 | 15% | 0.1500 |
| Minister Meta-Confidence | 0.500 | 20% | 0.1000 |
| Document/RAG Confidence | 0.000 | 15% | 0.0000 |
| Red Team Penalty | −0.060 | — | −0.0600 |
| **Total** | — | — | **63.1%** |

## Intelligence Gaps

- Missing: SIG_NEGOTIATION_BREAKDOWN
- Curiosity targets (VOI-ranked): SIG_DETERRENCE_SIGNALING (1.600), SIG_LOGISTICS_PREP (1.400), SIG_DECEPTION_ACTIVITY (1.320)

## Bias Detection

| Bias Type | Severity | Detail |
|---|---|---|
| Groupthink Risk | MEDIUM | All ministers reached consensus with no recorded conflicts |
| Legal Blind Spot | MEDIUM | No legal/treaty sources consulted |
| Sensor Anchoring | LOW | Final confidence very close to raw sensor score |

## Global Theater Synchronization

```
THEATER       SRE   P(HIGH)  CONTAGION  MODE
IRN         0.473     48.9%      0.000  MEDIUM

Systemic Cascade:   No (threshold: 4.0)
Highest Risk:       IRN (SRE=0.473)
```

## What To Watch Next

| Direction | Indicators |
|---|---|
| ▲ Would **increase** risk | Confirmed military mobilization, diplomatic channel closure, cyber attack on critical infrastructure, WMD program acceleration, alliance treaty invocation |
| ▼ Would **decrease** risk | Resumption of direct negotiations, withdrawal of forward-deployed assets, sanctions relief, third-party mediation acceptance |

## What This Example Demonstrates

- Bayesian conflict-state classification with posterior probabilities (not a single label)
- Weighted SRE decomposition with transparent formula
- Council reasoning with per-minister signal coverage
- Red team challenge that reduced final confidence by 6%
- CoVe verification integrated into confidence scoring
- Explicit intelligence gaps and VOI-ranked curiosity targets
- Bias detection and failure mode analysis
- Global theater synchronization with contagion tracking
- Dual-track output: empirical (Part A) and legal-political (Part B)
