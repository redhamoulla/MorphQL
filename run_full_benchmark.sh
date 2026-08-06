#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src:$ROOT/tests${PYTHONPATH:+:$PYTHONPATH}"
if [[ "${MORPHOQL_OVERWRITE_REFERENCE:-0}" == "1" ]]; then
  export MORPHOQL_RESULTS_DIR="$ROOT/results"
  export MORPHOQL_FIGURES_DIR="$ROOT/figures"
  export MORPHOQL_DATA_DIR="$ROOT/data"
else
  export MORPHOQL_RESULTS_DIR="${MORPHOQL_RESULTS_DIR:-$ROOT/results/reproduced}"
  export MORPHOQL_FIGURES_DIR="${MORPHOQL_FIGURES_DIR:-$ROOT/figures/reproduced}"
  export MORPHOQL_DATA_DIR="${MORPHOQL_DATA_DIR:-$ROOT/data/reproduced}"
fi
mkdir -p "$MORPHOQL_RESULTS_DIR" "$MORPHOQL_FIGURES_DIR" "$MORPHOQL_DATA_DIR"
python tests/validate_core_v02.py --skip-microbenchmark
python tests/run_microbenchmark_v7.py
python src/benchmark_morphoql_v7.py
python src/postprocess_v7.py
python src/ablation_wtmm_v7.py
python src/additional_seed_replication_v7.py
python src/verify_results_v8.py
echo "Reproduced results: $MORPHOQL_RESULTS_DIR"
echo "Reproduced figures: $MORPHOQL_FIGURES_DIR"
