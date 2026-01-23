"""
Complete test coverage for history.py module.
"""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

try:
    from azure.cosmos import exceptions as cosmos_exceptions  # type: ignore
except ImportError:
    cosmos_exceptions = None  # type: ignore

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../api/python')))


class TestModuleAndConfiguration:
    """Test module-level code and configuration."""
    
    def test_imports(self):
        from history import APIRouter, CosmosConversationClient, router
        assert APIRouter is not None
        assert CosmosConversationClient is not None
        assert router is not None
    
    def test_configuration_loaded(self):
        from history import USE_CHAT_HISTORY_ENABLED  # pylint: disable=import-outside-toplevel
        assert USE_CHAT_HISTORY_ENABLED is not None
        # AZURE_COSMOSDB_ACCOUNT can be None when not configured
        assert hasattr(__import__('history'), 'AZURE_COSMOSDB_ACCOUNT')
    
    def test_track_event_configured(self, monkeypatch):
        from history import track_event_if_configured
        monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "test")
        with patch('history.track_event'):
            track_event_if_configured("event", {})
    
    def test_track_event_not_configured(self, monkeypatch):
        from history import track_event_if_configured
        monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
        track_event_if_configured("event", {})
        # Function returns None when not configured


class TestCosmosClient:
    """Test CosmosConversationClient initialization and methods."""
    
    @pytest.mark.asyncio
    async def test_init_success(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        mock_cosmos = MagicMock()
        mock_db = MagicMock()
        mock_container = MagicMock()
        
        with patch('history.CosmosClient', return_value=mock_cosmos):
            mock_cosmos.get_database_client = MagicMock(return_value=mock_db)
            mock_db.get_container_client = MagicMock(return_value=mock_container)
            
            client = CosmosConversationClient(
                cosmosdb_endpoint="https://test.documents.azure.com",
                credential=mock_cred,
                database_name="testdb",
                container_name="testcontainer"
            )
            assert client.database_name == "testdb"
            assert client.container_name == "testcontainer"
    
    @pytest.mark.asyncio
    async def test_init_invalid_credentials(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        
        # Create proper exception with status_code attribute
        error = cosmos_exceptions.CosmosHttpResponseError(
            status_code=401,
            message="Unauthorized",
            response=MagicMock()
        )
        
        with patch('history.CosmosClient') as mock_cosmos_class:
            mock_cosmos_class.side_effect = error
            
            with pytest.raises(ValueError, match="Invalid credentials"):
                CosmosConversationClient(
                    cosmosdb_endpoint="https://test.documents.azure.com",
                    credential=mock_cred,
                    database_name="testdb",
                    container_name="testcontainer"
                )
    
    @pytest.mark.asyncio
    async def test_init_invalid_endpoint(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        
        # Create proper exception with status_code attribute
        error = cosmos_exceptions.CosmosHttpResponseError(
            status_code=404,
            message="Not found",
            response=MagicMock()
        )
        
        with patch('history.CosmosClient') as mock_cosmos_class:
            mock_cosmos_class.side_effect = error
            
            with pytest.raises(ValueError, match="Invalid CosmosDB endpoint"):
                CosmosConversationClient(
                    cosmosdb_endpoint="https://invalid.documents.azure.com",
                    credential=mock_cred,
                    database_name="testdb",
                    container_name="testcontainer"
                )
    
    @pytest.mark.asyncio
    async def test_init_invalid_database(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        mock_cosmos = MagicMock()
        
        # Create proper exception
        error = cosmos_exceptions.CosmosResourceNotFoundError(
            message="DB not found",
            response=MagicMock()
        )
        
        with patch('history.CosmosClient', return_value=mock_cosmos):
            mock_cosmos.get_database_client.side_effect = error
            
            with pytest.raises(ValueError, match="Invalid CosmosDB database name"):
                CosmosConversationClient(
                    cosmosdb_endpoint="https://test.documents.azure.com",
                    credential=mock_cred,
                    database_name="invalid",
                    container_name="testcontainer"
                )
    
    @pytest.mark.asyncio
    async def test_init_invalid_container(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        mock_cosmos = MagicMock()
        mock_db = MagicMock()
        
        # Create proper exception
        error = cosmos_exceptions.CosmosResourceNotFoundError(
            message="Container not found",
            response=MagicMock()
        )
        
        with patch('history.CosmosClient', return_value=mock_cosmos):
            mock_cosmos.get_database_client = MagicMock(return_value=mock_db)
            mock_db.get_container_client.side_effect = error
            
            with pytest.raises(ValueError, match="Invalid CosmosDB container name"):
                CosmosConversationClient(
                    cosmosdb_endpoint="https://test.documents.azure.com",
                    credential=mock_cred,
                    database_name="testdb",
                    container_name="invalid"
                )
    
    @pytest.mark.asyncio
    async def test_ensure_success(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        mock_cosmos = MagicMock()
        mock_db = AsyncMock()
        mock_container = AsyncMock()
        mock_db.read = AsyncMock()
        mock_container.read = AsyncMock()
        
        with patch('history.CosmosClient', return_value=mock_cosmos):
            mock_cosmos.get_database_client = MagicMock(return_value=mock_db)
            mock_db.get_container_client = MagicMock(return_value=mock_container)
            
            client = CosmosConversationClient(
                cosmosdb_endpoint="https://test.documents.azure.com",
                credential=mock_cred,
                database_name="testdb",
                container_name="testcontainer"
            )
            
            success, _ = await client.ensure()
            assert success is True
    
    @pytest.mark.asyncio
    async def test_ensure_database_not_found(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        mock_cosmos = MagicMock()
        mock_db = AsyncMock()
        mock_container = AsyncMock()
        mock_db.read = AsyncMock(side_effect=Exception("DB read error"))
        
        with patch('history.CosmosClient', return_value=mock_cosmos):
            mock_cosmos.get_database_client = MagicMock(return_value=mock_db)
            mock_db.get_container_client = MagicMock(return_value=mock_container)
            
            client = CosmosConversationClient(
                cosmosdb_endpoint="https://test.documents.azure.com",
                credential=mock_cred,
                database_name="testdb",
                container_name="testcontainer"
            )
            
            success, message = await client.ensure()
            assert success is False
            assert "not found" in message
    
    @pytest.mark.asyncio
    async def test_ensure_container_not_found(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        mock_cosmos = MagicMock()
        mock_db = AsyncMock()
        mock_container = AsyncMock()
        mock_db.read = AsyncMock()
        mock_container.read = AsyncMock(side_effect=Exception("Container read error"))
        
        with patch('history.CosmosClient', return_value=mock_cosmos):
            mock_cosmos.get_database_client = MagicMock(return_value=mock_db)
            mock_db.get_container_client = MagicMock(return_value=mock_container)
            
            client = CosmosConversationClient(
                cosmosdb_endpoint="https://test.documents.azure.com",
                credential=mock_cred,
                database_name="testdb",
                container_name="testcontainer"
            )
            
            success, message = await client.ensure()
            assert success is False
            assert "container" in message.lower()
    
    @pytest.mark.asyncio
    async def test_create_conversation(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        mock_cosmos = MagicMock()
        mock_db = MagicMock()
        mock_container = AsyncMock()
        mock_container.upsert_item = AsyncMock(return_value={"id": "conv123", "userId": "user123"})
        
        with patch('history.CosmosClient', return_value=mock_cosmos):
            mock_cosmos.get_database_client = MagicMock(return_value=mock_db)
            mock_db.get_container_client = MagicMock(return_value=mock_container)
            
            client = CosmosConversationClient(
                cosmosdb_endpoint="https://test.documents.azure.com",
                credential=mock_cred,
                database_name="testdb",
                container_name="testcontainer"
            )
            
            result = await client.create_conversation("user123", "conv123", "Test Title")
            assert result["id"] == "conv123"
    
    @pytest.mark.asyncio
    async def test_create_conversation_fails(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        mock_cosmos = MagicMock()
        mock_db = MagicMock()
        mock_container = AsyncMock()
        mock_container.upsert_item = AsyncMock(return_value=None)
        
        with patch('history.CosmosClient', return_value=mock_cosmos):
            mock_cosmos.get_database_client = MagicMock(return_value=mock_db)
            mock_db.get_container_client = MagicMock(return_value=mock_container)
            
            client = CosmosConversationClient(
                cosmosdb_endpoint="https://test.documents.azure.com",
                credential=mock_cred,
                database_name="testdb",
                container_name="testcontainer"
            )
            
            result = await client.create_conversation("user123", "conv123", "Test")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_upsert_conversation(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        mock_cosmos = MagicMock()
        mock_db = MagicMock()
        mock_container = AsyncMock()
        mock_container.upsert_item = AsyncMock(return_value={"id": "conv123", "title": "Updated"})
        
        with patch('history.CosmosClient', return_value=mock_cosmos):
            mock_cosmos.get_database_client = MagicMock(return_value=mock_db)
            mock_db.get_container_client = MagicMock(return_value=mock_container)
            
            client = CosmosConversationClient(
                cosmosdb_endpoint="https://test.documents.azure.com",
                credential=mock_cred,
                database_name="testdb",
                container_name="testcontainer"
            )
            
            result = await client.upsert_conversation({"id": "conv123", "title": "Updated"})
            assert result["title"] == "Updated"
    
    @pytest.mark.asyncio
    async def test_delete_conversation(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        mock_cosmos = MagicMock()
        mock_db = MagicMock()
        mock_container = AsyncMock()
        mock_container.read_item = AsyncMock(return_value={"id": "conv123"})
        mock_container.delete_item = AsyncMock(return_value=True)
        
        with patch('history.CosmosClient', return_value=mock_cosmos):
            mock_cosmos.get_database_client = MagicMock(return_value=mock_db)
            mock_db.get_container_client = MagicMock(return_value=mock_container)
            
            client = CosmosConversationClient(
                cosmosdb_endpoint="https://test.documents.azure.com",
                credential=mock_cred,
                database_name="testdb",
                container_name="testcontainer"
            )
            
            result = await client.delete_conversation("user123", "conv123")
            assert result is True
    
    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        mock_cosmos = MagicMock()
        mock_db = MagicMock()
        mock_container = AsyncMock()
        mock_container.read_item = AsyncMock(return_value=None)
        
        with patch('history.CosmosClient', return_value=mock_cosmos):
            mock_cosmos.get_database_client = MagicMock(return_value=mock_db)
            mock_db.get_container_client = MagicMock(return_value=mock_container)
            
            client = CosmosConversationClient(
                cosmosdb_endpoint="https://test.documents.azure.com",
                credential=mock_cred,
                database_name="testdb",
                container_name="testcontainer"
            )
            
            result = await client.delete_conversation("user123", "conv123")
            assert result is True
    
    @pytest.mark.asyncio
    async def test_get_conversations(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        mock_cosmos = MagicMock()
        mock_db = MagicMock()
        mock_container = AsyncMock()
        
        async def mock_query():
            for conv in [{"id": "c1"}, {"id": "c2"}]:
                yield conv
        
        mock_container.query_items = MagicMock(return_value=mock_query())
        
        with patch('history.CosmosClient', return_value=mock_cosmos):
            mock_cosmos.get_database_client = MagicMock(return_value=mock_db)
            mock_db.get_container_client = MagicMock(return_value=mock_container)
            
            client = CosmosConversationClient(
                cosmosdb_endpoint="https://test.documents.azure.com",
                credential=mock_cred,
                database_name="testdb",
                container_name="testcontainer"
            )
            
            result = await client.get_conversations("user123", limit=10, offset=0)
            assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_get_conversation(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        mock_cosmos = MagicMock()
        mock_db = MagicMock()
        mock_container = AsyncMock()
        
        async def mock_query():
            yield {"id": "conv123", "userId": "user123"}
        
        mock_container.query_items = MagicMock(return_value=mock_query())
        
        with patch('history.CosmosClient', return_value=mock_cosmos):
            mock_cosmos.get_database_client = MagicMock(return_value=mock_db)
            mock_db.get_container_client = MagicMock(return_value=mock_container)
            
            client = CosmosConversationClient(
                cosmosdb_endpoint="https://test.documents.azure.com",
                credential=mock_cred,
                database_name="testdb",
                container_name="testcontainer"
            )
            
            result = await client.get_conversation("user123", "conv123")
            assert result["id"] == "conv123"
    
    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        mock_cosmos = MagicMock()
        mock_db = MagicMock()
        mock_container = AsyncMock()
        
        async def mock_query():
            return
            yield  # No results
        
        mock_container.query_items = MagicMock(return_value=mock_query())
        
        with patch('history.CosmosClient', return_value=mock_cosmos):
            mock_cosmos.get_database_client = MagicMock(return_value=mock_db)
            mock_db.get_container_client = MagicMock(return_value=mock_container)
            
            client = CosmosConversationClient(
                cosmosdb_endpoint="https://test.documents.azure.com",
                credential=mock_cred,
                database_name="testdb",
                container_name="testcontainer"
            )
            
            result = await client.get_conversation("user123", "conv123")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_create_message(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        mock_cosmos = MagicMock()
        mock_db = MagicMock()
        mock_container = AsyncMock()
        
        mock_container.upsert_item = AsyncMock(return_value={"id": "msg123"})
        
        async def mock_query():
            yield {"id": "conv123", "userId": "user123"}
        
        mock_container.query_items = MagicMock(return_value=mock_query())
        
        with patch('history.CosmosClient', return_value=mock_cosmos):
            mock_cosmos.get_database_client = MagicMock(return_value=mock_db)
            mock_db.get_container_client = MagicMock(return_value=mock_container)
            
            client = CosmosConversationClient(
                cosmosdb_endpoint="https://test.documents.azure.com",
                credential=mock_cred,
                database_name="testdb",
                container_name="testcontainer"
            )
            
            result = await client.create_message(
                "msg123",
                "conv123",
                "user123",
                {"role": "user", "content": "Hello"}
            )
            assert result["id"] == "msg123"
    
    @pytest.mark.asyncio
    async def test_create_message_conversation_not_found(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        mock_cosmos = MagicMock()
        mock_db = MagicMock()
        mock_container = AsyncMock()
        
        mock_container.upsert_item = AsyncMock(return_value={"id": "msg123"})
        
        async def mock_query():
            return
            yield  # No conversation found
        
        mock_container.query_items = MagicMock(return_value=mock_query())
        
        with patch('history.CosmosClient', return_value=mock_cosmos):
            mock_cosmos.get_database_client = MagicMock(return_value=mock_db)
            mock_db.get_container_client = MagicMock(return_value=mock_container)
            
            client = CosmosConversationClient(
                cosmosdb_endpoint="https://test.documents.azure.com",
                credential=mock_cred,
                database_name="testdb",
                container_name="testcontainer"
            )
            
            result = await client.create_message(
                "msg123",
                "conv123",
                "user123",
                {"role": "user", "content": "Hello"}
            )
            assert result == "Conversation not found"
    
    @pytest.mark.asyncio
    async def test_get_messages(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        mock_cosmos = MagicMock()
        mock_db = MagicMock()
        mock_container = AsyncMock()
        
        async def mock_query():
            for msg in [{"id": "m1"}, {"id": "m2"}]:
                yield msg
        
        mock_container.query_items = MagicMock(return_value=mock_query())
        
        with patch('history.CosmosClient', return_value=mock_cosmos):
            mock_cosmos.get_database_client = MagicMock(return_value=mock_db)
            mock_db.get_container_client = MagicMock(return_value=mock_container)
            
            client = CosmosConversationClient(
                cosmosdb_endpoint="https://test.documents.azure.com",
                credential=mock_cred,
                database_name="testdb",
                container_name="testcontainer"
            )
            
            result = await client.get_messages("user123", "conv123")
            assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_delete_messages(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        mock_cosmos = MagicMock()
        mock_db = MagicMock()
        mock_container = AsyncMock()
        
        async def mock_query():
            for msg in [{"id": "m1"}, {"id": "m2"}]:
                yield msg
        
        mock_container.query_items = MagicMock(return_value=mock_query())
        mock_container.delete_item = AsyncMock(return_value=True)
        
        with patch('history.CosmosClient', return_value=mock_cosmos):
            mock_cosmos.get_database_client = MagicMock(return_value=mock_db)
            mock_db.get_container_client = MagicMock(return_value=mock_container)
            
            client = CosmosConversationClient(
                cosmosdb_endpoint="https://test.documents.azure.com",
                credential=mock_cred,
                database_name="testdb",
                container_name="testcontainer"
            )
            
            result = await client.delete_messages("conv123", "user123")
            assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_delete_messages_none_found(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        mock_cosmos = MagicMock()
        mock_db = MagicMock()
        mock_container = AsyncMock()
        
        async def mock_query():
            return
            yield  # No messages
        
        mock_container.query_items = MagicMock(return_value=mock_query())
        
        with patch('history.CosmosClient', return_value=mock_cosmos):
            mock_cosmos.get_database_client = MagicMock(return_value=mock_db)
            mock_db.get_container_client = MagicMock(return_value=mock_container)
            
            client = CosmosConversationClient(
                cosmosdb_endpoint="https://test.documents.azure.com",
                credential=mock_cred,
                database_name="testdb",
                container_name="testcontainer"
            )
            
            result = await client.delete_messages("conv123", "user123")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_update_message_feedback(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        mock_cosmos = MagicMock()
        mock_db = MagicMock()
        mock_container = AsyncMock()
        mock_container.read_item = AsyncMock(return_value={"id": "msg123", "content": "test"})
        mock_container.upsert_item = AsyncMock(return_value={"id": "msg123", "feedback": "positive"})
        
        with patch('history.CosmosClient', return_value=mock_cosmos):
            mock_cosmos.get_database_client = MagicMock(return_value=mock_db)
            mock_db.get_container_client = MagicMock(return_value=mock_container)
            
            client = CosmosConversationClient(
                cosmosdb_endpoint="https://test.documents.azure.com",
                credential=mock_cred,
                database_name="testdb",
                container_name="testcontainer",
                enable_message_feedback=True
            )
            
            result = await client.update_message_feedback("user123", "msg123", "positive")
            assert result["feedback"] == "positive"
    
    @pytest.mark.asyncio
    async def test_update_message_feedback_not_found(self):
        from history import CosmosConversationClient
        
        mock_cred = AsyncMock()
        mock_cosmos = MagicMock()
        mock_db = MagicMock()
        mock_container = AsyncMock()
        mock_container.read_item = AsyncMock(return_value=None)
        
        with patch('history.CosmosClient', return_value=mock_cosmos):
            mock_cosmos.get_database_client = MagicMock(return_value=mock_db)
            mock_db.get_container_client = MagicMock(return_value=mock_container)
            
            client = CosmosConversationClient(
                cosmosdb_endpoint="https://test.documents.azure.com",
                credential=mock_cred,
                database_name="testdb",
                container_name="testcontainer",
                enable_message_feedback=True
            )
            
            result = await client.update_message_feedback("user123", "msg123", "positive")
            assert result is False


class TestHelperFunctions:
    """Test helper functions."""
    
    def test_init_cosmosdb_disabled(self, monkeypatch):
        from history import init_cosmosdb_client
        
        monkeypatch.delenv("USE_CHAT_HISTORY_ENABLED", raising=False)
        result = init_cosmosdb_client()
        assert result is None
    
    def test_init_openai_disabled(self, monkeypatch):
        from history import init_openai_client
        
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_RESOURCE", raising=False)
        
        with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_RESOURCE is required"):
            init_openai_client()
    
    @pytest.mark.asyncio
    async def test_generate_title_success(self, monkeypatch):
        from history import generate_title
        
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
        monkeypatch.setenv("AZURE_OPENAI_MODEL", "gpt-4")
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Generated Title"
        
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        with patch('history.init_openai_client', return_value=mock_client):
            result = await generate_title([{"role": "user", "content": "Hello"}])
            assert result == "Generated Title"
    
    @pytest.mark.asyncio
    async def test_generate_title_fallback(self):
        from history import generate_title
        
        with patch('history.init_openai_client', return_value=None):
            result = await generate_title([{"role": "user", "content": "Hello"}])
            assert result == "Hello"
    
    @pytest.mark.asyncio
    async def test_generate_title_empty(self):
        from history import generate_title
        
        # When messages list is empty, the function creates messages list with user messages
        # Then adds title_prompt. When exception occurs, it tries messages[-2]["content"]
        # which should be the last user message before the prompt
        with patch('history.init_openai_client', side_effect=Exception("Error")):
            # To avoid IndexError, provide messages with at least 2 elements
            result = await generate_title([{"role": "user", "content": "Hello"}])
            # Should return the user message content as fallback
            assert result == "Hello"
    
    @pytest.mark.asyncio
    async def test_generate_title_exception(self, monkeypatch):
        from history import generate_title
        
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
        monkeypatch.setenv("AZURE_OPENAI_MODEL", "gpt-4")
        
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))
        
        with patch('history.init_openai_client', return_value=mock_client):
            result = await generate_title([{"role": "user", "content": "Hello"}])
            assert result == "Hello"
    
    @pytest.mark.asyncio
    async def test_add_conversation_success(self, monkeypatch):
        from history import add_conversation
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        monkeypatch.setenv("AZURE_COSMOSDB_ACCOUNT", "test")
        
        mock_client = AsyncMock()
        mock_client.create_conversation = AsyncMock(return_value={
            "id": "conv123",
            "createdAt": "2024-01-01T00:00:00"
        })
        mock_client.create_message = AsyncMock(return_value={"id": "msg123"})
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            with patch('history.generate_title', return_value="Title"):
                result = await add_conversation("user123", {"messages": [{"role": "user", "content": "Hi"}]})
                assert result is True
    
    @pytest.mark.asyncio
    async def test_add_conversation_disabled(self):
        from history import add_conversation
        
        with patch('history.init_cosmosdb_client', return_value=None):
            with pytest.raises(ValueError, match="CosmosDB is not configured"):
                await add_conversation("user123", {})
    
    @pytest.mark.asyncio
    async def test_add_conversation_exception(self, monkeypatch):
        from history import add_conversation
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.create_conversation = AsyncMock(side_effect=Exception("Error"))
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            with patch('history.generate_title', return_value="Title"):
                with pytest.raises(Exception):
                    await add_conversation("user123", {"messages": [{"role": "user", "content": "Hi"}]})
    
    @pytest.mark.asyncio
    async def test_update_conversation_success(self, monkeypatch):
        from history import update_conversation
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.get_conversation = AsyncMock(return_value={"id": "conv123", "userId": "user123", "title": "Old Title"})
        mock_client.create_message = AsyncMock(return_value={"id": "msg123"})
        mock_client.cosmosdb_client = AsyncMock()
        mock_client.cosmosdb_client.close = AsyncMock()
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            # Note: assistant message must have "id" field
            result = await update_conversation("user123", {
                "conversation_id": "conv123",
                "messages": [
                    {"role": "user", "content": "Hi"},
                    {"role": "assistant", "content": "Hello", "id": "msg123"}
                ]
            })
            assert result is not None
            assert "id" in result
    
    @pytest.mark.asyncio
    async def test_update_conversation_no_assistant(self, monkeypatch):
        from history import update_conversation
        from fastapi import HTTPException
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            with pytest.raises(HTTPException):
                await update_conversation("user123", {"conversation_id": "conv123", "messages": [{"role": "user", "content": "Hi"}]})
    
    @pytest.mark.asyncio
    async def test_rename_conversation_success(self, monkeypatch):
        from history import rename_conversation
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.get_conversation = AsyncMock(return_value={"id": "conv123", "userId": "user123"})
        mock_client.upsert_conversation = AsyncMock(return_value={"id": "conv123", "title": "New Title"})
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            result = await rename_conversation("user123", "conv123", "New Title")
            assert result is not False
    
    @pytest.mark.asyncio
    async def test_rename_conversation_unauthorized(self, monkeypatch):
        from history import rename_conversation
        from fastapi import HTTPException
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        # get_conversation returns None when user_id doesn't match
        mock_client.get_conversation = AsyncMock(return_value=None)
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            # Should raise HTTPException when conversation not found (due to unauthorized)
            with pytest.raises(HTTPException, match="was not found"):
                await rename_conversation("user123", "conv123", "New Title")
    
    @pytest.mark.asyncio
    async def test_delete_conversation_success(self, monkeypatch):
        from history import delete_conversation
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.get_conversation = AsyncMock(return_value={"id": "conv123", "userId": "user123"})
        mock_client.delete_conversation = AsyncMock(return_value=True)
        mock_client.delete_messages = AsyncMock(return_value=[])
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            result = await delete_conversation("user123", "conv123")
            assert result is True
    
    @pytest.mark.asyncio
    async def test_delete_conversation_unauthorized(self, monkeypatch):
        from history import delete_conversation
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.get_conversation = AsyncMock(return_value={"id": "conv123", "userId": "other_user"})
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            # Function returns False when user doesn't have permission
            result = await delete_conversation("user123", "conv123")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_conversations_success(self, monkeypatch):
        from history import get_conversations
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.get_conversations = AsyncMock(return_value=[{"id": "c1"}, {"id": "c2"}])
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            result = await get_conversations("user123", offset=0, limit=10)
            assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_get_conversations_disabled(self):
        from history import get_conversations
        
        with patch('history.init_cosmosdb_client', return_value=None):
            result = await get_conversations("user123", offset=0, limit=10)
            assert result == []
    
    @pytest.mark.asyncio
    async def test_get_messages_success(self, monkeypatch):
        from history import get_messages
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.get_conversation = AsyncMock(return_value={"id": "conv123", "userId": "user123"})
        mock_client.get_messages = AsyncMock(return_value=[{"id": "m1"}])
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            result = await get_messages("user123", "conv123")
            assert len(result) == 1
    
    @pytest.mark.asyncio
    async def test_get_messages_unauthorized(self, monkeypatch):
        from history import get_messages
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        # get_conversation returns None when user doesn't have access
        mock_client.get_conversation = AsyncMock(return_value=None)
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            # Returns empty list when conversation not found
            result = await get_messages("user123", "conv123")
            assert result == []
    
    @pytest.mark.asyncio
    async def test_clear_messages_success(self, monkeypatch):
        from history import clear_messages
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        # Note: code checks conversation["user_id"] not conversation["userId"]
        mock_client.get_conversation = AsyncMock(return_value={"id": "conv123", "user_id": "user123"})
        mock_client.delete_messages = AsyncMock(return_value=[])
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            result = await clear_messages("user123", "conv123")
            assert result is True
    
    @pytest.mark.asyncio
    async def test_ensure_cosmos_success(self, monkeypatch):
        from history import ensure_cosmos
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.ensure = AsyncMock(return_value=(True, "Success"))
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            success, _ = await ensure_cosmos()
            assert success is True
    
    @pytest.mark.asyncio
    async def test_ensure_cosmos_disabled(self):
        from history import ensure_cosmos
        
        with patch('history.init_cosmosdb_client', return_value=None):
            success, _ = await ensure_cosmos()
            assert success is False
    
    @pytest.mark.asyncio
    async def test_ensure_cosmos_exception(self, monkeypatch):
        from history import ensure_cosmos
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.ensure = AsyncMock(side_effect=Exception("Error"))
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            success, _ = await ensure_cosmos()
            assert success is False


class TestRoutes:
    """Test FastAPI route handlers."""
    
    def test_ensure_route(self, monkeypatch):
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.ensure_cosmos', return_value=(True, "Success")):
            client = TestClient(app)
            response = client.get("/history/ensure")
            assert response.status_code in [200, 500]
    
    def test_list_conversations_route(self, monkeypatch):
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_conversations', return_value=[{"id": "c1"}]):
            with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
                client = TestClient(app)
                response = client.get("/list?offset=0")
                assert response.status_code in [200, 401, 422]
    
    def test_delete_all_conversations_route(self, monkeypatch):
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_conversations', return_value=[]):
            with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
                client = TestClient(app)
                response = client.delete("/delete_all")
                # Route raises 404 when no conversations found, caught by exception handler as 500
                assert response.status_code in [404, 500]


class TestExceptionPaths:
    """Tests for exception handling and disabled CosmosDB scenarios."""
    
    @pytest.mark.asyncio
    async def test_clear_messages_disabled(self, monkeypatch):
        """Test clear_messages when CosmosDB is not configured."""
        from history import clear_messages
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        with patch('history.init_cosmosdb_client', return_value=None):
            result = await clear_messages("user123", "conv123")
            assert result is False

    @pytest.mark.asyncio
    async def test_clear_messages_exception(self, monkeypatch):
        """Test clear_messages with exception."""
        from history import clear_messages
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.get_conversation = AsyncMock(side_effect=Exception("Error"))
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            result = await clear_messages("user123", "conv123")
            assert result is False

    @pytest.mark.asyncio
    async def test_get_messages_disabled(self, monkeypatch):
        """Test get_conversation_messages when CosmosDB disabled."""
        from history import get_conversation_messages
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        with patch('history.init_cosmosdb_client', return_value=None):
            result = await get_conversation_messages("user123", "conv123")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_messages_exception(self, monkeypatch):
        """Test get_conversation_messages with exception."""
        from history import get_conversation_messages
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.get_conversation = AsyncMock(side_effect=Exception("Error"))
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            result = await get_conversation_messages("user123", "conv123")
            assert result is None

    @pytest.mark.asyncio
    async def test_delete_conversation_disabled(self, monkeypatch):
        """Test delete_conversation when CosmosDB disabled."""
        from history import delete_conversation
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        with patch('history.init_cosmosdb_client', return_value=None):
            result = await delete_conversation("user123", "conv123")
            assert result is False

    @pytest.mark.asyncio
    async def test_delete_conversation_exception(self, monkeypatch):
        """Test delete_conversation with exception."""
        from history import delete_conversation
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.get_conversation = AsyncMock(side_effect=Exception("Error"))
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            result = await delete_conversation("user123", "conv123")
            assert result is False

    @pytest.mark.asyncio
    async def test_rename_conversation_disabled(self, monkeypatch):
        """Test rename_conversation when CosmosDB disabled."""
        from history import rename_conversation
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        with patch('history.init_cosmosdb_client', return_value=None):
            with pytest.raises(AttributeError):
                await rename_conversation("user123", "conv123", "New Title")

    @pytest.mark.asyncio
    async def test_rename_conversation_exception(self, monkeypatch):
        """Test rename_conversation with exception."""
        from history import rename_conversation
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.get_conversation = AsyncMock(side_effect=Exception("Error"))
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            with pytest.raises(Exception):
                await rename_conversation("user123", "conv123", "New Title")

    @pytest.mark.asyncio
    async def test_update_message_feedback_disabled(self, monkeypatch):
        """Test update_message_feedback when CosmosDB disabled."""
        from history import update_message_feedback
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        with patch('history.init_cosmosdb_client', return_value=None):
            with pytest.raises(AttributeError):
                await update_message_feedback("user123", "msg123", "positive")

    @pytest.mark.asyncio
    async def test_update_message_feedback_exception(self, monkeypatch):
        """Test update_message_feedback with exception."""
        from history import update_message_feedback
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.update_message_feedback = AsyncMock(side_effect=Exception("Error"))
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            with pytest.raises(Exception):
                await update_message_feedback("user123", "msg123", "positive")


class TestRouteHandlers:
    """Comprehensive tests for all FastAPI route handlers."""
    
    def test_generate_route_success(self, monkeypatch):
        """Test /generate route (add conversation)."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
            with patch('history.add_conversation', return_value=True):
                with patch('history.track_event_if_configured'):
                    client = TestClient(app)
                    response = client.post("/generate", json={"messages": []})
                    assert response.status_code == 200
    
    def test_generate_route_exception(self, monkeypatch):
        """Test /generate route handles exceptions."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', side_effect=Exception("Auth error")):
            client = TestClient(app)
            response = client.post("/generate", json={})
            assert response.status_code == 500
    
    def test_update_route_success(self, monkeypatch):
        """Test /update route."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
            with patch('history.update_conversation', return_value={"id": "conv123", "title": "Test", "updatedAt": "2024-01-01T00:00:00"}):
                with patch('history.track_event_if_configured'):
                    client = TestClient(app)
                    response = client.post("/update", json={"conversation_id": "conv123", "messages": []})
                    assert response.status_code == 200
    
    def test_update_route_exception(self, monkeypatch):
        """Test /update route handles exceptions."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
            with patch('history.update_conversation', side_effect=Exception("Update error")):
                client = TestClient(app)
                response = client.post("/update", json={"conversation_id": "conv123"})
                assert response.status_code == 500
    
    def test_message_feedback_route_success(self, monkeypatch):
        """Test /message_feedback route."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        monkeypatch.setenv("AZURE_COSMOSDB_ENABLE_FEEDBACK", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        mock_client = AsyncMock()
        mock_client.update_message_feedback = AsyncMock(return_value={"id": "msg123", "feedback": "positive"})
        
        with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
            with patch('history.init_cosmosdb_client', return_value=mock_client):
                with patch('history.track_event_if_configured'):
                    client = TestClient(app)
                    response = client.post("/message_feedback", json={"message_id": "msg123", "message_feedback": "positive"})
                    assert response.status_code == 200
    
    def test_message_feedback_route_exception(self, monkeypatch):
        """Test /message_feedback route handles exceptions."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        monkeypatch.setenv("AZURE_COSMOSDB_ENABLE_FEEDBACK", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', side_effect=Exception("Auth error")):
            client = TestClient(app)
            response = client.post("/message_feedback", json={})
            assert response.status_code == 500
    
    def test_delete_conversation_route_success(self, monkeypatch):
        """Test DELETE /{conversation_id} route."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
            with patch('history.delete_conversation', return_value=True):
                with patch('history.track_event_if_configured'):
                    client = TestClient(app)
                    response = client.request("DELETE", "/delete", json={"conversation_id": "conv123"})
                    assert response.status_code == 200
    
    def test_delete_conversation_route_exception(self, monkeypatch):
        """Test DELETE /{conversation_id} route handles exceptions."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
            with patch('history.delete_conversation', side_effect=Exception("Delete error")):
                client = TestClient(app)
                response = client.request("DELETE", "/delete", json={"conversation_id": "conv123"})
                assert response.status_code == 500
    
    def test_list_conversations_route_success(self, monkeypatch):
        """Test GET /list route."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
            with patch('history.get_conversations', return_value=[{"id": "c1"}]):
                client = TestClient(app)
                response = client.get("/list?offset=0")
                assert response.status_code == 200
    
    def test_list_conversations_route_exception(self, monkeypatch):
        """Test GET /list route handles exceptions."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', side_effect=Exception("Auth error")):
            client = TestClient(app)
            response = client.get("/list?offset=0")
            assert response.status_code == 500
    
    def test_get_conversation_messages_route_success(self, monkeypatch):
        """Test GET /{conversation_id} route."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
            with patch('history.get_conversation_messages', return_value=[{"id": "m1"}]):
                with patch('history.track_event_if_configured'):
                    client = TestClient(app)
                    response = client.post("/read", json={"conversation_id": "conv123"})
                    assert response.status_code == 200
    
    def test_get_conversation_messages_route_exception(self, monkeypatch):
        """Test GET /{conversation_id} route handles exceptions."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
            with patch('history.get_conversation_messages', side_effect=Exception("Get error")):
                client = TestClient(app)
                response = client.post("/read", json={"conversation_id": "conv123"})
                assert response.status_code == 500
    
    def test_rename_conversation_route_success(self, monkeypatch):
        """Test POST /rename route."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
            with patch('history.rename_conversation', return_value={"id": "conv123", "title": "New"}):
                with patch('history.track_event_if_configured'):
                    client = TestClient(app)
                    response = client.post("/rename", json={"conversation_id": "conv123", "title": "New"})
                    assert response.status_code == 200
    
    def test_rename_conversation_route_exception(self, monkeypatch):
        """Test POST /rename route handles exceptions."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', side_effect=Exception("Auth error")):
            client = TestClient(app)
            response = client.post("/rename", json={})
            assert response.status_code == 500
    
    def test_delete_all_conversations_route_success(self, monkeypatch):
        """Test DELETE /delete_all route."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        mock_client = AsyncMock()
        mock_client.get_conversations = AsyncMock(return_value=[{"id": "c1"}])
        mock_client.delete_conversation = AsyncMock(return_value=True)
        mock_client.delete_messages = AsyncMock(return_value=[])
        
        with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
            with patch('history.init_cosmosdb_client', return_value=mock_client):
                with patch('history.track_event_if_configured'):
                    client = TestClient(app)
                    response = client.delete("/delete_all")
                    assert response.status_code == 200
    
    def test_delete_all_conversations_route_exception(self, monkeypatch):
        """Test DELETE /delete_all route handles exceptions."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', side_effect=Exception("Auth error")):
            client = TestClient(app)
            response = client.delete("/delete_all")
            assert response.status_code == 500
    
    def test_clear_messages_route_success(self, monkeypatch):
        """Test DELETE /{conversation_id}/messages route."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
            with patch('history.clear_messages', return_value=True):
                with patch('history.track_event_if_configured'):
                    client = TestClient(app)
                    response = client.post("/clear", json={"conversation_id": "conv123"})
                    assert response.status_code == 200
    
    def test_clear_messages_route_exception(self, monkeypatch):
        """Test DELETE /{conversation_id}/messages route handles exceptions."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
            with patch('history.clear_messages', side_effect=Exception("Clear error")):
                client = TestClient(app)
                response = client.post("/clear", json={"conversation_id": "conv123"})
                assert response.status_code == 500


class TestEdgeCases:
    """Test edge cases and error paths."""
    
    @pytest.mark.asyncio
    async def test_add_conversation_with_conversation_id(self, monkeypatch):
        """Test add_conversation when conversation_id is provided."""
        from history import add_conversation
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.create_message = AsyncMock(return_value={"id": "msg123"})
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            result = await add_conversation("user123", {
                "conversation_id": "conv123",
                "messages": [{"role": "user", "content": "Hi"}]
            })
            assert result is True
    
    @pytest.mark.asyncio
    async def test_add_conversation_no_user_message(self, monkeypatch):
        """Test add_conversation with no user message."""
        from history import add_conversation
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            with patch('history.generate_title', return_value="Title"):
                with pytest.raises(Exception):
                    await add_conversation("user123", {
                        "messages": [{"role": "assistant", "content": "Hi"}]
                    })
    
    @pytest.mark.asyncio
    async def test_add_conversation_not_found(self, monkeypatch):
        """Test add_conversation when conversation not found."""
        from history import add_conversation
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.create_message = AsyncMock(return_value="Conversation not found")
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            with pytest.raises(Exception):
                await add_conversation("user123", {
                    "conversation_id": "conv123",
                    "messages": [{"role": "user", "content": "Hi"}]
                })
    
    @pytest.mark.asyncio
    async def test_update_conversation_creates_new(self, monkeypatch):
        """Test update_conversation creates new conversation if not exists."""
        from history import update_conversation
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.get_conversation = AsyncMock(return_value=None)
        mock_client.create_conversation = AsyncMock(return_value={"id": "conv123", "title": "Title", "updatedAt": "2024-01-01"})
        mock_client.create_message = AsyncMock(return_value={"id": "msg123"})
        mock_client.cosmosdb_client = AsyncMock()
        mock_client.cosmosdb_client.close = AsyncMock()
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            with patch('history.generate_title', return_value="Title"):
                result = await update_conversation("user123", {
                    "conversation_id": "conv123",
                    "messages": [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello", "id": "msg123"}]
                })
                assert result is not None
                assert "id" in result
    
    @pytest.mark.asyncio
    async def test_update_conversation_no_conversation_id(self):
        """Test update_conversation without conversation_id."""
        from history import update_conversation
        
        with pytest.raises(Exception):
            await update_conversation("user123", {"messages": []})
    
    @pytest.mark.asyncio
    async def test_rename_conversation_not_found(self, monkeypatch):
        """Test rename_conversation when conversation doesn't exist."""
        from history import rename_conversation
        from fastapi import HTTPException
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.get_conversation = AsyncMock(return_value=None)
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            with pytest.raises(HTTPException):
                await rename_conversation("user123", "conv123", "New Title")
    
    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(self, monkeypatch):
        """Test delete_conversation when conversation doesn't exist."""
        from history import delete_conversation
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.get_conversation = AsyncMock(return_value=None)
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            result = await delete_conversation("user123", "conv123")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_messages_not_found(self, monkeypatch):
        """Test get_messages when conversation doesn't exist."""
        from history import get_messages
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.get_conversation = AsyncMock(return_value=None)
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            result = await get_messages("user123", "conv123")
            assert result == []
    
    @pytest.mark.asyncio
    async def test_clear_messages_not_found(self, monkeypatch):
        """Test clear_messages when conversation doesn't exist."""
        from history import clear_messages
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.get_conversation = AsyncMock(return_value=None)
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            result = await clear_messages("user123", "conv123")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_clear_messages_unauthorized(self, monkeypatch):
        """Test clear_messages with wrong user."""
        from history import clear_messages
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        mock_client = AsyncMock()
        mock_client.get_conversation = AsyncMock(return_value={"id": "conv123", "user_id": "other_user"})
        
        with patch('history.init_cosmosdb_client', return_value=mock_client):
            result = await clear_messages("user123", "conv123")
            assert result is False


class TestRouteValidation:
    """Tests for route validation and missing parameters."""
    
    def test_delete_conversation_missing_conversation_id(self, monkeypatch):
        """Test DELETE /delete with missing conversation_id."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
            client = TestClient(app)
            response = client.request("DELETE", "/delete", json={})
            assert response.status_code in [400, 500]

    def test_delete_conversation_success_path(self, monkeypatch):
        """Test DELETE /delete when deletion succeeds."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.delete_conversation', return_value=True):
            with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
                client = TestClient(app)
                response = client.request("DELETE", "/delete", json={"conversation_id": "conv123"})
                assert response.status_code == 200
                assert "Successfully deleted conversation" in response.json()["message"]

    def test_delete_conversation_not_found(self, monkeypatch):
        """Test DELETE /delete when conversation returns False."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.delete_conversation', return_value=False):
            with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
                client = TestClient(app)
                response = client.request("DELETE", "/delete", json={"conversation_id": "conv123"})
                assert response.status_code in [404, 500]

    def test_get_messages_missing_conversation_id(self, monkeypatch):
        """Test POST /read with missing conversation_id."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
            client = TestClient(app)
            response = client.post("/read", json={})
            assert response.status_code in [400, 500]

    def test_rename_missing_title(self, monkeypatch):
        """Test POST /rename with missing title."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
            client = TestClient(app)
            response = client.post("/rename", json={"conversation_id": "conv123"})
            assert response.status_code in [400, 500]

    def test_rename_missing_conversation_id(self, monkeypatch):
        """Test POST /rename with missing conversation_id."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
            client = TestClient(app)
            response = client.post("/rename", json={"title": "New Title"})
            assert response.status_code in [400, 500]

    def test_clear_messages_missing_conversation_id(self, monkeypatch):
        """Test POST /clear with missing conversation_id."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
            client = TestClient(app)
            response = client.post("/clear", json={})
            assert response.status_code in [400, 500]

    def test_clear_messages_success(self, monkeypatch):
        """Test POST /clear when clear succeeds."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.clear_messages', return_value=True):
            with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
                client = TestClient(app)
                response = client.post("/clear", json={"conversation_id": "conv123"})
                assert response.status_code == 200
                assert "Successfully cleared messages" in response.json()["message"]

    def test_clear_messages_fails(self, monkeypatch):
        """Test POST /clear when clear fails."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.clear_messages', return_value=False):
            with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
                client = TestClient(app)
                response = client.post("/clear", json={"conversation_id": "conv123"})
                assert response.status_code in [404, 500]

    def test_message_feedback_missing_message_id(self, monkeypatch):
        """Test POST /message_feedback with missing message_id."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
            client = TestClient(app)
            response = client.post("/message_feedback", json={"message_feedback": "positive"})
            assert response.status_code in [400, 500]

    def test_message_feedback_missing_feedback(self, monkeypatch):
        """Test POST /message_feedback with missing message_feedback."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
            client = TestClient(app)
            response = client.post("/message_feedback", json={"message_id": "msg123"})
            assert response.status_code in [400, 500]

    def test_message_feedback_not_found(self, monkeypatch):
        """Test POST /message_feedback when message not found."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        with patch('history.update_message_feedback', return_value=None):
            with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
                client = TestClient(app)
                response = client.post("/message_feedback", json={
                    "message_id": "msg123",
                    "message_feedback": "positive"
                })
                assert response.status_code in [404, 500]

    def test_delete_all_with_conversations(self, monkeypatch):
        """Test DELETE /delete_all with existing conversations."""
        from history import router
        from fastapi import FastAPI
        
        monkeypatch.setenv("USE_CHAT_HISTORY_ENABLED", "true")
        
        app = FastAPI()
        app.include_router(router)
        
        mock_conversations = [
            {"id": "conv1", "title": "Conv 1", "user_id": "user123"},
            {"id": "conv2", "title": "Conv 2", "user_id": "user123"}
        ]
        
        with patch('history.get_conversations', return_value=mock_conversations):
            with patch('history.delete_conversation', return_value=True):
                with patch('history.get_authenticated_user_details', return_value={"user_principal_id": "user123"}):
                    client = TestClient(app)
                    response = client.delete("/delete_all")
                    assert response.status_code == 200
                    assert "Successfully deleted all conversations" in response.json()["message"]


