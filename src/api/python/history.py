from datetime import datetime
import logging
import os
import uuid
from typing import Optional

from azure.cosmos import exceptions
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import get_bearer_token_provider
from azure.monitor.events.extension import track_event
from azure.monitor.opentelemetry import configure_azure_monitor
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from openai import AsyncAzureOpenAI
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

# from chat import adjust_processed_data_dates
from auth.auth_utils import get_authenticated_user_details
from auth.azure_credential_utils import get_azure_credential_async

router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if the Application Insights Instrumentation Key is set in the environment variables
instrumentation_key = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if instrumentation_key:
    # Configure Application Insights if the Instrumentation Key is found
    configure_azure_monitor(connection_string=instrumentation_key)
    logging.info("Application Insights configured with the provided Instrumentation Key")
else:
    # Log a warning if the Instrumentation Key is not found
    logger.warning("Application Insights Instrumentation Key not found in environment variables")

# Suppress INFO logs from 'azure.core.pipeline.policies.http_logging_policy'
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)
logging.getLogger("azure.identity.aio._internal").setLevel(logging.WARNING)

# Suppress info logs from OpenTelemetry exporter
logging.getLogger("azure.monitor.opentelemetry.exporter.export._base").setLevel(
    logging.WARNING
)

# Configuration variables
USE_CHAT_HISTORY_ENABLED = os.getenv("USE_CHAT_HISTORY_ENABLED", "false").strip().lower() == "true"
AZURE_COSMOSDB_DATABASE = os.getenv("AZURE_COSMOSDB_DATABASE")
AZURE_COSMOSDB_ACCOUNT = os.getenv("AZURE_COSMOSDB_ACCOUNT")
AZURE_COSMOSDB_CONVERSATIONS_CONTAINER = os.getenv("AZURE_COSMOSDB_CONVERSATIONS_CONTAINER")
AZURE_COSMOSDB_ENABLE_FEEDBACK = os.getenv("AZURE_COSMOSDB_ENABLE_FEEDBACK", "false").lower() == "true"
CHAT_HISTORY_ENABLED = (
    USE_CHAT_HISTORY_ENABLED
    and AZURE_COSMOSDB_ACCOUNT
    and AZURE_COSMOSDB_DATABASE
    and AZURE_COSMOSDB_CONVERSATIONS_CONTAINER
)

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_MODEL = os.getenv("AZURE_OPENAI_DEPLOYMENT_MODEL")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_RESOURCE = os.getenv("AZURE_OPENAI_RESOURCE")


def track_event_if_configured(event_name: str, event_data: dict):
    """Track events to Application Insights if configured."""
    instrumentation_key = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if instrumentation_key:
        track_event(event_name, event_data)
    else:
        logging.warning("Skipping track_event for %s as Application Insights is not configured", event_name)


