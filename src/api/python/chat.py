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
from azure.core.exceptions import HttpResponseError
from azure.monitor.events.extension import track_event
from azure.ai.projects.aio import AIProjectClient

# Agent Framework
from agent_framework.azure import AzureAIProjectAgentProvider

# Azure Auth
from auth.auth_utils import get_authenticated_user_details
from auth.azure_credential_utils import get_azure_credential_async

load_dotenv()

# Constants
HOST_NAME = "Agentic Applications for Unified Data Foundation"
HOST_INSTRUCTIONS = "Answer questions about Sales, Products and Orders data."

# Workshop mode configuration
IS_WORKSHOP = os.getenv("IS_WORKSHOP", "false").lower() == "true"
AZURE_ENV_ONLY = os.getenv("AZURE_ENV_ONLY", "true").lower() == "true"

router = APIRouter()

logger = logging.getLogger(__name__)

# Suppress informational warnings from agent_framework about runtime
# tool/structured_output overrides not being supported by AzureAIClient.
agent_log_level = os.getenv("AGENT_FRAMEWORK_LOG_LEVEL", "ERROR").upper()
logging.getLogger("agent_framework.azure").setLevel(getattr(logging, agent_log_level, logging.ERROR))


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
                # Response IDs (resp_xxx) don't need explicit deletion - they're managed by the API
                if thread_conversation_id.startswith("resp_"):
                    logger.info("Skipping deletion for response ID: %s", thread_conversation_id)
                    return
                # Get credential and use async context managers to ensure proper cleanup
                credential = await get_azure_credential_async()
                async with AIProjectClient(
                    endpoint=os.getenv("AZURE_AI_AGENT_ENDPOINT"),
                    credential=credential
                ) as project_client:
                    openai_client = project_client.get_openai_client()
                    try:
                        await openai_client.conversations.delete(conversation_id=thread_conversation_id)
                        logger.info("Thread deleted successfully: %s", thread_conversation_id)
                    finally:
                        await openai_client.close()
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


async def stream_openai_text(conversation_id: str, query: str, user_id: str = "") -> StreamingResponse:
    """
    Get a streaming text response from OpenAI using azure-ai-projects SDK.
    Uses responses.create() with conversation caching for chat history continuity.
    """
    logger.info("stream_openai_text called: conversation_id=%s, query_length=%d",
                conversation_id, len(query) if query else 0)
    complete_response = ""
    credential = None
    db_connection = None

    try:
        if not query:
            query = "Please provide a query."

        logger.info("Chat request received - query: %s, conversation_id: %s", query, conversation_id)

        credential = await get_azure_credential_async()

        async with AIProjectClient(
            endpoint=os.getenv("AZURE_AI_AGENT_ENDPOINT"),
            credential=credential
        ) as project_client:

            cache = get_thread_cache()
            thread_conversation_id = cache.get(conversation_id, None)

            # Get database connection
            from history_sql import SqlQueryTool, get_db_connection
            db_connection = await get_db_connection()
            if not db_connection:
                logger.error("Failed to establish database connection")
                raise Exception("Database connection failed")

            custom_tool = SqlQueryTool(pyodbc_conn=db_connection)

            openai_client = project_client.get_openai_client()

            # Create or reuse conversation for chat history continuity
            if not thread_conversation_id:
                conversation = await openai_client.conversations.create()
                thread_conversation_id = conversation.id
                cache[conversation_id] = thread_conversation_id

            # Initial request to the agent
            response = await openai_client.responses.create(
                conversation=thread_conversation_id,
                input=query,
                extra_body={"agent": {"name": os.getenv("AGENT_NAME_CHAT"), "type": "agent_reference"}}
            )

            # Process response - handle function calls iteratively
            max_iterations = 10
            iteration = 0

            while iteration < max_iterations:
                iteration += 1

                function_calls = []
                text_output = ""

                for item in response.output:
                    item_type = getattr(item, 'type', None)

                    if item_type == 'function_call':
                        function_calls.append(item)
                    elif item_type == 'message':
                        if hasattr(item, 'content') and item.content is not None:
                            for content in item.content:
                                if hasattr(content, 'text'):
                                    text_output += content.text
                    elif item_type == 'azure_ai_search_call':
                        args_str = getattr(item, 'arguments', '{}')
                        try:
                            args = json.loads(args_str) if args_str else {}
                            logger.info("AI Search query: %s", args.get('query', 'unknown'))
                        except Exception:
                            logger.info("AI Search called")
                    elif item_type in ('azure_ai_search_call_output', 'mcp_call_output'):
                        logger.info("Search/knowledge base retrieval completed")
                    elif item_type == 'mcp_call':
                        logger.info("Knowledge Base MCP call: %s", getattr(item, 'name', 'unknown'))

                # If no function calls, yield text and break
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

                    if func_name == "run_sql_query":
                        sql_query = func_args.get("sql_query", "")
                        logger.info("Executing SQL query: %s", sql_query[:100])
                        result = await custom_tool.run_sql_query(sql_query=sql_query)
                        logger.info("SQL query completed")
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
                response = await openai_client.responses.create(
                    conversation=thread_conversation_id,
                    input=tool_outputs,
                    extra_body={"agent": {"name": os.getenv("AGENT_NAME_CHAT"), "type": "agent_reference"}}
                )

            if iteration >= max_iterations:
                logger.warning("Max iterations reached for conversation %s", conversation_id)
                yield "\n\n(Response processing reached maximum iterations)"

            logger.info("Streaming complete for conversation %s: response_length=%d",
                        conversation_id, len(complete_response))
            track_event_if_configured("ChatResponseCompleted", {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "response_length": str(len(complete_response)),
            })

    except HttpResponseError as e:
        complete_response = str(e)
        if "Rate limit is exceeded" in str(e) or e.status_code == 429:
            logger.error("Rate limit error: %s", e)
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Rate limit is exceeded. {str(e)}") from e
        else:
            logger.error("RuntimeError: %s", e)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"An unexpected runtime error occurred: {str(e)}") from e

    except Exception as e:
        complete_response = str(e)
        logger.exception("Error in stream_openai_text: %s", e)
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


