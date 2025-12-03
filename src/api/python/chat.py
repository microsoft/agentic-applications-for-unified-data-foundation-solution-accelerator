"""
Chat API module for handling chat interactions and responses.
"""

import asyncio
import json
import logging
import os
import random
import re
from typing import AsyncGenerator

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
from agent_framework.azure import AzureAIAgentClient
from agent_framework.exceptions import ServiceResponseException

# Azure Auth
from auth.azure_credential_utils import get_azure_credential_async

load_dotenv()

# Constants
HOST_NAME = "Agentic Applications for Unified Data Foundation"
HOST_INSTRUCTIONS = "Answer questions about Sales, Products and Orders data."
INCOMPLETE_RUN_STATUS = "incomplete"

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
        for key, thread_id in items:
            try:
                # Create task for async deletion with proper session management
                asyncio.create_task(self._delete_thread_async(thread_id))
                logger.info("Scheduled thread deletion: %s", thread_id)
            except Exception as e:
                logger.error("Failed to schedule thread deletion for key %s: %s", key, e)
        return items

    def popitem(self):
        """Remove item using LRU eviction and delete associated Azure AI thread."""
        key, thread_id = super().popitem()
        try:
            # Create task for async deletion with proper session management
            asyncio.create_task(self._delete_thread_async(thread_id))
            logger.info("Scheduled thread deletion (LRU evict): %s", thread_id)
        except Exception as e:
            logger.error("Failed to schedule thread deletion for key %s (LRU evict): %s", key, e)
        return key, thread_id

    async def _delete_thread_async(self, thread_id: str):
        """Asynchronously delete a thread using a properly managed Azure AI Project Client."""
        credential = None
        try:
            if thread_id:
                # Get credential and use async context managers to ensure proper cleanup
                credential = await get_azure_credential_async()
                async with AIProjectClient(
                    endpoint=os.getenv("AZURE_AI_AGENT_ENDPOINT"),
                    credential=credential
                ) as client:
                    await client.agents.threads.delete(thread_id=thread_id)
                    logger.info("Thread deleted successfully: %s", thread_id)
        except Exception as e:
            logger.error("Failed to delete thread %s: %s", thread_id, e)
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


async def stream_openai_text(conversation_id: str, query: str) -> AsyncGenerator[str, None]:
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

        try:
            async with AIProjectClient(
                endpoint=os.getenv("AZURE_AI_AGENT_ENDPOINT"),
                credential=credential
            ) as client:
                foundry_agent = await client.agents.get_agent(os.getenv("AGENT_ID_ORCHESTRATOR"))

                cache = get_thread_cache()
                thread_id = cache.get(conversation_id, None)

                if thread_id:
                    should_discard = False
                    try:
                        runs_paged = client.agents.runs.list(thread_id=thread_id, limit=1)
                        most_recent_run = None
                        async for run in runs_paged:
                            most_recent_run = run
                            break
                        
                        if most_recent_run and most_recent_run.status == INCOMPLETE_RUN_STATUS:
                            should_discard = True

                    except Exception as check_err:
                        should_discard = True
                    
                    if should_discard:
                        cache.pop(conversation_id, None)
                        thread_id = None

                truncation_strategy = TruncationObject(type="last_messages", last_messages=4)

                from history_sql import SqlQueryTool, get_fabric_db_connection
                db_connection = await get_fabric_db_connection()
                if not db_connection:
                    logger.error("Failed to establish database connection")
                    raise Exception("Database connection failed")

                custom_tool = SqlQueryTool(pyodbc_conn=db_connection)

                try:
                    async with ChatAgent(
                        chat_client=AzureAIAgentClient(project_client=client, agent_id=foundry_agent.id),
                        tools=[custom_tool.run_sql_query],
                        tool_choice="auto",
                        store=True
                    ) as chat_agent:
                        if thread_id:
                            thread = chat_agent.get_new_thread(service_thread_id=thread_id)
                            assert thread.is_initialized
                        else:
                            service_thread = await client.agents.threads.create()
                            thread = chat_agent.get_new_thread(service_thread_id=service_thread.id)
                            assert thread.is_initialized
                            cache[conversation_id] = service_thread.id

                        async for response in chat_agent.run_stream(messages=query, thread=thread, truncation_strategy=truncation_strategy):
                            if response.text:
                                complete_response += response.text
                                yield response.text
                finally:
                    if db_connection:
                        db_connection.close()
        finally:
            # Close credential to prevent unclosed client session warnings
            if credential is not None:
                await credential.close()

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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error streaming OpenAI text") from e

    finally:
        # Provide a fallback response when no data is received from OpenAI.
        if complete_response == "":
            cache = get_thread_cache()
            cache.pop(conversation_id, None)
            yield "I cannot answer this question with the current data. Please rephrase or add more details."


async def stream_chat_request(conversation_id, query):
    """
    Handles streaming chat requests.
    """
    async def generate():
        try:
            assistant_content = ""
            async for chunk in stream_openai_text(conversation_id, query):
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
