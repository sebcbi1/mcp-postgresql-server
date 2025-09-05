#!/usr/bin/env python3

"""
SQL Query Execution Script 🚀

This script allows you to execute SQL queries with direct database connection.
It reads configuration from environment variable MCP_DATABASE or .env file.

Usage:
  python execute-query.py                           # Interactive mode
  python execute-query.py "SELECT * FROM users"    # Direct query
  python execute-query.py --file query.sql         # Execute from file

Environment variable:
  MCP_DATABASE=postgres://user:password@host:port/database

@author sebcbi1
"""

import sys
import argparse
import time
from pathlib import Path

# Import our shared database library
try:
    from db_connection import DatabaseManager
except ImportError:
    print("❌ Failed to import database connection library. Make sure db_connection.py is in the same directory.")
    sys.exit(1)


class QueryExecutor:
    """Command-line query execution interface"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
    
    def execute_query_with_output(self, sql_query: str, params=None):
        """
        Executes a SQL query and displays the results with timing
        Args:
            sql_query: The SQL query to execute
            params: Query parameters (optional)
        """
        if params is None:
            params = []
            
        trimmed_query = sql_query.strip()
        
        if not trimmed_query:
            print('❌ Empty query provided.')
            return
        
        print(f'🔍 Executing query: {trimmed_query}')
        
        if params:
            print(f'📋 Parameters: {params}')
        
        start_time = time.time()
        
        try:
            results = self.db_manager.execute_query(trimmed_query, params)
            execution_time = int((time.time() - start_time) * 1000)  # Convert to milliseconds
            
            print('\n' + self.db_manager.format_results_as_table(results))
            print(f'\n⏱️  Query executed in {execution_time}ms\n')
            
        except Exception as error:
            print('❌ Query execution failed:')
            print(f'   Error: {str(error)}')
            print('')
    
    def start_interactive_mode(self):
        """
        Starts interactive mode for executing queries
        """
        print('🎯 Interactive SQL Query Mode')
        print('Enter SQL queries (type "exit" or "quit" to leave):')
        print('Examples:')
        print('  SELECT * FROM users LIMIT 5;')
        print('  SELECT COUNT(*) FROM users;')
        print('')
        
        while True:
            try:
                user_input = input('SQL> ').strip()
                
                if user_input.lower() in ['exit', 'quit']:
                    print('👋 Goodbye!')
                    break
                
                if user_input.lower() == 'help':
                    print('Available commands:')
                    print('  help  - Show this help message')
                    print('  exit  - Exit interactive mode')
                    print('  quit  - Exit interactive mode')
                    print('')
                    continue
                
                if user_input:
                    self.execute_query_with_output(user_input)
                    
            except KeyboardInterrupt:
                print('\n👋 Shutting down gracefully...')
                break
            except EOFError:
                print('\n👋 Goodbye!')
                break
    
    def execute_from_file(self, file_path: str):
        """
        Reads and executes SQL from a file
        Args:
            file_path: Path to the SQL file
        """
        try:
            file_path = Path(file_path).resolve()
            
            if not file_path.exists():
                print(f'❌ File not found: {file_path}')
                return
            
            with open(file_path, 'r', encoding='utf-8') as file:
                sql_content = file.read()
            
            print(f'📁 Reading SQL from: {file_path}')
            self.execute_query_with_output(sql_content)
            
        except Exception as error:
            print(f'❌ Failed to read file: {error}')
    
    def close(self):
        """Close database connections"""
        self.db_manager.close()


def show_help():
    """
    Displays help information
    """
    print('🛠️  SQL Query Execution Script')
    print('')
    print('Usage:')
    print('  python execute-query.py                           # Interactive mode')
    print('  python execute-query.py "SELECT * FROM users"    # Direct query')
    print('  python execute-query.py --file query.sql         # Execute from file')
    print('  python execute-query.py --help                   # Show this help')
    print('')
    print('Configuration:')
    print('  Set MCP_DATABASE environment variable:')
    print('    export MCP_DATABASE="postgres://user:password@host:port/database"')
    print('')
    print('  Or create a .env file with:')
    print('    MCP_DATABASE=postgres://user:password@host:port/database')
    print('')
    print('Examples:')
    print('  python execute-query.py "SELECT COUNT(*) FROM properties"')
    print('  python execute-query.py --file ./queries/user-stats.sql')
    print('')


def main():
    """
    Main function to handle command line arguments and start the script
    """
    executor = None
    
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(
            description='SQL Query Execution Script',
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        parser.add_argument(
            'query',
            nargs='?',
            help='SQL query to execute'
        )
        parser.add_argument(
            '--file', '-f',
            dest='file_path',
            help='Execute SQL from file'
        )
        parser.add_argument(
            '--help-extended',
            action='store_true',
            help='Show extended help information'
        )
        
        args = parser.parse_args()
        
        # Show help if requested
        if args.help_extended:
            show_help()
            return
        
        # Initialize executor and database connection
        print('🔌 Initializing database connection...')
        executor = QueryExecutor()
        executor.db_manager.initialize()
        print('✅ Database connection established!\n')
        
        # Execute based on arguments
        if args.file_path:
            # Execute from file
            executor.execute_from_file(args.file_path)
            
        elif args.query:
            # Direct query execution
            executor.execute_query_with_output(args.query)
            
        else:
            # Interactive mode
            executor.start_interactive_mode()
            
    except Exception as error:
        print(f'❌ Failed to initialize: {error}')
        sys.exit(1)
    
    finally:
        if executor:
            executor.close()


# Backward compatibility functions for MCP server
def initialize_database():
    """Initialize database (backward compatibility for MCP server)"""
    from db_connection import initialize_database as init_db
    init_db()

def execute_db_query(sql: str, params=None):
    """Execute database query (backward compatibility for MCP server)"""
    from db_connection import execute_db_query as exec_query
    return exec_query(sql, params)

def close_database_connection():
    """Close database connection (backward compatibility for MCP server)"""
    from db_connection import close_database_connection as close_db
    close_db()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n👋 Shutting down gracefully...')
        sys.exit(0)
    except Exception as error:
        print(f'❌ Unexpected error: {error}')
        sys.exit(1)
