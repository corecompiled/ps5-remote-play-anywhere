# Troubleshooting

Diagnosis is fastest when you separate the network path into a **forward path**
(the packet from client to console) and a **return path** (the reply from console
to client). Many Remote Play failures are a working forward path with a broken
return path. See [ports-and-protocols.md](ports-and-protocols.md).

## First checks

- Console NAT Type is 1 or 2 (Type 3 breaks every path).
- Remote Play is enabled for the correct account.
- Rest-mode networking and "Enable Turning On PS5 from Network" are on.
- The console is **registered** (required for wake) and, for wake, in **rest
  mode**.
- You are testing from a **genuinely external network**, not a second device on
  the same home network.

## Symptom table

| Symptom | Likely cause | Where to look |
| --- | --- | --- |
| Works at home, fails away | Using manual mode without forwarding, or CGNAT | [Manual path failures](#manual-path-failures) |
| Relay path works, manual path does not | Missing or misordered port forwarding at a NAT hop | [Manual path failures](#manual-path-failures) |
| Console wakes but the session never establishes | Forward path works, return path broken (NAT/SNAT) | [Wake works, streaming fails](#wake-works-streaming-fails) |
| Console will not wake at all | Not in rest mode, not registered, wake port not forwarded | [Wake failures](#wake-failures) |
| Forwarded ports look correct but an outside check fails | Test from inside the network, or no NAT loopback | [Manual path failures](#manual-path-failures) |
| Relay path fails on one ISP but works on another | Hole punching blocked by the ISP's NAT | [Relay path failures](#relay-path-failures) |

## Wake works, streaming fails

This is the signature of a **working forward path and a broken return path**.

- Wake is fire-and-forget UDP: it needs no reply, so it succeeds as soon as the
  packet reaches the console.
- Streaming is stateful (TCP `9295` plus UDP): the console's replies must reach
  the client. If they are dropped, the app reports a failure such as "Connection
  could not be established" even though the console is awake.

Check, in order:

1. **Is the client's traffic reaching the console's network through the expected
   path?** Trace the route from the client to the console's LAN gateway. If the
   first hop is the overlay-network host rather than your local gateway, the
   traffic is being tunnelled and the return path depends on that host.
2. **Does the return path exist?** If you are using a forwarding host (for
   example an overlay subnet router), it must apply NAT (SNAT) to forwarded
   traffic so the console's replies come back to the host. A host that fails to
   install its NAT rules forwards wake packets but drops session replies. See
   [the optional path section](#optional-overlay-subnet-router-failures).
3. **For the manual path, confirm both NAT hops** are forwarded and the target
   addresses are static. One missing hop produces exactly this symptom from
   outside.

## Manual path failures

| Check | Why |
| --- | --- |
| Is the WAN IP public (not CGNAT)? | Under CGNAT no inbound connection can reach the console; port forwarding is impossible |
| Is the console's address static? | A forwarding rule to a dynamic address breaks when the lease changes |
| Is every NAT hop forwarded? | In a double-NAT setup, the main router must forward to the inner router, and the inner router to the console |
| Is the inner router's WAN address reserved? | An unpinned address can drift and orphan the outer forwarding rule |
| Is the port actually open from outside? | Test TCP `9295` on `<PUBLIC_IP>` from an external network while the console is booted |
| Are you testing from inside the network? | Many routers lack NAT loopback; an inside test against the public address can fail even when the rules are correct |

A public port checker can only prove **TCP** reachability. UDP ports and wake
cannot be tested this way; use an actual manual-mode wake from outside.

## Relay path failures

- Confirm PSN sign-in on both the console and the client.
- Confirm the console is registered to the client account.
- Hole punching can fail on some ISPs even when the relay path normally works.
  If it works on one network and not another, the ISP's NAT behavior is the
  variable.
- As a last resort on a network where the relay fails and CGNAT blocks
  forwarding, use the optional overlay path.

## Wake failures

- **Not in rest mode.** A powered-off console cannot be woken; use the power
  button.
- **Console not registered.** A raw-IP entry cannot wake the console. Re-register
  from the same network.
- **Wake port missing.** The manual path needs UDP `987` forwarded at every hop.
- **Wrong tool.** TCP-based checks cannot prove wake. Use a manual-mode wake
  attempt from an external network.

## Optional overlay subnet-router failures

Applies only if you chose the optional overlay path. The failure mode below
matches the general forward-vs-return split.

**Symptom:** the console wakes from an off-network client, but the stream fails
("Connection could not be established").

**Cause:** the host advertises the LAN subnet and forwards packets, but its NAT
(SNAT) rule is missing, so replies from the console cannot return to the client.
The forward path (wake) works because it needs no reply; the return path
(streaming) fails.

**Why the NAT rule can go missing:** on a Linux host running the overlay client
inside a container, the client installs its packet rules at startup. If the
container image's packet tooling targets a backend the host kernel does not
support (for example a legacy backend on a modern nftables-only kernel), the
install fails silently and no rules - including the SNAT rule - are applied.
Container restarts and reboots preserve the state; recreating the container or
updating the image can reset it.

**Check:**

1. Confirm the client's packet tool reports the nftables backend rather than the
   legacy backend.
2. Confirm a NAT rule that masquerades marked forwarded traffic exists.
3. Confirm IP forwarding is enabled on the host.
4. Read the overlay client's log for packet-rule or netfilter errors.

**Fix:** make the host install its rules with a backend the kernel supports
(point the packet tooling at the nftables variant), then restart the overlay
client. Verify by sending a real TCP connection from a client, through the
tunnel, to a host on the console's LAN, and confirming a reply comes back. Then
retry a session.

**Make it durable:** the change must survive container recreation. Apply it in a
way that is reapplied on every start, or use an image/backend combination that
works by default.

## Gathering evidence

Useful, vendor-neutral checks:

- Route from client to the console's LAN gateway (confirms traffic takes the
  intended path; the first hop tells you whether it is tunnelled).
- TCP connect test to the edge router's web port through the intended path
  (confirms a full round trip, not just forwarding).
- TCP connect test to the console's `9295` service (confirms the service is
  listening; an HTTP response of any code, including `403`, means it is up).
- Overlay client status and health output (surfaces packet-rule errors).
- Router forwarding tables on each hop (confirms the rules exist and point at
  the right static address).
