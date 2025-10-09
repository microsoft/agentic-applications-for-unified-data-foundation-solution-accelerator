"""
Chat API module for handling chat interactions and responses.
"""

import asyncio
import json
import logging
import os
import random
import re
import time
import uuid
from types import SimpleNamespace
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

from agent_framework import ChatAgent, AgentThread
from agent_framework.azure import AzureAIAgentClient
from agent_framework.exceptions import AgentException

# Azure Auth
from auth.azure_credential_utils import get_azure_credential_async, get_azure_credential

load_dotenv()

# Constants
HOST_NAME = "Agentic Applications for Unified Data Foundation"
HOST_INSTRUCTIONS = "Answer questions about Sales, Products and Orders data."

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

# Load schema from tables.json
file_path = "tables.json"
if not os.path.isfile(file_path):
    raise FileNotFoundError(f"Could not find tables.json at {file_path}")

with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# Prepare SQL instructions with table/column metadata
counter = 1
tables_str = ''
for table in data['tables']:
    tables_str += f"\n {counter}.Table:dbo.{table['tablename']}\n        Columns: " + ', '.join(table['columns'])
    counter += 1

agent_instructions = '''You are a helpful assistant.

Generate a valid T-SQL query for SQL database in Fabric for the user's request using these tables:''' + tables_str + '''Use accurate and semantically appropriate T-SQL expressions, data types, functions, aliases, and conversions based strictly on the column definitions and the explicit or implicit intent of the user query.
Avoid assumptions or defaults not grounded in schema or context.
Ensure all aggregations, filters, grouping logic, and time-based calculations are precise, logically consistent, and reflect the user's intent without ambiguity.
Only use the tables listed above. If the user query does not pertain to these tables, respond with "I don't know".
Always Use the get_sql_response function to execute the SQL query and get the results.

if the user query is asking for a chart,
    generate valid chart data to be shown using chart.js with version 4.4.4 compatible.
    Include chart type and chart options.
    Pick the best chart type for given data.
    Do not generate a chart unless the input contains some numbers. Otherwise return a message that Chart cannot be generated.
    **ONLY** return a valid JSON output and nothing else.
    Verify that the generated JSON can be parsed using json.loads.
    Do not include tooltip callbacks in JSON.
    Always make sure that the generated json can be rendered in chart.js.
    Always remove any extra trailing commas.
    Verify and refine that JSON should not have any syntax errors like extra closing brackets.
    Ensure Y-axis labels are fully visible by increasing **ticks.padding**, **ticks.maxWidth**, or enabling word wrapping where necessary.
    Ensure bars and data points are evenly spaced and not squished or cropped at **100%** resolution by maintaining appropriate **barPercentage** and **categoryPercentage** values.

If the question is unrelated to data but is conversational (e.g., greetings or follow-ups), respond appropriately using context.

Always use the structure { "answer": "", "citations": [ {"url":"","title":""} ] } to return final response.
If you do not know the answer, just say "I don't know" and do not try to make up an answer.'''


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
        try:
            if thread_id:
                # Use async context manager to ensure proper cleanup
                async with AIProjectClient(
                    endpoint=os.getenv("AZURE_AI_AGENT_ENDPOINT"),
                    credential=await get_azure_credential_async()
                ) as client:
                    await client.agents.threads.delete(thread_id=thread_id)
                    logger.info("Thread deleted successfully: %s", thread_id)
        except Exception as e:
            logger.error("Failed to delete thread %s: %s", thread_id, e)


def track_event_if_configured(event_name: str, event_data: dict):
    """Track event to Application Insights if configured."""
    instrumentation_key = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if instrumentation_key:
        track_event(event_name, event_data)
    else:
        logging.warning("Skipping track_event for %s as Application Insights is not configured", event_name)


