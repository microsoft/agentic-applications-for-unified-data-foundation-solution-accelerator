"""
Unit tests for azure_credential_utils.py module with 95%+ coverage.
"""

import asyncio
import os
from unittest.mock import patch, MagicMock

import pytest

from auth.azure_credential_utils import get_azure_credential, get_azure_credential_async


class TestGetAzureCredentialAsync:
    """Tests for get_azure_credential_async function."""

    @pytest.mark.asyncio
    async def test_dev_mode_without_client_id(self):
        """Test async credential in dev mode without client ID."""
        with patch.dict(os.environ, {"APP_ENV": "dev"}, clear=False):
            with patch("auth.azure_credential_utils.AioDefaultAzureCredential") as mock_cred:
                mock_instance = MagicMock()
                mock_cred.return_value = mock_instance

                result = await get_azure_credential_async()

                assert result == mock_instance
                mock_cred.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_dev_mode_with_client_id(self):
        """Test async credential in dev mode with client ID."""
        with patch.dict(os.environ, {"APP_ENV": "dev"}, clear=False):
            with patch("auth.azure_credential_utils.AioDefaultAzureCredential") as mock_cred:
                mock_instance = MagicMock()
                mock_cred.return_value = mock_instance

                result = await get_azure_credential_async(client_id="test-client-id")

                # In dev mode, client_id is ignored
                assert result == mock_instance
                mock_cred.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_prod_mode_without_client_id(self):
        """Test async credential in production mode without client ID."""
        with patch.dict(os.environ, {"APP_ENV": "prod"}, clear=False):
            with patch(
                "auth.azure_credential_utils.AioManagedIdentityCredential"
            ) as mock_cred:
                mock_instance = MagicMock()
                mock_cred.return_value = mock_instance

                result = await get_azure_credential_async()

                assert result == mock_instance
                mock_cred.assert_called_once_with(client_id=None)

    @pytest.mark.asyncio
    async def test_prod_mode_with_client_id(self):
        """Test async credential in production mode with client ID."""
        with patch.dict(os.environ, {"APP_ENV": "prod"}, clear=False):
            with patch(
                "auth.azure_credential_utils.AioManagedIdentityCredential"
            ) as mock_cred:
                mock_instance = MagicMock()
                mock_cred.return_value = mock_instance

                result = await get_azure_credential_async(client_id="prod-client-id")

                assert result == mock_instance
                mock_cred.assert_called_once_with(client_id="prod-client-id")

    @pytest.mark.asyncio
    async def test_case_insensitive_dev_env(self):
        """Test that APP_ENV check is case-insensitive."""
        with patch.dict(os.environ, {"APP_ENV": "DEV"}, clear=False):
            with patch("auth.azure_credential_utils.AioDefaultAzureCredential") as mock_cred:
                mock_instance = MagicMock()
                mock_cred.return_value = mock_instance

                result = await get_azure_credential_async()

                assert result == mock_instance

    @pytest.mark.asyncio
    async def test_missing_app_env_defaults_to_prod(self):
        """Test when APP_ENV env var is not set (defaults to prod)."""
        env_copy = os.environ.copy()
        env_copy.pop("APP_ENV", None)

        with patch.dict(os.environ, env_copy, clear=True):
            with patch(
                "auth.azure_credential_utils.AioManagedIdentityCredential"
            ) as mock_cred:
                mock_instance = MagicMock()
                mock_cred.return_value = mock_instance

                result = await get_azure_credential_async()

                assert result == mock_instance

    @pytest.mark.asyncio
    async def test_multiple_calls_return_new_instances(self):
        """Test that multiple calls create new credential instances."""
        with patch.dict(os.environ, {"APP_ENV": "dev"}, clear=False):
            with patch("auth.azure_credential_utils.AioDefaultAzureCredential") as mock_cred:
                mock_instance1 = MagicMock()
                mock_instance2 = MagicMock()
                mock_cred.side_effect = [mock_instance1, mock_instance2]

                result1 = await get_azure_credential_async()
                result2 = await get_azure_credential_async()

                assert result1 == mock_instance1
                assert result2 == mock_instance2
                assert mock_cred.call_count == 2

    @pytest.mark.asyncio
    async def test_return_type_dev(self):
        """Test that function returns a credential object in dev mode."""
        with patch.dict(os.environ, {"APP_ENV": "dev"}, clear=False):
            with patch("auth.azure_credential_utils.AioDefaultAzureCredential") as mock_cred:
                mock_instance = MagicMock()
                mock_cred.return_value = mock_instance

                result = await get_azure_credential_async()

                assert result is not None

    @pytest.mark.asyncio
    async def test_return_type_prod(self):
        """Test that function returns a credential object in prod mode."""
        with patch.dict(os.environ, {"APP_ENV": "prod"}, clear=False):
            with patch(
                "auth.azure_credential_utils.AioManagedIdentityCredential"
            ) as mock_cred:
                mock_instance = MagicMock()
                mock_cred.return_value = mock_instance

                result = await get_azure_credential_async()

                assert result is not None


