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
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from chat import router as chat_router
from history import router as history_router
from history_sql import router as history_sql_router

conversation_id_var: ContextVar[str] = ContextVar("conversation_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")

load_dotenv()


def _configure_logging():
    """Set up logging levels, Application Insights, and log-record enrichment."""
    basic_level = getattr(logging, os.getenv("AZURE_BASIC_LOGGING_LEVEL", "INFO").upper(), logging.INFO)
    package_level = getattr(logging, os.getenv("AZURE_PACKAGE_LOGGING_LEVEL", "WARNING").upper(), logging.WARNING)
    extra_suppressed = [p.strip() for p in os.getenv("AZURE_LOGGING_PACKAGES", "").split(",") if p.strip()]

    logging.basicConfig(level=basic_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    conn_str = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if conn_str:
        configure_azure_monitor(connection_string=conn_str)
        logging.getLogger().setLevel(basic_level)
        logging.info("Application Insights configured")
    else:
        logging.warning("No Application Insights connection string found")

    # Must be set AFTER configure_azure_monitor(); individual attrs map to customDimensions keys
    original_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = original_factory(*args, **kwargs)
        if record.funcName == "track_event":
            return record
        cid = conversation_id_var.get("")
        uid = user_id_var.get("")
        if cid:
            record.conversation_id = cid
        if uid:
            record.user_id = uid
        return record

    logging.setLogRecordFactory(record_factory)

    # Suppress noisy Azure SDK / third-party loggers
    for name in set([
        "azure.core.pipeline.policies.http_logging_policy",
        "azure.identity",
        "azure.ai",
        "azure.monitor.opentelemetry",
        "opentelemetry",
        "urllib3",
        "httpx",
        "httpcore",
    ] + extra_suppressed):
        logging.getLogger(name).setLevel(package_level)


_configure_logging()


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

        user_id = request.headers.get("x-ms-client-principal-id", "")
        if user_id:
            user_id_var.set(user_id)
            if span and span.is_recording():
                span.set_attribute("user_id", user_id)

        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.body()
                if body:
                    data = json.loads(body)
                    cid = data.get("conversation_id", "")
                    if cid:
                        conversation_id_var.set(cid)
                        if span and span.is_recording():
                            span.set_attribute("conversation_id", cid)
            except Exception as ex:
                logging.warning("Failed to parse request body for conversation_id: %s", ex)
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
FastAPIInstrumentor.instrument_app(app, excluded_urls="health")


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
