"""Secure and maintainable Streamlit application for Azure AI research."""

import streamlit as st
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import threading
from concurrent.futures import Future
import json

from azure_ai_research.infrastructure.config import AppConfig, get_default_config
from azure_ai_research.core.research import ResearchService, ResearchRequest, ResearchResult
from azure_ai_research.web.session import get_session_manager, create_session_helper
from azure_ai_research.web.callbacks import create_progress_callback_handler, create_throttled_callback
from azure_ai_research.security.validation import validate_research_query, ValidationError
from azure_ai_research.infrastructure.file_system import create_secure_file_handler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StreamlitApp:
    """Main Streamlit application class with proper architecture."""
    
    def __init__(self):
        """Initialize Streamlit application."""
        try:
            # Load configuration
            self.config = get_default_config()
            
            # Initialize services
            self.research_service = ResearchService(self.config)
            self.session_manager = get_session_manager()
            self.session_helper = create_session_helper()
            self.file_handler = create_secure_file_handler(
                self.config.logging.log_directory,
                self.config.security.allowed_file_extensions
            )
            
            # Initialize callback handler
            self.callback_handler = create_progress_callback_handler(self.session_manager)
            
            # Research future for async operations
            self.research_future: Optional[Future] = None
            
            logger.info("StreamlitApp initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize StreamlitApp: {e}")
            st.error(f"Application initialization failed: {e}")
            st.stop()
    
    def run(self) -> None:
        """Run the Streamlit application."""
        try:
            # Configure page
            st.set_page_config(
                page_title="Azure AI Deep Research",
                page_icon="🔍",
                layout="wide",
                initial_sidebar_state="expanded"
            )
            
            # Main application
            self._render_header()
            self._render_sidebar()
            self._render_main_content()
            self._render_footer()
            
        except Exception as e:
            logger.error(f"Application runtime error: {e}")
            st.error(f"Application error: {e}")
    
    def _render_header(self) -> None:
        """Render application header."""
        st.title("🔍 Azure AI Deep Research")
        st.markdown("Conduct comprehensive research using Azure AI Agents with proper security and observability.")
        
        # Status indicator
        if self.session_manager.is_research_running():
            st.info("🔄 Research in progress...")
        elif self.session_manager.get_error_message():
            st.error(f"❌ Error: {self.session_manager.get_error_message()}")
        elif self.session_manager.get_research_result():
            st.success("✅ Research completed successfully!")
    
    def _render_sidebar(self) -> None:
        """Render sidebar with configuration and controls."""
        with st.sidebar:
            st.header("Configuration")
            
            # Service status
            with st.expander("Service Status", expanded=False):
                status = self.research_service.get_service_status()
                st.json(status)
            
            # Research settings
            st.subheader("Research Settings")
            
            enable_citations = st.checkbox(
                "Enable Citations",
                value=True,
                help="Extract and format citations from research results"
            )
            
            # Store settings in session
            self.session_helper.safe_set("enable_citations", enable_citations)
            
            # Clear session button
            if st.button("Clear Session", help="Reset application state"):
                self._clear_session()
            
            # Log management
            st.subheader("Log Management")
            self._render_log_management()
    
    def _render_main_content(self) -> None:
        """Render main content area."""
        col1, col2 = st.columns([2, 1])
        
        with col1:
            self._render_research_interface()
        
        with col2:
            self._render_progress_panel()
        
        # Research results
        self._render_research_results()
    
    def _render_research_interface(self) -> None:
        """Render research query interface."""
        st.subheader("Research Query")
        
        # Research query input
        query = st.text_area(
            "Enter your research question:",
            height=100,
            placeholder="e.g., What are the latest developments in quantum computing?",
            help="Enter a detailed research question. Be specific for better results."
        )
        
        # Research button
        col1, col2 = st.columns([1, 3])
        
        with col1:
            if st.button(
                "🔍 Start Research",
                disabled=self.session_manager.is_research_running() or not query.strip(),
                help="Start comprehensive research on your query"
            ):
                self._start_research(query.strip())
        
        with col2:
            if self.session_manager.is_research_running():
                if st.button("⏹️ Stop Research", help="Stop current research"):
                    self._stop_research()
    
    def _render_progress_panel(self) -> None:
        """Render progress tracking panel."""
        st.subheader("Progress")
        
        # Progress messages
        messages = self.session_manager.get_progress_messages(limit=10)
        
        if messages:
            # Show latest message prominently
            latest = messages[-1]
            progress_value = latest.get("progress", 0.0)
            
            st.progress(progress_value)
            st.write(f"**{latest['message']}**")
            
            # Show all messages in expander
            with st.expander("Progress History", expanded=False):
                for msg in reversed(messages):
                    timestamp = msg.get("timestamp", "")
                    if timestamp:
                        # Format timestamp
                        try:
                            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                            time_str = dt.strftime("%H:%M:%S")
                        except:
                            time_str = timestamp[:8]
                    else:
                        time_str = ""
                    
                    progress_pct = int(msg.get("progress", 0) * 100)
                    st.write(f"`{time_str}` [{progress_pct:3d}%] {msg['message']}")
        else:
            st.info("No progress messages yet. Start a research to see progress updates.")
    
    def _render_research_results(self) -> None:
        """Render research results section."""
        result = self.session_manager.get_research_result()
        
        if result:
            st.subheader("Research Results")
            
            # Show success/failure status
            success = result.get("success", False)
            if success:
                st.success("Research completed successfully!")
                
                # Show content
                content = result.get("content", "")
                if content:
                    st.markdown("### Research Content")
                    st.markdown(content, unsafe_allow_html=True)
                
                # Show citations
                citations = result.get("citations", [])
                if citations:
                    st.markdown("### Citations")
                    for i, citation in enumerate(citations, 1):
                        title = citation.get("title", "Untitled")
                        url = citation.get("url", "")
                        st.markdown(f"{i}. **{title}**")
                        if url:
                            st.markdown(f"   🔗 [{url}]({url})")
                
                # Show metadata
                with st.expander("Research Metadata", expanded=False):
                    metadata = result.get("metadata", {})
                    execution_time = result.get("execution_time_seconds", 0)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Execution Time", f"{execution_time:.1f}s")
                    with col2:
                        st.metric("Citations Found", len(citations))
                    
                    st.json(metadata)
            else:
                error_msg = result.get("error_message", "Unknown error")
                st.error(f"Research failed: {error_msg}")
    
    def _render_log_management(self) -> None:
        """Render log management interface."""
        try:
            # List log files
            log_files = self.file_handler.list_files("research_log_*.json")
            
            if log_files:
                st.write(f"Found {len(log_files)} log files")
                
                # Show recent logs
                if st.button("Load Recent Logs"):
                    self._load_recent_logs()
                
                # Log file selector
                selected_log = st.selectbox(
                    "Select log file:",
                    options=[f.name for f in log_files],
                    index=0 if log_files else None
                )
                
                if selected_log and st.button("Load Selected Log"):
                    self._load_specific_log(selected_log)
            else:
                st.info("No log files found")
        
        except Exception as e:
            st.error(f"Error loading logs: {e}")
    
    def _render_footer(self) -> None:
        """Render application footer."""
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**Azure AI Deep Research**")
        
        with col2:
            if st.button("Export Results", disabled=not self.session_manager.get_research_result()):
                self._export_results()
        
        with col3:
            st.markdown(f"*Session: {datetime.now().strftime('%H:%M:%S')}*")
    
    def _start_research(self, query: str) -> None:
        """Start research operation."""
        try:
            # Validate query
            validated_query = validate_research_query(query, self.config.security.max_input_length)
            
            # Get research settings
            enable_citations = self.session_helper.safe_get("enable_citations", True)
            
            # Create research request
            request = ResearchRequest(
                query=validated_query,
                enable_citations=enable_citations
            )
            
            # Clear previous results and errors
            self.session_manager.clear_error()
            self.session_manager.clear_progress_messages()
            self.session_manager.set_research_running(True)
            
            # Create progress callback
            progress_callback = create_throttled_callback(
                self.callback_handler.create_callback()
            )
            
            # Start async research
            self.research_future = self.research_service.conduct_research_async(
                request, progress_callback
            )
            
            # Add completion callback
            def on_completion():
                try:
                    if self.research_future:
                        result = self.research_future.result()
                        self.callback_handler.create_completion_callback()(result)
                        
                        # Save to log file
                        log_path = self.research_service.save_research_log(result)
                        self.session_manager.set_log_file(log_path)
                        
                except Exception as e:
                    self.callback_handler.create_error_callback()(e)
            
            # Schedule completion check
            threading.Timer(1.0, self._check_research_completion).start()
            
            st.success(f"Research started for query: {query[:100]}...")
            st.rerun()
            
        except ValidationError as e:
            st.error(f"Invalid query: {e}")
        except Exception as e:
            logger.error(f"Failed to start research: {e}")
            st.error(f"Failed to start research: {e}")
    
    def _check_research_completion(self) -> None:
        """Check if research is completed and handle result."""
        if self.research_future and self.research_future.done():
            try:
                result = self.research_future.result()
                self.callback_handler.create_completion_callback()(result)
                
                # Save to log file
                log_path = self.research_service.save_research_log(result)
                self.session_manager.set_log_file(log_path)
                
            except Exception as e:
                self.callback_handler.create_error_callback()(e)
        elif self.session_manager.is_research_running():
            # Schedule next check
            threading.Timer(2.0, self._check_research_completion).start()
    
    def _stop_research(self) -> None:
        """Stop current research operation."""
        try:
            if self.research_future:
                self.research_future.cancel()
            
            self.session_manager.set_research_running(False)
            self.session_manager.add_progress_message("Research stopped by user", 1.0)
            
            st.warning("Research stopped by user")
            st.rerun()
            
        except Exception as e:
            logger.error(f"Failed to stop research: {e}")
            st.error(f"Failed to stop research: {e}")
    
    def _clear_session(self) -> None:
        """Clear session state."""
        try:
            self.session_manager.reset_session()
            st.success("Session cleared successfully")
            st.rerun()
        except Exception as e:
            logger.error(f"Failed to clear session: {e}")
            st.error(f"Failed to clear session: {e}")
    
    def _load_recent_logs(self) -> None:
        """Load recent research logs."""
        try:
            logs = self.research_service.load_research_logs()
            if logs:
                latest_log = logs[0]  # Most recent
                self.session_manager.set_research_result(latest_log)
                st.success("Recent log loaded successfully")
                st.rerun()
            else:
                st.info("No logs found")
        except Exception as e:
            logger.error(f"Failed to load recent logs: {e}")
            st.error(f"Failed to load logs: {e}")
    
    def _load_specific_log(self, log_filename: str) -> None:
        """Load specific log file."""
        try:
            log_data = self.file_handler.read_json(log_filename)
            self.session_manager.set_research_result(log_data)
            st.success(f"Log file '{log_filename}' loaded successfully")
            st.rerun()
        except Exception as e:
            logger.error(f"Failed to load log file {log_filename}: {e}")
            st.error(f"Failed to load log file: {e}")
    
    def _export_results(self) -> None:
        """Export research results."""
        try:
            result = self.session_manager.get_research_result()
            if result:
                # Create export data
                export_data = {
                    "export_timestamp": datetime.now().isoformat(),
                    "research_result": result,
                    "session_info": self.session_manager.get_session_info()
                }
                
                # Save export file
                export_filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                export_path = self.file_handler.write_json(export_filename, export_data)
                
                st.success(f"Results exported to: {export_path}")
            else:
                st.warning("No results to export")
        except Exception as e:
            logger.error(f"Failed to export results: {e}")
            st.error(f"Failed to export results: {e}")


def main():
    """Main application entry point."""
    try:
        app = StreamlitApp()
        app.run()
    except Exception as e:
        logger.error(f"Application failed to start: {e}")
        st.error(f"Application failed to start: {e}")


if __name__ == "__main__":
    main()