"""Telemetry and tracing service for observability."""

import logging
from typing import Dict, Any, Optional, ContextManager
from contextlib import contextmanager
from datetime import datetime
import threading
import time

# OpenTelemetry imports with fallback
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.trace import Span
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

logger = logging.getLogger(__name__)


class NoOpSpan:
    """No-operation span for when OpenTelemetry is not available."""
    
    def set_attribute(self, key: str, value: Any) -> None:
        """No-op set attribute."""
        pass
    
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """No-op add event."""
        pass
    
    def set_status(self, status: Any) -> None:
        """No-op set status."""
        pass


class TracingService:
    """Service for application tracing and telemetry."""
    
    def __init__(self, enabled: bool = True) -> None:
        """Initialize tracing service."""
        self.enabled = enabled and OTEL_AVAILABLE
        self._tracer = None
        self._lock = threading.RLock()
        
        if self.enabled:
            self._setup_tracing()
            logger.info("Tracing service initialized with OpenTelemetry")
        else:
            if not OTEL_AVAILABLE:
                logger.warning("OpenTelemetry not available, tracing disabled")
            else:
                logger.info("Tracing service disabled")
    
    def _setup_tracing(self) -> None:
        """Setup OpenTelemetry tracing."""
        try:
            # Set up tracer provider
            trace.set_tracer_provider(TracerProvider())
            
            # Add console exporter for debugging
            console_exporter = ConsoleSpanExporter()
            span_processor = BatchSpanProcessor(console_exporter)
            trace.get_tracer_provider().add_span_processor(span_processor)
            
            # Get tracer
            self._tracer = trace.get_tracer(__name__)
            
        except Exception as e:
            logger.error(f"Failed to setup tracing: {e}")
            self.enabled = False
    
    @contextmanager
    def trace_operation(self, operation_name: str, attributes: Optional[Dict[str, Any]] = None) -> ContextManager:
        """Context manager for tracing operations."""
        if not self.enabled or not self._tracer:
            # Return no-op span
            yield NoOpSpan()
            return
        
        with self._tracer.start_as_current_span(operation_name) as span:
            try:
                # Add default attributes
                span.set_attribute("operation", operation_name)
                span.set_attribute("timestamp", datetime.now().isoformat())
                span.set_attribute("thread_id", threading.current_thread().ident)
                
                # Add custom attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, str(value))
                
                yield span
                
            except Exception as e:
                span.set_attribute("error", True)
                span.set_attribute("error_message", str(e))
                span.add_event("error", {"exception": str(e)})
                raise
    
    def record_metric(self, name: str, value: float, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Record a metric value."""
        try:
            with self._lock:
                # For now, just log metrics
                # In production, you would send to a metrics backend
                metric_data = {
                    "metric": name,
                    "value": value,
                    "timestamp": datetime.now().isoformat(),
                    "attributes": attributes or {}
                }
                
                logger.debug(f"Metric recorded: {metric_data}")
                
        except Exception as e:
            logger.error(f"Failed to record metric {name}: {e}")
    
    def record_event(self, event_name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Record a custom event."""
        try:
            event_data = {
                "event": event_name,
                "timestamp": datetime.now().isoformat(),
                "attributes": attributes or {}
            }
            
            logger.info(f"Event: {event_data}")
            
        except Exception as e:
            logger.error(f"Failed to record event {event_name}: {e}")
    
    def measure_duration(self, operation_name: str):
        """Decorator to measure operation duration."""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                
                try:
                    with self.trace_operation(f"{operation_name}_{func.__name__}") as span:
                        result = func(*args, **kwargs)
                        
                        duration = time.time() - start_time
                        span.set_attribute("duration_seconds", duration)
                        
                        self.record_metric(
                            f"{operation_name}_duration",
                            duration,
                            {"function": func.__name__}
                        )
                        
                        return result
                        
                except Exception as e:
                    duration = time.time() - start_time
                    self.record_metric(
                        f"{operation_name}_error_duration",
                        duration,
                        {"function": func.__name__, "error": str(e)}
                    )
                    raise
            
            return wrapper
        return decorator
    
    def get_trace_context(self) -> Dict[str, Any]:
        """Get current trace context information."""
        try:
            if not self.enabled:
                return {"tracing_enabled": False}
            
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                span_context = current_span.get_span_context()
                return {
                    "tracing_enabled": True,
                    "trace_id": format(span_context.trace_id, '032x'),
                    "span_id": format(span_context.span_id, '016x'),
                    "is_recording": current_span.is_recording()
                }
            else:
                return {"tracing_enabled": True, "active_span": False}
                
        except Exception as e:
            logger.error(f"Failed to get trace context: {e}")
            return {"tracing_enabled": self.enabled, "error": str(e)}
    
    def flush_traces(self, timeout_seconds: int = 30) -> bool:
        """Flush any pending traces."""
        try:
            if not self.enabled:
                return True
            
            # Force flush span processors
            tracer_provider = trace.get_tracer_provider()
            if hasattr(tracer_provider, 'force_flush'):
                return tracer_provider.force_flush(timeout_millis=timeout_seconds * 1000)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to flush traces: {e}")
            return False
    
    def cleanup(self) -> None:
        """Clean up tracing resources."""
        try:
            if self.enabled:
                self.flush_traces()
                
                # Shutdown tracer provider
                tracer_provider = trace.get_tracer_provider()
                if hasattr(tracer_provider, 'shutdown'):
                    tracer_provider.shutdown()
                
                logger.info("Tracing service cleaned up")
                
        except Exception as e:
            logger.error(f"Error during tracing cleanup: {e}")
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get tracing service information."""
        return {
            "enabled": self.enabled,
            "otel_available": OTEL_AVAILABLE,
            "tracer_configured": self._tracer is not None,
            "service": "TracingService"
        }


# Global tracing service instance
_global_tracing_service: Optional[TracingService] = None
_tracing_lock = threading.RLock()


def get_global_tracing_service() -> TracingService:
    """Get or create global tracing service instance."""
    global _global_tracing_service
    
    with _tracing_lock:
        if _global_tracing_service is None:
            _global_tracing_service = TracingService()
        
        return _global_tracing_service


def set_global_tracing_service(service: TracingService) -> None:
    """Set global tracing service instance."""
    global _global_tracing_service
    
    with _tracing_lock:
        _global_tracing_service = service


def trace_function(operation_name: str):
    """Decorator to trace function execution."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            tracing_service = get_global_tracing_service()
            
            with tracing_service.trace_operation(f"{operation_name}_{func.__name__}") as span:
                span.set_attribute("function", func.__name__)
                span.set_attribute("module", func.__module__)
                
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def create_tracing_service(enabled: bool = True) -> TracingService:
    """Factory function to create tracing service."""
    return TracingService(enabled)