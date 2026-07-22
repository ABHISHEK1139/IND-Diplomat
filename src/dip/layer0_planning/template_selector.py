"""
Template Selector — Signature Routing
=======================================

Routes the investigation to a predefined template structure based on
the domains and objective extracted. Replaces generic planning prompts.
"""

import logging

logger = logging.getLogger("Layer0.TemplateSelector")

# Pre-defined templates for different investigation types
_TEMPLATES = {
    "Technology": {
        "needs": ["Academic Papers", "Patent Data", "Industry Reports", "News", "Government Policy"],
        "depth": "Research"
    },
    "Economy": {
        "needs": ["Financial Reports", "World Bank", "IMF", "OECD", "News", "Government Reports"],
        "depth": "Comprehensive"
    },
    "Health": {
        "needs": ["Academic Papers", "Clinical Trials", "WHO Data", "Government Reports", "News"],
        "depth": "Research"
    },
    "Military": {
        "needs": ["Conflict Data", "Sanctions Data", "Satellite Imagery", "Government Reports", "News"],
        "depth": "Comprehensive"
    },
    "Default": {
        "needs": ["News", "Government Reports", "Academic Papers", "Company Reports"],
        "depth": "Standard"
    }
}

class TemplateSelector:
    """
    Selects an investigation template (like DSPy signature routing).
    """

    def select(self, domains: list[str]) -> dict:
        """
        Returns the appropriate template based on the primary domain.
        """
        for domain in domains:
            if domain in _TEMPLATES:
                logger.info(f"Selected '{domain}' template.")
                return _TEMPLATES[domain]
                
        logger.info("Selected 'Default' template.")
        return _TEMPLATES["Default"]
