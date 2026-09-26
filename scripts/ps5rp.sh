#!/usr/bin/env sh
# ps5rp - run from the repository without installing anything.
# Usage: ./scripts/ps5rp.sh precheck   (or any other subcommand)
HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PYTHONPATH="$HERE" exec "${PYTHON:-python3}" -m ps5rp "$@"
