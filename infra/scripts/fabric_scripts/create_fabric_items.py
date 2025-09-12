import requests
import time
import json
from azure.identity import AzureCliCredential
import shlex
import argparse

p = argparse.ArgumentParser()
p.add_argument("--workspaceId", required=True)
p.add_argument("--solutionname", required=True)
p.add_argument("--backend_app_pid", required=True)
p.add_argument("--backend_app_uid", required=True)
p.add_argument("--exports-file", required=True)
args = p.parse_args()

workspaceId = args.workspaceId
solutionname = args.solutionname
backend_app_pid = args.backend_app_pid
backend_app_uid = args.backend_app_uid

def get_fabric_headers():
    credential = AzureCliCredential()
    cred = credential.get_token('https://api.fabric.microsoft.com/.default')
    token = cred.token
    fabric_headers = {"Authorization": "Bearer " + token.strip()}
    return(fabric_headers)

fabric_headers = get_fabric_headers()

lakehouse_name = 'retail_lakehouse_' + solutionname
sqldb_name = 'retail_sqldatabase_' + solutionname
pipeline_name = 'data_pipeline_' + solutionname

# print("workspace id: " ,workspaceId)

fabric_base_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/"
fabric_items_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/items/"
fabric_sql_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/sqlDatabases/"

fabric_create_workspace_url = f"https://api.fabric.microsoft.com/v1/workspaces"

# create lakehouse
lakehouse_data = {
  "displayName": lakehouse_name,
  "type": "Lakehouse"
}
lakehouse_res = requests.post(fabric_items_url, headers=fabric_headers, json=lakehouse_data)
# print(lakehouse_res.json())
lakehouseId = lakehouse_res.json()['id']


# copy local files to lakehouse
from azure.storage.filedatalake import (
    DataLakeServiceClient
)
from azure.identity import AzureCliCredential
credential = AzureCliCredential()

account_name = "onelake" #always onelake
data_path = f"{lakehouse_name}.Lakehouse/Files/"
folder_path = "/"

account_url = f"https://{account_name}.dfs.fabric.microsoft.com"
service_client = DataLakeServiceClient(account_url, credential=credential)

# # get workspace name
ws_res = requests.get(fabric_base_url, headers=fabric_headers)
# print(ws_res.json())
workspace_name = ws_res.json()['displayName']

#Create a file system client for the workspace
file_system_client = service_client.get_file_system_client(workspace_name)

directory_client = file_system_client.get_directory_client(f"{data_path}/{folder_path}")

print('uploading files')
# upload audio files
file_client = directory_client.get_file_client("data/" + 'tables.json')
with open(file='sql_files/tables.json', mode="rb") as data:
        # print('data', data)
    file_client.upload_data(data, overwrite=True)


fabric_headers = get_fabric_headers()

# create sql db
sqldb_data = {
  "displayName": sqldb_name,
  "description": "SQL Database"
}
sqldb_res = requests.post(fabric_sql_url, headers=fabric_headers, json=sqldb_data)
if sqldb_res.status_code == 202:
    print("sql database creation accepted with status 202")
    
    # print(sqldb_res.headers)
    retry_url = sqldb_res.headers.get("Location")

    # wait_seconds = 10
    wait_seconds = int(sqldb_res.headers.get("Retry-After"))
    attempt = 1
    status = 'Running'
    while status == 'Running':
        print(f"Polling attempt {attempt}...")
        time.sleep(wait_seconds)
        retry_response = requests.get(retry_url, headers=fabric_headers)
        # wait_seconds = int(retry_response.headers.get("Retry-After"))
        status = retry_response.json()['status']
        attempt += 1

    print('sql database created',retry_response.json()['status'])

elif sqldb_res.status_code == 200:
    print('sql database created')
else:
    print(f"sql database creation failed with status: {sqldb_res.status_code}")
    print(sqldb_res.text)

fabric_headers = get_fabric_headers()
# get SQL DBs list
sqldb_res = requests.get(fabric_sql_url, headers=fabric_headers)
sqlsdbs_res = sqldb_res.json()
# print(sqlsdbs_res)

