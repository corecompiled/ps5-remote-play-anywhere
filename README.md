# PS5 Remote Play from Outside Your Home Network

*`ps5-remote-play-anywhere` - a router-agnostic setup guide plus a dependency-free diagnostic CLI (`ps5rp`).*

A practical, router-agnostic guide to playing your PS5 while away from home on
Android, iOS, or a PlayStation Portal. It explains how the connection methods
actually work, which ones need router changes, and how to diagnose the ones that
don't.

This is community documentation. It is not affiliated with, endorsed by, or
supported by Sony Interactive Entertainment.

## What this repository covers

- The three ways a client can reach a PS5 that is not on the same network, and
  when each one works.
- The ports, protocols, and NAT behavior each method depends on.
- Wake-from-rest semantics (which paths can turn the console on, and why a
  powered-off console can never be woken remotely).
- How to detect CGNAT and why it decides whether port forwarding is even
  possible.
- A symptom-based troubleshooting guide, including the common
  "wake works, streaming fails" failure.
- An optional self-hosted path using an overlay network (a subnet router) for
  networks where nothing else is available.

## The three connection paths

| Path | How it connects | Router configuration | Survives CGNAT? | Typical client |
| --- | --- | --- | --- | --- |
| **Sony relay** | Console and client both dial outbound to Sony's Remote Play servers, which relay the stream | None (no inbound ports) | Yes | Official PS Remote Play app, PS Portal |
| **PXPlay via PSN** | Registers with Sony, then uses UDP hole punching through Sony's relay | None required | Usually | PXPlay |
| **PXPlay manual** | Direct inbound connection to the console | Public WAN IP + port forwarding at every NAT hop | No | PXPlay |
| **Overlay network** (optional) | Console LAN is advertised into a private overlay network; client joins the overlay | None on the routers; one always-on host on the LAN | Yes (via relay) | PXPlay / any client with an overlay client (Tailscale, NetBird, and similar) |

If you only want the simplest working setup, start with the Sony relay path: it
requires no router changes at all. Port forwarding is only needed if you
specifically want PXPlay's manual mode, and it is impossible on a CGNAT
connection.

Most homes have a single router, and the setup guide treats that as the default.
If your console sits behind a second router (a common upstairs/downstairs
arrangement), the guide adds one extra forwarding hop and the CLI detects it
from your config and tailors its instructions - see the Double NAT steps (B3) in
[docs/setup-guide.md](docs/setup-guide.md).

## Quick decision

1. **Check whether your internet connection is public or CGNAT.** See
   [Detecting CGNAT](docs/architecture.md#detecting-cgnat). If it is CGNAT, skip
   port forwarding entirely - use the relay paths, or the optional overlay
   network.
2. **Use the relay path first.** PS Portal, the official Remote Play app, and
   PXPlay's "Connect via PSN" mode need no router changes. This is enough for
   most people.
3. **Only configure port forwarding** if the relay paths fail and you have a
   public WAN IP. Follow [docs/setup-guide.md](docs/setup-guide.md).
4. **If relay fails and you are behind CGNAT,** use the optional
   [overlay network (subnet router) path](docs/setup-guide.md#path-c-optional-overlay-network-subnet-router).

## Guided workflows (ps5rp)

A dependency-free Python 3.10+ CLI that discovers your network, recommends a
path, prints the manual steps it cannot perform, and verifies a working setup.
No installation required:

```sh
python -m ps5rp precheck        # from the scripts/ directory
scripts\ps5rp.cmd precheck      # Windows wrapper, from the repo root
./scripts/ps5rp.sh precheck     # macOS/Linux wrapper
```

| Subcommand | Does |
| --- | --- |
| `init` | Interactively create the local config (`.ps5rp/config.json`, git-ignored) |
| `precheck` | Detect the environment and recommend a path |
| `verify --path relay\|manual\|overlay\|all` | Run checks with PASS/WARN/FAIL |
| `guide --path ...` | Print the manual steps for a path |
| `wake` | Send an experimental best-effort wake packet |

It automates discovery and diagnosis only. Anything behind a login - routers,
console menus, overlay sign-in - is printed as instructions, never performed.
See [docs/workflows.md](docs/workflows.md).

## Documentation map

| Document | Contents |
| --- | --- |
| [docs/architecture.md](docs/architecture.md) | NAT, CGNAT, the three connection paths, topology examples, wake behavior, the decision matrix, and the security model |
| [docs/setup-guide.md](docs/setup-guide.md) | Step-by-step setup for each path: PS5 settings, router configuration, static addresses, DDNS, client pairing, and testing |
| [docs/ports-and-protocols.md](docs/ports-and-protocols.md) | The port table, the wake-by-path matrix, and how TCP/UDP and NAT affect each path |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Symptom-to-cause table and triage procedures, including the forward-vs-return-path failure |
| [docs/workflows.md](docs/workflows.md) | The ps5rp command-line workflows: precheck, verify, guide, wake, and the local config |

## Repository layout

```
README.md                        This overview
LICENSE                          MIT
.gitignore
docs/
  architecture.md                How the paths work
  setup-guide.md                 How to configure each path
  ports-and-protocols.md         Port and protocol reference
  troubleshooting.md             Diagnosis and repair
  workflows.md                   The ps5rp command-line workflows
scripts/
  ps5rp/                         Python package (stdlib only)
  ps5rp.cmd / ps5rp.sh           Wrappers
  config.example.json            Config template
tests/
  test_ps5rp.py                  Unit tests (stdlib unittest)
local/                           Your private instance (git-ignored)
```

The `local/` directory is intentionally excluded from version control. It holds
machine-specific values (real addresses, MAC addresses, hostnames) and any
private notes. The public documents use placeholders; see
[Placeholders and local overrides](docs/architecture.md#placeholders-and-local-overrides).

## Requirements

Regardless of the path you choose, the console needs:

- Remote Play enabled for the account that owns the games.
- Rest-mode networking enabled, so the console can be turned on from the network.
- NAT Type 1 or 2 (Type 3 breaks every path).
- A wired Ethernet connection where possible, for lower latency and stability.

The exact menu locations are listed in
[docs/setup-guide.md](docs/setup-guide.md#step-1-configure-the-console).

## Verifying a setup

The reliable checks are:

- A **same-network test** first, to confirm pairing and sign-in work.
- An **external test** from a genuinely different network (a mobile hotspot or a
  friend's Wi-Fi). A second device inside your own home does not simulate this.
- For the port-forward path only, a TCP reachability check on port `9295` from
  outside (for example with a public port checker) while the console is booted.

See [docs/troubleshooting.md](docs/troubleshooting.md) for what each result
means.

## Contributing

Corrections and additions are welcome. Keep changes generic: do not commit real
IP addresses, MAC addresses, hostnames, credentials, or other details from your
own network. Use the placeholders described in
[docs/architecture.md](docs/architecture.md#placeholders-and-local-overrides),
and describe behavior rather than a specific vendor's menu tree.

## License

MIT. See [LICENSE](LICENSE).
