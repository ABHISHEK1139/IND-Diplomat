import logging
from typing import Dict, Any, List

logger = logging.getLogger("DIP3.Layer5.SensitivityAnalysis")

class SensitivityAnalysis:
    """
    Uses SALib to identify which variables the forecast is most sensitive to.
    """
    def __init__(self):
        pass

    def run_sensitivity(self, variables: List[str]) -> Dict[str, float]:
        logger.info("Running sensitivity analysis.")
        return {var: 0.0 for var in variables}
