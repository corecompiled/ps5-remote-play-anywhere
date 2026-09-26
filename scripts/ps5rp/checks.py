"""Check suites: precheck (which path is viable) and verify (per path).

All checks depend only on the `Prober` interface, so they run against a fake in
tests and against the operating system at runtime.
"""

from __future__ import annotations

from enum import Enum

from .config import Config, Topology
from .netprobe import IpClass, Prober, classify_ip
from .ui import Check, Report, Status, assert_never


class RemotePath(str, Enum):
    """The connection paths that can be verified."""

    RELAY = "relay"
    MANUAL = "manual"
    OVERLAY = "overlay"
    ALL = "all"


def _public_ip_checks(config: Config, prober: Prober) -> list[Check]:
    public = prober.public_ip()
    checks: list[Check] = []
    match classify_ip(public):
        case IpClass.PUBLIC:
            checks.append(Check("Public IP is public (no CGNAT)", Status.PASS, public or ""))
        case IpClass.CGNAT:
            checks.append(Check("Public IP classification", Status.FAIL, f"{public} is CGNAT - port forwarding is impossible"))
        case IpClass.PRIVATE:
            checks.append(Check("Public IP classification", Status.FAIL, f"{public} is private - ISP-level NAT"))
        case IpClass.INVALID:
            checks.append(Check("Public IP lookup", Status.FAIL, "could not reach a public IP service"))
        case unreachable:
            assert_never(unreachable)
    if public and config.public_ip and public != config.public_ip:
        checks.append(Check("Public IP unchanged since config", Status.WARN, f"config has {config.public_ip}, now {public}"))
    return checks


def _local_context_check(config: Config, prober: Prober) -> Check:
    local = prober.local_ipv4()
    gateway = prober.default_gateway()
    known = {config.main_router_ip, config.second_router_lan_ip} - {""}
    on_home = gateway is not None and gateway in known
    detail = f"this machine = {local or '?'}, gateway = {gateway or '?'}"
    if not known:
        return Check("Local network context", Status.INFO, f"{detail} (set router IPs via 'ps5rp init')")
    return Check("On the home LAN", Status.PASS if on_home else Status.WARN, detail)


def _ps5_listener_check(config: Config, prober: Prober) -> Check:
    if not config.ps5_ip:
        return Check("PS5 streaming listener (TCP 9295)", Status.INFO, "set ps5_ip via 'ps5rp init'")
    if prober.tcp_open(config.ps5_ip, 9295):
        return Check("PS5 streaming listener (TCP 9295)", Status.PASS, "console booted - remote play ready")
    return Check("PS5 streaming listener (TCP 9295)", Status.WARN, "closed - console in rest/off, or not reachable")


def _topology_check(config: Config) -> Check:
    match config.topology():
        case Topology.SINGLE:
            return Check("Topology", Status.INFO, "single router (default) - forward the ports on one router")
        case Topology.DOUBLE:
            return Check("Topology", Status.INFO, "double NAT - reserve the inner router WAN and forward at both hops")
        case unreachable:
            assert_never(unreachable)


def precheck(config: Config, prober: Prober) -> Report:
    """Discover the environment and recommend a path."""
    checks: list[Check] = [_local_context_check(config, prober)]
    checks.extend(_public_ip_checks(config, prober))
    if not config.has_values():
        checks.append(Check("Local configuration", Status.WARN, "no values set - run 'ps5rp init' for tailored instructions"))
    else:
        checks.append(_topology_check(config))
    checks.append(_ps5_listener_check(config, prober))

    public = classify_ip(prober.public_ip())
    match public:
        case IpClass.CGNAT | IpClass.PRIVATE:
            recommendation = "Path A (Sony relay) works; Path C (overlay) if not enough. Port forwarding is impossible."
        case IpClass.PUBLIC:
            recommendation = "Path A (Sony relay) recommended. Path B (port forwarding) is possible if you want manual mode."
        case IpClass.INVALID:
            recommendation = "Could not classify the connection - check internet access, then re-run."
        case unreachable:
            assert_never(unreachable)
    checks.append(Check("Recommended path", Status.INFO, recommendation))
    return Report(tuple(checks))


def _manual_checks(config: Config, prober: Prober) -> list[Check]:
    checks: list[Check] = []
    if config.main_router_ip:
        reachable = prober.tcp_open(config.main_router_ip, 443) or prober.ping(config.main_router_ip)
        checks.append(Check("Internet-facing router reachable", Status.PASS if reachable else Status.WARN, config.main_router_ip))
    match config.topology():
        case Topology.DOUBLE:
            inner = config.second_router_lan_ip
            if inner:
                reachable = prober.tcp_open(inner, 443) or prober.ping(inner)
                checks.append(Check("Inner router reachable (double NAT)", Status.PASS if reachable else Status.WARN, f"{inner} - forward the same ports here too"))
        case Topology.SINGLE:
            checks.append(Check("Topology", Status.INFO, "single router - one forwarding hop"))
        case unreachable:
            assert_never(unreachable)
    checks.append(_ps5_listener_check(config, prober))
    checks.append(Check("External TCP 9295 proof", Status.INFO, "cannot be automated from home - use a public port checker while the console is booted"))
    return checks


def _relay_checks(config: Config, prober: Prober) -> list[Check]:
    checks: list[Check] = [_ps5_listener_check(config, prober)]
    checks.append(Check("Sony relay session", Status.INFO, "cannot be tested from the LAN - run an external session test (mobile hotspot)"))
    return checks


def _overlay_checks(config: Config, prober: Prober) -> list[Check]:
    checks: list[Check] = []
    if prober.has_command("tailscale"):
        checks.append(Check("Overlay client present (tailscale)", Status.PASS, "found on PATH"))
    else:
        checks.append(Check("Overlay client present (tailscale)", Status.WARN, "not found - if you use another overlay, verify manually"))
    if not config.overlay_host_ip:
        checks.append(Check("Overlay subnet router", Status.INFO, "set overlay_host_ip via 'ps5rp init'"))
        return checks
    reachable = prober.ping(config.overlay_host_ip)
    checks.append(Check("Overlay host reachable", Status.PASS if reachable else Status.FAIL, config.overlay_host_ip))
    if config.second_router_lan_ip:
        hop = prober.traceroute_first_hop(config.second_router_lan_ip)
        routed = hop == config.overlay_host_ip
        checks.append(Check("LAN subnet routed via overlay", Status.PASS if routed else Status.WARN, f"first hop = {hop or '?'}, expected {config.overlay_host_ip}"))
        round_trip = prober.tcp_open(config.second_router_lan_ip, 443)
        checks.append(Check("SNAT round-trip through overlay", Status.PASS if round_trip else Status.FAIL, "TCP 443 on the inner router answers through the tunnel" if round_trip else "forwarded round-trip failed - SNAT likely missing on the subnet router"))
    return checks


def verify(config: Config, path: RemotePath, prober: Prober) -> Report:
    """Run the checks for one path (or all paths)."""
    checks: list[Check] = []
    match path:
        case RemotePath.MANUAL:
            checks.extend(_manual_checks(config, prober))
        case RemotePath.RELAY:
            checks.extend(_relay_checks(config, prober))
        case RemotePath.OVERLAY:
            checks.extend(_overlay_checks(config, prober))
        case RemotePath.ALL:
            checks.extend(_relay_checks(config, prober))
            checks.extend(_manual_checks(config, prober))
            checks.extend(_overlay_checks(config, prober))
        case unreachable:
            assert_never(unreachable)
    return Report(tuple(checks))
