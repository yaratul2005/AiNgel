"""Read UTF-8 files from an explicitly configured workspace directory."""

from __future__ import annotations

from pathlib import Path

from .base import Risk, ToolSpec


class WorkspaceReadTool:
    """Read small files beneath a configured root without writing to disk.

    This tool enforces a path boundary in the Python process. It is not an OS
    sandbox and should only be given a workspace the operator intends to expose.
    """

    def __init__(self, root: Path, *, max_bytes: int = 65_536) -> None:
        if max_bytes < 1:
            raise ValueError("max_bytes must be positive")
        resolved_root = root.expanduser().resolve(strict=True)
        if not resolved_root.is_dir():
            raise ValueError("workspace root must be a directory")
        self.root = resolved_root
        self.max_bytes = max_bytes
        self.spec = ToolSpec(
            name="workspace_read",
            description="Read a UTF-8 text file from the configured workspace.",
            risk=Risk.LOW,
            sandbox_safe=False,
            schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        )

    def run(self, **args: object) -> str:
        """Read a relative file path, returning a concise error on failure."""
        if set(args) != {"path"}:
            return "read error: expected only the path argument"
        relative = args.get("path")
        if not isinstance(relative, str) or not relative.strip():
            return "read error: path must be a non-empty relative string"

        requested = Path(relative)
        if requested.is_absolute() or ".." in requested.parts:
            return "read error: path must stay inside the configured workspace"

        try:
            candidate = (self.root / requested).resolve(strict=True)
            candidate.relative_to(self.root)
        except (OSError, ValueError):
            return "read error: file is missing or outside the configured workspace"

        try:
            if not candidate.is_file():
                return "read error: path is not a regular file"
            with candidate.open("rb") as file:
                content = file.read(self.max_bytes + 1)
        except OSError:
            return "read error: file could not be opened"

        if len(content) > self.max_bytes:
            return f"read error: file exceeds the {self.max_bytes}-byte limit"
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return "read error: file is not valid UTF-8 text"
