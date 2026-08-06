"""Minimal MorphoQL query over a small signed event relation."""
from __future__ import annotations

from configuration import CONFIG_SCHEMA_VERSION
from morphoql import Event, EventRelation, ProvenanceNode, ensure_event_ids, execute_query, parse


def node(time: float, sign: int) -> ProvenanceNode:
    return ProvenanceNode(scale=2.0,time=time,coefficient=float(sign),branch="example",scale_index=0)


events = ensure_event_ids([
    Event(10.0,+1,2.5,scale_min=2.0,scale_max=2.0,series_id="sales",provenance=(node(10.0,+1),),extractor_name="example"),
    Event(20.0,-1,3.0,scale_min=2.0,scale_max=2.0,series_id="sales",provenance=(node(20.0,-1),),extractor_name="example"),
    Event(28.0,+1,2.1,scale_min=2.0,scale_max=2.0,series_id="sales",provenance=(node(28.0,+1),),extractor_name="example"),
])
extractor_config={"schema_version":CONFIG_SCHEMA_VERSION,"config_kind":"extractor","extractor_name":"example","parameters":{"description":"hand-authored example events"}}
preprocessing_config={"schema_version":CONFIG_SCHEMA_VERSION,"config_kind":"preprocessing","parameters":{"description":"none"}}
relation=EventRelation(name="events",events=events,extractor_name="example",extractor_config=extractor_config,preprocessing_config=preprocessing_config)
query=parse("SELECT SERIES_ID, u, d, SCORE FROM events MATCH (EDGE UP AS u THEN EDGE DOWN AS d WITHIN 8d..14d) ORDER BY SCORE DESC;")
execution=execute_query(query,relation)
for row in execution.rows:
    print(dict(row))
