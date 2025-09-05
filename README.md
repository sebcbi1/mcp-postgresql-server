# PostgreSQL MCP Server

A secure, read-only PostgreSQL Model Context Protocol (MCP) server for AI
assistant integration with automatic database discovery and connection management.

## What It Does

This tool provides two main components:

- **Query Executor** (`execute_query.py`): Interactive PostgreSQL query
execution with support for direct queries, file input, and interactive mode
- **MCP Server** (`mcp_postgresql_server.py`): AI assistant integration that allows
natural language database interactions through Claude and other MCP clients

## Key Features

- **Automatic Database Discovery**: Scans project files for database
configurations and presents options for selection
- **Read-Only Safety**: Blocks write operations by default (configurable)
- **Interactive Configuration**: Guides users through database setup
with automatic `.env` file management
- **Connection Pooling**: Efficient PostgreSQL connection management
- **AI Integration**: Works seamlessly with Claude Desktop and Cursor IDE

## Quick Start

**Prerequisites**: Ensure you have [uv](https://docs.astral.sh/uv/) installed.

### Using uvx (Recommended)

Run directly without installation:

```bash
# MCP Server for AI integration
uvx mcp-postgresql-server

# Query executor
uvx --from mcp-postgresql-server execute-query "SELECT version()"
```

### Configuration

Set your database connection:

```bash
export MCP_POSTGRESQL_DATABASE="postgres://username:password@hostname:port/database"
```

Or create a `.env` file:

```env
MCP_POSTGRESQL_DATABASE=postgres://username:password@hostname:port/database
MCP_POSTGRESQL_READ_ONLY=true
MCP_POSTGRESQL_LOG_FILE=./mcp-postgresql.log
MCP_POSTGRESQL_LOG_LEVEL=info
```

## Usage Examples

### Query Executor

**Using uvx (recommended):**

```bash
# Interactive mode
uvx --from mcp-postgresql-server execute-query

# Direct query
uvx --from mcp-postgresql-server execute-query "SELECT COUNT(*) FROM users"

# From file
uvx --from mcp-postgresql-server execute-query --file queries.sql
```

**Using Python directly:**

```bash
# Interactive mode
python3 execute_query.py

# Direct query
python3 execute_query.py "SELECT COUNT(*) FROM users"

# From file
python3 execute_query.py --file queries.sql
```

### MCP Server with Claude Code (globally)

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "mcp-postgres": {
      "command": "uvx",
      "args": ["mcp-postgresql-server"],
      "env": {
        "MCP_POSTGRESQL_CWD": "${PWD}"
      }
    }
  }
}
```

Then ask Claude:

- "Show me all tables in the database"
- "Execute SELECT COUNT(*) FROM users"
- "Help me write a query to find recent orders"

### Cursor IDE Integration

Create/update `mcp.json` in your project root:

```json
{
  "mcpServers": {
    "mcp-postgresql-server": {
      "command": "uvx",
      "args": ["mcp-postgresql-server"],
      "env": {
        "MCP_POSTGRESQL_CWD": "."
      }
    }
  }
}
```

## Configuration Discovery

The server automatically discovers database configurations from:

- `.env` files
- `.conf` and `.ini` files
- `.json` and `.yaml` files
- Individual parameter files (db.host, db.user, etc.)

When multiple configurations are found, it presents an interactive selection menu.
Saved configurations are stored in a `.env` file for future use
using MCP_POSTGRESQL_DATABASE variable.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_POSTGRESQL_DATABASE` | PostgreSQL connection URI | Required |
| `MCP_POSTGRESQL_READ_ONLY` | Enable read-only mode | `true` |
| `MCP_POSTGRESQL_LOG_FILE` | Log file path (optional) | None |
| `MCP_POSTGRESQL_LOG_LEVEL` | Log level (debug, info, warning, error, critical) | `error` |
| `MCP_POSTGRESQL_CWD` | Path of the project working directory | `.` |

## Security

- **Read-only by default**: Blocks INSERT, UPDATE, CREATE, ALTER, DROP operations
- **Connection validation**: Validates all database connections before use
- **Credential protection**: Supports environment variables and `.env` files
- **Error handling**: Comprehensive error reporting without exposing sensitive data

## Common Issues

**Connection errors**: Verify `MCP_POSTGRESQL_DATABASE` format: `postgres://user:password@host:port/database`

**Permission issues**: Ensure database user has appropriate SELECT permissions
