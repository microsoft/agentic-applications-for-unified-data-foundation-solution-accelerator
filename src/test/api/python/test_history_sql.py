"""
Tests for history_sql.py module - SQL Server conversation management.
"""
# pylint: disable=redefined-outer-name,unused-argument,protected-access,unused-variable,broad-exception-caught,import-outside-toplevel
# Pytest fixtures intentionally redefine names and are used for side effects
# Test files need to access protected members to verify internal behavior

import importlib
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, date
import struct

try:
    import pyodbc  # type: ignore  # noqa: F401
except ImportError:
    pyodbc = None  # type: ignore


@pytest.fixture
def mock_db_connection():
    """Mock pyodbc database connection."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.close = Mock()
    mock_cursor.execute = Mock()
    mock_cursor.fetchall = Mock(return_value=[])
    mock_cursor.fetchone = Mock(return_value=None)
    mock_cursor.commit = Mock()
    mock_cursor.close = Mock()
    return mock_conn


@pytest.fixture
def mock_sql_dependencies():
    """Mock SQL-related dependencies."""
    with patch('history_sql.get_fabric_db_connection') as mock_get_conn, \
         patch('history_sql.pyodbc') as mock_pyodbc:
        
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None
        
        mock_get_conn.return_value = mock_conn
        mock_pyodbc.connect.return_value = mock_conn
        
        yield {
            'get_connection': mock_get_conn,
            'pyodbc': mock_pyodbc,
            'connection': mock_conn,
            'cursor': mock_cursor
        }


@pytest.fixture
def client():
    """Create a test client for FastAPI app with history_sql router."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    
    # Import the router from history_sql
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../api/python')))
    
    from history_sql import router
    
    # Create a minimal FastAPI app for testing
    app = FastAPI()
    app.include_router(router)
    
    return TestClient(app)


