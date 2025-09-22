"""Secure file system operations with validation and safety checks."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from contextlib import contextmanager
import tempfile
import shutil

from azure_ai_research.security.validation import (
    sanitize_file_path,
    validate_file_extension,
    validate_file_size,
    validate_json_structure,
    sanitize_log_entry,
    ValidationError,
)

logger = logging.getLogger(__name__)


class FileSystemError(Exception):
    """Custom exception for file system operations."""
    pass


class SecureFileHandler:
    """Secure file operations with validation and safety checks."""
    
    def __init__(self, base_directory: Union[str, Path], allowed_extensions: tuple = (".json", ".txt", ".md")):
        """Initialize secure file handler with base directory validation."""
        sanitized_path = sanitize_file_path(str(base_directory))
        self.base_directory = Path(sanitized_path).resolve()
        self.allowed_extensions = allowed_extensions
        
        # Ensure base directory exists and is secure
        self._ensure_secure_directory()
        
        logger.info(f"SecureFileHandler initialized for directory: {self.base_directory}")
    
    def _ensure_secure_directory(self) -> None:
        """Ensure base directory exists and has proper permissions."""
        try:
            self.base_directory.mkdir(parents=True, exist_ok=True)
            
            # Check directory permissions (read/write for owner)
            if not self.base_directory.is_dir():
                raise FileSystemError(f"Base directory is not a directory: {self.base_directory}")
            
            # Test write permissions
            test_file = self.base_directory / ".write_test"
            try:
                test_file.write_text("test")
                test_file.unlink()
            except (OSError, PermissionError) as e:
                raise FileSystemError(f"No write permission in directory {self.base_directory}: {e}")
                
        except Exception as e:
            logger.error(f"Failed to ensure secure directory: {e}")
            raise FileSystemError(f"Failed to ensure secure directory: {e}") from e
    
    def _validate_file_path(self, file_path: Union[str, Path]) -> Path:
        """Validate and resolve file path within base directory."""
        try:
            # Sanitize the path
            sanitized_path = sanitize_file_path(str(file_path))
            resolved_path = Path(sanitized_path)
            
            # If relative path, make it relative to base directory
            if not resolved_path.is_absolute():
                resolved_path = self.base_directory / resolved_path
            else:
                resolved_path = resolved_path.resolve()
            
            # Ensure path is within base directory (prevent directory traversal)
            try:
                resolved_path.relative_to(self.base_directory.resolve())
            except ValueError:
                raise ValidationError(f"File path outside base directory: {resolved_path}")
            
            # Validate file extension
            validate_file_extension(str(resolved_path), self.allowed_extensions)
            
            return resolved_path
            
        except Exception as e:
            logger.error(f"File path validation failed for {file_path}: {e}")
            raise FileSystemError(f"Invalid file path: {e}") from e
    
    def write_json(self, file_path: Union[str, Path], data: Dict[str, Any], 
                   sanitize: bool = True, atomic: bool = True) -> Path:
        """Write JSON data to file with validation and optional sanitization."""
        try:
            validated_path = self._validate_file_path(file_path)
            
            # Sanitize data if requested
            if sanitize:
                data = sanitize_log_entry(data)
            
            # Validate JSON structure
            validate_json_structure(data)
            
            # Atomic write using temporary file
            if atomic:
                return self._atomic_write_json(validated_path, data)
            else:
                return self._direct_write_json(validated_path, data)
                
        except Exception as e:
            logger.error(f"Failed to write JSON to {file_path}: {e}")
            raise FileSystemError(f"Failed to write JSON: {e}") from e
    
    def _atomic_write_json(self, file_path: Path, data: Dict[str, Any]) -> Path:
        """Atomically write JSON data using temporary file."""
        temp_file = None
        try:
            # Create temporary file in same directory
            with tempfile.NamedTemporaryFile(
                mode='w', 
                suffix='.tmp',
                dir=file_path.parent,
                delete=False,
                encoding='utf-8'
            ) as temp_file:
                json.dump(data, temp_file, indent=2, ensure_ascii=False)
                temp_file_path = Path(temp_file.name)
            
            # Atomically replace original file
            shutil.move(str(temp_file_path), str(file_path))
            
            logger.debug(f"JSON written atomically to: {file_path}")
            return file_path
            
        except Exception as e:
            # Clean up temporary file if it exists
            if temp_file and Path(temp_file.name).exists():
                try:
                    Path(temp_file.name).unlink()
                except OSError:
                    pass
            raise
    
    def _direct_write_json(self, file_path: Path, data: Dict[str, Any]) -> Path:
        """Directly write JSON data to file."""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"JSON written directly to: {file_path}")
        return file_path
    
    def write_text(self, file_path: Union[str, Path], content: str, 
                   encoding: str = 'utf-8', atomic: bool = True) -> Path:
        """Write text content to file with validation."""
        try:
            validated_path = self._validate_file_path(file_path)
            
            # Ensure parent directory exists
            validated_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Atomic write using temporary file
            if atomic:
                return self._atomic_write_text(validated_path, content, encoding)
            else:
                return self._direct_write_text(validated_path, content, encoding)
                
        except Exception as e:
            logger.error(f"Failed to write text to {file_path}: {e}")
            raise FileSystemError(f"Failed to write text: {e}") from e
    
    def _atomic_write_text(self, file_path: Path, content: str, encoding: str) -> Path:
        """Atomically write text content using temporary file."""
        temp_file = None
        try:
            # Create temporary file in same directory
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding=encoding,
                dir=file_path.parent,
                prefix=f".tmp_{file_path.stem}_",
                suffix=f"_{file_path.suffix}",
                delete=False
            ) as tf:
                tf.write(content)
                tf.flush()
                temp_file = Path(tf.name)
            
            # Atomic move
            shutil.move(str(temp_file), str(file_path))
            
            logger.debug(f"Text written atomically to: {file_path}")
            return file_path
            
        except Exception as e:
            # Clean up temp file on error
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
            raise
    
    def _direct_write_text(self, file_path: Path, content: str, encoding: str) -> Path:
        """Directly write text content to file."""
        with open(file_path, 'w', encoding=encoding) as f:
            f.write(content)
        
        logger.debug(f"Text written directly to: {file_path}")
        return file_path
    
    def read_json(self, file_path: Union[str, Path], validate_size: bool = True) -> Dict[str, Any]:
        """Read and validate JSON data from file."""
        try:
            validated_path = self._validate_file_path(file_path)
            
            if not validated_path.exists():
                raise FileNotFoundError(f"File not found: {validated_path}")
            
            # Validate file size if requested
            if validate_size:
                validate_file_size(validated_path, max_size_mb=50)
            
            with open(validated_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validate JSON structure
            validate_json_structure(data)
            
            logger.debug(f"JSON read successfully from: {validated_path}")
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in file {file_path}: {e}")
            raise FileSystemError(f"Invalid JSON: {e}") from e
        except Exception as e:
            logger.error(f"Failed to read JSON from {file_path}: {e}")
            raise FileSystemError(f"Failed to read JSON: {e}") from e
    
    def list_files(self, pattern: str = "*", max_files: int = 1000) -> List[Path]:
        """List files in base directory with pattern matching."""
        try:
            files = list(self.base_directory.glob(pattern))
            
            # Filter by allowed extensions and validate each file
            valid_files = []
            for file_path in files:
                if file_path.is_file():
                    try:
                        validate_file_extension(str(file_path), self.allowed_extensions)
                        valid_files.append(file_path)
                    except ValidationError:
                        continue  # Skip files with invalid extensions
            
            # Limit number of files returned
            if len(valid_files) > max_files:
                logger.warning(f"Too many files found ({len(valid_files)}), returning first {max_files}")
                valid_files = valid_files[:max_files]
            
            logger.debug(f"Found {len(valid_files)} valid files matching pattern: {pattern}")
            return valid_files
            
        except Exception as e:
            logger.error(f"Failed to list files with pattern {pattern}: {e}")
            raise FileSystemError(f"Failed to list files: {e}") from e
    
    def delete_file(self, file_path: Union[str, Path], force: bool = False) -> bool:
        """Safely delete a file with validation."""
        try:
            validated_path = self._validate_file_path(file_path)
            
            if not validated_path.exists():
                logger.warning(f"File does not exist for deletion: {validated_path}")
                return False
            
            if not force and validated_path.stat().st_size > 100 * 1024 * 1024:  # 100MB
                raise FileSystemError("File too large for deletion without force flag")
            
            validated_path.unlink()
            logger.info(f"File deleted successfully: {validated_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            raise FileSystemError(f"Failed to delete file: {e}") from e
    
    def get_file_info(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Get file information including size, modification time, etc."""
        try:
            validated_path = self._validate_file_path(file_path)
            
            if not validated_path.exists():
                raise FileNotFoundError(f"File not found: {validated_path}")
            
            stat = validated_path.stat()
            
            return {
                "path": str(validated_path),
                "size_bytes": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "is_file": validated_path.is_file(),
                "extension": validated_path.suffix,
                "name": validated_path.name
            }
            
        except Exception as e:
            logger.error(f"Failed to get file info for {file_path}: {e}")
            raise FileSystemError(f"Failed to get file info: {e}") from e
    
    @contextmanager
    def backup_context(self, file_path: Union[str, Path]):
        """Context manager for operations with automatic backup."""
        validated_path = self._validate_file_path(file_path)
        backup_path = None
        
        try:
            # Create backup if file exists
            if validated_path.exists():
                backup_path = validated_path.with_suffix(validated_path.suffix + '.backup')
                shutil.copy2(validated_path, backup_path)
                logger.debug(f"Backup created: {backup_path}")
            
            yield validated_path
            
            # Remove backup on success
            if backup_path and backup_path.exists():
                backup_path.unlink()
                logger.debug(f"Backup removed: {backup_path}")
                
        except Exception as e:
            # Restore from backup on failure
            if backup_path and backup_path.exists():
                try:
                    shutil.move(str(backup_path), str(validated_path))
                    logger.info(f"File restored from backup: {validated_path}")
                except Exception as restore_error:
                    logger.error(f"Failed to restore from backup: {restore_error}")
            raise


def create_secure_file_handler(base_directory: Union[str, Path], 
                             allowed_extensions: tuple = (".json", ".txt", ".md")) -> SecureFileHandler:
    """Factory function to create secure file handler."""
    return SecureFileHandler(base_directory, allowed_extensions)