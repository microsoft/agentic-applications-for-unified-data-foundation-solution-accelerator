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
from typing import Annotated, AsyncGenerator

from cachetools import TTLCache
from dotenv import load_dotenv
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

# Azure SDK
from azure.ai.agents.models import TruncationObject, MessageRole, ListSortOrder
from azure.monitor.events.extension import track_event
from azure.monitor.opentelemetry import configure_azure_monitor
from azure.ai.projects import AIProjectClient

# Semantic Kernel
from semantic_kernel.agents import AzureAIAgentThread
from semantic_kernel.exceptions.agent_exceptions import AgentException
from semantic_kernel.functions.kernel_function_decorator import kernel_function

# Azure Auth
from auth.azure_credential_utils import get_azure_credential

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


class ChatWithDataPlugin:
    """Plugin for handling chat interactions with data using various AI agents."""

    def __init__(self):
        self.ai_project_endpoint = os.getenv("AZURE_AI_AGENT_ENDPOINT")
        self.ai_project_api_version = os.getenv("AZURE_AI_AGENT_API_VERSION", "2025-05-01")
        self.foundry_sql_agent_id = os.getenv("AGENT_ID_SQL")
        self.foundry_chart_agent_id = os.getenv("AGENT_ID_CHART")

    @kernel_function(name="ChatWithSQLDatabase",
                     description="Provides quantified results, metrics, or structured data from the SQL database.")
    async def get_sql_response(
            self,
            input: Annotated[str, "the question"]
    ):
        """
        Executes a SQL generation agent to convert a natural language query into a T-SQL query,
        executes the SQL, and returns the result.

        Args:
            input (str): Natural language question to be converted into SQL.

        Returns:
            str: SQL query result or an error message if failed.
        """

        query = input
        try:
            from history_sql import execute_sql_query, run_sql_query
            project_client = AIProjectClient(
                endpoint=self.ai_project_endpoint,
                credential=get_azure_credential(),
                api_version=self.ai_project_api_version,
            )

            thread = project_client.agents.threads.create()

            project_client.agents.messages.create(
                thread_id=thread.id,
                role=MessageRole.USER,
                content=query,
            )

            run = project_client.agents.runs.create_and_process(
                thread_id=thread.id,
                agent_id=self.foundry_sql_agent_id,
            )

            if run.status == "failed":
                print(f"Run failed: {run.last_error}")
                return "Details could not be retrieved. Please try again later."

            sql_query = ""
            messages = project_client.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
            for msg in messages:
                if msg.role == MessageRole.AGENT and msg.text_messages:
                    sql_query = msg.text_messages[-1].text.value
                    break
            sql_query = sql_query.replace("```sql", '').replace("```", '').strip()
            # logger.info("Generated SQL Query: %s", sql_query)
            answer_raw = await run_sql_query(sql_query)
            if isinstance(answer_raw, str):
                answer = answer_raw[:20000] if len(answer_raw) > 20000 else answer_raw
            else:
                answer = answer_raw or ""

            # Clean up
            project_client.agents.threads.delete(thread_id=thread.id)

        except Exception as e:
            print(f"Fabric-SQL-Kernel-error: {e}", flush=True)
            answer = 'Details could not be retrieved. Please try again later.'

        print(f"fabric-SQL-Kernel-response: {answer}", flush=True)
        return answer

    @kernel_function(name="GenerateChartData", description="Generates Chart.js v4.4.4 compatible JSON data for data visualization requests using current and immediate previous context.")
    async def get_chart_data(
            self,
            input: Annotated[str, "The user's data visualization request along with relevant conversation history and context needed to generate appropriate chart data"],
    ):
        query = input
        query = query.strip()
        try:
            project_client = AIProjectClient(
                endpoint=self.ai_project_endpoint,
                credential=get_azure_credential(),
                api_version=self.ai_project_api_version,
            )

            thread = project_client.agents.threads.create()

            project_client.agents.messages.create(
                thread_id=thread.id,
                role=MessageRole.USER,
                content=query,
            )

            run = project_client.agents.runs.create_and_process(
                thread_id=thread.id,
                agent_id=self.foundry_chart_agent_id,
            )

            if run.status == "failed":
                print(f"Run failed: {run.last_error}")
                return "Details could not be retrieved. Please try again later."

            chartdata = ""
            messages = project_client.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
            for msg in messages:
                if msg.role == MessageRole.AGENT and msg.text_messages:
                    chartdata = msg.text_messages[-1].text.value
                    break
            # Clean up
            project_client.agents.threads.delete(thread_id=thread.id)

        except Exception as e:
            print(f"fabric-Chat-Kernel-error: {e}", flush=True)
            chartdata = 'Details could not be retrieved. Please try again later.'

        print(f"fabric-Chat-Kernel-response: {chartdata}", flush=True)
        return chartdata

    # @kernel_function(name="ChatWithCustomerSales", description="Provides summaries or detailed explanations of customer sales.")
    # async def get_answers_from_customersales(
    #         self,
    #         question: Annotated[str, "the question"]
    # ):
    #     """
    #     Uses Microsoft Fabric agent to answer a question based on customer data.

    #     Args:
    #         question (str): The user's query.

    #     Returns:
    #         dict: A dictionary with the answer and citation metadata.
    #     """
    #     answer: Dict[str, Any] = {"answer": "", "citations": []}
    #     agent = None

    #     try:
    #         # Get the fabric agent
    #         print("FABRIC-CustomerSalesKernel", flush=True)
    #         agent_info = await AgentFactory.get_agent(AgentType.FABRIC)
    #         agent = agent_info["agent"]
    #         project_client = agent_info["client"]
    #         print("FABRIC-CustomerSalesKernel: Fabric agent retrieved successfully", flush=True)
    #         print(f"FABRIC-CustomerSalesKernel: Agent ID: {agent_info['agent'].id}", flush=True)

    #         # Create thread
    #         thread = project_client.agents.threads.create()
    #         print(f"FABRIC-CustomerSalesKernel: Thread created successfully: {thread.id}", flush=True)

    #         # Create message with the actual question
    #         project_client.agents.messages.create(
    #             thread_id=thread.id,
    #             role=MessageRole.USER,
    #             content=question,
    #         )
    #         print(f"FABRIC-CustomerSalesKernel: Message created in thread {thread.id} with question: {question}", flush=True)

    #         run = project_client.agents.runs.create_and_process(
    #             thread_id=thread.id,
    #             agent_id=agent.id
    #         )
    #         print(f"FABRIC-CustomerSalesKernel: Agent run completed with status: {run.status}")

    #         if run.status == "failed":
    #             logging.error(f"FABRIC-CustomerSalesKernel: Run failed: {run.last_error}")
    #         else:
    #             # ADD CITATION PROCESSING HERE
    #             # def convert_citation_markers(text):
    #             #     def replace_marker(match):
    #             #         content = match.group(1).strip()
    #             #         parts = content.split(":")
    #             #         if len(parts) == 2 and parts[1].isdigit():
    #             #             new_index = int(parts[1]) + 1
    #             #             return f"[{new_index}]"
    #             #         return match.group(0)

    #             #     return re.sub(r'【\s*(\d+:\d+)\s*†source】', replace_marker, text)

    #             # Check the response structure
    #             # try:
    #             #     for run_step in project_client.agents.run_steps.list(thread_id=thread.id, run_id=run.id):
    #             #         print(f"FABRIC-CustomerSalesKernel: Processing run step: {run_step.id}, type: {type(run_step.step_details)}")
    #             #         if isinstance(run_step.step_details, RunStepToolCallDetails):
    #             #             for tool_call in run_step.step_details.tool_calls:
    #             #                 print(f"FABRIC-CustomerSalesKernel: Processing tool call: {tool_call}")

    #             # except Exception as run_step_error:
    #             #     logging.error(f"FABRIC-CustomerSalesKernel: Failed to process run steps: {type(run_step_error).__name__}: {run_step_error}")
    #             #     raise

    #             try:
    #                 messages = project_client.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
    #                 for msg in messages:
    #                     if msg.role == MessageRole.AGENT and msg.text_messages:
    #                         raw_answer = msg.text_messages[-1].text.value
    #                         # print(f"Raw answer from agent: {raw_answer}")
    #                         # converted_answer = convert_citation_markers(raw_answer)
    #                         # print(f"Converted answer: {converted_answer}")
    #                         answer["answer"] = raw_answer
    #                         break
    #             except Exception as messages_error:
    #                 # logging.error(f"Failed to retrieve messages: {type(messages_error).__name__}: {messages_error}")
    #                 raise

    #             logging.info(f"FABRIC-CustomerSalesKernel-Thread ID: {thread.id}, Run ID: {run.id}")
    #             # project_client.agents.threads.delete(thread_id=thread.id)

    #         if not answer["answer"]:
    #             answer["answer"] = "I couldn't find specific information about customer sales. Please try rephrasing your question."

    #     except Exception as e:
    #         logging.error(f"Full error details: {repr(e)}")
    #         import traceback
    #         return {"answer": "Details could not be retrieved. Please try again later.", "citations": []}

    #     print(f"FABRIC-CustomerSalesKernel-Answer: %s" % answer, flush=True)
    #     return answer


