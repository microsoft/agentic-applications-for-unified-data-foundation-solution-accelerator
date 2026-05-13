"""
Reusable LLM token usage tracking helpers.

This module centralizes:
  * Application Insights event emission (guarded by configuration).
  * Token-usage extraction from various LLM SDK shapes
    (dict payloads, agent_framework streaming updates, OpenAI Responses).
  * Emission of standardized telemetry events:
      - LLM_Token_Usage_Summary
      - LLM_Agent_Token_Usage
      - LLM_Model_Token_Usage

Import these helpers from any module that needs to record LLM usage,
instead of duplicating the logic.
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Tuple

from azure.monitor.events.extension import track_event

logger = logging.getLogger(__name__)

UsageTuple = Tuple[int, int, int]  # (input_tokens, output_tokens, total_tokens)


def track_event_if_configured(event_name: str, event_data: dict) -> None:
    """Track event to Application Insights if a connection string is configured."""
    instrumentation_key = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if instrumentation_key:
        track_event(event_name, event_data)
    else:
        logger.warning(
            "Skipping track_event for %s as Application Insights is not configured",
            event_name,
        )


def extract_usage_from_dict(d: dict) -> Optional[UsageTuple]:
    """Extract (input, output, total) token counts from a usage-like dict."""
    if not isinstance(d, dict) or not d:
        return None
    try:
        inp = d.get("input_token_count", 0) or d.get("prompt_tokens", 0) or d.get("input_tokens", 0) or 0
        out = d.get("output_token_count", 0) or d.get("completion_tokens", 0) or d.get("output_tokens", 0) or 0
        tot = d.get("total_token_count", 0) or d.get("total_tokens", 0) or (inp + out)
        inp_i, out_i, tot_i = int(inp), int(out), int(tot)
    except (TypeError, ValueError):
        return None
    if tot_i > 0:
        return (inp_i, out_i, tot_i)
    return None


def extract_usage_from_update(update) -> Optional[UsageTuple]:
    """Extract (input, output, total) token counts from an agent_framework streaming update.

    Checks, in order:
      1. update.contents[*].usage_details (dict)
      2. update.raw_representation.usage (dict or object with token attributes)
    """
    contents = getattr(update, "contents", None) or []
    for item in contents:
        usage_details = getattr(item, "usage_details", None)
        if isinstance(usage_details, dict):
            result = extract_usage_from_dict(usage_details)
            if result:
                return result

    raw = getattr(update, "raw_representation", None)
    if raw is not None:
        usage_obj = getattr(raw, "usage", None)
        if usage_obj is not None:
            if isinstance(usage_obj, dict):
                result = extract_usage_from_dict(usage_obj)
                if result:
                    return result
            else:
                try:
                    inp = getattr(usage_obj, "prompt_tokens", 0) or getattr(usage_obj, "input_tokens", 0) or 0
                    out = getattr(usage_obj, "completion_tokens", 0) or getattr(usage_obj, "output_tokens", 0) or 0
                    tot = getattr(usage_obj, "total_tokens", 0) or (inp + out)
                    inp_i, out_i, tot_i = int(inp), int(out), int(tot)
                except (TypeError, ValueError):
                    return None
                if tot_i > 0:
                    return (inp_i, out_i, tot_i)
    return None


def extract_usage_from_response(response) -> Optional[UsageTuple]:
    """Extract (input, output, total) tokens from an OpenAI Responses API response object."""
    if response is None:
        return None
    usage_obj = getattr(response, "usage", None)
    if usage_obj is None:
        return None
    if isinstance(usage_obj, dict):
        return extract_usage_from_dict(usage_obj)
    try:
        inp = getattr(usage_obj, "input_tokens", 0) or getattr(usage_obj, "prompt_tokens", 0) or 0
        out = getattr(usage_obj, "output_tokens", 0) or getattr(usage_obj, "completion_tokens", 0) or 0
        tot = getattr(usage_obj, "total_tokens", 0) or (inp + out)
        inp_i, out_i, tot_i = int(inp), int(out), int(tot)
    except (TypeError, ValueError):
        return None
    if tot_i > 0:
        return (inp_i, out_i, tot_i)
    return None


def track_token_usage(
    agent_name: str,
    model_deployment_name: str,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    user_id: str = "",
    conversation_id: str = "",
) -> None:
    """Emit LLM token usage events to Application Insights.

    Emits three events:
      - LLM_Token_Usage_Summary  : overall totals per request
      - LLM_Agent_Token_Usage    : usage attributed to the agent
      - LLM_Model_Token_Usage    : usage attributed to the model deployment
    """
    if total_tokens <= 0:
        return
    try:
        track_event_if_configured("LLM_Token_Usage_Summary", {
            "total_input_tokens": str(input_tokens),
            "total_output_tokens": str(output_tokens),
            "total_tokens": str(total_tokens),
            "agent_count": "1",
            "model_count": "1",
            "user_id": user_id or "",
            "conversation_id": conversation_id or "",
        })
        track_event_if_configured("LLM_Agent_Token_Usage", {
            "agent_name": agent_name or "",
            "input_tokens": str(input_tokens),
            "output_tokens": str(output_tokens),
            "total_tokens": str(total_tokens),
            "model_deployment_name": model_deployment_name or "",
            "user_id": user_id or "",
            "conversation_id": conversation_id or "",
        })
        track_event_if_configured("LLM_Model_Token_Usage", {
            "model_deployment_name": model_deployment_name or "",
            "input_tokens": str(input_tokens),
            "output_tokens": str(output_tokens),
            "total_tokens": str(total_tokens),
            "user_id": user_id or "",
            "conversation_id": conversation_id or "",
        })
        logger.info(
            "[TOKEN USAGE] agent=%s model=%s input=%d output=%d total=%d",
            agent_name, model_deployment_name, input_tokens, output_tokens, total_tokens,
        )
    except Exception as e:
        logger.warning("Failed to emit token usage telemetry: %s", e)


class UsageAccumulator:
    """Accumulates LLM token usage across multiple model calls / streaming chunks.

    Typical use:
        usage = UsageAccumulator()
        usage.add_from_response(response)              # OpenAI Responses object
        async for chunk in agent.run(...):
            usage.add_from_update(chunk)               # agent_framework streaming update
        usage.emit(agent_name, model_deployment_name,
                   user_id=user_id, conversation_id=conversation_id)
    """

    __slots__ = ("input", "output", "total")

    def __init__(self) -> None:
        self.input = 0
        self.output = 0
        self.total = 0

    def add(self, usage: Optional[UsageTuple]) -> None:
        """Add a (input, output, total) usage tuple, ignoring None."""
        if usage:
            self.input += usage[0]
            self.output += usage[1]
            self.total += usage[2]

    def add_from_response(self, response) -> None:
        """Extract and add usage from an OpenAI Responses API response object."""
        self.add(extract_usage_from_response(response))

    def add_from_update(self, update) -> None:
        """Extract and add usage from an agent_framework streaming update."""
        self.add(extract_usage_from_update(update))

    def emit(
        self,
        agent_name: str,
        model_deployment_name: str,
        user_id: str = "",
        conversation_id: str = "",
    ) -> None:
        """Emit accumulated token usage telemetry to Application Insights."""
        track_token_usage(
            agent_name=agent_name,
            model_deployment_name=model_deployment_name,
            input_tokens=self.input,
            output_tokens=self.output,
            total_tokens=self.total,
            user_id=user_id,
            conversation_id=conversation_id,
        )
