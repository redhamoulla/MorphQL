# MorphoQL

**Declarative morphological queries over multiscale wavelet event relations.**

MorphoQL Core 0.2 is a compact SQL-like language for querying ordered chains of signed events extracted from time series.

```sql
SELECT SERIES_ID, u, d, SCORE
FROM sales
MATCH (
  EDGE UP AS u
  THEN EDGE DOWN AS d WITHIN 8d..14d
)
WHERE MIN_STRENGTH >= 1.0
ORDER BY SCORE DESC
LIMIT 20;
```

The language describes observable morphology—edge direction, order, and temporal gaps—not business causes.

## Paper

- **Title:** *MorphoQL: Declarative Morphological Queries over Multiscale Wavelet Event Relations*
- [Open the current English PDF](https://drive.google.com/file/d/1VyjRZYagfj_DO_BYkGeLcpS-T8VYBh8q/view)
- The full English LaTeX manuscript is stored in `paper/parts/`. `./build_paper.sh` reconstructs the single `.tex` source. The compiled PDF and all figure files are included in the full reproducibility supplement linked below.

## Included code

- `src/morphoql.py` — parser, event-relation contract, three execution engines, projection, and execution records
- `src/wavelet_events.py` — first-difference, single-scale DoG, aggregated multiscale-maxima, and maximum-line extractors
- `tests/test_core.py` — parser, engine-equivalence, multi-series, projection, and extraction tests
- `examples/quickstart.py` — minimal event-relation example
- `examples/retail_demo.py` — retail-like sawtooth series and maximum-line query
- `config/` and `results/` — selected registered configurations and audited outputs from the paper

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Python 3.11 or later is required.

## Quick start

```bash
python examples/quickstart.py
python examples/retail_demo.py
```

## Tests

```bash
./run_validation_fast.sh
```

The compact repository validates the public core. The larger factorial validation, microbenchmark, bootstrap evaluation, ablation, lineage manifests, paper figures, compiled PDF, and observational-study aggregation artifacts are available in the [full reproducibility supplement](https://drive.google.com/file/d/1fHGQK0lcaYx3pCACpofMtdD5HBW8EWUC/view).

## Scope

A recomputed execution record establishes consistency relative to the supplied relation, implementation, and query. It is not a cryptographic signature, a causal explanation, or a guarantee that the event relation exhaustively represents the original signal.

## License

The repository is available for scientific inspection and non-commercial reproduction under the terms in [LICENSE](LICENSE).
