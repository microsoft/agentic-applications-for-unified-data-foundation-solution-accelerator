"""
Chat API module for handling chat interactions and responses.
"""

import asyncio
import json
import logging
import os
import random
import re

from cachetools import TTLCache
from dotenv import load_dotenv
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

# Azure SDK
from azure.ai.agents.models import TruncationObject
from azure.monitor.events.extension import track_event
from azure.monitor.opentelemetry import configure_azure_monitor
from azure.ai.projects.aio import AIProjectClient

from agent_framework import ChatAgent
from agent_framework.azure import AzureAIClient
from agent_framework.exceptions import ServiceResponseException

# Azure Auth
from auth.azure_credential_utils import get_azure_credential_async

load_dotenv()

# Constants
HOST_NAME = "Agentic Applications for Unified Data Foundation"
HOST_INSTRUCTIONS = "Answer questions about Sales, Products and Orders data."

# Workshop mode configuration
IS_WORKSHOP = os.getenv("IS_WORKSHOP", "false").lower() == "true"
AZURE_ENV_ONLY = os.getenv("AZURE_ENV_ONLY", "true").lower() == "true"

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
    logging.warning("No Application Insights Instrumentation Key found. Skipping configuration")

# Configure logging
logging.basicConfig(level=logging.INFO)

# Suppress INFO logs from 'azure.core.pipeline.policies.http_logging_policy'
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)
logging.getLogger("azure.identity.aio._internal").setLevel(logging.WARNING)

# Suppress info logs from OpenTelemetry exporter
logging.getLogger("azure.monitor.opentelemetry.exporter.export._base").setLevel(
    logging.WARNING
)


class ExpCache(TTLCache):
    """Extended TTLCache that deletes Azure AI agent threads when items expire."""

    def __init__(self, *args, **kwargs):
        """Initialize cache without creating persistent client connections."""
        super().__init__(*args, **kwargs)

    def expire(self, time=None):
        """Remove expired items and delete associated Azure AI threads."""
        items = super().expire(time)
        for key, thread_conversation_id in items:
            try:
                # Create task for async deletion with proper session management
                asyncio.create_task(self._delete_thread_async(thread_conversation_id))
                logger.info("Scheduled thread deletion: %s", thread_conversation_id)
            except Exception as e:
                logger.error("Failed to schedule thread deletion for key %s: %s", key, e)
        return items

    def popitem(self):
        """Remove item using LRU eviction and delete associated Azure AI thread."""
        key, thread_conversation_id = super().popitem()
        try:
            # Create task for async deletion with proper session management
            asyncio.create_task(self._delete_thread_async(thread_conversation_id))
            logger.info("Scheduled thread deletion (LRU evict): %s", thread_conversation_id)
        except Exception as e:
            logger.error("Failed to schedule thread deletion for key %s (LRU evict): %s", key, e)
        return key, thread_conversation_id

    async def _delete_thread_async(self, thread_conversation_id: str):
        """Asynchronously delete a thread using a properly managed Azure AI Project Client."""
        credential = None
        try:
            if thread_conversation_id:
                # Get credential and use async context managers to ensure proper cleanup
                credential = await get_azure_credential_async()
                async with AIProjectClient(
                    endpoint=os.getenv("AZURE_AI_AGENT_ENDPOINT"),
                    credential=credential
                ) as project_client:
                    openai_client = project_client.get_openai_client()
                    await openai_client.conversations.delete(conversation_id=thread_conversation_id)
                    logger.info("Thread deleted successfully: %s", thread_conversation_id)
        except Exception as e:
            logger.error("Failed to delete thread %s: %s", thread_conversation_id, e)
        finally:
            # Close credential to prevent unclosed client session warnings
            if credential is not None:
                await credential.close()


def track_event_if_configured(event_name: str, event_data: dict):
    """Track event to Application Insights if configured."""
    instrumentation_key = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if instrumentation_key:
        track_event(event_name, event_data)
    else:
        logging.warning("Skipping track_event for %s as Application Insights is not configured", event_name)


# Global thread cache
thread_cache = None


def get_thread_cache():
    """Get or create the global thread cache."""
    global thread_cache
    if thread_cache is None:
        thread_cache = ExpCache(maxsize=1000, ttl=3600.0)
    return thread_cache


