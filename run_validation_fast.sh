#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export MORPHOQL_RESULTS_DIR="${MORPHOQL_RESULTS_DIR:-$ROOT/results/reproduced_validation_v8}"
mkdir -p "$MORPHOQL_RESULTS_DIR"
python tests/validate_core_v02.py --skip-microbenchmark
printf 'Fast validation outputs: %s\n' "$MORPHOQL_RESULTS_DIR"
