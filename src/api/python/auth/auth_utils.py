import base64
import json
import logging


def get_authenticated_user_details(request_headers):
    user_object = {}

    normalized_headers = {k.lower(): v for k, v in request_headers.items()}

    # Log incoming auth-related headers for debugging
    auth_header_keys = [k for k in normalized_headers if k.startswith("x-ms-")]
    logging.info("Incoming x-ms-* header keys: %s", auth_header_keys)

    if "x-ms-client-principal-id" not in normalized_headers:
        # if it's not, assume we're in development mode and return a default user
        from . import sample_user

        raw_user_object = {k.lower(): v for k, v in sample_user.sample_user.items()}
        # Merge real incoming headers so tokens from the frontend are preserved
        raw_user_object.update(normalized_headers)
    else:
        # if it is, get the user details from the EasyAuth headers
        raw_user_object = normalized_headers

    user_object["user_principal_id"] = raw_user_object.get("x-ms-client-principal-id")
    user_object["user_name"] = raw_user_object.get("x-ms-client-principal-name")
    user_object["auth_provider"] = raw_user_object.get("x-ms-client-principal-idp")
    user_object["auth_token"] = raw_user_object.get("x-ms-token-aad-id-token")
    user_object["client_principal_b64"] = raw_user_object.get("x-ms-client-principal")
    user_object["aad_id_token"] = raw_user_object.get("x-ms-token-aad-id-token")
    user_object["aad_id_token"] = raw_user_object.get("x-ms-token-aad-id-token")
    user_object["aad_access_token"] = raw_user_object.get("x-ms-token-aad-access-token")

    logging.info(
        "Authenticated user details - user_principal_id: %s, user_name: %s, auth_provider: %s, "
        "aad_id_token present: %s, aad_access_token present: %s, client_principal_b64 present: %s",
        user_object.get("user_principal_id"),
        user_object.get("user_name"),
        user_object.get("auth_provider"),
        bool(user_object.get("aad_id_token")),
        bool(user_object.get("aad_access_token")),
        bool(user_object.get("client_principal_b64")),
    )

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