class CosmosConversationClient:
    """Client for managing conversations and messages in CosmosDB."""

    def __init__(
        self,
        cosmosdb_endpoint: str,
        credential: any,
        database_name: str,
        container_name: str,
        enable_message_feedback: bool = False,
    ):
        """Initialize CosmosDB conversation client."""
        self.cosmosdb_endpoint = cosmosdb_endpoint
        self.credential = credential
        self.database_name = database_name
        self.container_name = container_name
        self.enable_message_feedback = enable_message_feedback
        try:
            self.cosmosdb_client = CosmosClient(
                self.cosmosdb_endpoint, credential=credential
            )
        except exceptions.CosmosHttpResponseError as e:
            if e.status_code == 401:
                raise ValueError("Invalid credentials") from e
            else:
                raise ValueError("Invalid CosmosDB endpoint") from e

        try:
            self.database_client = self.cosmosdb_client.get_database_client(
                database_name
            )
        except exceptions.CosmosResourceNotFoundError:
            raise ValueError("Invalid CosmosDB database name")

        try:
            self.container_client = self.database_client.get_container_client(
                container_name
            )
        except exceptions.CosmosResourceNotFoundError:
            raise ValueError("Invalid CosmosDB container name")

    async def ensure(self):
        """Ensure CosmosDB client is properly initialized and accessible."""
        if (
            not self.cosmosdb_client
            or not self.database_client
            or not self.container_client
        ):
            return False, "CosmosDB client not initialized correctly"

        try:
            await self.database_client.read()
        except Exception:
            return (
                False,
                f"CosmosDB database {self.database_name} on account {self.cosmosdb_endpoint} not found",
            )

        try:
            await self.container_client.read()
        except Exception:
            return False, f"CosmosDB container {self.container_name} not found"

        return True, "CosmosDB client initialized successfully"

    async def create_conversation(
        self, user_id, conversation_id=str(uuid.uuid4()), title=""
    ):
        """Create a new conversation in CosmosDB."""
        conversation = {
            "id": conversation_id,
            "type": "conversation",
            "createdAt": datetime.utcnow().isoformat(),
            "updatedAt": datetime.utcnow().isoformat(),
            "userId": user_id,
            "title": title,
            "conversation_id": conversation_id,
        }
        # TODO: add some error handling based on the output of the upsert_item call
        resp = await self.container_client.upsert_item(conversation)
        if resp:
            return resp
        else:
            return False

    async def upsert_conversation(self, conversation):
        """Update or insert a conversation in CosmosDB."""
        resp = await self.container_client.upsert_item(conversation)
        if resp:
            return resp
        else:
            return False

    async def delete_conversation(self, user_id, conversation_id):
        """Delete a conversation from CosmosDB."""
        conversation = await self.container_client.read_item(
            item=conversation_id, partition_key=user_id
        )
        if conversation:
            resp = await self.container_client.delete_item(
                item=conversation_id, partition_key=user_id
            )
            return resp
        else:
            return True

    async def delete_messages(self, conversation_id, user_id):
        """Delete all messages for a conversation."""
        # get a list of all the messages in the conversation
        messages = await self.get_messages(user_id, conversation_id)
        response_list = []
        if messages:
            for message in messages:
                resp = await self.container_client.delete_item(
                    item=message["id"], partition_key=user_id
                )
                response_list.append(resp)
            return response_list

    async def get_conversations(self, user_id, limit, sort_order="DESC", offset=0):
        """Get list of conversations for a user with pagination."""
        parameters = [{"name": "@userId", "value": user_id}]
        query = f"SELECT * FROM c where c.userId = @userId and c.type='conversation' order by c.updatedAt {sort_order}"
        if limit is not None:
            query += f" offset {offset} limit {limit}"

        conversations = []
        async for item in self.container_client.query_items(
            query=query, parameters=parameters
        ):
            conversations.append(item)

        return conversations

    async def get_conversation(self, user_id, conversation_id):
        """Get a specific conversation by ID for a user."""
        parameters = [
            {"name": "@conversationId", "value": conversation_id},
            {"name": "@userId", "value": user_id},
        ]
        query = "SELECT * FROM c where c.id = @conversationId and c.type='conversation' and c.userId = @userId"
        conversations = []
        async for item in self.container_client.query_items(
            query=query, parameters=parameters
        ):
            conversations.append(item)

        # if no conversations are found, return None
        if len(conversations) == 0:
            return None
        else:
            return conversations[0]

    async def create_message(self, uuid, conversation_id, user_id, input_message: dict):
        """Create a new message in a conversation."""
        message = {
            "id": uuid,
            "type": "message",
            "userId": user_id,
            "createdAt": datetime.utcnow().isoformat(),
            "updatedAt": datetime.utcnow().isoformat(),
            "conversationId": conversation_id,
            "role": input_message["role"],
            "content": input_message,
        }

        if AZURE_COSMOSDB_ENABLE_FEEDBACK:
            message["feedback"] = ""

        resp = await self.container_client.upsert_item(message)
        if resp:
            # update the parent conversations's updatedAt field with the current message's createdAt datetime value
            conversation = await self.get_conversation(user_id, conversation_id)
            if not conversation:
                return "Conversation not found"
            conversation["updatedAt"] = message["createdAt"]
            await self.upsert_conversation(conversation)
            return resp
        else:
            return False

    async def update_message_feedback(self, user_id, message_id, feedback):
        """Update feedback for a specific message."""
        message = await self.container_client.read_item(
            item=message_id, partition_key=user_id
        )
        if message:
            message["feedback"] = feedback
            resp = await self.container_client.upsert_item(message)
            return resp
        else:
            return False

    async def get_messages(self, user_id, conversation_id):
        """Get all messages for a conversation."""
        parameters = [
            {"name": "@conversationId", "value": conversation_id},
            {"name": "@userId", "value": user_id},
        ]
        query = "SELECT * FROM c WHERE c.conversationId = @conversationId AND c.type='message' AND c.userId = @userId ORDER BY c.timestamp ASC"
        messages = []
        async for item in self.container_client.query_items(
            query=query, parameters=parameters
        ):
            messages.append(item)

        return messages


