#!/usr/bin/env python3

"""
PostgreSQL Database Connection Library 🔗

Shared database connection and query execution utilities for MCP PostgreSQL tools.
Provides connection pooling, query execution, and configuration management.

@author sebcbi1
"""

import os
import time
import re
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional, Union

try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("❌ psycopg2 is required. Install it with: pip install psycopg2-binary")
    raise ImportError("psycopg2-binary is required")

try:
    from dotenv import load_dotenv
except ImportError:
    print("❌ python-dotenv is required. Install it with: pip install python-dotenv")
    raise ImportError("python-dotenv is required")

try:
    from project_utils import get_project_path_as_path
except ImportError:
    print("❌ Failed to import project utilities. Make sure project_utils.py is in the same directory.")
    raise ImportError("project_utils is required")

# Import logging configuration
try:
    from logging_config import get_logger
    logger = get_logger("db-connection")
except ImportError:
    # Fallback to basic logging if logging_config is not available
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("db-connection")

def load_project_dotenv(override: bool = False):
    """
    Load .env file from the project directory.
    
    Args:
        override: If True, override existing environment variables.
                 If False, only set variables that don't already exist.
    """
    # Use project_utils to get the correct project path
    project_path = get_project_path_as_path()
    env_file = project_path / '.env'
    
    if env_file.exists():
        load_dotenv(str(env_file), override=override)
    else:
        # Fallback to current directory
        load_dotenv(override=override)

# Load initial environment on module import
load_project_dotenv()


