# db_discovery.py

"""
This module provides functionality to automatically discover database configuration
from common project configuration files.

@author sebcbi1
"""

import os
import json
import re
import yaml
import toml
import configparser
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional

from db_connection import DatabaseManager
from project_utils import get_project_path, get_project_path_as_path

# Supported file types and their parsers
SUPPORTED_FILES = {
    '.json': 'json',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.toml': 'toml',
    '.ini': 'ini',
    '.cfg': 'ini',
    '.conf': 'ini',
}

# Regex patterns for database URIs
POSTGRES_URI_PATTERN = re.compile(r"postgres(?:ql)?://[^\s'\"`]+")


def _extract_uris_from_string(content: str) -> List[str]:
    """Extracts PostgreSQL URIs from a string."""
    return POSTGRES_URI_PATTERN.findall(content)

def _find_uris_in_obj(obj: Any) -> List[str]:
    """Recursively finds PostgreSQL URIs in a Python object (dict, list, etc.)."""
    uris = []
    if isinstance(obj, dict):
        for value in obj.values():
            if isinstance(value, str):
                uris.extend(_extract_uris_from_string(value))
            elif isinstance(value, (dict, list)):
                uris.extend(_find_uris_in_obj(value))
    elif isinstance(obj, list):
        for item in obj:
            uris.extend(_find_uris_in_obj(item))
    return uris

def _parse_json(content: str) -> List[str]:
    try:
        data = json.loads(content)
        return _find_uris_in_obj(data)
    except json.JSONDecodeError:
        return []

def _parse_yaml(content: str) -> List[str]:
    try:
        data = yaml.safe_load(content)
        return _find_uris_in_obj(data)
    except yaml.YAMLError:
        return []

def _parse_toml(content: str) -> List[str]:
    try:
        data = toml.loads(content)
        return _find_uris_in_obj(data)
    except toml.TomlDecodeError:
        return []

def _extract_db_parameters(config_dict: Dict[str, str]) -> Dict[str, Dict[str, str]]:
    """Extract database parameters and group them by database identifier."""
    db_groups = {}
    
    # Parameter mappings for different naming conventions
    param_mappings = {
        'host': ['host', 'hostname', 'server'],
        'port': ['port'],
        'user': ['user', 'username', 'dbuser'],
        'password': ['pass', 'password', 'dbpass', 'pwd'],
        'database': ['name', 'dbname', 'database', 'db'],
    }
    
    for key, value in config_dict.items():
        if not value or value.startswith('#'):
            continue
            
        # Handle prefixed parameters (e.g., db.host, imotidb.user)
        if '.' in key:
            prefix, param = key.split('.', 1)
            
            # Skip non-database prefixes
            if prefix in ['cdn', 'memcached', 'sphinx', 'elastic', 'ftp', 'mongo']:
                continue
                
            if prefix not in db_groups:
                db_groups[prefix] = {}
                
            # Map parameter names to standard names
            for std_param, variants in param_mappings.items():
                if param.lower() in variants:
                    db_groups[prefix][std_param] = value
                    break
        else:
            # Handle simple parameters (no prefix)
            if 'default' not in db_groups:
                db_groups['default'] = {}
                
            for std_param, variants in param_mappings.items():
                if key.lower() in variants:
                    db_groups['default'][std_param] = value
                    break
    
    return db_groups

def _construct_postgres_uri(db_params: Dict[str, str]) -> Optional[str]:
    """Construct a PostgreSQL URI from database parameters."""
    required_params = ['host', 'database']
    
    # Check if we have minimum required parameters
    if not all(param in db_params for param in required_params):
        return None
    
    host = db_params['host']
    database = db_params['database']
    port = db_params.get('port', '5432')
    user = db_params.get('user', '')
    password = db_params.get('password', '')
    
    # Construct the URI
    if user and password:
        uri = f"postgresql://{user}:{password}@{host}:{port}/{database}"
    elif user:
        uri = f"postgresql://{user}@{host}:{port}/{database}"
    else:
        uri = f"postgresql://{host}:{port}/{database}"
    
    return uri

