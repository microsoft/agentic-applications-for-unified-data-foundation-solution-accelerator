import requests
import time
import json
import base64
import os
from azure.identity import AzureCliCredential

def get_fabric_headers():
    credential = AzureCliCredential()
    cred = credential.get_token('https://api.fabric.microsoft.com/.default')
    token = cred.token
    fabric_headers = {"Authorization": "Bearer " + token.strip()}
    return(fabric_headers)

fabric_headers = get_fabric_headers()

solutionname = ""
workspaceId = ""


lakehouse_name = 'lakehouse_' + solutionname
sqldb_name = 'sqldatabase_' + solutionname
pipeline_name = 'data_pipeline_' + solutionname

# print("workspace id: " ,workspaceId)

fabric_base_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/"
fabric_items_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/items/"
fabric_sql_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/sqlDatabases/"

fabric_create_workspace_url = f"https://api.fabric.microsoft.com/v1/workspaces"

# create environment 
env_name = 'env_' + solutionname
fabric_env_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/environments"
env_json ={
  "displayName": env_name,
  "description": "environment for " + solutionname,
}

env_res = requests.post(fabric_env_url, headers=fabric_headers, json=env_json)
print(env_res.json())
environmentId = env_res.json()['id']

# upload yml file
url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/environments/{environmentId}/staging/libraries"
file_path='environment.yml'
files = {'file': open(file_path, 'rb')}

response = requests.post(url=url, files=files, headers=fabric_headers)
print(response.status_code)
print(response.json())

# publish environment
publish_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/environments/{environmentId}/staging/publish"
publish_env = requests.post(publish_url, headers=fabric_headers)
print(publish_env.status_code)
print(publish_env.json())

# get environment details
env_details_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/environments/{environmentId}"
env_details = requests.get(env_details_url, headers=fabric_headers)
env_details_json = env_details.json()
print('env details: ', env_details_json)


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
with open(file='../fabric_scripts/sql_files/tables.json', mode="rb") as data:
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
        # FABRIC_SQL_CONNECTION_STRING = f"DRIVER={odbc_driver};SERVER={FABRIC_SQL_SERVER};DATABASE={FABRIC_SQL_DATABASE};UID={backend_app_uid};Authentication=ActiveDirectoryMSI"
print(sqldb_id)



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
sql_filename = '../fabric_scripts/sql_files/data_sql.sql'
with open(sql_filename, 'r', encoding='utf-8') as f:
    sql_script = f.read()
    cursor.execute(sql_script)
cursor.commit()
conn.close()

import json


file_path = "../fabric_scripts/sql_files/tables.json"

time.sleep(60)
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)

for table in data['tables']:
    # # create shortcut for lakehouse
    try: 
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
    except: 
        time.sleep(30)
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


while env_details_json['properties']['publishDetails']['state'] == 'Running':
    print('publishing is running')
    time.sleep(120)
    env_details_json = requests.get(env_details_url, headers=fabric_headers).json()
    print(env_details_json)

print(env_details_json)

# create notebook item
notebook_names = ['create_data_agent']

for notebook_name in notebook_names:
    with open('notebooks/'+ notebook_name +'.ipynb', 'r') as f:
        notebook_json = json.load(f)

    print("lakehouse_res")
    print(lakehouse_res)
    print(lakehouse_res.json())
    
    try:
        notebook_json['metadata']['dependencies']['lakehouse']['default_lakehouse'] = lakehouse_res.json()['id']
        notebook_json['metadata']['dependencies']['lakehouse']['default_lakehouse_name'] = lakehouse_res.json()['displayName']
        notebook_json['metadata']['dependencies']['lakehouse']['default_lakehouse_workspace_id'] = lakehouse_res.json()['workspaceId']
        print('lakehouse name: ', notebook_json['metadata']['dependencies']['lakehouse']['default_lakehouse_name'] )
    except:
        pass
    
    if environmentId != '':
        try:
            notebook_json['metadata']['dependencies']['environment']['environmentId'] = environmentId
            notebook_json['metadata']['dependencies']['environment']['workspaceId'] = lakehouse_res.json()['workspaceId']
        except:
            pass


    notebook_base64 = base64.b64encode(json.dumps(notebook_json).encode('utf-8'))
    
    notebook_data = {
        "displayName":notebook_name,
        "type":"Notebook",
        "definition" : {
            "format": "ipynb",
            "parts": [
                {
                    "path": "notebook-content.ipynb",
                    "payload": notebook_base64.decode('utf-8'),
                    "payloadType": "InlineBase64"
                }
            ]
        }
    }
    
    fabric_response = requests.post(fabric_items_url, headers=fabric_headers, json=notebook_data)
    
