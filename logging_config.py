#!/usr/bin/env python3
"""
Logging Configuration Module for MCP PostgreSQL Server

Provides centralized logging configuration based on environment variables:
- MCP_POSTGRESQL_LOG_FILE: Log file path (if not set, no file logging)
- MCP_POSTGRESQL_LOG_LEVEL: Log level (default: error)

@author sebcbi1
"""

import os
import logging
import sys
from pathlib import Path
from typing import Optional

try:
    from project_utils import get_project_path_as_path
except ImportError:
    # Fallback if project_utils is not available
    def get_project_path_as_path():
        return Path.cwd()

def _get_log_level(level_str: str) -> int:
    """Convert string log level to logging constant"""
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'WARN': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
        'FATAL': logging.CRITICAL
    }
    return level_map.get(level_str.upper(), logging.ERROR)

def setup_logging(logger_name: str = "mcp-postgresql") -> logging.Logger:
    """
    Setup logging based on environment variables.
    
    Args:
        logger_name: Name of the logger to create/configure
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(logger_name)
    
    # Prevent duplicate handlers if already configured
    if logger.hasHandlers():
        return logger
    
    # Get environment variables
    log_file = os.getenv('MCP_POSTGRESQL_LOG_FILE', '').strip()
    log_level_str = os.getenv('MCP_POSTGRESQL_LOG_LEVEL', 'error').strip()
    
    # Convert log level
    log_level = _get_log_level(log_level_str)
    logger.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Setup file handler if log file is specified
    if log_file:
        try:
            # Resolve log file path relative to project directory
            log_path = Path(log_file)
            if not log_path.is_absolute():
                # Make relative paths relative to project directory
                project_path = get_project_path_as_path()
                log_path = project_path / log_path
            
            # Create log directory if it doesn't exist
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create file handler
            file_handler = logging.FileHandler(str(log_path), mode='a', encoding='utf-8')
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
        except Exception as e:
            # If file logging setup fails, fall back to console logging for this error
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.ERROR)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
            logger.error(f"Failed to setup file logging to '{log_file}': {e}")
            return logger
    
    # If no file logging configured, only setup console for ERROR and above
    if not log_file:
        # Only add console handler for errors when no file logging
        if log_level <= logging.ERROR:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.ERROR)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
    else:
        # When file logging is enabled, also log ERROR and above to console
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.ERROR)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger

def get_logger(logger_name: str = "mcp-postgresql") -> logging.Logger:
    """
    Get a configured logger instance.
    
    Args:
        logger_name: Name of the logger
        
    Returns:
        Logger instance (will be configured if not already)
    """
    logger = logging.getLogger(logger_name)
    
    # If logger doesn't have handlers, configure it
    if not logger.hasHandlers():
        return setup_logging(logger_name)
    
    return logger

def is_logging_enabled() -> bool:
    """
    Check if file logging is enabled.
    
    Returns:
        True if MCP_POSTGRESQL_LOG_FILE is set and not empty
    """
    log_file = os.getenv('MCP_POSTGRESQL_LOG_FILE', '').strip()
    return bool(log_file)

def get_log_file_path() -> Optional[str]:
    """
    Get the configured log file path, resolved to absolute path.
    
    Returns:
        Absolute log file path if configured, None otherwise
    """
    log_file = os.getenv('MCP_POSTGRESQL_LOG_FILE', '').strip()
    if not log_file:
        return None
    
    log_path = Path(log_file)
    if not log_path.is_absolute():
        # Make relative paths relative to project directory
        project_path = get_project_path_as_path()
        log_path = project_path / log_path
    
    return str(log_path)

def get_log_level_name() -> str:
    """
    Get the configured log level name.
    
    Returns:
        Log level name (default: 'error')
    """
    return os.getenv('MCP_POSTGRESQL_LOG_LEVEL', 'error').strip()

# Create default logger instance for module-level usage
default_logger = setup_logging()