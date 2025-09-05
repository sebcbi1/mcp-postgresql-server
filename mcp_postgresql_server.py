#!/usr/bin/env python3
"""
MCP PostgreSQL Server

A Model Context Protocol server that provides READ-ONLY PostgreSQL database access.
This server uses the shared database connection library for consistent
database operations across all MCP PostgreSQL tools.

Security: All write operations (INSERT, UPDATE, DELETE, CREATE, ALTER, DROP) are blocked.
Only read operations (SELECT, WITH, SHOW, EXPLAIN, DESCRIBE) are permitted.

Usage:
    python3 mcp-postgresql-server.py

Environment:
    MCP_POSTGRESQL_DATABASE - PostgreSQL connection URI
    MCP_POSTGRESQL_READ_ONLY - Set to "false" to disable read-only mode (default: "true")
    MCP_POSTGRESQL_LOG_FILE - Log file path (optional)
    MCP_POSTGRESQL_LOG_LEVEL - Log level (default: "error")

@author sebcbi1
"""

import asyncio
import sys
import json
import logging
import os
from typing import Any, Dict, List, Optional
# Import MCP components
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    Resource,
)

# Import our shared database library first (this loads .env file)
try:
    from db_connection import DatabaseManager, load_project_dotenv
    from db_discovery import discover_database_configs
    from project_utils import get_project_path
    # .env file is already loaded by db_connection import
except ImportError:
    print("❌ Failed to import a required library. Make sure db_connection.py and db_discovery.py are present.")
    sys.exit(1)


# Setup logging using our configuration module
try:
    from logging_config import get_logger
    logger = get_logger("mcp-postgresql-server")
except ImportError:
    # Fallback to basic logging if logging_config is not available
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("mcp-postgresql-server")

# Set working directory to MCP_POSTGRESQL_CWD
project_path = get_project_path()
os.chdir(project_path)

# Initialize MCP server
app = Server("mcp-postgresql-server")


class DiscoveryMCPServer:
    """
    MCP Server wrapper for database discovery operations.
    """
    def discover_database_configs(self) -> Dict[str, Any]:
        """Scan and return all found database configurations."""
        try:
            configs = discover_database_configs()
            return {
                "success": True,
                "configurations": configs,
                "count": len(configs)
            }
        except Exception as e:
            logger.error(f"Discovery failed: {e}")
            return {"success": False, "error": str(e)}

    def list_config_files(self) -> Dict[str, Any]:
        """List all configuration files found in the project."""
        try:
            from db_discovery import list_config_files
            files = list_config_files()
            return {
                "success": True,
                "files": files,
                "count": len(files)
            }
        except Exception as e:
            logger.error(f"Listing config files failed: {e}")
            return {"success": False, "error": str(e)}

    def validate_database_config(self, uri: str) -> Dict[str, Any]:
        """Validate a given database URI."""
        try:
            from db_discovery import validate_database_config
            is_valid = validate_database_config(uri)
            return {"success": True, "is_valid": is_valid}
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return {"success": False, "error": str(e)}

    def backup_env_file(self) -> Dict[str, Any]:
        """Backup the .env file."""
        try:
            from db_discovery import backup_env_file
            backup_path = backup_env_file()
            return {"success": True, "backup_path": backup_path}
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return {"success": False, "error": str(e)}

    def setup_database_config(self, uri: str) -> Dict[str, Any]:
        """Setup the .env file with the given URI."""
        try:
            from db_discovery import setup_database_config
            setup_database_config(uri)
            load_project_dotenv(override=True)
            return {"success": True}
        except Exception as e:
            logger.error(f"Setup failed: {e}")
            return {"success": False, "error": str(e)}

    def select_and_configure_database(self, selected_index: int = None) -> Dict[str, Any]:
        """Discover database configurations and optionally select one to configure."""
        try:
            configs = discover_database_configs()
            
            if not configs:
                return {"success": False, "error": "No database configurations found"}
            
            if selected_index is None:
                # Return configurations for user selection
                return {
                    "success": True,
                    "action": "selection_required",
                    "configurations": [
                        {
                            "index": i,
                            "source": config["source"],
                            "uri": config["uri"]
                        }
                        for i, config in enumerate(configs)
                    ],
                    "count": len(configs),
                    "message": "Multiple database configurations found. Please specify selected_index to choose one."
                }
            
            # Validate selected index
            if selected_index < 0 or selected_index >= len(configs):
                return {
                    "success": False, 
                    "error": f"Invalid selection. Index must be between 0 and {len(configs) - 1}"
                }
            
            # Configure the selected database
            selected_config = configs[selected_index]
            
            # Backup existing .env file
            from db_discovery import backup_env_file, setup_database_config
            backup_path = backup_env_file()
            
            # Setup the new configuration
            setup_database_config(selected_config["uri"])
            load_project_dotenv(override=True)
            
            return {
                "success": True,
                "action": "configured",
                "selected_config": {
                    "index": selected_index,
                    "source": selected_config["source"],
                    "uri": selected_config["uri"]
                },
                "backup_path": backup_path,
                "message": f"Database configuration from '{selected_config['source']}' has been set in .env file"
            }
            
        except Exception as e:
            logger.error(f"Database selection and configuration failed: {e}")
            return {"success": False, "error": str(e)}

