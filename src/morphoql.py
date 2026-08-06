"""MorphoQL Core 0.2: declarative edge-chain queries over event relations.

The implementation intentionally separates:
1. strict satisfaction over a finite, multi-series event relation;
2. execution strategies (reference enumeration, temporal joins, SQLite);
3. deterministic scoring, ordering, projection, and LIMIT;
4. a recomputable execution record.

The language describes observable morphology. It does not assign business or
causal labels to retrieved episodes.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from itertools import combinations
import hashlib
import json
import math
import re
import sqlite3
from typing import Any, Iterable, Mapping, Sequence

from lark import Lark, Transformer

IMPLEMENTATION_VERSION = "0.8.0"
SCHEMA_VERSION = "morphoql.event-relation/0.8"

_GRAMMAR = r"""
start: query
query: SELECT projection FROM CNAME MATCH "(" chain ")" where_clause? order_clause? limit_clause? ";"?
projection: "*" -> project_all | field ("," field)* -> project_fields
field: MATCH_START -> match_start | MATCH_END -> match_end | SCORE -> score_field | SERIES_ID -> series_id | CNAME -> named_field
chain: edge (THEN edge WITHIN interval)+
edge: EDGE direction alias?
direction: UP -> up | DOWN -> down
alias: AS CNAME
interval: duration ".." duration
duration: NUMBER UNIT
where_clause: WHERE MIN_STRENGTH ">=" SIGNED_NUMBER
order_clause: ORDER BY SCORE DESC
limit_clause: LIMIT INT
SELECT: /SELECT/i
FROM: /FROM/i
MATCH: /MATCH/i
EDGE: /EDGE/i
UP: /UP/i
DOWN: /DOWN/i
AS: /AS/i
THEN: /THEN/i
WITHIN: /WITHIN/i
WHERE: /WHERE/i
MIN_STRENGTH: /MIN_STRENGTH/i
ORDER: /ORDER/i
BY: /BY/i
SCORE: /SCORE/i
DESC: /DESC/i
LIMIT: /LIMIT/i
MATCH_START: /MATCH_START/i
MATCH_END: /MATCH_END/i
SERIES_ID: /SERIES_ID/i
UNIT: /(jours|jour|days|day|min|ms|h|w|d|j|s)\b/i
%import common.CNAME
%import common.INT
%import common.NUMBER
%import common.SIGNED_NUMBER
%import common.WS
%ignore WS
"""

_UNIT_TO_DAYS = {
    "ms": 1 / 86_400_000,
    "s": 1 / 86_400,
    "min": 1 / 1_440,
    "h": 1 / 24,
    "d": 1.0,
    "day": 1.0,
    "days": 1.0,
    "j": 1.0,
    "jour": 1.0,
    "jours": 1.0,
    "w": 7.0,
}


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be an int or float, not {type(value).__name__}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def deterministic_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(deterministic_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Atom:
    sign: int
    alias: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.sign, int) or isinstance(self.sign, bool) or self.sign not in {-1, 1}:
            raise TypeError("Atom.sign must be the integer -1 or +1")
        if self.alias is not None and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.alias):
            raise ValueError("Invalid alias")


@dataclass(frozen=True)
class Gap:
    minimum: float
    maximum: float

    def __post_init__(self) -> None:
        lo = _finite_number(self.minimum, "Gap.minimum")
        hi = _finite_number(self.maximum, "Gap.maximum")
        if lo < 0 or hi < lo:
            raise ValueError("A gap requires 0 <= minimum <= maximum")
        object.__setattr__(self, "minimum", lo)
        object.__setattr__(self, "maximum", hi)


@dataclass(frozen=True)
class Query:
    source: str
    atoms: tuple[Atom, ...]
    gaps: tuple[Gap, ...]
    select_fields: tuple[str, ...] = ("*",)
    min_strength: float = 0.0
    order_by_score: bool = False
    limit: int | None = None

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.source):
            raise ValueError("Invalid source name")
        if len(self.atoms) < 2 or len(self.gaps) != len(self.atoms) - 1:
            raise ValueError("Core 0.2 requires at least two atoms and one gap per THEN")
        threshold = _finite_number(self.min_strength, "min_strength")
        object.__setattr__(self, "min_strength", threshold)
        if self.limit is not None and (not isinstance(self.limit, int) or isinstance(self.limit, bool) or self.limit <= 0):
            raise ValueError("LIMIT must be a positive integer")
        aliases = [a.alias for a in self.atoms if a.alias]
        if len(aliases) != len(set(aliases)):
            raise ValueError("Aliases must be unique")
        if not self.select_fields:
            raise ValueError("SELECT must contain at least one field")
        allowed = {"*", "MATCH_START", "MATCH_END", "SCORE", "SERIES_ID", *aliases}
        for item in self.select_fields:
            if item not in allowed and item.upper() not in allowed:
                raise ValueError(f"Unknown projection field: {item}")

    def normalized(self) -> str:
        projection = ", ".join(self.select_fields)
        parts: list[str] = []
        for i, atom in enumerate(self.atoms):
            edge = f"EDGE {'UP' if atom.sign > 0 else 'DOWN'}"
            if atom.alias:
                edge += f" AS {atom.alias}"
            if i:
                gap = self.gaps[i - 1]
                parts.append(f"THEN {edge} WITHIN {gap.minimum:g}d..{gap.maximum:g}d")
            else:
                parts.append(edge)
        text = f"SELECT {projection} FROM {self.source} MATCH ({' '.join(parts)})"
        if self.min_strength != 0:
            text += f" WHERE MIN_STRENGTH >= {self.min_strength:g}"
        if self.order_by_score:
            text += " ORDER BY SCORE DESC"
        if self.limit is not None:
            text += f" LIMIT {self.limit}"
        return text + ";"


@dataclass(frozen=True)
class ProvenanceNode:
    scale: float
    time: float
    coefficient: float
    branch: str
    scale_index: int | None = None

    def __post_init__(self) -> None:
        for name in ("scale", "time", "coefficient"):
            object.__setattr__(self, name, _finite_number(getattr(self, name), name))
        if self.scale < 0:
            raise ValueError("scale must be non-negative")
        if not self.branch:
            raise ValueError("branch must be non-empty")


@dataclass(frozen=True)
class Event:
    time: float
    sign: int
    strength: float
    persistence: float = 1.0
    scale_min: float = 0.0
    scale_max: float = 0.0
    series_id: str = "series_0"
    provenance: tuple[ProvenanceNode, ...] = field(default_factory=tuple)
    extractor_name: str = "external"
    event_id: str | None = None

    def __post_init__(self) -> None:
        if not self.series_id or not self.extractor_name:
            raise ValueError("series_id and extractor_name must be non-empty")
        if not isinstance(self.sign, int) or isinstance(self.sign, bool) or self.sign not in {-1, 1}:
            raise TypeError("Event.sign must be the integer -1 or +1")
        for name in ("time", "strength", "persistence", "scale_min", "scale_max"):
            object.__setattr__(self, name, _finite_number(getattr(self, name), name))
        if self.strength < 0 or not 0 <= self.persistence <= 1 or not 0 <= self.scale_min <= self.scale_max:
            raise ValueError("Invalid event numeric domain")
        if not self.provenance:
            raise ValueError("Every event requires non-empty provenance")
        if any((1 if n.coefficient > 0 else -1) != self.sign for n in self.provenance if n.coefficient != 0):
            raise ValueError("Provenance coefficient signs must agree with the event")
        expected = event_content_id(self)
        if self.event_id is not None and self.event_id != expected:
            raise ValueError("event_id must equal the content address of the event")
        object.__setattr__(self, "event_id", expected)


def event_payload(event: Event, *, include_id: bool = False) -> dict[str, Any]:
    payload = {
        "time": event.time,
        "sign": event.sign,
        "strength": event.strength,
        "persistence": event.persistence,
        "scale_min": event.scale_min,
        "scale_max": event.scale_max,
        "series_id": event.series_id,
        "extractor_name": event.extractor_name,
        "provenance": [asdict(node) for node in event.provenance],
    }
    if include_id:
        payload["event_id"] = event.event_id
    return payload


def event_content_id(event: Event) -> str:
    return "evt_" + fingerprint(event_payload(event, include_id=False))


@dataclass(frozen=True)
class EventRelation:
    name: str
    events: tuple[Event, ...]

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.name):
            raise ValueError("Invalid relation name")
        keys = [(e.series_id, e.event_id) for e in self.events]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate (series_id, event_id) key")
        object.__setattr__(self, "events", tuple(sorted(self.events, key=lambda e: (e.series_id, e.time, e.event_id))))

    @property
    def relation_fingerprint(self) -> str:
        return fingerprint([event_payload(e, include_id=True) for e in self.events])


@dataclass(frozen=True)
class Match:
    events: tuple[Event, ...]
    score: float

    @property
    def series_id(self) -> str:
        return self.events[0].series_id

    @property
    def event_ids(self) -> tuple[str, ...]:
        return tuple(e.event_id or "" for e in self.events)

    @property
    def gaps(self) -> tuple[float, ...]:
        return tuple(b.time - a.time for a, b in zip(self.events, self.events[1:]))


@dataclass(frozen=True)
class Execution:
    query: Query
    matches: tuple[Match, ...]
    rows: tuple[Mapping[str, Any], ...]
    witnesses: tuple[Mapping[str, Any], ...]


class _TreeToQuery(Transformer):
    def up(self, _): return 1
    def down(self, _): return -1
    def alias(self, items): return str(items[-1])
    def edge(self, items):
        sign = next(x for x in items if isinstance(x, int))
        alias = next((x for x in items if isinstance(x, str) and x not in {"EDGE"}), None)
        return Atom(sign, alias)
    def duration(self, items):
        number = float(items[0]); unit = str(items[1]).lower()
        return number * _UNIT_TO_DAYS[unit]
    def interval(self, items): return Gap(float(items[0]), float(items[1]))
    def chain(self, items):
        return tuple(x for x in items if isinstance(x, (Atom, Gap)))
    def project_all(self, _): return ("*",)
    def match_start(self, _): return "MATCH_START"
    def match_end(self, _): return "MATCH_END"
    def score_field(self, _): return "SCORE"
    def series_id(self, _): return "SERIES_ID"
    def named_field(self, items): return str(items[0])
    def project_fields(self, items): return tuple(x for x in items if isinstance(x, str))
    def where_clause(self, items): return ("where", float(items[-1]))
    def order_clause(self, _): return ("order", True)
    def limit_clause(self, items): return ("limit", int(items[-1]))
    def query(self, items):
        projection = next(x for x in items if isinstance(x, tuple) and (not x or isinstance(x[0], str)))
        chain = next(x for x in items if isinstance(x, tuple) and x and isinstance(x[0], (Atom, Gap)))
        source_tokens = [str(x) for x in items if getattr(x, "type", None) == "CNAME"]
        source = source_tokens[0]
        atoms = tuple(x for x in chain if isinstance(x, Atom))
        gaps = tuple(x for x in chain if isinstance(x, Gap))
        options = {x[0]: x[1] for x in items if isinstance(x, tuple) and len(x) == 2 and x[0] in {"where", "order", "limit"}}
        return Query(source, atoms, gaps, projection, options.get("where", 0.0), options.get("order", False), options.get("limit"))
    def start(self, items): return items[0]


_PARSER = Lark(_GRAMMAR, parser="lalr", transformer=_TreeToQuery())


def parse(text: str) -> Query:
    if not isinstance(text, str) or not text.strip():
        raise TypeError("query text must be a non-empty string")
    return _PARSER.parse(text)


def satisfies(query: Query, events: Sequence[Event]) -> bool:
    if len(events) != len(query.atoms):
        return False
    if len({e.series_id for e in events}) != 1:
        return False
    for event, atom in zip(events, query.atoms):
        if event.sign != atom.sign or event.strength < query.min_strength:
            return False
    for left, right, gap in zip(events, events[1:], query.gaps):
        observed = right.time - left.time
        if right.time <= left.time or not gap.minimum <= observed <= gap.maximum:
            return False
    return True


def match_score(events: Sequence[Event], query: Query) -> float:
    logs = [math.log1p(e.strength) for e in events]
    score = min(logs) + 0.35 * sum(logs) / len(logs)
    for observed, gap in zip((b.time - a.time for a, b in zip(events, events[1:])), query.gaps):
        center = (gap.minimum + gap.maximum) / 2
        half = max((gap.maximum - gap.minimum) / 2, 1e-12)
        score -= 0.08 * abs(observed - center) / half
    return float(score)


def interpret_reference(query: Query, events: Sequence[Event]) -> tuple[Match, ...]:
    by_series: dict[str, list[Event]] = {}
    for event in events:
        by_series.setdefault(event.series_id, []).append(event)
    output: list[Match] = []
    for series_events in by_series.values():
        series_events.sort(key=lambda e: (e.time, e.event_id))
        for indices in combinations(range(len(series_events)), len(query.atoms)):
            selected = tuple(series_events[i] for i in indices)
            if satisfies(query, selected):
                output.append(Match(selected, match_score(selected, query)))
    return tuple(output)


def execute_temporal_join(query: Query, events: Sequence[Event]) -> tuple[Match, ...]:
    candidates = [e for e in events if e.sign == query.atoms[0].sign and e.strength >= query.min_strength]
    prefixes: list[tuple[Event, ...]] = [(e,) for e in candidates]
    for atom, gap in zip(query.atoms[1:], query.gaps):
        next_prefixes: list[tuple[Event, ...]] = []
        for prefix in prefixes:
            last = prefix[-1]
            for event in events:
                observed = event.time - last.time
                if (event.series_id == last.series_id and event.sign == atom.sign and event.strength >= query.min_strength
                        and event.time > last.time and gap.minimum <= observed <= gap.maximum):
                    next_prefixes.append(prefix + (event,))
        prefixes = next_prefixes
    return tuple(Match(prefix, match_score(prefix, query)) for prefix in prefixes)


def execute_sqlite(query: Query, events: Sequence[Event]) -> tuple[Match, ...]:
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE events (series_id TEXT, event_id TEXT, time REAL, sign INTEGER, strength REAL)")
    connection.executemany("INSERT INTO events VALUES (?,?,?,?,?)", [(e.series_id, e.event_id, e.time, e.sign, e.strength) for e in events])
    aliases = [f"e{i}" for i in range(len(query.atoms))]
    select = ",".join(f"{a}.event_id" for a in aliases)
    sql = f"SELECT {select} FROM events {aliases[0]}"
    params: list[Any] = []
    for i in range(1, len(aliases)):
        prev, current, gap = aliases[i-1], aliases[i], query.gaps[i-1]
        sql += (f" JOIN events {current} ON {current}.series_id={aliases[0]}.series_id"
                f" AND {current}.time>{prev}.time AND {current}.time-{prev}.time BETWEEN ? AND ?")
        params.extend([gap.minimum, gap.maximum])
    conditions = []
    for alias, atom in zip(aliases, query.atoms):
        conditions += [f"{alias}.sign=?", f"{alias}.strength>=?"]
        params.extend([atom.sign, query.min_strength])
    sql += " WHERE " + " AND ".join(conditions)
    ids = connection.execute(sql, params).fetchall()
    lookup = {e.event_id: e for e in events}
    connection.close()
    return tuple(Match(tuple(lookup[event_id] for event_id in row), match_score(tuple(lookup[event_id] for event_id in row), query)) for row in ids)


def _sort_key(match: Match, order_by_score: bool) -> tuple[Any, ...]:
    times = tuple(e.time for e in match.events)
    ids = match.event_ids
    if order_by_score:
        return (-match.score, match.series_id, *times, *ids)
    return (match.series_id, *times, -match.score, *ids)


def project_match(query: Query, match: Match) -> dict[str, Any]:
    aliases = {atom.alias: event.time for atom, event in zip(query.atoms, match.events) if atom.alias}
    full = {
        "SERIES_ID": match.series_id,
        "MATCH_START": match.events[0].time,
        "MATCH_END": match.events[-1].time,
        "SCORE": match.score,
        "EVENT_IDS": list(match.event_ids),
        "TIMES": [e.time for e in match.events],
        "OBSERVED_GAPS": list(match.gaps),
        **aliases,
    }
    if query.select_fields == ("*",):
        return full
    return {field: full[field if field in full else field.upper()] for field in query.select_fields}


def execute_query(query: Query, relation: EventRelation, *, engine: str = "relational") -> Execution:
    if query.source != relation.name:
        raise ValueError(f"Query source {query.source!r} does not match relation {relation.name!r}")
    engines = {"reference": interpret_reference, "relational": execute_temporal_join, "sqlite": execute_sqlite}
    if engine not in engines:
        raise ValueError(f"Unknown engine: {engine}")
    strict = engines[engine](query, relation.events)
    visible = tuple(sorted(strict, key=lambda m: _sort_key(m, query.order_by_score)))
    if query.limit is not None:
        visible = visible[:query.limit]
    rows = tuple(project_match(query, match) for match in visible)
    projected_manifest = fingerprint(rows)
    witnesses = tuple({
        "schema_version": "morphoql.execution-witness/0.8",
        "implementation_version": IMPLEMENTATION_VERSION,
        "engine": engine,
        "normalized_query": query.normalized(),
        "relation_fingerprint": relation.relation_fingerprint,
        "strict_candidate_count": len(strict),
        "visible_output_count": len(visible),
        "output_rank": rank,
        "event_ids": list(match.event_ids),
        "observed_gaps": list(match.gaps),
        "score": match.score,
        "projected_row": row,
        "projected_output_manifest_fingerprint": projected_manifest,
    } for rank, (match, row) in enumerate(zip(visible, rows), start=1))
    return Execution(query, visible, rows, witnesses)


def verify_execution(execution: Execution, relation: EventRelation, *, engine: str = "relational") -> bool:
    recomputed = execute_query(execution.query, relation, engine=engine)
    return deterministic_json(recomputed.rows) == deterministic_json(execution.rows) and deterministic_json(recomputed.witnesses) == deterministic_json(execution.witnesses)
