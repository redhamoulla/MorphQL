# MorphoQL

**Declarative morphological queries over multiscale wavelet event relations.**

MorphoQL Core 0.2 is a compact SQL-like language for querying ordered chains of signed events extracted from time series. The reference implementation supports parsing, three strict execution engines, deterministic post-processing, projection, multiseries event relations, coefficient-level provenance, and recomputable execution witnesses.

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

- [MorphoQL: Declarative Morphological Queries over Multiscale Wavelet Event Relations](paper/MorphoQL_Paper_English.pdf)

## Repository layout

- `src/morphoql.py` — grammar, parser, event-relation contract, execution engines, projection, and witnesses
- `src/configuration.py` — versioned configurations and deterministic fingerprints
- `src/benchmark_morphoql_v7.py` — retail-like synthetic generator and four event extractors
- `tests/validate_core_v02.py` — parser, differential, adversarial, provenance, and witness validation
- `examples/quickstart.py` — minimal executable example
- `config/` — registered extraction and benchmark configurations
- `results/` — selected audited tables and witness examples
- `paper/` — English paper

Internal suffixes such as `_v7` and `_v8` are retained where they identify immutable scientific artifacts and result lineage.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Python 3.11 or later is required.

## Quick start

```bash
PYTHONPATH=src python examples/quickstart.py
```

## Validate the implementation

```bash
./run_validation_fast.sh
```

The reference validation checks 1,200 valid queries, 1,200 invalid mutations, 800 differential cases across the reference, temporal-join, and SQLite engines, and 85 boundary/adversarial tests.

## Reproduce experiments

```bash
./run_microbenchmark.sh
./run_full_benchmark.sh
```

The complete benchmark compares first differences, a single-scale derivative of Gaussian, aggregated multiscale maxima, and chained maximum lines on retail-like synthetic series. Generated outputs are written to reproduction directories unless explicit overwrite is enabled.

## Scope

A verified execution witness establishes consistency by recomputation relative to the supplied relation, implementation, configurations, and query. It is not a cryptographic signature, a causal explanation, or a guarantee that the event relation exhaustively represents the original signal.

## License

The repository is available for scientific inspection and non-commercial reproduction under the terms in [LICENSE](LICENSE).
