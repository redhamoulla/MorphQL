"""Minimal MorphoQL query over a small signed event relation."""
from morphoql import Event, EventRelation, ProvenanceNode, execute_query, parse


def make_event(time: float, sign: int, strength: float) -> Event:
    node = ProvenanceNode(scale=2.0, time=time, coefficient=float(sign), branch="example", scale_index=0)
    return Event(time, sign, strength, scale_min=2.0, scale_max=2.0, series_id="sales", provenance=(node,), extractor_name="example")

relation = EventRelation("events", (
    make_event(10.0, +1, 2.5),
    make_event(20.0, -1, 3.0),
    make_event(28.0, +1, 2.1),
))
query = parse("SELECT SERIES_ID, u, d, SCORE FROM events MATCH (EDGE UP AS u THEN EDGE DOWN AS d WITHIN 8d..14d) ORDER BY SCORE DESC;")
execution = execute_query(query, relation)
for row in execution.rows:
    print(dict(row))
