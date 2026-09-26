"""Experimental, best-effort wake.

The reliable wake is the client app / PSN relay. This sends a standard
Wake-on-LAN magic packet to the console's UDP wake ports using its MAC address.
It is not guaranteed to work on every console and is offered for
experimentation only - it is never presented as a supported method.
"""

from __future__ import annotations

from .config import Config
from .netprobe import Prober
from .ui import Check, Status

_MAC_LENGTH: int = 12


def _magic_packet(mac: str) -> bytes | None:
    cleaned = mac.replace(":", "").replace("-", "").replace(".", "")
    if len(cleaned) != _MAC_LENGTH:
        return None
    try:
        octets = bytes.fromhex(cleaned)
    except ValueError:
        return None
    return b"\xff" * 6 + octets * 16


def wake(config: Config, target_host: str, prober: Prober) -> list[Check]:
    """Send a best-effort wake packet to a target host."""
    checks: list[Check] = [
        Check("Wake method", Status.INFO, "experimental WoL magic packet; the reliable wake is the app/PSN relay")
    ]
    if not config.ps5_mac:
        checks.append(Check("Console MAC", Status.WARN, "set ps5_mac via 'ps5rp init'"))
        return checks
    packet = _magic_packet(config.ps5_mac)
    if packet is None:
        checks.append(Check("Console MAC", Status.FAIL, f"'{config.ps5_mac}' is not a valid MAC address"))
        return checks
    sent: list[int] = []
    for port in config.wake_ports:
        try:
            prober.send_udp(target_host, port, packet)
        except OSError as exc:
            checks.append(Check(f"Wake packet to UDP {port}", Status.FAIL, str(exc)))
            continue
        sent.append(port)
    if sent:
        ports = ", ".join(str(port) for port in sent)
        checks.append(Check("Wake packets sent", Status.INFO, f"UDP {ports} to {target_host} (unverified - watch the console)"))
    return checks
