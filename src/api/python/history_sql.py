import json
import logging
import os
import struct
import uuid
from datetime import datetime, date
from typing import Tuple, Any
from decimal import Decimal
from azure.ai.projects.aio import AIProjectClient
from pydantic import BaseModel, ConfigDict
import pyodbc
from azure.identity.aio import AzureCliCredential
from azure.monitor.events.extension import track_event
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from auth.auth_utils import get_authenticated_user_details
from auth.azure_credential_utils import get_azure_credential_async

from agent_framework import ChatAgent
from agent_framework.azure import AzureAIClient
from agent_framework.exceptions import ServiceResponseException

router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Suppress INFO logs from 'azure.core.pipeline.policies.http_logging_policy'
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)
logging.getLogger("azure.identity.aio._internal").setLevel(logging.WARNING)

# Suppress info logs from OpenTelemetry exporter
logging.getLogger("azure.monitor.opentelemetry.exporter.export._base").setLevel(
    logging.ERROR
)

# Azure AI Foundry configuration
AZURE_AI_AGENT_ENDPOINT = os.getenv("AZURE_AI_AGENT_ENDPOINT")
AGENT_NAME_TITLE = os.getenv("AGENT_NAME_TITLE")

# Database configuration


def track_event_if_configured(event_name: str, event_data: dict):
    """
    Track an event with Application Insights if configured.

    Args:
        event_name (str): The name of the event to track.
        event_data (dict): The data to associate with the event.
    """
    instrumentation_key = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if instrumentation_key:
        track_event(event_name, event_data)
    else:
        logging.warning("Skipping track_event for %s as Application Insights is not configured", event_name)


async def get_fabric_db_connection():
    """
    Get a connection to the SQL database.

    Returns:
        Connection: Database connection object, or None if connection fails.
    """
    app_env = os.getenv("APP_ENV", "prod").lower()
    database = os.getenv("FABRIC_SQL_DATABASE")
    server = os.getenv("FABRIC_SQL_SERVER")
    driver17 = "ODBC Driver 17 for SQL Server"
    driver18 = "ODBC Driver 18 for SQL Server"
    api_uid = os.getenv("API_UID", "")
    fabric_sql_connection_string18 = os.getenv("FABRIC_SQL_CONNECTION_STRING", "")
    fabric_sql_connection_string17 = f"DRIVER={driver17};SERVER={server};DATABASE={database};UID={api_uid};Authentication=ActiveDirectoryMSI"

    try:
        conn = None
        try:
            if app_env == 'dev':
                credential = AzureCliCredential()
                try:
                    token = await credential.get_token("https://database.windows.net/.default")
                    token_bytes = token.token.encode("utf-16-LE")
                    token_struct = struct.pack(
                        f"<I{len(token_bytes)}s",
                        len(token_bytes),
                        token_bytes
                    )
                    SQL_COPT_SS_ACCESS_TOKEN = 1256
                    connection_string = f"DRIVER={driver18};SERVER={server};DATABASE={database};"
                    conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
                finally:
                    await credential.close()
            else:
                # connection_string = f"DRIVER={driver};SERVER={server};DATABASE={database};UID={api_uid};Authentication=ActiveDirectoryMSI;"
                conn = pyodbc.connect(fabric_sql_connection_string18)
        except Exception:
            if app_env == 'dev':
                credential = AzureCliCredential()
                try:
                    token = await credential.get_token("https://database.windows.net/.default")
                    token_bytes = token.token.encode("utf-16-LE")
                    token_struct = struct.pack(
                        f"<I{len(token_bytes)}s",
                        len(token_bytes),
                        token_bytes
                    )
                    SQL_COPT_SS_ACCESS_TOKEN = 1256
                    connection_string = f"DRIVER={driver17};SERVER={server};DATABASE={database};"
                    conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
                finally:
                    await credential.close()
            else:
                conn = pyodbc.connect(fabric_sql_connection_string17)

        return conn
    except pyodbc.Error as e:
        logging.info("FABRIC-SQL:Failed to connect Fabric SQL Database: %s", e)
        return None