# Helper functions that were previously in HistoryService
def init_cosmosdb_client():
    """Initialize and return a CosmosDB client."""
    if not CHAT_HISTORY_ENABLED:
        logger.debug("CosmosDB is not enabled in configuration")
        return None

    try:
        cosmos_endpoint = f"https://{AZURE_COSMOSDB_ACCOUNT}.documents.azure.com:443/"

        return CosmosConversationClient(
            cosmosdb_endpoint=cosmos_endpoint,
            credential=get_azure_credential_async(),
            database_name=AZURE_COSMOSDB_DATABASE,
            container_name=AZURE_COSMOSDB_CONVERSATIONS_CONTAINER,
            enable_message_feedback=AZURE_COSMOSDB_ENABLE_FEEDBACK,
        )
    except Exception:
        logger.exception("Failed to initialize CosmosDB client")
        raise


def init_openai_client():
    """Initialize and return an Azure OpenAI client."""
    user_agent = "GitHubSampleWebApp/AsyncAzureOpenAI/1.0.0"

    try:
        if not AZURE_OPENAI_ENDPOINT and not AZURE_OPENAI_RESOURCE:
            raise ValueError(
                "AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_RESOURCE is required")

        endpoint = AZURE_OPENAI_ENDPOINT or f"https://{AZURE_OPENAI_RESOURCE}.openai.azure.com/"
        ad_token_provider = None

        logger.debug("Using Azure AD authentication for OpenAI")
        ad_token_provider = get_bearer_token_provider(
            get_azure_credential_async(), "https://cognitiveservices.azure.com/.default")

        if not AZURE_OPENAI_DEPLOYMENT_MODEL:
            raise ValueError("AZURE_OPENAI_MODEL is required")

        return AsyncAzureOpenAI(
            api_version=AZURE_OPENAI_API_VERSION,
            azure_ad_token_provider=ad_token_provider,
            default_headers={"x-ms-useragent": user_agent},
            azure_endpoint=endpoint,
        )
    except Exception:
        logger.exception("Failed to initialize Azure OpenAI client")
        raise


async def generate_title(conversation_messages):
    """Generate a title for a conversation based on its messages."""
    title_prompt = (
        "Summarize the conversation so far into a 4-word or less title. "
        "Do not use any quotation marks or punctuation. "
        "Do not include any other commentary or description."
    )

    messages = [{"role": msg["role"], "content": msg["content"]}
                for msg in conversation_messages if msg["role"] == "user"]
    messages.append({"role": "user", "content": title_prompt})

    try:
        azure_openai_client = init_openai_client()
        response = await azure_openai_client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT_MODEL,
            messages=messages,
            temperature=1,
            max_tokens=64,
        )
        return response.choices[0].message.content
    except Exception:
        logger.error("Error generating title")
        return messages[-2]["content"]


