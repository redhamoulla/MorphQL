#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src:$ROOT/tests${PYTHONPATH:+:$PYTHONPATH}"
if [[ "${MORPHOQL_OVERWRITE_REFERENCE:-0}" == "1" ]]; then
  export MORPHOQL_RESULTS_DIR="$ROOT/results"
else
  export MORPHOQL_RESULTS_DIR="${MORPHOQL_RESULTS_DIR:-$ROOT/results/reproduced_microbenchmark}"
fi
mkdir -p "$MORPHOQL_RESULTS_DIR"
python tests/run_microbenchmark_v7.py
echo "Microbenchmark outputs: $MORPHOQL_RESULTS_DIR"
