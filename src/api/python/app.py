"""
FastAPI application entry point for the Agentic Applications for Unified Data Foundation Solution Accelerator.

This module sets up the FastAPI app, configures middleware, loads environment variables,
registers API routers, and manages application lifespan events such as agent initialization
and cleanup.
"""

import os
import logging
from azure.monitor.opentelemetry import configure_azure_monitor

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv
import uvicorn

from chat import router as chat_router
from history import router as history_router
from history_sql import router as history_sql_router

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

# Reduce Azure Monitor internal logs
logging.getLogger("azure.monitor.opentelemetry").setLevel(logging.ERROR)
    
# Exclude Azure Monitor settings endpoint from tracing
os.environ["OTEL_PYTHON_REQUESTS_EXCLUDED_URLS"] = "settings.sdk.monitor.azure.com"

load_dotenv()


def build_app() -> FastAPI:
    """
    Creates and configures the FastAPI application instance.
    """
    fastapi_app = FastAPI(
        title="Agentic Applications for Unified Data Foundation Solution Accelerator",
        version="1.0.0"
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
