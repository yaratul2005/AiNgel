"""In-process and file-backed emergency stop."""

from pathlib import Path


class KillSwitch:
    """Stop actions when explicitly engaged or when its flag file exists."""

    def __init__(self, flag_path: Path | None = None) -> None:
        self.flag_path = flag_path
        self._engaged = False

    @property
    def engaged(self) -> bool:
        """Whether the in-process switch or configured flag file is active."""
        return self._engaged or (self.flag_path is not None and self.flag_path.exists())

    def engage(self) -> None:
        """Engage the in-process emergency stop."""
        self._engaged = True

    def reset(self) -> None:
        """Reset the in-process switch; a present flag file remains active."""
        self._engaged = False