class ExpCache(TTLCache):
    """Extended TTLCache that deletes Azure AI agent threads when items expire."""

    def __init__(self, *args, agent=None, **kwargs):
        """Initialize cache with optional agent for thread cleanup."""
        super().__init__(*args, **kwargs)
        self.agent = agent

    def expire(self, time=None):
        """Remove expired items and delete associated Azure AI threads."""
        items = super().expire(time)
        for key, thread_id in items:
            try:
                if self.agent:
                    thread = AzureAIAgentThread(client=self.agent.client, thread_id=thread_id)
                    asyncio.create_task(thread.delete())
                    logger.info("Thread deleted: %s", thread_id)
            except Exception as e:
                logger.error("Failed to delete thread for key %s: %s", key, e)
        return items

    def popitem(self):
        """Remove item using LRU eviction and delete associated Azure AI thread."""
        key, thread_id = super().popitem()
        try:
            if self.agent:
                thread = AzureAIAgentThread(client=self.agent.client, thread_id=thread_id)
                asyncio.create_task(thread.delete())
                logger.info("Thread deleted (LRU evict): %s", thread_id)
        except Exception as e:
            logger.error("Failed to delete thread for key %s (LRU evict): %s", key, e)
        return key, thread_id


# async def get_db_connection():
#     """Get a connection to the SQL database"""
#     database = os.getenv("SQLDB_DATABASE")
#     server = os.getenv("SQLDB_SERVER")
#     driver = "{ODBC Driver 17 for SQL Server}"
#     mid_id = os.getenv("SQLDB_USER_MID")

