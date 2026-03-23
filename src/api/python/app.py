"""
FastAPI application entry point for the Agentic Applications for Unified Data Foundation Solution Accelerator.

This module sets up the FastAPI app, configures middleware, loads environment variables,
registers API routers, and manages application lifespan events such as agent initialization
and cleanup.
"""

import json
import os
import logging
from contextvars import ContextVar
from azure.monitor.opentelemetry import configure_azure_monitor

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace

from dotenv import load_dotenv

# Context variables for request-scoped data (auto-injected into all logs)
conversation_id_var: ContextVar[str] = ContextVar("conversation_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")
import uvicorn

from chat import router as chat_router
from history import router as history_router
from history_sql import router as history_sql_router

load_dotenv()

# Basic application logging level (default: INFO)
AZURE_BASIC_LOGGING_LEVEL = os.getenv("AZURE_BASIC_LOGGING_LEVEL", "INFO").upper()
# Azure package logging level (default: WARNING to suppress verbose INFO)
AZURE_PACKAGE_LOGGING_LEVEL = os.getenv("AZURE_PACKAGE_LOGGING_LEVEL", "WARNING").upper()
# Comma-separated list of Azure logger names to suppress
AZURE_LOGGING_PACKAGES = [
    pkg.strip() for pkg in os.getenv("AZURE_LOGGING_PACKAGES", "").split(",") if pkg.strip()
]

logging.basicConfig(
    level=getattr(logging, AZURE_BASIC_LOGGING_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Configure Application Insights AFTER logging.basicConfig
connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if connection_string:
    configure_azure_monitor(connection_string=connection_string)
    logging.getLogger().setLevel(getattr(logging, AZURE_BASIC_LOGGING_LEVEL, logging.INFO))
    logging.info("Application Insights configured with the provided connection string")
else:
    logging.warning("No Application Insights connection string found. Skipping configuration")

# Wrap the LogRecordFactory AFTER configure_azure_monitor() so our factory runs last.
# Set conversation_id and user_id as individual record attributes (not inside a dict).
# The OTel LoggingHandler picks up non-standard record attributes and maps them
# directly to App Insights customDimensions as individual keys.
# Using a dict (record.custom_dimensions) doesn't work because dicts are not valid
# OTel attribute types and get stringified (e.g., "{'conversation_id': '...')").
_original_factory = logging.getLogRecordFactory()

def _record_factory(*args, **kwargs):
    record = _original_factory(*args, **kwargs)
    # Skip records from track_event — they pass properties via their own mechanism.
    if getattr(record, "funcName", "") == "track_event":
        return record
    cid = conversation_id_var.get("")
    uid = user_id_var.get("")
    if cid:
        record.conversation_id = cid
    if uid:
        record.user_id = uid
    return record

logging.setLogRecordFactory(_record_factory)

# Suppress noisy Azure SDK / third-party loggers at the configured package level
_default_suppressed_loggers = [
    "azure.core.pipeline.policies.http_logging_policy",
    "azure.identity",
    "azure.ai",
    "azure.monitor.opentelemetry",
    "opentelemetry",
    "urllib3",
    "httpx",
    "httpcore",
]
for logger_name in set(_default_suppressed_loggers + AZURE_LOGGING_PACKAGES):
    logging.getLogger(logger_name).setLevel(
        getattr(logging, AZURE_PACKAGE_LOGGING_LEVEL, logging.WARNING)
    )


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

    @fastapi_app.middleware("http")
    async def attach_trace_attributes(request: Request, call_next):
        """Auto-attach user_id and conversation_id to span + logging context."""
        span = trace.get_current_span()

        # user_id from Easy Auth header
        user_id = request.headers.get("x-ms-client-principal-id", "")
        if user_id:
            user_id_var.set(user_id)
            if span and span.is_recording():
                span.set_attribute("user_id", user_id)

        # conversation_id from JSON body (POST/PUT/PATCH only)
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.body()
                if body:
                    body_json = json.loads(body)
                    conversation_id = body_json.get("conversation_id", "")
                    if conversation_id:
                        conversation_id_var.set(conversation_id)
                        if span and span.is_recording():
                            span.set_attribute("conversation_id", conversation_id)
            except Exception:
                pass

        return await call_next(request)

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