async def add_conversation(user_id: str, request_json: dict):
    """Add a new conversation with initial message."""
    try:
        conversation_id = request_json.get("conversation_id")
        messages = request_json.get("messages", [])

        history_metadata = {}

        # make sure cosmos is configured
        cosmos_conversation_client = init_cosmosdb_client()
        if not cosmos_conversation_client:
            raise ValueError("CosmosDB is not configured or unavailable")

        if not conversation_id:
            title = await generate_title(messages)
            conversation_dict = await cosmos_conversation_client.create_conversation(user_id, title)
            conversation_id = conversation_dict["id"]
            history_metadata["title"] = title
            history_metadata["date"] = conversation_dict["createdAt"]

        if messages and messages[-1]["role"] == "user":
            created_message = await cosmos_conversation_client.create_message(str(uuid.uuid4()), conversation_id, user_id, messages[-1])
            if created_message == "Conversation not found":
                raise ValueError(
                    f"Conversation not found for ID: {conversation_id}")
        else:
            raise ValueError("No user message found")

        # request_body = {
        #     "messages": messages, "history_metadata": {
        #         "conversation_id": conversation_id}}
        # return await complete_chat_request(request_body)
        return True
    except Exception:
        logger.exception("Error in add_conversation")
        raise


async def update_conversation(user_id: str, request_json: dict):
    """Update a conversation with new messages."""
    conversation_id = request_json.get("conversation_id")
    messages = request_json.get("messages", [])
    if not conversation_id:
        raise ValueError("No conversation_id found")
    cosmos_conversation_client = init_cosmosdb_client()
    # Retrieve or create conversation
    conversation = await cosmos_conversation_client.get_conversation(user_id, conversation_id)
    if not conversation:
        title = await generate_title(messages)
        conversation = await cosmos_conversation_client.create_conversation(
            user_id=user_id, conversation_id=conversation_id, title=title
        )
        conversation_id = conversation["id"]

    # Format the incoming message object in the "chat/completions" messages format then write it to the
    # conversation history in cosmos
    messages = request_json["messages"]
    if len(messages) > 0 and messages[0]["role"] == "user":
        user_message = next(
            (
                message
                for message in reversed(messages)
                if message["role"] == "user"
            ),
            None,
        )
        createdMessageValue = await cosmos_conversation_client.create_message(
            uuid=str(uuid.uuid4()),
            conversation_id=conversation_id,
            user_id=user_id,
            input_message=user_message,
        )
        if createdMessageValue == "Conversation not found":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conversation not found")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User message not found")

    # Format the incoming message object in the "chat/completions" messages format
    # then write it to the conversation history in cosmos
    messages = request_json["messages"]
    if len(messages) > 0 and messages[-1]["role"] == "assistant":
        if len(messages) > 1 and messages[-2].get("role", None) == "tool":
            # write the tool message first
            await cosmos_conversation_client.create_message(
                uuid=str(uuid.uuid4()),
                conversation_id=conversation_id,
                user_id=user_id,
                input_message=messages[-2],
            )
        # write the assistant message
        await cosmos_conversation_client.create_message(
            uuid=messages[-1]["id"],
            conversation_id=conversation_id,
            user_id=user_id,
            input_message=messages[-1],
        )
    else:
        await cosmos_conversation_client.cosmosdb_client.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No assistant message found")
    await cosmos_conversation_client.cosmosdb_client.close()
    return {
        "id": conversation["id"],
        "title": conversation["title"],
        "updatedAt": conversation.get("updatedAt")}


async def rename_conversation(user_id: str, conversation_id, title):
    """Rename a conversation."""
    if not conversation_id:
        raise ValueError("No conversation_id found")

    cosmos_conversation_client = init_cosmosdb_client()
    conversation = await cosmos_conversation_client.get_conversation(user_id, conversation_id)

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} was not found. It either does not exist or the logged-in user does not have access to it.")

    conversation["title"] = title
    updated_conversation = await cosmos_conversation_client.upsert_conversation(
        conversation
    )

    return updated_conversation


async def update_message_feedback(
        user_id: str,
        message_id: str,
        message_feedback: str) -> Optional[dict]:
    """Update feedback for a specific message."""
    try:
        logger.info(
            f"Updating feedback for message_id: {message_id} by user: {user_id}")
        cosmos_conversation_client = init_cosmosdb_client()
        updated_message = await cosmos_conversation_client.update_message_feedback(user_id, message_id, message_feedback)

        if updated_message:
            logger.info(
                f"Successfully updated message_id: {message_id} with feedback: {message_feedback}")
            return updated_message
        else:
            logger.warning(f"Message ID {message_id} not found or access denied")
            return None
    except Exception:
        logger.exception(
            f"Error updating message feedback for message_id: {message_id}")
        raise


