"""Token-based authentication utilities.

Validates Entra ID (Azure AD) bearer access tokens using JWKS and derives the
authenticated user identity exclusively from validated token claims.

Environment variables (resolved lazily on every request so that values written
to ``.env`` and loaded by ``load_dotenv()`` after this module is imported are
picked up correctly):
    OBO_CLIENT_ID: Application (client) ID of the API app registration. Used to
        build the expected token audience ``api://{OBO_CLIENT_ID}``.
    OBO_TENANT_ID: Tenant (directory) ID that must issue the token.
"""

import base64
import json
import logging
import os
import time
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

import jwt
import requests
from fastapi import HTTPException, status
from opentelemetry import trace

from telemetry_context import user_id_var

logger = logging.getLogger(__name__)

_JWKS_CACHE_TTL_SECONDS = 3600
_JWKS_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_JWKS_LOCK = Lock()

_UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}


def _get_obo_client_id() -> str:
    """Return OBO_CLIENT_ID from the current environment (lazy resolution)."""
    return (os.getenv("OBO_CLIENT_ID") or "").strip()


def _get_obo_tenant_id() -> str:
    """Return OBO_TENANT_ID from the current environment (lazy resolution)."""
    return (os.getenv("OBO_TENANT_ID") or "").strip()


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers=_UNAUTHORIZED_HEADERS,
    )


def _jwks_url(tenant_id: str) -> str:
    return f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"


def _fetch_jwks(tenant_id: str) -> Dict[str, Any]:
    """Fetch and cache JWKS for a tenant. Cache is TTL-bounded and thread-safe."""
    now = time.time()
    with _JWKS_LOCK:
        cached = _JWKS_CACHE.get(tenant_id)
        if cached and cached[0] > now:
            return cached[1]

    try:
        response = requests.get(_jwks_url(tenant_id), timeout=10)
        response.raise_for_status()
        jwks = response.json()
    except Exception as exc:
        logger.exception("Failed to fetch JWKS for tenant %s", tenant_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication provider unavailable",
        ) from exc

    with _JWKS_LOCK:
        _JWKS_CACHE[tenant_id] = (time.time() + _JWKS_CACHE_TTL_SECONDS, jwks)
    return jwks


def _invalidate_jwks(tenant_id: str) -> None:
    with _JWKS_LOCK:
        _JWKS_CACHE.pop(tenant_id, None)


