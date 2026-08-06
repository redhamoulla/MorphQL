"""Compact extraction pipelines used by the MorphoQL examples.

These functions turn a regularly sampled one-dimensional series into signed
MorphoQL events. They are research-reference implementations, not production
streaming detectors.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

from morphoql import Event, ProvenanceNode

DEFAULT_SCALES = (1.0, 2.0, 3.0, 4.0, 5.0, 7.0, 10.0, 14.0)


def robust_standardize(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    median = np.nanmedian(values)
    mad = np.nanmedian(np.abs(values - median))
    return (values - median) / (1.4826 * mad + 1e-6)


def retail_residual(values: Iterable[float], *, dates: Iterable[pd.Timestamp] | None = None) -> np.ndarray:
    x = np.asarray(list(values), dtype=float)
    if dates is None:
        dates = pd.date_range("2000-01-03", periods=len(x), freq="D")
    index = pd.DatetimeIndex(dates)
    series = pd.Series(x, index=index)
    global_median = float(series.median())
    weekday_effect = series.groupby(index.dayofweek).median() - global_median
    deseasonalized = series - index.dayofweek.map(weekday_effect).to_numpy()
    baseline = deseasonalized.rolling(63, center=True, min_periods=15).median().bfill().ffill()
    return robust_standardize((deseasonalized - baseline).to_numpy())


def _nodes(coef: np.ndarray, scale: float, threshold: float, distance: int, branch: str, scale_index: int) -> list[tuple[int, int, float, ProvenanceNode]]:
    output: list[tuple[int, int, float, ProvenanceNode]] = []
    for sign in (1, -1):
        peaks, props = find_peaks(sign * coef, height=threshold, distance=distance)
        for position, height in zip(peaks, props["peak_heights"]):
            node = ProvenanceNode(scale, float(position), float(sign * height), branch, scale_index)
            output.append((int(position), sign, float(height), node))
    return output


def extract_first_difference(standardized: np.ndarray, *, series_id: str = "series_0", threshold: float = 1.0) -> tuple[Event, ...]:
    delta = np.diff(np.asarray(standardized, dtype=float), prepend=float(standardized[0]))
    nodes = _nodes(delta, 0.0, threshold, 1, "DirectDelta", 0)
    return tuple(Event(float(t), sign, strength, 1.0, 0.0, 0.0, series_id, (node,), "DirectDelta") for t, sign, strength, node in nodes)


def extract_dog(standardized: np.ndarray, *, series_id: str = "series_0", sigma: float = 1.5, threshold: float = 1.0) -> tuple[Event, ...]:
    coef = sigma * gaussian_filter1d(np.asarray(standardized, dtype=float), sigma=sigma, order=1, mode="nearest")
    coef = robust_standardize(coef)
    nodes = _nodes(coef, sigma, threshold, 2, "DoGMono", 0)
    return tuple(Event(float(t), sign, strength, 1.0, sigma, sigma, series_id, (node,), "DoGMono") for t, sign, strength, node in nodes)


def multiscale_nodes(standardized: np.ndarray, *, scales: Iterable[float] = DEFAULT_SCALES, threshold: float = 0.8, branch: str = "WTMM") -> list[tuple[int, int, float, ProvenanceNode]]:
    output: list[tuple[int, int, float, ProvenanceNode]] = []
    x = np.asarray(standardized, dtype=float)
    for scale_index, scale in enumerate(scales):
        coef = scale * gaussian_filter1d(x, sigma=scale, order=1, mode="nearest")
        coef = robust_standardize(coef)
        output.extend(_nodes(coef, scale, threshold, max(1, int(scale // 2)), branch, scale_index))
    return output


def extract_multiscale_maxima(standardized: np.ndarray, *, series_id: str = "series_0", node_threshold: float = 0.8, event_threshold: float = 0.6) -> tuple[Event, ...]:
    nodes = multiscale_nodes(standardized, threshold=node_threshold, branch="WTMMAggregated")
    length = len(standardized)
    scores = {1: np.zeros(length), -1: np.zeros(length)}
    by_key: dict[tuple[int, int], list[ProvenanceNode]] = {}
    for t, sign, strength, node in nodes:
        scores[sign][t] += strength
        by_key.setdefault((t, sign), []).append(node)
    output: list[Event] = []
    for sign in (1, -1):
        smooth = gaussian_filter1d(scores[sign], sigma=1.2)
        peaks, props = find_peaks(smooth, height=event_threshold, distance=2)
        for t, height in zip(peaks, props["peak_heights"]):
            support = tuple(node for (time, s), values in by_key.items() if s == sign and abs(time - t) <= 1 for node in values)
            if not support:
                continue
            scales = [node.scale for node in support]
            output.append(Event(float(t), sign, float(height), len(set(scales)) / len(DEFAULT_SCALES), min(scales), max(scales), series_id, support, "WTMMAggregated"))
    return tuple(output)


@dataclass
class _Line:
    sign: int
    nodes: list[ProvenanceNode]

    @property
    def last(self) -> ProvenanceNode:
        return self.nodes[-1]


def extract_maximum_lines(standardized: np.ndarray, *, series_id: str = "series_0", node_threshold: float = 0.65, event_threshold: float = 0.30, min_scales: int = 2) -> tuple[Event, ...]:
    nodes = multiscale_nodes(standardized, threshold=node_threshold, branch="WTMMLines")
    by_sign_scale: dict[tuple[int, int], list[tuple[float, ProvenanceNode]]] = {}
    for _, sign, strength, node in nodes:
        by_sign_scale.setdefault((sign, int(node.scale_index or 0)), []).append((strength, node))
    lines: list[_Line] = []
    for sign in (1, -1):
        active: list[_Line] = []
        finished: list[_Line] = []
        for scale_index, scale in enumerate(DEFAULT_SCALES):
            candidates = by_sign_scale.get((sign, scale_index), [])
            assignments: list[tuple[float, int, int]] = []
            for li, line in enumerate(active):
                last_index = int(line.last.scale_index or 0)
                if scale_index - last_index > 2:
                    continue
                tolerance = max(2.0, 0.65 * scale + 1.0)
                for ni, (strength, node) in enumerate(candidates):
                    distance = abs(node.time - line.last.time)
                    if distance <= tolerance:
                        cost = distance / (tolerance + 1e-6) - 0.03 * strength
                        assignments.append((cost, li, ni))
            used_lines: set[int] = set(); used_nodes: set[int] = set()
            for _, li, ni in sorted(assignments):
                if li in used_lines or ni in used_nodes:
                    continue
                active[li].nodes.append(candidates[ni][1]); used_lines.add(li); used_nodes.add(ni)
            still_active: list[_Line] = []
            for line in active:
                if scale_index - int(line.last.scale_index or 0) <= 2:
                    still_active.append(line)
                else:
                    finished.append(line)
            active = still_active
            for ni, (_, node) in enumerate(candidates):
                if ni not in used_nodes:
                    active.append(_Line(sign, [node]))
        finished.extend(active)
        lines.extend(finished)
    events: list[Event] = []
    for line in lines:
        distinct = sorted({node.scale for node in line.nodes})
        if len(distinct) < min_scales:
            continue
        strengths = np.asarray([abs(node.coefficient) for node in line.nodes])
        fine = [node for node in line.nodes if node.scale <= 3]
        representative = float(np.average([n.time for n in fine], weights=[abs(n.coefficient) for n in fine])) if fine else line.nodes[0].time
        persistence = len(distinct) / len(DEFAULT_SCALES)
        strength = float(np.median(strengths) * (1 + 1.7 * persistence) + 0.15 * strengths.max() - 0.03 * np.std([n.time for n in line.nodes]))
        if strength >= event_threshold:
            events.append(Event(representative, line.sign, strength, persistence, min(distinct), max(distinct), series_id, tuple(sorted(line.nodes, key=lambda n: (n.scale, n.time))), "WTMMLines"))
    return tuple(sorted(events, key=lambda e: (e.time, e.sign)))
