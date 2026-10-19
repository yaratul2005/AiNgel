"""Optional Ollama adapter implemented with the Python standard library."""

from __future__ import annotations

import json
import math
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .base import Brain, Response, ToolCall

MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class OllamaError(RuntimeError):
    """An Ollama request failed or returned an invalid response."""


class OllamaBrain(Brain):
    """Call Ollama's non-streaming chat API behind the vendor-neutral brain contract."""

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        *,
        timeout: float = 30.0,
    ) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("Ollama model must be a non-empty string")
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("Ollama base_url must be a non-empty URL")
        parsed_url = urlsplit(base_url.strip())
        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ValueError("Ollama base_url must use http or https and include a host")
        if parsed_url.username is not None or parsed_url.password is not None:
            raise ValueError("Ollama base_url must not contain credentials")
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError("Ollama timeout must be a positive number of seconds")
        self.model = model.strip()
        self.base_url = base_url.strip().rstrip("/")
        self.timeout = float(timeout)

    def think(self, system: str, context: str, tools: list[dict[str, object]]) -> Response:
        """Return text and validated tool-call proposals from Ollama's chat endpoint."""
        if not isinstance(system, str) or not isinstance(context, str):
            raise TypeError("brain system and context must be strings")
        if not isinstance(tools, list):
            raise TypeError("brain tools must be a list")

        payload: dict[str, object] = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": context},
            ],
        }
        if tools:
            payload["tools"] = [self._format_tool(tool) for tool in tools]
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as result:
                raw_response = result.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            details = self._read_error_detail(error)
            hint = " Run `ollama pull <model>` if the model is not installed." if error.code == 404 else ""
            message = f"Ollama returned HTTP {error.code} for {self.base_url}/api/chat"
            if details:
                message += f": {details}"
            raise OllamaError(message + hint) from error
        except (URLError, TimeoutError, OSError) as error:
            reason = getattr(error, "reason", error)
            raise OllamaError(
                f"Could not reach Ollama at {self.base_url}: {reason}. "
                "Start the Ollama service and verify base_url."
            ) from error

        if len(raw_response) > MAX_RESPONSE_BYTES:
            raise OllamaError(
                f"Ollama response exceeded the {MAX_RESPONSE_BYTES}-byte size limit"
            )

        try:
            decoded: Any = json.loads(raw_response)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise OllamaError("Ollama returned invalid JSON; verify the server endpoint and version") from error
        return self._parse_response(decoded)

    @staticmethod
    def _format_tool(tool: dict[str, object]) -> dict[str, object]:
        """Translate Aingel's public tool spec into Ollama's function-tool shape."""
        name = tool.get("name")
        description = tool.get("description")
        parameters = tool.get("parameters", {"type": "object", "properties": {}})
        if not isinstance(name, str) or not name.strip():
            raise ValueError("tool spec name must be a non-empty string")
        if not isinstance(description, str):
            raise TypeError(f"tool spec {name!r} description must be a string")
        if not isinstance(parameters, dict) or parameters.get("type", "object") != "object":
            raise ValueError(f"tool spec {name!r} parameters must be an object schema")
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        }

    @staticmethod
    def _parse_response(data: Any) -> Response:
        """Validate the response envelope and translate proposed calls."""
        if not isinstance(data, dict):
            raise OllamaError("Ollama response must be a JSON object")
        message = data.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise OllamaError("Ollama response is missing message.content")
        raw_calls = message.get("tool_calls", [])
        if not isinstance(raw_calls, list):
            raise OllamaError("Ollama response message.tool_calls must be a list")
        calls: list[ToolCall] = []
        for index, raw_call in enumerate(raw_calls):
            if not isinstance(raw_call, dict):
                raise OllamaError(f"Ollama tool call {index} must be an object")
            function = raw_call.get("function")
            if not isinstance(function, dict):
                raise OllamaError(f"Ollama tool call {index} is missing function data")
            name = function.get("name")
            arguments = function.get("arguments", {})
            if not isinstance(name, str) or not name.strip():
                raise OllamaError(f"Ollama tool call {index} has an invalid function name")
            if not isinstance(arguments, dict) or any(
                not isinstance(key, str) for key in arguments
            ):
                raise OllamaError(f"Ollama tool call {index} arguments must be an object")
            calls.append(ToolCall(name=name, args=arguments))
        return Response(text=message["content"], tool_calls=calls)

    @staticmethod
    def _read_error_detail(error: HTTPError) -> str:
        """Extract a short server error without dumping arbitrary response bodies."""
        try:
            body = json.loads(error.read(4_096))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return ""
        detail = body.get("error") if isinstance(body, dict) else None
        if not isinstance(detail, str):
            return ""
        return " ".join(detail.split())[:300]