def _get_signing_key(token: str, tenant_id: str):
    """Locate the JWKS entry whose ``kid`` matches the token header."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        raise _unauthorized("Invalid token header") from exc

    kid = header.get("kid")
    if not kid:
        raise _unauthorized("Token missing key id")

    for attempt in range(2):
        jwks = _fetch_jwks(tenant_id)
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
        # Key rotation: drop cache and retry once
        _invalidate_jwks(tenant_id)

    raise _unauthorized("Signing key not found")


def _allowed_audiences() -> List[str]:
    client_id = _get_obo_client_id()
    if not client_id:
        return []
    return [f"api://{client_id}", client_id]


def _allowed_issuers(tenant_id: str) -> List[str]:
    if not tenant_id:
        return []
    return [
        f"https://sts.windows.net/{tenant_id}/",
        f"https://login.microsoftonline.com/{tenant_id}/v2.0",
    ]


def _validate_access_token(token: str) -> Dict[str, Any]:
    """Verify the token signature and standard claims. Returns validated claims."""
    client_id = _get_obo_client_id()
    tenant_id = _get_obo_tenant_id()
    if not client_id or not tenant_id:
        logger.error(
            "OBO_CLIENT_ID/OBO_TENANT_ID not configured; refusing to authenticate."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication is not configured on the server",
        )

    signing_key = _get_signing_key(token, tenant_id)
    allowed_issuers = _allowed_issuers(tenant_id)
    last_error: Optional[Exception] = None
    claims: Optional[Dict[str, Any]] = None

    # PyJWT accepts only a single issuer string; try each accepted issuer.
    for issuer in allowed_issuers:
        try:
            claims = jwt.decode(
                token,
                key=signing_key,
                algorithms=["RS256"],
                audience=_allowed_audiences(),
                issuer=issuer,
                options={"require": ["exp", "iss", "aud"]},
            )
            break
        except jwt.ExpiredSignatureError as exc:
            raise _unauthorized("Token has expired") from exc
        except jwt.InvalidIssuerError as exc:
            last_error = exc
            continue
        except jwt.InvalidTokenError as exc:
            last_error = exc
            break

    if claims is None:
        logger.warning("Token validation failed: %s", last_error)
        raise _unauthorized("Invalid token")

    tid = claims.get("tid")
    if tid != tenant_id:
        raise _unauthorized("Token tenant not permitted")

    return claims


def _extract_bearer_token(headers: Dict[str, str]) -> Optional[str]:
    """Extract a bearer token from the Authorization header or EasyAuth injection."""
    normalized = {str(k).lower(): v for k, v in headers.items()}

    authorization = normalized.get("authorization", "") or ""
    scheme, _, bearer = authorization.partition(" ")
    if scheme.lower() == "bearer" and bearer.strip():
        return bearer.strip()

    easyauth_token = normalized.get("x-ms-token-aad-access-token")
    if easyauth_token and easyauth_token.strip():
        return easyauth_token.strip()

    return None


def get_authenticated_user_details(request_headers) -> Dict[str, Any]:
    """Return authenticated user details derived from a validated access token.

    The returned ``user_principal_id`` is always sourced from the token's ``oid``
    (falling back to ``sub``) claim, never from ``x-ms-client-principal-*``
    request headers.

    Args:
        request_headers: A mapping-like object of HTTP headers (case-insensitive
            keys as provided by Starlette/FastAPI).

    Returns:
        A dictionary containing the authenticated user's principal id, display
        name, tenant id, the raw access token (for OBO downstream calls), and
        the full set of validated claims.

    Raises:
        HTTPException: 401 when no bearer token is present or the token fails
            signature, issuer, audience, expiration, or tenant validation.
    """
    if hasattr(request_headers, "items"):
        headers_dict = {str(k): v for k, v in request_headers.items()}
    else:
        headers_dict = dict(request_headers)

    token = _extract_bearer_token(headers_dict)
    if not token:
        raise _unauthorized("Authentication required")

    claims = _validate_access_token(token)

    user_principal_id = claims.get("oid") or claims.get("sub")
    if not user_principal_id:
        raise _unauthorized("Token missing subject")

    user_name = (
        claims.get("preferred_username")
        or claims.get("upn")
        or claims.get("email")
        or claims.get("unique_name")
        or claims.get("name")
    )

    # Enrich the request-scoped logging + tracing context with the validated
    # identity. This is done here (rather than in an HTTP middleware) so that
    # user_id is derived exclusively from a signature-verified token — never
    # from client-supplied headers — and every route that authenticates
    # automatically gets telemetry enrichment without extra bookkeeping.
    try:
        user_id_var.set(str(user_principal_id))
        span = trace.get_current_span()
        if span is not None and span.is_recording():
            span.set_attribute("user_id", str(user_principal_id))
    except Exception:  # pragma: no cover - defensive; telemetry must never break auth
        logger.debug("Failed to enrich telemetry context with user_id", exc_info=True)

    return {
        "user_principal_id": user_principal_id,
        "user_name": user_name,
        "auth_provider": "aad",
        "auth_token": token,
        "client_principal_b64": None,
        "aad_id_token": None,
        "aad_access_token": token,
        "tenant_id": claims.get("tid"),
        "claims": claims,
    }


def get_tenantid(client_principal_b64):
    """Extract the tenant id from a base64-encoded EasyAuth client principal.

    Retained for compatibility with telemetry helpers. Do not use for
    authorization decisions.
    """
    tenant_id = ""
    if client_principal_b64:
        try:
            decoded_bytes = base64.b64decode(client_principal_b64)
            decoded_string = decoded_bytes.decode("utf-8")
            user_info = json.loads(decoded_string)
            tenant_id = user_info.get("tid")
        except Exception as ex:
            logging.exception(ex)
    return tenant_id

