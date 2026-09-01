import logging

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
except ImportError:
    trace = None

logger = logging.getLogger("DIP3.Layer10.Audit")

class OpenTelemetryAudit:
    """
    OTLP tracer for compliance and audit logging.
    """
    def __init__(self, endpoint: str = "localhost:4317"):
        if not trace:
            logger.warning("opentelemetry not installed. Tracing mocked.")
            self.tracer = None
            return
            
        provider = TracerProvider()
        processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        self.tracer = trace.get_tracer("dip-tracer")

    def start_span(self, name: str):
        if not self.tracer:
            class MockSpan:
                def __enter__(self): pass
                def __exit__(self, *args): pass
            return MockSpan()
            
        return self.tracer.start_as_current_span(name)
