"""
Core.legal.signal_interpreter — Behavior-to-Legal Mapping Layer
=================================================================

**THE MISSING ARCHITECTURAL PIECE**

Problem:
    Signals are abstract indicators (SIG_MIL_ESCALATION, SIG_FORCE_POSTURE).
    Law operates on **acts** — concrete real-world behaviors like
    "threat of force", "blockade of a port", "forward military deployment".

    The legal reasoner cannot compute treaty applicability when all it
    receives is "SIG_MIL_ESCALATION" — it needs to know WHAT the state
    is actually DOING, in language that maps to treaty provisions.

Solution:
    This module translates observed signal combinations into structured
    **InferredBehavior** records that describe:
        1. behavior — what the state is actually doing (concrete act)
        2. legal_test — the legal question framed in treaty language
        3. relevant_instruments — which treaties/articles are most relevant
        4. severity — low / medium / high / critical

    The output is injected into the LLM user prompt as an "INFERRED
    STATE BEHAVIORS" section, giving the legal reasoner concrete acts
    to evaluate against the evidence.

Pipeline position:
    signals → signal_legal_mapper → **signal_interpreter** → rag_bridge → formatter → reasoner

Design constraints:
    • No LLM calls — purely deterministic mapping
    • Combo rules fire first (SIG_A + SIG_B → richer interpretation)
    • Falls back to individual signal rules
    • Idempotent — safe to call multiple times per assessment
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

logger = logging.getLogger("Core.legal.signal_interpreter")


# ═══════════════════════════════════════════════════════════════════════
# DATA CLASS
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class InferredBehavior:
    """One concrete state behavior inferred from signal combinations."""
    behavior: str                   # What the state is doing (plain English)
    legal_test: str                 # The legal question in treaty language
    relevant_instruments: List[str] # Most relevant treaties/articles
    severity: str                   # low | medium | high | critical
    triggering_signals: List[str]   # Which signals produced this inference
    legal_domain: str               # use_of_force, maritime, sanctions, etc.

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_prompt_text(self) -> str:
        """Format for injection into LLM user prompt."""
        instruments = ", ".join(self.relevant_instruments) if self.relevant_instruments else "general international law"
        return (
            f"BEHAVIOR: {self.behavior}\n"
            f"LEGAL QUESTION: {self.legal_test}\n"
            f"RELEVANT LAW: {instruments}\n"
            f"SEVERITY: {self.severity.upper()}\n"
            f"SIGNALS: {', '.join(self.triggering_signals)}"
        )


# ═══════════════════════════════════════════════════════════════════════
# COMBO RULES — most specific, tried first
# ═══════════════════════════════════════════════════════════════════════
# Each combo is a frozenset of signals → InferredBehavior template.
# Combos that match MORE signals are tried first (most specific wins).

_COMBO_RULES: List[Tuple[FrozenSet[str], Dict[str, Any]]] = [
    # ── Military escalation + force posture → forward deployment ─
    (
        frozenset({"SIG_MIL_ESCALATION", "SIG_FORCE_POSTURE"}),
        {
            "behavior": "Forward deployment of combat-ready forces near another state's border or territory, suggesting preparation for cross-border military operations",
            "legal_test": "Does the forward deployment of military forces constitute a 'threat of force' prohibited by Article 2(4) of the UN Charter? Is the positioning of forces at a border an implicit threat sufficient to trigger the prohibition?",
            "relevant_instruments": ["UN Charter Article 2(4)", "UN Charter Article 51", "ICJ Nicaragua Judgment (1986)"],
            "severity": "critical",
            "legal_domain": "use_of_force",
        },
    ),
    # ── Military escalation + border clash → armed engagement ─────
    (
        frozenset({"SIG_MIL_ESCALATION", "SIG_BORDER_CLASH"}),
        {
            "behavior": "Armed military engagement at an international boundary, with broader mobilization indicating escalation beyond an isolated incident",
            "legal_test": "Does the armed engagement constitute an 'armed attack' within the meaning of Article 51, triggering the inherent right of self-defense? Does the broader military mobilization exceed proportional self-defense?",
            "relevant_instruments": ["UN Charter Article 51", "UN Charter Article 2(4)", "ICJ Oil Platforms (2003)", "Geneva Conventions Common Article 2"],
            "severity": "critical",
            "legal_domain": "use_of_force",
        },
    ),
    # ── Military escalation + blockade → naval warfare ────────────
    (
        frozenset({"SIG_MIL_ESCALATION", "SIG_BLOCKADE"}),
        {
            "behavior": "Military escalation accompanied by naval blockade of maritime access points, preventing commercial and military vessel transit",
            "legal_test": "Is the naval blockade an act of war? Does it violate UNCLOS freedom of navigation (Article 87) and innocent passage (Article 17)? Does it constitute use of force under Article 2(4)?",
            "relevant_instruments": ["UNCLOS Articles 17, 38, 87", "UN Charter Article 2(4)", "San Remo Manual on Naval Warfare"],
            "severity": "critical",
            "legal_domain": "maritime_law",
        },
    ),
    # ── Force posture + chokepoint → maritime coercion ────────────
    (
        frozenset({"SIG_FORCE_POSTURE", "SIG_CHOKEPOINT_CONTROL"}),
        {
            "behavior": "Military naval forces deployed to control or restrict access through an international strait or strategic waterway",
            "legal_test": "Does the naval deployment violate transit passage rights under UNCLOS Part III (Articles 34-44)? Does restricting passage through an international strait constitute a 'threat of force'?",
            "relevant_instruments": ["UNCLOS Part III (Transit Passage)", "UNCLOS Article 38", "UNCLOS Article 44", "UN Charter Article 2(4)"],
            "severity": "high",
            "legal_domain": "maritime_law",
        },
    ),
    # ── Sanctions + economic pressure → economic coercion ─────────
    (
        frozenset({"SIG_SANCTIONS_ACTIVE", "SIG_ECONOMIC_PRESSURE"}),
        {
            "behavior": "Imposition of comprehensive economic sanctions designed to inflict severe economic harm on a target state to coerce policy change",
            "legal_test": "Are the sanctions authorized by UN Security Council resolution, or are they unilateral? Do unilateral sanctions constitute prohibited economic coercion violating state sovereignty under the UN Charter and the Declaration on Friendly Relations?",
            "relevant_instruments": ["UN Charter Article 41", "UNGA Res. 2625 (Declaration on Friendly Relations)", "WTO GATT Article XXI (Security Exceptions)"],
            "severity": "high",
            "legal_domain": "sanctions_law",
        },
    ),
    # ── Cyber + military escalation → hybrid warfare ──────────────
    (
        frozenset({"SIG_CYBER_ACTIVITY", "SIG_MIL_ESCALATION"}),
        {
            "behavior": "Coordinated cyber operations against critical infrastructure alongside military mobilization, indicating preparation for hybrid warfare campaign",
            "legal_test": "Do state-directed cyber operations targeting critical infrastructure constitute a 'use of force' under Article 2(4)? Does coordination with military mobilization establish the threshold for 'armed attack' under Article 51?",
            "relevant_instruments": ["UN Charter Article 2(4)", "UN Charter Article 51", "Tallinn Manual 2.0 Rules 69-71", "ILC Articles on State Responsibility"],
            "severity": "critical",
            "legal_domain": "cyber_law",
        },
    ),
    # ── WMD risk + military escalation → WMD deployment threat ────
    (
        frozenset({"SIG_WMD_RISK", "SIG_MIL_ESCALATION"}),
        {
            "behavior": "Military mobilization combined with indicators of weapons of mass destruction readiness or deployment preparation",
            "legal_test": "Does WMD readiness alongside military mobilization violate the Nuclear Non-Proliferation Treaty, Chemical Weapons Convention, or Biological Weapons Convention? Does it constitute a threat of force with WMD under ICJ Advisory Opinion on Nuclear Weapons (1996)?",
            "relevant_instruments": ["NPT Articles I-III", "CWC Articles I, VI", "BWC Articles I, III", "ICJ Nuclear Weapons Advisory Opinion (1996)"],
            "severity": "critical",
            "legal_domain": "nuclear_law",
        },
    ),
    # ── Treaty break + diplomatic break → total rupture ───────────
    (
        frozenset({"SIG_TREATY_BREAK", "SIG_DIP_BREAK"}),
        {
            "behavior": "Unilateral withdrawal from or non-compliance with treaty obligations accompanied by severance of diplomatic relations",
            "legal_test": "Does the treaty breach constitute a 'material breach' under Article 60 of the Vienna Convention on the Law of Treaties, entitling the other party to suspend or terminate? Does severance of diplomatic relations violate the Vienna Convention on Diplomatic Relations?",
            "relevant_instruments": ["VCLT Articles 60, 65-68", "Vienna Convention on Diplomatic Relations Article 2", "UN Charter Article 2(3)"],
            "severity": "high",
            "legal_domain": "treaty_obligations",
        },
    ),
    # ── Alliance activation + military escalation → collective defense
    (
        frozenset({"SIG_ALLIANCE_ACTIVATION", "SIG_MIL_ESCALATION"}),
        {
            "behavior": "Invocation of collective defense obligations under a mutual defense treaty, with military mobilization by alliance members",
            "legal_test": "Has the threshold for collective self-defense under Article 51 been met? Must the attacked state request assistance? Are the collective defense measures proportionate and necessary?",
            "relevant_instruments": ["UN Charter Article 51", "ICJ Nicaragua Judgment (1986)", "NATO Treaty Article 5 / applicable regional defense treaty"],
            "severity": "critical",
            "legal_domain": "collective_defense",
        },
    ),
    # ── Territorial incursion + force concentration → invasion prep
    (
        frozenset({"SIG_TERRITORIAL_INCURSION", "SIG_FORCE_CONCENTRATION"}),
        {
            "behavior": "Incursion into another state's territory accompanied by massing of military forces, indicating preparation for sustained territorial seizure",
            "legal_test": "Does the territorial incursion violate the prohibition on the use of force (Art 2(4))? Does force concentration constitute aggression as defined by UNGA Resolution 3314?",
            "relevant_instruments": ["UN Charter Article 2(4)", "UNGA Res. 3314 (Definition of Aggression)", "Rome Statute Article 8bis (Crime of Aggression)"],
            "severity": "critical",
            "legal_domain": "use_of_force",
        },
    ),
    # ── Negotiation breakdown + coercive bargaining → coercion ────
    (
        frozenset({"SIG_NEGOTIATION_BREAKDOWN", "SIG_COERCIVE_BARGAINING"}),
        {
            "behavior": "State issuing ultimatums or coercive demands while refusing to engage in good faith dispute resolution",
            "legal_test": "Does refusal to negotiate combined with coercive demands violate the obligation to settle disputes peacefully (Article 2(3) UN Charter)? Does the coercion constitute a prohibited 'threat of force'?",
            "relevant_instruments": ["UN Charter Article 2(3)", "UN Charter Article 2(4)", "UN Charter Article 33", "UNGA Res. 2625"],
            "severity": "high",
            "legal_domain": "treaty_obligations",
        },
    ),
    # ── Logistics surge + force posture → pre-conflict deployment ─
    (
        frozenset({"SIG_LOGISTICS_SURGE", "SIG_FORCE_POSTURE"}),
        {
            "behavior": "Large-scale military logistics movement (fuel, ammunition, medical supplies) combined with forward force positioning, indicating imminent military operations",
            "legal_test": "Does the logistical surge combined with forward positioning constitute preparation for aggression? Under the Definition of Aggression (Res. 3314), is mobilization itself an act of aggression?",
            "relevant_instruments": ["UNGA Res. 3314 Article 3", "UN Charter Article 2(4)", "Rome Statute Article 8bis"],
            "severity": "high",
            "legal_domain": "use_of_force",
        },
    ),
]

# Sort combos by size (descending) so larger matches are tried first
_COMBO_RULES.sort(key=lambda x: len(x[0]), reverse=True)


# ═══════════════════════════════════════════════════════════════════════
# INDIVIDUAL SIGNAL RULES — fallback when no combo matches
# ═══════════════════════════════════════════════════════════════════════

_INDIVIDUAL_RULES: Dict[str, Dict[str, Any]] = {
    # ── Military / Sovereignty ────────────────────────────────────
    "SIG_MIL_ESCALATION": {
        "behavior": "Mobilization or escalation of military forces indicating preparation for or conduct of armed conflict",
        "legal_test": "Does the military mobilization constitute a 'threat of force' or 'use of force' prohibited by Article 2(4) of the UN Charter?",
        "relevant_instruments": ["UN Charter Article 2(4)", "UN Charter Article 51"],
        "severity": "high",
        "legal_domain": "use_of_force",
    },
    "SIG_FORCE_POSTURE": {
        "behavior": "Repositioning of military units into a forward or offensive posture near a border or strategic area",
        "legal_test": "Does aggressive force posturing near a border constitute an implicit 'threat of force' under Article 2(4)?",
        "relevant_instruments": ["UN Charter Article 2(4)", "ICJ Corfu Channel Case (1949)"],
        "severity": "medium",
        "legal_domain": "use_of_force",
    },
    "SIG_BORDER_CLASH": {
        "behavior": "Armed engagement between military or paramilitary forces at an international border",
        "legal_test": "Does the border clash constitute an 'armed attack' triggering the right of self-defense under Article 51? Do the Geneva Conventions apply to the engagement?",
        "relevant_instruments": ["UN Charter Article 51", "Geneva Conventions Common Article 2", "Hague Regulations"],
        "severity": "high",
        "legal_domain": "use_of_force",
    },
    "SIG_TERRITORIAL_INCURSION": {
        "behavior": "Military forces entered another state's sovereign territory without authorization or consent",
        "legal_test": "Does the incursion violate the prohibition on the use of force (Article 2(4)) and the principle of territorial integrity? Does it constitute 'aggression' under UNGA Res. 3314?",
        "relevant_instruments": ["UN Charter Article 2(4)", "UNGA Res. 3314 (Definition of Aggression)", "ICJ Nicaragua (1986)"],
        "severity": "critical",
        "legal_domain": "use_of_force",
    },
    "SIG_FORCE_CONCENTRATION": {
        "behavior": "Massing of military forces in a concentrated area near a border or strategic chokepoint",
        "legal_test": "Does force concentration near a border constitute a 'threat of force' under Article 2(4)? Under the Definition of Aggression, is mobilization itself an act?",
        "relevant_instruments": ["UN Charter Article 2(4)", "UNGA Res. 3314 Article 3"],
        "severity": "medium",
        "legal_domain": "use_of_force",
    },
    "SIG_SOVEREIGNTY_BREACH": {
        "behavior": "Actions by a foreign state that violate the sovereign rights and territorial integrity of another state",
        "legal_test": "Does this conduct violate the principle of sovereign equality and territorial integrity under the UN Charter?",
        "relevant_instruments": ["UN Charter Article 2(1)", "UN Charter Article 2(4)", "UNGA Res. 2625"],
        "severity": "high",
        "legal_domain": "use_of_force",
    },

    # ── Maritime / Naval ──────────────────────────────────────────
    "SIG_CHOKEPOINT_CONTROL": {
        "behavior": "Naval deployment to control or restrict access to an international strait or major waterway",
        "legal_test": "Does controlling a chokepoint violate transit passage rights under UNCLOS Part III? Does it restrict innocent passage (UNCLOS Part II, Section 3)?",
        "relevant_instruments": ["UNCLOS Articles 17-19 (Innocent Passage)", "UNCLOS Articles 34-44 (Transit Passage)", "UNCLOS Article 87"],
        "severity": "high",
        "legal_domain": "maritime_law",
    },
    "SIG_BLOCKADE": {
        "behavior": "Naval blockade preventing commercial and military vessel access to a port, coastline, or maritime zone",
        "legal_test": "Is the blockade an act of war? Does it violate UNCLOS freedom of navigation (Art 87) and the right of innocent passage? Is it lawful under the laws of naval warfare (San Remo Manual)?",
        "relevant_instruments": ["UNCLOS Article 87", "UNCLOS Article 17", "San Remo Manual on Naval Warfare", "UN Charter Article 2(4)"],
        "severity": "critical",
        "legal_domain": "maritime_law",
    },
    "SIG_MARITIME_VIOLATION": {
        "behavior": "Violation of established maritime zones, exclusive economic zones, or navigational rights under international maritime law",
        "legal_test": "Does the conduct violate UNCLOS provisions on territorial sea (Part II), EEZ (Part V), or continental shelf (Part VI)?",
        "relevant_instruments": ["UNCLOS Parts II, V, VI", "UNCLOS Article 56", "UNCLOS Article 58"],
        "severity": "medium",
        "legal_domain": "maritime_law",
    },
    "SIG_LOGISTICS_SURGE": {
        "behavior": "Large-scale military logistics movement (equipment, ammunition, medical supplies) indicating preparation for sustained operations",
        "legal_test": "Does the logistics surge indicate preparation for aggression? Under customary international law, is pre-conflict mobilization a prohibited act?",
        "relevant_instruments": ["UNGA Res. 3314 Article 3", "UN Charter Article 2(4)"],
        "severity": "medium",
        "legal_domain": "use_of_force",
    },
    "SIG_LOGISTICS_PREP": {
        "behavior": "Pre-positioning of military supply chains and logistics infrastructure for extended deployment",
        "legal_test": "Does logistical preparation constitute evidence of intent to use force inconsistent with Article 2(4)?",
        "relevant_instruments": ["UN Charter Article 2(4)", "UNGA Res. 3314"],
        "severity": "low",
        "legal_domain": "use_of_force",
    },

    # ── Economic / Sanctions ──────────────────────────────────────
    "SIG_SANCTIONS_ACTIVE": {
        "behavior": "State-imposed trade restrictions, financial sanctions, or asset freezes targeting another state, its entities, or its nationals",
        "legal_test": "Are the sanctions authorized by a UN Security Council resolution (Chapter VII), or are they unilateral? Do unilateral sanctions violate WTO rules or constitute prohibited economic coercion?",
        "relevant_instruments": ["UN Charter Chapter VII (Articles 39-42)", "WTO GATT Article XXI", "UNGA Res. 2625"],
        "severity": "medium",
        "legal_domain": "sanctions_law",
    },
    "SIG_ECO_SANCTIONS_ACTIVE": {
        "behavior": "Enforcement of economic sanctions with active measures such as asset seizures, trade embargoes, or financial system exclusion",
        "legal_test": "Are enforcement measures proportionate? Do they violate bilateral investment treaties or WTO obligations?",
        "relevant_instruments": ["UN Charter Article 41", "WTO GATT Article XXI", "Applicable BITs"],
        "severity": "medium",
        "legal_domain": "sanctions_law",
    },
    "SIG_ECONOMIC_PRESSURE": {
        "behavior": "Non-military coercive economic measures (currency manipulation, trade barriers, supply chain disruption) intended to compel a target state to change policy",
        "legal_test": "Does economic pressure constitute prohibited 'economic coercion' violating state sovereignty and the principle of non-intervention?",
        "relevant_instruments": ["UNGA Res. 2625 (Non-Intervention Principle)", "UN Charter Article 2(7)", "WTO Most Favoured Nation rules"],
        "severity": "medium",
        "legal_domain": "sanctions_law",
    },

    # ── Diplomatic / Treaty ───────────────────────────────────────
    "SIG_NEGOTIATION_BREAKDOWN": {
        "behavior": "State refusing to engage in or abandoning diplomatic negotiations for peaceful dispute resolution",
        "legal_test": "Does the refusal to negotiate violate the obligation to settle disputes by peaceful means (Article 2(3) UN Charter)? Is there a duty to negotiate under applicable treaties?",
        "relevant_instruments": ["UN Charter Article 2(3)", "UN Charter Article 33", "VCLT Article 65"],
        "severity": "medium",
        "legal_domain": "treaty_obligations",
    },
    "SIG_DIP_BREAK": {
        "behavior": "Severance or significant downgrading of diplomatic relations between states",
        "legal_test": "What are the legal consequences of severing diplomatic relations under the Vienna Convention on Diplomatic Relations? Does this affect treaty obligations between the states?",
        "relevant_instruments": ["Vienna Convention on Diplomatic Relations Articles 2, 45", "VCLT Article 63"],
        "severity": "medium",
        "legal_domain": "treaty_obligations",
    },
    "SIG_TREATY_BREAK": {
        "behavior": "Non-compliance with or withdrawal from existing bilateral or multilateral treaty obligations",
        "legal_test": "Does the breach constitute a 'material breach' under Article 60 VCLT, entitling the other party to suspend or terminate? Were proper withdrawal procedures followed (Article 56)?",
        "relevant_instruments": ["VCLT Article 60 (Material Breach)", "VCLT Articles 56, 65-68", "Pacta Sunt Servanda (VCLT Article 26)"],
        "severity": "high",
        "legal_domain": "treaty_obligations",
    },
    "SIG_DIP_CHANNEL_CLOSURE": {
        "behavior": "Closure of diplomatic communication channels, embassies, or consular offices",
        "legal_test": "Does channel closure violate obligations under the Vienna Convention on Consular Relations? Does it impede peaceful dispute settlement?",
        "relevant_instruments": ["Vienna Convention on Consular Relations", "UN Charter Article 33"],
        "severity": "medium",
        "legal_domain": "treaty_obligations",
    },
    "SIG_DIP_HOSTILITY": {
        "behavior": "Hostile diplomatic actions including persona non grata declarations, expulsion of diplomats, or hostile rhetoric at international fora",
        "legal_test": "Are the diplomatic actions consistent with the Vienna Convention on Diplomatic Relations (Article 9 on persona non grata)? Do they cross the line into coercion?",
        "relevant_instruments": ["Vienna Convention on Diplomatic Relations Article 9", "UN Charter Article 2(4)"],
        "severity": "medium",
        "legal_domain": "treaty_obligations",
    },

    # ── WMD / Nuclear ─────────────────────────────────────────────
    "SIG_WMD_RISK": {
        "behavior": "Activities consistent with development, testing, or deployment of weapons of mass destruction (nuclear, chemical, or biological)",
        "legal_test": "Do the observed activities violate NPT, CWC, or BWC obligations? Has the state withdrawn from any of these regimes? Does the ICJ Advisory Opinion on Nuclear Weapons apply?",
        "relevant_instruments": ["NPT Articles I-III", "CWC Articles I, VI", "BWC Articles I, III", "ICJ Nuclear Weapons Advisory Opinion (1996)"],
        "severity": "critical",
        "legal_domain": "nuclear_law",
    },
    "SIG_NUCLEAR_ACTIVITY": {
        "behavior": "Nuclear-related activities including enrichment, testing, warhead assembly, or delivery system development",
        "legal_test": "Does this activity violate NPT safeguards obligations or IAEA safeguards agreements? Is it consistent with peaceful use (NPT Article IV)?",
        "relevant_instruments": ["NPT Articles I-IV", "IAEA Statute Article III", "UNSC Resolutions on nuclear programs"],
        "severity": "critical",
        "legal_domain": "nuclear_law",
    },

    # ── Cyber ─────────────────────────────────────────────────────
    "SIG_CYBER_ACTIVITY": {
        "behavior": "State-directed or state-sponsored cyber operations targeting another state's critical infrastructure, government systems, or information networks",
        "legal_test": "Do the cyber operations violate the sovereignty of the target state? Do they constitute a 'use of force' under Article 2(4) if they cause physical damage or injury? What is the standard under the Tallinn Manual?",
        "relevant_instruments": ["UN Charter Article 2(4)", "Tallinn Manual 2.0 Rules 1-7, 69-71", "ILC Articles on State Responsibility"],
        "severity": "high",
        "legal_domain": "cyber_law",
    },
    "SIG_CYBER_PREPARATION": {
        "behavior": "Development of offensive cyber capabilities or positioning of cyber tools for potential deployment against another state",
        "legal_test": "Does preparation of offensive cyber capabilities violate the principle of non-intervention? At what point does cyber preparation become a 'threat of force'?",
        "relevant_instruments": ["Tallinn Manual 2.0 Rules 1-7", "UN Charter Article 2(4)", "UNGA Res. 2625"],
        "severity": "medium",
        "legal_domain": "cyber_law",
    },

    # ── Alliance ──────────────────────────────────────────────────
    "SIG_ALLIANCE_ACTIVATION": {
        "behavior": "Formal invocation of collective defense clause in a mutual defense treaty by an alliance member",
        "legal_test": "Has the threshold for collective self-defense under Article 51 been met? Was there an 'armed attack'? Did the attacked state request assistance?",
        "relevant_instruments": ["UN Charter Article 51", "ICJ Nicaragua (1986)", "Applicable mutual defense treaty"],
        "severity": "critical",
        "legal_domain": "collective_defense",
    },
    "SIG_ALLIANCE_SHIFT": {
        "behavior": "Realignment of alliance structures, new defense partnerships, or withdrawal from existing collective defense arrangements",
        "legal_test": "What are the treaty obligations regarding withdrawal from mutual defense agreements? Does realignment affect existing collective defense commitments?",
        "relevant_instruments": ["VCLT Articles 54-56 (Treaty Termination)", "Applicable alliance treaties"],
        "severity": "medium",
        "legal_domain": "collective_defense",
    },

    # ── Coercive Diplomacy ────────────────────────────────────────
    "SIG_COERCIVE_BARGAINING": {
        "behavior": "State issuing ultimatums, threats, or coercive demands accompanied by credible capability to execute the threat",
        "legal_test": "Does the coercive bargaining constitute a 'threat of force' prohibited by Article 2(4)? Does it violate the obligation to settle disputes peacefully?",
        "relevant_instruments": ["UN Charter Article 2(4)", "UN Charter Article 2(3)", "ICJ Nuclear Weapons Advisory Opinion (1996)"],
        "severity": "high",
        "legal_domain": "coercive_diplomacy",
    },
    "SIG_RETALIATORY_THREAT": {
        "behavior": "Explicit or implicit threat of retaliation (military, economic, or diplomatic) in response to another state's actions",
        "legal_test": "Does the retaliatory threat constitute an unlawful 'threat of force'? Is it a lawful countermeasure under the ILC Articles on State Responsibility?",
        "relevant_instruments": ["UN Charter Article 2(4)", "ILC Articles on State Responsibility (Part III, Ch. II)", "UNGA Res. 2625"],
        "severity": "high",
        "legal_domain": "coercive_diplomacy",
    },
    "SIG_DETERRENCE_SIGNALING": {
        "behavior": "Deliberate signaling of military capability or willingness to escalate as a deterrence measure",
        "legal_test": "Does deterrence signaling cross the threshold of 'threat of force' under Article 2(4)? Is it distinguishable from lawful defensive posturing?",
        "relevant_instruments": ["UN Charter Article 2(4)", "UN Charter Article 51", "ICJ Nuclear Weapons Advisory Opinion (1996)"],
        "severity": "medium",
        "legal_domain": "coercive_diplomacy",
    },

    # ── Internal / Human Rights ───────────────────────────────────
    "SIG_INTERNAL_INSTABILITY": {
        "behavior": "Severe internal disorder, mass protests, or government breakdown that may endanger civilian lives or trigger international response",
        "legal_test": "Does the internal situation trigger Responsibility to Protect (R2P) obligations? Do human rights treaty obligations (ICCPR, ICESCR) apply?",
        "relevant_instruments": ["ICCPR Articles 6-7", "ICESCR", "R2P Doctrine (2005 World Summit)", "Geneva Conventions Common Article 3"],
        "severity": "medium",
        "legal_domain": "human_rights",
    },
    "SIG_MILITARY_DEFECTION": {
        "behavior": "Large-scale military defections indicating internal fragmentation of state armed forces",
        "legal_test": "Does mass defection trigger non-international armed conflict provisions (Geneva Conventions Common Article 3)? Are there obligations regarding treatment of defectors?",
        "relevant_instruments": ["Geneva Conventions Common Article 3", "Additional Protocol II", "ICCPR Article 6"],
        "severity": "medium",
        "legal_domain": "human_rights",
    },

    # ── Illegal coercion (catch-all) ──────────────────────────────
    "SIG_ILLEGAL_COERCION": {
        "behavior": "State conduct that constitutes coercion through force, economic pressure, or political subversion to compel another state's compliance",
        "legal_test": "Does the conduct violate the prohibition on the use of force (Article 2(4)), the principle of non-intervention, or constitute unlawful countermeasures?",
        "relevant_instruments": ["UN Charter Article 2(4)", "UNGA Res. 2625", "ILC Articles on State Responsibility"],
        "severity": "high",
        "legal_domain": "use_of_force",
    },
}


# ═══════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════

def interpret_signals(
    observed_signals: Set[str],
    *,
    subject_country: str = "",
    target_country: str = "",
    escalation_score: float = 0.0,
) -> List[InferredBehavior]:
    """
    Translate observed signals into concrete inferred behaviors.

    Parameters
    ----------
    observed_signals : set[str]
        All observed signal codes from the pipeline.
    subject_country : str, optional
        ISO code of the acting state.
    target_country : str, optional
        ISO code of the target state.
    escalation_score : float, optional
        Overall escalation score (0-1) — used to calibrate severity.

    Returns
    -------
    list[InferredBehavior]
        Concrete behavior descriptions ready for LLM injection.
    """
    if not observed_signals:
        return []

    normalized = {sig.strip().upper() for sig in observed_signals if sig.strip()}
    behaviors: List[InferredBehavior] = []
    consumed: Set[str] = set()  # signals already explained by a combo rule

    # ── Pass 1: Combo rules (most specific first) ─────────────────
    for combo_signals, template in _COMBO_RULES:
        if combo_signals.issubset(normalized) and not combo_signals.issubset(consumed):
            behavior_text = template["behavior"]

            # Substitute country names if available
            if subject_country:
                behavior_text = behavior_text.replace("a state", f"{subject_country}", 1)
                behavior_text = behavior_text.replace("a foreign state", f"{subject_country}", 1)
            if target_country:
                behavior_text = behavior_text.replace("another state's", f"{target_country}'s")
                behavior_text = behavior_text.replace("another state", target_country)
                behavior_text = behavior_text.replace("a target state", target_country)

            # Escalation score can upgrade severity
            severity = template["severity"]
            if escalation_score >= 0.85 and severity in ("medium", "high"):
                severity = "critical" if severity == "high" else "high"

            behaviors.append(InferredBehavior(
                behavior=behavior_text,
                legal_test=template["legal_test"],
                relevant_instruments=list(template["relevant_instruments"]),
                severity=severity,
                triggering_signals=sorted(combo_signals),
                legal_domain=template["legal_domain"],
            ))
            consumed |= combo_signals

    # ── Pass 2: Individual rules for remaining signals ────────────
    for sig in sorted(normalized - consumed):
        template = _INDIVIDUAL_RULES.get(sig)
        if not template:
            continue

        behavior_text = template["behavior"]

        # Substitute country names if available
        if subject_country:
            behavior_text = behavior_text.replace("a state", f"{subject_country}", 1)
            behavior_text = behavior_text.replace("State", f"{subject_country}", 1)
        if target_country:
            behavior_text = behavior_text.replace("another state's", f"{target_country}'s")
            behavior_text = behavior_text.replace("another state", target_country)
            behavior_text = behavior_text.replace("a target state", target_country)

        severity = template["severity"]
        if escalation_score >= 0.85 and severity in ("medium", "high"):
            severity = "critical" if severity == "high" else "high"

        behaviors.append(InferredBehavior(
            behavior=behavior_text,
            legal_test=template["legal_test"],
            relevant_instruments=list(template["relevant_instruments"]),
            severity=severity,
            triggering_signals=[sig],
            legal_domain=template["legal_domain"],
        ))

    logger.info(
        "[INTERPRETER] %d signal(s) → %d inferred behavior(s) "
        "(combos=%d, individual=%d)",
        len(normalized),
        len(behaviors),
        len([b for b in behaviors if len(b.triggering_signals) > 1]),
        len([b for b in behaviors if len(b.triggering_signals) == 1]),
    )

    return behaviors


def behaviors_to_prompt_block(behaviors: List[InferredBehavior]) -> str:
    """
    Format all inferred behaviors as a text block for LLM injection.

    This goes into the user prompt BEFORE the evidence block,
    so the legal reasoner knows WHAT concrete acts to evaluate.
    """
    if not behaviors:
        return "No specific state behaviors inferred from the observed signals."

    lines = []
    for i, beh in enumerate(behaviors, 1):
        lines.append(f"--- Inferred Behavior {i} ---")
        lines.append(beh.to_prompt_text())
        lines.append("")

    return "\n".join(lines)


def behaviors_to_rag_queries(behaviors: List[InferredBehavior]) -> List[str]:
    """
    Generate additional RAG queries from inferred behaviors.

    These are behavior-description-based queries that may retrieve
    more relevant treaty text than the abstract signal-based queries
    in rag_bridge.SIGNAL_QUERY_MAP.
    """
    queries = []
    for beh in behaviors:
        # Use the legal test as a RAG query — it's phrased in treaty language
        if beh.legal_test:
            queries.append(beh.legal_test[:300])
        # Also use the relevant instrument names
        for inst in beh.relevant_instruments[:2]:
            queries.append(inst)
    return queries
