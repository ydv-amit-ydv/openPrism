"""Summary data the front-end needs to draw graphs (means, error bars...)."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from .descriptive import summarize


def _err(v: np.ndarray, kind: str):
    n = len(v)
    if n == 0:
        return None, None, None
    if kind in ("median_iqr", "median_range", "median_ci"):
        c = float(np.median(v))
    elif kind == "geomean_gsd":
        c = float(np.exp(np.log(v).mean())) if np.all(v > 0) else float(np.mean(v))
    else:
        c = float(np.mean(v))
    if n < 2 or kind == "none":
        return c, 0.0, 0.0
    sd = float(np.std(v, ddof=1))
    if kind == "sd":
        return c, sd, sd
    if kind == "sem":
        s = sd / math.sqrt(n)
        return c, s, s
    if kind == "ci95":
        h = stats.t.ppf(0.975, n - 1) * sd / math.sqrt(n)
        return c, h, h
    if kind == "range":
        return c, float(v.max() - c), float(c - v.min())
    if kind == "median_iqr":
        q1, q3 = np.percentile(v, [25, 75])
        return c, float(q3 - c), float(c - q1)
    if kind == "median_range":
        return c, float(v.max() - c), float(c - v.min())
    if kind == "median_ci":
        s = np.sort(v)
        j = max(1, int(stats.binom.ppf(0.025, n, 0.5)))
        return c, float(s[n - j] - c), float(c - s[j - 1])
    if kind == "geomean_gsd":
        if np.all(v > 0):
            g = math.exp(np.log(v).std(ddof=1))
            return c, c * g - c, c - c / g
        return c, sd, sd
    return c, sd, sd


def _clean(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return f if math.isfinite(f) else None


def graph_data(table, error="sem"):
    out = {"type": table.type, "names": table.names, "rowLabels": table.row_labels,
           "x": [_clean(v) for v in table.x], "datasets": []}
    for i, arr in enumerate(table.Y):
        vals = table.column_values(i)
        s = summarize(vals) if len(vals) else {"n": 0}
        c, up, lo = _err(vals, error)
        rows = []
        for r in range(arr.shape[0]):
            rv = arr[r][np.isfinite(arr[r])]
            rc, ru, rl = _err(rv, error) if len(rv) else (None, None, None)
            rows.append({"center": _clean(rc), "plus": _clean(ru), "minus": _clean(rl), "n": int(len(rv)),
                         "values": [float(v) for v in rv]})
        out["datasets"].append({
            "name": table.names[i],
            "values": [float(v) for v in vals],
            "center": _clean(c), "plus": _clean(up), "minus": _clean(lo),
            "summary": {k: _clean(v) for k, v in s.items()},
            "rows": rows,
        })
    return out
