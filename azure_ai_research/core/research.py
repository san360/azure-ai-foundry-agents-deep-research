"""Core research functionality with proper separation of concerns."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, Protocol, runtime_checkable
from dataclasses import dataclass
import threading
from concurrent.futures import ThreadPoolExecutor, Future
import json

from azure.ai.projects import AIProjectClient
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import DeepResearchTool, MessageRole, ThreadMessage

from azure_ai_research.infrastructure.config import AppConfig
from azure_ai_research.infrastructure.azure_client import AzureClientProvider, AzureClientError
from azure_ai_research.infrastructure.file_system import SecureFileHandler, FileSystemError
from azure_ai_research.core.citations import CitationProcessor
from azure_ai_research.core.telemetry import TracingService
from azure_ai_research.security.validation import validate_research_query, ValidationError

logger = logging.getLogger(__name__)


@runtime_checkable
class ProgressCallback(Protocol):
    """Protocol for progress callback functions."""
    
    def __call__(self, message: str, progress: float = 0.0, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Progress callback signature."""
        ...


@dataclass(frozen=True)
class ResearchRequest:
    """Immutable research request with validation."""
    
    query: str
    max_iterations: int = 10
    timeout_seconds: int = 300
    enable_citations: bool = True
    
    def __post_init__(self) -> None:
        """Validate research request parameters."""
        if self.max_iterations <= 0 or self.max_iterations > 50:
            raise ValueError("max_iterations must be between 1 and 50")
        
        if self.timeout_seconds <= 0 or self.timeout_seconds > 3600:
            raise ValueError("timeout_seconds must be between 1 and 3600")
        
        # Validate and sanitize query
        object.__setattr__(self, 'query', validate_research_query(self.query))


@dataclass
class ResearchResult:
    """Research result with metadata and citations."""
    
    content: str
    citations: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    execution_time_seconds: float
    success: bool
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "content": self.content,
            "citations": self.citations,
            "metadata": self.metadata,
            "execution_time_seconds": self.execution_time_seconds,
            "success": self.success,
            "error_message": self.error_message,
            "timestamp": datetime.now().isoformat()
        }


