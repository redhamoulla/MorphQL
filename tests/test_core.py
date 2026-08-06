from __future__ import annotations

import unittest
import numpy as np

from morphoql import (
    Event,
    EventRelation,
    ProvenanceNode,
    execute_query,
    execute_sqlite,
    execute_temporal_join,
    interpret_reference,
    parse,
    verify_execution,
)
from wavelet_events import extract_dog, extract_maximum_lines, retail_residual


def event(time: float, sign: int, strength: float, series: str = "A") -> Event:
    node = ProvenanceNode(2.0, time, float(sign), "test", 0)
    return Event(time, sign, strength, 1.0, 2.0, 2.0, series, (node,), "test")


class MorphoQLCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.relation = EventRelation("sales", (
            event(10, +1, 2.5), event(20, -1, 3.0), event(28, +1, 2.1),
            event(11, +1, 2.0, "B"), event(23, -1, 2.2, "B"),
        ))

    def test_parse_and_normalize(self):
        query = parse("SELECT SERIES_ID, u, d, SCORE FROM sales MATCH (EDGE UP AS u THEN EDGE DOWN AS d WITHIN 8d..14d) ORDER BY SCORE DESC LIMIT 10;")
        self.assertEqual(query.atoms[0].sign, 1)
        self.assertEqual(query.gaps[0].minimum, 8)
        self.assertIn("EDGE UP AS u", query.normalized())

    def test_three_engines_agree(self):
        query = parse("SELECT * FROM sales MATCH (EDGE UP THEN EDGE DOWN WITHIN 8d..14d);")
        outputs = [
            {m.event_ids for m in interpret_reference(query, self.relation.events)},
            {m.event_ids for m in execute_temporal_join(query, self.relation.events)},
            {m.event_ids for m in execute_sqlite(query, self.relation.events)},
        ]
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], outputs[2])
        self.assertEqual(len(outputs[0]), 2)

    def test_projection_and_witness_recompute(self):
        query = parse("SELECT SERIES_ID, u, d, SCORE FROM sales MATCH (EDGE UP AS u THEN EDGE DOWN AS d WITHIN 8d..14d) ORDER BY SCORE DESC LIMIT 1;")
        execution = execute_query(query, self.relation)
        self.assertEqual(tuple(execution.rows[0]), ("SERIES_ID", "u", "d", "SCORE"))
        self.assertTrue(verify_execution(execution, self.relation))
        self.assertEqual(execution.witnesses[0]["output_rank"], 1)

    def test_no_cross_series_matches(self):
        query = parse("SELECT * FROM sales MATCH (EDGE UP THEN EDGE DOWN WITHIN 8d..14d THEN EDGE UP WITHIN 5d..10d);")
        output = execute_query(query, self.relation)
        self.assertEqual(len(output.matches), 1)
        self.assertEqual(output.matches[0].series_id, "A")

    def test_wavelet_extractors_emit_auditable_events(self):
        rng = np.random.default_rng(4)
        x = 100 + 8 * np.sin(np.arange(365) * 2 * np.pi / 7) + rng.normal(0, 2, 365)
        x[120:132] += 30
        residual = retail_residual(x)
        for extractor in (extract_dog, extract_maximum_lines):
            events = extractor(residual)
            self.assertGreater(len(events), 0)
            self.assertTrue(all(e.event_id and e.provenance for e in events))


if __name__ == "__main__":
    unittest.main()
