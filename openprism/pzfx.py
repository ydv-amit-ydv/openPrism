"""Read and write GraphPad Prism XML project files (.pzfx).

.pzfx is Prism's open XML format (File → Save As → .pzfx in Prism). Only the
data tables are exchanged — Prism's analyses and graphs are binary-specific and
are recreated in OpenPrism from the data.

Supported table types: XY, Column (OneWay), Grouped (TwoWay), Contingency,
Survival, Parts of whole, Multiple variables and Nested. Replicate subcolumns,
row titles, X values and excluded values are kept. Tables entered as summary
data (mean with SD/SEM and N) are imported as their means, with a warning.
"""
from __future__ import annotations

import datetime as dt
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

NS = "http://graphpad.com/prism/Prism.htm"
TYPES_IN = {"XY": "xy", "OneWay": "column", "TwoWay": "grouped", "Contingency": "contingency", "Survival": "survival",
            "PartsOfWhole": "parts", "MultipleVariables": "multi", "Nested": "nested"}
TYPES_OUT = {v: k for k, v in TYPES_IN.items()}
SUMMARY = {"SDN", "SEMN", "CVN", "SD", "SEM", "CV", "low-high", "upper-lower-limits", "SDN-SEM"}
MAX_CELLS = 2_000_000


def _tag(el):
    return el.tag.split("}", 1)[-1]


def _text(el):
    return "".join(el.itertext()).strip() if el is not None else ""


def _child(el, name):
    for c in el:
        if _tag(c) == name:
            return c
    return None


def _children(el, name):
    return [c for c in el if _tag(c) == name]


def _subcolumns(col):
    """List of subcolumns, each a list of (value text, excluded)."""
    out = []
    for sc in _children(col, "Subcolumn"):
        vals = []
        for d in _children(sc, "d"):
            v = _text(d)
            exc = d.attrib.get("Excluded", "") in ("1", "true", "True")
            if v.endswith("*"):
                v, exc = v[:-1].strip(), True
            vals.append((v, exc))
        out.append(vals)
    return out


def read(raw: bytes):
    """Return (tables, warnings). Each table is an OpenPrism table dict with an 'excluded' map."""
    if len(raw) > 60 * 1024 * 1024:
        raise ValueError("File too large")
    head = raw[:4096].decode("utf-8", errors="ignore")
    if "<!DOCTYPE" in head or "<!ENTITY" in raw.decode("utf-8", errors="ignore"):
        raise ValueError("Files with a DTD are not accepted")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise ValueError(f"Not a valid .pzfx (XML) file: {e}") from None
    if _tag(root) != "GraphPadPrismFile":
        raise ValueError("Not a GraphPad Prism XML file")
    tables, warnings = [], []
    total = 0
    for tb in root.iter():
        if _tag(tb) not in ("Table", "HugeTable"):
            continue
        name = _text(_child(tb, "Title")) or f"Table {len(tables) + 1}"
        ptype = tb.attrib.get("TableType", "OneWay")
        ttype = TYPES_IN.get(ptype)
        if ttype is None:
            warnings.append(f"“{name}”: table type {ptype} is not supported and was skipped.")
            continue
        yformat = tb.attrib.get("YFormat", "replicates")
        summary = yformat in SUMMARY
        if summary and ttype == "column" and yformat in ("SDN", "SEMN"):
            # Prism column table entered as mean, SD/SEM, N → an OpenPrism summary-data table
            rows_, cells_ = [], []
            for yc in [c for c in tb if _tag(c) in ("YColumn", "YAdvancedColumn")]:
                subs = _subcolumns(yc)
                if len(subs) < 3:
                    continue
                n_rows = max(len(sc) for sc in subs)
                for r in range(n_rows):
                    vals = [subs[j][r][0] if r < len(subs[j]) else "" for j in range(3)]
                    if any(v != "" for v in vals):
                        label = _text(_child(yc, "Title")) or f"Group {len(rows_) + 1}"
                        rows_.append(label if n_rows == 1 else f"{label} ({r + 1})")
                        cells_.append(vals)
            if cells_:
                tables.append({"name": name[:200], "type": "summary", "xTitle": "X",
                               "datasets": [{"name": "Mean", "reps": 1}, {"name": "SD" if yformat == "SDN" else "SEM", "reps": 1}, {"name": "N", "reps": 1}],
                               "rowLabels": rows_, "x": [""] * len(rows_), "cells": cells_, "excluded": {}})
                continue
        if summary:
            warnings.append(f"“{name}”: entered as summary data ({yformat}); only the means were imported.")
        rt = _child(tb, "RowTitlesColumn")
        row_titles = [v for v, _ in (_subcolumns(rt)[0] if rt is not None and _subcolumns(rt) else [])]
        xcol = _child(tb, "XColumn")
        if xcol is None:
            xcol = _child(tb, "XAdvancedColumn")
        x = [v for v, _ in (_subcolumns(xcol)[0] if xcol is not None and _subcolumns(xcol) else [])]
        datasets, columns = [], []
        for yc in [c for c in tb if _tag(c) in ("YColumn", "YAdvancedColumn")]:
            subs = _subcolumns(yc)
            if not subs:
                continue
            if summary:
                subs = subs[:1]
            datasets.append({"name": (_text(_child(yc, "Title")) or f"Data set {len(datasets) + 1}")[:200], "reps": len(subs)})
            columns.extend(subs)
        if not datasets:
            warnings.append(f"“{name}”: no data columns.")
            continue
        nrows = max([len(c) for c in columns] + [len(x), len(row_titles)])
        total += nrows * len(columns)
        if total > MAX_CELLS:
            raise ValueError("The file contains too much data.")
        cells, excluded = [], {}
        for r in range(nrows):
            row = []
            for ci, col in enumerate(columns):
                v, exc = col[r] if r < len(col) else ("", False)
                row.append(v)
                if exc and v != "":
                    excluded[f"{r},{ci}"] = True
            cells.append(row)
        if ttype == "multi" and not datasets:
            continue
        tables.append({"name": name[:200], "type": ttype, "xTitle": (_text(_child(xcol, "Title")) if xcol is not None else "") or "X",
                       "datasets": datasets, "rowLabels": (row_titles + [""] * nrows)[:nrows], "x": (x + [""] * nrows)[:nrows],
                       "cells": cells, "excluded": excluded})
    if not tables:
        raise ValueError("No data tables found in this file." + (" " + " ".join(warnings) if warnings else ""))
    return tables, warnings


