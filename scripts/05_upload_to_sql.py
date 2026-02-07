"""
06a - Upload Data to Azure SQL Server
Reads CSV files from the data folder and loads them into Azure SQL Server.

Usage:
    python 06a_upload_to_sql.py [--data-folder <PATH>]

Prerequisites:
    - Run 01_generate_sample_data.py (creates CSV files in data folder)
    - Azure CLI logged in (az login)
    - SQLDB_SERVER and SQLDB_DATABASE set in azd environment

What this script does:
    1. Reads ontology_config.json from data folder to get table definitions
    2. Creates tables in Azure SQL based on ontology config
    3. Loads CSV files from tables/ folder into SQL tables
    4. Adjusts date columns to current date
    5. Assigns SQL roles to API managed identity (db_datareader, db_datawriter)
"""

import argparse
import os
import struct
import sys
import json
import pandas as pd
import pyodbc
from datetime import datetime
from azure.identity import DefaultAzureCredential

# Add scripts directory to path for load_env
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from load_env import load_all_env, get_data_folder

# ============================================================================
# Configuration
# ============================================================================

def parse_args():
    """Parse command line arguments."""
    p = argparse.ArgumentParser(description="Upload data to Azure SQL Server")
    p.add_argument("--data-folder", help="Path to data folder (default: from .env)")
    p.add_argument("--sql-server", type=str, help="Azure SQL Server hostname (overrides env)")
    p.add_argument("--sql-database", type=str, help="Azure SQL Database name (overrides env)")
    return p.parse_args()


# ============================================================================
# SQL Type Mapping
# ============================================================================

# Map ontology types to SQL types
ONTOLOGY_TO_SQL_TYPE = {
    'String': 'NVARCHAR(MAX)',
    'BigInt': 'BIGINT',
    'Int': 'INT',
    'Float': 'DECIMAL(18,4)',
    'Double': 'DECIMAL(18,4)',
    'Boolean': 'BIT',
    'DateTime': 'DATETIME2(6)',
    'Date': 'DATE',
    'Time': 'TIME',
}

# Map pandas dtypes to SQL types (fallback)
PANDAS_TO_SQL_TYPE = {
    'int64': 'BIGINT',
    'float64': 'DECIMAL(18,4)',
    'object': 'NVARCHAR(MAX)',
    'bool': 'BIT',
    'datetime64[ns]': 'DATETIME2(6)',
    'timedelta[ns]': 'TIME',
}


def get_sql_type(column_name: str, ontology_type: str = None, pandas_dtype: str = None) -> str:
    """Get SQL type for a column based on ontology config or pandas dtype."""
    if ontology_type and ontology_type in ONTOLOGY_TO_SQL_TYPE:
        return ONTOLOGY_TO_SQL_TYPE[ontology_type]
    if pandas_dtype and pandas_dtype in PANDAS_TO_SQL_TYPE:
        return PANDAS_TO_SQL_TYPE[pandas_dtype]
    return 'NVARCHAR(MAX)'


# ============================================================================
# Database Connection
# ============================================================================

def get_sql_connection(server: str, database: str):
    """
    Get a connection to Azure SQL Server using DefaultAzureCredential.
    
    Args:
        server: Azure SQL Server hostname
        database: Database name
        
    Returns:
        pyodbc connection object
    """
    driver18 = "ODBC Driver 18 for SQL Server"
    driver17 = "ODBC Driver 17 for SQL Server"
    
    credential = DefaultAzureCredential()
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


# ============================================================================
# Table Creation and Data Loading
# ============================================================================

def create_table_from_ontology(cursor, table_name: str, table_config: dict, df: pd.DataFrame):
    """Create a table based on ontology configuration."""
    columns = table_config.get('columns', [])
    types = table_config.get('types', {})
    key_column = table_config.get('key', None)
    
    # Build column definitions
    column_defs = []
    for col in columns:
        if col not in df.columns:
            continue
        
        ontology_type = types.get(col)
        pandas_dtype = str(df[col].dtype)
        sql_type = get_sql_type(col, ontology_type, pandas_dtype)
        
        # Add NOT NULL constraint for key columns
        null_constraint = 'NOT NULL' if col == key_column else 'NULL'
        column_defs.append(f'    [{col}] {sql_type} {null_constraint}')
    
    if not column_defs:
        print(f"  [WARN] No columns found for table {table_name}")
        return False
    
    # Drop and create table
    drop_sql = f'DROP TABLE IF EXISTS [dbo].[{table_name}];'
    create_sql = f'CREATE TABLE [dbo].[{table_name}] (\n' + ',\n'.join(column_defs) + '\n);'
    
    cursor.execute(drop_sql)
    cursor.execute(create_sql)
    cursor.commit()
    
    return True


def load_data_to_table(cursor, conn, table_name: str, df: pd.DataFrame, batch_size: int = 1000):
    """Load DataFrame data into SQL table using batch inserts."""
    if df.empty:
        print(f"  [WARN] No data to load for {table_name}")
        return 0
    
    columns = df.columns.tolist()
    column_list = ', '.join([f'[{col}]' for col in columns])
    placeholders = ', '.join(['?' for _ in columns])
    insert_sql = f'INSERT INTO [dbo].[{table_name}] ({column_list}) VALUES ({placeholders})'
    
    rows_inserted = 0
    batch = []
    
    for _, row in df.iterrows():
        values = []
        for val in row:
            if pd.isna(val):
                values.append(None)
            elif isinstance(val, bool):
                values.append(1 if val else 0)
            else:
                values.append(val)
        batch.append(tuple(values))
        
        if len(batch) >= batch_size:
            cursor.executemany(insert_sql, batch)
            rows_inserted += len(batch)
            batch = []
    
    # Insert remaining rows
    if batch:
        cursor.executemany(insert_sql, batch)
        rows_inserted += len(batch)
    
    conn.commit()
    return rows_inserted