class PostgreSQLMCPServer:
    """
    MCP Server wrapper for PostgreSQL database operations using shared database library
    """
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.db_initialized = False
        
    async def initialize_database(self):
        """Initialize database connection using the shared library"""
        if not os.getenv('MCP_POSTGRESQL_DATABASE'):
            raise Exception("MCP_POSTGRESQL_DATABASE environment variable not set.")
        try:
            if not self.db_initialized:
                self.db_manager.initialize()
                self.db_initialized = True
                read_only_status = "ENABLED" if self.db_manager.is_read_only() else "DISABLED"
                logger.info(f"Database initialized successfully - Read-only mode: {read_only_status}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def execute_sql_query(self, sql: str, params: Optional[List] = None) -> Dict[str, Any]:
        """Execute SQL query and return formatted results"""
        try:
            await self.initialize_database()
            
            if params is None:
                params = []
            
            # Use the shared database manager
            results = self.db_manager.execute_query(sql, params)
            
            # Format results for MCP response
            if not results:
                return {
                    "success": True,
                    "rows": [],
                    "row_count": 0,
                    "message": "Query executed successfully, no results returned"
                }
            
            return {
                "success": True,
                "rows": results,
                "row_count": len(results),
                "message": f"Query executed successfully, {len(results)} row(s) returned"
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Query execution failed: {error_msg}")
            
            return {
                "success": False,
                "error": error_msg,
                "rows": [],
                "row_count": 0
            }
    
    async def list_tables(self) -> Dict[str, Any]:
        """List all tables in the database"""
        sql = """
        SELECT 
            table_name,
            table_type,
            table_schema
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name;
        """

        return await self.execute_sql_query(sql)
    
    async def describe_table(self, table_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific table"""
        sql = """
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_default,
            character_maximum_length,
            numeric_precision,
            numeric_scale
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = %s
        ORDER BY ordinal_position;
        """
        return await self.execute_sql_query(sql, [table_name])
    
    async def get_database_info(self) -> Dict[str, Any]:
        """Get general database information"""
        sql = """
        SELECT 
            version() as database_version,
            current_database() as database_name,
            current_user as current_user,
            NOW() as current_timestamp;
        """
        return await self.execute_sql_query(sql)
    
    def close(self):
        """Close database connections"""
        if self.db_manager:
            self.db_manager.close()
            self.db_initialized = False

# Initialize our server wrappers
postgres_server = PostgreSQLMCPServer()
discovery_server = DiscoveryMCPServer()

# Define MCP Tools
@app.list_tools()
async def list_tools() -> List[Tool]:
    """List all available tools"""
    return [
        Tool(
            name="execute_sql_query",
            description="Execute a read-only SQL query against the PostgreSQL database. Only SELECT, WITH, SHOW, EXPLAIN, and DESCRIBE operations are allowed. Write operations (INSERT, UPDATE, DELETE, CREATE, ALTER, DROP) are blocked. Set MCP_POSTGRESQL_READ_ONLY=false to disable read-only mode.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "The SQL query to execute"
                    },
                    "params": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional parameters for the SQL query",
                        "default": []
                    }
                },
                "required": ["sql"]
            }
        ),
        Tool(
            name="list_tables",
            description="List all tables in the database",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="describe_table",
            description="Get detailed schema information about a specific table",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Name of the table to describe"
                    }
                },
                "required": ["table_name"]
            }
        ),
        Tool(
            name="get_database_info",
            description="Get general information about the database (version, name, user, etc.)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="setup_database_config",
            description="Create or update the .env file with the selected database URI.",
            inputSchema={
                "type": "object",
                "properties": {
                    "uri": {
                        "type": "string",
                        "description": "The database URI to set."
                    }
                },
                "required": ["uri"]
            }
        ),
        Tool(
            name="backup_env_file",
            description="Backup the .env file.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="validate_database_config",
            description="Validate a database connection URI.",
            inputSchema={
                "type": "object",
                "properties": {
                    "uri": {
                        "type": "string",
                        "description": "The database URI to validate."
                    }
                },
                "required": ["uri"]
            }
        ),
        Tool(
            name="list_config_files",
            description="List all supported configuration files found in the project directory.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="discover_database_configs",
            description="Scan project files to discover potential database connection URIs.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_working_directory",
            description="Get the current working directory from the editor/client.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="select_and_configure_database",
            description="Discover database configurations and interactively select one to save in .env file. IMPORTANT: Always call this tool WITHOUT selected_index first to show all available configurations to the user. Only call again WITH selected_index after the user has explicitly chosen which configuration they want to use. DO NOT auto-select configurations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "selected_index": {
                        "type": "integer",
                        "description": "The index of the configuration to select (0-based). ONLY provide this AFTER the user has explicitly chosen from the displayed list of configurations. DO NOT provide this parameter on the first call."
                    }
                },
                "required": []
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> List[TextContent]:
    """Handle tool calls"""
    try:
        if name == "execute_sql_query":
            sql = arguments.get("sql")
            params = arguments.get("params", [])
            result = await postgres_server.execute_sql_query(sql, params)
            
        elif name == "list_tables":
            result = await postgres_server.list_tables()
            
        elif name == "describe_table":
            table_name = arguments.get("table_name")
            result = await postgres_server.describe_table(table_name)
            
        elif name == "get_database_info":
            result = await postgres_server.get_database_info()

        elif name == "discover_database_configs":
            result = discovery_server.discover_database_configs()

        elif name == "list_config_files":
            result = discovery_server.list_config_files()

        elif name == "validate_database_config":
            uri = arguments.get("uri")
            result = discovery_server.validate_database_config(uri)

        elif name == "backup_env_file":
            result = discovery_server.backup_env_file()

        elif name == "setup_database_config":
            uri = arguments.get("uri")
            result = discovery_server.setup_database_config(uri)
            
        elif name == "get_working_directory":
            result = {
                "success": True,
                "working_directory": get_project_path(),
                "source": "MCP_POSTGRESQL_CWD environment variable" if os.getenv('MCP_POSTGRESQL_CWD') else "server cwd fallback"
            }
        
        elif name == "select_and_configure_database":
            selected_index = arguments.get('selected_index')
            result = discovery_server.select_and_configure_database(selected_index)
            
        else:
            result = {
                "success": False,
                "error": f"Unknown tool: {name}"
            }
        
        # Format the response
        response_text = json.dumps(result, indent=2, default=str)
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        logger.error(f"Tool call failed: {str(e)}")
        error_result = {
            "success": False,
            "error": str(e)
        }
        return [TextContent(type="text", text=json.dumps(error_result, indent=2))]

# Define MCP Resources
@app.list_resources()
async def list_resources() -> List[Resource]:
    """List available resources"""
    return [
        Resource(
            uri="schema://tables",
            name="Database Tables",
            description="List of all tables in the database",
            mimeType="application/json"
        ),
        Resource(
            uri="schema://database_info",
            name="Database Information",
            description="General database information (version, name, etc.)",
            mimeType="application/json"
        )
    ]

@app.read_resource()
async def read_resource(uri: str) -> str:
    """Read a resource by URI"""
    try:
        if uri == "schema://tables":
            result = await postgres_server.list_tables()
            return json.dumps(result, indent=2, default=str)
            
        elif uri == "schema://database_info":
            result = await postgres_server.get_database_info()
            return json.dumps(result, indent=2, default=str)
            
        else:
            return json.dumps({
                "error": f"Unknown resource URI: {uri}"
            }, indent=2)
            
    except Exception as e:
        logger.error(f"Resource read failed: {str(e)}")
        return json.dumps({
            "error": str(e)
        }, indent=2)

async def main():
    """Main entry point for the MCP server"""
    try:
        logger.info("Starting MCP PostgreSQL Server...")
        logger.info(get_project_path())
        
        # Run the MCP server
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
            
    except Exception as e:
        logger.error(f"Failed to start MCP server: {e}")
        sys.exit(1)
    
    finally:
        # Clean up database connections
        postgres_server.close()

def cli_main():
    """Entry point for the MCP PostgreSQL server CLI"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
        postgres_server.close()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        postgres_server.close()
        sys.exit(1)

if __name__ == "__main__":
    cli_main()