async def stream_openai_text_workshop(conversation_id: str, query: str, user_id: str = "") -> StreamingResponse:
    """
    Get a streaming text response from OpenAI with workshop mode using AzureAIProjectAgentProvider.
    Uses agent_framework to handle function calls (SQL) and search tools automatically.
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
            cache = get_thread_cache()
            conv_id = cache.get(conversation_id, None)

            # Get database connection based on AZURE_ENV_ONLY flag
            from history_sql import SqlQueryTool, get_azure_sql_connection, get_fabric_db_connection

            if AZURE_ENV_ONLY:
                logger.info("Workshop mode: Using Azure SQL Database")
                db_connection = await get_azure_sql_connection()
            else:
                logger.info("Workshop mode: Using Fabric Lakehouse SQL")
                db_connection = await get_fabric_db_connection()

            if not db_connection:
                logger.warning("Failed to establish database connection")

            custom_tool = SqlQueryTool(pyodbc_conn=db_connection) if db_connection else None

            # Create provider and get agent with tools
            provider = AzureAIProjectAgentProvider(project_client=project_client)
            agent = await provider.get_agent(
                name=os.getenv("AGENT_NAME_CHAT"),
                tools=custom_tool.execute_sql if custom_tool else None
            )

            # Create or retrieve conversation
            if not conv_id:
                openai_client = project_client.get_openai_client()
                conv = await openai_client.conversations.create()
                conv_id = conv.id
                cache[conversation_id] = conv_id

            # Citation tracking
            citations = []
            first_chunk = True
            citation_marker_map = {}  # Maps original markers to sequential numbers
            citation_counter = 0

            def replace_citation_marker(match):
                nonlocal citation_counter
                marker = match.group(0)
                if marker not in citation_marker_map:
                    citation_counter += 1
                    citation_marker_map[marker] = citation_counter
                return f"[{citation_marker_map[marker]}]"

            # Stream response using agent_framework - handles function calls automatically
            async for chunk in agent.run(query, stream=True, conversation_id=conv_id):
                # # Collect citations from Azure AI Search responses
                # for content in getattr(chunk, "contents", []):
                #     annotations = getattr(content, "annotations", [])
                #     if annotations:
                #         citations.extend(annotations)

                chunk_text = str(chunk.text) if chunk.text else ""

                # Remove citation markers like 【4:0†source】 from response text until citation issue resolved
                chunk_text = re.sub(r'【\d+:\d+†[^】]+】', '', chunk_text)
                # Replace citation markers like 【4:0†source】 with [1], [2], etc.
                # chunk_text = re.sub(r'【\d+:\d+†[^】]+】', replace_citation_marker, chunk_text)

                if chunk_text:
                    complete_response += chunk_text
                    if first_chunk:
                        first_chunk = False
                        yield "{ \"answer\": " + chunk_text
                    else:
                        yield chunk_text

            cache[conversation_id] = conv_id

            logger.info("Streaming complete for conversation %s: response_length=%d, citation_count=%d",
                        conversation_id, len(complete_response), len(citations))
            track_event_if_configured("ChatResponseCompleted", {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "response_length": str(len(complete_response)),
                "citation_count": str(len(citations)),
            })

            # Yield citations at end of stream
            if citations:
                citation_list = []
                seen_doc_ids = set()

                for citation in citations:
                    # URL is directly on the citation object, fallback to additional_properties.get_url
                    url = citation.get("url") or (citation.get("additional_properties") or {}).get("get_url") or "N/A"
                    title = citation.get("title", "N/A")

                    # Skip duplicate citations based on title
                    if title in seen_doc_ids:
                        continue
                    seen_doc_ids.add(title)

                    citation_list.append(json.dumps({"url": url, "title": title}))

                yield ", \"citations\": [" + ",".join(citation_list) + "]}"
            else:
                yield ", \"citations\": []}"

    except Exception as e:
        complete_response = str(e)
        logger.exception("Error in stream_openai_text_workshop: %s", e)
        cache = get_thread_cache()
        conv_id = cache.pop(conversation_id, None)
        if conv_id is not None:
            corrupt_key = f"{conversation_id}_corrupt_{random.randint(1000, 9999)}"
            cache[corrupt_key] = conv_id
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


async def stream_chat_request(conversation_id, query, user_id: str = ""):
    """
    Handles streaming chat requests.
    """
    logger.info("stream_chat_request called: conversation_id=%s", conversation_id)

    async def generate():
        try:
            assistant_content = ""
            # Use workshop function if IS_WORKSHOP is enabled
            stream_func = stream_openai_text_workshop if IS_WORKSHOP else stream_openai_text
            async for chunk in stream_func(conversation_id, query, user_id=user_id):
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

        except HTTPException as e:
            error_message = str(e.detail) if hasattr(e, 'detail') else str(e)
            retry_after = "sometime"
            if "Rate limit is exceeded" in error_message or e.status_code == 429:
                match = re.search(r"Try again in (\d+) seconds.", error_message)
                if match:
                    retry_after = f"{match.group(1)} seconds"
                logger.error("Rate limit error: %s", error_message)
                yield json.dumps({"error": f"Rate limit is exceeded. Try again in {retry_after}."}) + "\n\n"
            else:
                logger.error("HttpResponseError: %s", error_message)
                yield json.dumps({"error": "An error occurred. Please try again later."}) + "\n\n"

        except Exception as e:
            logger.exception("Unexpected error: %s", e)
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
        authenticated_user = get_authenticated_user_details(request_headers=request.headers)
        user_id = authenticated_user.get("user_principal_id", "")

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

        logger.info("POST /chat called: conversation_id=%s, query_length=%d",
                     conversation_id, len(query) if query else 0)

        # Track chat request initiation
        track_event_if_configured("ChatRequestReceived", {
            "conversation_id": conversation_id,
            "user_id": user_id
        })

        result = await stream_chat_request(conversation_id, query, user_id=user_id)
        track_event_if_configured(
            "ChatStreamSuccess",
            {"conversation_id": conversation_id, "user_id": user_id, "query": query}
        )
        return StreamingResponse(result, media_type="application/json-lines")

    except Exception as ex:
        logger.exception("Error in conversation endpoint: %s", str(ex))

        # Track specific error type
        track_event_if_configured("ChatRequestError", {
            "conversation_id": request_json.get("conversation_id") if 'request_json' in locals() else "",
            "user_id": locals().get("user_id", ""),
            "error": str(ex),
            "error_type": type(ex).__name__
        })

        span = trace.get_current_span()
        if span is not None:
            span.record_exception(ex)
            span.set_status(Status(StatusCode.ERROR, str(ex)))
        return JSONResponse(content={"error": "An internal error occurred while processing the conversation."}, status_code=500)
