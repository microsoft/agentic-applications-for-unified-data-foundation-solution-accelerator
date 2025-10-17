"""
FastAPI application entry point for the Agentic Applications for Unified Data Foundation Solution Accelerator.

This module sets up the FastAPI app, configures middleware, loads environment variables,
registers API routers, and manages application lifespan events such as agent initialization
and cleanup.
"""


from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv
import uvicorn
import os

from chat import router as chat_router
from history import router as history_router
from history_sql import router as history_sql_router
from semantic_kernel.agents import AzureAIAgent, AzureAIAgentSettings
from auth.azure_credential_utils import get_azure_credential_async
load_dotenv()


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """
    Manages the application lifespan events for the FastAPI app.

    On startup, initializes the Azure AI agent using the configuration and attaches it to the app state.
    On shutdown, deletes the agent instance and performs any necessary cleanup.
    """
    from chat import ChatWithDataPlugin

    ai_agent_settings = AzureAIAgentSettings(endpoint=os.getenv("AZURE_AI_AGENT_ENDPOINT"))
    client = AzureAIAgent.create_client(
        credential=await get_azure_credential_async(),
        endpoint=ai_agent_settings.endpoint,
    )
    agent = await client.agents.get_agent(
        agent_id=os.getenv("AGENT_ID_ORCHESTRATOR")
    )
    # print(f"Agent retrieved: {agent}")
    fastapi_app.state.orchestrator_agent = AzureAIAgent(
        client=client,
        definition=agent,
        plugins=[ChatWithDataPlugin()]
    )
    yield
    fastapi_app.state.orchestrator_agent = None


def build_app() -> FastAPI:
    """
    Creates and configures the FastAPI application instance.
    """
    fastapi_app = FastAPI(
        title="Agentic Applications for Unified Data Foundation Solution Accelerator",
        version="1.0.0",
        lifespan=lifespan
    )

    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    fastapi_app.include_router(chat_router, prefix="/api", tags=["chat"])
    fastapi_app.include_router(history_router, prefix="/history", tags=["history"])
    fastapi_app.include_router(history_sql_router, prefix="/historyfab", tags=["historyfab"])

    @fastapi_app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {"status": "healthy"}

    return fastapi_app


app = build_app()


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
