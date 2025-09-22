"""Configuration management module with security and validation."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Any
import json
import logging

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load .env file from current directory or parent directory
    env_file = Path(".env")
    if not env_file.exists():
        env_file = Path("../.env")
    if env_file.exists():
        load_dotenv(env_file)
        logging.getLogger(__name__).info(f"Loaded environment variables from {env_file.absolute()}")
    else:
        logging.getLogger(__name__).warning("No .env file found")
except ImportError:
    logging.getLogger(__name__).warning("python-dotenv not available, skipping .env file loading")

from azure_ai_research.security.validation import (
    validate_project_name,
    validate_model_name,
    sanitize_file_path,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AzureConfig:
    """Azure-specific configuration with validation."""
    
    project_endpoint: str
    project_name: str
    model_deployment_name: str = "gpt-4o"
    deep_research_model_deployment_name: str = "o3-deep-research"
    bing_resource_name: str = "bingsearch"
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.project_endpoint:
            raise ValueError("project_endpoint is required")
        if not self.project_endpoint.startswith(("http://", "https://")):
            raise ValueError("project_endpoint must be a valid URL")
        validate_project_name(self.project_name)
        validate_model_name(self.model_deployment_name)
        validate_model_name(self.deep_research_model_deployment_name)
    
    def validate(self) -> None:
        """Validate the Azure configuration."""
        # This method is called by other parts of the code
        # The actual validation is done in __post_init__, but we provide this for compatibility
        pass


@dataclass(frozen=True)
class LoggingConfig:
    """Logging configuration with file path validation."""
    
    level: str = "INFO"
    log_directory: Path = field(default_factory=lambda: Path("logs"))
    file_prefix: str = "research_log"
    max_file_size_mb: int = 10
    backup_count: int = 5
    
    def __post_init__(self) -> None:
        """Validate and sanitize logging configuration."""
        if self.level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError(f"Invalid log level: {self.level}")
        
        # Sanitize and validate log directory
        sanitized_path = sanitize_file_path(str(self.log_directory))
        object.__setattr__(self, "log_directory", Path(sanitized_path))
        
        if self.max_file_size_mb <= 0:
            raise ValueError("max_file_size_mb must be positive")
        
        if self.backup_count < 0:
            raise ValueError("backup_count must be non-negative")


@dataclass(frozen=True)
class SecurityConfig:
    """Security-related configuration."""
    
    max_input_length: int = 10000
    allowed_file_extensions: tuple = field(default_factory=lambda: (".json", ".txt", ".md"))
    max_file_size_mb: int = 50
    sanitize_output: bool = True
    enable_tracing: bool = True
    
    def __post_init__(self) -> None:
        """Validate security configuration."""
        if self.max_input_length <= 0:
            raise ValueError("max_input_length must be positive")
        
        if self.max_file_size_mb <= 0:
            raise ValueError("max_file_size_mb must be positive")


@dataclass(frozen=True)
class AppConfig:
    """Application configuration with comprehensive validation."""
    
    azure: AzureConfig
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    
    @classmethod
    def from_environment(cls) -> "AppConfig":
        """Create configuration from environment variables with validation."""
        try:
            # Load required environment variables (using existing .env variable names)
            project_endpoint = os.getenv("PROJECT_ENDPOINT")
            if not project_endpoint:
                raise ValueError("PROJECT_ENDPOINT environment variable is required")
            
            # Extract project name from endpoint URL for compatibility
            # PROJECT_ENDPOINT format: https://project-name.services.ai.azure.com/api/projects/project_name
            try:
                import urllib.parse
                parsed = urllib.parse.urlparse(project_endpoint)
                project_name = parsed.hostname.split('.')[0] if parsed.hostname else "default-project"
            except:
                project_name = "default-project"
            
            # Use the Deep Research model name from existing .env
            model_name = os.getenv("DEEP_RESEARCH_MODEL_DEPLOYMENT_NAME", "o3-deep-research")
            
            # Get other environment variables
            model_deployment_name = os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4o")
            bing_resource_name = os.getenv("BING_RESOURCE_NAME", "bingsearch")
            
            # Create Azure configuration
            azure_config = AzureConfig(
                project_endpoint=project_endpoint,
                project_name=project_name,
                model_deployment_name=model_deployment_name,
                deep_research_model_deployment_name=model_name,
                bing_resource_name=bing_resource_name
            )
            
            # Create logging configuration from environment
            log_level = os.getenv("LOG_LEVEL", "INFO").upper()
            log_dir = Path(os.getenv("LOG_DIRECTORY", "logs"))
            
            logging_config = LoggingConfig(
                level=log_level,
                log_directory=log_dir,
                max_file_size_mb=int(os.getenv("MAX_LOG_FILE_SIZE_MB", "10")),
                backup_count=int(os.getenv("LOG_BACKUP_COUNT", "5"))
            )
            
            # Create security configuration from environment
            security_config = SecurityConfig(
                max_input_length=int(os.getenv("MAX_INPUT_LENGTH", "10000")),
                max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "50")),
                sanitize_output=os.getenv("SANITIZE_OUTPUT", "true").lower() == "true",
                enable_tracing=os.getenv("ENABLE_TRACING", "true").lower() == "true"
            )
            
            return cls(
                azure=azure_config,
                logging=logging_config,
                security=security_config
            )
            
        except (ValueError, TypeError) as e:
            logger.error(f"Configuration error: {e}")
            raise
    
    @classmethod
    def from_file(cls, config_path: Path) -> "AppConfig":
        """Load configuration from JSON file with validation."""
        try:
            sanitized_path = sanitize_file_path(str(config_path))
            config_file = Path(sanitized_path)
            
            if not config_file.exists():
                raise FileNotFoundError(f"Configuration file not found: {config_file}")
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Validate JSON structure
            if not isinstance(config_data, dict):
                raise ValueError("Configuration file must contain a JSON object")
            
            azure_data = config_data.get("azure", {})
            logging_data = config_data.get("logging", {})
            security_data = config_data.get("security", {})
            
            azure_config = AzureConfig(**azure_data)
            logging_config = LoggingConfig(**logging_data)
            security_config = SecurityConfig(**security_data)
            
            return cls(
                azure=azure_config,
                logging=logging_config,
                security=security_config
            )
            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Failed to load configuration from {config_path}: {e}")
            raise
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for serialization."""
        return {
            "azure": {
                "project_endpoint": "***REDACTED***",  # Never expose endpoint
                "project_name": self.azure.project_name,
                "model_deployment_name": self.azure.model_deployment_name,
                "deep_research_model_deployment_name": self.azure.deep_research_model_deployment_name,
                "bing_resource_name": self.azure.bing_resource_name
            },
            "logging": {
                "level": self.logging.level,
                "log_directory": str(self.logging.log_directory),
                "file_prefix": self.logging.file_prefix,
                "max_file_size_mb": self.logging.max_file_size_mb,
                "backup_count": self.logging.backup_count
            },
            "security": {
                "max_input_length": self.security.max_input_length,
                "allowed_file_extensions": list(self.security.allowed_file_extensions),
                "max_file_size_mb": self.security.max_file_size_mb,
                "sanitize_output": self.security.sanitize_output,
                "enable_tracing": self.security.enable_tracing
            }
        }
    
    def validate(self) -> None:
        """Perform comprehensive validation of the configuration."""
        try:
            # All validation is done in __post_init__ methods
            # This method can be extended for cross-field validation
            logger.info("Configuration validation passed")
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            raise


def get_default_config() -> AppConfig:
    """Get default application configuration from environment."""
    return AppConfig.from_environment()