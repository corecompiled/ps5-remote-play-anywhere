"""Low-level, dependency-free network probes.

`SystemProber` is the real, operating-system-backed implementation used at
runtime. `Prober` is the structural interface the check layer depends on, so
tests can supply a fake without touching the network.
"""

from __future__ import annotations

import http.client
import re
import shutil
import socket
import subprocess
import sys
import urllib.request
from enum import Enum
from typing import Final, Protocol

_PUBLIC_IP_URLS: Final[tuple[str, ...]] = ("https://api.ipify.org", "https://ifconfig.me")
_IPV4_RE: Final = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")
_CGNAT_RE: Final = re.compile(r"^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.")
_PRIVATE_RE: Final = re.compile(r"^(10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.)")


class IpClass(str, Enum):
    """Classification of an IPv4 address for Remote Play purposes."""

    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"
    CGNAT = "CGNAT"
    INVALID = "INVALID"


def _is_ipv4(value: str) -> bool:
    if not _IPV4_RE.fullmatch(value):
        return False
    return all(part.isdigit() and int(part) <= 255 for part in value.split("."))


def classify_ip(ip: str | None) -> IpClass:
    """Classify an address as public, private, CGNAT, or invalid."""
    if ip is None:
        return IpClass.INVALID
    value = ip.strip()
    if not _is_ipv4(value):
        return IpClass.INVALID
    if _CGNAT_RE.match(value):
        return IpClass.CGNAT
    if _PRIVATE_RE.match(value):
        return IpClass.PRIVATE
    return IpClass.PUBLIC


class Prober(Protocol):
    """Network capabilities the check layer depends on."""

    def local_ipv4(self) -> str | None: ...

    def default_gateway(self) -> str | None: ...

    def public_ip(self) -> str | None: ...

    def tcp_open(self, host: str, port: int, timeout: float = 2.0) -> bool: ...

    def http_status(self, host: str, port: int, timeout: float = 2.0) -> int | None: ...

    def ping(self, host: str, timeout_ms: int = 1500) -> bool: ...

    def traceroute_first_hop(self, host: str, max_hops: int = 3) -> str | None: ...

    def has_command(self, name: str) -> bool: ...

    def overlay_status(self) -> str | None: ...

    def send_udp(self, host: str, port: int, payload: bytes, count: int = 3) -> None: ...


def _run(args: list[str], timeout: float) -> tuple[int, str] | None:
    try:
        completed = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return completed.returncode, completed.stdout


def _first_ipv4(text: str) -> str | None:
    match = _IPV4_RE.search(text)
    return match.group(1) if match else None


def _local_ipv4() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return None


def _default_gateway() -> str | None:
    if sys.platform.startswith("win"):
        output = _run(["ipconfig"], 5.0)
        if not output:
            return None
        for line in output[1].splitlines():
            if "Default Gateway" in line:
                candidate = _first_ipv4(line)
                if candidate:
                    return candidate
        return None
    if sys.platform == "darwin":
        output = _run(["route", "-n", "get", "default"], 5.0)
        if not output:
            return None
        for line in output[1].splitlines():
            if line.strip().startswith("gateway:"):
                return _first_ipv4(line)
        return None
    output = _run(["ip", "route", "show", "default"], 5.0)
    if output:
        tokens = output[1].split()
        if "via" in tokens:
            return tokens[tokens.index("via") + 1]
    return None


def _public_ip(timeout: float = 10.0) -> str | None:
    for url in _PUBLIC_IP_URLS:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                body = response.read().decode("utf-8", "replace")
        except OSError:
            continue
        match = _IPV4_RE.search(body)
        if match:
            return match.group(1)
    return None


def _tcp_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_status(host: str, port: int, timeout: float = 2.0) -> int | None:
    connection = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        connection.request("GET", "/")
        return connection.getresponse().status
    except (OSError, http.client.HTTPException):
        return None
    finally:
        connection.close()


def _ping(host: str, timeout_ms: int = 1500) -> bool:
    if sys.platform.startswith("win"):
        args = ["ping", "-n", "1", "-w", str(timeout_ms), host]
    else:
        args = ["ping", "-c", "1", "-W", str(max(1, timeout_ms // 1000)), host]
    result = _run(args, timeout_ms / 1000 + 2.0)
    return result is not None and result[0] == 0


def _traceroute_first_hop(host: str, max_hops: int = 3) -> str | None:
    if sys.platform.startswith("win"):
        args = ["tracert", "-d", "-h", str(max_hops), host]
    else:
        args = ["traceroute", "-n", "-m", str(max_hops), host]
    result = _run(args, 15.0)
    if result is None:
        return None
    for line in result[1].splitlines():
        if line[:1].isspace():
            candidate = _first_ipv4(line)
            if candidate:
                return candidate
    return None


def _send_udp(host: str, port: int, payload: bytes, count: int = 3) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for _ in range(count):
            sock.sendto(payload, (host, port))


class SystemProber:
    """Real Prober backed by the operating system."""

    def local_ipv4(self) -> str | None:
        return _local_ipv4()

    def default_gateway(self) -> str | None:
        return _default_gateway()

    def public_ip(self) -> str | None:
        return _public_ip()

    def tcp_open(self, host: str, port: int, timeout: float = 2.0) -> bool:
        return _tcp_open(host, port, timeout)

    def http_status(self, host: str, port: int, timeout: float = 2.0) -> int | None:
        return _http_status(host, port, timeout)

    def ping(self, host: str, timeout_ms: int = 1500) -> bool:
        return _ping(host, timeout_ms)

    def traceroute_first_hop(self, host: str, max_hops: int = 3) -> str | None:
        return _traceroute_first_hop(host, max_hops)

    def has_command(self, name: str) -> bool:
        return shutil.which(name) is not None

    def overlay_status(self) -> str | None:
        if shutil.which("tailscale") is None:
            return None
        result = _run(["tailscale", "status"], 10.0)
        return result[1] if result else None

    def send_udp(self, host: str, port: int, payload: bytes, count: int = 3) -> None:
        _send_udp(host, port, payload, count)
