"""Shared helpers for the validation suite."""
from __future__ import annotations

import math
import re

from openprism.stats import run
from openprism.tables import make_table, parse_table

NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?|[-+]?inf|nan")


def lre(value, ref):
    """Log relative error = number of correct significant digits (capped at 15)."""
    if value is None or ref is None or (isinstance(value, float) and math.isnan(value)):
        return 0.0
    value, ref = float(value), float(ref)
    if value == ref:
        return 15.0
    err = abs(value - ref) / abs(ref) if ref != 0 else abs(value - ref)
    return max(0.0, min(15.0, -math.log10(err)))


def number(s, k=0):
    """k-th number inside a result string ('1.2 to 3.4' -> k=0: 1.2, k=1: 3.4)."""
    if isinstance(s, (int, float)):
        return float(s)
    found = NUM.findall(str(s).replace("−", "-").replace("∞", "inf"))
    return float(found[k]) if len(found) > k else float("nan")


def analyze(key, table_dict, params=None):
    p = dict(params or {})
    p["_digits"] = "full"
    return run(key, parse_table(table_dict), p)


def section(res, prefix):
    for s in res["sections"]:
        if s["title"].startswith(prefix):
            return s
    raise KeyError(f"section {prefix!r} not in {[s['title'] for s in res['sections']]}")


def cell(res, sec_prefix, row, col=1, k=0):
    """Number in section *sec_prefix*, row whose first cell starts with *row*, column *col*."""
    s = section(res, sec_prefix)
    cols = s.get("columns")
    if isinstance(col, str):
        col = cols.index(col)
    for r in s["rows"]:
        if str(r[0]).startswith(row):
            return number(r[col], k)
    raise KeyError(f"row {row!r} not in section {sec_prefix!r}: {[r[0] for r in s['rows']]}")


def kv(res, sec_prefix, row, k=0):
    return cell(res, sec_prefix, row, 1, k)


def column_table(cols, names=None):
    n = max(len(c) for c in cols)
    names = names or [f"G{i + 1}" for i in range(len(cols))]
    return make_table("t", "column", [{"name": nm, "reps": 1} for nm in names],
                      [[(c[i] if i < len(c) else None) for c in cols] for i in range(n)])


def multi_table(cols, names):
    n = len(cols[0])
    return make_table("m", "multi", [{"name": nm, "reps": 1} for nm in names], [[c[i] for c in cols] for i in range(n)])


def xy_table(x, ys, names=None):
    names = names or [f"Y{i + 1}" for i in range(len(ys))]
    return make_table("xy", "xy", [{"name": nm, "reps": 1} for nm in names], [[y[i] for y in ys] for i in range(len(x))], x=list(x))


def ct_table(rows, row_labels=None):
    k = len(rows[0])
    return make_table("c", "contingency", [{"name": f"C{j + 1}", "reps": 1} for j in range(k)], rows,
                      row_labels=row_labels or [f"R{i + 1}" for i in range(len(rows))])
