"""Infrastructure package for core application services."""

from azure_ai_research.infrastructure.config import AppConfig, get_default_config

__all__ = ["AppConfig", "get_default_config"]