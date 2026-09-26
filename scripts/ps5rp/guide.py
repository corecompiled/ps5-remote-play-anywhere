"""Manual instructions the tool prints instead of performing.

Everything behind a login - router admin pages, console menus, overlay sign-in -
is a manual step, rendered here with the user's values substituted where known.
"""

from __future__ import annotations

from .checks import RemotePath
from .config import Config, Topology
from .ui import assert_never


def _val(value: str, placeholder: str) -> str:
    return value or placeholder


def render_guide(config: Config, path: RemotePath) -> str:
    """Render the manual steps for a path (or all paths)."""
    match path:
        case RemotePath.RELAY:
            return _relay()
        case RemotePath.MANUAL:
            return _manual(config)
        case RemotePath.OVERLAY:
            return _overlay(config)
        case RemotePath.ALL:
            return "\n\n".join((_relay(), _manual(config), _overlay(config)))
        case unreachable:
            assert_never(unreachable)


def _relay() -> str:
    return (
        "Path A - Sony relay (recommended, no router changes)\n"
        "\n"
        "1. On the PS5, enable Remote Play and rest-mode networking:\n"
        "     Settings > System > Remote Play > Enable Remote Play           = ON\n"
        "     Settings > System > Power Saving > Features Available in Rest Mode:\n"
        "       Stay Connected to the Internet                                = ON\n"
        "       Enable Turning On PS5 from Network                            = ON\n"
        "2. Register the console once, on the same network:\n"
        "     PS5:    Settings > System > Remote Play > Link Device  -> 8-digit code\n"
        "     Client: choose to link a console, enter the code, sign in with PSN.\n"
        "3. Connect from outside with the official Remote Play app, PS Portal, or\n"
        "   PXPlay's 'Connect via PSN' mode.\n"
        "4. Verify from a genuinely external network (mobile hotspot or a friend's\n"
        "   Wi-Fi).\n"
        "\n"
        "Wake works only from rest mode; a powered-off console cannot be woken."
    )


def _manual(config: Config) -> str:
    ps5 = _val(config.ps5_ip, "<PS5_IP>")
    mac = _val(config.ps5_mac, "<PS5_MAC>")
    wan = _val(config.second_router_wan_ip, "<SECOND_ROUTER_WAN_IP>")
    public = _val(config.ddns_hostname or config.public_ip, "<PUBLIC_IP or DDNS hostname>")
    header = (
        "Path B - PXPlay manual (port forwarding, public WAN IP required)\n"
        "\n"
        "Only possible with a public, non-CGNAT WAN IP.\n"
    )
    match config.topology():
        case Topology.SINGLE:
            body = (
                "\n"
                f"1. Reserve the console's address on the router for MAC {mac} -> {ps5}.\n"
                f"2. Forward these ports to {ps5}:\n"
                "     9295 TCP, 9295 UDP, 9296 UDP, 9297 UDP, 987 UDP (wake)\n"
                "3. Register the console as in Path A (registration is required for wake).\n"
                "4. Optional DDNS if the public IP changes; then use the hostname below.\n"
                f"5. Point PXPlay manual mode at {public}.\n"
                "6. Verify from a genuinely external network.\n"
                "\n"
                "This is the default case for most homes: one router, one hop. If a\n"
                "second router sits in front of the console, add its addresses via\n"
                "'ps5rp init' and this becomes the two-hop version.\n"
            )
        case Topology.DOUBLE:
            body = (
                "\n"
                f"1. On the inner router, reserve the console's address (MAC {mac}) -> {ps5}.\n"
                f"2. On the inner router, forward these ports to {ps5}:\n"
                "     9295 TCP, 9295 UDP, 9296 UDP, 9297 UDP, 987 UDP (wake)\n"
                f"3. On the main router, reserve the inner router's WAN address ({wan})\n"
                "   and forward the same ports to it.\n"
                "4. Register the console as in Path A (registration is required for wake).\n"
                "5. Optional DDNS if the public IP changes; then use the hostname below.\n"
                f"6. Point PXPlay manual mode at {public}.\n"
                "7. Verify from a genuinely external network.\n"
                "\n"
                "Double NAT detected (inner router configured): both hops must be\n"
                "forwarded. One missing hop wakes nothing from outside.\n"
            )
        case unreachable:
            assert_never(unreachable)
    return header + body + "\nThis is the only path that exposes the console's ports to the internet."


def _overlay(config: Config) -> str:
    host = _val(config.overlay_host_ip, "<PI_IP>")
    tailnet = _val(config.tailnet_name, "<TAILNET_NAME>")
    ps5 = _val(config.ps5_ip, "<PS5_IP>")
    return (
        "Path C - optional overlay network (subnet router)\n"
        "\n"
        "1. Choose an overlay: a managed service (Tailscale, NetBird, ZeroTier) or\n"
        "   a self-hosted control plane. If you self-host and need the relay role,\n"
        "   that relay must be publicly reachable.\n"
        f"2. Install the overlay client on an always-on LAN host ({host}).\n"
        f"3. Advertise the console's LAN subnet and approve the route ({tailnet}).\n"
        "4. Enable IP forwarding and NAT (SNAT) on the host so replies return.\n"
        f"5. Join client devices to the overlay and connect to {ps5}.\n"
        "\n"
        "If the console wakes but the stream fails, check the host's SNAT rules\n"
        "first (see docs/troubleshooting.md)."
    )