#     async with AsyncDefaultAzureCredential(managed_identity_client_id=mid_id) as credential:
#         token = await credential.get_token("https://database.windows.net/.default")
#         token_bytes = token.token.encode("utf-16-LE")
#         token_struct = struct.pack(
#             f"<I{len(token_bytes)}s",
#             len(token_bytes),
#             token_bytes
#         )
#         SQL_COPT_SS_ACCESS_TOKEN = 1256

#         # Set up the connection
#         connection_string = f"DRIVER={driver};SERVER={server};DATABASE={database};"
#         conn = pyodbc.connect(
#             connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct}
#         )

#         logging.info("Connected using Default Azure Credential")
#         return conn


# async def adjust_processed_data_dates():
#     """
#     Adjusts the dates in the processed_data, km_processed_data, and processed_data_key_phrases tables
#     to align with the current date.
#     """
#     conn = await get_db_connection()
#     cursor = None
#     try:
#         cursor = conn.cursor()
#         # Adjust the dates to the current date
#         today = datetime.today()
#         cursor.execute(
#             "SELECT MAX(CAST(StartTime AS DATETIME)) FROM [dbo].[processed_data]"
#         )
#         max_start_time = (cursor.fetchone())[0]

#         if max_start_time:
#             days_difference = (today - max_start_time).days - 1
#             if days_difference != 0:
#                 # Update processed_data table
#                 cursor.execute(
#                     "UPDATE [dbo].[processed_data] SET StartTime = FORMAT(DATEADD(DAY, ?, StartTime), 'yyyy-MM-dd "
#                     "HH:mm:ss'), EndTime = FORMAT(DATEADD(DAY, ?, EndTime), 'yyyy-MM-dd HH:mm:ss')",
#                     (days_difference, days_difference)
#                 )
#                 # Update km_processed_data table
#                 cursor.execute(
#                     "UPDATE [dbo].[km_processed_data] SET StartTime = FORMAT(DATEADD(DAY, ?, StartTime), 'yyyy-MM-dd "
#                     "HH:mm:ss'), EndTime = FORMAT(DATEADD(DAY, ?, EndTime), 'yyyy-MM-dd HH:mm:ss')",
#                     (days_difference, days_difference)
#                 )
#                 # Update processed_data_key_phrases table
#                 cursor.execute(
#                     "UPDATE [dbo].[processed_data_key_phrases] SET StartTime = FORMAT(DATEADD(DAY, ?, StartTime), "
#                     "'yyyy-MM-dd HH:mm:ss')", (days_difference,)
#                 )
#                 # Commit the changes
#                 conn.commit()
#     finally:
#         if cursor:
#             cursor.close()
#         conn.close()


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
                        "content": delta.content,
                    }
                    response_obj["choices"][0]["messages"].append(message_obj)
                    return response_obj

    return {}