async def delete_conversation(user_id: str, conversation_id: str) -> bool:
    """
    Deletes a conversation and its messages from the database if the user has access.

    Args:
        user_id (str): The ID of the authenticated user.
        conversation_id (str): The ID of the conversation to delete.

    Returns:
        bool: True if the conversation was deleted successfully, False otherwise.
    """
    try:
        cosmos_conversation_client = init_cosmosdb_client()

        # Fetch conversation to ensure it exists and belongs to the user
        conversation = await cosmos_conversation_client.get_conversation(user_id, conversation_id)

        if not conversation:
            logger.warning(f"Conversation {conversation_id} not found.")
            return False

        if conversation["userId"] != user_id:
            logger.warning(
                f"User {user_id} does not have permission to delete {conversation_id}.")
            return False

        # Delete associated messages first (if applicable)
        await cosmos_conversation_client.delete_messages(conversation_id, user_id)

        # Delete the conversation itself
        await cosmos_conversation_client.delete_conversation(user_id, conversation_id)

        logger.info(f"Successfully deleted conversation {conversation_id}.")
        return True

    except Exception as e:
        logger.exception(f"Error deleting conversation {conversation_id}: {e}")
        return False


async def get_conversations(user_id: str, offset: int, limit: Optional[int]):
    """
    Retrieves a list of conversations for a given user.

    Args:
        user_id (str): The ID of the authenticated user.

    Returns:
        list: A list of conversation objects or an empty list if none exist.
    """
    try:
        cosmos_conversation_client = init_cosmosdb_client()
        if not cosmos_conversation_client:
            raise ValueError("CosmosDB is not configured or unavailable")

        conversations = await cosmos_conversation_client.get_conversations(user_id, offset=offset, limit=limit)

        return conversations or []
    except Exception:
        logger.exception(f"Error retrieving conversations for user {user_id}")
        return []


async def get_messages(user_id: str, conversation_id: str):
    """
    Retrieves all messages for a given conversation ID if the user has access.

    Args:
        user_id (str): The ID of the authenticated user.
        conversation_id (str): The ID of the conversation.

    Returns:
        list: A list of messages in the conversation.
    """
    try:
        cosmos_conversation_client = init_cosmosdb_client()
        if not cosmos_conversation_client:
            raise ValueError("CosmosDB is not configured or unavailable")

        # Fetch conversation to ensure it exists and belongs to the user
        conversation = await cosmos_conversation_client.get_conversation(user_id, conversation_id)
        if not conversation:
            logger.warning(f"Conversation {conversation_id} not found.")
            return []

        # Fetch messages associated with the conversation
        messages = await cosmos_conversation_client.get_messages(user_id, conversation_id)
        return messages

    except Exception as e:
        logger.exception(
            f"Error retrieving messages for conversation {conversation_id}: {e}")
        return []


async def get_conversation_messages(user_id: str, conversation_id: str):
    """
    Retrieves a single conversation and its messages for a given user.

    Args:
        user_id (str): The ID of the authenticated user.
        conversation_id (str): The ID of the conversation to retrieve.

    Returns:
        dict: The conversation object with messages or None if not found.
    """
    try:
        cosmos_conversation_client = init_cosmosdb_client()
        if not cosmos_conversation_client:
            raise ValueError("CosmosDB is not configured or unavailable")

        # Fetch the conversation details
        conversation = await cosmos_conversation_client.get_conversation(user_id, conversation_id)
        if not conversation:
            logger.warning(
                f"Conversation {conversation_id} not found for user {user_id}.")
            return None

        # Get messages related to the conversation
        conversation_messages = await cosmos_conversation_client.get_messages(user_id, conversation_id)

        # Format messages for the frontend
        messages = [
            {
                "id": msg["id"],
                "role": msg["role"],
                "content": msg["content"],
                "createdAt": msg["createdAt"],
                "feedback": msg.get("feedback"),
            }
            for msg in conversation_messages
        ]

        return messages
    except Exception:
        logger.exception(
            f"Error retrieving conversation {conversation_id} for user {user_id}")
        return None


