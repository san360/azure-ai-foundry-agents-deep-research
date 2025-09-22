"""Progress and completion callback handlers for web interface."""

import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import threading

from azure_ai_research.web.session import ThreadSafeSessionManager

logger = logging.getLogger(__name__)


class ProgressCallbackHandler:
    """Handler for progress callbacks from research operations."""
    
    def __init__(self, session_manager: ThreadSafeSessionManager):
        """Initialize with session manager."""
        self.session_manager = session_manager
        self._lock = threading.RLock()
        
        logger.debug("ProgressCallbackHandler initialized")
    
    def create_callback(self) -> Callable[[str, float, Optional[Dict[str, Any]]], None]:
        """Create progress callback function."""
        def progress_callback(message: str, progress: float = 0.0, metadata: Optional[Dict[str, Any]] = None):
            """Progress callback for research operations."""
            try:
                with self._lock:
                    # Validate inputs
                    if not isinstance(message, str):
                        message = str(message)
                    
                    progress = max(0.0, min(1.0, float(progress)))  # Clamp between 0 and 1
                    
                    if metadata is None:
                        metadata = {}
                    
                    # Add timestamp and thread info to metadata
                    enhanced_metadata = {
                        **metadata,
                        "callback_timestamp": datetime.now().isoformat(),
                        "thread_id": threading.current_thread().ident,
                        "thread_name": threading.current_thread().name
                    }
                    
                    # Update session state
                    self.session_manager.add_progress_message(
                        message=message,
                        progress=progress,
                        metadata=enhanced_metadata
                    )
                    
                    logger.debug(f"Progress callback: {message} ({progress:.1%})")
                    
            except Exception as e:
                logger.error(f"Progress callback failed: {e}")
                # Don't raise exception to avoid breaking research operation
        
        return progress_callback
    
    def create_completion_callback(self) -> Callable[[Any], None]:
        """Create completion callback function."""
        def completion_callback(result: Any):
            """Completion callback for research operations."""
            try:
                with self._lock:
                    if hasattr(result, 'to_dict'):
                        result_dict = result.to_dict()
                    elif isinstance(result, dict):
                        result_dict = result
                    else:
                        result_dict = {"result": str(result)}
                    
                    # Update session with result
                    self.session_manager.set_research_result(result_dict)
                    
                    # Add completion message
                    success = result_dict.get("success", True)
                    if success:
                        message = "Research completed successfully!"
                        progress = 1.0
                    else:
                        message = f"Research failed: {result_dict.get('error_message', 'Unknown error')}"
                        progress = 1.0
                        self.session_manager.set_error(result_dict.get('error_message', 'Research failed'))
                    
                    self.session_manager.add_progress_message(
                        message=message,
                        progress=progress,
                        metadata={
                            "completion": True,
                            "success": success,
                            "completion_timestamp": datetime.now().isoformat()
                        }
                    )
                    
                    logger.info(f"Research completion: success={success}")
                    
            except Exception as e:
                logger.error(f"Completion callback failed: {e}")
                self.session_manager.set_error(f"Completion callback error: {e}")
        
        return completion_callback
    
    def create_error_callback(self) -> Callable[[Exception], None]:
        """Create error callback function."""
        def error_callback(error: Exception):
            """Error callback for research operations."""
            try:
                with self._lock:
                    error_message = str(error)
                    
                    # Update session with error
                    self.session_manager.set_error(error_message)
                    
                    # Add error message
                    self.session_manager.add_progress_message(
                        message=f"Research failed: {error_message}",
                        progress=1.0,
                        metadata={
                            "error": True,
                            "error_type": type(error).__name__,
                            "error_timestamp": datetime.now().isoformat()
                        }
                    )
                    
                    logger.error(f"Research error: {error_message}")
                    
            except Exception as e:
                logger.error(f"Error callback failed: {e}")
        
        return error_callback


class CallbackChain:
    """Chain multiple callbacks together."""
    
    def __init__(self):
        """Initialize callback chain."""
        self.callbacks = []
        self._lock = threading.RLock()
    
    def add_callback(self, callback: Callable) -> None:
        """Add callback to chain."""
        with self._lock:
            self.callbacks.append(callback)
    
    def create_chained_callback(self) -> Callable:
        """Create callback that calls all registered callbacks."""
        def chained_callback(*args, **kwargs):
            """Call all callbacks in chain."""
            with self._lock:
                for callback in self.callbacks:
                    try:
                        callback(*args, **kwargs)
                    except Exception as e:
                        logger.error(f"Callback in chain failed: {e}")
        
        return chained_callback


class ThrottledProgressCallback:
    """Progress callback with throttling to prevent UI spam."""
    
    def __init__(self, 
                 base_callback: Callable,
                 min_interval_seconds: float = 0.5,
                 min_progress_delta: float = 0.01):
        """Initialize throttled callback."""
        self.base_callback = base_callback
        self.min_interval_seconds = min_interval_seconds
        self.min_progress_delta = min_progress_delta
        
        self.last_call_time = 0.0
        self.last_progress = 0.0
        self._lock = threading.RLock()
    
    def __call__(self, message: str, progress: float = 0.0, metadata: Optional[Dict[str, Any]] = None):
        """Throttled progress callback."""
        current_time = datetime.now().timestamp()
        
        with self._lock:
            # Check if enough time has passed
            time_elapsed = current_time - self.last_call_time
            progress_change = abs(progress - self.last_progress)
            
            # Call if enough time passed or significant progress change or completion
            should_call = (
                time_elapsed >= self.min_interval_seconds or
                progress_change >= self.min_progress_delta or
                progress >= 1.0 or
                progress == 0.0
            )
            
            if should_call:
                try:
                    self.base_callback(message, progress, metadata)
                    self.last_call_time = current_time
                    self.last_progress = progress
                except Exception as e:
                    logger.error(f"Throttled callback failed: {e}")


def create_progress_callback_handler(session_manager: ThreadSafeSessionManager) -> ProgressCallbackHandler:
    """Factory function to create progress callback handler."""
    return ProgressCallbackHandler(session_manager)


def create_throttled_callback(base_callback: Callable, 
                            min_interval_seconds: float = 0.5) -> ThrottledProgressCallback:
    """Factory function to create throttled callback."""
    return ThrottledProgressCallback(base_callback, min_interval_seconds)