# Global thread cache
thread_cache = None


def get_thread_cache(agent):
    """Get or create the global thread cache."""
    global thread_cache
    if thread_cache is None:
        thread_cache = ExpCache(maxsize=1000, ttl=3600.0, agent=agent)
    return thread_cache


async def stream_openai_text(conversation_id: str, query: str, agent) -> AsyncGenerator[str, None]:
    """
    Get a streaming text response from OpenAI.
    """
    thread = None
    complete_response = ""
    try:
        if not query:
            query = "Please provide a query."

        cache = get_thread_cache(agent)
        thread_id = cache.get(conversation_id, None)

        if thread_id:
            thread = AzureAIAgentThread(client=agent.client, thread_id=thread_id)

        truncation_strategy = TruncationObject(type="last_messages", last_messages=4)

        async for response in agent.invoke_stream(messages=query, thread=thread, truncation_strategy=truncation_strategy):
            cache[conversation_id] = response.thread.id
            complete_response += str(response.content)
            yield response.content

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
            cache = get_thread_cache(agent)
            thread_id = cache.pop(conversation_id, None)
            if thread_id is not None:
                corrupt_key = f"{conversation_id}_corrupt_{random.randint(1000, 9999)}"
                cache[corrupt_key] = thread_id
            yield "I cannot answer this question with the current data. Please rephrase or add more details."


async def stream_chat_request(request_body, conversation_id, query, agent):
    """
    Handles streaming chat requests.
    """
    history_metadata = request_body.get("history_metadata", {})

    async def generate():
        try:
            assistant_content = ""
            async for chunk in stream_openai_text(conversation_id, query, agent):
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
                    yield json.dumps(format_stream_response(completion_chunk_obj, history_metadata, "")) + "\n\n"

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
        last_rag_response = request_json.get("last_rag_response")
        conversation_id = request_json.get("conversation_id")
        # logger.info("Received last_rag_response: %s", last_rag_response)

        query = request_json.get("messages")[-1].get("content")

        agent = request.app.state.orchestrator_agent

        result = await stream_chat_request(request_json, conversation_id, query, agent)
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