def adjust_dates_to_current(cursor, conn, table_name: str, date_columns: list, reference_column: str = None):
    """Adjust date columns to be relative to current date."""
    if not date_columns:
        return
    
    today = datetime.today()
    
    # Find the reference column (first date column if not specified)
    ref_col = reference_column or date_columns[0]
    
    try:
        cursor.execute(f"SELECT MAX(CAST([{ref_col}] AS DATETIME)) FROM [dbo].[{table_name}]")
        max_date = cursor.fetchone()[0]
        
        if max_date:
            days_difference = (today - max_date).days - 1
            
            for col in date_columns:
                cursor.execute(
                    f"UPDATE [dbo].[{table_name}] SET [{col}] = DATEADD(DAY, ?, [{col}])",
                    (days_difference,)
                )
            
            conn.commit()
            print(f"    Adjusted {len(date_columns)} date column(s) by {days_difference} days")
    except Exception as e:
        print(f"    [WARN] Could not adjust dates: {e}")


# ============================================================================
# Main
# ============================================================================

def main():
    # Load environment variables from azd and .env
    load_all_env()
    
    args = parse_args()
    
    # Get configuration from CLI args or environment
    sql_server = args.sql_server or os.getenv("SQLDB_SERVER")
    sql_database = args.sql_database or os.getenv("SQLDB_DATABASE")
    
    # Validate SQL settings
    if not sql_server:
        print("ERROR: SQL Server not configured.")
        print("       Set SQLDB_SERVER in azd environment or pass --sql-server")
        sys.exit(1)
    
    if not sql_database:
        print("ERROR: SQL Database not configured.")
        print("       Set SQLDB_DATABASE in azd environment or pass --sql-database")
        sys.exit(1)
    
    # Get data folder - use arg if provided, else from .env with proper path resolution
    if args.data_folder:
        data_dir = os.path.abspath(args.data_folder)
    else:
        try:
            data_dir = get_data_folder()
        except ValueError:
            print("ERROR: DATA_FOLDER not set.")
            print("       Run 01_generate_data.py first, or pass --data-folder")
            sys.exit(1)
    
    # Set up paths for folder structure (config/, tables/)
    config_dir = os.path.join(data_dir, "config")
    tables_dir = os.path.join(data_dir, "tables")
    
    # Fallback to old structure if config dir doesn't exist
    if not os.path.exists(config_dir):
        config_dir = data_dir
        tables_dir = data_dir
    
    config_path = os.path.join(config_dir, "ontology_config.json")
    
    if not os.path.exists(config_path):
        print(f"ERROR: ontology_config.json not found at {config_path}")
        print("       Run 01_generate_sample_data.py first")
        sys.exit(1)
    
    # Load ontology configuration
    with open(config_path) as f:
        ontology_config = json.load(f)
    
    tables = ontology_config.get('tables', {})
    scenario = ontology_config.get('scenario', 'unknown')
    
    print(f"\n{'='*60}")
    print("Upload Data to Azure SQL Server")
    print(f"{'='*60}")
    print(f"  Server: {sql_server}")
    print(f"  Database: {sql_database}")
    print(f"  Data folder: {data_dir}")
    print(f"  Scenario: {scenario}")
    print(f"  Tables: {', '.join(tables.keys())}")
    
    # Connect to Azure SQL Server
    print("\n[1/3] Connecting to Azure SQL Server...")
    try:
        conn = get_sql_connection(sql_server, sql_database)
    except Exception as e:
        print(f"ERROR: Failed to connect to SQL Server: {e}")
        sys.exit(1)
    
    cursor = conn.cursor()
    
    # Process each table from ontology config
    print("\n[2/3] Creating tables and loading data...")
    
    loaded_tables = []
    for table_name, table_config in tables.items():
        csv_file = f"{table_name}.csv"
        csv_path = os.path.join(tables_dir, csv_file)
        
        if not os.path.exists(csv_path):
            print(f"\n  [SKIP] {table_name} - CSV not found: {csv_file}")
            continue
        
        print(f"\n  Processing {table_name}...")
        
        # Read CSV file
        try:
            df = pd.read_csv(csv_path)
            print(f"    Loaded {len(df)} rows from {csv_file}")
        except Exception as e:
            print(f"    [FAIL] Failed to read CSV: {e}")
            continue
        
        # Create table
        if not create_table_from_ontology(cursor, table_name, table_config, df):
            continue
        print(f"    Created table [dbo].[{table_name}]")
        
        # Load data
        rows = load_data_to_table(cursor, conn, table_name, df)
        print(f"    Inserted {rows} rows")
        
        # Identify date columns and adjust dates
        types = table_config.get('types', {})
        date_columns = [col for col, typ in types.items() if typ in ('DateTime', 'Date')]
        if date_columns:
            adjust_dates_to_current(cursor, conn, table_name, date_columns)
        
        loaded_tables.append(table_name)
    
    # Summary
    print(f"\n[3/3] Verifying data...")
    for table_name in loaded_tables:
        cursor.execute(f"SELECT COUNT(*) FROM [dbo].[{table_name}]")
        count = cursor.fetchone()[0]
        print(f"  [OK] {table_name}: {count} rows")
    
    cursor.close()
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"[OK] Successfully loaded {len(loaded_tables)} table(s) to Azure SQL Server!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