async def stream_openai_text(conversation_id: str, query: str) -> StreamingResponse:
    """
    Get a streaming text response from OpenAI.
    """
    thread = None
    complete_response = ""
    credential = None
    db_connection = None

    try:
        if not query:
            query = "Please provide a query."

        credential = await get_azure_credential_async()

        async with AIProjectClient(
            endpoint=os.getenv("AZURE_AI_AGENT_ENDPOINT"),
            credential=credential
        ) as project_client:

            cache = get_thread_cache()
            thread_conversation_id = cache.get(conversation_id, None)
            truncation_strategy = TruncationObject(type="last_messages", last_messages=4)

            from history_sql import SqlQueryTool, get_db_connection
            db_connection = await get_db_connection()
            if not db_connection:
                logger.error("Failed to establish database connection")
                raise Exception("Database connection failed")

            custom_tool = SqlQueryTool(pyodbc_conn=db_connection)
            my_tools = [custom_tool.run_sql_query]

            # Create chat client with existing agent
            chat_client = AzureAIClient(
                project_client=project_client,
                agent_name=os.getenv("AGENT_NAME_CHAT"),
                use_latest_version=True,
            )

            async with ChatAgent(
                chat_client=chat_client,
                tools=my_tools,
                tool_choice="auto",
                store=True,
            ) as chat_agent:

                if thread_conversation_id:
                    thread = chat_agent.get_new_thread(service_thread_id=thread_conversation_id)
                    assert thread.is_initialized
                else:
                    # Create a conversation using openAI client
                    openai_client = project_client.get_openai_client()
                    conversation = await openai_client.conversations.create()
                    thread_conversation_id = conversation.id
                    thread = chat_agent.get_new_thread(service_thread_id=thread_conversation_id)
                    cache[conversation_id] = thread_conversation_id

                async for chunk in chat_agent.run_stream(messages=query, thread=thread, truncation_strategy=truncation_strategy):
                    if chunk is not None and chunk.text != "":
                        complete_response += chunk.text
                        yield chunk.text

    except ServiceResponseException as e:
        complete_response = str(e)
        if "Rate limit is exceeded" in str(e):
            logger.error("Rate limit error: %s", e)
            raise ServiceResponseException(f"Rate limit is exceeded. {str(e)}") from e
        else:
            logger.error("RuntimeError: %s", e)
            raise ServiceResponseException(f"An unexpected runtime error occurred: {str(e)}") from e

    except Exception as e:
        complete_response = str(e)
        logger.error("Error in stream_openai_text: %s", e)
        cache = get_thread_cache()
        thread_conversation_id = cache.pop(conversation_id, None)
        if thread_conversation_id is not None:
            corrupt_key = f"{conversation_id}_corrupt_{random.randint(1000, 9999)}"
            cache[corrupt_key] = thread_conversation_id
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error streaming OpenAI text") from e

    finally:
        if db_connection:
            db_connection.close()
        if credential is not None:
            await credential.close()
        # Provide a fallback response when no data is received from OpenAI.
        if complete_response == "":
            logger.info("No response received from OpenAI.")
            yield "I cannot answer this question with the current data. Please rephrase or add more details."

async def stream_openai_text_workshop(conversation_id: str, query: str) -> StreamingResponse:
    """
    Get a streaming text response from OpenAI with workshop mode using responses.create().
    Handles both SQL function calls and AI Search like 08_test_agent.py.
    Uses Fabric SQL when AZURE_ENV_ONLY is false, otherwise uses Azure SQL.
    """
    complete_response = ""
    credential = None
    db_connection = None

    try:
        if not query:
            query = "Please provide a query."

        credential = await get_azure_credential_async()

        async with AIProjectClient(
            endpoint=os.getenv("AZURE_AI_AGENT_ENDPOINT"),
            credential=credential
        ) as project_client:

            # Get database connection based on AZURE_ENV_ONLY flag
            from history_sql import SqlQueryTool, get_azure_sql_connection, get_fabric_db_connection
            
            if AZURE_ENV_ONLY:
                logger.info("Workshop mode: Using Azure SQL Database")
                db_connection = await get_azure_sql_connection()
            else:
                logger.info("Workshop mode: Using Fabric Lakehouse SQL")
                db_connection = await get_fabric_db_connection()
            
            if not db_connection:
                logger.error("Failed to establish database connection")
                raise Exception("Database connection failed")
            
            custom_tool = SqlQueryTool(pyodbc_conn=db_connection)

            openai_client = project_client.get_openai_client()
            
            # Initial request to the agent
            response = await openai_client.responses.create(
                input=query,
                extra_body={"agent": {"name": os.getenv("AGENT_NAME_CHAT"), "type": "agent_reference"}}
            )
            
            # Process response - handle function calls and search
            max_iterations = 10
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                
                # Check for function calls and tool uses in output
                function_calls = []
                text_output = ""
                search_results = []
                
                for item in response.output:
                    item_type = getattr(item, 'type', None)
                    
                    if item_type == 'function_call':
                        function_calls.append(item)
                    elif item_type == 'message':
                        # Type guard: only process if item has content attribute and it's not None
                        if hasattr(item, 'content') and item.content is not None:
                            for content in item.content:
                                if hasattr(content, 'text'):
                                    text_output += content.text
                                # Check for annotations (citations from search)
                                if hasattr(content, 'annotations'):
                                    for ann in content.annotations:
                                        if hasattr(ann, 'url_citation'):
                                            search_results.append(ann.url_citation)
                                        elif hasattr(ann, 'file_citation'):
                                            search_results.append(getattr(ann.file_citation, 'file_id', str(ann.file_citation)))
                    # Handle search tool call (request)
                    elif item_type == 'azure_ai_search_call':
                        args_str = getattr(item, 'arguments', '{}')
                        try:
                            args = json.loads(args_str) if args_str else {}
                            query_text = args.get('query', 'unknown')
                            logger.info("AI Search query: %s", query_text)
                        except Exception:
                            logger.info("AI Search called")
                    # Handle search tool output (result)
                    elif item_type == 'azure_ai_search_call_output':
                        logger.info("AI Search completed")
                
                # If no function calls, we're done
                if not function_calls:
                    if text_output:
                        complete_response += text_output
                        yield text_output
                    break
                
                # Handle function calls
                tool_outputs = []
                for fc in function_calls:
                    func_name = fc.name
                    func_args = json.loads(fc.arguments)
                    
                    logger.info("Calling function: %s", func_name)
                    
                    if func_name == "execute_sql":
                        sql_query = func_args.get("sql_query", "")
                        logger.info("Executing SQL query: %s", sql_query[:100])
                        result = await custom_tool.run_sql_query(sql_query=sql_query)
                        logger.info("SQL query completed")
                        # Convert result to string - it's a list of dicts from run_sql_query
                        if result is None:
                            result_str = "No results returned"
                        elif isinstance(result, (list, dict)):
                            result_str = json.dumps(result, ensure_ascii=False)
                        else:
                            result_str = str(result)
                    else:
                        result_str = f"Unknown function: {func_name}"
                        logger.warning("Unknown function called: %s", func_name)
                    
                    tool_outputs.append({
                        "type": "function_call_output",
                        "call_id": fc.call_id,
                        "output": result_str
                    })
                
                # Submit tool outputs and get next response
                # Note: Don't include 'conversation' when using 'previous_response_id'
                response = await openai_client.responses.create(
                    input=tool_outputs,
                    extra_body={
                        "agent": {"name": os.getenv("AGENT_NAME_CHAT"), "type": "agent_reference"},
                        "previous_response_id": response.id
                    }
                )
            
            if iteration >= max_iterations:
                logger.warning("Max iterations reached in workshop mode")
                yield "\n\n(Response processing reached maximum iterations)"

    except Exception as e:
        complete_response = str(e)
        logger.error("Error in stream_openai_text_workshop: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error streaming OpenAI text") from e

    finally:
        if db_connection:
            db_connection.close()
        if credential is not None:
            await credential.close()
        # Provide a fallback response when no data is received from OpenAI.
        if complete_response == "":
            logger.info("No response received from OpenAI.")
            yield "I cannot answer this question with the current data. Please rephrase or add more details."