def format_stream_response(chat_completion_chunk, history_metadata, apim_request_id):
    """Format chat completion chunk into standardized response object."""
    response_obj = {
        "id": chat_completion_chunk.id,
        "model": chat_completion_chunk.model,
        "created": chat_completion_chunk.created,
        "object": chat_completion_chunk.object,
        "choices": [{"messages": []}],
        "history_metadata": history_metadata,
        "apim-request-id": apim_request_id,
    }

    if len(chat_completion_chunk.choices) > 0:
        delta = chat_completion_chunk.choices[0].delta
        if delta:
            content = getattr(delta, "content", "")
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except json.JSONDecodeError:
                    pass
            if hasattr(delta, "context"):
                message_obj = {"role": "tool", "content": json.dumps(delta.context)}
                response_obj["choices"][0]["messages"].append(message_obj)
                return response_obj
            if delta.role == "assistant" and hasattr(delta, "context"):
                message_obj = {
                    "role": "assistant",
                    "context": delta.context,
                }
                response_obj["choices"][0]["messages"].append(message_obj)
                return response_obj
            else:
                if delta.content:
                    message_obj = {
                        "role": "assistant",
                        "content": content,
                    }
                    response_obj["choices"][0]["messages"].append(message_obj)
                    return response_obj

    return {}


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
    try:
        if not query:
            query = "Please provide a query."

        async with AIProjectClient(
            endpoint=os.getenv("AZURE_AI_AGENT_ENDPOINT"),
            credential=await get_azure_credential_async()
        ) as client:
            foundry_agent = await client.agents.get_agent(os.getenv("AGENT_ID_CHAT"))
            # print(f"Using Agent: {foundry_agent.name} with ID: {foundry_agent.id}")

            cache = get_thread_cache()
            thread_id = cache.get(conversation_id, None)

            truncation_strategy = TruncationObject(type="last_messages", last_messages=4)

            from history_sql import SqlQueryTool, get_fabric_db_connection
            custom_tool = SqlQueryTool(pyodbc_conn=await get_fabric_db_connection())
            async with ChatAgent(
                chat_client=AzureAIAgentClient(project_client=client, agent_id=foundry_agent.id),
                instructions=agent_instructions,
                tools=[custom_tool.run_sql_query],
                tool_choice="auto"
            ) as chat_agent:
                if thread_id:
                    # print(f"Resuming existing thread with ID: {thread_id}")
                    thread = chat_agent.get_new_thread(service_thread_id=thread_id)
                    assert thread.is_initialized
                else:
                    service_thread = await client.agents.threads.create()
                    thread = chat_agent.get_new_thread(service_thread_id=service_thread.id)
                    assert thread.is_initialized
                    # print(f"Created new thread with ID: {service_thread.id}")
                    cache[conversation_id] = service_thread.id
                
                async for response in chat_agent.run_stream(messages=query, thread=thread, truncation_strategy=truncation_strategy):
                    if response.text:
                        complete_response += response.text
                        # print(f"Complete response so far: {complete_response}")
                        yield response.text

    except RuntimeError as e:
        complete_response = str(e)
        if "Rate limit is exceeded" in str(e):
            logger.error("Rate limit error: %s", e)
            raise AgentException(f"Rate limit is exceeded. {str(e)}") from e
        else:
            logger.error("RuntimeError: %s", e)
            raise AgentException(f"An unexpected runtime error occurred: {str(e)}") from e

    except Exception as e:
        complete_response = str(e)
        logger.error("Error in stream_openai_text: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error streaming OpenAI text") from e

    finally:
        # Provide a fallback response when no data is received from OpenAI.
        if complete_response == "":
            logger.info("No response received from OpenAI.")
            cache = get_thread_cache()
            thread_id = cache.pop(conversation_id, None)
            if thread_id is not None:
                corrupt_key = f"{conversation_id}_corrupt_{random.randint(1000, 9999)}"
                cache[corrupt_key] = thread_id
            yield "I cannot answer this question with the current data. Please rephrase or add more details."


async def stream_chat_request(request_body, conversation_id, query):
    """
    Handles streaming chat requests.
    """
    history_metadata = request_body.get("history_metadata", {})

    async def generate():
        try:
            assistant_content = ""
            async for chunk in stream_openai_text(conversation_id, query):
                if isinstance(chunk, dict):
                    chunk = json.dumps(chunk)  # Convert dict to JSON string
                assistant_content += str(chunk)

                if assistant_content:
                    chat_completion_chunk = {
                        "id": "",
                        "model": "",
                        "created": 0,
                        "object": "",
                        "choices": [
                            {
                                "messages": [],
                                "delta": {},
                            }
                        ],
                        "history_metadata": history_metadata,
                        "apim-request-id": "",
                    }

                    chat_completion_chunk["id"] = str(uuid.uuid4())
                    chat_completion_chunk["model"] = "rag-model"
                    chat_completion_chunk["created"] = int(time.time())
                    chat_completion_chunk["object"] = "extensions.chat.completion.chunk"
                    chat_completion_chunk["choices"][0]["messages"].append(
                        {"role": "assistant", "content": assistant_content}
                    )
                    chat_completion_chunk["choices"][0]["delta"] = {
                        "role": "assistant",
                        "content": assistant_content,
                    }

                    completion_chunk_obj = json.loads(
                        json.dumps(chat_completion_chunk),
                        object_hook=lambda d: SimpleNamespace(**d),
                    )
                    formatted = format_stream_response(completion_chunk_obj, history_metadata, "")
                    yield json.dumps(formatted, ensure_ascii=False) + "\n\n"

        except AgentException as e:
            error_message = str(e)
            retry_after = "sometime"
            if "Rate limit is exceeded" in error_message:
                match = re.search(r"Try again in (\d+) seconds", error_message)
                if match:
                    retry_after = f"{match.group(1)} seconds"
                logger.error("Rate limit error: %s", error_message)
                error_response = {
                    "error": f"Rate limit exceeded. Please try again after {retry_after}."
                }
                yield json.dumps(error_response) + "\n\n"
            else:
                logger.error("Agent exception: %s", error_message)
                error_response = {"error": "An error occurred. Please try again later."}
                yield json.dumps(error_response) + "\n\n"

        except Exception as e:
            logger.error("Unexpected error: %s", e)
            error_response = {"error": "An error occurred while processing the request."}
            yield json.dumps(error_response) + "\n\n"

    return generate()


@router.post("/chat")
async def conversation(request: Request):
    """Handle chat requests - streaming text or chart generation based on query keywords."""
    try:
        # Get the request JSON and last RAG response from the client
        request_json = await request.json()
        # last_rag_response = request_json.get("last_rag_response")
        conversation_id = request_json.get("conversation_id")
        # logger.info("Received last_rag_response: %s", last_rag_response)

        query = request_json.get("messages")[-1].get("content")

        result = await stream_chat_request(request_json, conversation_id, query)
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
