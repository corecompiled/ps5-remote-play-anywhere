# Architecture

This document explains how each Remote Play path moves traffic, why some setups
work with no router changes and others require port forwarding, and the network
conditions that decide between them. It uses placeholders rather than any
specific installation's values.

## Core concepts

**NAT (Network Address Translation).** Your router gives your private devices
addresses (for example `192.168.1.x`) and translates them to one public address
on the internet. Outbound connections create a temporary mapping that lets the
reply come back. Inbound connections have no mapping, so they are dropped unless
you create one with port forwarding.

**Port forwarding.** A rule that maps a public port to a specific private
address and port, so an inbound connection can reach that device. It requires a
**stable private address** for the target (a DHCP reservation) and a **public
WAN IP** on the internet-facing router.

**CGNAT (Carrier-Grade NAT).** The ISP shares one public address among many
customers, so the WAN address on your router is itself private/shared - in the
`100.64.0.0/10` range (RFC 6598), sometimes a private range. Under CGNAT, **no
inbound connection can reach your home**, so port forwarding is impossible no
matter how it is configured.

**Relay.** Both endpoints connect outbound to a third-party server, which
forwards traffic between them. No inbound ports are needed, and it works behind
CGNAT. Sony operates a relay for Remote Play.

**Hole punching.** The two endpoints discover each other's public mapping
through a rendezvous server and then send packets that open a path directly
between them. It needs no port forwarding and often works behind CGNAT, but it
depends on the NAT behavior of the ISP.

**Double NAT.** Two routers in series, each performing NAT, create two layers
between a device and the internet. Every layer is a separate NAT hop that must
be handled: static addresses to pin the inner router's WAN address, and port
forwarding at every hop.

## Placeholders and local overrides

The public documents use these placeholders. Substitute your own values in your
private notes; do not commit them.

| Placeholder | Meaning |
| --- | --- |
| `<PUBLIC_IP>` | The internet-facing (WAN) address of the router closest to the internet |
| `<DDNS_HOSTNAME>` | A stable hostname that tracks a changing public IP |
| `<MAIN_ROUTER_LAN_IP>` | LAN address of the internet-facing router |
| `<SECOND_ROUTER_WAN_IP>` | WAN address of the inner router, assigned by the main router |
| `<SECOND_ROUTER_LAN_IP>` | LAN address of the inner router |
| `<PS5_IP>` | The console's static address on the innermost LAN |
| `<PS5_MAC>` | The console's MAC address |
| `<PI_IP>` | Address of the optional always-on host used for the overlay-network path |
| `<TAILNET_NAME>` | The name of the overlay network |
| `<CONTROL_PLANE_URL>` | Control-plane endpoint for the overlay network |

The example addresses in the diagrams (`192.168.1.x`, `192.168.2.x`) are
illustrative only.

## The three connection paths

### Path A - Sony relay

Used by the official PS Remote Play app, the PS Portal, and PXPlay's
"Connect via PSN" mode.

- The console and the client each connect **outbound** to Sony's Remote Play
  servers, which relay the stream between them.
- **No inbound ports and no router configuration.** Works behind CGNAT.
- Wake is pushed through the console's outbound PSN keep-alive.
- Requires PSN sign-in on both ends and NAT Type 1 or 2 on the console.

This path is the default recommendation. Start here.

### Path B - PXPlay "Connect via PSN"

- PXPlay registers with Sony, then attempts **UDP hole punching** through Sony's
  relay.
- No port forwarding. Usually works on NAT Type 2, and frequently works behind
  CGNAT depending on the ISP's NAT behavior.
- Same PSN-relay wake as Path A.

### Path C - PXPlay manual (direct)

- The client connects **directly inbound** to the console's public address.
- Requires a **public, non-CGNAT WAN IP** and port forwarding at **every** NAT
  hop between the internet and the console.