async def stream_chat_request(conversation_id, query):
    """
    Handles streaming chat requests.
    """
    async def generate():
        try:
            assistant_content = ""
            # Use workshop function if IS_WORKSHOP is enabled
            stream_func = stream_openai_text_workshop if IS_WORKSHOP else stream_openai_text
            async for chunk in stream_func(conversation_id, query):
                if isinstance(chunk, dict):
                    chunk = json.dumps(chunk)  # Convert dict to JSON string
                assistant_content += str(chunk)

                if assistant_content:
                    response = {
                        "choices": [{
                            "messages": [{"role": "assistant", "content": assistant_content}]
                        }]
                    }
                    yield json.dumps(response, ensure_ascii=False) + "\n\n"

        except ServiceResponseException as e:
            error_message = str(e)
            retry_after = "sometime"
            if "Rate limit is exceeded" in error_message:
                match = re.search(r"Try again in (\d+) seconds.", error_message)
                if match:
                    retry_after = f"{match.group(1)} seconds"
                logger.error("Rate limit error: %s", error_message)
                yield json.dumps({"error": f"Rate limit is exceeded. Try again in {retry_after}."}) + "\n\n"
            else:
                logger.error("ServiceResponseException: %s", error_message)
                yield json.dumps({"error": "An error occurred. Please try again later."}) + "\n\n"

        except Exception as e:
            logger.error("Unexpected error: %s", e)
            error_response = {"error": "An error occurred while processing the request."}
            yield json.dumps(error_response) + "\n\n"

    return generate()


@router.post("/chat")
async def conversation(request: Request):
    """Handle chat requests - streaming text or chart generation based on query keywords."""
    try:
        # Get the request JSON with optimized payload (only conversation_id and query)
        request_json = await request.json()
        conversation_id = request_json.get("conversation_id")
        query = request_json.get("query")

        # Validate required parameters
        if not query:
            return JSONResponse(
                content={"error": "Query is required"},
                status_code=400
            )

        if not conversation_id:
            return JSONResponse(
                content={"error": "Conversation ID is required"},
                status_code=400
            )

        result = await stream_chat_request(conversation_id, query)
        track_event_if_configured(
            "ChatStreamSuccess",
            {"conversation_id": conversation_id, "query": query}
        )
        return StreamingResponse(result, media_type="application/json-lines")

    except Exception as ex:
        logger.exception("Error in conversation endpoint: %s", str(ex))
        span = trace.get_current_span()
        if span is not None:
            span.record_exception(ex)
            span.set_status(Status(StatusCode.ERROR, str(ex)))
        return JSONResponse(content={"error": "An internal error occurred while processing the conversation."}, status_code=500)