async def clear_messages(user_id: str, conversation_id: str) -> bool:
    """
    Clears all messages in a conversation while keeping the conversation itself.

    Args:
        user_id (str): The ID of the authenticated user.
        conversation_id (str): The ID of the conversation.

    Returns:
        bool: True if messages were cleared successfully, False otherwise.
    """
    try:
        cosmos_conversation_client = init_cosmosdb_client()
        if not cosmos_conversation_client:
            raise ValueError("CosmosDB is not configured or unavailable")

        # Ensure the conversation exists and belongs to the user
        conversation = await cosmos_conversation_client.get_conversation(user_id, conversation_id)
        if not conversation:
            logger.warning(f"Conversation {conversation_id} not found.")
            return False

        if conversation["user_id"] != user_id:
            logger.warning(
                f"User {user_id} does not have permission to clear messages in {conversation_id}.")
            return False

        # Delete all messages associated with the conversation
        await cosmos_conversation_client.delete_messages(conversation_id, user_id)

        logger.info(
            f"Successfully cleared messages in conversation {conversation_id}.")
        return True

    except Exception as e:
        logger.exception(
            f"Error clearing messages for conversation {conversation_id}: {e}")
        return False


async def ensure_cosmos():
    """Ensure CosmosDB is properly configured and accessible."""
    try:
        cosmos_conversation_client = init_cosmosdb_client()
        success, err = await cosmos_conversation_client.ensure()
        return success, err
    except Exception as e:
        logger.exception(f"Error ensuring CosmosDB configuration: {e}")
        return False, str(e)


