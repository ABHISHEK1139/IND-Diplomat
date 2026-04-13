"""
Signal Ontology — Expanded canonical signal registry (80+ signals).

This is an ADDITIVE layer on top of the existing registries at:
  - Layer3_StateModel/signal_registry.py
  - Layer4_Analysis/evidence/signal_ontology.py
  - layer4_reasoning/signal_ontology.py

It does NOT replace them; it extends with richer metadata so that
ministers, the red team, and the backtester can reason over a
wider vocabulary.

Each entry carries:
    dimension   — grouping axis (military, diplomatic, economic,
                  domestic, wmd, cyber, maritime, energy, information)
    weight      — default belief weight [0.0-1.0]
    description — human-readable label
    escalation  — which escalation profile the signal maps to
                  (offensive, defensive, diplomatic, stabilising,
                   destabilising, neutral)

Usage::

    from Core.signals.ontology import SIGNAL_ONTOLOGY, get_signal_metadata

    meta = get_signal_metadata("SIG_MIL_MOBILIZATION")
    print(meta["dimension"], meta["weight"])
"""

from __future__ import annotations

from typing import Any, Dict, Optional


# ── Type alias ────────────────────────────────────────────────────
SignalMeta = Dict[str, Any]   # {dimension, weight, description, escalation}


def _s(dimension: str, weight: float, description: str,
       escalation: str = "neutral") -> SignalMeta:
    """Shorthand constructor for a signal metadata entry."""
    return {
        "dimension":  dimension,
        "weight":     round(weight, 3),
        "description": description,
        "escalation": escalation,
    }


# ── SIGNAL_ONTOLOGY ──────────────────────────────────────────────
# 85 canonical signals grouped by dimension.

