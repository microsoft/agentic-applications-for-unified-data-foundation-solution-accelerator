import requests
import time
import json
from azure.identity import AzureCliCredential
import argparse

# Parse command-line arguments
p = argparse.ArgumentParser(description="Delete Fabric workspace items created by create_fabric_items.py")
p.add_argument("--workspaceId", required=True, help="Fabric workspace ID")
p.add_argument("--solutionname", required=True, help="Solution name")
p.add_argument("--backend_app_pid", required=True, help="Backend app principal ID for role assignment removal")
args = p.parse_args()

workspaceId = args.workspaceId
solutionname = args.solutionname
backend_app_pid = args.backend_app_pid

def get_fabric_headers():
    """Get authentication headers for Fabric API"""
    credential = AzureCliCredential()
    cred = credential.get_token('https://api.fabric.microsoft.com/.default')
    token = cred.token
    fabric_headers = {"Authorization": "Bearer " + token.strip()}
    return fabric_headers

# Initialize
fabric_headers = get_fabric_headers()
fabric_base_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/"
fabric_items_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/items"
fabric_sql_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/sqlDatabases"
fabric_ra_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/roleAssignments"

print(f"Starting deletion process for workspace: {workspaceId}")
print("=" * 60)

# Step 1: Remove role assignment
print("\n[1/3] Removing role assignment for service principal...")
try:
    # Get all role assignments
    get_ra_url = f"{fabric_ra_url}/{backend_app_pid}"
    ra_response = requests.get(get_ra_url, headers=fabric_headers)

    if ra_response.status_code == 200:
        role_assignment_id = ra_response.json().get('id', None)
        
        if role_assignment_id:
            print(f"Found role assignment: {role_assignment_id}")

            # Delete the role assignment
            delete_ra_url = f"{fabric_ra_url}/{role_assignment_id}"
            delete_ra_response = requests.delete(delete_ra_url, headers=fabric_headers)

            if delete_ra_response.status_code == 200:
                print(f"✓ Role assignment removed successfully")
            else:
                print(f"⚠ Failed to remove role assignment. Status: {delete_ra_response.status_code}")
                print(f"Response: {delete_ra_response.text}")
        else:
            print(f"⚠ No role assignment found for principal ID: {backend_app_pid}")
    else:
        print(f"⚠ Failed to get role assignment. Status: {ra_response.status_code}")
        print(f"Response: {ra_response.text}")
        
except Exception as e:
    print(f"⚠ Error removing role assignment: {str(e)}")

# Refresh headers
fabric_headers = get_fabric_headers()

# Step 2: Delete SQL Database
sqldb_name = 'retail_sqldatabase_' + solutionname
print("\n[2/3] Deleting SQL Database...")
try:
    # Get all SQL databases
    sqldb_found = False
    next_url = fabric_sql_url
    
    while next_url and not sqldb_found:
        sqldb_response = requests.get(next_url, headers=fabric_headers)
        
        if sqldb_response.status_code == 200:
            response_data = sqldb_response.json()
            sql_databases = response_data.get('value', [])
            
            # Find the SQL database by name
            for sqldb in sql_databases:
                if sqldb['displayName'] == sqldb_name:
                    sqldb_id = sqldb['id']
                    print(f"Found SQL Database: {sqldb_name} (ID: {sqldb_id})")
                    
                    # Delete the SQL database
                    delete_sqldb_url = f"{fabric_sql_url}/{sqldb_id}"
                    delete_sqldb_response = requests.delete(delete_sqldb_url, headers=fabric_headers)
                    
                    if delete_sqldb_response.status_code in [200, 204]:
                        print(f"✓ SQL Database deleted successfully")
                        sqldb_found = True
                    else:
                        print(f"⚠ Failed to delete SQL Database. Status: {delete_sqldb_response.status_code}")
                        print(f"Response: {delete_sqldb_response.text}")
                    
                    break  # Stop after finding the first match
            
            # Check for next page
            next_url = response_data.get('continuationUri', None)
            
        else:
            print(f"⚠ Failed to list SQL Databases. Status: {sqldb_response.status_code}")
            print(f"Response: {sqldb_response.text}")
            break
    
    if not sqldb_found:
        print(f"⚠ No SQL Database found with name: {sqldb_name}")
        
except Exception as e:
    print(f"⚠ Error deleting SQL Database: {str(e)}")

# Refresh headers
fabric_headers = get_fabric_headers()

# Step 3: Delete Lakehouse
lakehouse_name = 'retail_lakehouse_' + solutionname
print("\n[3/3] Deleting Lakehouse...")
try:
    # Get all items with pagination support
    lakehouse_found = False
    next_url = fabric_items_url
    
    while next_url and not lakehouse_found:
        items_response = requests.get(next_url, headers=fabric_headers)
        
        if items_response.status_code == 200:
            response_data = items_response.json()
            items = response_data.get('value', [])
            
            # Find the lakehouse by name
            for item in items:
                if item['type'] == 'Lakehouse' and item['displayName'] == lakehouse_name:
                    lakehouse_id = item['id']
                    print(f"Found Lakehouse: {lakehouse_name} (ID: {lakehouse_id})")
                    
                    # Delete the lakehouse
                    delete_lakehouse_url = f"{fabric_items_url}/{lakehouse_id}"
                    delete_lakehouse_response = requests.delete(delete_lakehouse_url, headers=fabric_headers)
                    
                    if delete_lakehouse_response.status_code in [200, 204]:
                        print(f"✓ Lakehouse deleted successfully")
                        lakehouse_found = True
                    else:
                        print(f"⚠ Failed to delete Lakehouse. Status: {delete_lakehouse_response.status_code}")
                        print(f"Response: {delete_lakehouse_response.text}")
                    
                    break  # Stop after finding the first match
            
            # Check for next page
            next_url = response_data.get('continuationUri', None)
            
        else:
            print(f"⚠ Failed to list items. Status: {items_response.status_code}")
            print(f"Response: {items_response.text}")
            break
    
    if not lakehouse_found:
        print(f"⚠ No Lakehouse found with name: {lakehouse_name}")
        
except Exception as e:
    print(f"⚠ Error deleting Lakehouse: {str(e)}")

print("\n" + "=" * 60)
print("Deletion process completed!")
print("\nNote: App Service environment variables are NOT removed by this script.")
print("You may need to manually clean up FABRIC_SQL_* variables from your App Service.")
