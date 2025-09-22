"""Azure AI Foundry Agents Deep Research Package.

A secure, maintainable, and well-architected package for performing
deep research using Azure AI Agents with proper separation of concerns,
comprehensive security, and robust error handling.
"""

__version__ = "0.2.0"
__author__ = "Microsoft Corporation"
__license__ = "MIT"

from azure_ai_research.core.research import ResearchService
from azure_ai_research.infrastructure.config import AppConfig

__all__ = ["ResearchService", "AppConfig"]