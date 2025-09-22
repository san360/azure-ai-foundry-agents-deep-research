"""Streamlit session state management with thread safety."""

import streamlit as st
import threading
import logging
from typing import Any, Dict, Optional, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class SessionState:
    """Thread-safe session state container."""
    
    research_running: bool = False
    research_result: Optional[Dict[str, Any]] = None
    current_log_file: Optional[str] = None
    progress_messages: list = field(default_factory=list)
    last_update: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session state to dictionary."""
        return {
            "research_running": self.research_running,
            "research_result": self.research_result,
            "current_log_file": self.current_log_file,
            "progress_messages": self.progress_messages[-10:],  # Keep last 10 messages
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "error_message": self.error_message
        }


class ThreadSafeSessionManager:
    """Thread-safe session state manager for Streamlit."""
    
    def __init__(self):
        """Initialize session manager with lock."""
        self._lock = threading.RLock()
        logger.debug("ThreadSafeSessionManager initialized")
    
    def get_state(self) -> SessionState:
        """Get current session state in thread-safe manner."""
        with self._lock:
            # Initialize session state if not exists
            if 'app_state' not in st.session_state:
                st.session_state.app_state = SessionState()
            
            return st.session_state.app_state
    
    def update_state(self, **kwargs) -> None:
        """Update session state fields in thread-safe manner."""
        with self._lock:
            state = self.get_state()
            
            for key, value in kwargs.items():
                if hasattr(state, key):
                    setattr(state, key, value)
                    logger.debug(f"Updated session state: {key}")
                else:
                    logger.warning(f"Unknown session state field: {key}")
            
            # Update timestamp
            state.last_update = datetime.now()
            st.session_state.app_state = state
    
    def add_progress_message(self, message: str, progress: float = 0.0, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add progress message to session state."""
        with self._lock:
            state = self.get_state()
            
            progress_entry = {
                "message": message,
                "progress": progress,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            state.progress_messages.append(progress_entry)
            
            # Keep only last 20 messages to prevent memory issues
            if len(state.progress_messages) > 20:
                state.progress_messages = state.progress_messages[-20:]
            
            state.last_update = datetime.now()
            st.session_state.app_state = state
            
            logger.debug(f"Added progress message: {message}")
    
    def clear_progress_messages(self) -> None:
        """Clear all progress messages."""
        with self._lock:
            state = self.get_state()
            state.progress_messages = []
            state.last_update = datetime.now()
            st.session_state.app_state = state
            
            logger.debug("Cleared progress messages")
    
    def set_research_running(self, running: bool) -> None:
        """Set research running state."""
        with self._lock:
            self.update_state(research_running=running)
            
            if running:
                self.clear_progress_messages()
                self.update_state(error_message=None)
            
            logger.info(f"Research running state set to: {running}")
    
    def set_research_result(self, result: Optional[Dict[str, Any]]) -> None:
        """Set research result."""
        with self._lock:
            self.update_state(
                research_result=result,
                research_running=False
            )
            
            logger.info("Research result updated in session state")
    
    def set_error(self, error_message: str) -> None:
        """Set error message and stop research."""
        with self._lock:
            self.update_state(
                error_message=error_message,
                research_running=False
            )
            
            logger.error(f"Error set in session state: {error_message}")
    
    def clear_error(self) -> None:
        """Clear error message."""
        with self._lock:
            self.update_state(error_message=None)
            logger.debug("Error message cleared")
    
    def set_log_file(self, log_file: Optional[str]) -> None:
        """Set current log file."""
        with self._lock:
            self.update_state(current_log_file=log_file)
            logger.debug(f"Log file set to: {log_file}")
    
    def get_progress_messages(self, limit: int = 10) -> list:
        """Get recent progress messages."""
        with self._lock:
            state = self.get_state()
            messages = state.progress_messages[-limit:] if state.progress_messages else []
            return messages
    
    def is_research_running(self) -> bool:
        """Check if research is currently running."""
        with self._lock:
            state = self.get_state()
            return state.research_running
    
    def get_research_result(self) -> Optional[Dict[str, Any]]:
        """Get current research result."""
        with self._lock:
            state = self.get_state()
            return state.research_result
    
    def get_current_log_file(self) -> Optional[str]:
        """Get current log file path."""
        with self._lock:
            state = self.get_state()
            return state.current_log_file
    
    def get_error_message(self) -> Optional[str]:
        """Get current error message."""
        with self._lock:
            state = self.get_state()
            return state.error_message
    
    def reset_session(self) -> None:
        """Reset session state to initial values."""
        with self._lock:
            st.session_state.app_state = SessionState()
            logger.info("Session state reset")
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get session information for debugging."""
        with self._lock:
            state = self.get_state()
            return {
                "session_id": id(st.session_state),
                "state_summary": state.to_dict(),
                "thread_id": threading.current_thread().ident,
                "thread_name": threading.current_thread().name
            }


class SessionStateHelper:
    """Helper class for common session state operations."""
    
    def __init__(self, session_manager: ThreadSafeSessionManager):
        """Initialize with session manager."""
        self.session_manager = session_manager
    
    def ensure_initialized(self, key: str, default_value: Any) -> Any:
        """Ensure a session state key is initialized with default value."""
        if key not in st.session_state:
            st.session_state[key] = default_value
            logger.debug(f"Initialized session state key '{key}' with default value")
        
        return st.session_state[key]
    
    def safe_get(self, key: str, default: Any = None) -> Any:
        """Safely get session state value with default."""
        try:
            return st.session_state.get(key, default)
        except Exception as e:
            logger.warning(f"Failed to get session state key '{key}': {e}")
            return default
    
    def safe_set(self, key: str, value: Any) -> bool:
        """Safely set session state value."""
        try:
            st.session_state[key] = value
            logger.debug(f"Set session state key '{key}'")
            return True
        except Exception as e:
            logger.error(f"Failed to set session state key '{key}': {e}")
            return False
    
    def create_progress_callback(self) -> callable:
        """Create progress callback for research operations."""
        def progress_callback(message: str, progress: float = 0.0, metadata: Optional[Dict[str, Any]] = None):
            """Thread-safe progress callback for background operations."""
            try:
                self.session_manager.add_progress_message(message, progress, metadata)
            except Exception as e:
                logger.error(f"Failed to update progress: {e}")
        
        return progress_callback
    
    def format_progress_message(self, message: str, progress: float) -> str:
        """Format progress message with percentage."""
        percentage = int(progress * 100)
        return f"[{percentage:3d}%] {message}"


# Global session manager instance
_global_session_manager: Optional[ThreadSafeSessionManager] = None
_session_lock = threading.RLock()


def get_session_manager() -> ThreadSafeSessionManager:
    """Get or create global session manager."""
    global _global_session_manager
    
    with _session_lock:
        if _global_session_manager is None:
            _global_session_manager = ThreadSafeSessionManager()
        
        return _global_session_manager


def create_session_helper() -> SessionStateHelper:
    """Create session state helper with global manager."""
    return SessionStateHelper(get_session_manager())