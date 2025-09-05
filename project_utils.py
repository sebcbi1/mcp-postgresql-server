"""
Project utilities for global project path management.

@author sebcbi1
"""
import os
from pathlib import Path

def get_project_path() -> str:
    """
    Returns the global project path from MCP_POSTGRESQL_CWD environment variable.
    Falls back to current working directory if MCP_POSTGRESQL_CWD is not set.
    """
    return os.getenv('MCP_POSTGRESQL_CWD', os.getcwd())

def get_project_path_as_path() -> Path:
    """
    Returns the global project path as a Path object.
    """
    return Path(get_project_path())
