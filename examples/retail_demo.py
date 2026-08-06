"""Generate a retail-like sawtooth series and query its wavelet events."""
from __future__ import annotations

import numpy as np
import pandas as pd

from morphoql import EventRelation, execute_query, parse
from wavelet_events import extract_maximum_lines, retail_residual

rng = np.random.default_rng(20260806)
dates = pd.date_range("2025-01-01", periods=365, freq="D")
weekday = np.array([-42, -24, -10, 4, 24, 52, -6], dtype=float)
sales = 220 + weekday[dates.dayofweek] + 8 * np.sin(np.arange(365) * 2 * np.pi / 365) + rng.normal(0, 8, 365)
sales[68:78] += 60
sales[134:138] += 90
residual = retail_residual(sales, dates=dates)
events = extract_maximum_lines(residual, series_id="retail")
relation = EventRelation("sales", events)
query = parse("SELECT MATCH_START, MATCH_END, SCORE FROM sales MATCH (EDGE UP THEN EDGE DOWN WITHIN 8d..14d) ORDER BY SCORE DESC LIMIT 5;")
for row in execute_query(query, relation).rows:
    print(dict(row))