class DatabaseConfig:
    """Database configuration management"""
    
    def __init__(self):
        self._config = None
    
    def load_config(self, database_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Loads database configuration from a given URI or environment variable.
        Args:
            database_url: Optional PostgreSQL URI.
        Returns: Database configuration dictionary
        """
        if self._config:
            return self._config

        if database_url is None:
            database_url = os.getenv('MCP_POSTGRESQL_DATABASE')
        
        if not database_url:
            raise ValueError(
                'No database URI provided and MCP_POSTGRESQL_DATABASE environment variable is not set.'
            )
        
        # Parse PostgreSQL URI
        try:
            parsed = urlparse(database_url)
            
            if parsed.scheme not in ['postgres', 'postgresql']:
                raise ValueError('Invalid PostgreSQL URI. Must start with postgres:// or postgresql://')
            
            self._config = {
                'host': parsed.hostname,
                'port': parsed.port or 5432,
                'database': parsed.path[1:] if parsed.path else None,  # Remove leading slash
                'user': parsed.username,
                'password': parsed.password,
                'minconn': 1,
                'maxconn': 20,
            }
            
            # Validate required fields
            if not all([self._config['host'], self._config['database'], self._config['user']]):
                raise ValueError('Invalid PostgreSQL URI. Missing required components.')
            
            return self._config
            
        except Exception as error:
            raise ValueError(f'Failed to parse database URI: {error}')


class DatabasePool:
    """Database connection pool manager"""
    
    def __init__(self, database_url: Optional[str] = None):
        self._pool = None
        self._config = DatabaseConfig()
        self.database_url = database_url
    
    def initialize(self):
        """Initialize database connection pool"""
        if self._pool:
            logger.debug("Database pool already initialized, skipping")
            return
            
        try:
            db_config = self._config.load_config(self.database_url)
            logger.info(f"Initializing database connection pool to {db_config['host']}:{db_config['port']}/{db_config['database']}")
            
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=db_config['minconn'],
                maxconn=db_config['maxconn'],
                host=db_config['host'],
                port=db_config['port'],
                database=db_config['database'],
                user=db_config['user'],
                password=db_config['password'],
                cursor_factory=RealDictCursor
            )
            
            logger.info(f"Database pool initialized successfully with {db_config['minconn']}-{db_config['maxconn']} connections")
            
        except Exception as error:
            logger.error(f"Failed to initialize database pool: {error}", exc_info=True)
            raise Exception(f'Failed to initialize database pool: {error}')
    
    def get_connection(self):
        """Get connection from pool"""
        if not self._pool:
            self.initialize()
        return self._pool.getconn()
    
    def return_connection(self, connection):
        """Return connection to pool"""
        if self._pool and connection:
            self._pool.putconn(connection)
    
    def close_all(self):
        """Close all connections in pool"""
        if self._pool:
            try:
                self._pool.closeall()
                self._pool = None
            except Exception as error:
                print(f'⚠️  Warning: Error closing database pool: {error}')


class DatabaseExecutor:
    """Database query execution utilities"""
    
    def __init__(self, pool: DatabasePool, read_only: bool = True):
        self.pool = pool
        self.read_only = read_only
        # Define read-only SQL patterns
        self.write_operations = [
            'INSERT', 'UPDATE', 'DELETE', 'UPSERT', 'MERGE',
            'CREATE', 'ALTER', 'DROP', 'TRUNCATE', 'REPLACE'
        ]
    
    def validate_read_only_query(self, sql: str) -> bool:
        """
        Validate that SQL query is read-only (SELECT operations only)
        Args:
            sql: SQL query string
        Returns: True if query is read-only, raises Exception if not
        """
        # Normalize SQL - remove comments and extra whitespace
        normalized_sql = re.sub(r'--.*?(\n|$)', '', sql, flags=re.MULTILINE)  # Remove line comments
        normalized_sql = re.sub(r'/\*.*?\*/', '', normalized_sql, flags=re.DOTALL)  # Remove block comments
        normalized_sql = re.sub(r'\s+', ' ', normalized_sql).strip().upper()  # Normalize whitespace
        
        # Check for write operations
        for operation in self.write_operations:
            pattern = rf'\b{operation}\b'
            if re.search(pattern, normalized_sql):
                raise Exception(f"Write operation '{operation}' is not allowed. Only read-only operations (SELECT, WITH, SHOW, EXPLAIN, DESCRIBE) are permitted.")
        
        # Check for specific forbidden patterns
        forbidden_patterns = [
            r'\bEXEC\b',  # Execute stored procedures
            r'\bCALL\b',  # Call procedures
            r'\bDO\b',    # Execute anonymous code blocks
            r'\bCOPY\b.*\bFROM\b',  # COPY FROM (data insertion)
            r'\bLOCK\b',  # Table locking
            r'\bUNLOCK\b', # Table unlocking
        ]
        
        for pattern in forbidden_patterns:
            if re.search(pattern, normalized_sql):
                raise Exception(f"Operation matching pattern '{pattern}' is not allowed. Only read-only operations are permitted.")
        
        # Allow specific read operations
        allowed_start_patterns = [
            r'^\s*SELECT\b',
            r'^\s*WITH\b',      # Common Table Expressions (CTEs)
            r'^\s*SHOW\b',      # Show commands
            r'^\s*EXPLAIN\b',   # Query plans
            r'^\s*DESCRIBE\b',  # Describe tables
            r'^\s*DESC\b',      # Short form of DESCRIBE
            r'^\s*\(',          # Subqueries in parentheses
        ]
        
        is_allowed = any(re.match(pattern, normalized_sql) for pattern in allowed_start_patterns)
        
        if not is_allowed:
            raise Exception(f"Query type not allowed. Only SELECT, WITH, SHOW, EXPLAIN, and DESCRIBE operations are permitted. Query starts with: {normalized_sql[:50]}...")
        
        return True
    
    def execute_query(self, sql: str, params: Optional[List] = None) -> List[Dict[str, Any]]:
        """
        Execute a SQL query using the database pool
        Args:
            sql: SQL query string
            params: Query parameters (optional)
        Returns: Query results as list of dictionaries
        """
        if params is None:
            params = []
        
        # Log query execution attempt (truncate for readability)
        query_preview = sql[:100].replace('\n', ' ').strip()
        if len(sql) > 100:
            query_preview += "..."
        logger.debug(f"Executing query: {query_preview}")
        if params:
            logger.debug(f"Query parameters: {params}")
        
        # Validate query is read-only before execution (if read_only mode is enabled)
        if self.read_only:
            try:
                self.validate_read_only_query(sql)
                logger.debug("Query validated as read-only")
            except Exception as e:
                logger.warning(f"Query validation failed: {e}")
                raise
        
        connection = None
        cursor = None
        
        try:
            # Get connection from pool
            connection = self.pool.get_connection()
            cursor = connection.cursor()
            
            # Execute query
            start_time = time.time()
            cursor.execute(sql, params)
            execution_time = time.time() - start_time
            
            # Fetch results if it's a SELECT query
            if cursor.description:
                # Convert RealDictRow to regular dict for consistent formatting
                rows = [dict(row) for row in cursor.fetchall()]
                logger.info(f"Query executed successfully in {execution_time:.3f}s, returned {len(rows)} rows")
                return rows
            else:
                # This should not happen with read-only queries, but handle gracefully
                logger.info(f"Query executed successfully in {execution_time:.3f}s, no results returned")
                return [{'message': 'Query executed successfully, no results returned'}]
                
        except Exception as error:
            if connection:
                connection.rollback()
            logger.error(f"Database query failed: {str(error)}", exc_info=True)
            raise Exception(f"Database query failed: {str(error)}")
        finally:
            if cursor:
                cursor.close()
            if connection:
                self.pool.return_connection(connection)
    
    def format_results_as_table(self, rows: List[Dict[str, Any]]) -> str:
        """
        Format database query results as a readable table
        Args:
            rows: Database query results
        Returns: Formatted table string
        """
        if not rows or len(rows) == 0:
            return '📝 No results found.'
        
        # Get column names
        columns = list(rows[0].keys())
        
        # Calculate maximum width for each column
        max_widths = {}
        for col in columns:
            max_widths[col] = max(
                len(col),
                max(len(str(row.get(col, ''))) for row in rows)
            )
        
        # Create header
        header = ' | '.join(col.ljust(max_widths[col]) for col in columns)
        separator = '-+-'.join('-' * max_widths[col] for col in columns)
        
        # Create rows
        formatted_rows = []
        for row in rows:
            formatted_row = ' | '.join(
                str(row.get(col, '')).ljust(max_widths[col]) for col in columns
            )
            formatted_rows.append(formatted_row)
        
        # Combine everything
        result = [
            f'📊 Results ({len(rows)} row{"" if len(rows) == 1 else "s"}):',
            '',
            header,
            separator
        ] + formatted_rows
        
        return '\n'.join(result)


class DatabaseManager:
    """High-level database management interface"""
    
    def __init__(self, database_url: Optional[str] = None, read_only: bool = None):
        if read_only is None:
            # Check environment variable, default to True (read-only mode)
            read_only_env = os.getenv('MCP_POSTGRESQL_READ_ONLY', 'true')
            read_only = read_only_env.lower() != 'false'
        
        self.pool = DatabasePool(database_url)
        self.executor = DatabaseExecutor(self.pool, read_only=read_only)
        self._initialized = False
        self.read_only = read_only
    
    def initialize(self):
        """Initialize the database manager"""
        if not self._initialized:
            read_only_mode = "enabled" if self.read_only else "disabled"
            logger.info(f"Initializing DatabaseManager with read-only mode {read_only_mode}")
            self.pool.initialize()
            self._initialized = True
            logger.info("DatabaseManager initialized successfully")
    
    def test_connection(self) -> bool:
        """Tests the database connection without executing a query."""
        connection = None
        try:
            connection = self.pool.get_connection()
            return True
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
        finally:
            if connection:
                self.pool.return_connection(connection)
    
    def execute_query(self, sql: str, params: Optional[List] = None) -> List[Dict[str, Any]]:
        """Execute a query and return results"""
        if not self._initialized:
            self.initialize()
        return self.executor.execute_query(sql, params)
    
    def format_results_as_table(self, rows: List[Dict[str, Any]]) -> str:
        """Format query results as a table"""
        return self.executor.format_results_as_table(rows)
    
    def is_read_only(self) -> bool:
        """Check if database manager is in read-only mode"""
        return self.read_only
    
    def close(self):
        """Close all database connections"""
        self.pool.close_all()
        self._initialized = False


# Global instance for backward compatibility
_global_manager = None

def get_database_manager(read_only: bool = None) -> DatabaseManager:
    """Get or create the global database manager instance"""
    global _global_manager
    if _global_manager is None:
        _global_manager = DatabaseManager(read_only=read_only)
    return _global_manager

def initialize_database():
    """Initialize the global database manager (backward compatibility)"""
    manager = get_database_manager()
    manager.initialize()

def execute_db_query(sql: str, params: Optional[List] = None) -> List[Dict[str, Any]]:
    """Execute a database query (backward compatibility)"""
    manager = get_database_manager()
    return manager.execute_query(sql, params)

def close_database_connection():
    """Close database connections (backward compatibility)"""
    global _global_manager
    if _global_manager:
        _global_manager.close()
        _global_manager = None
