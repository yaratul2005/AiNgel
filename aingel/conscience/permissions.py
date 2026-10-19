"""Fail-closed permission decisions for registered tools."""

from dataclasses import dataclass
from enum import StrEnum

from ..body.tools.base import Risk, Tool, validate_arguments
from .killswitch import KillSwitch


class Verdict(StrEnum):
    """Possible conscience decisions."""

    ALLOW = "allow"
    ASK_HUMAN = "ask_human"
    DENY = "deny"


@dataclass(frozen=True)
class Decision:
    """Permission decision and human-readable reason."""

    verdict: Verdict
    reason: str


class Conscience:
    """Apply mode, declared risk, registration, and emergency-stop policy."""

    def __init__(self, mode: str, killswitch: KillSwitch | None = None) -> None:
        if mode not in {"sandbox", "supervised", "autonomous"}:
            raise ValueError(f"Unsupported conscience mode: {mode}")
        self.mode = mode
        self.killswitch = killswitch or KillSwitch()

    def check(self, tool: Tool | None, args: object = None) -> Decision:
        """Decide whether a proposed tool can run; unknown tools fail closed."""
        if self.killswitch.engaged:
            return Decision(Verdict.DENY, "kill switch is engaged")
        if tool is None:
            return Decision(Verdict.DENY, "tool is not registered")
        argument_error = validate_arguments(tool.spec.schema, {} if args is None else args)
        if argument_error:
            return Decision(Verdict.DENY, argument_error)
        if self.mode == "autonomous":
            return Decision(Verdict.DENY, "autonomous mode is not enabled in this release")
        if self.mode == "sandbox":
            if not tool.spec.sandbox_safe:
                return Decision(Verdict.DENY, "tool is not marked safe for sandbox mode")
            if tool.spec.risk is not Risk.LOW:
                return Decision(Verdict.DENY, "sandbox mode allows only low-risk tools")
            return Decision(Verdict.ALLOW, "low-risk sandbox-safe tool")
        if tool.spec.risk is Risk.LOW:
            return Decision(Verdict.ALLOW, "low-risk tool allowed in supervised mode")
        return Decision(Verdict.ASK_HUMAN, "human approval is required for this risk level")
