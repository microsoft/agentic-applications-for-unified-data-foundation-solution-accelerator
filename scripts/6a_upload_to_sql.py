"""
Upload Data to Azure SQL Server
Creates tables and loads sample data into Azure SQL Server.
This script is part of the build solution pipeline.

Usage:
    python scripts/6a_upload_to_sql.py

Environment Variables (from azd or .env):
    - SQLDB_SERVER: Azure SQL Server hostname
    - SQLDB_DATABASE: Azure SQL Database name
    - USECASE: Use case (retail-sales-analysis or insurance)
"""

import argparse
import os
import struct
import sys
import pandas as pd
import pyodbc
from datetime import datetime
from azure.identity import AzureCliCredential

# Add scripts directory to path for load_env
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from load_env import load_all_env


def parse_args():
    """Parse command line arguments."""
    p = argparse.ArgumentParser(description="Upload data to Azure SQL Server")
    p.add_argument("--sql-server", type=str, help="Azure SQL Server hostname (overrides env)")
    p.add_argument("--sql-database", type=str, help="Azure SQL Database name (overrides env)")
    p.add_argument("--usecase", type=str, help="Use case: retail-sales-analysis or insurance (overrides env)")
    return p.parse_args()


def get_sql_connection(server: str, database: str):
    """
    Get a connection to Azure SQL Server using Azure CLI credentials.
    
    Args:
        server: Azure SQL Server hostname
        database: Database name
        
    Returns:
        pyodbc connection object
    """
    driver18 = "ODBC Driver 18 for SQL Server"
    driver17 = "ODBC Driver 17 for SQL Server"
    
    credential = AzureCliCredential()
    token = credential.get_token("https://database.windows.net/.default")
    token_bytes = token.token.encode("utf-16-LE")
    token_struct = struct.pack(
        f"<I{len(token_bytes)}s",
        len(token_bytes),
        token_bytes
    )
    SQL_COPT_SS_ACCESS_TOKEN = 1256
    
    try:
        connection_string = f"DRIVER={{{driver18}}};SERVER={server};DATABASE={database};"
        conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
        print(f"  Connected using {driver18}")
        return conn
    except Exception:
        connection_string = f"DRIVER={{{driver17}}};SERVER={server};DATABASE={database};"
        conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
        print(f"  Connected using {driver17}")
        return conn


def execute_sql_file(cursor, filepath: str):
    """Execute SQL commands from a file."""
    print(f"  Executing: {os.path.basename(filepath)}")
    with open(filepath, 'r', encoding='utf-8') as f:
        sql_script = f.read()
        cursor.execute(sql_script)
    cursor.commit()


def generate_insurance_sql(file_path: str, output_file_path: str):
    """Generate SQL insert statements from CSV files for insurance use case."""
    print("  Generating insurance SQL from CSV files...")
    
    sql_data_types = {
        'int64': 'INT',
        'float64': 'DECIMAL(10,2)',
        'object': 'NVARCHAR(MAX)',
        'bool': 'BIT',
        'datetime64[ns]': 'DATETIME2(6)',
        'timedelta[ns]': 'TIME'
    }
    
    sql_commands = []
    
    for file in os.listdir(file_path):
        if file.endswith('.csv'):
            table_file_path = os.path.join(file_path, file)
            df = pd.read_csv(table_file_path)
            table_name = file.replace('.csv', '')
            
            if table_name == 'customer':
                df = df.fillna('').replace({None: ''})
            
            # Create table statement
            create_table_statement = f'DROP TABLE IF EXISTS [dbo].[{table_name}]; \nCREATE TABLE [dbo].[{table_name}] (\n'
            create_table_columns = []
            
            for column in df.columns:
                if 'id' in column.lower():
                    sql_type = sql_data_types[str(df.dtypes[column])] + ' NOT NULL '
                elif 'Date' in column:
                    sql_type = ' DATETIME2(6) NULL '
                else:
                    sql_type = sql_data_types[str(df.dtypes[column])] + ' NULL '
                
                create_table_columns.append(f'    [{column}] {sql_type}')
            
            create_table_statement += ',\n'.join(create_table_columns) + '\n);'
            sql_commands.append(create_table_statement)
            
            # Insert statements
            insert_sql = f"INSERT INTO {table_name} ([{'] , ['.join(df.columns) }]) VALUES "
            values_list = []
            count = 0
            
            for index, row in df.iterrows():
                values = []
                for value in row:
                    if isinstance(value, str):
                        str_value = value.replace("'", "''")
                        str_value = f"'{str_value}'"
                        values.append(str_value)
                    elif isinstance(value, bool):
                        values.append("1" if value else "0")
                    else:
                        values.append(str(value))
                
                count += 1
                values_list.append(f"({', '.join(values)})")
                
                if count == 1000:
                    insert_sql += ",\n".join(values_list) + ";\n"
                    sql_commands.append(insert_sql)
                    insert_sql = f"INSERT INTO {table_name} ([{'] , ['.join(df.columns)}]) VALUES "
                    values_list = []
                    count = 0
            
            if values_list:
                insert_sql += ",\n".join(values_list) + ";\n"
                sql_commands.append(insert_sql)
    
    with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(sql_commands))
    
    return output_file_path


