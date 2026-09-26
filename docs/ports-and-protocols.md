# Ports and Protocols

This document lists the ports Remote Play uses, what each one is for, and how
NAT treats the traffic. Read it alongside
[architecture.md](architecture.md) for how the paths differ.

## Port table

| Port | Protocol | Purpose | When it must be forwarded |
| --- | --- | --- | --- |
| 987 | UDP | PXPlay wake-up from outside | Manual (port-forward) path only, to power on the console from outside |
| 9295 | TCP | PXPlay/Chiaki streaming and control channel | Manual path only |
| 9295 | UDP | PXPlay/Chiaki streaming | Manual path only |
| 9296 | UDP | PXPlay/Chiaki streaming | Manual path only |
| 9297 | UDP | PXPlay/Chiaki streaming | Manual path only |
| 9302 | UDP | PS5 wake packet (community-documented) | Optional; keep forwarded if you use it, but see 987 |
| 8572 | UDP | Official Remote Play / PS Portal | Not required in the normal case; forward only if your router blocks outbound traffic |

Notes:

- Forwarding is only relevant to the **manual (port-forward) path**. The Sony
  relay path and PXPlay "Connect via PSN" open no inbound ports.
- `9295/TCP` also answers an HTTP health probe on the console
  (`/sce/rc/health`). Any HTTP response, including `403`, means the service is
  listening. A timeout means it is not.
- Wake is a UDP operation. TCP-based tools such as a public port checker or a
  generic "test connection" utility cannot prove that wake works; the only
  definitive test is a wake attempt from a genuinely external network.

## Transaction direction: forward path vs return path

The single most useful concept for diagnosing Remote Play is the difference
between the forward path and the return path.

- **Forward path** - the packet from the client to the console. For a wake
  packet this is a single, fire-and-forget UDP datagram. It needs no reply.
- **Return path** - the packet from the console back to the client. Streaming
  is a stateful session (TCP `9295` plus UDP), so every reply must be able to
  reach the client.

A network can carry the forward path and drop the return path. When that
happens, the console wakes but the session never establishes. This is the root
of the "wake works, streaming fails" failure and is covered in
[troubleshooting.md](troubleshooting.md#wake-works-streaming-fails).

## Wake-by-path matrix

Wake works only from **rest mode**. A console that is fully powered off can only
be turned on with the power button; no network path can wake it. The console
also requires "Enable Turning On PS5 from Network" to be on.

| Path | Wake mechanism | Configuration |
| --- | --- | --- |
| PS Portal | Sony relay pushes the wake through the console's outbound PSN keep-alive. No inbound ports. | Works as-is |
| Official Remote Play app | Same PSN-relay wake as PS Portal. | Works as-is |
| PXPlay "Connect via PSN" | Same PSN-relay wake. | Works as-is |
| PXPlay manual (port forwarding) | Client sends a wake packet to UDP `987` at the public address; it traverses every NAT hop to the console. | Requires UDP `987` forwarded at every hop and a registered console |
| PXPlay manual (overlay network) | The same UDP `987` wake packet, routed over the overlay tunnel to the LAN. | No router configuration; the advertised subnet route carries it |

Wake-up is a feature of **registered** consoles. Registration is a one-time
step performed on the same network (an 8-digit code from
`Settings -> System -> Remote Play -> Link Device`, plus PSN sign-in). A console
entry created by raw IP address without registration can never wake the console,
no matter how many times it is retried. Use the registered entry, or the app's
explicit wake button where available.

## Do not use ARP as a power-state test

A rest-mode console over Wi-Fi may show a stale ARP entry and no listener on
`9295`, yet still wake and stream correctly. Conversely, a missing ARP entry
does not by itself prove the console is off. The definitive state test is a
wake attempt, not the ARP table.