SIGNAL_ONTOLOGY: Dict[str, SignalMeta] = {

    # ══════════════════════════════════════════════════════════════
    # MILITARY  (16 signals)
    # ══════════════════════════════════════════════════════════════
    "SIG_MIL_MOBILIZATION":    _s("military", 0.90,
        "Large-scale troop mobilization or reserve call-up",
        "offensive"),
    "SIG_FORCE_POSTURE":       _s("military", 0.80,
        "Forward deployment or force concentration near border",
        "offensive"),
    "SIG_MIL_ESCALATION":      _s("military", 0.85,
        "Kinetic engagement — border clashes, strikes, skirmishes",
        "offensive"),
    "SIG_LOGISTICS_PREP":      _s("military", 0.70,
        "Logistics surge — fuel/ammo pre-positioning",
        "offensive"),
    "SIG_NAVAL_DEPLOYMENT":    _s("military", 0.75,
        "Major naval task-force deployment or carrier transit",
        "offensive"),
    "SIG_AIR_DEFENSE_ACTIVATION": _s("military", 0.65,
        "Air-defence system activation or IADS alert",
        "defensive"),
    "SIG_MISSILE_TESTING":     _s("military", 0.80,
        "Ballistic or cruise-missile test launch",
        "offensive"),
    "SIG_AIRBASE_READINESS":   _s("military", 0.60,
        "Combat-aircraft generation or sortie-rate surge",
        "offensive"),
    "SIG_FORTIFICATION":       _s("military", 0.50,
        "Defensive fortification or entrenchment activity",
        "defensive"),
    "SIG_MIL_WITHDRAWAL":      _s("military", 0.40,
        "Force withdrawal or repositioning to rear areas",
        "stabilising"),
    "SIG_CEASEFIRE_VIOLATION":  _s("military", 0.75,
        "Ceasefire or armistice violation",
        "offensive"),
    "SIG_ARMS_TRANSFER":       _s("military", 0.65,
        "Significant arms transfer or military-aid package",
        "offensive"),
    "SIG_SPECIAL_OPS":         _s("military", 0.70,
        "Special-operations activity or covert military action",
        "offensive"),
    "SIG_DRONE_ACTIVITY":      _s("military", 0.60,
        "Increased ISR or strike-drone operations",
        "offensive"),
    "SIG_MILITARY_EXERCISE":   _s("military", 0.55,
        "Scheduled or snap military exercise near adversary",
        "offensive"),
    "SIG_CONSCRIPTION":        _s("military", 0.70,
        "Emergency conscription or draft announcement",
        "offensive"),

    # ══════════════════════════════════════════════════════════════
    # DIPLOMATIC  (12 signals)
    # ══════════════════════════════════════════════════════════════
    "SIG_DIP_HOSTILITY":       _s("diplomatic", 0.65,
        "Hostile diplomatic rhetoric or threat posturing",
        "destabilising"),
    "SIG_DIPLOMACY_ACTIVE":    _s("diplomatic", 0.40,
        "Active diplomatic engagement or back-channel talks",
        "stabilising"),
    "SIG_EMBASSY_RECALL":      _s("diplomatic", 0.70,
        "Ambassador recall or embassy drawdown/closure",
        "destabilising"),
    "SIG_NEGOTIATION_BREAKDOWN": _s("diplomatic", 0.75,
        "Collapse of ongoing negotiations or peace process",
        "destabilising"),
    "SIG_SANCTIONS_ANNOUNCEMENT": _s("diplomatic", 0.65,
        "New sanctions package announced or proposed",
        "destabilising"),
    "SIG_TREATY_INVOCATION":   _s("diplomatic", 0.60,
        "Invocation of mutual-defence treaty or Article 5 equivalent",
        "offensive"),
    "SIG_ALLIANCE_ACTIVATION": _s("diplomatic", 0.70,
        "Alliance activation or joint-defence coordination",
        "offensive"),
    "SIG_COERCIVE_BARGAINING": _s("diplomatic", 0.60,
        "Coercive-diplomacy signalling — ultimatums, red lines",
        "destabilising"),
    "SIG_PEACE_PROPOSAL":      _s("diplomatic", 0.35,
        "Formal peace proposal or ceasefire offer",
        "stabilising"),
    "SIG_UN_RESOLUTION":       _s("diplomatic", 0.45,
        "UN Security Council resolution or General Assembly vote",
        "neutral"),
    "SIG_MEDIATION_EFFORT":    _s("diplomatic", 0.35,
        "Third-party mediation attempt (UN, regional body)",
        "stabilising"),
    "SIG_EXPULSION":           _s("diplomatic", 0.65,
        "Expulsion of diplomats or international observers",
        "destabilising"),

    # ══════════════════════════════════════════════════════════════
    # ECONOMIC  (10 signals)
    # ══════════════════════════════════════════════════════════════
    "SIG_ECONOMIC_PRESSURE":   _s("economic", 0.65,
        "Broad economic coercion — sanctions, embargo, supply cut",
        "destabilising"),
    "SIG_CURRENCY_CRISIS":     _s("economic", 0.55,
        "Rapid currency depreciation or capital-flight event",
        "destabilising"),
    "SIG_ENERGY_DISRUPTION":   _s("economic", 0.70,
        "Energy supply disruption — pipeline shutdown, embargo",
        "destabilising"),
    "SIG_TRADE_RESTRICTION":   _s("economic", 0.55,
        "Export controls, trade bans, tariff escalation",
        "destabilising"),
    "SIG_DEBT_DEFAULT":        _s("economic", 0.60,
        "Sovereign debt default or restructuring",
        "destabilising"),
    "SIG_AID_SUSPENSION":      _s("economic", 0.50,
        "Foreign-aid suspension or humanitarian blockade",
        "destabilising"),
    "SIG_ASSET_FREEZE":        _s("economic", 0.55,
        "Asset freeze or financial-sector sanctions",
        "destabilising"),
    "SIG_FOOD_INSECURITY":     _s("economic", 0.50,
        "Food-price spike or supply-chain disruption",
        "destabilising"),
    "SIG_RESOURCE_COMPETITION": _s("economic", 0.50,
        "Competition for critical resources — water, minerals, rare earth",
        "destabilising"),
    "SIG_ECONOMIC_RECOVERY":   _s("economic", 0.30,
        "Economic stabilisation or recovery indicator",
        "stabilising"),

    # ══════════════════════════════════════════════════════════════
    # DOMESTIC / INTERNAL  (10 signals)
    # ══════════════════════════════════════════════════════════════
    "SIG_INTERNAL_INSTABILITY": _s("domestic", 0.65,
        "Broad internal instability — unrest, institutional decay",
        "destabilising"),
    "SIG_PUBLIC_PROTEST":       _s("domestic", 0.55,
        "Mass public protest or civil disobedience",
        "destabilising"),
    "SIG_COUP_ATTEMPT":         _s("domestic", 0.85,
        "Military coup attempt or unconstitutional power seizure",
        "destabilising"),
    "SIG_ELECTION_CRISIS":      _s("domestic", 0.60,
        "Disputed election results or electoral violence",
        "destabilising"),
    "SIG_MARTIAL_LAW":          _s("domestic", 0.75,
        "Declaration of martial law or state of emergency",
        "destabilising"),
    "SIG_MEDIA_BLACKOUT":       _s("domestic", 0.55,
        "Internet shutdown or media censorship escalation",
        "destabilising"),
    "SIG_ETHNIC_TENSION":       _s("domestic", 0.60,
        "Ethnic or sectarian violence escalation",
        "destabilising"),
    "SIG_REFUGEE_FLOW":         _s("domestic", 0.50,
        "Large-scale refugee or IDP movement",
        "destabilising"),
    "SIG_LEADERSHIP_CHANGE":    _s("domestic", 0.50,
        "Major leadership transition — planned or abrupt",
        "neutral"),
    "SIG_DOMESTIC_STABILITY":   _s("domestic", 0.25,
        "Indicators of domestic calm and institutional function",
        "stabilising"),

    # ══════════════════════════════════════════════════════════════
    # WMD / NUCLEAR  (7 signals)
    # ══════════════════════════════════════════════════════════════
    "SIG_NUCLEAR_POSTURE":      _s("wmd", 0.95,
        "Nuclear-force readiness change or strategic-alert elevation",
        "offensive"),
    "SIG_NUCLEAR_TEST":         _s("wmd", 0.95,
        "Nuclear weapon test or seismic-detected detonation",
        "offensive"),
    "SIG_ENRICHMENT_ACTIVITY":  _s("wmd", 0.80,
        "Uranium enrichment acceleration or centrifuge expansion",
        "offensive"),
    "SIG_CHEM_BIO_ACTIVITY":    _s("wmd", 0.85,
        "Chemical or biological weapons activity",
        "offensive"),
    "SIG_ARMS_CONTROL_EXIT":    _s("wmd", 0.75,
        "Withdrawal from arms-control treaty (INF, NPT, JCPOA)",
        "destabilising"),
    "SIG_NUCLEAR_RHETORIC":     _s("wmd", 0.70,
        "Nuclear-use rhetoric or explicit deterrence signalling",
        "destabilising"),
    "SIG_NONPROLIFERATION":     _s("wmd", 0.35,
        "Non-proliferation compliance or inspection cooperation",
        "stabilising"),

    # ══════════════════════════════════════════════════════════════
    # CYBER  (7 signals)
    # ══════════════════════════════════════════════════════════════
    "SIG_CYBER_ACTIVITY":       _s("cyber", 0.65,
        "Significant cyber operation — espionage or probing",
        "offensive"),
    "SIG_CYBER_ATTACK":         _s("cyber", 0.80,
        "Destructive cyber attack on critical infrastructure",
        "offensive"),
    "SIG_CYBER_ESPIONAGE":      _s("cyber", 0.55,
        "State-sponsored cyber espionage campaign",
        "offensive"),
    "SIG_INFO_WARFARE":         _s("cyber", 0.60,
        "Coordinated disinformation or influence operation",
        "destabilising"),
    "SIG_ELECTION_INTERFERENCE": _s("cyber", 0.65,
        "Foreign interference in electoral process",
        "destabilising"),
    "SIG_INFRASTRUCTURE_PROBE": _s("cyber", 0.55,
        "Reconnaissance probing of critical infrastructure",
        "offensive"),
    "SIG_CYBER_NORM_AGREEMENT": _s("cyber", 0.30,
        "Bilateral or multilateral cyber-norms agreement",
        "stabilising"),

    # ══════════════════════════════════════════════════════════════
    # MARITIME  (6 signals)
    # ══════════════════════════════════════════════════════════════
    "SIG_MARITIME_ESCALATION":  _s("maritime", 0.70,
        "Maritime confrontation or freedom-of-navigation incident",
        "offensive"),
    "SIG_SEA_LANE_DISRUPTION":  _s("maritime", 0.65,
        "Disruption to critical sea lane or chokepoint",
        "destabilising"),
    "SIG_NAVAL_BUILDUP":        _s("maritime", 0.60,
        "Naval base expansion or fleet modernisation surge",
        "offensive"),
    "SIG_ISLAND_MILITARISATION": _s("maritime", 0.65,
        "Militarisation of disputed island territory",
        "offensive"),
    "SIG_TERRITORIAL_CLAIM":    _s("maritime", 0.55,
        "New or expanded maritime territorial claim",
        "destabilising"),
    "SIG_MARITIME_COOPERATION": _s("maritime", 0.30,
        "Maritime security cooperation or joint patrol",
        "stabilising"),

    # ══════════════════════════════════════════════════════════════
    # ENERGY / RESOURCE  (5 signals)
    # ══════════════════════════════════════════════════════════════
    "SIG_PIPELINE_THREAT":      _s("energy", 0.65,
        "Threat to or attack on energy-pipeline infrastructure",
        "offensive"),
    "SIG_OIL_PRICE_SHOCK":      _s("energy", 0.55,
        "Sudden oil-price spike of geopolitical origin",
        "destabilising"),
    "SIG_ENERGY_WEAPONISATION": _s("energy", 0.70,
        "Use of energy exports as political leverage",
        "destabilising"),
    "SIG_CRITICAL_MINERAL":     _s("energy", 0.50,
        "Critical-mineral supply disruption or export ban",
        "destabilising"),
    "SIG_ENERGY_DIVERSIFICATION": _s("energy", 0.30,
        "Energy source diversification reducing dependency",
        "stabilising"),

    # ══════════════════════════════════════════════════════════════
    # INFORMATION / NARRATIVE  (5 signals)
    # ══════════════════════════════════════════════════════════════
    "SIG_PROPAGANDA_SURGE":     _s("information", 0.55,
        "State-media propaganda surge or narrative escalation",
        "destabilising"),
    "SIG_NARRATIVE_SHIFT":      _s("information", 0.50,
        "Significant shift in official narrative or framing",
        "neutral"),
    "SIG_DISINFO_CAMPAIGN":     _s("information", 0.60,
        "Coordinated disinformation campaign across platforms",
        "destabilising"),
    "SIG_WHISTLEBLOWER":        _s("information", 0.45,
        "Major leak or whistleblower disclosure",
        "neutral"),
    "SIG_TRANSPARENCY_MEASURE": _s("information", 0.30,
        "Transparency or confidence-building measure",
        "stabilising"),

    # ══════════════════════════════════════════════════════════════
    # CROSS-CUTTING / META  (7 signals)
    # ══════════════════════════════════════════════════════════════
    "SIG_ESCALATION_SPIRAL":    _s("meta", 0.85,
        "Action-reaction escalation spiral detected",
        "offensive"),
    "SIG_DEESCALATION":         _s("meta", 0.35,
        "De-escalation signalling from one or both parties",
        "stabilising"),
    "SIG_STATUS_QUO":           _s("meta", 0.20,
        "Maintenance of status-quo — no significant change",
        "neutral"),
    "SIG_PROXY_ACTIVATION":     _s("meta", 0.70,
        "Activation of proxy force or non-state armed group",
        "offensive"),
    "SIG_HUMANITARIAN_CRISIS":  _s("meta", 0.55,
        "Emerging or worsening humanitarian emergency",
        "destabilising"),
    "SIG_WAR_DECLARATION":      _s("meta", 0.99,
        "Formal declaration of war or armed-conflict status",
        "offensive"),
    "SIG_PEACEKEEPING_DEPLOY":  _s("meta", 0.35,
        "International peacekeeping deployment or expansion",
        "stabilising"),
}


