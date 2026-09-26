# Setup Guide

Step-by-step setup for each path. Start with the relay path; only continue to
port forwarding if the relay path fails and your connection is not CGNAT.
Placeholders are defined in
[architecture.md](architecture.md#placeholders-and-local-overrides).

## Before you start

1. **Determine whether your connection is public or CGNAT.** From a device on
   the network, read the public address as seen from outside
   (`curl https://ifconfig.me`) and classify it per
   [Detecting CGNAT](architecture.md#detecting-cgnat). Write the result down; it
   decides whether port forwarding is even possible.
2. **Confirm the console's NAT type** is 1 or 2 (below). Type 3 breaks every
   path.
3. **Decide which client you are configuring**: the official PS Remote Play app,
   PS Portal, or PXPlay. The relay path covers all three.

## Step 1: Configure the console

These settings are required for every path.

- `Settings -> System -> Remote Play -> Enable Remote Play` - on, for the
  account that owns the games.
- `Settings -> System -> Power Saving -> Features Available in Rest Mode`:
  - **Stay Connected to the Internet** - on.
  - **Enable Turning On PS5 from Network** - on.
- `Settings -> Network -> Connection Status -> View Connection Status` - **NAT
  Type must be 1 or 2**.
- Prefer a **wired Ethernet** connection for stability and lower latency.

Wake works only from **rest mode**. A powered-off console cannot be woken by any
network path.

## Step 2: Choose a path

| If ... | Use |
| --- | --- |
| You want the simplest setup | Path A - Sony relay |
| Relay fails and your WAN IP is public | Path B - manual port forwarding |
| Relay fails and you are behind CGNAT | Path C - optional overlay network (subnet router) |

## Path A - Sony relay (recommended, no router changes)

This path needs no port forwarding and works behind CGNAT.

1. **Register the console** once, on the same network as the console. In the
   client, choose to link a console and enter the 8-digit code shown at
   `Settings -> System -> Remote Play -> Link Device` on the console, then sign
   in with PSN. Registration is what enables wake-from-rest; an entry created by
   raw IP address alone cannot wake the console.
2. **Sign in with PSN** on both the console and the client.
3. **Connect**:
   - Official PS Remote Play app: sign in and connect to the registered console.
   - PS Portal: sign in and connect.
   - PXPlay: choose "Connect via PSN".
4. **Test** (see [Testing](#testing)).

That is the whole setup for the relay path.

## Path B - manual port forwarding

Only use this path if your WAN IP is public. It is impossible under CGNAT.

### B1 - Give the console a stable address

Create a **DHCP reservation** on the router for the console's MAC address
(`<PS5_MAC>`) so it always receives `<PS5_IP>`. A forward rule that points at a
dynamically-assigned address will silently break when the lease changes.

### B2 - Forward the ports (single NAT)

On the internet-facing router, create forwarding rules to `<PS5_IP>`:

| Port | Protocol |
| --- | --- |
| 9295 | TCP |
| 9295 | UDP |
| 9296 | UDP |
| 9297 | UDP |
| 987 | UDP |

`987/UDP` is the wake port for the manual path. `9302/UDP` is sometimes listed
as a wake port; if you use it, forward it as well. See
[ports-and-protocols.md](ports-and-protocols.md#port-table).

### B3 - Double NAT: add the outer hop

With two routers in series, forward at **both** hops and pin the addresses:

1. On the **main (internet-facing) router**, reserve an address for the **inner
   router's WAN** address (`<SECOND_ROUTER_WAN_IP>`) so it cannot drift.
2. On the **main router**, forward the same ports to `<SECOND_ROUTER_WAN_IP>`.
3. On the **inner router**, forward the same ports to `<PS5_IP>` (B2).

Some routers do not support NAT loopback (hairpin connections), so a test from
inside the network against the public address may fail even when the rules are
correct. Always test the port-forward path from a genuinely external network.

### B4 - Optional: DDNS for a changing public IP

If your public IP is dynamic, a DDNS hostname keeps the manual target stable.

1. Create a hostname with a DDNS provider.
2. Configure DDNS on the main router (provider, hostname, credentials), on the
   WAN interface that carries the public address.
3. Confirm the DDNS status shows a successful update.
4. In PXPlay manual mode, use `<DDNS_HOSTNAME>` instead of `<PUBLIC_IP>`.

This affects the manual path only; the relay paths do not need it.

### B5 - Register the console (required for wake)

Even in manual mode, waking the console requires the one-time registration from
Path A, step 1. Registration stores the key the console uses to accept a wake.

### B6 - Configure PXPlay manual mode

1. Enter the target address: `<PUBLIC_IP>` (or `<DDNS_HOSTNAME>`).
2. Start at a conservative quality (720p/60 or 1080p/60) and increase only if
   the measured upload speed supports it (about 5 Mbps minimum, 15 Mbps
   recommended).

## Path C: optional overlay network (subnet router)

Use this when the relay paths fail and CGNAT prevents port forwarding. It needs
one always-on host on the console's LAN; no router port forwarding is required.
For the roles involved and the provider choices, see
[the optional path in architecture.md](architecture.md#optional-path-overlay-network-subnet-router).

1. **Choose an overlay network.** A managed service (Tailscale, NetBird, and
   similar) supplies the control plane and relay for you and is the simplest
   option. A self-hosted control plane (for example Headscale) can run on a VPS
   or a host on your LAN; if you self-host and also need the relay role, that
   relay must be publicly reachable, or point the control plane at the
   provider's public relays.
2. **Install the overlay client** on the always-on host and join it to
   `<TAILNET_NAME>` (`<CONTROL_PLANE_URL>` for a self-hosted control plane).
3. **Advertise the LAN subnet.** Configure the host to advertise the console's
   subnet (for example `192.168.2.0/24`), and **approve the subnet route** in
   the control plane.
4. **Enable forwarding and NAT on the host.** IP forwarding must be on, and the
   host must apply NAT (SNAT) to traffic it forwards, so replies from the LAN
   can return to the client. Confirm the forwarding rules are actually installed
   after startup.
5. **Join client devices** to the same overlay.
6. **Connect** the client to the console's LAN address (`<PS5_IP>`), or use
   PXPlay manual mode with that address.

If the console wakes but the stream fails, the host's NAT rules are the first
thing to check - see
[troubleshooting.md](troubleshooting.md#optional-overlay-subnet-router-failures).

## Testing

Run tests in this order:

1. **Same-network sanity check.** From a device on the same network, connect
   with each client to confirm pairing and sign-in work.
2. **External test.** From a genuinely different network (mobile hotspot or a
   friend's Wi-Fi), connect. A second device inside your own home does not
   simulate this.
3. **Port-forward check (manual path only).** With the console booted, test TCP
   `9295` on `<PUBLIC_IP>` from outside. A public port checker that reports the
   port as open confirms the forward chain. UDP ports and wake cannot be proven
   this way; the definitive wake test is a manual-mode wake from outside.

Prerequisite for the wake tests: the console must be in **rest mode** and
**registered**.

## Rollback

To remove the manual path, delete the forwarding rules on each hop and the
optional DDNS configuration. The console's DHCP reservation can stay. The relay
paths are unaffected and remain available.
