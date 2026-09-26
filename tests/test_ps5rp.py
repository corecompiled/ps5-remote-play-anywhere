"""Tests for ps5rp.

Uses only the standard library test runner:
    python -m unittest discover -s tests

All addresses here are documentation/example values (RFC 5737 TEST-NET ranges,
CGNAT example addresses, synthetic MACs). Never commit real network values.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ps5rp.checks import RemotePath, precheck, verify  # noqa: E402
from ps5rp.cli import main  # noqa: E402
from ps5rp.config import Config, ConfigError, Topology, load_config, save_config  # noqa: E402
from ps5rp.guide import render_guide  # noqa: E402
from ps5rp.netprobe import IpClass, classify_ip  # noqa: E402
from ps5rp.wake import _magic_packet  # noqa: E402

_PUBLIC_DOC = "203.0.113.10"  # RFC 5737 TEST-NET-3
_PS5 = "192.168.1.202"
_MAC = "AA-BB-CC-DD-EE-FF"
_OVERLAY_HOST = "100.64.0.1"


class FakeProber:
    """In-memory Prober with canned answers; no network access."""

    def __init__(
        self,
        *,
        public: str | None = "198.51.100.7",  # RFC 5737 TEST-NET-2
        gateway: str | None = "192.168.1.1",
        local: str | None = "192.168.1.50",
        tcp: dict[tuple[str, int], bool] | None = None,
        ping_hosts: list[str] | None = None,
        hop: str | None = None,
        has_tailscale: bool = True,
    ) -> None:
        self._public = public
        self._gateway = gateway
        self._local = local
        self._tcp = tcp or {}
        self._ping = set(ping_hosts or [])
        self._hop = hop
        self._has_tailscale = has_tailscale
        self.sent: tuple[str, int, bytes] | None = None

    def local_ipv4(self) -> str | None:
        return self._local

    def default_gateway(self) -> str | None:
        return self._gateway

    def public_ip(self) -> str | None:
        return self._public

    def tcp_open(self, host: str, port: int, timeout: float = 2.0) -> bool:
        return self._tcp.get((host, port), False)

    def http_status(self, host: str, port: int, timeout: float = 2.0) -> int | None:
        return None

    def ping(self, host: str, timeout_ms: int = 1500) -> bool:
        return host in self._ping

    def traceroute_first_hop(self, host: str, max_hops: int = 3) -> str | None:
        return self._hop

    def has_command(self, name: str) -> bool:
        return self._has_tailscale and name == "tailscale"

    def overlay_status(self) -> str | None:
        return "ok" if self._has_tailscale else None

    def send_udp(self, host: str, port: int, payload: bytes, count: int = 3) -> None:
        self.sent = (host, port, payload)


class ClassifyIpTests(unittest.TestCase):
    def test_cgnat_boundaries(self) -> None:
        self.assertIs(classify_ip("100.64.0.1"), IpClass.CGNAT)
        self.assertIs(classify_ip("100.127.255.255"), IpClass.CGNAT)
        self.assertIs(classify_ip("100.63.255.255"), IpClass.PUBLIC)
        self.assertIs(classify_ip("100.128.0.1"), IpClass.PUBLIC)

    def test_private_ranges(self) -> None:
        for ip in ("10.0.0.1", "192.168.1.1", "172.16.0.1", "172.31.255.255", "169.254.1.1"):
            self.assertIs(classify_ip(ip), IpClass.PRIVATE, ip)

    def test_public_boundaries(self) -> None:
        for ip in ("8.8.8.8", _PUBLIC_DOC, "172.15.0.1", "172.32.0.1"):
            self.assertIs(classify_ip(ip), IpClass.PUBLIC, ip)

    def test_invalid(self) -> None:
        for ip in (None, "", "not-an-ip", "999.1.1.1", "1.2.3"):
            self.assertIs(classify_ip(ip), IpClass.INVALID, repr(ip))


class ConfigTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            save_config(Config(ps5_ip=_PS5, ps5_mac=_MAC), path)
            loaded = load_config(path)
            self.assertEqual(loaded.ps5_ip, _PS5)
            self.assertEqual(loaded.wake_ports, (987, 9302))

    def test_missing_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ConfigError):
                load_config(Path(tmp) / "nope.json")

    def test_bad_ports_raise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text(json.dumps({"wake_ports": ["x"]}), encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_non_object_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text("[1, 2]", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_bom_prefixed_file_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text('\ufeff{"ps5_ip": "192.168.1.202"}', encoding="utf-8")
            self.assertEqual(load_config(path).ps5_ip, "192.168.1.202")


class CheckTests(unittest.TestCase):
    def test_precheck_public_recommends_relay(self) -> None:
        config = Config(ps5_ip=_PS5, main_router_ip="192.168.1.1")
        prober = FakeProber(public=_PUBLIC_DOC, tcp={(_PS5, 9295): True})
        report = precheck(config, prober)
        self.assertFalse(report.failed)
        self.assertTrue(any("Path A" in check.detail for check in report.checks))

    def test_precheck_cgnat_fails(self) -> None:
        report = precheck(Config(), FakeProber(public="100.64.0.5"))
        self.assertTrue(report.failed)

    def test_verify_overlay_snat_round_trip(self) -> None:
        config = Config(ps5_ip=_PS5, overlay_host_ip=_OVERLAY_HOST, second_router_lan_ip="192.168.1.1")
        prober = FakeProber(hop=_OVERLAY_HOST, tcp={("192.168.1.1", 443): True}, ping_hosts=[_OVERLAY_HOST])
        self.assertFalse(verify(config, RemotePath.OVERLAY, prober).failed)

    def test_verify_overlay_missing_snat_fails(self) -> None:
        config = Config(overlay_host_ip=_OVERLAY_HOST, second_router_lan_ip="192.168.1.1")
        prober = FakeProber(hop=_OVERLAY_HOST, ping_hosts=[_OVERLAY_HOST])
        self.assertTrue(verify(config, RemotePath.OVERLAY, prober).failed)


class TopologyTests(unittest.TestCase):
    def test_defaults_to_single(self) -> None:
        self.assertIs(Config().topology(), Topology.SINGLE)

    def test_double_when_inner_router_set(self) -> None:
        self.assertIs(Config(second_router_lan_ip="192.168.1.1").topology(), Topology.DOUBLE)
        self.assertIs(Config(second_router_wan_ip="192.168.0.16").topology(), Topology.DOUBLE)

    def test_precheck_reports_topology(self) -> None:
        config = Config(main_router_ip="192.168.1.1", second_router_lan_ip="192.168.1.1")
        report = precheck(config, FakeProber())
        self.assertTrue(any(check.label == "Topology" and "double" in check.detail for check in report.checks))

    def test_manual_double_nat_checks_inner_router(self) -> None:
        config = Config(second_router_lan_ip="192.168.1.1", second_router_wan_ip="192.168.0.16")
        report = verify(config, RemotePath.MANUAL, FakeProber(ping_hosts=["192.168.1.1"]))
        self.assertTrue(any("double NAT" in check.label for check in report.checks))


class GuideTests(unittest.TestCase):
    def test_manual_substitutes_values(self) -> None:
        text = render_guide(Config(ps5_ip=_PS5), RemotePath.MANUAL)
        self.assertIn(_PS5, text)
        self.assertIn("9295", text)

    def test_manual_single_is_default_case(self) -> None:
        text = render_guide(Config(ps5_ip=_PS5), RemotePath.MANUAL)
        self.assertIn("default case for most homes", text)

    def test_manual_double_shows_two_hops(self) -> None:
        config = Config(ps5_ip=_PS5, second_router_lan_ip="192.168.1.1", second_router_wan_ip="192.168.0.16")
        text = render_guide(config, RemotePath.MANUAL)
        self.assertIn("Double NAT detected", text)
        self.assertIn("inner router", text)


class WakeTests(unittest.TestCase):
    def test_magic_packet_shape(self) -> None:
        packet = _magic_packet(_MAC)
        self.assertIsNotNone(packet)
        self.assertEqual(len(packet or b""), 102)
        self.assertEqual((packet or b"")[:6], b"\xff" * 6)

    def test_invalid_mac(self) -> None:
        self.assertIsNone(_magic_packet("nope"))


class CliTests(unittest.TestCase):
    def test_precheck_exit_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            save_config(Config(ps5_ip=_PS5, main_router_ip="192.168.1.1"), path)
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["precheck", "--config", str(path)], prober=FakeProber(tcp={(_PS5, 9295): True}))
            self.assertEqual(code, 0)
            self.assertIn("RESULT: PASS", buffer.getvalue())

    def test_missing_config_non_precheck_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["verify", "--config", str(Path(tmp) / "nope.json")], prober=FakeProber())
            self.assertEqual(code, 2)

    def test_malformed_config_exits_2_for_guide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text("{ not json", encoding="utf-8")
            code = main(["guide", "--config", str(path)], prober=FakeProber())
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
