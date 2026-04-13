"""
Layer6_Presentation — The Analyst's Voice
==========================================

Transforms internal pipeline state into human-readable intelligence
briefings.  The analytical brain (Layers 1–5) *thinks*.
This layer *speaks*.

Layer-6 is a **camera, not a narrator**.  It reads the frozen
assessment record produced by Layer-5 and formats it for human
consumption.  It NEVER computes intelligence.

Quick start::

    from engine.Layer6_Presentation import build_user_report
    report = build_user_report(result_dict)

    # Full 7-section + 3-appendix briefing:
    from engine.Layer6_Presentation import build_full_briefing
    from engine.Layer5_Judgment.assessment_record import build_assessment_record
    record = build_assessment_record(result_dict)
    briefing = build_full_briefing(record)
"""

from .report_builder import (  # noqa: F401
    build_user_report,
    build_report_from_pipeline_result,
)

from .briefing_builder import (  # noqa: F401
    build_full_briefing,
    build_briefing_from_file,
    write_briefing,
)

__all__ = [
    "build_user_report",
    "build_report_from_pipeline_result",
    "build_full_briefing",
    "build_briefing_from_file",
    "write_briefing",
]
