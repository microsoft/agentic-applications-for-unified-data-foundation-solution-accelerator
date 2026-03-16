"""
Unit tests for the attach_trace_attributes middleware in app.py.
"""
# pylint: disable=redefined-outer-name

import json
import os
import sys
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


# Ensure the API Python path is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../api/python')))


@pytest.fixture
def test_env_vars(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("AZURE_AI_AGENT_ENDPOINT", "https://test.azure.com")
    monkeypatch.setenv("AGENT_NAME_TITLE", "TestTitleAgent")
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "false")
    monkeypatch.setenv("FABRIC_SQL_DATABASE", "testdb")
    monkeypatch.setenv("FABRIC_SQL_SERVER", "testserver")


@pytest.fixture
def app_instance(test_env_vars):
    """Create a FastAPI app instance for testing."""
    from app import build_app
    return build_app()


@pytest.fixture
def test_client(app_instance):
    """Create a test client for the FastAPI app."""
    return TestClient(app_instance)


class TestAttachTraceAttributesMiddleware:
    """Tests for the attach_trace_attributes middleware."""

    def test_get_request_passes_through(self, test_client):
        """Test that middleware doesn't break normal GET requests."""
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_post_with_invalid_json_body_doesnt_crash(self, test_client):
        """Test POST with non-JSON body doesn't crash middleware."""
        response = test_client.post(
            "/health",
            content=b"not-json",
            headers={"content-type": "text/plain"}
        )
        assert response.status_code in (200, 405)

    def test_middleware_sets_user_id_span_attribute(self, test_client):
        """Test that user_id from auth header is set on the OTel span."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        with patch("app.trace.get_current_span", return_value=mock_span):
            response = test_client.get(
                "/health",
                headers={"x-ms-client-principal-id": "test-user-123"}
            )
        assert response.status_code == 200
        mock_span.set_attribute.assert_any_call("user_id", "test-user-123")

    def test_middleware_sets_conversation_id_span_attribute(self, test_client):
        """Test that conversation_id from POST body is set on the OTel span."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        with patch("app.trace.get_current_span", return_value=mock_span):
            response = test_client.post(
                "/health",
                json={"conversation_id": "conv-456", "query": "test"},
            )
        # 405 is expected for POST /health, but middleware should still run
        assert response.status_code in (200, 405)
        mock_span.set_attribute.assert_any_call("conversation_id", "conv-456")

    def test_middleware_registered_in_app(self, app_instance):
        """Test that the app has user_middleware configured."""
        assert len(app_instance.user_middleware) > 0