# ── Precomputed indexes ──────────────────────────────────────────

_BY_DIMENSION: Dict[str, list] = {}
_BY_ESCALATION: Dict[str, list] = {}

for _sig, _meta in SIGNAL_ONTOLOGY.items():
    _BY_DIMENSION.setdefault(_meta["dimension"], []).append(_sig)
    _BY_ESCALATION.setdefault(_meta["escalation"], []).append(_sig)


# ── Public API ────────────────────────────────────────────────────

def get_signal_metadata(signal: str) -> Optional[SignalMeta]:
    """
    Return metadata dict for a canonical signal, or None if unknown.

    Parameters
    ----------
    signal : str
        Canonical signal token (e.g. ``"SIG_MIL_MOBILIZATION"``).

    Returns
    -------
    dict or None
        ``{dimension, weight, description, escalation}`` or ``None``.
    """
    return SIGNAL_ONTOLOGY.get(signal)


def signals_by_dimension(dimension: str) -> list:
    """Return all signals belonging to the given dimension."""
    return list(_BY_DIMENSION.get(dimension, []))


def signals_by_escalation(profile: str) -> list:
    """Return all signals with the given escalation profile."""
    return list(_BY_ESCALATION.get(profile, []))


def all_dimensions() -> list:
    """Return sorted list of dimension names."""
    return sorted(_BY_DIMENSION.keys())


def signal_weight(signal: str, default: float = 0.50) -> float:
    """Return the default belief weight for a signal."""
    meta = SIGNAL_ONTOLOGY.get(signal)
    return meta["weight"] if meta else default


def is_offensive(signal: str) -> bool:
    """True if the signal's escalation profile is 'offensive'."""
    meta = SIGNAL_ONTOLOGY.get(signal)
    return meta is not None and meta["escalation"] == "offensive"


def is_stabilising(signal: str) -> bool:
    """True if the signal's escalation profile is 'stabilising'."""
    meta = SIGNAL_ONTOLOGY.get(signal)
    return meta is not None and meta["escalation"] == "stabilising"
