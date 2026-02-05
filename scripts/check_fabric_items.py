"""Quick script to check existing Fabric items"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from load_env import load_all_env
load_all_env()

from azure.identity import AzureCliCredential
import requests

credential = AzureCliCredential()
token = credential.get_token('https://api.fabric.microsoft.com/.default').token
headers = {'Authorization': f'Bearer {token}'}

workspace_id = os.getenv('FABRIC_WORKSPACE_ID')
prefix = os.getenv('SOLUTION_PREFIX', 'demo')

print(f"Looking for items with prefix: {prefix}")
print()

# List lakehouses
resp = requests.get(f'https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/items?type=Lakehouse', headers=headers)
if resp.status_code == 200:
    print('Lakehouses:')
    for item in resp.json().get('value', []):
        if prefix in item['displayName']:
            print(f"  - {item['displayName']}")

# List ontologies
resp = requests.get(f'https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/ontologies', headers=headers)
if resp.status_code == 200:
    print('Ontologies:')
    for item in resp.json().get('value', []):
        if prefix in item['displayName']:
            print(f"  - {item['displayName']}")
