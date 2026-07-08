"""Unit tests for token_usage helpers."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from token_usage import (
    UsageAccumulator,
    extract_usage_from_dict,
    extract_usage_from_response,
    extract_usage_from_update,
    track_event_if_configured,
    track_token_usage,
)


class TestExtractUsageFromDict:
    def test_openai_style_keys(self):
        assert extract_usage_from_dict(
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        ) == (10, 5, 15)

    def test_agent_framework_style_keys(self):
        assert extract_usage_from_dict(
            {"input_token_count": 7, "output_token_count": 3, "total_token_count": 10}
        ) == (7, 3, 10)

    def test_alternate_input_output_keys(self):
        assert extract_usage_from_dict(
            {"input_tokens": 4, "output_tokens": 6, "total_tokens": 10}
        ) == (4, 6, 10)

    def test_total_derived_from_input_output(self):
        # No total_tokens key -> total is inp + out
        assert extract_usage_from_dict(
            {"prompt_tokens": 2, "completion_tokens": 3}
        ) == (2, 3, 5)

    def test_zero_total_returns_none(self):
        assert extract_usage_from_dict({"prompt_tokens": 0, "completion_tokens": 0}) is None

    def test_empty_dict_returns_none(self):
        assert extract_usage_from_dict({}) is None

    def test_non_dict_returns_none(self):
        assert extract_usage_from_dict(None) is None
        assert extract_usage_from_dict("not a dict") is None

    def test_non_int_values_are_coerced(self):
        # int(MagicMock) yields 1 by default; non-coercible values fall back to None
        class Bad:
            def __int__(self):
                raise ValueError("bad")

        assert extract_usage_from_dict(
            {"prompt_tokens": Bad(), "completion_tokens": Bad(), "total_tokens": Bad()}
        ) is None


class TestExtractUsageFromResponse:
    def test_object_with_usage_attributes(self):
        usage = SimpleNamespace(input_tokens=11, output_tokens=4, total_tokens=15)
        response = SimpleNamespace(usage=usage)
        assert extract_usage_from_response(response) == (11, 4, 15)

    def test_object_with_dict_usage(self):
        response = SimpleNamespace(
            usage={"prompt_tokens": 8, "completion_tokens": 2, "total_tokens": 10}
        )
        assert extract_usage_from_response(response) == (8, 2, 10)

    def test_none_response_returns_none(self):
        assert extract_usage_from_response(None) is None

    def test_response_without_usage_returns_none(self):
        assert extract_usage_from_response(SimpleNamespace(usage=None)) is None

    def test_non_coercible_usage_returns_none(self):
        class Bad:
            def __int__(self):
                raise TypeError("bad")

        response = SimpleNamespace(
            usage=SimpleNamespace(input_tokens=Bad(), output_tokens=Bad(), total_tokens=Bad())
        )
        assert extract_usage_from_response(response) is None


class TestExtractUsageFromUpdate:
    def test_contents_usage_details(self):
        item = SimpleNamespace(
            usage_details={"input_token_count": 5, "output_token_count": 2, "total_token_count": 7}
        )
        update = SimpleNamespace(contents=[item])
        assert extract_usage_from_update(update) == (5, 2, 7)

    def test_raw_representation_usage_object(self):
        raw = SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=9, completion_tokens=1, total_tokens=10)
        )
        update = SimpleNamespace(contents=[], raw_representation=raw)
        assert extract_usage_from_update(update) == (9, 1, 10)

    def test_raw_representation_usage_dict(self):
        raw = SimpleNamespace(usage={"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7})
        update = SimpleNamespace(contents=[], raw_representation=raw)
        assert extract_usage_from_update(update) == (3, 4, 7)

    def test_no_usage_returns_none(self):
        update = SimpleNamespace(contents=[], raw_representation=None)
        assert extract_usage_from_update(update) is None


class TestTrackEventIfConfigured:
    def test_calls_track_event_when_configured(self, monkeypatch):
        monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=x")
        with patch("token_usage.track_event") as mock_track:
            track_event_if_configured("E", {"k": "v"})
            mock_track.assert_called_once_with("E", {"k": "v"})

    def test_skips_when_not_configured(self, monkeypatch):
        monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
        with patch("token_usage.track_event") as mock_track:
            track_event_if_configured("E", {"k": "v"})
            mock_track.assert_not_called()

    def test_warns_only_once_when_not_configured(self, monkeypatch):
        """Repeated calls without App Insights should warn at most once
        (subsequent calls log at DEBUG to avoid flooding logs)."""
        import token_usage

        monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
        monkeypatch.setattr(token_usage, "_app_insights_warning_emitted", False)

        with patch("token_usage.logger.warning") as mock_warning, \
             patch("token_usage.logger.debug") as mock_debug:
            track_event_if_configured("E1", {})
            track_event_if_configured("E2", {})
            track_event_if_configured("E3", {})

            assert mock_warning.call_count == 1
            assert mock_debug.call_count == 2


class TestTrackTokenUsage:
    def test_no_events_when_total_zero(self):
        with patch("token_usage.track_event_if_configured") as mock_emit:
            track_token_usage("agent", "model", 0, 0, 0)
            mock_emit.assert_not_called()

    def test_emits_three_events(self, monkeypatch):
        monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=x")
        with patch("token_usage.track_event_if_configured") as mock_emit:
            track_token_usage("agent", "model", 10, 5, 15, "u", "c")
            assert mock_emit.call_count == 3
            event_names = [call.args[0] for call in mock_emit.call_args_list]
            assert event_names == [
                "LLM_Token_Usage_Summary",
                "LLM_Agent_Token_Usage",
                "LLM_Model_Token_Usage",
            ]


class TestUsageAccumulator:
    def test_initial_state(self):
        acc = UsageAccumulator()
        assert (acc.input, acc.output, acc.total) == (0, 0, 0)

    def test_add_tuple(self):
        acc = UsageAccumulator()
        acc.add((3, 4, 7))
        acc.add((1, 2, 3))
        assert (acc.input, acc.output, acc.total) == (4, 6, 10)

    def test_add_none_is_noop(self):
        acc = UsageAccumulator()
        acc.add(None)
        assert (acc.input, acc.output, acc.total) == (0, 0, 0)

    def test_add_from_response(self):
        acc = UsageAccumulator()
        response = SimpleNamespace(
            usage=SimpleNamespace(input_tokens=2, output_tokens=3, total_tokens=5)
        )
        acc.add_from_response(response)
        assert acc.total == 5

    def test_add_from_update(self):
        acc = UsageAccumulator()
        item = SimpleNamespace(
            usage_details={"input_token_count": 1, "output_token_count": 1, "total_token_count": 2}
        )
        update = SimpleNamespace(contents=[item])
        acc.add_from_update(update)
        assert acc.total == 2

    def test_emit_delegates_to_track_token_usage(self):
        acc = UsageAccumulator()
        acc.add((10, 5, 15))
        with patch("token_usage.track_token_usage") as mock_track:
            acc.emit("agent", "model", user_id="u", conversation_id="c")
            mock_track.assert_called_once_with(
                agent_name="agent",
                model_deployment_name="model",
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                user_id="u",
                conversation_id="c",
            )

    def test_emit_with_zero_does_not_track(self):
        acc = UsageAccumulator()
        with patch("token_usage.track_event_if_configured") as mock_emit:
            acc.emit("agent", "model")
            mock_emit.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
