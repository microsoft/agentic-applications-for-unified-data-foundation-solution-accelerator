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
from agent_framework_foundry import FoundryAgent

# Azure Auth
from auth.auth_utils import get_authenticated_user_details
from auth.azure_credential_utils import get_azure_credential_async

load_dotenv()

from telemetry import token_emitter  # noqa: E402
from llm_token_telemetry import TokenUsageScope, extract_usage  # noqa: E402

# Constants
HOST_NAME = "Agentic Applications for Unified Data Foundation"
HOST_INSTRUCTIONS = "Answer questions about Sales, Products and Orders data."

# Workshop mode configuration
IS_WORKSHOP = os.getenv("IS_WORKSHOP", "false").lower() == "true"
AZURE_ENV_ONLY = os.getenv("AZURE_ENV_ONLY", "true").lower() == "true"
USE_USER_ACCESS_TOKEN = os.getenv("USE_USER_ACCESS_TOKEN", "false").lower() == "true"

router = APIRouter()

logger = logging.getLogger(__name__)

# Suppress informational warnings from agent_framework_foundry about runtime
# tool/structured_output overrides not being supported by FoundryAgent.
agent_log_level = os.getenv("AGENT_FRAMEWORK_LOG_LEVEL", "ERROR").upper()
logging.getLogger("agent_framework_foundry").setLevel(getattr(logging, agent_log_level, logging.ERROR))


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