# Route handlers
@router.post("/generate")
async def add_conversation_route(request: Request):
    """Route handler for adding a new conversation."""
    try:
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers)
        user_id = authenticated_user["user_principal_id"]

        # Parse request body
        request_json = await request.json()

        response = await add_conversation(user_id, request_json)
        track_event_if_configured("ConversationCreated", {
            "user_id": user_id,
            "request": request_json,
        })
        return response

    except Exception as e:
        logger.exception("Exception in /generate: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.post("/update")
async def update_conversation_route(request: Request):
    """Route handler for updating a conversation."""
    try:
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers)
        user_id = authenticated_user["user_principal_id"]

        # Parse request body
        request_json = await request.json()
        conversation_id = request_json.get("conversation_id")

        if not conversation_id:
            raise HTTPException(status_code=400, detail="No conversation_id found")

        # Call update_conversation function
        update_response = await update_conversation(user_id, request_json)

        if not update_response:
            raise HTTPException(status_code=500, detail="Failed to update conversation")
        track_event_if_configured("ConversationUpdated", {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "title": update_response["title"]
        })

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "title": update_response["title"],
                    "date": update_response["updatedAt"],
                    "conversation_id": update_response["id"],
                },
            },
            status_code=200,
        )
    except Exception as e:
        logger.exception("Exception in /history/update: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.post("/message_feedback")
async def update_message_feedback_route(request: Request):
    """Route handler for updating message feedback."""
    try:
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers)
        user_id = authenticated_user["user_principal_id"]

        # Parse request body
        request_json = await request.json()
        message_id = request_json.get("message_id")
        message_feedback = request_json.get("message_feedback")

        if not message_id:
            track_event_if_configured("MessageFeedbackValidationError", {
                "error": "message_id is missing",
                "user_id": user_id
            })
            raise HTTPException(status_code=400, detail="message_id is required")

        if not message_feedback:
            track_event_if_configured("MessageFeedbackValidationError", {
                "error": "message_feedback is missing",
                "user_id": user_id
            })
            raise HTTPException(status_code=400, detail="message_feedback is required")

        # Call update_message_feedback function
        updated_message = await update_message_feedback(user_id, message_id, message_feedback)

        if updated_message:
            track_event_if_configured("MessageFeedbackUpdated", {
                "user_id": user_id,
                "message_id": message_id,
                "feedback": message_feedback
            })
            return JSONResponse(
                content={
                    "message": f"Successfully updated message with feedback {message_feedback}",
                    "message_id": message_id,
                },
                status_code=200,
            )
        else:
            track_event_if_configured("MessageFeedbackNotFound", {
                "user_id": user_id,
                "message_id": message_id
            })
            raise HTTPException(
                status_code=404,
                detail=f"Unable to update message {message_id}. It either does not exist or the user does not have access to it."
            )

    except Exception as e:
        logger.exception("Exception in /history/message_feedback: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.delete("/delete")
async def delete_conversation_route(request: Request):
    """Route handler for deleting a conversation."""
    try:
        # Get the user ID from request headers
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers)
        user_id = authenticated_user["user_principal_id"]
        # Parse request body
        request_json = await request.json()
        conversation_id = request_json.get("conversation_id")
        if not conversation_id:
            track_event_if_configured("DeleteConversationValidationError", {
                "error": "conversation_id is missing",
                "user_id": user_id
            })
            raise HTTPException(status_code=400, detail="conversation_id is required")

        # Delete conversation using delete_conversation function
        deleted = await delete_conversation(user_id, conversation_id)
        if deleted:
            track_event_if_configured("ConversationDeleted", {
                "user_id": user_id,
                "conversation_id": conversation_id
            })
            return JSONResponse(
                content={
                    "message": "Successfully deleted conversation and messages",
                    "conversation_id": conversation_id},
                status_code=200,
            )
        else:
            track_event_if_configured("DeleteConversationNotFound", {
                "user_id": user_id,
                "conversation_id": conversation_id
            })
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found or user does not have permission.")
    except Exception as e:
        logger.exception("Exception in /history/delete: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.get("/list")
async def list_conversations(
    request: Request,
    offset: int = Query(0, alias="offset"),
    limit: int = Query(25, alias="limit")
):
    """Route handler for listing conversations."""
    try:
        # await adjust_processed_data_dates()
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers)
        user_id = authenticated_user["user_principal_id"]

        logger.info(f"user_id: {user_id}, offset: {offset}, limit: {limit}")

        # Get conversations
        conversations = await get_conversations(user_id, offset=offset, limit=limit)

        if not isinstance(conversations, list):
            track_event_if_configured("ListConversationsNotFound", {
                "user_id": user_id,
                "offset": offset,
                "limit": limit
            })
            return JSONResponse(
                content={
                    "error": f"No conversations for {user_id} were found"},
                status_code=404)
        track_event_if_configured("ConversationsListed", {
            "user_id": user_id,
            "offset": offset,
            "limit": limit,
            "conversation_count": len(conversations)
        })
        return JSONResponse(content=conversations, status_code=200)

    except Exception as e:
        logger.exception("Exception in /history/list: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.post("/read")
async def get_conversation_messages_route(request: Request):
    """Route handler for reading conversation messages."""
    try:
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers)
        user_id = authenticated_user["user_principal_id"]

        # Parse request body
        request_json = await request.json()
        conversation_id = request_json.get("conversation_id")

        if not conversation_id:
            track_event_if_configured("ReadConversationValidationError", {
                "error": "conversation_id is required",
                "user_id": user_id
            })
            raise HTTPException(status_code=400, detail="conversation_id is required")

        # Get conversation details
        conversationMessages = await get_conversation_messages(user_id, conversation_id)
        if not conversationMessages:
            track_event_if_configured("ReadConversationNotFound", {
                "user_id": user_id,
                "conversation_id": conversation_id
            })
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} was not found. It either does not exist or the user does not have access to it."
            )
        track_event_if_configured("ConversationRead", {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "message_count": len(conversationMessages)
        })

        return JSONResponse(
            content={
                "conversation_id": conversation_id,
                "messages": conversationMessages},
            status_code=200)

    except Exception as e:
        logger.exception("Exception in /history/read: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.post("/rename")
async def rename_conversation_route(request: Request):
    """Route handler for renaming a conversation."""
    try:
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers)
        user_id = authenticated_user["user_principal_id"]

        # Parse request body
        request_json = await request.json()
        conversation_id = request_json.get("conversation_id")
        title = request_json.get("title")

        if not conversation_id:
            track_event_if_configured("RenameConversationValidationError", {
                "error": "conversation_id is required",
                "user_id": user_id
            })
            raise HTTPException(status_code=400, detail="conversation_id is required")
        if not title:
            track_event_if_configured("RenameConversationValidationError", {
                "error": "title is required",
                "user_id": user_id
            })
            raise HTTPException(status_code=400, detail="title is required")

        rename_result = await rename_conversation(user_id, conversation_id, title)

        track_event_if_configured("ConversationRenamed", {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "new_title": title
        })

        return JSONResponse(content=rename_result, status_code=200)

    except Exception as e:
        logger.exception("Exception in /history/rename: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.delete("/delete_all")
async def delete_all_conversations(request: Request):
    """Route handler for deleting all conversations for a user."""
    try:
        # Get the user ID from request headers
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers)
        user_id = authenticated_user["user_principal_id"]

        # Get all user conversations
        conversations = await get_conversations(user_id, offset=0, limit=None)
        if not conversations:
            track_event_if_configured("DeleteAllConversationsNotFound", {
                "user_id": user_id
            })
            raise HTTPException(status_code=404,
                                detail=f"No conversations for {user_id} were found")

        # Delete all conversations
        for conversation in conversations:
            await delete_conversation(user_id, conversation["id"])

        track_event_if_configured("AllConversationsDeleted", {
            "user_id": user_id,
            "deleted_count": len(conversations)
        })

        return JSONResponse(
            content={
                "message": f"Successfully deleted all conversations for user {user_id}"},
            status_code=200,
        )

    except Exception as e:
        logging.exception("Exception in /history/delete_all: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.post("/clear")
async def clear_messages_route(request: Request):
    """Route handler for clearing messages in a conversation."""
    try:
        # Get the user ID from request headers
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers)
        user_id = authenticated_user["user_principal_id"]

        # Parse request body
        request_json = await request.json()
        conversation_id = request_json.get("conversation_id")

        if not conversation_id:
            track_event_if_configured("ClearMessagesValidationError", {
                "error": "conversation_id is required",
                "user_id": user_id
            })
            raise HTTPException(status_code=400, detail="conversation_id is required")

        # Delete conversation messages from CosmosDB
        success = await clear_messages(user_id, conversation_id)

        if not success:
            track_event_if_configured("ClearMessagesFailed", {
                "user_id": user_id,
                "conversation_id": conversation_id
            })
            raise HTTPException(
                status_code=404,
                detail="Failed to clear messages or conversation not found")
        track_event_if_configured("MessagesCleared", {
            "user_id": user_id,
            "conversation_id": conversation_id
        })

        return JSONResponse(
            content={
                "message": "Successfully cleared messages"},
            status_code=200)

    except Exception as e:
        logger.exception("Exception in /history/clear: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.get("/history/ensure")
async def ensure_cosmos_route():
    """Route handler for ensuring CosmosDB configuration."""
    try:
        success, err = await ensure_cosmos()
        if not success:
            track_event_if_configured("CosmosDBEnsureFailed", {
                "error": err or "Unknown error occurred"
            })
            return JSONResponse(
                content={
                    "error": err or "Unknown error occurred"},
                status_code=422)
        track_event_if_configured("CosmosDBEnsureSuccess", {
            "status": "CosmosDB is configured and working"
        })

        return JSONResponse(
            content={
                "message": "CosmosDB is configured and working"},
            status_code=200)
    except Exception as e:
        logger.exception("Exception in /history/ensure: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        cosmos_exception = str(e)

        if "Invalid credentials" in cosmos_exception:
            return JSONResponse(content={"error": "Invalid credentials"}, status_code=401)
        elif "Invalid CosmosDB database name" in cosmos_exception or "Invalid CosmosDB container name" in cosmos_exception:
            return JSONResponse(content={"error": "Invalid CosmosDB configuration"}, status_code=422)
        else:
            return JSONResponse(
                content={
                    "error": "CosmosDB is not configured or not working"},
                status_code=500)
