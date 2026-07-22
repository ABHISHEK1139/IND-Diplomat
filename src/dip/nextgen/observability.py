from __future__ import annotations

"""Optional observability hooks for OpenTelemetry and MLflow."""

from dip.Config.config import config

from contextlib import contextmanager
from typing import Any, Dict, Optional

# OpenTelemetry (optional)
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource
    OTEL_AVAILABLE = True
except Exception:
    OTEL_AVAILABLE = False

# MLflow (optional)
try:
    import mlflow
    MLFLOW_AVAILABLE = True
except Exception:
    MLFLOW_AVAILABLE = False


class ObservabilityManager:
    """Manages optional observability backends."""

    def __init__(self, service_name: str = "dip2-nextgen"):
        self.service_name = service_name
        self._tracer = None
        self._mlflow_active = False
        self._init_otel()
        self._init_mlflow()

    def _init_otel(self) -> None:
        if not OTEL_AVAILABLE:
            return
        if not config.DIP_OTEL_ENABLED:
            return
        resource = Resource.create({"service.name": self.service_name})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)
        self._tracer = trace.get_tracer(__name__)

    def _init_mlflow(self) -> None:
        if not MLFLOW_AVAILABLE:
            return
        if not config.DIP_MLFLOW_ENABLED:
            return
        tracking_uri = config.MLFLOW_TRACKING_URI
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(config.DIP_MLFLOW_EXPERIMENT)
        self._mlflow_active = True

    @contextmanager
    def trace_phase(self, phase: str, attributes: Optional[Dict[str, Any]] = None):
        """Context manager for tracing a pipeline phase."""
        if self._tracer:
            with self._tracer.start_as_current_span(f"dip2.{phase}", attributes=attributes or {}) as span:
                yield span
        else:
            yield None

    def log_metric(self, name: str, value: float, step: Optional[int] = None) -> None:
        """Log a metric to MLflow if active."""
        if self._mlflow_active:
            try:
                mlflow.log_metric(name, value, step=step)
            except Exception:
                pass

    def log_param(self, name: str, value: Any) -> None:
        """Log a parameter to MLflow if active."""
        if self._mlflow_active:
            try:
                mlflow.log_param(name, str(value))
            except Exception:
                pass

    def start_run(self, run_name: Optional[str] = None) -> Any:
        """Start an MLflow run if active."""
        if self._mlflow_active:
            try:
                return mlflow.start_run(run_name=run_name)
            except Exception:
                return None
        return None

    def end_run(self) -> None:
        """End MLflow run if active."""
        if self._mlflow_active:
            try:
                mlflow.end_run()
            except Exception:
                pass


# Global instance
observability = ObservabilityManager()


def get_tracer():
    """Get the OpenTelemetry tracer if available."""
    return observability._tracer


def is_otel_enabled() -> bool:
    return observability._tracer is not None


def is_mlflow_enabled() -> bool:
    return observability._mlflow_active