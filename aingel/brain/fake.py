"""Deterministic brain for offline demonstrations and integration work."""

from collections.abc import Iterable

from .base import Response, ToolCall


class ScriptedBrain:
    """Return scripted responses in sequence without network access."""

    def __init__(self, responses: Iterable[Response]) -> None:
        self._responses = iter(responses)
        self.contexts: list[str] = []

    def think(self, system: str, context: str, tools: list[dict[str, object]]) -> Response:
        """Return the next response or an empty response when the script ends."""
        del system, tools
        self.contexts.append(context)
        try:
            return next(self._responses)
        except StopIteration:
            return Response()


def scripted_calls(*calls: ToolCall) -> ScriptedBrain:
    """Create a script with one response containing the supplied calls."""
    return ScriptedBrain([Response(tool_calls=list(calls))])
