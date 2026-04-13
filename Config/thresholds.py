"""
Centralized Configuration for Signal Thresholds.
"""

class SignalThresholds:
    # Military
    HIGH_MOBILIZATION = 0.65
    HIGH_LOGISTICS_ACTIVITY = 0.60
    SIGNIFICANT_EXERCISES = 0.30  # Normalized score
    EXERCISE_COUNT_MIN = 3
    
    # Diplomatic
    HIGH_HOSTILITY_TONE = 0.60
    NEGOTIATION_OPEN = 0.40
    HIGH_ALLIANCE_ACTIVITY = 0.50
    ALLIANCE_REALIGNMENT = 0.55
    
    # Economic
    HIGH_SANCTIONS_PRESSURE = 0.50
    HIGH_ECONOMIC_PRESSURE = 0.60
    HIGH_TRADE_DEPENDENCY = 0.60
    
    # Domestic
    REGIME_INSTABILITY = 0.55
    HIGH_CIVIL_UNREST = 0.50
    HIGH_PROTEST_PRESSURE = 0.40
    LOW_REGIME_STABILITY = 0.40  # Direct stability score threshold
    
    # Text Normalization
    LOGISTICS_LEVELS = {"high", "medium"}
    STOCKPILE_LEVELS = {"high"}
    
    @classmethod
    def get_defaults(cls):
        """Return a dictionary of default thresholds used by Verifier."""
        return {
            "high_mobilization": cls.HIGH_MOBILIZATION,
            "logistics_buildup": cls.HIGH_LOGISTICS_ACTIVITY,
            "border_positioning": 0.60, # Specific to verifier logic
            "recent_exercises": cls.SIGNIFICANT_EXERCISES,
            "hostility_tone_high": cls.HIGH_HOSTILITY_TONE,
            "negotiation_channels_open": cls.NEGOTIATION_OPEN,
            "alliance_activity_high": cls.HIGH_ALLIANCE_ACTIVITY,
            "alliance_realignment": cls.ALLIANCE_REALIGNMENT,
            "escalation_ladder_active": 0.55,
            "sanctions_pressure": cls.HIGH_SANCTIONS_PRESSURE,
            "economic_pressure_high": cls.HIGH_ECONOMIC_PRESSURE,
            "trade_dependency_high": cls.HIGH_TRADE_DEPENDENCY,
            "regime_instability": cls.REGIME_INSTABILITY,
            "civil_unrest": cls.HIGH_CIVIL_UNREST,
            "protest_pressure": cls.HIGH_PROTEST_PRESSURE,
        }
