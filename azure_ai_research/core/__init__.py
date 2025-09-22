"""Core module for Azure AI research functionality."""

from azure_ai_research.core.research import ResearchService, ResearchRequest, ResearchResult
from azure_ai_research.core.citations import CitationProcessor, Citation
from azure_ai_research.core.telemetry import TracingService

__all__ = [
    "ResearchService", 
    "ResearchRequest", 
    "ResearchResult",
    "CitationProcessor", 
    "Citation",
    "TracingService"
]