async def run_nonquery_params(sql_query, params: Tuple[Any, ...] = ()):
    """
    Execute a SQL non-query operation like DELETE, INSERT, or UPDATE.

    Args:
        sql_query (str): The SQL query to execute with parameter placeholders.
        params (Tuple[Any, ...]): Parameters to bind to the query.

    Returns:
        bool: True if the operation was successful, False otherwise.
    """
    conn = await get_fabric_db_connection()
    if not conn:
        logging.error("Database connection failed in run_nonquery_params")
        return False
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(sql_query, params)
        conn.commit()
        return True
    except Exception as e:
        logging.error("Error executing SQL query: %s", e)
        return False
    finally:
        if cursor:
            cursor.close()
        conn.close()


async def run_query_params(sql_query, params: Tuple[Any, ...] = ()):
    """
    Execute parameterized SQL query and return results as list of dictionaries.

    Args:
        sql_query (str): The SQL query to execute with parameter placeholders.
        params (Tuple[Any, ...): Parameters to bind to the query.

    Returns:
        list: List of dictionaries containing query results, or None if an error occurs.
    """
    # Connect to the database
    conn = await get_fabric_db_connection()
    if not conn:
        logging.error("Database connection failed in run_query_params")
        return None
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(sql_query, params)
        columns = [desc[0] for desc in cursor.description]
        result = []
        for row in cursor.fetchall():
            row_dict = {}
            for col_name, value in zip(columns, row):
                if isinstance(value, (datetime, date)):
                    row_dict[col_name] = value.isoformat()
                elif isinstance(value, Decimal):
                    row_dict[col_name] = float(value)
                else:
                    row_dict[col_name] = value
            result.append(row_dict)

        return result
    except Exception as e:
        logging.error("Error executing SQL query: %s", e)
        return None
    finally:
        if cursor:
            cursor.close()
        conn.close()


