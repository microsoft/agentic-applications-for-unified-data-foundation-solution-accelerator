"""Unit tests for auth_utils.py — token validation and identity extraction."""

import base64
import json
import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from auth import auth_utils
from auth.auth_utils import get_authenticated_user_details, get_tenantid


TEST_TENANT_ID = "11111111-1111-1111-1111-111111111111"
TEST_CLIENT_ID = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def rsa_keys():
    """Generate a fresh RSA keypair for signing test tokens."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem, private_key.public_key()


@pytest.fixture(autouse=True)
def configure_env(monkeypatch):
    """Configure OBO env vars and clear caches between tests."""
    monkeypatch.setenv("OBO_CLIENT_ID", TEST_CLIENT_ID)
    monkeypatch.setenv("OBO_TENANT_ID", TEST_TENANT_ID)
    with auth_utils._JWKS_LOCK:
        auth_utils._JWKS_CACHE.clear()
    yield
    with auth_utils._JWKS_LOCK:
        auth_utils._JWKS_CACHE.clear()


def _sign_token(private_pem, claims, kid="test-kid", headers=None):
    hdr = {"kid": kid}
    if headers:
        hdr.update(headers)
    return jwt.encode(claims, private_pem, algorithm="RS256", headers=hdr)


def _patch_signing_key(public_key):
    """Patch _get_signing_key so tests do not hit the network for JWKS."""
    return patch.object(auth_utils, "_get_signing_key", return_value=public_key)


def _standard_claims(overrides=None):
    now = int(time.time())
    claims = {
        "iss": f"https://sts.windows.net/{TEST_TENANT_ID}/",
        "aud": f"api://{TEST_CLIENT_ID}",
        "tid": TEST_TENANT_ID,
        "oid": "user-oid-1",
        "sub": "subject-1",
        "preferred_username": "user@example.com",
        "iat": now - 10,
        "nbf": now - 10,
        "exp": now + 3600,
    }
    if overrides:
        claims.update(overrides)
    return claims


class TestGetAuthenticatedUserDetails:
    """Tests for token-based authentication."""

    def test_valid_bearer_token_returns_identity(self, rsa_keys):
        private_pem, _, public_key = rsa_keys
        token = _sign_token(private_pem, _standard_claims())
        headers = {"Authorization": f"Bearer {token}"}

        with _patch_signing_key(public_key):
            result = get_authenticated_user_details(headers)

        assert result["user_principal_id"] == "user-oid-1"
        assert result["user_name"] == "user@example.com"
        assert result["auth_provider"] == "aad"
        assert result["aad_access_token"] == token
        assert result["tenant_id"] == TEST_TENANT_ID
        assert result["client_principal_b64"] is None

    def test_easyauth_injected_token_is_accepted(self, rsa_keys):
        private_pem, _, public_key = rsa_keys
        token = _sign_token(private_pem, _standard_claims())
        headers = {"x-ms-token-aad-access-token": token}

        with _patch_signing_key(public_key):
            result = get_authenticated_user_details(headers)

        assert result["user_principal_id"] == "user-oid-1"

    def test_bearer_token_takes_precedence_over_easyauth_header(self, rsa_keys):
        private_pem, _, public_key = rsa_keys
        bearer_claims = _standard_claims({"oid": "bearer-user"})
        bearer_token = _sign_token(private_pem, bearer_claims)
        easyauth_token = _sign_token(private_pem, _standard_claims({"oid": "easyauth-user"}))
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "x-ms-token-aad-access-token": easyauth_token,
        }

        with _patch_signing_key(public_key):
            result = get_authenticated_user_details(headers)

        assert result["user_principal_id"] == "bearer-user"

    def test_missing_token_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            get_authenticated_user_details({})
        assert exc_info.value.status_code == 401
        assert exc_info.value.headers.get("WWW-Authenticate") == "Bearer"

    def test_spoofed_principal_headers_are_ignored(self):
        """Client-supplied principal-id headers must NOT be used as identity."""
        headers = {
            "X-Ms-Client-Principal-Id": "attacker-user",
            "X-Ms-Client-Principal-Name": "attacker@evil.com",
        }
        with pytest.raises(HTTPException) as exc_info:
            get_authenticated_user_details(headers)
        assert exc_info.value.status_code == 401

    def test_expired_token_raises_401(self, rsa_keys):
        private_pem, _, public_key = rsa_keys
        claims = _standard_claims({"exp": int(time.time()) - 60})
        token = _sign_token(private_pem, claims)
        headers = {"Authorization": f"Bearer {token}"}

        with _patch_signing_key(public_key):
            with pytest.raises(HTTPException) as exc_info:
                get_authenticated_user_details(headers)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_wrong_audience_raises_401(self, rsa_keys):
        private_pem, _, public_key = rsa_keys
        claims = _standard_claims({"aud": "api://some-other-app"})
        token = _sign_token(private_pem, claims)
        headers = {"Authorization": f"Bearer {token}"}

        with _patch_signing_key(public_key):
            with pytest.raises(HTTPException) as exc_info:
                get_authenticated_user_details(headers)
        assert exc_info.value.status_code == 401

    def test_wrong_issuer_raises_401(self, rsa_keys):
        private_pem, _, public_key = rsa_keys
        claims = _standard_claims({"iss": "https://sts.windows.net/other-tenant/"})
        token = _sign_token(private_pem, claims)
        headers = {"Authorization": f"Bearer {token}"}

        with _patch_signing_key(public_key):
            with pytest.raises(HTTPException) as exc_info:
                get_authenticated_user_details(headers)
        assert exc_info.value.status_code == 401

    def test_cross_tenant_token_rejected(self, rsa_keys):
        """Token whose tid claim does not match OBO_TENANT_ID must be rejected."""
        private_pem, _, public_key = rsa_keys
        claims = _standard_claims({"tid": "33333333-3333-3333-3333-333333333333"})
        token = _sign_token(private_pem, claims)
        headers = {"Authorization": f"Bearer {token}"}

        with _patch_signing_key(public_key):
            with pytest.raises(HTTPException) as exc_info:
                get_authenticated_user_details(headers)
        assert exc_info.value.status_code == 401

    def test_token_missing_subject_raises_401(self, rsa_keys):
        private_pem, _, public_key = rsa_keys
        claims = _standard_claims()
        claims.pop("oid")
        claims.pop("sub")
        token = _sign_token(private_pem, claims)
        headers = {"Authorization": f"Bearer {token}"}

        with _patch_signing_key(public_key):
            with pytest.raises(HTTPException) as exc_info:
                get_authenticated_user_details(headers)
        assert exc_info.value.status_code == 401

    def test_v2_issuer_is_accepted(self, rsa_keys):
        private_pem, _, public_key = rsa_keys
        claims = _standard_claims({
            "iss": f"https://login.microsoftonline.com/{TEST_TENANT_ID}/v2.0"
        })
        token = _sign_token(private_pem, claims)
        headers = {"Authorization": f"Bearer {token}"}

        with _patch_signing_key(public_key):
            result = get_authenticated_user_details(headers)
        assert result["user_principal_id"] == "user-oid-1"

    def test_missing_configuration_returns_500(self, rsa_keys, monkeypatch):
        monkeypatch.delenv("OBO_CLIENT_ID", raising=False)
        private_pem, _, _ = rsa_keys
        token = _sign_token(private_pem, _standard_claims())
        headers = {"Authorization": f"Bearer {token}"}

        with pytest.raises(HTTPException) as exc_info:
            get_authenticated_user_details(headers)
        assert exc_info.value.status_code == 500

    def test_env_vars_resolved_lazily(self, rsa_keys, monkeypatch):
        """Config set after import (as ``load_dotenv`` does) must be honored."""
        private_pem, _, public_key = rsa_keys
        # Simulate a process that started with no OBO config (module import
        # would have captured empty values in the old bug) and later had
        # .env loaded.
        monkeypatch.delenv("OBO_CLIENT_ID", raising=False)
        monkeypatch.delenv("OBO_TENANT_ID", raising=False)
        token = _sign_token(private_pem, _standard_claims())
        auth_prefix = "Bear" + "er "
        headers = {"Authorization": auth_prefix + token}

        # First call: no config, must fail with 500.
        with pytest.raises(HTTPException) as exc_info:
            get_authenticated_user_details(headers)
        assert exc_info.value.status_code == 500

        # Config becomes available (as if load_dotenv just ran).
        monkeypatch.setenv("OBO_CLIENT_ID", TEST_CLIENT_ID)
        monkeypatch.setenv("OBO_TENANT_ID", TEST_TENANT_ID)

        # Second call: same module, same import, but now succeeds.
        with _patch_signing_key(public_key):
            result = get_authenticated_user_details(headers)
        assert result["user_principal_id"] == "user-oid-1"

    def test_falls_back_to_sub_when_oid_missing(self, rsa_keys):
        private_pem, _, public_key = rsa_keys
        claims = _standard_claims()
        claims.pop("oid")
        token = _sign_token(private_pem, claims)
        headers = {"Authorization": f"Bearer {token}"}

        with _patch_signing_key(public_key):
            result = get_authenticated_user_details(headers)
        assert result["user_principal_id"] == "subject-1"

    def test_case_insensitive_header_lookup(self, rsa_keys):
        private_pem, _, public_key = rsa_keys
        token = _sign_token(private_pem, _standard_claims())
        headers = {"AUTHORIZATION": f"Bearer {token}"}

        with _patch_signing_key(public_key):
            result = get_authenticated_user_details(headers)
        assert result["user_principal_id"] == "user-oid-1"

    def test_malformed_bearer_scheme_raises_401(self):
        headers = {"Authorization": "Basic dXNlcjpwYXNz"}
        with pytest.raises(HTTPException) as exc_info:
            get_authenticated_user_details(headers)
        assert exc_info.value.status_code == 401

    def test_telemetry_context_populated_on_success(self, rsa_keys):
        """Successful auth must set user_id_var and the active span attribute."""
        from telemetry_context import user_id_var

        private_pem, _, public_key = rsa_keys
        token = _sign_token(private_pem, _standard_claims({"oid": "telemetry-user"}))
        headers = {"Authorization": f"Bearer {token}"}

        recording_span = MagicMock()
        recording_span.is_recording.return_value = True

        # Reset the context var to a known state before the call
        user_id_var.set("")
        with _patch_signing_key(public_key), \
             patch.object(auth_utils.trace, "get_current_span", return_value=recording_span):
            get_authenticated_user_details(headers)

        assert user_id_var.get() == "telemetry-user"
        recording_span.set_attribute.assert_any_call("user_id", "telemetry-user")

    def test_telemetry_context_not_touched_on_failure(self, rsa_keys):
        """A rejected token must not overwrite the caller's user_id context."""
        from telemetry_context import user_id_var

        private_pem, _, public_key = rsa_keys
        # Expired token — validation will fail before enrichment runs.
        claims = _standard_claims({"exp": int(time.time()) - 60, "oid": "should-not-leak"})
        token = _sign_token(private_pem, claims)
        headers = {"Authorization": f"Bearer {token}"}

        user_id_var.set("previous-value")
        with _patch_signing_key(public_key):
            with pytest.raises(HTTPException):
                get_authenticated_user_details(headers)

        assert user_id_var.get() == "previous-value"


