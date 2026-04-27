import os
import logging
from azure.identity import ManagedIdentityCredential, DefaultAzureCredential, OnBehalfOfCredential
from azure.identity.aio import (
    ManagedIdentityCredential as AioManagedIdentityCredential,
    DefaultAzureCredential as AioDefaultAzureCredential,
    OnBehalfOfCredential as AioOnBehalfOfCredential
)

logger = logging.getLogger(__name__)

async def get_azure_credential_async(client_id=None, user_assertion=None):
    """
    Returns an Azure credential asynchronously based on the application environment.

    If user_assertion is provided and OBO is configured, uses OnBehalfOfCredential.
    If the environment is 'dev', it uses AioDefaultAzureCredential.
    Otherwise, it uses AioManagedIdentityCredential.

    Args:
        client_id (str, optional): The client ID for the Managed Identity Credential.
        user_assertion (str, optional): User's access token for OBO flow.

    Returns:
        Credential object: AioOnBehalfOfCredential, AioDefaultAzureCredential, or AioManagedIdentityCredential.
    """
    # Check if OBO should be used (user token provided and OBO configured)
    if user_assertion:
        obo_client_id = os.getenv("OBO_CLIENT_ID")
        obo_client_secret = os.getenv("OBO_CLIENT_SECRET")
        obo_tenant_id = os.getenv("OBO_TENANT_ID")
        
        if obo_client_id and obo_client_secret and obo_tenant_id:
            logger.info("Using On-Behalf-Of Credential for user assertion")
            return AioOnBehalfOfCredential(
                tenant_id=obo_tenant_id,
                client_id=obo_client_id,
                client_secret=obo_client_secret,
                user_assertion=user_assertion
            )
        else:
            logger.warning("OBO requested but OBO_CLIENT_ID, OBO_CLIENT_SECRET, or OBO_TENANT_ID not configured")
    
    if os.getenv("APP_ENV", "prod").lower() == 'dev':
        return AioDefaultAzureCredential()  # CodeQL [SM05139] Okay use of DefaultAzureCredential as it is only used in development
    else:
        return AioManagedIdentityCredential(client_id=client_id)

def get_azure_credential(client_id=None):
    """
    Returns an Azure credential based on the application environment.

    If the environment is 'dev', it uses DefaultAzureCredential.
    Otherwise, it uses ManagedIdentityCredential.

    Args:
        client_id (str, optional): The client ID for the Managed Identity Credential.

    Returns:
        Credential object: Either DefaultAzureCredential or ManagedIdentityCredential.
    """
    if os.getenv("APP_ENV", "prod").lower() == 'dev':
        return DefaultAzureCredential()  # CodeQL [SM05139] Okay use of DefaultAzureCredential as it is only used in development
    else:
        return ManagedIdentityCredential(client_id=client_id)
