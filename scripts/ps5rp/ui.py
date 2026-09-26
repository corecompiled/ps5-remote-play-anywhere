"""Result model and console rendering for ps5rp checks."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Final, NoReturn, TypeVar

_T = TypeVar("_T")


def assert_never(value: _T) -> NoReturn:
    """Exhaustiveness guard for match statements over variants."""
    raise AssertionError(f"unhandled variant: {value!r}")


class Status(str, Enum):
    """Outcome of a single check."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    INFO = "INFO"


_COLORS: Final[dict[Status, str]] = {
    Status.PASS: "\033[32m",
    Status.WARN: "\033[33m",
    Status.FAIL: "\033[31m",
    Status.INFO: "\033[36m",
}
_RESET: Final[str] = "\033[0m"


@dataclass(frozen=True, slots=True)
class Check:
    """One named result in a report."""

    label: str
    status: Status
    detail: str = ""


@dataclass(frozen=True, slots=True)
class Report:
    """An ordered set of checks plus a PASS/FAIL verdict."""

    checks: tuple[Check, ...]

    @property
    def failed(self) -> bool:
        """True when at least one check failed."""
        return any(check.status is Status.FAIL for check in self.checks)

    def counts(self) -> tuple[int, int, int]:
        """Return (passed, failed, warned)."""
        passed = sum(1 for check in self.checks if check.status is Status.PASS)
        failed = sum(1 for check in self.checks if check.status is Status.FAIL)
        warned = sum(1 for check in self.checks if check.status is Status.WARN)
        return passed, failed, warned

    def render(self) -> str:
        """Render the report as plain text with optional ANSI color."""
        color = _use_color()
        lines = [_render_check(check, color) for check in self.checks]
        passed, failed, warned = self.counts()
        verdict = "FAIL - one or more checks failed." if self.failed else "PASS - all checks ok."
        lines.append("")
        lines.append(f"Summary: {passed} passed, {failed} failed, {warned} warnings")
        lines.append(f"RESULT: {verdict}")
        return "\n".join(lines)


def _render_check(check: Check, color: bool) -> str:
    tag = f"[{check.status.value}]"
    if color:
        tag = _COLORS[check.status] + tag + _RESET
    return f"{tag} {check.label}  - {check.detail}" if check.detail else f"{tag} {check.label}"


def _use_color() -> bool:
    return not os.environ.get("NO_COLOR") and sys.stdout.isatty()