class TestJwksCaching:
    """Tests for JWKS caching and refresh behavior."""

    def test_jwks_is_cached(self):
        fake_jwks = {"keys": [{"kid": "k1"}]}
        response = MagicMock()
        response.json.return_value = fake_jwks
        response.raise_for_status.return_value = None

        with patch.object(auth_utils.requests, "get", return_value=response) as mock_get:
            first = auth_utils._fetch_jwks(TEST_TENANT_ID)
            second = auth_utils._fetch_jwks(TEST_TENANT_ID)

        assert first == fake_jwks
        assert second == fake_jwks
        assert mock_get.call_count == 1

    def test_jwks_fetch_failure_returns_503(self):
        with patch.object(
            auth_utils.requests, "get", side_effect=RuntimeError("boom")
        ):
            with pytest.raises(HTTPException) as exc_info:
                auth_utils._fetch_jwks(TEST_TENANT_ID)
        assert exc_info.value.status_code == 503


class TestGetTenantId:
    """Backward-compatible tenant id extractor."""

    def test_valid_base64_with_tid(self):
        token_data = {"tid": "tenant-123", "aud": "app-id"}
        encoded = base64.b64encode(json.dumps(token_data).encode()).decode()
        assert get_tenantid(encoded) == "tenant-123"

    def test_valid_base64_without_tid(self):
        token_data = {"aud": "app-id"}
        encoded = base64.b64encode(json.dumps(token_data).encode()).decode()
        assert get_tenantid(encoded) is None

    def test_empty_string(self):
        assert get_tenantid("") == ""

    def test_none_value(self):
        assert get_tenantid(None) == ""

    def test_invalid_base64(self):
        assert get_tenantid("invalid!!!base64") == ""

    def test_invalid_json(self):
        invalid_json = base64.b64encode(b"{invalid json}").decode()
        assert get_tenantid(invalid_json) == ""

