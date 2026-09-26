# Workflows (ps5rp)

`ps5rp` is a small, dependency-free command-line tool that walks you through
setting up PS5 Remote Play: it discovers your network, tells you which path is
viable, prints the manual steps it cannot do for you, and verifies a working
setup.

It requires **Python 3.10 or newer** and nothing else - no `pip install`, no
virtual environment.

## What it automates, and what it does not

| Layer | Automated | Manual (printed as instructions) |
| --- | --- | --- |
| Discovery | Local address/gateway, public IP, CGNAT classification | - |
| Diagnosis | Reachability probes, path recommendation, PASS/WARN/FAIL checks | - |
| Configuration | Nothing | Router port forwarding, static reservations, PS5 menu settings, console registration, DDNS, overlay subnet routing and sign-in |
| Wake | Best-effort packet send (experimental) | The reliable wake is the client app / PSN relay |

Anything behind a login - a router admin page, a console menu, an overlay
service - is a manual step. The tool prints exactly what to do and never stores
credentials. It stores only non-secret addresses in a local config.

## Quick start

Run from the `scripts/` directory, or use a wrapper (below).

```sh
# 1. Answer a few questions about your network (optional but recommended).
python -m ps5rp init

# 2. See what your network supports and which path to use.
python -m ps5rp precheck

# 3. Print the exact manual steps for a path.
python -m ps5rp guide --path manual

# 4. After configuring, verify what can be checked from here.
python -m ps5rp verify --path all
```

Wrappers let you run it from the repository root with one command:

```bat
scripts\ps5rp.cmd precheck
```

```sh
./scripts/ps5rp.sh precheck
```

## Subcommands

| Subcommand | Purpose |
| --- | --- |
| `init` | Interactively build the local config. Keeps existing values as defaults. |
| `precheck` | Detect the environment (OS, LAN context, public IP, CGNAT), probe reachability, and recommend a path. Works without a config. |
| `verify --path <relay\|manual\|overlay\|all>` | Run the checks for a path and report PASS/WARN/FAIL. |
| `guide --path <relay\|manual\|overlay\|all>` | Print the manual steps for a path, with your values substituted. Works without a config. |
| `wake --target <lan\|manual\|overlay> [--host H]` | Send an experimental best-effort wake packet. |

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | All checks passed (or the command completed). |
| `1` | `precheck`/`verify`/`wake`: one or more checks failed. |
| `2` | Usage or configuration error (for example, no config where one is required). |

## Configuration

`init` writes `.ps5rp/config.json` at the repository root. It is git-ignored and
holds non-secret values only. A template is provided at
[`scripts/config.example.json`](../scripts/config.example.json).

| Field | Meaning |
| --- | --- |
| `public_ip` | Internet-facing WAN address (blank to auto-detect) |
| `ddns_hostname` | Stable hostname for a changing public IP |
| `main_router_ip` | LAN address of the internet-facing router |
| `second_router_wan_ip` | Inner router's WAN address (double NAT only) |
| `second_router_lan_ip` | Inner router's LAN address |
| `ps5_ip` | Console's static LAN address |
| `ps5_mac` | Console's MAC address (used only by the experimental wake) |
| `overlay_host_ip` | Optional overlay subnet-router host address |
| `tailnet_name` | Optional overlay network name |
| `control_plane_url` | Optional self-hosted overlay control-plane URL |
| `wake_ports` | UDP ports to target with `wake` (default `[987, 9302]`) |

You can point at a different file with `--config PATH` (place it after the
subcommand, for example `ps5rp precheck --config ./my.json`).

Setting either `second_router_*` field marks the setup as **double NAT**: the
checks and the manual steps then cover the extra hop (reserve the inner router's
WAN address, forward the same ports at both routers). With neither set, a
**single-router** setup is assumed - the default for most homes.

## Running the tests

```sh
python -m unittest discover -s tests
```

The suite uses only the standard library and covers IP classification, config
parsing, the check suites (against an in-memory prober, no network), the guide
substitution, and the CLI exit codes.

## Extending it

The code is split so a new capability is one small change:

- **A new probe** (for example, a different router API): add a method to the
  `Prober` protocol and to `SystemProber` in `scripts/ps5rp/netprobe.py`.
- **A new check**: add it to `scripts/ps5rp/checks.py`; checks depend only on
  `Prober`, so they are testable with a fake.
- **A new path**: add a member to `RemotePath`, a check function, and a guide
  section. The `match` statements are exhaustive, so the type checker and
  `assert_never` will point at every place that needs updating.
- **New manual text**: edit `scripts/ps5rp/guide.py`.

Run the tests after any change; they are fast and need no network.

## Platform notes

- Windows, macOS, and Linux are supported. Local address, gateway, ping, and
  traceroute are read from the native tools on each platform.
- On Windows use `py -3` if `python` is not on `PATH`; the `ps5rp.cmd` wrapper
  falls back automatically.
- The overlay checks look for the `tailscale` command. If you use another
  overlay, verify that path manually - the checks report it as a warning, not a
  failure.
