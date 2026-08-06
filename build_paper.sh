#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
cat paper/parts/part_*.tex > paper/MorphoQL_Paper_English.tex
echo "Reconstructed paper/MorphoQL_Paper_English.tex"

required_figure="figures/representative_retail_series_en.pdf"
if command -v latexmk >/dev/null 2>&1 && [[ -f "$required_figure" ]]; then
  (cd paper && latexmk -xelatex -interaction=nonstopmode -halt-on-error MorphoQL_Paper_English.tex)
  echo "Compiled paper/MorphoQL_Paper_English.pdf"
else
  echo "Compilation skipped: XeLaTeX/latexmk or the paper figure bundle is unavailable."
  echo "The complete figure bundle and compiled PDF are in the reproducibility supplement."
fi
