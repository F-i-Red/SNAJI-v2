
from opentelemetry import trace

tracer = trace.get_tracer("snaji")

class TraceManager:

    def start_trace(self, operation_name):

        with tracer.start_as_current_span(operation_name) as span:
            span.set_attribute(
                "system",
                "SNAJI"
            )

            return span
