"""Azure client management with secure connection handling."""

import logging
from typing import Optional, Protocol, runtime_checkable
from contextlib import contextmanager
from azure.ai.projects import AIProjectClient
from azure.core.exceptions import (
    AzureError, 
    ClientAuthenticationError, 
    ResourceNotFoundError,
    ServiceRequestError
)

from azure_ai_research.infrastructure.config import AzureConfig
from azure_ai_research.security.validation import ValidationError

logger = logging.getLogger(__name__)


@runtime_checkable
class IAzureClientProvider(Protocol):
    """Protocol for Azure client providers."""
    
    def get_client(self) -> AIProjectClient:
        """Get an Azure AI Project client instance."""
        ...
    
    def validate_connection(self) -> bool:
        """Validate the Azure connection."""
        ...


class AzureClientError(Exception):
    """Custom exception for Azure client operations."""
    pass


class AzureClientProvider:
    """Secure Azure AI Project client provider with connection management."""
    
    def __init__(self, config: AzureConfig) -> None:
        """Initialize client provider with validated configuration."""
        self._config = config
        self._client: Optional[AIProjectClient] = None
        self._connection_validated = False
        
        logger.info(f"Initializing Azure client for project: {config.project_name}")
    
    def get_client(self) -> AIProjectClient:
        """Get or create Azure AI Project client with connection validation."""
        if self._client is None:
            try:
                self._client = self._create_client()
                logger.info("Azure AI Project client created successfully")
            except Exception as e:
                logger.error(f"Failed to create Azure client: {e}")
                raise AzureClientError(f"Failed to create Azure client: {e}") from e
        
        return self._client
    
    def _create_client(self) -> AIProjectClient:
        """Create new Azure AI Project client instance."""
        try:
            # Validate configuration before creating client
            self._config.validate()
            
            from azure.identity import DefaultAzureCredential
            
            logger.info(f"Creating Azure AI Project client with endpoint: {self._config.project_endpoint}")
            client = AIProjectClient(
                endpoint=self._config.project_endpoint,
                credential=DefaultAzureCredential()
            )
            
            # Verify client can connect
            if not self._test_connection(client):
                raise AzureClientError("Failed to establish connection to Azure AI Project")
            
            return client
            
        except ClientAuthenticationError as e:
            logger.error(f"Azure authentication failed: {e}")
            raise AzureClientError("Azure authentication failed. Check authentication credentials.") from e
        except ResourceNotFoundError as e:
            logger.error(f"Azure resource not found: {e}")
            raise AzureClientError("Azure project not found. Check project endpoint.") from e
        except Exception as e:
            logger.error(f"Unexpected error creating Azure client: {type(e).__name__}: {e}")
            raise AzureClientError(f"Failed to create Azure client: {e}") from e
        except ServiceRequestError as e:
            logger.error(f"Azure service request failed: {e}")
            raise AzureClientError("Azure service request failed. Check network connectivity.") from e
        except AzureError as e:
            logger.error(f"Azure error: {e}")
            raise AzureClientError(f"Azure error: {e}") from e
        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            raise AzureClientError(f"Configuration validation failed: {e}") from e
    
    def _test_connection(self, client: AIProjectClient) -> bool:
        """Test Azure client connection."""
        try:
            # Try to list agents to verify connection
            logger.info(f"Testing connection to Azure AI Project...")
            agents = client.agents.list_agents()
            agent_count = len(list(agents))
            logger.info(f"Connection test successful. Found {agent_count} agents.")
            self._connection_validated = True
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {type(e).__name__}: {e}")
            logger.error(f"Endpoint: {self._config.project_endpoint}")
            return False
    
    def validate_connection(self) -> bool:
        """Validate current Azure connection."""
        if not self._connection_validated and self._client:
            return self._test_connection(self._client)
        return self._connection_validated
    
    @contextmanager
    def get_client_context(self):
        """Context manager for Azure client operations."""
        client = None
        try:
            client = self.get_client()
            if not self.validate_connection():
                raise AzureClientError("Azure connection validation failed")
            
            yield client
            
        except AzureClientError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in Azure client context: {e}")
            raise AzureClientError(f"Unexpected error: {e}") from e
        finally:
            # Clean up if needed (Azure client handles connection pooling)
            if client:
                logger.debug("Azure client context closed")
    
    def refresh_client(self) -> None:
        """Refresh the Azure client connection."""
        logger.info("Refreshing Azure client connection")
        self._client = None
        self._connection_validated = False
        
        # Force recreation on next get_client() call
        try:
            self.get_client()
            logger.info("Azure client refreshed successfully")
        except Exception as e:
            logger.error(f"Failed to refresh Azure client: {e}")
            raise
    
    def get_connection_info(self) -> dict:
        """Get sanitized connection information for logging."""
        return {
            "project_name": self._config.project_name,
            "model_name": self._config.deep_research_model_deployment_name,
            "connection_validated": self._connection_validated,
            "client_created": self._client is not None
        }


def create_azure_client_provider(config: AzureConfig) -> AzureClientProvider:
    """Factory function to create Azure client provider."""
    return AzureClientProvider(config)