def _parse_ini(content: str) -> List[str]:
    """Parses INI/CFG content and extracts potential database URIs."""
    uris = []
    
    # First, try to extract complete URIs using regex
    try:
        config = configparser.ConfigParser()
        config.read_string(content)
        for section in config.sections():
            for key, value in config.items(section):
                uris.extend(_extract_uris_from_string(value))
    except configparser.Error:
        pass # Ignore parsing errors
    
    # Parse as key-value pairs (like .conf files)
    config_dict = {}
    for line in content.split('\n'):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            config_dict[key.strip()] = value.strip()
    
    # Extract database parameters and construct URIs
    if config_dict:
        db_groups = _extract_db_parameters(config_dict)
        for db_name, params in db_groups.items():
            uri = _construct_postgres_uri(params)
            if uri:
                uris.append(uri)
    
    return uris

def scan_for_config_files() -> List[Path]:
    """Scans the project directory for supported configuration files."""
    found_files = []
    project_path = get_project_path()
    for root, _, files in os.walk(project_path):
        if '.venv' in root or 'venv' in root or '.git' in root or '__pycache__' in root:
            continue
        for file in files:
            file_path = Path(root) / file
            if file_path.suffix in SUPPORTED_FILES or file_path.name.startswith('.env'):
                found_files.append(file_path)
    return found_files

def discover_database_configs() -> List[Dict[str, Any]]:
    """
    Discovers database configurations by scanning and parsing files.
    """
    config_files = scan_for_config_files()
    all_configs = []
    
    # Use a set to avoid adding duplicate URIs from the same file
    seen_configs = set()

    for file_path in config_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            uris = []
            parser_map = {
                '.json': _parse_json,
                '.yaml': _parse_yaml,
                '.yml': _parse_yaml,
                '.toml': _parse_toml,
                '.ini': _parse_ini,
                '.cfg': _parse_ini,
                '.conf': _parse_ini,
            }
            parser = parser_map.get(file_path.suffix)
            if parser:
                uris.extend(parser(content))

            # Also do a raw regex scan as a fallback for all file types
            uris.extend(_extract_uris_from_string(content))

            if uris:
                for uri in set(uris):
                    config_tuple = (str(file_path), uri)
                    if config_tuple not in seen_configs:
                        all_configs.append({
                            'source': str(file_path),
                            'uri': uri,
                        })
                        seen_configs.add(config_tuple)

        except Exception as e:
            print(f"Could not read or parse {file_path}: {e}")
            continue
    
    # Sort by source path for consistent ordering
    return sorted(all_configs, key=lambda x: x['source'])

def list_config_files() -> List[str]:
    """Returns a list of all found configuration files."""
    return [str(p) for p in scan_for_config_files()]

def validate_database_config(uri: str) -> bool:
    """Validates a database URI by attempting to connect."""
    try:
        db_manager = DatabaseManager(database_url=uri)
        return db_manager.test_connection()
    except Exception:
        return False

def backup_env_file() -> Optional[str]:
    """Backs up the .env file if it exists, returning the backup path."""
    env_path = get_project_path_as_path() / '.env'
    if not env_path.exists():
        return None
    
    backup_path = env_path.with_suffix('.env.bak')
    shutil.copy(env_path, backup_path)
    return str(backup_path)

def setup_database_config(uri: str):
    """Creates or updates the .env file with the given database URI."""
    env_path = get_project_path_as_path() / '.env'
    with open(env_path, 'a+') as f:
        f.seek(0)
        lines = f.readlines()
        
        # Remove existing MCP_POSTGRESQL_DATABASE and MCP_DATABASE lines
        lines = [line for line in lines if not (line.strip().startswith('MCP_POSTGRESQL_DATABASE=') or line.strip().startswith('MCP_DATABASE='))]
        
        # Add the new line with preferred variable name
        lines.append(f'MCP_POSTGRESQL_DATABASE={uri}\n')
        
        f.seek(0)
        f.truncate()
        f.writelines(lines)

if __name__ == '__main__':
    print("🔍 Starting database configuration discovery...")
    discovered = discover_database_configs()
    if discovered:
        print("✅ Found potential database configurations:")
        for i, config in enumerate(discovered):
            print(f"  [{i}] Source: {config['source']}")
            print(f"      URI: {config['uri']}")
    else:
        print("❌ No database configurations found.")