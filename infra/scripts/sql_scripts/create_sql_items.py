"""
Azure SQL Server table creation and sample data loading script.
This script creates tables and loads sample data into Azure SQL Server
for workshop deployments (when IS_WORKSHOP=true).
"""

import argparse
import os
import struct
import shlex
import pandas as pd
import pyodbc
from datetime import datetime
from azure.identity import AzureCliCredential


def parse_args():
    """Parse command line arguments."""
    p = argparse.ArgumentParser()
    p.add_argument("--sql-server", required=True, help="Azure SQL Server hostname")
    p.add_argument("--sql-database", required=True, help="Azure SQL Database name")
    p.add_argument("--backend_app_uid", required=True, help="Backend app user ID for MSI auth")
    p.add_argument("--usecase", required=True, help="Use case: retail-sales-analysis or insurance")
    p.add_argument("--exports-file", required=True, help="File to write environment exports")
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
        return conn
    except Exception:
        connection_string = f"DRIVER={{{driver17}}};SERVER={server};DATABASE={database};"
        conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
        return conn


def execute_sql_file(cursor, filepath: str):
    """Execute SQL commands from a file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        sql_script = f.read()
        cursor.execute(sql_script)
    cursor.commit()

def generate_insurance_sql(file_path: str, output_file_path: str):
    """Generate SQL insert statements from CSV files for insurance use case."""
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
    args = parse_args()
    
    # Normalize usecase
    usecase = args.usecase.lower()
    if usecase == 'retail-sales-analysis':
        usecase = 'retail'
    else:
        usecase = 'insurance'
    
    
    # Connect to Azure SQL Server
    print("\nConnecting to Azure SQL Server...")
    conn = get_sql_connection(args.sql_server, args.sql_database)
    cursor = conn.cursor()
    
    # Get the script directory for relative paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    fabric_scripts_dir = os.path.join(script_dir, '..', 'fabric_scripts')
    
    # Execute base SQL (history tables)
    base_sql_file = os.path.join(fabric_scripts_dir, 'sql_files', 'data_sql.sql')
    execute_sql_file(cursor, base_sql_file)
    
    # Execute use case specific SQL
    if usecase == "retail":
        usecase_sql_file = os.path.join(fabric_scripts_dir, 'sql_files', 'retail_data_sql.sql')
        execute_sql_file(cursor, usecase_sql_file)
        adjust_dates_retail(cursor, conn)
    else:
        # Generate insurance SQL from CSV files
        data_path = os.path.join(fabric_scripts_dir, 'data')
        output_sql_path = os.path.join(fabric_scripts_dir, 'sql_files', 'insurance_data_sql.sql')
        
        # Check if insurance SQL already exists
        if not os.path.exists(output_sql_path) or os.path.getsize(output_sql_path) < 1000:
            generate_insurance_sql(data_path, output_sql_path)
        
        execute_sql_file(cursor, output_sql_path)
        adjust_dates_insurance(cursor, conn)
    
    cursor.close()
    conn.close()
    print("\n✓ Azure SQL Server setup completed successfully!")
    
    # Build connection strings for export
    odbc_driver_18 = "{ODBC Driver 18 for SQL Server}"
    sqldb_connection_string = f"DRIVER={odbc_driver_18};SERVER={args.sql_server};DATABASE={args.sql_database};UID={args.backend_app_uid};Authentication=ActiveDirectoryMSI"
    
    # Write shell-safe exports (using SQLDB_* to match infra naming)
    with open(args.exports_file, "w", encoding="utf-8", newline="\n") as f:
        f.write("export SQLDB_SERVER1=" + shlex.quote(args.sql_server) + "\n")
        f.write("export SQLDB_DATABASE1=" + shlex.quote(args.sql_database) + "\n")
        f.write("export SQLDB_CONNECTION_STRING1=" + shlex.quote(sqldb_connection_string) + "\n")


if __name__ == "__main__":
    main()