for sqldb in sqlsdbs_res['value']:
    if sqldb['displayName'] == sqldb_name:
        sqldb_id = sqldb['id']
        FABRIC_SQL_DATABASE = '{' + sqldb['properties']['databaseName'] + '}'
        FABRIC_SQL_SERVER = sqldb['properties']['serverFqdn'].replace(',1433','')
        odbc_driver = "{ODBC Driver 17 for SQL Server}"
        FABRIC_SQL_CONNECTION_STRING = f"DRIVER={odbc_driver};SERVER={FABRIC_SQL_SERVER};DATABASE={FABRIC_SQL_DATABASE};UID={backend_app_uid};Authentication=ActiveDirectoryMSI"
# print(sqldb_id)



# create tables and upload data
from azure.identity import AzureCliCredential
import pyodbc
import struct

def get_fabric_db_connection():
    server = FABRIC_SQL_SERVER
    database = FABRIC_SQL_DATABASE
    driver = "{ODBC Driver 17 for SQL Server}"
    
    try:
        conn=None
        connection_string = ""
 
        with AzureCliCredential() as credential:
            token = credential.get_token("https://database.windows.net/.default")
            # logging.info("FABRIC-SQL-TOKEN: %s" % token.token)
            token_bytes = token.token.encode("utf-16-LE")
            token_struct = struct.pack(
                f"<I{len(token_bytes)}s",
                len(token_bytes),
                token_bytes
            )

            SQL_COPT_SS_ACCESS_TOKEN = 1256
            connection_string = f"DRIVER={driver};SERVER={server};DATABASE={database};"  
            conn = pyodbc.connect( connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})      
            print('connected to fabric sql db')        
 
        return conn
    except :
        print("Failed to connect to Fabric SQL Database")
        pass

conn = get_fabric_db_connection()
cursor = conn.cursor()
print(cursor)
sql_filename = 'sql_files/data_sql.sql'
with open(sql_filename, 'r', encoding='utf-8') as f:
    sql_script = f.read()
    cursor.execute(sql_script)
cursor.commit()
conn.close()    


import json

file_path = "sql_files/tables.json"

time.sleep(120)
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)

for table in data['tables']:
    # # create shortcut for lakehouse 
    fabric_shortcuts_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/items/{lakehouseId}/shortcuts?shortcutConflictPolicy=CreateOrOverwrite"
    shortcut_lh ={
        "path": "/Tables",
        "name": table['tablename'],
        "target": {
            "oneLake": {
                "workspaceId": workspaceId,
                "itemId": sqldb_id,
                "path": f"Tables/dbo/{table['tablename']}"
            }
        }
    }
    shortcut_res = requests.post(fabric_shortcuts_url, headers=fabric_headers, json=shortcut_lh)
    print('shortcut: ',shortcut_res.json())
# fabric_headers = get_fabric_headers()

# # get connection Id
# fabric_connection_url = f"https://api.fabric.microsoft.com/v1/connections"
# conn_res = requests.get(fabric_connection_url, headers=fabric_headers)
# for r in conn_res.json()['value']:
#     if r['connectionDetails']['path'] == 'FabricSql':
#     #   print(r['id'])
#         sqldb_connection_id = r['id']
        
#         # else: 
#         #     # create connection 
    
# # load data    
# fabric_headers = get_fabric_headers()
# import os
# folder_path = 'sql_files'

# for filename in os.listdir(folder_path):
#     file_path = os.path.join(folder_path, filename)

#     # Skip directories, process only files
#     if os.path.isfile(file_path):
#         print(f"Processing file: {filename}")

#         sql_filepath = file_path #'data_sql.sql'
#         with open(sql_filepath, 'r', encoding='utf-8') as f:
#             sql_query_str = f.read()

