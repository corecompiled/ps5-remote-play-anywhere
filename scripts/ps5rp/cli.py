"""Command-line entry point for ps5rp.

Subcommands: init, precheck, verify, guide, wake. Everything is stdlib-only;
run with `python -m ps5rp` from the scripts/ directory, or via the ps5rp.cmd /
ps5rp.sh wrappers.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .checks import RemotePath, precheck, verify
from .config import Config, ConfigError, DEFAULT_CONFIG_PATH, load_config, prompt_config, save_config
from .guide import render_guide
from .netprobe import Prober, SystemProber
from .ui import Check, Report, Status, assert_never
from .wake import wake


def _build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="config file path")

    parser = argparse.ArgumentParser(prog="ps5rp", description="Cross-platform PS5 Remote Play workflows.")
    parser.add_argument("--version", action="version", version=f"ps5rp {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", parents=[common], help="interactively create the local config")
    sub.add_parser("precheck", parents=[common], help="discover the environment and recommend a path")

    verify_parser = sub.add_parser("verify", parents=[common], help="run the checks for a path")
    _add_path_option(verify_parser)

    guide_parser = sub.add_parser("guide", parents=[common], help="print the manual steps for a path")
    _add_path_option(guide_parser)

    wake_parser = sub.add_parser("wake", parents=[common], help="send an experimental wake packet")
    wake_parser.add_argument("--target", choices=("lan", "manual", "overlay"), default="lan")
    wake_parser.add_argument("--host", default="", help="override the target host")
    return parser


def _add_path_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--path",
        choices=[member.value for member in RemotePath],
        default=RemotePath.ALL.value,
    )


def _load_for_command(path: Path, command: str) -> Config:
    # A missing file is fine for the discovery commands; a malformed one is not,
    # and must surface rather than silently degrade to placeholder output.
    if not path.exists():
        if command in ("precheck", "guide"):
            return Config()
        raise ConfigError(f"no config at {path} - run 'ps5rp init' first")
    return load_config(path)


def _resolve_wake_host(config: Config, target: str, override: str) -> str:
    if override:
        return override
    if target in ("lan", "overlay"):
        return config.ps5_ip
    return config.ddns_hostname or config.public_ip


def main(argv: list[str] | None = None, prober: Prober | None = None) -> int:
    """Parse arguments, dispatch, and return a process exit code."""
    args = _build_parser().parse_args(argv)
    config_path: Path = args.config

    if args.command == "init":
        existing = load_config(config_path) if config_path.exists() else Config()
        updated = prompt_config(existing, input)
        save_config(updated, config_path)
        print(f"Saved configuration to {config_path}")
        return 0

    try:
        config = _load_for_command(config_path, args.command)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    active = prober if prober is not None else SystemProber()
    match args.command:
        case "precheck":
            return _emit(precheck(config, active))
        case "verify":
            return _emit(verify(config, RemotePath(args.path), active))
        case "guide":
            print(render_guide(config, RemotePath(args.path)))
            return 0
        case "wake":
            host = _resolve_wake_host(config, args.target, args.host)
            if not host:
                print("error: no target host - set ps5_ip (or use --host)", file=sys.stderr)
                return 2
            return _emit(Report(tuple(wake(config, host, active))))
        case unreachable:
            assert_never(unreachable)


def _emit(report: Report) -> int:
    print(report.render())
    return 1 if report.failed else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