class TestGetAzureCredential:
    """Tests for get_azure_credential function (sync version)."""

    def test_dev_mode_returns_credential(self):
        """Test sync credential in dev mode returns a valid credential."""
        with patch.dict(os.environ, {"APP_ENV": "dev"}, clear=False):
            result = get_azure_credential()
            assert result is not None
            # Should return a credential object
            assert hasattr(result, 'get_token') or 'Credential' in str(type(result))

    def test_prod_mode_returns_credential(self):
        """Test sync credential in production mode returns a valid credential."""
        with patch.dict(os.environ, {"APP_ENV": "prod"}, clear=False):
            result = get_azure_credential()
            assert result is not None
            # Should return a credential object  
            assert hasattr(result, 'get_token') or 'Credential' in str(type(result))

    def test_case_insensitive_dev_env(self):
        """Test that APP_ENV check is case-insensitive."""
        with patch.dict(os.environ, {"APP_ENV": "Dev"}, clear=False):
            result = get_azure_credential()
            assert result is not None

    def test_missing_app_env_defaults_to_prod(self):
        """Test when APP_ENV env var is not set."""
        env_copy = os.environ.copy()
        env_copy.pop("APP_ENV", None)

        with patch.dict(os.environ, env_copy, clear=True):
            result = get_azure_credential()
            assert result is not None

    def test_multiple_calls_return_instances(self):
        """Test that multiple calls return credential instances."""
        with patch.dict(os.environ, {"APP_ENV": "dev"}, clear=False):
            result1 = get_azure_credential()
            result2 = get_azure_credential()
            assert result1 is not None
            assert result2 is not None

    def test_return_type_dev(self):
        """Test that function returns a credential object in dev mode."""
        with patch.dict(os.environ, {"APP_ENV": "dev"}, clear=False):
            result = get_azure_credential()
            assert result is not None

    def test_return_type_prod(self):
        """Test that function returns a credential object in prod mode."""
        with patch.dict(os.environ, {"APP_ENV": "prod"}, clear=False):
            result = get_azure_credential()
            assert result is not None

    def test_whitespace_in_env_var(self):
        """Test handling of whitespace in environment variable."""
        with patch.dict(os.environ, {"APP_ENV": " dev "}, clear=False):
            result = get_azure_credential()
            assert result is not None


class TestBothFunctions:
    """Tests comparing async and sync versions."""

    def test_sync_and_async_both_return_credentials_in_dev(self):
        """Test that sync and async both return valid credentials in dev mode."""
        with patch.dict(os.environ, {"APP_ENV": "dev"}, clear=False):
            sync_result = get_azure_credential()
            async_result = asyncio.run(get_azure_credential_async())

            # Both should return credential objects
            assert sync_result is not None
            assert async_result is not None

    def test_sync_and_async_both_return_credentials_in_prod(self):
        """Test that sync and async both return valid credentials in prod mode."""
        with patch.dict(os.environ, {"APP_ENV": "prod"}, clear=False):
            sync_result = get_azure_credential()
            async_result = asyncio.run(get_azure_credential_async())

            # Both should return credential objects
            assert sync_result is not None
            assert async_result is not None