time.sleep(120)
fabric_notebooks_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/notebooks"
notebooks_res = requests.get(fabric_notebooks_url, headers=fabric_headers)
notebooks_res.json()


pipeline_notebook_id = ''
print("notebook_res.json.values: ", notebooks_res.json().values())
for n in notebooks_res.json().values():
    for notebook in n:
        # print("notebook displayname", notebook['displayName'])
        # if notebook['displayName'] == pipeline_notebook_name:
        pipeline_notebook_id = notebook['id']
        #     break
print("pipeline_notebook_id: ", pipeline_notebook_id)


pipeline_name = 'notebook_pipeline' + solutionname
# create pipeline item
pipeline_json = {
    "name": pipeline_name,
    "properties": {
        "activities": [
            {
                "name": "create_dataagent",
                "type": "TridentNotebook",
                "dependsOn": [],
                "policy": {
                    "timeout": "0.12:00:00",
                    "retry": 0,
                    "retryIntervalInSeconds": 30,
                    "secureOutput": "false",
                    "secureInput": "false"
                },
                "typeProperties": {
                    "notebookId": pipeline_notebook_id,
                    "workspaceId": workspaceId
                }
            }
        ]
    }
}


pipeline_json = {
    "name": pipeline_name,
    "properties": {
        "activities": [
            {
                "name": "create_dataagent",
                "type": "TridentNotebook",
                "dependsOn": [],
                "policy": {
                    "timeout": "0.12:00:00",
                    "retry": 0,
                    "retryIntervalInSeconds": 30,
                    "secureOutput": "false",
                    "secureInput": "false"
                },
                "typeProperties": {
                    "notebookId": pipeline_notebook_id,
                    "workspaceId": workspaceId,
                    "parameters": {
                        "data_agent_name": {
                            "value": {
                                "value": "@pipeline().parameters.data_agent_name",
                                "type": "Expression"
                            },
                            "type": "string"
                        },
                        "lakehouse_name": {
                            "value": {
                                "value": "@pipeline().parameters.lakehouse_name",
                                "type": "Expression"
                            },
                            "type": "string"
                        }
                    }
                }
            }
        ],
        "parameters": {
            "data_agent_name": {
                "type": "string",
                "defaultValue": "my_data_agent"
            },
            "lakehouse_name": {
                "type": "string", 
                "defaultValue": lakehouse_name
            }
        },
    }
}


pipeline_base64 = base64.b64encode(json.dumps(pipeline_json).encode('utf-8'))

pipeline_data = {
        "displayName":pipeline_name,
        "type":"DataPipeline",
        "definition" : {
            # "format": "json",
            "parts": [
                {
                    "path": "pipeline-content.json",
                    "payload": pipeline_base64.decode('utf-8'),
                    "payloadType": "InlineBase64"
                }
            ]
        }
    }

pipeline_response = requests.post(fabric_items_url, headers=fabric_headers, json=pipeline_data)
pipeline_response.json()
pipeline_nb_id = pipeline_response.json()['id']
print('pipeline for notebook id: ', pipeline_nb_id)

# run the pipeline once
job_url = fabric_base_url + f"items/{pipeline_nb_id}/jobs/instances?jobType=Pipeline"
# f"items/{pipeline_id}/jobs/instances?jobType=Pipeline"
job_response = requests.post(job_url, headers=fabric_headers)


print(job_response)

if job_response.status_code == 202:
    print("pipeline run accepted with status 202")
    
    retry_url = job_response.headers.get("Location")

    # wait_seconds = 20
    wait_seconds = int(job_response.headers.get("Retry-After"))
    attempt = 1
    status = ''
    while (status != 'Completed') and (status != 'Failed'):
        print(f"Polling attempt {attempt}...")
        time.sleep(wait_seconds)
        retry_response = requests.get(retry_url, headers=fabric_headers)
        print(retry_response.json())
        # wait_seconds = int(retry_response.headers.get("Retry-After"))
        status = retry_response.json()['status']
        print(status)
        attempt += 1
        # if attempt % 2 == 0:
        #     fabric_headers = get_fabric_headers()

    print('pipeline run completed',retry_response.json()['status'])

elif job_response.status_code == 200:
    print('pipeline run completed')
else:
    print(f"pipeline run request failed with status: {job_response.status_code}")
    print('pipeline job response: ',job_response.text)


# get all items
items_res = requests.get(fabric_items_url, headers=fabric_headers)
print(items_res.json())
artifact_id = ''
for item in items_res.json()['value']:
    if item['displayName'] == 'my_data_agent':
        artifact_id = item['id']
        print('data agent id: ', artifact_id) 