class ResearchService:
    """Main service for conducting Azure AI research with proper architecture."""
    
    def __init__(self, config: AppConfig) -> None:
        """Initialize research service with dependencies."""
        self.config = config
        self.azure_client_provider = AzureClientProvider(config.azure)
        self.file_handler = SecureFileHandler(
            config.logging.log_directory,
            config.security.allowed_file_extensions
        )
        self.citation_processor = CitationProcessor()
        self.tracing_service = TracingService(config.security.enable_tracing)
        
        # Thread safety
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="research")
        
        logger.info("ResearchService initialized successfully")
    
    def conduct_research_async(self, 
                             request: ResearchRequest,
                             progress_callback: Optional[ProgressCallback] = None) -> Future[ResearchResult]:
        """Conduct research asynchronously with progress tracking."""
        with self.tracing_service.trace_operation("conduct_research_async"):
            try:
                # Validate request
                if not isinstance(request, ResearchRequest):
                    raise ValueError("Invalid research request type")
                
                # Submit research task to executor
                future = self._executor.submit(
                    self._conduct_research_sync,
                    request,
                    progress_callback
                )
                
                logger.info(f"Research task submitted asynchronously for query: {request.query[:100]}...")
                return future
                
            except Exception as e:
                logger.error(f"Failed to start async research: {e}")
                raise
    
    def conduct_research_sync(self, 
                            request: ResearchRequest,
                            progress_callback: Optional[ProgressCallback] = None) -> ResearchResult:
        """Conduct research synchronously."""
        return self._conduct_research_sync(request, progress_callback)
    
    def _conduct_research_sync(self, 
                             request: ResearchRequest,
                             progress_callback: Optional[ProgressCallback] = None) -> ResearchResult:
        """Internal synchronous research implementation."""
        start_time = datetime.now()
        
        with self.tracing_service.trace_operation("conduct_research") as span:
            try:
                span.set_attribute("query_length", len(request.query))
                span.set_attribute("max_iterations", request.max_iterations)
                
                # Initialize progress tracking
                if progress_callback:
                    progress_callback("Starting research...", 0.0, {"stage": "initialization"})
                
                # Get Azure client
                with self.azure_client_provider.get_client_context() as client:
                    # Create or get research agent
                    agent = self._get_research_agent(client)
                    span.set_attribute("agent_id", agent.id)
                    
                    if progress_callback:
                        progress_callback("Agent ready, creating thread...", 0.1, {"agent_id": agent.id})
                    
                    # Create thread for research
                    thread = self._create_research_thread(client, request.query)
                    span.set_attribute("thread_id", thread.id)
                    
                    if progress_callback:
                        progress_callback("Thread created, starting research...", 0.2, {"thread_id": thread.id})
                    
                    # Execute research
                    result_content = self._execute_research(
                        client, agent, thread, request, progress_callback
                    )
                    
                    if progress_callback:
                        progress_callback("Research completed, processing results...", 0.9)
                    
                    # Process citations if enabled
                    citations = []
                    if request.enable_citations:
                        citations = self.citation_processor.extract_citations(result_content)
                        result_content = self.citation_processor.convert_to_superscript(result_content)
                    
                    # Calculate execution time
                    execution_time = (datetime.now() - start_time).total_seconds()
                    
                    # Create result
                    result = ResearchResult(
                        content=result_content,
                        citations=citations,
                        metadata={
                            "agent_id": agent.id,
                            "thread_id": thread.id,
                            "query": request.query,
                            "max_iterations": request.max_iterations,
                            "timestamp": start_time.isoformat()
                        },
                        execution_time_seconds=execution_time,
                        success=True
                    )
                    
                    span.set_attribute("success", True)
                    span.set_attribute("execution_time", execution_time)
                    
                    if progress_callback:
                        progress_callback("Research completed successfully!", 1.0, {"success": True})
                    
                    logger.info(f"Research completed successfully in {execution_time:.2f} seconds")
                    return result
                    
            except Exception as e:
                execution_time = (datetime.now() - start_time).total_seconds()
                error_msg = f"Research failed: {str(e)}"
                
                span.set_attribute("success", False)
                span.set_attribute("error", error_msg)
                
                logger.error(error_msg)
                
                if progress_callback:
                    progress_callback(f"Research failed: {str(e)}", 1.0, {"success": False, "error": str(e)})
                
                return ResearchResult(
                    content="",
                    citations=[],
                    metadata={"query": request.query, "timestamp": start_time.isoformat()},
                    execution_time_seconds=execution_time,
                    success=False,
                    error_message=error_msg
                )
    
    def _get_research_agent(self, client: AIProjectClient) -> Any:
        """Get or create research agent."""
        try:
            # Try to find existing deep research agent
            agents = client.agents.list_agents()
            for agent in agents:
                if "deep-research" in agent.name.lower():
                    logger.info(f"Using existing research agent: {agent.name}")
                    return agent
            
            # Create new research agent if none found
            logger.info("Creating new deep research agent")
            
            # Get Bing connection ID
            conn_id = client.connections.get(name=self.config.azure.bing_resource_name).id
            logger.info(f"Using Bing connection ID: {conn_id}")
            
            # Initialize Deep Research tool with Bing Connection ID and Deep Research model
            deep_research_tool = DeepResearchTool(
                bing_grounding_connection_id=conn_id,
                deep_research_model=self.config.azure.deep_research_model_deployment_name,
            )
            
            agent = client.agents.create_agent(
                model=self.config.azure.model_deployment_name,  # Use the GPT model for agent creation
                name="Deep Research Agent",
                instructions="You are a helpful research assistant that provides comprehensive, well-researched answers with proper citations.",
                tools=deep_research_tool.definitions,
            )
            
            logger.info(f"Created new deep research agent: {agent.id}")
            return agent
            
        except Exception as e:
            logger.error(f"Failed to get research agent: {e}")
            raise AzureClientError(f"Failed to get research agent: {e}")
    
    def _create_research_thread(self, client: AIProjectClient, query: str) -> Any:
        """Create a new research thread."""
        try:
            # Create thread using the new API
            thread = client.agents.threads.create()
            
            # Add initial message using the new API
            message = client.agents.messages.create(
                thread_id=thread.id,
                role="user",
                content=query
            )
            
            logger.debug(f"Research thread created: {thread.id}")
            return thread
            
        except Exception as e:
            logger.error(f"Failed to create research thread: {e}")
            raise AzureClientError(f"Failed to create research thread: {e}")
    
    def _execute_research(self, 
                         client: AIProjectClient,
                         agent: Any,
                         thread: Any,
                         request: ResearchRequest,
                         progress_callback: Optional[ProgressCallback] = None) -> str:
        """Execute research with the agent."""
        try:
            # Start the research run using the new API
            run = client.agents.runs.create(
                thread_id=thread.id,
                agent_id=agent.id
            )
            
            logger.debug(f"Research run started: {run.id}")
            
            # Poll for completion with progress updates
            iteration = 0
            while iteration < request.max_iterations:
                run = client.agents.runs.get(thread_id=thread.id, run_id=run.id)
                
                if run.status == "completed":
                    break
                elif run.status in ["failed", "cancelled", "expired"]:
                    raise AzureClientError(f"Research run {run.status}: {run.last_error}")
                
                if progress_callback:
                    progress = 0.2 + (iteration / request.max_iterations) * 0.7
                    progress_callback(
                        f"Research in progress... (iteration {iteration + 1})",
                        progress,
                        {"iteration": iteration + 1, "status": run.status}
                    )
                
                iteration += 1
                
                # Brief pause before next poll
                import time
                time.sleep(2)
            
            if run.status != "completed":
                raise AzureClientError(f"Research did not complete within {request.max_iterations} iterations")
            
            # Get the latest messages
            messages = client.agents.messages.list(thread_id=thread.id)
            
            # Find the assistant's response
            for message in messages:
                if message.role == "assistant":
                    content = ""
                    for content_item in message.content:
                        if hasattr(content_item, 'text'):
                            content += content_item.text.value
                    
                    if content.strip():
                        logger.debug("Research content retrieved successfully")
                        return content.strip()
            
            raise AzureClientError("No research content found in agent response")
            
        except Exception as e:
            logger.error(f"Failed to execute research: {e}")
            raise AzureClientError(f"Failed to execute research: {e}")
    
    def save_research_log(self, result: ResearchResult, log_filename: Optional[str] = None) -> str:
        """Save research result to log file."""
        try:
            if not log_filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                log_filename = f"research_log_{timestamp}.json"
            
            log_data = result.to_dict()
            
            # Save with atomic write
            saved_path = self.file_handler.write_json(log_filename, log_data, sanitize=True, atomic=True)
            
            logger.info(f"Research log saved: {saved_path}")
            return str(saved_path)
            
        except Exception as e:
            logger.error(f"Failed to save research log: {e}")
            raise FileSystemError(f"Failed to save research log: {e}")
    
    def load_research_logs(self, pattern: str = "research_log_*.json") -> List[Dict[str, Any]]:
        """Load research logs from files."""
        try:
            log_files = self.file_handler.list_files(pattern)
            logs = []
            
            for log_file in sorted(log_files, reverse=True):  # Most recent first
                try:
                    log_data = self.file_handler.read_json(log_file)
                    logs.append(log_data)
                except Exception as e:
                    logger.warning(f"Failed to load log file {log_file}: {e}")
                    continue
            
            logger.info(f"Loaded {len(logs)} research logs")
            return logs
            
        except Exception as e:
            logger.error(f"Failed to load research logs: {e}")
            raise FileSystemError(f"Failed to load research logs: {e}")
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get service status for health checks."""
        try:
            azure_info = self.azure_client_provider.get_connection_info()
            
            return {
                "service": "ResearchService",
                "status": "healthy",
                "azure_connection": azure_info,
                "config": {
                    "model_name": self.config.azure.deep_research_model_deployment_name,
                    "log_directory": str(self.config.logging.log_directory),
                    "tracing_enabled": self.config.security.enable_tracing
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Service status check failed: {e}")
            return {
                "service": "ResearchService",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def cleanup(self) -> None:
        """Clean up resources."""
        try:
            self._executor.shutdown(wait=True, timeout=30)
            self.tracing_service.cleanup()
            logger.info("ResearchService cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def create_research_service(config: AppConfig) -> ResearchService:
    """Factory function to create research service."""
    return ResearchService(config)