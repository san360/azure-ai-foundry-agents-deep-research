"""Security validation and sanitization utilities."""

import re
import html
from pathlib import Path
from typing import Any, Union
import logging

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


def validate_connection_string(connection_string: str) -> None:
    """Validate Azure AI project connection string format."""
    if not connection_string or not isinstance(connection_string, str):
        raise ValidationError("Connection string must be a non-empty string")
    
    if len(connection_string.strip()) == 0:
        raise ValidationError("Connection string cannot be empty or whitespace only")
    
    # Basic format validation for Azure connection strings
    if not connection_string.startswith("https://"):
        raise ValidationError("Connection string must start with https://")
    
    # Check for required components (basic validation)
    if ".api.azureml.ms" not in connection_string:
        raise ValidationError("Connection string must contain Azure ML API domain")


def validate_project_name(project_name: str) -> None:
    """Validate Azure AI project name."""
    if not project_name or not isinstance(project_name, str):
        raise ValidationError("Project name must be a non-empty string")
    
    project_name = project_name.strip()
    if len(project_name) == 0:
        raise ValidationError("Project name cannot be empty or whitespace only")
    
    # Azure project name constraints
    if len(project_name) > 255:
        raise ValidationError("Project name cannot exceed 255 characters")
    
    # Check for valid characters (alphanumeric, hyphens, underscores)
    if not re.match(r'^[a-zA-Z0-9_-]+$', project_name):
        raise ValidationError("Project name can only contain alphanumeric characters, hyphens, and underscores")


def validate_model_name(model_name: str) -> None:
    """Validate Azure AI model name."""
    if not model_name or not isinstance(model_name, str):
        raise ValidationError("Model name must be a non-empty string")
    
    model_name = model_name.strip()
    if len(model_name) == 0:
        raise ValidationError("Model name cannot be empty or whitespace only")
    
    # Model name constraints
    if len(model_name) > 100:
        raise ValidationError("Model name cannot exceed 100 characters")
    
    # Check for valid characters
    if not re.match(r'^[a-zA-Z0-9_.-]+$', model_name):
        raise ValidationError("Model name can only contain alphanumeric characters, dots, hyphens, and underscores")


def validate_research_query(query: str, max_length: int = 10000) -> str:
    """Validate and sanitize research query input."""
    if not query or not isinstance(query, str):
        raise ValidationError("Research query must be a non-empty string")
    
    query = query.strip()
    if len(query) == 0:
        raise ValidationError("Research query cannot be empty or whitespace only")
    
    if len(query) > max_length:
        raise ValidationError(f"Research query cannot exceed {max_length} characters")
    
    # Remove potentially harmful characters
    sanitized_query = re.sub(r'[<>\"\'&]', '', query)
    
    # Check for minimal content after sanitization
    if len(sanitized_query.strip()) < 3:
        raise ValidationError("Research query too short after sanitization")
    
    return sanitized_query


def sanitize_file_path(file_path: str) -> str:
    """Sanitize file path to prevent directory traversal attacks."""
    if not file_path or not isinstance(file_path, str):
        raise ValidationError("File path must be a non-empty string")
    
    # Check for directory traversal attempts before normalization
    if ".." in file_path or file_path.startswith("/"):
        raise ValidationError("File path contains invalid directory traversal")
    
    # Normalize path but don't resolve relative paths to absolute
    try:
        # Use normpath instead of resolve to preserve relative paths
        path = Path(file_path)
        if path.is_absolute():
            # Only resolve absolute paths
            normalized_path = str(path.resolve())
        else:
            # Keep relative paths as relative, just normalize them
            normalized_path = str(Path(file_path).as_posix())
            # Convert back to platform-specific path separators
            normalized_path = str(Path(normalized_path))
    except (OSError, ValueError) as e:
        raise ValidationError(f"Invalid file path: {e}")
    
    # For absolute paths, ensure they don't access system directories
    if Path(normalized_path).is_absolute():
        forbidden_prefixes = [
            "C:\\Windows", "C:\\System32", "/etc", "/proc", "/sys", "/root"
        ]
        
        for prefix in forbidden_prefixes:
            if normalized_path.startswith(prefix):
                raise ValidationError(f"Access to system directory not allowed: {prefix}")
    
    return normalized_path


def validate_file_extension(file_path: str, allowed_extensions: tuple = (".json", ".txt", ".md")) -> None:
    """Validate file extension against allowed list."""
    if not file_path:
        raise ValidationError("File path cannot be empty")
    
    path = Path(file_path)
    extension = path.suffix.lower()
    
    if extension not in allowed_extensions:
        raise ValidationError(f"File extension '{extension}' not allowed. Allowed: {allowed_extensions}")


def sanitize_html_output(content: str) -> str:
    """Sanitize HTML content to prevent XSS attacks."""
    if not isinstance(content, str):
        return str(content)
    
    # HTML escape the content
    sanitized = html.escape(content)
    
    # Remove any remaining script tags or javascript
    sanitized = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
    sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'on\w+\s*=', '', sanitized, flags=re.IGNORECASE)
    
    return sanitized


def validate_json_structure(data: Any, required_fields: list = None) -> None:
    """Validate JSON data structure."""
    if not isinstance(data, dict):
        raise ValidationError("Data must be a JSON object (dictionary)")
    
    if required_fields:
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValidationError(f"Missing required fields: {missing_fields}")


def validate_file_size(file_path: Union[str, Path], max_size_mb: int = 50) -> None:
    """Validate file size doesn't exceed maximum."""
    try:
        path = Path(file_path)
        if not path.exists():
            raise ValidationError(f"File does not exist: {file_path}")
        
        file_size_mb = path.stat().st_size / (1024 * 1024)
        if file_size_mb > max_size_mb:
            raise ValidationError(f"File size ({file_size_mb:.2f} MB) exceeds maximum ({max_size_mb} MB)")
            
    except OSError as e:
        raise ValidationError(f"Error checking file size: {e}")


def sanitize_log_entry(entry: dict) -> dict:
    """Sanitize log entry data for safe storage."""
    sanitized = {}
    
    for key, value in entry.items():
        # Sanitize key
        clean_key = re.sub(r'[^a-zA-Z0-9_]', '_', str(key))
        
        # Sanitize value
        if isinstance(value, str):
            clean_value = sanitize_html_output(value)
            # Truncate extremely long values
            if len(clean_value) > 10000:
                clean_value = clean_value[:10000] + "... [TRUNCATED]"
        elif isinstance(value, (dict, list)):
            # Recursively sanitize nested structures
            clean_value = _sanitize_nested_structure(value)
        else:
            clean_value = value
        
        sanitized[clean_key] = clean_value
    
    return sanitized


def _sanitize_nested_structure(data: Union[dict, list]) -> Union[dict, list]:
    """Recursively sanitize nested data structures."""
    if isinstance(data, dict):
        return {
            re.sub(r'[^a-zA-Z0-9_]', '_', str(k)): 
            sanitize_html_output(str(v)) if isinstance(v, str) else v
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [
            sanitize_html_output(str(item)) if isinstance(item, str) else item
            for item in data
        ]
    else:
        return data