class SqlQueryTool(BaseModel):
    """SQL query tool for executing database queries using Agent Framework."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    pyodbc_conn: pyodbc.Connection

    async def run_sql_query(self, sql_query):
        """Execute parameterized SQL query and return results as list of dictionaries."""
        # Connect to the database
        cursor = None
        try:
            logger.info("Chat Agent - Executing SQL query: %s", sql_query)
            cursor = self.pyodbc_conn.cursor()
            cursor.execute(sql_query)
            columns = [desc[0] for desc in cursor.description]
            result = []
            for row in cursor.fetchall():
                row_dict = {}
                for col_name, value in zip(columns, row):
                    if isinstance(value, (datetime, date)):
                        row_dict[col_name] = value.isoformat()
                    elif isinstance(value, Decimal):
                        row_dict[col_name] = float(value)
                    else:
                        row_dict[col_name] = value
                result.append(row_dict)
            logger.info("Chat Agent - Result of SQL query: %s", result)
            return json.dumps(result, default=str) if result else "No results found."
        except Exception as e:
            logger.error("Chat Agent - Error executing SQL query: %s", e)
            return f"SQL query failed with error: {str(e)}. Please fix the query and try again."
        finally:
            if cursor:
                cursor.close()


# Configuration variable
USE_CHAT_HISTORY_ENABLED = os.getenv("USE_CHAT_HISTORY_ENABLED", "true").lower() == "true"


async def get_conversations(user_id, limit, sort_order="DESC", offset=0):
    """
    Retrieve conversations for a specific user with pagination and sorting.

    Args:
        user_id (str): The ID of the user whose conversations to retrieve.
        limit (int): Maximum number of conversations to return.
        sort_order (str): Sort order for conversations ("DESC" or "ASC").
        offset (int): Number of conversations to skip for pagination.

    Returns:
        list: List of conversation dictionaries.

    Raises:
        Exception: If an error occurs during conversation retrieval.
    """
    try:
        query = ""
        params = ()
        if user_id:
            query = f"SELECT conversation_id, title, createdAt, updatedAt FROM hst_conversations where userId = ? order by updatedAt {sort_order}"
            params = (user_id,)
        else:  # If no user_id is provided, return all conversations -- This is for local testing purposes
            query = f"SELECT conversation_id, title, createdAt, updatedAt FROM hst_conversations ORDER BY updatedAt {sort_order}"
            params = ()

        result = await run_query_params(query, params)
        return result
    except Exception:
        logger.exception("Error in get_conversation")
        raise


async def get_conversation_messages(user_id: str, conversation_id: str, sort_order="ASC"):
    """
    Retrieve all messages for a specific conversation.

    Args:
        user_id (str): The ID of the user requesting the messages.
        conversation_id (str): The ID of the conversation to retrieve.

    Returns:
        list: List of message dictionaries with deserialized citations, or None if an error occurs.
    """
    try:
        if not conversation_id:
            logger.warning("No conversation_id found, cannot retrieve conversation messages.")
            return None

        query = ""
        params = ()
        if user_id:
            query = f"SELECT role, content, citations, feedback FROM hst_conversation_messages where userId = ? and conversation_id = ? order by updatedAt {sort_order}"
            params = (user_id, conversation_id)
        else:  # If no user_id is provided, return all conversation messages -- This is for local testing purposes
            query = f"SELECT role, content, citations, feedback FROM hst_conversation_messages where conversation_id = ? order by updatedAt {sort_order}"
            params = (conversation_id,)

        result = await run_query_params(query, params)
        # Process the result to deserialize citations
        processed_result = []
        for message in result:
            processed_message = dict(message)
            # Deserialize citations from JSON string back to list
            if processed_message.get("citations"):
                try:
                    processed_message["citations"] = json.loads(processed_message["citations"])
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning("Failed to deserialize citations: %s", e)
                    processed_message["citations"] = []
            else:
                processed_message["citations"] = []

            # Deserialize content if it's a JSON string
            content = processed_message.get("content")
            if isinstance(content, str):
                try:
                    # Try to parse as JSON
                    processed_message["content"] = json.loads(content)
                except (json.JSONDecodeError, TypeError):
                    # Leave as string if not JSON
                    processed_message["content"] = content
            processed_result.append(processed_message)

        return processed_result
    except Exception:
        logger.exception(
            "Error retrieving conversation %s for user %s", conversation_id, user_id
        )
        return None


async def delete_conversation(user_id: str, conversation_id: str) -> bool:
    """
    Delete a specific conversation and all its messages for a user.

    Args:
        user_id (str): The ID of the user who owns the conversation.
        conversation_id (str): The ID of the conversation to delete.

    Returns:
        bool: True if the conversation was successfully deleted, False otherwise.
    """
    try:
        if not conversation_id:
            logger.warning("No conversation_id found, cannot delete conversation.")
            return False

        query = "SELECT userId, conversation_id FROM hst_conversations where conversation_id = ?"
        conversation = await run_query_params(query, (conversation_id,))
        if not conversation or len(conversation) == 0:
            logger.warning("Conversation %s not found.", conversation_id)
            return False

        # If the userId in the conversation does not match the user_id, deny access
        if user_id and conversation and conversation[0]["userId"] != user_id:
            logger.warning(
                "User %s does not have permission to delete %s.", user_id, conversation_id
            )
            return False

        if user_id:
            # Prepare parameters for deletion
            params = (user_id, conversation_id)
            # Delete associated messages first (if applicable)
            query_m = "DELETE FROM hst_conversation_messages where userId = ?  and conversation_id = ?"
            await run_nonquery_params(query_m, params)

            # Delete the conversation itself
            query_m = "DELETE FROM hst_conversations where userId = ?  and conversation_id = ?"
            await run_nonquery_params(query_m, params)
        else:
            params = (conversation_id)
            # Delete associated messages first (if applicable)
            query_m = "DELETE FROM hst_conversation_messages where conversation_id = ?"
            await run_nonquery_params(query_m, params)

            # Delete the conversation itself
            query_c = "DELETE FROM hst_conversations where conversation_id = ?"
            await run_nonquery_params(query_c, params)

        return True

    except Exception as e:
        logger.exception("Error deleting conversation %s: %s", conversation_id, e)
        return False


async def delete_all_conversations(user_id: str) -> bool:
    """
    Delete all conversations and messages for a specific user.

    Args:
        user_id (str): The ID of the user whose conversations should be deleted.

    Returns:
        bool: True if all conversations were successfully deleted, False otherwise.
    """
    try:

        if user_id:
            # Delete all associated messages
            query_m = "DELETE FROM hst_conversation_messages WHERE userId = ?"
            messages_result = await run_nonquery_params(query_m, (user_id,))

            # Delete all conversations
            query_c = "DELETE FROM hst_conversations WHERE userId = ?"
            conversations_result = await run_nonquery_params(query_c, (user_id,))
        else:
            # If user_id is None, delete all conversations without user filtering
            query_m = "DELETE FROM hst_conversation_messages"
            messages_result = await run_nonquery_params(query_m)

            query_c = "DELETE FROM hst_conversations"
            conversations_result = await run_nonquery_params(query_c)

        # Verify deletion was successful
        if messages_result is False or conversations_result is False:
            logger.error("Failed to delete all conversations for user %s", user_id)
            return False

        return True

    except Exception as e:
        logger.exception("Error deleting all conversations for user %s: %s", user_id, e)
        return False


async def rename_conversation(user_id: str, conversation_id, title) -> bool:
    """
    Update the title of a specific conversation.

    Args:
        user_id (str): The ID of the user who owns the conversation.
        conversation_id (str): The ID of the conversation to rename.
        title (str): The new title for the conversation.

    Returns:
        bool: True if the conversation was successfully renamed, False otherwise.
    """
    try:
        if not conversation_id:
            raise ValueError("No conversation_id found")

        if title is None:
            logger.warning("Title is None, cannot rename title of the conversation %s.", conversation_id)
            return False

        query = "SELECT userId, conversation_id FROM hst_conversations where conversation_id = ?"
        conversation = await run_query_params(query, (conversation_id,))

        # Check if the conversation exists
        if not conversation or len(conversation) == 0:
            logger.warning("Conversation %s not found.", conversation_id)
            return False

        # Check if the user has permission to rename it
        if user_id and conversation and conversation[0]["userId"] != user_id:
            logger.warning(
                "User %s does not have permission to rename %s.", user_id, conversation_id
            )
            return False

        # Update the title of the conversation
        if user_id:
            query_t = "UPDATE hst_conversations SET title = ? WHERE userId = ?  and conversation_id = ?"
            await run_nonquery_params(query_t, (title, user_id, conversation_id))
        else:
            query_t = "UPDATE hst_conversations SET title = ? WHERE conversation_id = ?"
            await run_nonquery_params(query_t, (title, conversation_id))

        return True
    except Exception as e:
        logger.exception("Error updating title of conversation %s to '%s': %s", conversation_id, title, e)
        return False


async def generate_title(conversation_messages):
    """
    Generate a concise title for a conversation using Azure AI Foundry agent.

    Args:
        conversation_messages (list): List of messages in the conversation.

    Returns:
        str: A 4-word or less title summarizing the conversation.
    """

    try:
        # Get the last user message for title generation
        user_messages = [msg for msg in conversation_messages if msg["role"] == "user"]

        if not user_messages:
            logger.debug("No user messages found, returning default title")
            return generate_fallback_title(conversation_messages)

        # Combine all user messages with the title prompt
        combined_content = "\n".join([msg["content"] for msg in user_messages])
        final_prompt = f"Generate a 4-word or less title for this request:\n{combined_content}"
        if not AZURE_AI_AGENT_ENDPOINT:
            logger.warning("Azure AI Agent endpoint not configured, using fallback title generation")
            return generate_fallback_title(conversation_messages)

        async with AIProjectClient(
            endpoint=AZURE_AI_AGENT_ENDPOINT,
            credential=await get_azure_credential_async()
        ) as project_client:
            chat_client = AzureAIClient(
                project_client=project_client,
                agent_name=AGENT_NAME_TITLE,
                use_latest_version=True,
            )

            async with ChatAgent(
                chat_client=chat_client,
                tool_choice="none",
            ) as chat_agent:
                thread = chat_agent.get_new_thread()
                result = await chat_agent.run(messages=final_prompt, thread=thread)
                return str(result).strip() if result is not None else generate_fallback_title(conversation_messages)

    except ServiceResponseException as sre:
        logger.warning("ServiceResponseException generating title with Azure AI Foundry agent: %s", sre)
        return generate_fallback_title(conversation_messages)

    except Exception as e:
        logger.warning("Error generating title with Azure AI Foundry agent: %s", e)
        return generate_fallback_title(conversation_messages)


def generate_fallback_title(conversation_messages):
    """
    Generate a fallback title from conversation messages when AI generation fails.

    Args:
        conversation_messages (list): List of messages in the conversation.

    Returns:
        str: A fallback title based on the first user message.
    """
    user_messages = [msg for msg in conversation_messages if msg["role"] == "user"]
    if user_messages:
        first_message = user_messages[0]["content"]
        return _generate_fallback_title_from_message(first_message)
    return "New Conversation"


def _generate_fallback_title_from_message(message_content):
    """
    Generate a fallback title from a single message when AI generation fails.

    Args:
        message_content (str): The message content to generate title from.

    Returns:
        str: A fallback title based on the first few words of the message.
    """
    if isinstance(message_content, dict):
        # If content is a dictionary, try to extract text
        message_content = str(message_content)

    if message_content:
        # Create a simple title from first 4 words
        words = str(message_content).split()[:4]
        title = " ".join(words) if words else "New Conversation"
        return title if title.strip() else "New Conversation"
    return "New Conversation"


async def create_conversation(user_id, title="", conversation_id=None):
    """
    Create a new conversation or return existing one if it already exists.

    Args:
        user_id (str): The ID of the user creating the conversation.
        title (str): The title for the conversation. Defaults to empty string.
        conversation_id (str): The ID for the conversation. Generated if None.

    Returns:
        bool: True if conversation was created successfully, existing conversation if it already exists.

    Raises:
        Exception: If an error occurs during conversation creation.
    """
    try:
        # if not user_id:
        #     logger.warning("No User ID found, cannot create conversation.")
        #     return None

        if not conversation_id:
            logger.warning("No conversation_id found, generating a new one.")
            conversation_id = str(uuid.uuid4())

        # Check if conversation already exists
        query = "SELECT * FROM hst_conversations where conversation_id = ?"
        existing_conversation = await run_query_params(query, (conversation_id,))
        if existing_conversation and len(existing_conversation) > 0:
            return existing_conversation

        utc_now = datetime.utcnow().isoformat()
        query = "INSERT INTO hst_conversations (userId, conversation_id, title, createdAt, updatedAt) VALUES (?, ?, ?, ?, ?)"
        params = (user_id, conversation_id, title, utc_now, utc_now)
        resp = await run_nonquery_params(query, params)
        return resp
    except Exception:
        logger.exception("Error in create_conversation")
        raise


async def create_message(uuid, conversation_id, user_id, input_message: dict):
    """
    Create a new message in a conversation.

    Args:
        uuid (str): Unique identifier for the message.
        conversation_id (str): The ID of the conversation to add the message to.
        user_id (str): The ID of the user creating the message.
        input_message (dict): Dictionary containing message data including role, content, and citations.

    Returns:
        bool: True if the message was created successfully, False otherwise.

    Raises:
        Exception: If an error occurs during message creation.
    """
    try:
        # if not user_id:
        #     logger.warning("No User ID found, cannot create message.")
        #     return None

        if not conversation_id:
            logger.warning("No conversation_id found, cannot create conversation message.")
            return None

        # Ensure the conversation exists
        query = "SELECT * FROM hst_conversations where conversation_id = ?"
        exist_conversation = await run_query_params(query, (conversation_id,))
        if not exist_conversation or len(exist_conversation) == 0:
            logger.error("Conversation not found for ID: %s", conversation_id)
            return None

        utc_now = datetime.utcnow().isoformat()
        feedback = ""

        # Extract citations from input_message
        citations_json = ""
        if "citations" in input_message and input_message["citations"]:
            # Convert citations list to JSON string for storage
            try:
                citations_json = json.dumps(input_message["citations"])
            except (TypeError, ValueError) as e:
                logger.warning("Failed to serialize citations: %s", e)
                citations_json = ""

        query = (
            "INSERT INTO hst_conversation_messages ("
            "userId, "
            "conversation_id, "
            "role, "
            "content_id, "
            "content, "
            "citations, "
            "feedback, "
            "createdAt, "
            "updatedAt"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        content = input_message["content"]
        if isinstance(content, dict):
            content = json.dumps(content)
            print(content)
        params = (user_id, conversation_id, input_message["role"], input_message["id"],
                  content, citations_json, feedback, utc_now, utc_now)
        resp = await run_nonquery_params(query, params)

        if resp:
            # Update the conversation's updatedAt timestamp
            query_t = "UPDATE hst_conversations SET updatedAt = ? WHERE conversation_id = ?"
            resp = await run_nonquery_params(query_t, (utc_now, conversation_id))

            return resp
        else:
            return False

    except Exception:
        logger.exception("Error in create_message")
        raise


async def update_conversation(user_id: str, request_json: dict):
    """
    Update conversation with new messages or create new conversation if it doesn't exist.

    Args:
        user_id (str): The ID of the user updating the conversation.
        request_json (dict): Dictionary containing conversation_id and messages to add.

    Returns:
        dict: Dictionary containing conversation id, title, and updatedAt timestamp, or None if update fails.

    Raises:
        HTTPException: If validation fails or required messages are not found.
        Exception: If an error occurs during conversation update.
    """
    try:
        conversation_id = request_json.get("conversation_id")
        messages = request_json.get("messages", [])

        # if not user_id:
        #     logger.warning("No User ID found, cannot update conversation.")
        #     return None

        # conversation = None
        query = "SELECT * FROM hst_conversations where conversation_id = ?"
        conversation = await run_query_params(query, (conversation_id,))

        if not conversation or len(conversation) == 0:
            title = await generate_title(messages)
            await create_conversation(user_id=user_id, conversation_id=conversation_id, title=title)

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
            createdMessageValue = await create_message(
                uuid=str(uuid.uuid4()),
                conversation_id=conversation_id,
                user_id=user_id,
                input_message=user_message,
            )

            if not createdMessageValue:
                logger.warning("Conversation not found for ID: %s", conversation_id)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Conversation not found"
                )
        else:
            logger.warning("No user message found in request")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User message not found"
            )

        messages = request_json["messages"]
        if len(messages) > 0 and messages[-1]["role"] == "assistant":
            if len(messages) > 1 and messages[-2].get("role", None) == "tool":
                # write the tool message first
                await create_message(
                    uuid=str(uuid.uuid4()),
                    conversation_id=conversation_id,
                    user_id=user_id,
                    input_message=messages[-2],
                )
            # write the assistant message
            await create_message(
                uuid=messages[-1]["id"],
                conversation_id=conversation_id,
                user_id=user_id,
                input_message=messages[-1],
            )
        else:
            logger.warning("No assistant message found in request")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assistant message not found"
            )

        queryReturn = "SELECT * FROM hst_conversations where conversation_id = ?"
        conversationUpdated = await run_query_params(queryReturn, (conversation_id,))

        if conversationUpdated and len(conversationUpdated) > 0:
            return {
                "id": conversationUpdated[0].get("conversation_id"),
                "title": conversationUpdated[0].get("title"),
                "updatedAt": conversationUpdated[0].get("updatedAt")}
        else:
            return None

    except Exception:
        logger.exception("Error in update_conversation")
        raise


@router.get("/list")
async def list_conversations(
    request: Request,
    offset: int = Query(0, alias="offset"),
    limit: int = Query(25, alias="limit")
):
    """
    List conversations for authenticated user with pagination.

    Args:
        request (Request): FastAPI request object containing authentication headers.
        offset (int): Number of conversations to skip for pagination.
        limit (int): Maximum number of conversations to return.

    Returns:
        JSONResponse: Response containing list of conversations or error message.

    Raises:
        HTTPException: If authentication fails or validation errors occur.
    """
    try:
        # from chat import adjust_processed_data_dates
        # await adjust_processed_data_dates()

        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers
        )
        user_id = authenticated_user["user_principal_id"]

        logger.info("Historyfab list-API: user_id: %s, offset: %s, limit: %s", user_id, offset, limit)

        # Get conversations
        conversations = await get_conversations(user_id, offset=offset, limit=limit)
        if user_id:
            track_event_if_configured("ConversationsListed", {
                "user_id": user_id,
                "offset": offset,
                "limit": limit,
                "conversation_count": len(conversations)
            })

        return JSONResponse(content=conversations, status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Exception in /historyfab/list: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.get("/read")
async def get_conversation_messages_endpoint(request: Request, id: str = Query(...)):
    """
    Get messages for a specific conversation.

    Args:
        request (Request): FastAPI request object containing authentication headers.
        id (str): The conversation ID to retrieve messages for.

    Returns:
        JSONResponse: Response containing conversation messages or error message.

    Raises:
        HTTPException: If authentication fails, conversation not found, or validation errors occur.
    """
    try:
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers
        )
        user_id = authenticated_user["user_principal_id"]

        conversation_id = id

        if not conversation_id:
            if user_id:
                track_event_if_configured("ReadConversationValidationError", {
                    "error": "conversation_id is required",
                    "user_id": user_id
                })
            raise HTTPException(status_code=400, detail="conversation_id is required")

        # Get conversation message details
        conversationMessages = await get_conversation_messages(user_id, conversation_id)
        if not conversationMessages or len(conversationMessages) == 0:
            if user_id:
                track_event_if_configured("ReadConversationNotFound", {
                    "user_id": user_id,
                    "conversation_id": conversation_id
                })
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} was not found. It either does not exist or the user does not have access to it."
            )

        if user_id:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Exception in /historyfab/read: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.delete("/delete")
async def delete_conversation_endpoint(request: Request, id: str = Query(...)):
    """
    Delete a specific conversation and its messages.

    Args:
        request (Request): FastAPI request object containing authentication headers.
        id (str): The conversation ID to delete.

    Returns:
        JSONResponse: Response indicating success or failure.

    Raises:
        HTTPException: If authentication fails, conversation not found, or user lacks permission.
    """
    try:
        # Get the user ID from request headers
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers
        )
        user_id = authenticated_user["user_principal_id"]

        conversation_id = id
        if not conversation_id:
            track_event_if_configured("DeleteConversationValidationError", {
                "error": "conversation_id is missing",
                "user_id": user_id
            })
            raise HTTPException(status_code=400, detail="conversation_id is required")

        # Delete conversation using HistoryService
        deleted = await delete_conversation(user_id, conversation_id)
        if deleted:
            if user_id:
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
            if user_id:
                track_event_if_configured("DeleteConversationNotFound", {
                    "user_id": user_id,
                    "conversation_id": conversation_id
                })
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found or user does not have permission to delete.")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Exception in /historyfab/delete: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.delete("/delete_all")
async def delete_all_conversations_endpoint(request: Request):
    """
    Delete all conversations for authenticated user.

    Args:
        request (Request): FastAPI request object containing authentication headers.

    Returns:
        JSONResponse: Response indicating success or failure.

    Raises:
        HTTPException: If authentication fails or no conversations found.
    """
    try:
        # Get the user ID from request headers
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers)
        user_id = authenticated_user["user_principal_id"]

        # if not user_id:
        #     track_event_if_configured("DeleteAllConversationsValidationError", {
        #         "error": "user_id is missing",
        #         "user_id": user_id
        #     })
        #     raise HTTPException(status_code=400, detail="user_id is required")
        # Get all user conversations
        conversations = await get_conversations(user_id, offset=0, limit=None)
        if not conversations:
            track_event_if_configured("DeleteAllConversationsNotFound", {
                "user_id": user_id
            })
            raise HTTPException(status_code=404,
                                detail=f"No conversations for {user_id} were found")

        # Delete all conversations
        deleted = await delete_all_conversations(user_id)
        if deleted:
            if user_id:
                track_event_if_configured("AllConversationsDeleted", {
                    "user_id": user_id,
                    "deleted_count": len(conversations)
                })
            return JSONResponse(
                content={
                    "message": f"Successfully deleted all conversations for user {user_id}"},
                status_code=200,
            )
        else:
            if user_id:
                track_event_if_configured("DeleteAllConversationsNotFound", {
                    "user_id": user_id
                })
            raise HTTPException(
                status_code=404,
                detail=f"Conversation not found for user {user_id}")
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Exception in /historyfab/delete_all: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.post("/rename")
async def rename_conversation_endpoint(request: Request):
    """
    Rename a conversation's title.

    Args:
        request (Request): FastAPI request object containing authentication headers and JSON body with conversation_id and title.

    Returns:
        JSONResponse: Response indicating success or failure.

    Raises:
        HTTPException: If authentication fails, validation errors occur, or conversation not found.
    """
    try:
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers)
        user_id = authenticated_user["user_principal_id"]

        # Parse request body
        request_json = await request.json()
        conversation_id = request_json.get("conversation_id")
        title = request_json.get("title")

        if not conversation_id:
            if user_id:
                track_event_if_configured("RenameConversationValidationError", {
                    "error": "conversation_id is required",
                    "user_id": user_id
                })
            raise HTTPException(status_code=400, detail="conversation_id is required")
        if not title:
            if user_id:
                track_event_if_configured("RenameConversationValidationError", {
                    "error": "title is required",
                    "user_id": user_id
                })
            raise HTTPException(status_code=400, detail="title is required")

        rename_result = await rename_conversation(user_id, conversation_id, title)

        if rename_result:
            if user_id:
                track_event_if_configured("ConversationRenamedTitle", {
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "new_title": title
                })
            return JSONResponse(
                content={
                    "message": f"Successfully renamed title of conversation {conversation_id} to title '{title}'"},
                status_code=200,
            )
        else:
            if user_id:
                track_event_if_configured("ConversationRenamedTitleNotFound", {
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "new_title": title
                })
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found or user does not have permission to rename.")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Exception in /historyfab/rename: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)


@router.post("/update")
async def update_conversation_endpoint(request: Request):
    """
    Update conversation with new messages.

    Args:
        request (Request): FastAPI request object containing authentication headers and JSON body with conversation data.

    Returns:
        JSONResponse: Response containing updated conversation details or error message.

    Raises:
        HTTPException: If authentication fails or validation errors occur.
    """
    try:
        authenticated_user = get_authenticated_user_details(
            request_headers=request.headers)
        user_id = authenticated_user["user_principal_id"]

        # Parse request body
        request_json = await request.json()
        conversation_id = request_json.get("conversation_id")
        # logging.info("FABRIC-fab-update_conversation-request_json: %s" % request_json)
        if not conversation_id:
            raise HTTPException(status_code=400, detail="No conversation_id found")

        # Call HistoryService to update conversation
        update_response = await update_conversation(user_id, request_json)

        if not update_response:
            if user_id:
                track_event_if_configured("ConversationUpdated", {
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "title": update_response["title"]
                })
            raise HTTPException(status_code=500, detail="Failed to update conversation")

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
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Exception in /historyfab/update: %s", str(e))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
        return JSONResponse(content={"error": "An internal error has occurred!"}, status_code=500)
