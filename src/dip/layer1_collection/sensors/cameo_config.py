"""
CAMEO Event Configuration
=========================
Maps CAMEO (Conflict and Mediation Event Observations) root codes to Canonical Signals.
Includes Goldstein scale mappings for intensity.
"""

CAMEO_TO_SIGNAL = {
    # Military / Escalation
    "18": "SIG_MIL_ESCALATION",         # Assault
    "19": "SIG_MIL_ESCALATION",         # Fight
    "20": "SIG_MIL_ESCALATION",         # Unconventional mass violence
    "15": "SIG_FORCE_POSTURE",          # Exhibit military posture
    
    # Coercion / Hostility
    "17": "SIG_COERCIVE_PRESSURE",      # Coerce
    "13": "SIG_DIP_HOSTILITY",          # Threaten
    "11": "SIG_DIP_HOSTILITY",          # Disapprove
    "10": "SIG_COERCIVE_BARGAINING",    # Demand
    
    # Diplomatic Breakdown
    "16": "SIG_NEGOTIATION_BREAKDOWN",  # Reduce relations
    "12": "SIG_NEGOTIATION_BREAKDOWN",  # Reject
    
    # Internal
    "14": "SIG_INTERNAL_INSTABILITY",   # Protest
    
    # Diplomacy / Cooperation
    "04": "SIG_DIPLOMACY_ACTIVE",       # Consult
    "05": "SIG_DIPLOMACY_ACTIVE",       # Engage in diplomatic cooperation
    "06": "SIG_DIPLOMACY_ACTIVE",       # Engage in material cooperation
    "07": "SIG_AID_COOPERATION",        # Provide aid
    "08": "SIG_AID_COOPERATION",        # Yield
    
    # Statements
    "01": "SIG_PUBLIC_STATEMENT",       # Make public statement
    "02": "SIG_PUBLIC_STATEMENT",       # Appeal
    "03": "SIG_PUBLIC_STATEMENT",       # Express intent to cooperate
}

# Goldstein Scale (-10.0 to 10.0) mapping for base intensity computation
GOLDSTEIN_SCALE = {
    "18": -9.0,
    "19": -10.0,
    "20": -10.0,
    "15": -7.0,
    "17": -9.0,
    "13": -5.8,
    "11": -2.0,
    "10": -5.0,
    "16": -7.2,
    "12": -4.0,
    "14": -6.5,
    "04": 1.0,
    "05": 3.4,
    "06": 6.0,
    "07": 7.4,
    "08": 5.0,
    "01": 0.0,
    "02": 3.0,
    "03": 4.0,
}

def get_signal_type(cameo_code: str) -> str:
    root = cameo_code[:2] if cameo_code else "00"
    return CAMEO_TO_SIGNAL.get(root, "SIG_UNKNOWN")

def get_goldstein(cameo_code: str) -> float:
    root = cameo_code[:2] if cameo_code else "00"
    return GOLDSTEIN_SCALE.get(root, 0.0)
