"""Typed errors for ps5rp.

Each error carries typed fields rather than a bare message string, so a caller
can react to the specific failure instead of parsing prose.
"""

from __future__ import annotations


class Ps5rpError(Exception):
    """Base class for every error raised by ps5rp."""


class ConfigError(Ps5rpError):
    """The local configuration is missing, unreadable, or malformed."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ProbeError(Ps5rpError):
    """A network probe could not be completed as requested."""

    def __init__(self, probe: str, detail: str) -> None:
        super().__init__(f"{probe}: {detail}")
        self.probe = probe
        self.detail = detail
