import base64
import json
import logging

logger = logging.getLogger(__name__)


def get_authenticated_user_details(request_headers):
    user_object = {}

    # Normalize all headers to lowercase for consistent lookup
    normalized_headers = {k.lower(): v for k, v in request_headers.items()}

    if "x-ms-client-principal-id" not in normalized_headers:
        # if it's not, assume we're in development mode and return a default user
        from . import sample_user

        raw_user_object = sample_user.sample_user
    else:
        # Use normalized headers for consistent key lookup
        raw_user_object = normalized_headers

    user_object["user_principal_id"] = raw_user_object.get("x-ms-client-principal-id")
    user_object["user_name"] = raw_user_object.get("x-ms-client-principal-name")
    user_object["auth_provider"] = raw_user_object.get("x-ms-client-principal-idp")
    user_object["auth_token"] = raw_user_object.get("x-ms-token-aad-id-token")
    user_object["client_principal_b64"] = raw_user_object.get("x-ms-client-principal")
    user_object["aad_id_token"] = raw_user_object.get("x-ms-token-aad-id-token")
    
    # Access token for OBO (On-Behalf-Of) flow - needed for Work IQ Teams
    # Try multiple sources: EasyAuth header first, then custom header from frontend
    easyauth_token = normalized_headers.get("x-ms-token-aad-access-token")
    zumo_token = normalized_headers.get("x-zumo-auth")
    
    if easyauth_token:
        user_object["aad_access_token"] = easyauth_token
        logger.info("Token source: x-ms-token-aad-access-token (EasyAuth)")
    elif zumo_token:
        user_object["aad_access_token"] = zumo_token
        logger.info("Token source: x-zumo-auth (frontend)")
    else:
        user_object["aad_access_token"] = None
        logger.warning("Token source: NONE - no access token found")

    return user_object


def get_tenantid(client_principal_b64):
    tenant_id = ""
    if client_principal_b64:
        try:
            # Decode the base64 header to get the JSON string
            decoded_bytes = base64.b64decode(client_principal_b64)
            decoded_string = decoded_bytes.decode("utf-8")
            # Convert the JSON string1into a Python dictionary
            user_info = json.loads(decoded_string)
            # Extract the tenant ID
            tenant_id = user_info.get("tid")  # 'tid' typically holds the tenant ID
        except Exception as ex:
            logging.exception(ex)
    return tenant_id
