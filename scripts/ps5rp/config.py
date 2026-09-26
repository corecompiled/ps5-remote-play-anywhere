"""Local configuration: load, save, and interactively build.

The configuration holds non-secret values only - addresses and names. No
credentials are ever stored here; anything behind a login (routers, console
menus, overlay services) is a manual step the tool prints rather than performs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Final, Mapping, TypeAlias

from .errors import ConfigError

_JsonValue: TypeAlias = str | int | float | bool | None | list[int]

_DEFAULT_WAKE_PORTS: Final[tuple[int, ...]] = (987, 9302)
_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH: Final[Path] = _REPO_ROOT / ".ps5rp" / "config.json"

_STR_FIELDS: Final[tuple[str, ...]] = (
    "public_ip",
    "ddns_hostname",
    "main_router_ip",
    "second_router_wan_ip",
    "second_router_lan_ip",
    "ps5_ip",
    "ps5_mac",
    "overlay_host_ip",
    "tailnet_name",
    "control_plane_url",
)

_PROMPTS: Final[tuple[tuple[str, str], ...]] = (
    ("public_ip", "Public IP (blank to auto-detect)"),
    ("ddns_hostname", "DDNS hostname (optional)"),
    ("main_router_ip", "Internet-facing router LAN IP"),
    ("second_router_wan_ip", "Inner router WAN IP (blank if single NAT)"),
    ("second_router_lan_ip", "Inner router LAN IP"),
    ("ps5_ip", "PS5 static LAN IP"),
    ("ps5_mac", "PS5 MAC address (optional)"),
    ("overlay_host_ip", "Overlay subnet-router host IP (optional)"),
    ("tailnet_name", "Overlay network name (optional)"),
    ("control_plane_url", "Overlay control-plane URL (optional)"),
)


class Topology(str, Enum):
    """Whether one or two NAT hops sit between the console and the internet."""

    SINGLE = "single"
    DOUBLE = "double"


@dataclass(frozen=True, slots=True)
class Config:
    """User-supplied network values. All optional; empty means unknown."""

    public_ip: str = ""
    ddns_hostname: str = ""
    main_router_ip: str = ""
    second_router_wan_ip: str = ""
    second_router_lan_ip: str = ""
    ps5_ip: str = ""
    ps5_mac: str = ""
    overlay_host_ip: str = ""
    tailnet_name: str = ""
    control_plane_url: str = ""
    wake_ports: tuple[int, ...] = _DEFAULT_WAKE_PORTS

    def has_values(self) -> bool:
        """True when at least one address was supplied."""
        return any(getattr(self, field) for field in _STR_FIELDS)

    def topology(self) -> Topology:
        """Double NAT when an inner router is configured; single otherwise."""
        if self.second_router_lan_ip or self.second_router_wan_ip:
            return Topology.DOUBLE
        return Topology.SINGLE


def _as_str(raw: Mapping[str, _JsonValue], key: str) -> str:
    value = raw.get(key)
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    raise ConfigError(f"field {key!r} must be a string")


def _as_ports(raw: Mapping[str, _JsonValue]) -> tuple[int, ...]:
    value = raw.get("wake_ports")
    if value is None:
        return _DEFAULT_WAKE_PORTS
    if isinstance(value, list) and all(isinstance(item, int) and not isinstance(item, bool) for item in value):
        return tuple(value)
    raise ConfigError("field 'wake_ports' must be a list of integers")


def _parse_config(raw: Mapping[str, _JsonValue]) -> Config:
    values = {field: _as_str(raw, field) for field in _STR_FIELDS}
    return Config(**values, wake_ports=_as_ports(raw))


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    """Load and parse the config file, or raise ConfigError."""
    if not path.exists():
        raise ConfigError(f"no config at {path} - run 'ps5rp init' first")
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must contain a JSON object")
    return _parse_config(raw)


def save_config(config: Config, path: Path = DEFAULT_CONFIG_PATH) -> None:
    """Write the config as indented JSON, creating parent directories."""
    payload: dict[str, _JsonValue] = {field: getattr(config, field) for field in _STR_FIELDS}
    payload["wake_ports"] = list(config.wake_ports)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot write {path}: {exc}") from exc


def prompt_config(existing: Config, ask: Callable[[str], str]) -> Config:
    """Interactively build a config, keeping current values as defaults."""
    current: dict[str, str] = {field: getattr(existing, field) for field in _STR_FIELDS}
    for key, label in _PROMPTS:
        shown = current[key]
        suffix = f" [{shown}]" if shown else ""
        answer = ask(f"{label}{suffix}: ").strip()
        current[key] = answer or shown
    return Config(**current, wake_ports=existing.wake_ports)