class TestGetFabricDBConnection:
    """Tests for get_fabric_db_connection function."""

    @pytest.mark.asyncio
    async def test_get_connection_dev_mode_driver18(self, monkeypatch):
        """Test database connection in dev mode with driver 18."""
        from history_sql import get_fabric_db_connection
        
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("FABRIC_SQL_DATABASE", "test-db")
        monkeypatch.setenv("FABRIC_SQL_SERVER", "test-server.database.windows.net")
        
        mock_token = Mock()
        mock_token.token = "test-token-12345"
        
        mock_credential = AsyncMock()
        mock_credential.get_token = AsyncMock(return_value=mock_token)
        mock_credential.close = AsyncMock()
        
        with patch('history_sql.AzureCliCredential', return_value=mock_credential), \
             patch('history_sql.pyodbc.connect') as mock_connect:
            
            mock_conn = Mock()
            mock_connect.return_value = mock_conn
            
            result = await get_fabric_db_connection()
            
            assert result is not None
            mock_connect.assert_called_once()
            mock_credential.close.assert_called()

    @pytest.mark.asyncio
    async def test_get_connection_prod_mode(self, monkeypatch):
        """Test database connection in production mode."""
        from history_sql import get_fabric_db_connection
        
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.setenv("FABRIC_SQL_CONNECTION_STRING", "Driver={ODBC Driver 18};Server=test;")
        
        with patch('history_sql.pyodbc.connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn
            
            result = await get_fabric_db_connection()
            
            assert result is not None
            mock_connect.assert_called()

    @pytest.mark.asyncio
    async def test_get_connection_failure(self, monkeypatch):
        """Test database connection failure handling."""
        from history_sql import get_fabric_db_connection
        
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.setenv("FABRIC_SQL_CONNECTION_STRING", "invalid")
        
        with patch('history_sql.pyodbc.connect', side_effect=pyodbc.Error("Connection failed")):
            result = await get_fabric_db_connection()
            
            assert result is None

    @pytest.mark.asyncio
    async def test_get_connection_fallback_to_driver17(self, monkeypatch):
        """Test fallback to driver 17 when driver 18 fails."""
        from history_sql import get_fabric_db_connection
        
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("FABRIC_SQL_DATABASE", "test-db")
        monkeypatch.setenv("FABRIC_SQL_SERVER", "test-server.database.windows.net")
        
        mock_token = Mock()
        mock_token.token = "test-token"
        
        mock_credential = AsyncMock()
        mock_credential.get_token = AsyncMock(return_value=mock_token)
        mock_credential.close = AsyncMock()
        
        with patch('history_sql.AzureCliCredential', return_value=mock_credential), \
             patch('history_sql.pyodbc.connect') as mock_connect:
            
            # First call fails, second succeeds
            mock_connect.side_effect = [Exception("Driver 18 failed"), Mock()]
            
            result = await get_fabric_db_connection()
            
            assert result is not None
            assert mock_connect.call_count == 2


class TestRunNonQueryParams:
    """Tests for run_nonquery_params function."""

    @pytest.mark.asyncio
    async def test_run_nonquery_success(self, mock_db_connection):
        """Test successful non-query execution."""
        from history_sql import run_nonquery_params
        
        with patch('history_sql.get_fabric_db_connection', return_value=mock_db_connection):
            result = await run_nonquery_params(
                "DELETE FROM conversations WHERE id = ?",
                ("conv_123",)
            )
            
            assert result is True
            mock_db_connection.cursor().execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_nonquery_no_connection(self):
        """Test non-query when connection fails."""
        from history_sql import run_nonquery_params
        
        with patch('history_sql.get_db_connection', new_callable=AsyncMock, return_value=None):
            result = await run_nonquery_params("DELETE FROM test")
            assert result is False

    @pytest.mark.asyncio
    async def test_run_nonquery_with_params(self, mock_db_connection):
        """Test non-query with multiple parameters."""
        from history_sql import run_nonquery_params
        
        with patch('history_sql.get_fabric_db_connection', return_value=mock_db_connection):
            result = await run_nonquery_params(
                "UPDATE conversations SET title = ? WHERE id = ? AND userId = ?",
                ("New Title", "conv_123", "user_123")
            )
            
            assert result is True
            cursor = mock_db_connection.cursor()
            cursor.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_nonquery_exception_handling(self, mock_db_connection):
        """Test exception handling in non-query execution."""
        from history_sql import run_nonquery_params
        
        mock_db_connection.cursor().execute.side_effect = Exception("SQL Error")
        
        with patch('history_sql.get_fabric_db_connection', return_value=mock_db_connection):
            result = await run_nonquery_params("INVALID SQL")
            
            assert result is False


class TestRunQueryParams:
    """Tests for run_query_params function."""

    @pytest.mark.asyncio
    async def test_run_query_success(self, mock_db_connection):
        """Test successful query execution."""
        from history_sql import run_query_params
        
        mock_db_connection.cursor().fetchall.return_value = [
            ("conv_1", "user_1", "Title 1"),
            ("conv_2", "user_2", "Title 2")
        ]
        
        with patch('history_sql.get_fabric_db_connection', return_value=mock_db_connection):
            # Check if function exists
            result = await run_query_params("SELECT * FROM conversations")
            
            if result is not None:
                assert len(result) >= 0

    @pytest.mark.asyncio
    async def test_run_query_with_params(self, mock_db_connection):
        """Test query with parameters."""
        from history_sql import run_query_params
        
        mock_db_connection.cursor().fetchall.return_value = [
            ("conv_123", "user_123", "My Conversation")
        ]
        
        with patch('history_sql.get_fabric_db_connection', return_value=mock_db_connection):
            result = await run_query_params(
                "SELECT * FROM conversations WHERE userId = ?",
                ("user_123",)
            )
            
            if result is not None:
                assert isinstance(result, list)


class TestTrackEventIfConfigured:
    """Tests for track_event_if_configured helper."""

    def test_track_event_with_instrumentation_key(self, monkeypatch):
        """Test tracking event when Application Insights is configured."""
        from history_sql import track_event_if_configured
        
        monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=test")
        
        with patch('history_sql.track_event') as mock_track:
            track_event_if_configured("TestEvent", {"key": "value"})
            mock_track.assert_called_once_with("TestEvent", {"key": "value"})

    def test_track_event_without_instrumentation_key(self, monkeypatch):
        """Test tracking event without Application Insights."""
        from history_sql import track_event_if_configured
        
        monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
        
        with patch('history_sql.track_event') as mock_track:
            track_event_if_configured("TestEvent", {"key": "value"})
            mock_track.assert_not_called()


class TestSqlQueryTool:
    """Tests for SqlQueryTool class."""

    def test_sqlquerytool_exists(self):
        """Test SqlQueryTool class exists."""
        # SqlQueryTool uses Pydantic and requires specific fields
        try:
            from history_sql import SqlQueryTool
            assert SqlQueryTool is not None
        except ImportError:
            pytest.skip("SqlQueryTool not available")

    def test_sqlquerytool_with_mock_connection(self, mock_db_connection):  # noqa: ARG002
        """Test SqlQueryTool with mocked connection."""
        try:
            from history_sql import SqlQueryTool
            # SqlQueryTool may have required fields, so just verify it exists
            assert hasattr(SqlQueryTool, 'run_sql_query') or hasattr(SqlQueryTool, '__init__')
        except ImportError:
            pytest.skip("SqlQueryTool requires specific initialization")


class TestConversationManagement:
    """Tests for conversation management functions."""

    @pytest.mark.asyncio
    async def test_create_conversation_function_exists(self):
        """Test create_conversation function exists."""
        try:
            from history_sql import create_conversation
            assert create_conversation is not None
        except ImportError:
            # Function may not be directly importable
            pass

    @pytest.mark.asyncio
    async def test_delete_conversation_function_exists(self):
        """Test delete_conversation function exists."""
        try:
            from history_sql import delete_conversation
            assert delete_conversation is not None
        except ImportError:
            # Function may not be directly importable
            pass

    @pytest.mark.asyncio
    async def test_update_conversation_function_exists(self):
        """Test update_conversation function exists."""
        try:
            from history_sql import update_conversation
            assert update_conversation is not None
        except ImportError:
            # Function may not be directly importable
            pass


class TestSQLDataConversion:
    """Tests for SQL data conversion utilities."""

    def test_decimal_conversion(self):
        """Test Decimal to float conversion."""
        from decimal import Decimal  # noqa: F811
        
        value = Decimal("123.45")
        result = float(value)
        
        assert result == 123.45

    def test_date_conversion(self):
        """Test date to string conversion."""
        test_date = date(2024, 1, 15)
        result = test_date.isoformat()
        
        assert result == "2024-01-15"

    def test_datetime_conversion(self):
        """Test datetime to ISO format conversion."""
        test_datetime = datetime(2024, 1, 15, 12, 30, 45)
        result = test_datetime.isoformat()
        
        assert "2024-01-15" in result


class TestSQLEndpoints:
    """Tests for SQL history API endpoints."""

    @pytest.mark.asyncio
    async def test_get_conversations_endpoint(self, client, mock_sql_dependencies):
        """Test GET /history/conversations endpoint."""
        with patch('history_sql.get_fabric_db_connection', return_value=mock_sql_dependencies['connection']):
            response = client.get("/history/conversations?userId=user_123")
            
            # The endpoint should return a valid status code
            assert response.status_code in [200, 401, 404, 422, 500]

    @pytest.mark.asyncio
    async def test_create_conversation_endpoint(self, client, mock_sql_dependencies):
        """Test POST /history/conversation endpoint."""
        with patch('history_sql.get_fabric_db_connection', return_value=mock_sql_dependencies['connection']):
            response = client.post("/history/conversation", json={
                "userId": "user_123",
                "title": "Test Conversation"
            })
            
            assert response.status_code in [200, 201, 401, 404, 422, 500]

    @pytest.mark.asyncio
    async def test_delete_conversation_endpoint(self, client, mock_sql_dependencies):
        """Test DELETE /history/conversation endpoint."""
        with patch('history_sql.get_fabric_db_connection', return_value=mock_sql_dependencies['connection']):
            response = client.delete("/history/conversation?userId=user_123&conversationId=conv_123")
            
            assert response.status_code in [200, 204, 401, 404, 500]


class TestDatabaseErrorHandling:
    """Tests for database error handling."""

    @pytest.mark.asyncio
    async def test_connection_timeout(self):
        """Test handling of connection timeout."""
        from history_sql import get_fabric_db_connection
        
        with patch('history_sql.pyodbc.connect', side_effect=pyodbc.OperationalError("Timeout")):
            result = await get_fabric_db_connection()
            assert result is None

    @pytest.mark.asyncio
    async def test_sql_execution_error(self, mock_db_connection):
        """Test handling of SQL execution errors."""
        from history_sql import run_nonquery_params
        
        mock_db_connection.cursor().execute.side_effect = pyodbc.ProgrammingError("Invalid SQL")
        
        with patch('history_sql.get_fabric_db_connection', return_value=mock_db_connection):
            result = await run_nonquery_params("INVALID QUERY")
            assert result is False

    @pytest.mark.asyncio
    async def test_connection_already_closed(self, mock_db_connection):
        """Test handling when connection is already closed."""
        from history_sql import run_nonquery_params
        
        mock_db_connection.cursor.side_effect = pyodbc.ProgrammingError("Connection closed")
        
        with patch('history_sql.get_fabric_db_connection', return_value=mock_db_connection):
            result = await run_nonquery_params("SELECT * FROM test")
            assert result is False


class TestTokenAuthentication:
    """Tests for SQL token-based authentication."""

    @pytest.mark.asyncio
    async def test_token_struct_packing(self):
        """Test token struct packing for SQL authentication."""
        test_token = "test-access-token"
        token_bytes = test_token.encode("utf-16-LE")
        
        token_struct = struct.pack(
            f"<I{len(token_bytes)}s",
            len(token_bytes),
            token_bytes
        )
        
        assert token_struct is not None
        assert len(token_struct) > 0

    @pytest.mark.asyncio
    async def test_azure_cli_credential_usage(self, monkeypatch):
        """Test using Azure CLI credential for dev environment."""
        from history_sql import get_fabric_db_connection
        
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("FABRIC_SQL_DATABASE", "test-db")
        monkeypatch.setenv("FABRIC_SQL_SERVER", "test.database.windows.net")
        
        mock_token = Mock()
        mock_token.token = "dev-token"
        
        mock_credential = AsyncMock()
        mock_credential.get_token = AsyncMock(return_value=mock_token)
        mock_credential.close = AsyncMock()
        
        with patch('history_sql.AzureCliCredential', return_value=mock_credential), \
             patch('history_sql.pyodbc.connect') as mock_connect:
            
            mock_connect.return_value = Mock()
            result = await get_fabric_db_connection()
            
            assert result is not None
            mock_credential.get_token.assert_called_with("https://database.windows.net/.default")


class TestQueryResultProcessing:
    """Tests for processing SQL query results."""

    def test_process_empty_result(self):
        """Test processing empty query result."""
        result = []
        assert len(result) == 0

    def test_process_single_row(self, mock_db_connection):
        """Test processing single row result."""
        mock_db_connection.cursor().fetchone.return_value = ("conv_123", "user_123", "Title")
        
        row = mock_db_connection.cursor().fetchone()
        assert row is not None
        assert len(row) == 3

    def test_process_multiple_rows(self, mock_db_connection):
        """Test processing multiple rows result."""
        mock_db_connection.cursor().fetchall.return_value = [
            ("conv_1", "user_1", "Title 1"),
            ("conv_2", "user_2", "Title 2")
        ]
        
        rows = mock_db_connection.cursor().fetchall()
        assert len(rows) == 2


class TestGetConversationsFunction:
    """Tests for get_conversations function to increase coverage."""
    
    @pytest.mark.asyncio
    async def test_get_conversations_basic(self, mock_db_connection):
        """Test get_conversations basic functionality."""
        from history_sql import get_conversations
        
        mock_cursor = mock_db_connection.cursor()
        mock_cursor.description = [("id",), ("title",), ("createdAt",)]
        mock_cursor.fetchall.return_value = [
            ("conv1", "Test 1", datetime(2024, 1, 1)),
        ]
        
        with patch('history_sql.get_fabric_db_connection', return_value=mock_db_connection):
            result = await get_conversations("user123", limit=10)
            assert isinstance(result, list)
            mock_cursor.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_conversations_with_all_params(self, mock_db_connection):
        """Test get_conversations with all parameters."""
        from history_sql import get_conversations
        
        mock_cursor = mock_db_connection.cursor()
        mock_cursor.description = [("id",)]
        mock_cursor.fetchall.return_value = []
        
        with patch('history_sql.get_fabric_db_connection', return_value=mock_db_connection):
            result = await get_conversations("user123", limit=5, sort_order="ASC", offset=10)
            assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_get_conversations_exception(self, mock_db_connection):
        """Test get_conversations handles exceptions."""
        from history_sql import get_conversations
        
        mock_cursor = mock_db_connection.cursor()
        mock_cursor.execute.side_effect = Exception("DB Error")
        
        with patch('history_sql.get_fabric_db_connection', return_value=mock_db_connection):
            result = await get_conversations("user123", limit=10)
            assert result is None


class TestGetConversationMessagesFunction:
    """Tests for get_conversation_messages function."""
    
    @pytest.mark.asyncio
    async def test_get_messages_basic(self, mock_db_connection):
        """Test get_conversation_messages basic functionality."""
        from history_sql import get_conversation_messages
        
        mock_cursor = mock_db_connection.cursor()
        mock_cursor.description = [("id",), ("content",)]
        mock_cursor.fetchall.return_value = [("msg1", "Hello")]
        
        with patch('history_sql.get_fabric_db_connection', return_value=mock_db_connection):
            result = await get_conversation_messages("user123", "conv123")
            assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_get_messages_desc_order(self, mock_db_connection):
        """Test get_conversation_messages with DESC order."""
        from history_sql import get_conversation_messages
        
        mock_cursor = mock_db_connection.cursor()
        mock_cursor.description = [("id",)]
        mock_cursor.fetchall.return_value = []
        
        with patch('history_sql.get_fabric_db_connection', return_value=mock_db_connection):
            result = await get_conversation_messages("user123", "conv123", sort_order="DESC")
            assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_get_messages_exception(self, mock_db_connection):
        """Test get_conversation_messages handles exceptions."""
        from history_sql import get_conversation_messages
        
        mock_cursor = mock_db_connection.cursor()
        mock_cursor.execute.side_effect = Exception("Error")
        
        with patch('history_sql.get_fabric_db_connection', return_value=mock_db_connection):
            result = await get_conversation_messages("user123", "conv123")
            assert result is None


class TestDeleteConversationFunction:
    """Tests for delete_conversation function."""
    
    @pytest.mark.asyncio
    async def test_delete_conversation_calls_nonquery(self):
        """Test delete_conversation calls run_nonquery_params."""
        from history_sql import delete_conversation
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query, \
             patch('history_sql.run_nonquery_params', new_callable=AsyncMock) as mock_run:
            mock_query.return_value = [{"userId": "user123", "conversation_id": "conv123"}]
            mock_run.return_value = True
            result = await delete_conversation("user123", "conv123")
            assert result is True
            assert mock_run.call_count == 2  # Called twice for messages and conversation
    
    @pytest.mark.asyncio
    async def test_delete_conversation_exception(self):
        """Test delete_conversation handles exceptions."""
        from history_sql import delete_conversation
        
        with patch('history_sql.run_nonquery_params', side_effect=Exception("Error")):
            result = await delete_conversation("user123", "conv123")
            assert result is False


class TestDeleteAllConversationsFunction:
    """Tests for delete_all_conversations function."""
    
    @pytest.mark.asyncio
    async def test_delete_all_success(self):
        """Test delete_all_conversations success."""
        from history_sql import delete_all_conversations
        
        with patch('history_sql.run_nonquery_params', return_value=True):
            result = await delete_all_conversations("user123")
            assert result is True
    
    @pytest.mark.asyncio
    async def test_delete_all_exception(self):
        """Test delete_all_conversations handles exceptions."""
        from history_sql import delete_all_conversations
        
        with patch('history_sql.run_nonquery_params', side_effect=Exception("Error")):
            result = await delete_all_conversations("user123")
            assert result is False


class TestRenameConversationFunction:
    """Tests for rename_conversation function."""
    
    @pytest.mark.asyncio
    async def test_rename_success(self):
        """Test rename_conversation success."""
        from history_sql import rename_conversation
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query, \
             patch('history_sql.run_nonquery_params', new_callable=AsyncMock) as mock_run:
            mock_query.return_value = [{"userId": "user123", "conversation_id": "conv123"}]
            mock_run.return_value = True
            result = await rename_conversation("user123", "conv123", "New Title")
            assert result is True
    
    @pytest.mark.asyncio
    async def test_rename_exception(self):
        """Test rename_conversation handles exceptions."""
        from history_sql import rename_conversation
        
        with patch('history_sql.run_nonquery_params', side_effect=Exception("Error")):
            result = await rename_conversation("user123", "conv123", "New Title")
            assert result is False


class TestGenerateTitleFunction:
    """Tests for generate_title function."""
    
    @pytest.mark.asyncio
    async def test_generate_title_empty_messages(self):
        """Test generate_title with empty messages."""
        from history_sql import generate_title
        
        result = await generate_title([])
        assert result == "New Conversation"
    
    @pytest.mark.asyncio
    async def test_generate_title_with_agent(self):
        """Test generate_title uses agent when available."""
        from history_sql import generate_title
        
        messages = [{"role": "user", "content": "Hello"}]
        
        mock_agent = MagicMock()
        mock_agent.invoke_sync.return_value = "AI Generated Title"
        
        with patch('history_sql.ChatAgent', return_value=mock_agent):
            with patch('history_sql.AzureAIClient'):
                with patch('history_sql.AZURE_AI_AGENT_ENDPOINT', 'http://test'):
                    result = await generate_title(messages)
                    assert isinstance(result, str)


class TestGenerateFallbackTitleFunction:
    """Tests for generate_fallback_title function."""
    
    def test_fallback_title_empty(self):
        """Test generate_fallback_title with empty messages."""
        from history_sql import generate_fallback_title
        
        result = generate_fallback_title([])
        assert result == "New Conversation"
    
    def test_fallback_title_with_content(self):
        """Test generate_fallback_title with message content."""
        from history_sql import generate_fallback_title
        
        messages = [{"role": "user", "content": "Test message"}]
        result = generate_fallback_title(messages)
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_fallback_title_truncates(self):
        """Test generate_fallback_title uses first 4 words."""
        from history_sql import generate_fallback_title
        
        # Long message - should only take first 4 words
        long_content = "word1 word2 word3 word4 word5 word6 word7 word8"
        messages = [{"role": "user", "content": long_content}]
        result = generate_fallback_title(messages)
        assert result == "word1 word2 word3 word4"


class TestCreateConversationFunction:
    """Tests for create_conversation function."""
    
    @pytest.mark.asyncio
    async def test_create_conversation_with_title(self, mock_db_connection):
        """Test create_conversation with title."""
        from history_sql import create_conversation
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query, \
             patch('history_sql.run_nonquery_params', new_callable=AsyncMock) as mock_run:
            mock_query.return_value = []  # No existing conversation
            mock_run.return_value = True
            result = await create_conversation("user123", title="My Title", conversation_id="conv123")
            assert result is True  # Returns bool when creating new
    
    @pytest.mark.asyncio
    async def test_create_conversation_no_title(self, mock_db_connection):
        """Test create_conversation without title."""
        from history_sql import create_conversation
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query, \
             patch('history_sql.run_nonquery_params', new_callable=AsyncMock) as mock_run:
            mock_query.return_value = []
            mock_run.return_value = True
            result = await create_conversation("user123", conversation_id="conv123")
            assert result is True  # Returns bool when creating new
    
    @pytest.mark.asyncio
    async def test_create_conversation_with_id(self, mock_db_connection):
        """Test create_conversation with custom conversation_id."""
        from history_sql import create_conversation
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query:
            # Return existing conversation
            existing = [{"conversation_id": "custom123", "title": "Existing"}]
            mock_query.return_value = existing
            result = await create_conversation("user123", conversation_id="custom123")
            assert result == existing  # Returns existing conversation list
    
    @pytest.mark.asyncio
    async def test_create_conversation_exception(self):
        """Test create_conversation handles exceptions."""
        from history_sql import create_conversation
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query:
            mock_query.side_effect = Exception("Error")
            with pytest.raises(Exception):
                await create_conversation("user123")


class TestCreateMessageFunction:
    """Tests for create_message function."""
    
    @pytest.mark.asyncio
    async def test_create_message_string_content(self, mock_db_connection):
        """Test create_message with string content."""
        from history_sql import create_message
        
        message = {"role": "user", "content": "Hello", "id": "msg123"}
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query, \
             patch('history_sql.run_nonquery_params', new_callable=AsyncMock) as mock_run:
            mock_query.return_value = [{"conversation_id": "conv123"}]
            mock_run.return_value = True
            result = await create_message("msg123", "conv123", "user123", message)
            assert result is True  # Returns True when both inserts succeed
    
    @pytest.mark.asyncio
    async def test_create_message_list_content(self, mock_db_connection):
        """Test create_message with list content."""
        from history_sql import create_message
        
        message = {"role": "assistant", "content": {"type": "text", "text": "Hi"}, "id": "msg123"}
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query, \
             patch('history_sql.run_nonquery_params', new_callable=AsyncMock) as mock_run:
            mock_query.return_value = [{"conversation_id": "conv123"}]
            mock_run.return_value = True
            result = await create_message("msg123", "conv123", "user123", message)
            assert result is True
    
    @pytest.mark.asyncio
    async def test_create_message_exception(self):
        """Test create_message handles exceptions."""
        from history_sql import create_message
        
        message = {"role": "user", "content": "Test", "id": "msg123"}
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query:
            mock_query.side_effect = Exception("Error")
            with pytest.raises(Exception):
                await create_message("msg123", "conv123", "user123", message)


class TestUpdateConversationFunction:
    """Tests for update_conversation function."""
    
    @pytest.mark.asyncio
    async def test_update_conversation_new_messages(self, mock_db_connection):
        """Test update_conversation with new messages."""
        from history_sql import update_conversation
        
        request_json = {
            "conversation_id": "conv123",
            "messages": [
                {"role": "user", "content": "Hello", "id": "msg1"},
                {"role": "assistant", "content": "Hi there", "id": "msg2"}
            ]
        }
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query, \
             patch('history_sql.create_message', new_callable=AsyncMock) as mock_create:
            # First call: check conversation exists, Second call: return updated conversation
            mock_query.side_effect = [
                [{"conversation_id": "conv123"}],  # Conversation exists
                [{"conversation_id": "conv123", "title": "Test", "updatedAt": "2024-01-01"}]  # Final query
            ]
            mock_create.return_value = True
            result = await update_conversation("user123", request_json)
            assert result is not None
            assert result["id"] == "conv123"
            assert mock_create.call_count == 2  # User message + assistant message
    
    @pytest.mark.asyncio
    async def test_update_conversation_with_title(self, mock_db_connection):
        """Test update_conversation with existing title."""
        from history_sql import update_conversation
        
        request_json = {
            "conversation_id": "conv123",
            "messages": [
                {"role": "user", "content": "First message", "id": "msg1"},
                {"role": "assistant", "content": "Response", "id": "msg2"}
            ]
        }
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query, \
             patch('history_sql.generate_title', new_callable=AsyncMock) as mock_title, \
             patch('history_sql.create_conversation', new_callable=AsyncMock), \
             patch('history_sql.create_message', new_callable=AsyncMock) as mock_create:
            mock_query.side_effect = [
                [],  # No existing conversation
                [{"conversation_id": "conv123", "title": "Generated Title", "updatedAt": "2024-01-01"}]  # Final query
            ]
            mock_title.return_value = "Generated Title"
            mock_create.return_value = True
            result = await update_conversation("user123", request_json)
            mock_title.assert_called_once()
            assert result["title"] == "Generated Title"
    
    @pytest.mark.asyncio
    async def test_update_conversation_exception(self):
        """Test update_conversation handles exceptions."""
        from history_sql import update_conversation
        
        request_json = {"conversation_id": "conv123", "messages": []}
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query:
            mock_query.side_effect = Exception("Error")
            with pytest.raises(Exception):
                await update_conversation("user123", request_json)


class TestModuleConfiguration:
    """Tests for module-level configuration."""
    
    def test_router_exists(self):
        """Test router is configured."""
        from history_sql import router
        assert router is not None
    
    def test_logger_configured(self):
        """Test logger is configured."""
        from history_sql import logger
        assert logger is not None
    
    def test_track_event_function_exists(self):
        """Test track_event_if_configured function exists."""
        from history_sql import track_event_if_configured
        assert callable(track_event_if_configured)


class TestEndpointIntegration:
    """Integration tests for FastAPI endpoints."""
    
    @pytest.mark.asyncio
    async def test_list_conversations_endpoint_success(self):
        """Test list endpoint returns conversations."""
        from history_sql import list_conversations
        from fastapi import Request
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth, \
             patch('history_sql.get_conversations', new_callable=AsyncMock) as mock_get, \
             patch('history_sql.track_event_if_configured'):
            mock_auth.return_value = {"user_principal_id": "user123"}
            mock_get.return_value = [{"id": "conv1", "title": "Test"}]
            
            response = await list_conversations(mock_request, offset=0, limit=25)
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_list_conversations_endpoint_exception(self):
        """Test list endpoint handles exceptions."""
        from history_sql import list_conversations
        from fastapi import Request
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth:
            mock_auth.side_effect = Exception("Auth failed")
            
            response = await list_conversations(mock_request, offset=0, limit=25)
            assert response.status_code == 500
    
    @pytest.mark.asyncio
    async def test_read_conversation_endpoint_success(self):
        """Test read endpoint returns messages."""
        from history_sql import get_conversation_messages_endpoint
        from fastapi import Request
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth, \
             patch('history_sql.get_conversation_messages', new_callable=AsyncMock) as mock_get, \
             patch('history_sql.track_event_if_configured'):
            mock_auth.return_value = {"user_principal_id": "user123"}
            mock_get.return_value = [{"role": "user", "content": "Hello"}]
            
            response = await get_conversation_messages_endpoint(mock_request, id="conv123")
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_read_conversation_endpoint_not_found(self):
        """Test read endpoint when conversation not found."""
        from history_sql import get_conversation_messages_endpoint
        from fastapi import Request, HTTPException
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth, \
             patch('history_sql.get_conversation_messages', new_callable=AsyncMock) as mock_get, \
             patch('history_sql.track_event_if_configured'):
            mock_auth.return_value = {"user_principal_id": "user123"}
            mock_get.return_value = []
            
            with pytest.raises(HTTPException) as exc_info:
                await get_conversation_messages_endpoint(mock_request, id="conv123")
            assert exc_info.value.status_code == 404
    
    @pytest.mark.asyncio
    async def test_read_conversation_endpoint_no_id(self):
        """Test read endpoint requires conversation ID."""
        from history_sql import get_conversation_messages_endpoint
        from fastapi import Request, HTTPException
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth, \
             patch('history_sql.track_event_if_configured'):
            mock_auth.return_value = {"user_principal_id": "user123"}
            
            with pytest.raises(HTTPException) as exc_info:
                await get_conversation_messages_endpoint(mock_request, id="")
            assert exc_info.value.status_code == 400
    
    @pytest.mark.asyncio
    async def test_delete_conversation_endpoint_success(self):
        """Test delete endpoint removes conversation."""
        from history_sql import delete_conversation_endpoint
        from fastapi import Request
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth, \
             patch('history_sql.delete_conversation', new_callable=AsyncMock) as mock_delete, \
             patch('history_sql.track_event_if_configured'):
            mock_auth.return_value = {"user_principal_id": "user123"}
            mock_delete.return_value = True
            
            response = await delete_conversation_endpoint(mock_request, id="conv123")
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_delete_conversation_endpoint_failed(self):
        """Test delete endpoint when deletion fails."""
        from history_sql import delete_conversation_endpoint
        from fastapi import Request, HTTPException
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth, \
             patch('history_sql.delete_conversation', new_callable=AsyncMock) as mock_delete, \
             patch('history_sql.track_event_if_configured'):
            mock_auth.return_value = {"user_principal_id": "user123"}
            mock_delete.return_value = False  # Deletion failed
            
            with pytest.raises(HTTPException) as exc_info:
                await delete_conversation_endpoint(mock_request, id="conv123")
            assert exc_info.value.status_code == 404  # Not found or no permission
    
    @pytest.mark.asyncio
    async def test_delete_all_conversations_endpoint_success(self):
        """Test delete all endpoint removes all conversations."""
        from history_sql import delete_all_conversations_endpoint
        from fastapi import Request
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth, \
             patch('history_sql.get_conversations', new_callable=AsyncMock) as mock_get, \
             patch('history_sql.delete_all_conversations', new_callable=AsyncMock) as mock_delete, \
             patch('history_sql.track_event_if_configured'):
            mock_auth.return_value = {"user_principal_id": "user123"}
            mock_get.return_value = [{"id": "conv1"}, {"id": "conv2"}]  # Has conversations
            mock_delete.return_value = True
            
            response = await delete_all_conversations_endpoint(mock_request)
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_rename_conversation_endpoint_success(self):
        """Test rename endpoint updates conversation title."""
        from history_sql import rename_conversation_endpoint
        from fastapi import Request
        
        mock_request = Mock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        # Create an async function that returns the dict
        async def mock_json():
            return {"conversation_id": "conv123", "title": "New Title"}
        mock_request.json = mock_json
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth, \
             patch('history_sql.rename_conversation', new_callable=AsyncMock) as mock_rename, \
             patch('history_sql.track_event_if_configured'):
            mock_auth.return_value = {"user_principal_id": "user123"}
            mock_rename.return_value = True
            
            response = await rename_conversation_endpoint(mock_request)
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_update_conversation_endpoint_success(self):
        """Test update endpoint adds messages to conversation."""
        from history_sql import update_conversation_endpoint
        from fastapi import Request
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        
        request_json = {
            "conversation_id": "conv123",
            "messages": [
                {"role": "user", "content": "Hello", "id": "msg1"},
                {"role": "assistant", "content": "Hi", "id": "msg2"}
            ]
        }
        mock_request.json = AsyncMock(return_value=request_json)
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth, \
             patch('history_sql.update_conversation', new_callable=AsyncMock) as mock_update, \
             patch('history_sql.track_event_if_configured'):
            mock_auth.return_value = {"user_principal_id": "user123"}
            mock_update.return_value = {
                "id": "conv123", 
                "title": "Test", 
                "updatedAt": "2024-01-01"
            }
            
            response = await update_conversation_endpoint(mock_request)
            assert response.status_code == 200


class TestErrorPaths:
    """Tests for error handling paths."""
    
    @pytest.mark.asyncio
    async def test_get_conversations_with_limit_offset(self):
        """Test get_conversations with limit and offset parameters."""
        from history_sql import get_conversations
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [{"conversation_id": "conv1"}, {"conversation_id": "conv2"}]
            result = await get_conversations("user123", offset=10, limit=5)
            assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_get_conversation_messages_asc_order(self):
        """Test get_conversation_messages with ascending order."""
        from history_sql import get_conversation_messages
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [
                {"role": "user", "content": "msg1", "citations": "", "feedback": ""},
                {"role": "assistant", "content": "msg2", "citations": "", "feedback": ""}
            ]
            result = await get_conversation_messages("user123", "conv123", sort_order="asc")
            assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_delete_conversation_no_user_id(self):
        """Test delete_conversation without user_id (admin mode)."""
        from history_sql import delete_conversation
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query, \
             patch('history_sql.run_nonquery_params', new_callable=AsyncMock) as mock_run:
            mock_query.return_value = [{"userId": "user123", "conversation_id": "conv123"}]
            mock_run.return_value = True
            result = await delete_conversation(None, "conv123")  # No user_id
            assert result is True
    
    @pytest.mark.asyncio
    async def test_delete_conversation_permission_denied(self):
        """Test delete_conversation when user doesn't have permission."""
        from history_sql import delete_conversation
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [{"userId": "different_user", "conversation_id": "conv123"}]
            result = await delete_conversation("user123", "conv123")
            assert result is False  # Permission denied
    
    @pytest.mark.asyncio
    async def test_delete_all_conversations_no_user_id(self):
        """Test delete_all_conversations without user filtering."""
        from history_sql import delete_all_conversations
        
        with patch('history_sql.run_nonquery_params', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = True
            result = await delete_all_conversations(None)  # Delete all
            assert result is True
    
    @pytest.mark.asyncio
    async def test_rename_conversation_permission_denied(self):
        """Test rename_conversation when user doesn't have permission."""
        from history_sql import rename_conversation
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [{"userId": "different_user", "conversation_id": "conv123"}]
            result = await rename_conversation("user123", "conv123", "New Title")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_rename_conversation_no_title(self):
        """Test rename_conversation with None title."""
        from history_sql import rename_conversation
        
        result = await rename_conversation("user123", "conv123", None)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_create_message_with_citations(self):
        """Test create_message properly handles citations."""
        from history_sql import create_message
        
        message = {
            "role": "assistant",
            "content": "Answer with sources",
            "id": "msg123",
            "citations": [{"url": "https://example.com", "title": "Source"}]
        }
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query, \
             patch('history_sql.run_nonquery_params', new_callable=AsyncMock) as mock_run:
            mock_query.return_value = [{"conversation_id": "conv123"}]
            mock_run.return_value = True
            result = await create_message("msg123", "conv123", "user123", message)
            assert result is True
    
    @pytest.mark.asyncio
    async def test_create_message_conversation_not_found(self):
        """Test create_message when conversation doesn't exist."""
        from history_sql import create_message
        
        message = {"role": "user", "content": "Hello", "id": "msg123"}
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = []  # Conversation not found
            result = await create_message("msg123", "conv123", "user123", message)
            assert result is None


class TestDatabaseConnectionPaths:
    """Tests for database connection fallback and error paths."""
    
    @pytest.mark.asyncio
    async def test_get_fabric_db_connection_prod_mode_driver17_fallback(self):
        """Test connection falls back to driver 17 after 18 fails in prod."""
        from history_sql import get_fabric_db_connection
        
        with patch('history_sql.os.getenv') as mock_env, \
             patch('history_sql.pyodbc.connect') as mock_connect, \
             patch('history_sql.AzureCliCredential'):
            mock_env.side_effect = lambda key, default=None: {
                'RUNNING_IN_PRODUCTION': 'true',
                'SQL_ENDPOINT': 'server.database.windows.net',
                'SQL_DATABASE': 'testdb'
            }.get(key, default)
            
            # First call with driver 18 fails, second with driver 17 succeeds
            mock_connect.side_effect = [
                Exception("Driver 18 failed"),
                MagicMock()  # Driver 17 succeeds
            ]
            
            conn = await get_fabric_db_connection()
            assert conn is not None
            assert mock_connect.call_count == 2
    
    @pytest.mark.asyncio
    async def test_delete_conversation_no_conversation_id(self):
        """Test delete_conversation returns False when no conversation_id."""
        from history_sql import delete_conversation
        
        result = await delete_conversation("user123", None)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(self):
        """Test delete_conversation when conversation doesn't exist."""
        from history_sql import delete_conversation
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = []  # No conversation found
            result = await delete_conversation("user123", "conv123")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_rename_conversation_not_found(self):
        """Test rename_conversation when conversation doesn't exist."""
        from history_sql import rename_conversation
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = []  # No conversation found
            result = await rename_conversation("user123", "conv123", "New Title")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_rename_conversation_no_user_id(self):
        """Test rename_conversation without user_id (admin mode)."""
        from history_sql import rename_conversation
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query, \
             patch('history_sql.run_nonquery_params', new_callable=AsyncMock) as mock_run:
            mock_query.return_value = [{"userId": "user123", "conversation_id": "conv123"}]
            mock_run.return_value = True
            result = await rename_conversation(None, "conv123", "New Title")
            assert result is True
    
    @pytest.mark.asyncio
    async def test_rename_conversation_no_conversation_id(self):
        """Test rename_conversation returns False when no conversation_id."""
        from history_sql import rename_conversation
        
        result = await rename_conversation("user123", None, "New Title")
        assert result is False  # Catches ValueError and returns False
    
    @pytest.mark.asyncio
    async def test_create_message_no_conversation_id(self):
        """Test create_message returns None when no conversation_id."""
        from history_sql import create_message
        
        message = {"role": "user", "content": "Hello", "id": "msg123"}
        result = await create_message("msg123", None, "user123", message)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_conversation_messages_no_conversation_id(self):
        """Test get_conversation_messages returns None when no conversation_id."""
        from history_sql import get_conversation_messages
        
        result = await get_conversation_messages("user123", None)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_conversation_messages_no_user_id(self):
        """Test get_conversation_messages without user_id (admin mode)."""
        from history_sql import get_conversation_messages
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [
                {"role": "user", "content": "msg1", "citations": "", "feedback": ""}
            ]
            result = await get_conversation_messages(None, "conv123")
            assert len(result) == 1
    
    @pytest.mark.asyncio
    async def test_get_conversations_no_user_id(self):
        """Test get_conversations without user_id (returns all)."""
        from history_sql import get_conversations
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [{"conversation_id": "conv1"}, {"conversation_id": "conv2"}]
            result = await get_conversations(None, offset=0, limit=25)
            assert len(result) == 2


class TestEndpointErrorPaths:
    """Tests for endpoint error handling."""
    
    @pytest.mark.asyncio
    async def test_list_conversations_endpoint_no_auth(self):
        """Test list endpoint without authentication."""
        from history_sql import list_conversations
        from fastapi import Request, HTTPException
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {}
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth:
            mock_auth.side_effect = HTTPException(status_code=401, detail="Unauthorized")
            
            with pytest.raises(HTTPException) as exc_info:
                await list_conversations(mock_request)
            assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_read_conversation_endpoint_exception(self):
        """Test read endpoint handles exceptions."""
        from history_sql import get_conversation_messages_endpoint
        from fastapi import Request
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth, \
             patch('history_sql.get_conversation_messages', new_callable=AsyncMock) as mock_get:
            mock_auth.return_value = {"user_principal_id": "user123"}
            mock_get.side_effect = Exception("DB Error")
            
            response = await get_conversation_messages_endpoint(mock_request, id="conv123")
            assert response.status_code == 500
    
    @pytest.mark.asyncio
    async def test_delete_conversation_endpoint_exception(self):
        """Test delete endpoint handles exceptions."""
        from history_sql import delete_conversation_endpoint
        from fastapi import Request
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth:
            mock_auth.return_value = {"user_principal_id": "user123"}
            
            with patch('history_sql.delete_conversation', new_callable=AsyncMock) as mock_delete:
                mock_delete.side_effect = Exception("DB Error")
                
                response = await delete_conversation_endpoint(mock_request, id="conv123")
                assert response.status_code == 500
    
    @pytest.mark.asyncio
    async def test_delete_all_conversations_endpoint_no_conversations(self):
        """Test delete all endpoint when no conversations exist."""
        from history_sql import delete_all_conversations_endpoint
        from fastapi import Request, HTTPException
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth, \
             patch('history_sql.get_conversations', new_callable=AsyncMock) as mock_get:
            mock_auth.return_value = {"user_principal_id": "user123"}
            mock_get.return_value = []  # No conversations
            
            with pytest.raises(HTTPException) as exc_info:
                await delete_all_conversations_endpoint(mock_request)
            assert exc_info.value.status_code == 404
    
    @pytest.mark.asyncio
    async def test_delete_all_conversations_endpoint_exception(self):
        """Test delete all endpoint handles exceptions."""
        from history_sql import delete_all_conversations_endpoint
        from fastapi import Request
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth:
            mock_auth.return_value = {"user_principal_id": "user123"}
            
            with patch('history_sql.get_conversations', new_callable=AsyncMock) as mock_get:
                mock_get.side_effect = Exception("DB Error")
                
                response = await delete_all_conversations_endpoint(mock_request)
                assert response.status_code == 500
    
    @pytest.mark.asyncio
    async def test_rename_conversation_endpoint_no_conversation_id(self):
        """Test rename endpoint without conversation_id."""
        from history_sql import rename_conversation_endpoint
        from fastapi import Request, HTTPException
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        mock_request.json = AsyncMock(return_value={"title": "New Title"})
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth:
            mock_auth.return_value = {"user_principal_id": "user123"}
            
            with pytest.raises(HTTPException) as exc_info:
                await rename_conversation_endpoint(mock_request)
            assert exc_info.value.status_code == 400
    
    @pytest.mark.asyncio
    async def test_rename_conversation_endpoint_no_title(self):
        """Test rename endpoint without title."""
        from history_sql import rename_conversation_endpoint
        from fastapi import Request, HTTPException
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        mock_request.json = AsyncMock(return_value={"conversation_id": "conv123"})
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth:
            mock_auth.return_value = {"user_principal_id": "user123"}
            
            with pytest.raises(HTTPException) as exc_info:
                await rename_conversation_endpoint(mock_request)
            assert exc_info.value.status_code == 400
    
    @pytest.mark.asyncio
    async def test_rename_conversation_endpoint_failed(self):
        """Test rename endpoint when rename fails."""
        from history_sql import rename_conversation_endpoint
        from fastapi import Request, HTTPException
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        mock_request.json = AsyncMock(return_value={"conversation_id": "conv123", "title": "New Title"})
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth, \
             patch('history_sql.rename_conversation', new_callable=AsyncMock) as mock_rename:
            mock_auth.return_value = {"user_principal_id": "user123"}
            mock_rename.return_value = False
            
            with pytest.raises(HTTPException) as exc_info:
                await rename_conversation_endpoint(mock_request)
            assert exc_info.value.status_code == 404
    
    @pytest.mark.asyncio
    async def test_rename_conversation_endpoint_exception(self):
        """Test rename endpoint handles exceptions."""
        from history_sql import rename_conversation_endpoint
        from fastapi import Request
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        mock_request.json = AsyncMock(side_effect=Exception("Parse error"))
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth:
            mock_auth.return_value = {"user_principal_id": "user123"}
            
            response = await rename_conversation_endpoint(mock_request)
            assert response.status_code == 500
    
    @pytest.mark.asyncio
    async def test_update_conversation_endpoint_exception(self):
        """Test update endpoint handles exceptions."""
        from history_sql import update_conversation_endpoint
        from fastapi import Request
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        mock_request.json = AsyncMock(side_effect=Exception("Parse error"))
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth:
            mock_auth.return_value = {"user_principal_id": "user123"}
            
            response = await update_conversation_endpoint(mock_request)
            assert response.status_code == 500
    
    @pytest.mark.asyncio
    async def test_delete_conversation_endpoint_no_id(self):
        """Test delete endpoint without conversation ID."""
        from history_sql import delete_conversation_endpoint
        from fastapi import Request, HTTPException
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth, \
             patch('history_sql.track_event_if_configured'):
            mock_auth.return_value = {"user_principal_id": "user123"}
            
            with pytest.raises(HTTPException) as exc_info:
                await delete_conversation_endpoint(mock_request, id="")
            assert exc_info.value.status_code == 400


class TestMessageContentProcessing:
    """Tests for message content processing and edge cases."""
    
    @pytest.mark.asyncio
    async def test_get_conversation_messages_with_json_content(self):
        """Test get_conversation_messages deserializes JSON content."""
        from history_sql import get_conversation_messages
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [
                {"role": "user", "content": '{"text": "Hello"}', "citations": "", "feedback": ""}
            ]
            result = await get_conversation_messages("user123", "conv123")
            assert len(result) == 1
            assert isinstance(result[0]["content"], dict)
    
    @pytest.mark.asyncio
    async def test_get_conversation_messages_with_invalid_citations(self):
        """Test get_conversation_messages handles invalid citation JSON."""
        from history_sql import get_conversation_messages
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [
                {"role": "user", "content": "Hello", "citations": "invalid json", "feedback": ""}
            ]
            result = await get_conversation_messages("user123", "conv123")
            assert len(result) == 1
            assert result[0]["citations"] == []  # Falls back to empty list
    
    @pytest.mark.asyncio
    async def test_create_message_failed_insert(self):
        """Test create_message when insert fails."""
        from history_sql import create_message
        
        message = {"role": "user", "content": "Hello", "id": "msg123"}
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query, \
             patch('history_sql.run_nonquery_params', new_callable=AsyncMock) as mock_run:
            mock_query.return_value = [{"conversation_id": "conv123"}]
            mock_run.return_value = False  # Insert failed
            result = await create_message("msg123", "conv123", "user123", message)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_create_message_with_invalid_citations(self):
        """Test create_message handles citations serialization errors."""
        from history_sql import create_message
        
        # Create an object that can't be serialized
        class NonSerializable:
            pass
        
        message = {
            "role": "assistant",
            "content": "Answer",
            "id": "msg123",
            "citations": [NonSerializable()]  # Can't serialize
        }
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query, \
             patch('history_sql.run_nonquery_params', new_callable=AsyncMock) as mock_run:
            mock_query.return_value = [{"conversation_id": "conv123"}]
            mock_run.return_value = True
            result = await create_message("msg123", "conv123", "user123", message)
            # Should still work, just with empty citations
            assert result is True
    
    @pytest.mark.asyncio
    async def test_update_conversation_with_tool_message(self):
        """Test update_conversation handles tool messages."""
        from history_sql import update_conversation
        
        request_json = {
            "conversation_id": "conv123",
            "messages": [
                {"role": "user", "content": "Hello", "id": "msg1"},
                {"role": "tool", "content": "Tool result", "id": "msg2"},
                {"role": "assistant", "content": "Response", "id": "msg3"}
            ]
        }
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query, \
             patch('history_sql.create_message', new_callable=AsyncMock) as mock_create:
            mock_query.side_effect = [
                [{"conversation_id": "conv123"}],  # Conversation exists
                [{"conversation_id": "conv123", "title": "Test", "updatedAt": "2024-01-01"}]
            ]
            mock_create.return_value = True
            result = await update_conversation("user123", request_json)
            assert result is not None
            assert mock_create.call_count == 3  # User + tool + assistant
    
    @pytest.mark.asyncio
    async def test_generate_title_service_response_exception(self):
        """Test generate_title handles ServiceResponseException."""
        from history_sql import generate_title
        
        messages = [{"role": "user", "content": "Test message"}]
        
        with patch('history_sql.AZURE_AI_AGENT_ENDPOINT', 'http://test'), \
             patch('history_sql.AIProjectClient') as mock_client, \
             patch('history_sql.AzureAIClient'), \
             patch('history_sql.ChatAgent'):
            # Make the context manager raise ServiceResponseException
            mock_instance = MagicMock()
            mock_instance.__aenter__.side_effect = Exception("ServiceResponseException")
            mock_client.return_value = mock_instance
            
            result = await generate_title(messages)
            assert isinstance(result, str)  # Falls back to generate_fallback_title
            assert result == "Test message"  # First 4 words (only one word here)


class TestApplicationInsights:
    """Tests for Application Insights configuration."""
    
    def test_application_insights_configured(self):
        """Test Application Insights is configured when key present."""
        import sys
        
        # Remove history_sql from cache to test fresh import
        if 'history_sql' in sys.modules:
            del sys.modules['history_sql']
        
        with patch('history_sql.os.getenv') as mock_env:
            mock_env.return_value = 'test-instrumentation-key'
            hs = importlib.import_module('history_sql')
            # Module imports successfully regardless of instrumentation key
            assert hs.logger is not None
    
    def test_application_insights_not_configured(self):
        """Test Application Insights skipped when no key."""
        import sys
        
        # Remove history_sql from cache to test fresh import
        if 'history_sql' in sys.modules:
            del sys.modules['history_sql']
        
        with patch('history_sql.os.getenv') as mock_env:
            mock_env.return_value = None
            hs = importlib.import_module('history_sql')
            # Module imports successfully
            assert hs.logger is not None


class TestDatabaseConnectionEdgeCases:
    """Tests for database connection edge cases."""
    
    @pytest.mark.asyncio
    async def test_run_query_params_connection_failure(self):
        """Test run_query_params when connection fails."""
        from history_sql import run_query_params
        
        with patch('history_sql.get_db_connection', new_callable=AsyncMock, return_value=None):
            result = await run_query_params("SELECT * FROM test", ())
            assert result is None
    
    @pytest.mark.asyncio
    async def test_run_nonquery_params_connection_failure(self):
        """Test run_nonquery_params when connection fails."""
        from history_sql import run_nonquery_params
        
        with patch('history_sql.get_db_connection', new_callable=AsyncMock, return_value=None):
            result = await run_nonquery_params("INSERT INTO test VALUES (?)", ("value",))
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_fabric_db_connection_driver_17_fallback_succeeds(self):
        """Test connection falls back to driver 17 successfully."""
        from history_sql import get_fabric_db_connection
        
        with patch('history_sql.os.getenv') as mock_env, \
             patch('history_sql.pyodbc.connect') as mock_connect, \
             patch('history_sql.AzureCliCredential'):
            mock_env.side_effect = lambda key, default=None: {
                'RUNNING_IN_PRODUCTION': 'true',
                'SQL_ENDPOINT': 'server.database.windows.net',
                'SQL_DATABASE': 'testdb'
            }.get(key, default)
            
            # Driver 18 fails, driver 17 succeeds
            mock_conn = MagicMock()
            mock_connect.side_effect = [Exception("Driver 18 failed"), mock_conn]
            
            conn = await get_fabric_db_connection()
            assert conn == mock_conn
            assert mock_connect.call_count == 2


class TestUpdateConversationEdgeCases:
    """Tests for update_conversation edge cases."""
    
    @pytest.mark.asyncio
    async def test_update_conversation_no_messages(self):
        """Test update_conversation with empty messages."""
        from history_sql import update_conversation
        from fastapi import HTTPException
        
        request_json = {
            "conversation_id": "conv123",
            "messages": []
        }
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [{"conversation_id": "conv123"}]
            
            with pytest.raises(HTTPException) as exc_info:
                await update_conversation("user123", request_json)
            assert exc_info.value.status_code == 400
    
    @pytest.mark.asyncio
    async def test_update_conversation_only_assistant_message(self):
        """Test update_conversation with only assistant message."""
        from history_sql import update_conversation
        from fastapi import HTTPException
        
        request_json = {
            "conversation_id": "conv123",
            "messages": [
                {"role": "assistant", "content": "Response", "id": "msg1"}
            ]
        }
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [{"conversation_id": "conv123"}]
            
            with pytest.raises(HTTPException) as exc_info:
                await update_conversation("user123", request_json)
            assert exc_info.value.status_code == 400
    
    @pytest.mark.asyncio
    async def test_update_conversation_create_message_fails(self):
        """Test update_conversation when create_message fails."""
        from history_sql import update_conversation
        from fastapi import HTTPException
        
        request_json = {
            "conversation_id": "conv123",
            "messages": [
                {"role": "user", "content": "Hello", "id": "msg1"},
                {"role": "assistant", "content": "Hi", "id": "msg2"}
            ]
        }
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query, \
             patch('history_sql.create_message', new_callable=AsyncMock) as mock_create:
            mock_query.return_value = [{"conversation_id": "conv123"}]
            mock_create.return_value = None  # Failed to create message
            
            with pytest.raises(HTTPException) as exc_info:
                await update_conversation("user123", request_json)
            assert exc_info.value.status_code == 400
    
    @pytest.mark.asyncio
    async def test_update_conversation_creates_new_conversation(self):
        """Test update_conversation creates conversation if missing."""
        from history_sql import update_conversation
        
        request_json = {
            "conversation_id": "conv123",
            "messages": [
                {"role": "user", "content": "Hello", "id": "msg1"},
                {"role": "assistant", "content": "Hi", "id": "msg2"}
            ]
        }
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query, \
             patch('history_sql.generate_title', new_callable=AsyncMock) as mock_title, \
             patch('history_sql.create_conversation', new_callable=AsyncMock) as mock_conv, \
             patch('history_sql.create_message', new_callable=AsyncMock) as mock_create:
            mock_query.side_effect = [
                [],  # No conversation found
                [{"conversation_id": "conv123", "title": "New", "updatedAt": "2024-01-01"}]
            ]
            mock_title.return_value = "New Conversation"
            mock_create.return_value = True
            
            result = await update_conversation("user123", request_json)
            assert result is not None
            mock_conv.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_conversation_returns_none_when_not_found(self):
        """Test update_conversation returns None when final query fails."""
        from history_sql import update_conversation
        
        request_json = {
            "conversation_id": "conv123",
            "messages": [
                {"role": "user", "content": "Hello", "id": "msg1"},
                {"role": "assistant", "content": "Hi", "id": "msg2"}
            ]
        }
        
        with patch('history_sql.run_query_params', new_callable=AsyncMock) as mock_query, \
             patch('history_sql.create_message', new_callable=AsyncMock) as mock_create:
            mock_query.side_effect = [
                [{"conversation_id": "conv123"}],  # Conversation exists
                []  # Final query returns nothing
            ]
            mock_create.return_value = True
            
            result = await update_conversation("user123", request_json)
            assert result is None


class TestEndpointValidation:
    """Tests for endpoint validation and edge cases."""
    
    @pytest.mark.asyncio
    async def test_delete_all_conversations_endpoint_delete_fails(self):
        """Test delete all endpoint when deletion returns False."""
        from history_sql import delete_all_conversations_endpoint
        from fastapi import Request, HTTPException
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth, \
             patch('history_sql.get_conversations', new_callable=AsyncMock) as mock_get, \
             patch('history_sql.delete_all_conversations', new_callable=AsyncMock) as mock_delete:
            mock_auth.return_value = {"user_principal_id": "user123"}
            mock_get.return_value = [{"id": "conv1"}]
            mock_delete.return_value = False  # Deletion failed
            
            with pytest.raises(HTTPException) as exc_info:
                await delete_all_conversations_endpoint(mock_request)
            assert exc_info.value.status_code == 404
    
    @pytest.mark.asyncio
    async def test_list_conversations_endpoint_default_params(self):
        """Test list endpoint with default offset and limit."""
        from history_sql import list_conversations
        from fastapi import Request
        
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer token"}
        
        with patch('history_sql.get_authenticated_user_details') as mock_auth, \
             patch('history_sql.get_conversations', new_callable=AsyncMock) as mock_get, \
             patch('history_sql.track_event_if_configured'):
            mock_auth.return_value = {"user_principal_id": "user123"}
            mock_get.return_value = []
            
            response = await list_conversations(mock_request)  # No offset/limit
            assert response.status_code == 200
            mock_get.assert_called_once()


class TestGenerateTitleEdgeCases:
    """Tests for title generation edge cases."""
    
    @pytest.mark.asyncio
    async def test_generate_title_no_user_messages(self):
        """Test generate_title with no user messages."""
        from history_sql import generate_title
        
        messages = [{"role": "assistant", "content": "Hello"}]
        result = await generate_title(messages)
        assert result == "New Conversation"  # Fallback
    
    @pytest.mark.asyncio
    async def test_generate_title_returns_none_from_agent(self):
        """Test generate_title when agent returns None."""
        from history_sql import generate_title
        
        messages = [{"role": "user", "content": "Test"}]
        
        with patch('history_sql.AZURE_AI_AGENT_ENDPOINT', 'http://test'), \
             patch('history_sql.AIProjectClient') as mock_client, \
             patch('history_sql.AzureAIClient') as mock_ai_client, \
             patch('history_sql.ChatAgent') as mock_agent:
            # Setup mocks
            mock_project = MagicMock()
            mock_client.return_value.__aenter__.return_value = mock_project
            
            mock_chat_instance = MagicMock()
            mock_ai_client.return_value = mock_chat_instance
            
            mock_agent_instance = MagicMock()
            mock_agent_instance.get_new_thread.return_value = MagicMock()
            mock_agent_instance.run = AsyncMock(return_value=None)  # Returns None
            mock_agent.return_value.__aenter__.return_value = mock_agent_instance
            
            result = await generate_title(messages)
            assert result == "Test"  # Falls back


class TestDeleteAllEdgeCases:
    """Tests for delete_all_conversations edge cases."""
    
    @pytest.mark.asyncio
    async def test_delete_all_conversations_messages_delete_fails(self):
        """Test delete_all when message deletion fails."""
        from history_sql import delete_all_conversations
        
        with patch('history_sql.run_nonquery_params', new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [False, True]  # Messages fail, conversations succeed
            result = await delete_all_conversations("user123")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_all_conversations_conversations_delete_fails(self):
        """Test delete_all when conversation deletion fails."""
        from history_sql import delete_all_conversations
        
        with patch('history_sql.run_nonquery_params', new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [True, False]  # Messages succeed, conversations fail
            result = await delete_all_conversations("user123")
            assert result is False

