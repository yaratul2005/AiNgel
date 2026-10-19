import io
import json
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest

from aingel.brain.base import ToolCall
from aingel.brain.ollama import OllamaBrain, OllamaError


def test_ollama_request_maps_tool_specs_and_parses_tool_calls() -> None:
    body = {
        "message": {
            "role": "assistant",
            "content": "I will inspect the note.",
            "tool_calls": [
                {"function": {"name": "workspace_read", "arguments": {"path": "note.txt"}}}
            ],
        },
        "done": True,
    }
    response = io.BytesIO(json.dumps(body).encode())
    tools = [
        {
            "name": "workspace_read",
            "description": "Read a workspace file",
            "risk": "low",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        }
    ]

    with patch("aingel.brain.ollama.urlopen", return_value=response) as open_url:
        result = OllamaBrain("llama3.2", timeout=12).think(
            "system prompt", "task context", tools
        )

    request = open_url.call_args.args[0]
    payload = json.loads(request.data)
    assert request.full_url == "http://localhost:11434/api/chat"
    assert open_url.call_args.kwargs["timeout"] == 12
    assert payload["stream"] is False
    assert payload["messages"] == [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "task context"},
    ]
    assert payload["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "workspace_read",
                "description": "Read a workspace file",
                "parameters": tools[0]["parameters"],
            },
        }
    ]
    assert result.text == "I will inspect the note."
    assert result.tool_calls == [ToolCall("workspace_read", {"path": "note.txt"})]


def test_ollama_omits_tools_when_none_are_registered() -> None:
    response = io.BytesIO(b'{"message":{"content":"ready"}}')
    with patch("aingel.brain.ollama.urlopen", return_value=response) as open_url:
        result = OllamaBrain("llama3.2").think("system", "context", [])

    assert "tools" not in json.loads(open_url.call_args.args[0].data)
    assert result.text == "ready"


def test_ollama_connection_failure_has_actionable_hint() -> None:
    with (
        patch("aingel.brain.ollama.urlopen", side_effect=URLError("connection refused")),
        pytest.raises(OllamaError, match="Start the Ollama service"),
    ):
        OllamaBrain("llama3.2").think("system", "context", [])


def test_ollama_missing_model_error_suggests_pull_command() -> None:
    error = HTTPError(
        "http://localhost:11434/api/chat",
        404,
        "Not Found",
        {},
        io.BytesIO(b'{"error":"model not found"}'),
    )
    with (
        patch("aingel.brain.ollama.urlopen", side_effect=error),
        pytest.raises(OllamaError, match="ollama pull <model>"),
    ):
        OllamaBrain("missing-model").think("system", "context", [])


@pytest.mark.parametrize(
    "response_body",
    [b"not json", b"{}", b'{"message":{"content":"ok","tool_calls":[{}]}}'],
)
def test_ollama_invalid_responses_fail_clearly(response_body: bytes) -> None:
    with (
        patch("aingel.brain.ollama.urlopen", return_value=io.BytesIO(response_body)),
        pytest.raises(OllamaError),
    ):
        OllamaBrain("llama3.2").think("system", "context", [])


def test_ollama_oversized_response_is_rejected() -> None:
    from aingel.brain.ollama import MAX_RESPONSE_BYTES

    response = io.BytesIO(b" " * (MAX_RESPONSE_BYTES + 1))
    with (
        patch("aingel.brain.ollama.urlopen", return_value=response),
        pytest.raises(OllamaError, match="size limit"),
    ):
        OllamaBrain("llama3.2").think("system", "context", [])


@pytest.mark.parametrize(
    ("model", "base_url", "timeout"),
    [
        ("", "http://localhost:11434", 30),
        ("model", "file:///tmp/ollama", 30),
        ("model", "http://localhost", 0),
        ("model", "http://localhost", float("inf")),
    ],
)
def test_ollama_configuration_is_validated(model: str, base_url: str, timeout: float) -> None:
    with pytest.raises(ValueError):
        OllamaBrain(model, base_url, timeout=timeout)
