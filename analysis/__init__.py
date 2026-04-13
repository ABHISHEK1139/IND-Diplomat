"""Analysis package — additive analytical tools that layer on top of the core pipeline."""

from .experiments import (                       # noqa: F401
    CrisisReplayExperiment,
    AblationExperiment,
    LeadTimeExperiment,
    brier_score,
    run_all_experiments,
    print_full_report,
    CRISIS_TIMELINES,
)
