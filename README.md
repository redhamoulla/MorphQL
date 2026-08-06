# MorphoQL

**MorphoQL** is a declarative query language for morphological patterns in time series. It converts signed multi-scale events—derived from first differences, Gaussian derivatives, aggregated wavelet maxima, or chained modulus-maxima lines—into an auditable event relation that can be queried with an SQL-like `EDGE–THEN–WITHIN` core.

## Paper

- [English paper (PDF)](paper/MorphoQL_Paper_English.pdf)
- [Complete LaTeX source](paper/MorphoQL_Paper_English.tex)
- Rebuild locally: `./build_paper.sh`

The paper describes the formal semantics, three equivalent execution plans, coefficient-level provenance, reproducible execution witnesses, synthetic retail benchmarks, and the limits of the current observational study.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Quick start

```python
from morphoql import Event, EventRelation, execute_query, parse_query

relation = EventRelation([
    Event(series_id="sales", time=10.0, sign=+1, strength=2.4),
    Event(series_id="sales", time=19.0, sign=-1, strength=3.1),
])

query = parse_query("""
SELECT SERIES_ID, u, d, SCORE
FROM events
MATCH EDGE UP AS u
THEN EDGE DOWN AS d WITHIN 8d..14d
ORDER BY SCORE DESC
""")

result = execute_query(query, relation)
print(result.rows)
```

Runnable examples are available in [`examples/`](examples/), including a retail-oriented demonstration.

## Validation

```bash
./run_validation_fast.sh
```

The validation suite checks the parser, strict typing, the three execution engines, event-relation invariants, provenance, deterministic ordering, projection, output manifests, and witness verification.

## Repository layout

```text
src/        language, execution engines, event extraction
examples/   minimal and retail-oriented examples
tests/      core validation tests
config/     registered preprocessing and extractor configurations
results/    representative audited outputs
paper/      English LaTeX manuscript source
```

## Scientific scope

MorphoQL queries observable temporal morphology, not business causes. A pattern such as an upward edge followed by a downward edge after 8–14 days can be retrieved declaratively; interpreting that pattern as a promotion, stockout, campaign effect, or another causal event requires external metadata or a causal model.

## Citation

Citation metadata are provided in [`CITATION.cff`](CITATION.cff).

## License

See [`LICENSE`](LICENSE).
