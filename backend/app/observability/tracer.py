"""OpenTelemetry tracer setup for per-node spans.

Default: ConsoleSpanExporter (zero cost, always on).
Optional: OTLP exporter gated behind OTLP_ENDPOINT env var — set this to pipe
spans to Jaeger, Tempo, or any OTEL-compatible backend.
"""
from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app.config import get_settings

_settings = get_settings()

provider = TracerProvider()

# ConsoleSpanExporter is always active (zero-cost local visibility).
provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

# Optional OTLP exporter — enabled when OTLP_ENDPOINT is set.
if _settings.otlp_endpoint:
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        otlp_exporter = OTLPSpanExporter(endpoint=_settings.otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    except ImportError:
        # opentelemetry-exporter-otlp not installed — log and continue.
        import logging
        logging.getLogger("agentflow.tracer").warning(
            "OTLP_ENDPOINT is set but opentelemetry-exporter-otlp is not installed. "
            "Install it with: pip install opentelemetry-exporter-otlp"
        )

trace.set_tracer_provider(provider)
tracer = trace.get_tracer("agentflow")


def traced_node(name: str):
    """Decorator: wraps a graph node function in an OTel span."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(name):
                return func(*args, **kwargs)
        return wrapper
    return decorator