#         # create pipeline item
#         pipeline_json = {
#             "name": (pipeline_name + '_' + filename.replace('.sql', '')),
#             "properties": {
#                 "activities": [
#                     {
#                         "name": "process_data",
#                         "type": "Script",
#                         "dependsOn": [],
#                         "policy": {
#                             "timeout": "0.12:00:00",
#                             "retry": 0,
#                             "retryIntervalInSeconds": 30,
#                             "secureOutput": "false",
#                             "secureInput": "false"
#                         },
#                         "connectionSettings": {
#                             "name": "sqldatabase",
#                             "properties": {
#                                 "annotations": [],
#                                 "type": "FabricSqlDatabase",
#                                 "typeProperties": {
#                                     "workspaceId": workspaceId,
#                                     "artifactId": sqldb_id
#                                 },
#                                 "externalReferences": {
#                                     "connection": sqldb_connection_id 
#                                 }
#                             }
#                         },
#                         "typeProperties": {
#                             "scripts": [
#                                 {
#                                     "type": "Query",
#                                     "text": {
#                                         "value": sql_query_str,
#                                         "type": "Expression"
#                                     }
#                                 }
#                             ],
#                             "scriptBlockExecutionTimeout": "02:00:00"
#                         }
#                     }
#                 ]
#             }
#         }

#         import base64

#         pipeline_base64 = base64.b64encode(json.dumps(pipeline_json).encode('utf-8'))

#         pipeline_data = {
#                 "displayName":(pipeline_name + '_' + filename.replace('.sql', '')),
#                 "type":"DataPipeline",
#                 "definition" : {
#                     # "format": "json",
#                     "parts": [
#                         {
#                             "path": "pipeline-content.json",
#                             "payload": pipeline_base64.decode('utf-8'),
#                             "payloadType": "InlineBase64"
#                         }
#                     ]
#                 }
#             }

#         pipeline_response = requests.post(fabric_items_url, headers=fabric_headers, json=pipeline_data)
#         # print('pipeline response: ',pipeline_response.json())


#         pipeline_id = pipeline_response.json()['id']

#         fabric_headers = get_fabric_headers()

#         # run the pipeline once
#         job_url = fabric_base_url + f"items/{pipeline_id}/jobs/instances?jobType=Pipeline"
#         job_response = requests.post(job_url, headers=fabric_headers)
#         # print(job_response)

#         if job_response.status_code == 202:
#             print("pipeline run accepted with status 202")
            
#             retry_url = job_response.headers.get("Location")

#             # wait_seconds = 20
#             wait_seconds = int(job_response.headers.get("Retry-After"))
#             attempt = 1
#             status = ''
#             while (status != 'Completed') and (status != 'Failed'):
#                 print(f"Polling attempt {attempt}...")
#                 time.sleep(wait_seconds)
#                 retry_response = requests.get(retry_url, headers=fabric_headers)
#                 # print(retry_response.json())
#                 # wait_seconds = int(retry_response.headers.get("Retry-After"))
#                 status = retry_response.json()['status']
#                 # print(status)
#                 attempt += 1

#             print('pipeline run completed',retry_response.json()['status'])

#         elif job_response.status_code == 200:
#             print('pipeline run completed')
#         else:
#             print(f"pipeline run request failed with status: {job_response.status_code}")
#             print('pipeline job response: ',job_response.text)


#create role assignments
fabric_headers = get_fabric_headers()
fabric_ra_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/roleAssignments"
roleassignment_json ={
  "principal": {
    "id": args.backend_app_pid, 
    "type": "ServicePrincipal"
  },
  "role": "Contributor"
}
roleassignment_res = requests.post(fabric_ra_url, headers=fabric_headers, json=roleassignment_json)

# Write shell-safe exports
with open(args.exports_file, "w", encoding="utf-8", newline="\n") as f:
    f.write("export FABRIC_SQL_SERVER1=" + shlex.quote(FABRIC_SQL_SERVER) + "\n")
    f.write("export FABRIC_SQL_DATABASE1=" + shlex.quote(FABRIC_SQL_DATABASE) + "\n")
    f.write("export FABRIC_SQL_CONNECTION_STRING1=" + shlex.quote(FABRIC_SQL_CONNECTION_STRING) + "\n")