def write(tables, project="OpenPrism project"):
    """OpenPrism tables (dicts as stored in the project) → .pzfx bytes."""
    now = dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           f'<GraphPadPrismFile xmlns="{NS}" PrismXMLVersion="5.00">',
           f'<Created><OriginalVersion CreatedByProgram="OpenPrism" CreatedByVersion="1" Login="" DateTime="{now}"/></Created>',
           '<InfoSequence><Ref ID="Info0" Selected="1"/></InfoSequence>',
           f'<Info ID="Info0"><Title>{escape(project)}</Title><Notes></Notes></Info>',
           '<TableSequence Selected="1">' + "".join(f'<Ref ID="Table{i}"{" Selected=\"1\"" if i == 0 else ""}/>' for i in range(len(tables))) + "</TableSequence>"]

    def d(v, exc=False):
        v = "" if v is None else str(v)
        return f'<d Excluded="1">{escape(v)}</d>' if exc and v != "" else (f"<d>{escape(v)}</d>" if v != "" else "<d/>")

    for i, t in enumerate(tables):
        ttype = t.get("type", "column")
        if ttype == "summary":  # → Prism column table entered as mean, SD (or SEM), N
            sem = "SE" in str((t.get("datasets") or [{}, {}])[1].get("name", "")).upper()
            parts = [f'<Table ID="Table{i}" XFormat="none" YFormat="{"SEMN" if sem else "SDN"}" TableType="OneWay" EVFormat="AsteriskAfterNumber">',
                     f"<Title>{escape(t.get('name', f'Table {i + 1}'))}</Title>"]
            for r, row in enumerate(t.get("cells") or []):
                if not any(str(v).strip() for v in row[:3] if v is not None):
                    continue
                label = (t.get("rowLabels") or [""] * (r + 1))[r] or f"Group {r + 1}"
                parts.append(f'<YColumn Width="81" Decimals="2" Subcolumns="3"><Title>{escape(str(label))}</Title>'
                             + "".join(f"<Subcolumn>{d(row[j] if j < len(row) else '')}</Subcolumn>" for j in range(3)) + "</YColumn>")
            parts.append("</Table>")
            out.append("".join(parts))
            continue
        ds = t.get("datasets") or []
        cells = t.get("cells") or []
        exc = t.get("excluded") or {}
        maxrep = max([int(x.get("reps", 1) or 1) for x in ds] or [1])
        has_x = ttype in ("xy", "survival")
        xf = "numbers" if has_x else "none"
        attrs = f'ID="Table{i}" XFormat="{xf}" YFormat="replicates" Replicates="{maxrep}" TableType="{TYPES_OUT.get(ttype, "OneWay")}" EVFormat="AsteriskAfterNumber"'
        parts = [f"<Table {attrs}>", f"<Title>{escape(t.get('name', f'Table {i + 1}'))}</Title>"]
        labels = t.get("rowLabels") or []
        if any(labels):
            parts.append('<RowTitlesColumn Width="81"><Subcolumn>' + "".join(d(v) for v in labels[:len(cells)]) + "</Subcolumn></RowTitlesColumn>")
        if has_x:
            parts.append(f'<XColumn Width="81" Decimals="2" Subcolumns="1"><Title>{escape(t.get("xTitle") or "X")}</Title><Subcolumn>'
                         + "".join(d(v) for v in (t.get("x") or [])[:len(cells)]) + "</Subcolumn></XColumn>")
        col = 0
        for x in ds:
            reps = int(x.get("reps", 1) or 1)
            parts.append(f'<YColumn Width="81" Decimals="2" Subcolumns="{reps}"><Title>{escape(x.get("name", ""))}</Title>')
            for k in range(reps):
                c = col + k
                parts.append("<Subcolumn>" + "".join(d(row[c] if c < len(row) else "", exc.get(f"{r},{c}")) for r, row in enumerate(cells)) + "</Subcolumn>")
            parts.append("</YColumn>")
            col += reps
        parts.append("</Table>")
        out.append("".join(parts))
    out.append("</GraphPadPrismFile>")
    return "\n".join(out).encode("utf-8")
