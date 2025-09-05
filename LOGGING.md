# MCP PostgreSQL Logging System

This project includes a comprehensive logging system that can be configured via environment variables.

## Environment Variables

### MCP_POSTGRESQL_LOG_FILE
- **Purpose**: Specifies the path to the log file
- **Default**: Empty (no file logging)
- **Path Resolution**: 
  - Absolute paths: Used as-is (e.g., `/var/log/mcp-postgresql.log`)
  - Relative paths: Resolved relative to project directory from MCP_POSTGRESQL_CWD (e.g., `logs/app.log`)
- **Behavior**: 
  - If not set or empty: No file logging occurs
  - If set: All log messages are written to the specified file

### MCP_POSTGRESQL_LOG_LEVEL
- **Purpose**: Sets the minimum log level
- **Default**: `error`
- **Valid values**: `debug`, `info`, `warning`, `warn`, `error`, `critical`, `fatal`
- **Case insensitive**

## Configuration Examples

### No File Logging (Default)
```bash
# These are the defaults in .env
MCP_POSTGRESQL_LOG_FILE=
MCP_POSTGRESQL_LOG_LEVEL=error
```

Only ERROR level messages and above will be shown on the console.

### File Logging Enabled

**Absolute path:**
```bash
# Enable file logging with absolute path
MCP_POSTGRESQL_LOG_FILE=/var/log/mcp-postgresql.log
MCP_POSTGRESQL_LOG_LEVEL=info
```

**Relative path:**
```bash
# Enable file logging with relative path (resolved to project directory)
MCP_POSTGRESQL_LOG_FILE=logs/mcp-postgresql.log
MCP_POSTGRESQL_LOG_LEVEL=info
```

All INFO level messages and above will be written to the log file, and ERROR messages will also appear on console.

### Debug Logging
```bash
# Enable detailed debug logging
MCP_POSTGRESQL_LOG_FILE=./debug.log
MCP_POSTGRESQL_LOG_LEVEL=debug
```

All messages including DEBUG level will be written to the log file.

## Log Format

The log format is:
```
YYYY-MM-DD HH:MM:SS - logger_name - LEVEL - message
```

Example:
```
2025-09-05 12:06:04 - db-connection - INFO - Database pool initialized successfully with 1-20 connections
2025-09-05 12:06:04 - mcp-postgresql-server - ERROR - Query execution failed: connection timeout
```

## Using Logging in Code

### Import the Logger
```python
from logging_config import get_logger

# Get a logger for your module
logger = get_logger("my-module-name")
```

### Log Messages
```python
logger.debug("Detailed debug information")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error occurred", exc_info=True)  # Include stack trace
logger.critical("Critical error")
```

### Check if Logging is Enabled
```python
from logging_config import is_logging_enabled, get_log_file_path

if is_logging_enabled():
    print(f"Logging to: {get_log_file_path()}")
else:
    print("File logging is disabled")
```

## Components with Logging

The following components include comprehensive logging:

1. **mcp_postgresql_server.py**: Main MCP server operations
2. **execute_query.py**: Query execution and interactive mode
3. **db_connection.py**: Database connection pool and query execution
4. **logging_config.py**: Logging configuration module

## Log Directory Creation

The logging system automatically creates the log directory if it doesn't exist. 

Examples:
```bash
# Absolute path - creates /var/log/mcp/ if needed
MCP_POSTGRESQL_LOG_FILE=/var/log/mcp/postgresql.log

# Relative path - creates logs/ directory in project root if needed
MCP_POSTGRESQL_LOG_FILE=logs/postgresql.log
```

**Note**: Relative paths are resolved relative to the project directory (MCP_POSTGRESQL_CWD environment variable), not the current working directory.

## Error Handling

- If the log file cannot be created or written to, an error message is logged to the console
- The application continues running even if file logging fails
- Console error logging is always available as a fallback

## Testing

Run the logging tests to verify functionality:
```bash
python3 test_logging.py
```

This will test:
- No file logging configuration
- File logging with different levels
- Database logging integration (if database is available)