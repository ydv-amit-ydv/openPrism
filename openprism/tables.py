"""Parsing of the JSON data-table representation sent by the front-end.

A table looks like::

    {
      "id": "t1", "name": "Data 1", "type": "xy",
      "xTitle": "Dose",
      "datasets": [{"name": "Control", "reps": 3}, ...],
      "rowLabels": ["", ...],
      "x": ["1", "2", ...],                # only for xy / survival tables
      "cells": [["1.2", "1.3", ""], ...]   # rows x (sum of reps) strings
    }

Table types: ``xy``, ``column``, ``grouped``, ``contingency``, ``survival``,
``parts`` (parts of whole).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

import numpy as np


# Strict mathematical number format: optional sign, digits with an optional decimal
# POINT, optional exponent. No thousands separators, no decimal commas, no spaces
# inside the number, no 'inf'/'nan'/'1_000'. Anything else is not a number and is
# reported (never silently reinterpreted, e.g. '1,5' is NOT read as 15).
NUMBER_RE = re.compile(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")


def is_number_text(s) -> bool:
    return bool(NUMBER_RE.fullmatch(str(s).strip()))


def to_float(v) -> float:
    if v is None:
        return np.nan
    if isinstance(v, bool):
        return np.nan
    if isinstance(v, (int, float)):
        return float(v) if np.isfinite(v) else np.nan
    s = str(v).strip()
    if s == "" or not NUMBER_RE.fullmatch(s):
        return np.nan
    f = float(s)
    return f if np.isfinite(f) else np.nan


@dataclass
class ParsedTable:
    name: str
    type: str
    x_title: str
    names: list[str]
    row_labels: list[str]
    x: np.ndarray                      # (nrows,) float, nan where missing
    Y: list[np.ndarray] = field(default_factory=list)  # each (nrows, reps)
    raw: list = field(default_factory=list)            # the original text of each cell (same shape as Y)
    invalid: list = field(default_factory=list)        # (row, column, text) of non-empty cells that are not numbers
    x_raw: list = field(default_factory=list)          # the original text of the X column

    @property
    def nrows(self) -> int:
        return len(self.row_labels)

    def column_values(self, i: int) -> np.ndarray:
        """All finite values of data set *i* (replicates flattened row-wise)."""
        v = self.Y[i].ravel()
        return v[np.isfinite(v)]

    def row_means(self, i: int) -> np.ndarray:
        with np.errstate(all="ignore"):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return np.nanmean(self.Y[i], axis=1)

    def xy_points(self, i: int, use_means: bool = False):
        """(x, y) pairs for data set *i* with all finite values."""
        if use_means:
            y = self.row_means(i)
            m = np.isfinite(self.x) & np.isfinite(y)
            return self.x[m], y[m]
        reps = self.Y[i].shape[1]
        xx = np.repeat(self.x, reps)
        yy = self.Y[i].ravel()
        m = np.isfinite(xx) & np.isfinite(yy)
        return xx[m], yy[m]

    def shifted(self, idx):
        """Values of data sets *idx* minus a common offset, subtracted in exact decimal arithmetic.

        Returns (offset, [array per data set]). Spread statistics (SD, sums of squares,
        F, t...) are shift-invariant, so computing them from these deviations keeps
        full precision even for data such as 1000000000000.4, which a double cannot
        hold to more than ~4 decimals after the point (NIST StRD SmLs07-09, NumAcc4).
        """
        offset = None
        out = []
        for i in idx:
            vals = []
            raw = self.raw[i].ravel() if i < len(self.raw) else None
            flat = self.Y[i].ravel()
            for k, v in enumerate(flat):
                if not np.isfinite(v):
                    continue
                d = None
                if raw is not None:
                    try:
                        d = Decimal(str(raw[k]).strip())
                    except (InvalidOperation, ValueError):
                        d = None
                if d is None or not d.is_finite():
                    d = Decimal(float(v))
                if offset is None:
                    offset = d
                vals.append(float(d - offset))
            out.append(np.array(vals, float))
        return (float(offset) if offset is not None else 0.0), out

    def nonempty_datasets(self) -> list[int]:
        return [i for i in range(len(self.Y)) if np.isfinite(self.Y[i]).any()]


def parse_table(t: dict) -> ParsedTable:
    datasets = t.get("datasets") or []
    cells = t.get("cells") or []
    row_labels = list(t.get("rowLabels") or [])
    nrows = max(len(cells), len(row_labels), len(t.get("x") or []))
    row_labels += [""] * (nrows - len(row_labels))
    xs = list(t.get("x") or []) + [""] * nrows
    x = np.array([to_float(v) for v in xs[:nrows]], dtype=float)

    Y = []
    raw = []
    invalid = []
    col = 0
    for ds in datasets:
        reps = max(1, int(ds.get("reps", 1) or 1))
        arr = np.full((nrows, reps), np.nan)
        txt = np.full((nrows, reps), "", dtype=object)
        for r in range(nrows):
            row = cells[r] if r < len(cells) else []
            for k in range(reps):
                c = col + k
                if c < len(row):
                    arr[r, k] = to_float(row[c])
                    if np.isnan(arr[r, k]) and row[c] not in (None, "") and str(row[c]).strip() != "" and len(invalid) < 1000:
                        invalid.append((r, c, str(row[c])[:40]))
                    txt[r, k] = row[c] if isinstance(row[c], str) else ("" if row[c] is None else repr(row[c]))
        Y.append(arr)
        raw.append(txt)
        col += reps

    return ParsedTable(
        name=t.get("name", "Data"),
        type=t.get("type", "column"),
        x_title=t.get("xTitle", "X"),
        names=[d.get("name") or f"Data set {i + 1}" for i, d in enumerate(datasets)],
        row_labels=[str(r) if r not in (None, "") else f"Row {i + 1}" for i, r in enumerate(row_labels)],
        x=x,
        Y=Y,
        raw=raw,
        invalid=invalid + [(r, "X", str(v)[:40]) for r, v in enumerate(xs[:nrows]) if v not in (None, "") and str(v).strip() and np.isnan(x[r])][:100],
        x_raw=[v if isinstance(v, str) else ("" if v is None else repr(v)) for v in xs[:nrows]],
    )


def make_table(name, ttype, datasets, cells, x=None, row_labels=None, x_title="X"):
    """Build a front-end table dict (used by analyses that output new tables)."""
    nrows = len(cells)

    def fmt(v):
        if v is None:
            return ""
        if isinstance(v, str):  # already text: keep every digit exactly as given
            return v.strip()
        try:
            f = float(v)
        except (TypeError, ValueError):
            return str(v)
        if not np.isfinite(f):
            return ""
        return f"{f:.15g}"

    return {
        "name": name,
        "type": ttype,
        "xTitle": x_title,
        "datasets": datasets,
        "rowLabels": list(row_labels) if row_labels is not None else [""] * nrows,
        "x": [fmt(v) for v in x] if x is not None else [""] * nrows,
        "cells": [[fmt(v) for v in row] for row in cells],
    }