def adjust_dates_retail(cursor, conn):
    """Adjust dates in retail tables to current date."""
    print("  Adjusting retail dates to current date...")
    today = datetime.today()
    cursor.execute("SELECT MAX(CAST(OrderDate AS DATETIME)) FROM dbo.orders")
    max_start_time = cursor.fetchone()[0]
    days_difference = (today - max_start_time).days - 1 if max_start_time else 0
    
    cursor.execute("UPDATE [dbo].[orders] SET OrderDate = FORMAT(DATEADD(DAY, ?, OrderDate), 'yyyy-MM-dd')", (days_difference,))
    cursor.execute("UPDATE [dbo].[invoice] SET InvoiceDate = FORMAT(DATEADD(DAY, ?, InvoiceDate), 'yyyy-MM-dd'), DueDate = FORMAT(DATEADD(DAY, ?, DueDate), 'yyyy-MM-dd')", (days_difference, days_difference))
    cursor.execute("UPDATE [dbo].[payment] SET PaymentDate = FORMAT(DATEADD(DAY, ?, PaymentDate), 'yyyy-MM-dd')", (days_difference,))
    cursor.execute("UPDATE [dbo].[customer] SET CustomerEstablishedDate = FORMAT(DATEADD(DAY, ?, CustomerEstablishedDate), 'yyyy-MM-dd')", (days_difference,))
    cursor.execute("UPDATE [dbo].[account] SET CreatedDate = FORMAT(DATEADD(DAY, ?, CreatedDate), 'yyyy-MM-dd')", (days_difference,))
    conn.commit()


def adjust_dates_insurance(cursor, conn):
    """Adjust dates in insurance tables to current date."""
    print("  Adjusting insurance dates to current date...")
    today = datetime.today()
    cursor.execute("SELECT MAX(CAST(StartDate AS DATETIME)) FROM dbo.policy")
    max_start_time = cursor.fetchone()[0]
    days_difference = (today - max_start_time).days - 1 if max_start_time else 0
    
    cursor.execute("UPDATE [dbo].[policy] SET StartDate = FORMAT(DATEADD(DAY, ?, StartDate), 'yyyy-MM-dd')", (days_difference,))
    cursor.execute("UPDATE [dbo].[claim] SET ClaimDate = FORMAT(DATEADD(DAY, ?, ClaimDate), 'yyyy-MM-dd')", (days_difference,))
    cursor.execute("UPDATE [dbo].[communicationshistory] SET CommunicationDate = FORMAT(DATEADD(DAY, ?, CommunicationDate), 'yyyy-MM-dd')", (days_difference,))
    cursor.execute("UPDATE [dbo].[customer] SET CustomerEstablishedDate = FORMAT(DATEADD(DAY, ?, CustomerEstablishedDate), 'yyyy-MM-dd')", (days_difference,))
    conn.commit()


def main():
    # Load environment variables from azd and .env
    load_all_env()
    
    args = parse_args()
    
    # Get configuration from CLI args or environment
    sql_server = args.sql_server or os.getenv("SQLDB_SERVER")
    sql_database = args.sql_database or os.getenv("SQLDB_DATABASE")
    usecase = args.usecase or os.getenv("USE_CASE") or os.getenv("USECASE", "insurance")
    
    # Validate required settings
    if not sql_server:
        print("ERROR: SQL Server not configured. Set SQLDB_SERVER in .env or pass --sql-server")
        sys.exit(1)
    
    if not sql_database:
        print("ERROR: SQL Database not configured. Set SQLDB_DATABASE in .env or pass --sql-database")
        sys.exit(1)
    
    # Normalize usecase
    usecase = usecase.lower()
    if usecase == 'retail-sales-analysis':
        usecase = 'retail'
    elif usecase not in ['retail', 'insurance']:
        usecase = 'insurance'
    
    print(f"\n{'='*60}")
    print("Upload Data to Azure SQL Server")
    print(f"{'='*60}")
    print(f"  Server: {sql_server}")
    print(f"  Database: {sql_database}")
    print(f"  Use Case: {usecase}")
    
    # Connect to Azure SQL Server
    print("\nConnecting to Azure SQL Server...")
    try:
        conn = get_sql_connection(sql_server, sql_database)
    except Exception as e:
        print(f"ERROR: Failed to connect to SQL Server: {e}")
        sys.exit(1)
    
    cursor = conn.cursor()
    
    # Get paths to SQL files and data (relative to this script)
    sql_files_dir = os.path.join(script_dir, 'sql_files')
    data_dir = os.path.join(sql_files_dir, 'data')
    
    # Verify directories exist
    if not os.path.exists(sql_files_dir):
        print(f"ERROR: SQL files directory not found: {sql_files_dir}")
        cursor.close()
        conn.close()
        sys.exit(1)
    
    # Execute base SQL (history tables)
    print("\nCreating base tables...")
    base_sql_file = os.path.join(sql_files_dir, 'data_sql.sql')
    if os.path.exists(base_sql_file):
        execute_sql_file(cursor, base_sql_file)
    
    # Execute use case specific SQL
    print(f"\nLoading {usecase} data...")
    if usecase == "retail":
        usecase_sql_file = os.path.join(sql_files_dir, 'retail_data_sql.sql')
        if os.path.exists(usecase_sql_file):
            execute_sql_file(cursor, usecase_sql_file)
            adjust_dates_retail(cursor, conn)
        else:
            print(f"WARNING: Retail SQL file not found: {usecase_sql_file}")
    else:
        # Generate insurance SQL from CSV files
        output_sql_path = os.path.join(sql_files_dir, 'insurance_data_sql.sql')
        
        # Check if insurance SQL needs to be generated
        if not os.path.exists(output_sql_path) or os.path.getsize(output_sql_path) < 1000:
            if os.path.exists(data_dir):
                generate_insurance_sql(data_dir, output_sql_path)
            else:
                print(f"WARNING: Data directory not found: {data_dir}")
        
        if os.path.exists(output_sql_path):
            execute_sql_file(cursor, output_sql_path)
            adjust_dates_insurance(cursor, conn)
        else:
            print(f"WARNING: Insurance SQL file not found: {output_sql_path}")
    
    cursor.close()
    conn.close()
    
    print(f"\n{'='*60}")
    print("[OK] Azure SQL Server data upload completed successfully!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
