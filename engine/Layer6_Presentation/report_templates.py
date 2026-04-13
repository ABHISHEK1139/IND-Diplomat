"""
Layer-6 Presentation — Report Templates
=========================================

Plain-text templates for intelligence briefings.
Each template is a format-string consumed by report_builder.py.

Design rules:
    1.  No ANSI colour — terminal-safe, pipe-safe, file-safe.
    2.  Fit in 80 columns (printable on paper).
    3.  Use box-drawing where possible (UTF-8 safe).
    4.  Every section has a clear header — scannable in 10 seconds.
"""

# ── Dimension labels (human-readable) ────────────────────────────────
DIMENSION_LABELS = {
    "CAPABILITY": "Military Capability",
    "INTENT":     "Strategic Intent",
    "STABILITY":  "Domestic Stability",
    "COST":       "Cost / Economic Pressure",
}

# ── Confidence descriptors ────────────────────────────────────────────
def confidence_word(value: float) -> str:
    """Map a 0–1 confidence score to an ICD-203 style descriptor."""
    if value >= 0.85:
        return "HIGH"
    if value >= 0.65:
        return "MODERATE"
    if value >= 0.45:
        return "LOW"
    if value >= 0.25:
        return "VERY LOW"
    return "INDETERMINATE"


def dimension_word(value: float) -> str:
    """Map a 0–1 dimension coverage to a qualitative assessment."""
    if value >= 0.75:
        return "STRONG"
    if value >= 0.50:
        return "MODERATE"
    if value >= 0.25:
        return "WEAK"
    if value >= 0.10:
        return "MARGINAL"
    return "INSUFFICIENT"


# ── Section dividers ──────────────────────────────────────────────────
HEAVY_LINE = "=" * 64
LIGHT_LINE = "-" * 64
THIN_LINE  = "·" * 64

# ── WITHHELD report template ─────────────────────────────────────────
WITHHELD_TEMPLATE = """{header}
{heavy}

  ASSESSMENT:  WITHHELD
  CONFIDENCE:  {confidence_word}
  DATE:        {date}

{heavy}

  The system has determined that available intelligence is
  INSUFFICIENT to support a reliable assessment.

  The analytical council completed its deliberation and
  proposed "{proposed}" — but the Judgment Authority blocked
  release because {reason_count} quality gate(s) failed.

{light}
  WHY THIS ASSESSMENT WAS WITHHELD
{light}

{reasons}

{light}
  CURRENT SITUATION PICTURE  (what we DO know)
{light}

{dimensions}

{light}
  INTELLIGENCE GAPS  (what we do NOT know)
{light}

{gaps}

{light}
  COLLECTION REQUIRED  (what the system is requesting)
{light}

{collection}

{light}
  KEY EARLY-WARNING INDICATORS  (what would change the picture)
{light}

{indicators}

{light}
  SOURCES CONSULTED  ({source_count})
{light}

{sources}

{heavy}
  RECOMMENDATION:  Do NOT act on this assessment.
  Collect the requested intelligence, then re-task the system.
{heavy}
"""


# ── AUTHORIZED (normal) report template ──────────────────────────────
AUTHORIZED_TEMPLATE = """{header}
{heavy}

  ASSESSMENT:  {risk_level}
  CONFIDENCE:  {confidence_word} ({confidence:.1%})
  DATE:        {date}

{heavy}

{executive_summary}

{light}
  SITUATION OVERVIEW
{light}

{dimensions}

{light}
  KEY INDICATORS
{light}

{key_indicators}

{light}
  CONSTRAINTS ON ESCALATION
{light}

{constraints}

{light}
  WHAT WOULD CHANGE THIS ASSESSMENT
{light}

{counterfactuals}

{light}
  INTELLIGENCE GAPS
{light}

{gaps}

{light}
  SOURCES  ({source_count})
{light}

{sources}

{heavy}
"""

# ── Header ────────────────────────────────────────────────────────────
HEADER = "  IND-DIPLOMAT INTELLIGENCE ASSESSMENT"