- Waking requires UDP `987` to be forwarded and the console to be registered.
- This is the only path that exposes the console's streaming ports to the
  internet. See [Security model](#security-model).

## Topology examples

### Single NAT

```
Internet
  |
  |  public WAN = <PUBLIC_IP>
  v
Router  <MAIN_ROUTER_LAN_IP>
  |
  +-- PS5 <PS5_IP>
```

Forward the streaming ports on the single router to the console's static
address. One hop, one set of rules.

### Double NAT

```
Internet
  |
  |  public WAN = <PUBLIC_IP>
  v
Main router  <MAIN_ROUTER_LAN_IP>
  |  reserving an address for the inner router's WAN
  v
Second router
  WAN = <SECOND_ROUTER_WAN_IP>   LAN = <SECOND_ROUTER_LAN_IP>
  |
  +-- PS5 <PS5_IP>
```

Two rules to satisfy:

1. Reserve the inner router's WAN address on the main router so it cannot drift.
2. Forward the streaming ports on the main router to that reserved address, and
   again on the second router to the console's static address.

The relay paths (A and B) avoid all of this because they never need inbound
access.

## Detecting CGNAT

From a device inside the network, read the public address as seen from outside
(for example `curl https://ifconfig.me`). Then classify it:

- `100.64.0.0/10` - CGNAT (RFC 6598). Port forwarding is impossible.
- `10.x`, `172.16-31.x`, `192.168.x` - private. Your ISP is also performing NAT;
  treat it as CGNAT.
- Anything else - public. Port forwarding is possible.

If the address changes over time, your ISP uses a dynamic public IP; use DDNS for
the manual path.

## Decision matrix

| Scenario | Sony relay / PS Portal | PXPlay via PSN | PXPlay manual | What to do |
| --- | --- | --- | --- | --- |
| Public IP, single NAT | Works | Works | Works | Forward the ports once on the router |
| Public IP, double NAT | Works | Works | Works | Reserve addresses and forward at both hops |
| CGNAT | Works (relay) | Usually works (hole punch) | Impossible | Do not port forward; use relay or the optional overlay network |

## Wake behavior

Wake works only from **rest mode**, never from a powered-off console. The
console must have rest-mode networking and "Enable Turning On PS5 from Network"
enabled. See the wake-by-path matrix in
[ports-and-protocols.md](ports-and-protocols.md#wake-by-path-matrix).

A rest-mode console may show no listener on `9295` and a stale neighbor entry
while still being wakeable; do not treat ARP state as a power-state test.

## Optional path: overlay network (subnet router)

For networks where the relay paths fail or are undesirable and CGNAT rules out
port forwarding, an overlay network can carry the traffic instead. This is
optional and adds a dependency, so treat it as a fallback.

An overlay network has up to three roles. Only the first is specific to this
setup; the others are the provider's to host or yours.

- **Subnet router** - an always-on host on the console's LAN (a Raspberry Pi, a
  NAS, a small server) runs the overlay client and **advertises the LAN
  subnet** into the overlay. This is the only piece you must run on your LAN.
- **Control plane** - coordinates the mesh and distributes configuration. It can
  be a managed service or self-hosted.
- **Relay** - forwards traffic between two peers that cannot establish a direct
  path, which is the CGNAT case. A relay endpoint **must be publicly
  reachable**.

The choice of provider is independent of the technology:

- A **managed overlay service** (Tailscale, NetBird, ZeroTier, and similar)
  supplies the control plane and the relay, so it works behind CGNAT with no
  VPS and nothing to host beyond the subnet router.
- A **self-hosted control plane** (for example Headscale) can run on a VPS or on
  a host on your own LAN. No VPS is required for the control plane itself.
- If you self-host **and** also need the **relay** role, that relay must live
  somewhere publicly reachable; a host behind CGNAT cannot relay for other
  CGNAT peers. You can avoid hosting a relay at all by pointing a self-hosted
  control plane at the provider's public relays.
- A **plain point-to-point tunnel with no relay** (bare WireGuard) is the one
  case that cannot cross CGNAT on its own; it needs a publicly reachable
  endpoint that both sides dial out to.

Once the pieces are in place:

- Client devices (phone, tablet, laptop) join the overlay. A client that wants
  the console reaches it through the subnet router, which forwards the traffic
  onto the LAN.
- No router port forwarding is required on your home routers.

The subnet router requires two things: the subnet route must be approved in the
control plane, and IP forwarding plus working NAT (SNAT) must be in place so
return traffic from the LAN can find its way back to the client. A host that
fails to install its NAT rules will forward wake packets (fire-and-forget) but
drop the replies that streaming depends on - the same forward-vs-return split
described above. See
[troubleshooting.md](troubleshooting.md#optional-overlay-subnet-router-failures).

## Security model

- **The relay paths open no inbound ports.** Nothing on your network is exposed
  to the internet. This is the safest configuration and the default
  recommendation.
- **The manual path exposes the console's streaming ports to the entire
  internet.** PSN sign-in limits who can use a session but does not stop port
  scanning. Prefer the relay paths when they work.
- Keep any overlay-network fallback installed and configured for untrusted
  networks such as hotels, airports, and public Wi-Fi.
- Under CGNAT, a self-hosted overlay needs a publicly reachable relay endpoint
  if hole punching fails; a managed overlay service supplies one for you. A
  plain point-to-point tunnel with no relay is the one case that cannot cross
  CGNAT without a publicly reachable endpoint.