async def stream_openai_text(conversation_id: str, query: str, user_id: str = "", user_assertion: str = None):
    """
    Async generator yielding plain text chunks from OpenAI.

    Uses responses.create() with conversation caching for chat history continuity.
    If *user_assertion* is provided, uses OBO credential for user context.
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

        # Use OBO credential if user token is available and USE_USER_ACCESS_TOKEN is enabled
        effective_assertion = user_assertion if USE_USER_ACCESS_TOKEN else None
        credential = await get_azure_credential_async(user_assertion=effective_assertion)

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
            agent_name = os.getenv("AGENT_NAME_CHAT", "")
            model_deployment_name = os.getenv("AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME", "")

            response = await openai_client.responses.create(
                conversation=thread_conversation_id,
                input=query,
                extra_body={"agent_reference": {"name": agent_name, "type": "agent_reference"}}
            )

            accumulated_usage = extract_usage(response)

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
                    extra_body={"agent_reference": {"name": agent_name, "type": "agent_reference"}}
                )

                iter_usage = extract_usage(response)
                if iter_usage:
                    accumulated_usage = (accumulated_usage + iter_usage) if accumulated_usage else iter_usage

            if iteration >= max_iterations:
                logger.warning("Max iterations reached for conversation %s", conversation_id)
                yield "\n\n(Response processing reached maximum iterations)"

            try:
                if accumulated_usage and accumulated_usage.has_any:
                    resolved_model = getattr(response, "model", "") or model_deployment_name
                    token_emitter.emit_all(
                        agent_name=agent_name,
                        model_deployment_name=resolved_model,
                        usage=accumulated_usage,
                        conversation_id=conversation_id,
                        user_id=user_id,
                    )
            except Exception:
                logger.debug("Token usage telemetry failed", exc_info=True)

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


_MARKER_RE = re.compile(r'【\d+:(\d+)†([^】]*)】')


def _parse_mcp_docs(mcp_text: str, mcp_docs: dict):
    """Parse JSON document blocks from MCP output text keyed by section index."""
    sections = re.split(r'【\d+:(\d+)†[^】]*】', mcp_text)
    # sections alternates: [preamble, idx0, content0, idx1, content1, ...]
    for i in range(1, len(sections) - 1, 2):
        sec_idx = sections[i]
        sec_content = sections[i + 1]
        json_match = re.search(r'\{[^{}]*"id"\s*:\s*"[^"]*"[^{}]*\}', sec_content)
        if json_match:
            try:
                doc = json.loads(json_match.group())
                if "id" in doc:
                    mcp_docs[sec_idx] = doc
            except (json.JSONDecodeError, ValueError):
                pass  # Skip malformed JSON fragments; parsing continues


def _extract_mcp_from_raw(raw_repr, mcp_docs: dict):
    """Extract MCP docs from any raw_representation type."""
    # Direct McpCall with string output
    raw_output = getattr(raw_repr, "output", None)
    if raw_output and isinstance(raw_output, str):
        _parse_mcp_docs(raw_output, mcp_docs)
        return
    # ResponseCompletedEvent → traverse response.output for McpCall objects
    response = getattr(raw_repr, "response", None)
    if response:
        output_items = getattr(response, "output", None) or []
        for item in output_items:
            item_output = getattr(item, "output", None)
            if item_output and isinstance(item_output, str):
                _parse_mcp_docs(item_output, mcp_docs)


async def stream_openai_text_workshop(conversation_id: str, query: str, user_id: str = "", user_assertion: str = None):
    """
    Async generator yielding ``(role, content)`` tuples (workshop mode).

    Uses FoundryAgent with agent_framework to handle function calls (SQL)
    and search tools automatically.  Fabric SQL is used when AZURE_ENV_ONLY
    is false, otherwise Azure SQL.  *user_assertion* enables OBO credential.
    """
    complete_response = ""
    credential = None
    db_connection = None

    try:
        if not query:
            query = "Please provide a query."

        # Use OBO credential if user token is available and USE_USER_ACCESS_TOKEN is enabled
        effective_assertion = user_assertion if USE_USER_ACCESS_TOKEN else None
        credential = await get_azure_credential_async(user_assertion=effective_assertion)

        async with AIProjectClient(
            endpoint=os.getenv("AZURE_AI_AGENT_ENDPOINT"),
            credential=credential
        ) as project_client:
            cache = get_thread_cache()
            conv_id = cache.get(conversation_id, None)

            # Check if Data Agent mode is enabled (MCP handles SQL server-side)
            use_data_agent = os.getenv("USE_DATA_AGENT", "false").lower() in ("true", "1", "yes")

            custom_tool = None
            if not use_data_agent:
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
            else:
                logger.info("Workshop mode: Using Fabric Data Agent (MCP) - skipping local SQL tool")

            # Create agent with tools
            agent_name = os.getenv("AGENT_NAME_CHAT")
            if use_data_agent:
                agent = FoundryAgent(
                    project_client=project_client,
                    agent_name=agent_name,
                )
            else:
                agent = FoundryAgent(
                    project_client=project_client,
                    agent_name=agent_name,
                    tools=custom_tool.execute_sql if custom_tool else None,
                )

            # Create or retrieve conversation
            if not conv_id:
                openai_client = project_client.get_openai_client()
                conv = await openai_client.conversations.create()
                conv_id = conv.id
                cache[conversation_id] = conv_id

            # Citation tracking
            mcp_docs = {}  # Map section index → {id, title, source} from MCP output
            marker_buf = ""  # Buffer for incomplete marker fragments
            citation_idx = 0  # Sequential citation counter
            marker_re = _MARKER_RE

            model_deployment_name = os.getenv("AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME", "")

            scope = TokenUsageScope(
                token_emitter,
                agent_name=agent_name or "",
                model_deployment_name=model_deployment_name or agent_name or "",
                conversation_id=conversation_id,
                user_id=user_id,
            )
            try:
                async for chunk in agent.run(query, stream=True, options={"conversation_id": conv_id}):
                    for content in getattr(chunk, "contents", []) or []:
                        raw_repr = getattr(content, "raw_representation", None)
                        if raw_repr:
                            _extract_mcp_from_raw(raw_repr, mcp_docs)

                    scope.add(chunk)

                    chunk_text = str(chunk.text) if chunk.text else ""
                    if not chunk_text:
                        continue
                    complete_response += chunk_text
                    marker_buf += chunk_text

                    # Process all complete markers in buffer; keep trailing incomplete fragment
                    while True:
                        m = marker_re.search(marker_buf)
                        if not m:
                            open_pos = marker_buf.rfind('【')
                            if open_pos == -1:
                                if marker_buf:
                                    yield ("assistant", marker_buf)
                                marker_buf = ""
                            elif open_pos > 0:
                                yield ("assistant", marker_buf[:open_pos])
                                marker_buf = marker_buf[open_pos:]
                            break

                        # Flush text before this marker
                        if m.start() > 0:
                            yield ("assistant", marker_buf[:m.start()])

                        # Replace marker: drop section 0, renumber rest (consolidate same source)
                        sec_idx = m.group(1)
                        if sec_idx != "0":
                            citation_idx += 1
                            yield ("assistant", f"[{citation_idx}]")

                        marker_buf = marker_buf[m.end():]

                # Flush any remaining buffer
                if marker_buf:
                    yield ("assistant", marker_buf)
            finally:
                try:
                    scope.__exit__(None, None, None)
                except Exception:
                    logger.debug("Token usage telemetry failed", exc_info=True)

            cache[conversation_id] = conv_id

            # Collect original markers from complete_response for citation building
            original_markers = [
                m for m in marker_re.finditer(complete_response)
                if m.group(1) != "0"
            ]

            logger.info("Streaming complete for conversation %s: response_length=%d, mcp_doc_count=%d",
                        conversation_id, len(complete_response), len(mcp_docs))
            track_event_if_configured("ChatResponseCompleted", {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "response_length": str(len(complete_response)),
                "citation_count": str(len(mcp_docs)),
            })

            # Yield citations as a tool message — deduplicated by source
            citation_list = []
            if original_markers:
                search_endpoint = os.getenv("AZURE_AI_SEARCH_ENDPOINT", "")
                search_index = os.getenv("AZURE_AI_SEARCH_INDEX", "")

                for m in original_markers:
                    sec_idx = m.group(1)
                    marker_source = m.group(2)
                    mcp_doc = mcp_docs.get(sec_idx, {})
                    doc_source = mcp_doc.get("source") or marker_source or f"source_{sec_idx}"
                    doc_id = mcp_doc.get("id", "")

                    doc_url = ""
                    if search_endpoint and search_index and doc_id:
                        from urllib.parse import quote
                        doc_url = (
                            f"{search_endpoint.rstrip('/')}/indexes/{search_index}"
                            f"/docs/{quote(doc_id, safe='')}?api-version=2024-07-01"
                            f"&$select=id,chunk_id,content,source"
                        )

                    citation_list.append({"url": doc_url, "source": doc_source, "id": doc_id})

            yield ("tool", json.dumps(citation_list))

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
            yield ("assistant", "I cannot answer this question with the current data. Please rephrase or add more details.")


async def stream_chat_request(conversation_id, query, user_id: str = "", user_assertion: str = None):
    """
    Handles streaming chat requests.

    Workshop mode uses delta format (incremental fragments).
    Non-workshop mode uses messages format (accumulated text).
    """
    logger.info("stream_chat_request called: conversation_id=%s", conversation_id)

    async def generate():
        try:
            assistant_content = ""
            # Use workshop function if IS_WORKSHOP is enabled
            stream_func = stream_openai_text_workshop if IS_WORKSHOP else stream_openai_text
            if IS_WORKSHOP:
                # Workshop: delta format — incremental fragments, frontend appends
                async for role, content in stream_func(conversation_id, query, user_id=user_id, user_assertion=user_assertion):
                    if not content:
                        continue
                    if role == "assistant":
                        assistant_content += content
                    response = {
                        "choices": [{
                            "delta": {"role": role, "content": content}
                        }]
                    }
                    yield json.dumps(response, ensure_ascii=False) + "\n"
            else:
                # Non-workshop: messages format — accumulated text, frontend replaces
                async for chunk in stream_func(conversation_id, query, user_id=user_id, user_assertion=user_assertion):
                    if isinstance(chunk, dict):
                        chunk = json.dumps(chunk)
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


@router.post("/fetch-azure-search-content")
async def fetch_azure_search_content(request: Request):
    """Fetch document content from Azure AI Search by citation URL."""
    try:
        request_json = await request.json()
        citation_url = request_json.get("url")
        fallback_label = request_json.get("source") or request_json.get("title", "")
        logger.info(
            "POST /fetch-azure-search-content called: url=%s",
            citation_url,
        )

        if not citation_url:
            return JSONResponse(
                content={"error": "URL is required"}, status_code=400
            )

        # --- SSRF protection: only allow requests to the configured search endpoint ---
        from urllib.parse import urlparse, parse_qs, quote

        search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT") or os.getenv(
            "AZURE_AI_SEARCH_ENDPOINT", ""
        )
        if not search_endpoint:
            return JSONResponse(
                content={"error": "Search endpoint not configured"},
                status_code=500,
            )

        allowed_host = urlparse(search_endpoint).netloc.lower()
        parsed = urlparse(citation_url)
        if parsed.netloc.lower() != allowed_host:
            logger.warning(
                "Blocked fetch to non-allowed host: %s (allowed: %s)",
                parsed.netloc,
                allowed_host,
            )
            return JSONResponse(
                content={"error": "URL host not allowed"}, status_code=403
            )

        # Parse the doc id from the URL: .../docs/{doc_id}?api-version=...
        path_parts = parsed.path.rstrip("/").split("/")
        doc_id = None
        for i, part in enumerate(path_parts):
            if part == "docs" and i + 1 < len(path_parts):
                doc_id = path_parts[i + 1]
                break

        if not doc_id:
            return JSONResponse(
                content={"error": "Could not parse document ID from URL"},
                status_code=400,
            )

        # Reconstruct URL using OData key lookup (no $select — causes 400)
        idx = parsed.path.find("/docs/")
        base_path = parsed.path[:idx]
        qs = parse_qs(parsed.query)
        api_version = qs.get("api-version", ["2024-07-01"])[0]

        from urllib.parse import unquote
        decoded_doc_id = unquote(doc_id)
        encoded_key = quote(decoded_doc_id, safe="")
        lookup_url = (
            f"{parsed.scheme}://{parsed.netloc}{base_path}"
            f"/docs('{encoded_key}')?api-version={api_version}"
        )

        credential = await get_azure_credential_async()
        try:
            token = await credential.get_token(
                "https://search.azure.com/.default"
            )
            access_token = token.token
        finally:
            await credential.close()

        def fetch_content():
            try:
                import requests as req

                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                }
                response = req.get(
                    lookup_url, headers=headers, timeout=10
                )
                logger.info(
                    "Azure Search lookup: status=%d, url=%s",
                    response.status_code,
                    lookup_url,
                )

                if response.status_code == 200:
                    data = response.json()
                    content = data.get("content", "")
                    source = data.get("source", fallback_label)
                    return {"content": content, "title": source}
                logger.warning(
                    "Azure Search fetch failed: status=%d, body=%s",
                    response.status_code,
                    response.text[:500],
                )
                return {"error": f"HTTP {response.status_code}"}
            except Exception:
                logger.exception("Exception fetching search content")
                return {"error": "Unable to fetch content"}

        result = await asyncio.to_thread(fetch_content)
        return JSONResponse(content=result)

    except Exception:
        logger.exception("Error in fetch_azure_search_content")
        return JSONResponse(
            content={"error": "Internal server error"}, status_code=500
        )


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

        # Get user's access token for OBO flow (needed for Work IQ Teams)
        user_assertion = authenticated_user.get("aad_access_token")

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

        logger.info(
            "POST /chat called: conversation_id=%s, query_length=%d, has_user_token=%s",
            conversation_id, len(query) if query else 0, bool(user_assertion),
        )

        # Track chat request initiation
        track_event_if_configured("ChatRequestReceived", {
            "conversation_id": conversation_id,
            "user_id": user_id
        })

        result = await stream_chat_request(conversation_id, query, user_id=user_id, user_assertion=user_assertion)
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
