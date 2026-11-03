"""Recognise the layout of an imported spreadsheet and turn it into the right kind of data table.

Newcomers rarely know what an "XY" or "Column" table is, and most files exported by Excel,
lab instruments or statistics programs are in "long" format (one row per measurement: a group
column and a value column). ``inspect`` looks at the columns, proposes the table type that fits
best, explains why in plain words and lists the other sensible ways to read the file; ``build``
creates the table for the option the user picks.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .tables import is_number_text, make_table

MAX_LEVELS = 40          # a text column with more distinct values is treated as labels, not groups

TIME_WORDS = re.compile(r"time|day|week|month|year|hour|min|surv|follow|durat|age_at|tte|os\b|pfs|dfs|efs", re.I)
EVENT_WORDS = re.compile(r"event|status|death|dead|died|censor|outcome|relapse|recur|progress|fail|vital", re.I)
X_WORDS = re.compile(r"^(x|time|t|dose|conc|concentration|log|minutes?|hours?|days?|age|temperature|temp|wavelength|ph|position|distance|depth)\b", re.I)
SUMMARY_MEAN = re.compile(r"\bmean\b|\baverage\b|\bavg\b", re.I)
SUMMARY_SD = re.compile(r"\bsd\b|\bs\.d\.|\bstd|\bsem\b|\bse\b|\bs\.e\.", re.I)
SUMMARY_N = re.compile(r"^n$|\bn\b|\bcount\b|\bsize\b", re.I)


# ---------------------------------------------------------------- reading
def read_frame(raw: bytes, filename: str) -> pd.DataFrame:
    """Read CSV/TSV/Excel; the first row is used as titles when it looks like titles."""
    if filename.lower().endswith((".xlsx", ".xls")):
        import io
        df = pd.read_excel(io.BytesIO(raw), header=None, nrows=200_001, dtype=object)
    else:
        import csv
        import io
        text = raw.decode("utf-8-sig", errors="replace")
        sample = text[:20000]
        sep = "\t" if sample.count("\t") > sample.count(",") and sample.count("\t") > sample.count(";") else (
            ";" if sample.count(";") > sample.count(",") else ",")
        rows = list(csv.reader(io.StringIO(text), delimiter=sep))
        rows = [r for r in rows if any(c.strip() for c in r)][:200_001]
        width = max((len(r) for r in rows), default=0)
        df = pd.DataFrame([r + [""] * (width - len(r)) for r in rows], dtype=object)
    df = df.dropna(how="all").dropna(axis=1, how="all")
    df = df.map(lambda v: None if v is None or (isinstance(v, float) and np.isnan(v)) or (isinstance(v, str) and not v.strip()) else v)
    df = df.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    if df.empty:
        raise ValueError("The file contains no data.")
    first = df.iloc[0].tolist()
    rest = df.iloc[1:]
    header = False
    if len(df) > 1:
        text_first = sum(1 for v in first if v is not None and not _is_num(v))
        num_cols_below = sum(1 for c in df.columns if rest[c].dropna().map(_is_num).mean() > 0.8) if len(rest) else 0
        header = text_first > 0 and (text_first >= num_cols_below or all(v is None or not _is_num(v) for v in first))
    if header:
        names, seen = [], {}
        for j, v in enumerate(first):
            nm = str(v).strip() if v is not None and not (isinstance(v, float) and np.isnan(v)) and str(v).strip() else ("Row titles" if j == 0 else f"Column {j + 1}")
            seen[nm] = seen.get(nm, 0) + 1
            names.append(nm if seen[nm] == 1 else f"{nm} ({seen[nm]})")
        df = rest.reset_index(drop=True)
        df.columns = [n[:100] for n in names]
    else:
        df.columns = [f"Column {j + 1}" for j in range(df.shape[1])]
    return df


def _is_num(v) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float, np.integer, np.floating)):
        return bool(np.isfinite(v))
    return is_number_text(str(v).strip())


def _num(v):
    return float(v) if _is_num(v) else None


# ---------------------------------------------------------------- describing columns
def describe(df: pd.DataFrame) -> list[dict]:
    out = []
    n = len(df)
    for c in df.columns:
        vals = df[c].dropna().tolist()
        k = len(vals)
        nums = [float(v) for v in vals if _is_num(v)]
        numeric = k > 0 and len(nums) >= 0.9 * k
        info = {"name": c, "filled": k, "numeric": numeric}
        if numeric:
            arr = np.array(nums)
            uniq = np.unique(arr)
            info.update(binary=bool(len(uniq) <= 2 and set(uniq.tolist()) <= {0.0, 1.0}),
                        codes=bool(len(uniq) <= 4 and set(uniq.tolist()) <= {0.0, 1.0, 2.0, 3.0}),
                        integer=bool(np.all(arr == np.round(arr))), nonneg=bool(np.all(arr >= 0)),
                        increasing=bool(len(uniq) >= 3 and np.all(np.diff(arr) >= 0)),
                        median=float(np.median(np.abs(arr))) if len(arr) else 0.0, distinct=int(len(uniq)))
        else:
            levels = list(dict.fromkeys(str(v).strip() for v in vals))
            info.update(levels=levels[:MAX_LEVELS + 1], distinct=len(levels),
                        categorical=1 < len(levels) <= MAX_LEVELS and len(levels) < max(k, 1),
                        labels=len(levels) == k)
        out.append(info)
    return out


# ---------------------------------------------------------------- options
def _opt(ttype, layout, title, why, **mapping):
    return {"type": ttype, "layout": layout, "title": title, "why": why, "mapping": mapping}


def options(df: pd.DataFrame) -> list[dict]:
    """All sensible ways to read this file, best first."""
    cols = describe(df)
    num = [c for c in cols if c["numeric"]]
    cat = [c for c in cols if not c["numeric"] and c.get("categorical")]
    lab = [c for c in cols if not c["numeric"] and c.get("labels")]
    names = [c["name"] for c in cols]
    opts = []

    # summary data: mean / SD|SEM / n columns
    mean = next((c for c in num if SUMMARY_MEAN.search(c["name"])), None)
    sd = next((c for c in num if SUMMARY_SD.search(c["name"])), None)
    nn = next((c for c in num if SUMMARY_N.search(c["name"]) and c.get("integer")), None)
    if mean and sd and nn:
        grp = (lab or cat or [None])[0]
        opts.append(_opt("summary", "summary", "Summary data (mean, SD/SEM and n per group)",
                         f"the columns “{mean['name']}”, “{sd['name']}” and “{nn['name']}” hold a mean, a spread and a group size",
                         group=grp["name"] if grp else None, mean=mean["name"], sd=sd["name"], n=nn["name"]))

    # survival in long format: a time column + an event (0/1) column (+ optional group)
    times = [c for c in num if c.get("nonneg") and not c.get("codes") and (TIME_WORDS.search(c["name"]) or True)]
    events = [c for c in num if c.get("codes") and EVENT_WORDS.search(c["name"])] or \
             [c for c in num if c.get("binary") and EVENT_WORDS.search(c["name"])]
    if events and times:
        tcol = next((c for c in times if TIME_WORDS.search(c["name"])), times[0])
        ecol = events[0]
        grp = cat[0]["name"] if cat else None
        opts.append(_opt("survival", "long", "Survival (time until an event)",
                         f"“{tcol['name']}” looks like follow-up time and “{ecol['name']}” records whether the event happened (1) or not (0)"
                         + (f"; “{grp}” gives the groups to compare" if grp else ""),
                         time=tcol["name"], event=ecol["name"], group=grp))

    # long format: categorical column(s) + one numeric value column
    if len(cat) >= 1 and len(num) == 1:
        v = num[0]["name"]
        g1 = cat[0]["name"]
        opts.append(_opt("column", "long", f"Compare groups — one column per {g1}",
                         f"“{g1}” contains group names ({', '.join(cat[0]['levels'][:4])}{'…' if cat[0]['distinct'] > 4 else ''}) "
                         f"and “{v}” the measured values; each group becomes one column",
                         group=g1, value=v))
        if len(cat) >= 2:
            g2 = cat[1]["name"]
            opts.insert(len(opts) - 1, _opt("grouped", "long", f"Two factors — {g1} × {g2}",
                                            f"there are two grouping columns (“{g1}” and “{g2}”) and one value column (“{v}”): "
                                            f"rows become {g1}, columns become {g2}, repeated values become replicates",
                                            rows=g1, cols=g2, value=v))
    if len(cat) >= 2 and not num:
        a, b = cat[0]["name"], cat[1]["name"]
        opts.append(_opt("contingency", "long", f"Count combinations of {a} and {b}",
                         f"“{a}” and “{b}” are categories for each subject; OpenPrism counts how many subjects fall into each combination",
                         rows=a, cols=b))
    if len(cat) == 1 and len(num) >= 2:
        g1 = cat[0]["name"]
        opts.append(_opt("grouped", "bygroup", f"Groups ({g1}) × measured variables",
                         f"“{g1}” names the group of each row and the other columns are measurements: rows become groups, "
                         "columns stay variables and the rows of each group become replicates",
                         rows=g1))

    # wide layouts
    first = cols[0]
    others_num = all(c["numeric"] for c in cols[1:]) and len(cols) > 1
    if lab and first is lab[0] and others_num:
        counts = all(c.get("integer") and c.get("nonneg") for c in cols[1:])
        small = len(df) <= 30 and len(cols) <= 11
        if counts and small:
            opts.append(_opt("contingency", "wide", "Counts in categories (contingency table)",
                             f"the first column names the rows ({', '.join(first['levels'][:3])}…) and the other columns contain whole-number counts",
                             ))
        if len(cols) == 2 and all(c.get("nonneg") for c in cols[1:]):
            opts.append(_opt("parts", "wide", "Parts of a whole (pie chart)",
                             "one label column and one column of amounts that add up to a total"))
        opts.append(_opt("grouped", "wide", "Rows × columns (grouped)",
                         f"the first column names the rows and the other columns are groups"))
    if all(c["numeric"] for c in cols):
        xnamed = bool(X_WORDS.search(first["name"]))
        scales = [c["median"] for c in cols if c["median"] > 0]
        spread = (max(scales) / min(scales)) if scales else 1
        multi_like = any(c.get("binary") for c in cols) or len(cols) > 8 or spread > 50
        col_opt = _opt("column", "wide", "Compare groups — each column is a group",
                       f"every column holds numbers of the same kind ({', '.join(names[:3])}{'…' if len(names) > 3 else ''}), one column per group")
        xy_opt = _opt("xy", "wide", f"X and Y — “{first['name']}” is X",
                      (f"the first column “{first['name']}” increases steadily" if first.get("increasing") else
                       f"the first column “{first['name']}” sounds like a dose / time / concentration" if xnamed else
                       f"use the first column “{first['name']}” as X")
                      + ", and the other columns are Y values measured at each X")
        multi_opt = _opt("multi", "wide", "Several variables per subject",
                         "each row is one subject and the columns are different variables"
                         + (" (one of them is a yes/no 0–1 variable)" if any(c.get("binary") for c in cols) else "")
                         + (" with very different scales" if spread > 50 else ""))
        other_med = [c["median"] for c in cols[1:] if c["median"] > 0]
        differs = bool(other_med) and first["median"] > 0 and (max(first["median"] / np.median(other_med), np.median(other_med) / first["median"]) > 3)
        if len(cols) >= 2 and first.get("increasing") and (xnamed or differs or first.get("distinct", 0) >= 6):
            order = [xy_opt, col_opt, multi_opt]
        elif multi_like:
            order = [multi_opt, xy_opt, col_opt] if xnamed else [multi_opt, col_opt, xy_opt]
        elif xnamed and len(cols) >= 2:
            order = [xy_opt, col_opt, multi_opt]
        else:
            order = [col_opt, xy_opt, multi_opt]
        opts += order if len(cols) >= 2 else [col_opt]
    elif not opts or (num and len(cat) + len(lab) >= 1):
        opts.append(_opt("multi", "wide", "Several variables per subject",
                         "each row is one subject and the columns are different variables; text categories are coded as numbers"))
    if not any(o["type"] == "column" and o["layout"] == "wide" for o in opts) and num:
        opts.append(_opt("column", "wide", "Each numeric column is a group", "only the columns that contain numbers are used, one group per column"))
    # de-duplicate (type, layout)
    seen, out = set(), []
    for o in opts:
        k = (o["type"], o["layout"], tuple(sorted((o["mapping"] or {}).items(), key=str)))
        if k not in seen:
            seen.add(k)
            out.append(o)
    return out


# ---------------------------------------------------------------- building tables
def _code(series):
    """Text categories → 1, 2, 3 … (returns codes, mapping text)."""
    levels = list(dict.fromkeys(str(v).strip() for v in series if v is not None))
    m = {lv: i + 1 for i, lv in enumerate(levels)}
    return [m.get(str(v).strip()) if v is not None else None for v in series], ", ".join(f"{k} = {v}" for k, v in m.items())


def build(df: pd.DataFrame, name: str, opt: dict) -> tuple[dict, list[str]]:
    t, layout, m = opt["type"], opt["layout"], opt.get("mapping") or {}
    cols = list(df.columns)
    warns: list[str] = []
    if layout == "long" and t == "column":
        g, v = m["group"], m["value"]
        levels = list(dict.fromkeys(str(x).strip() for x in df[g] if x is not None))
        buckets = {lv: [] for lv in levels}
        for gv, vv in zip(df[g], df[v]):
            if gv is not None and vv is not None:
                buckets[str(gv).strip()].append(vv)
        nr = max((len(b) for b in buckets.values()), default=0)
        cells = [[(buckets[lv][i] if i < len(buckets[lv]) else None) for lv in levels] for i in range(nr)]
        return make_table(name, "column", [{"name": lv[:100], "reps": 1} for lv in levels], cells), warns
    if layout == "long" and t == "grouped":
        r, c, v = m["rows"], m["cols"], m["value"]
        rl = list(dict.fromkeys(str(x).strip() for x in df[r] if x is not None))
        cl = list(dict.fromkeys(str(x).strip() for x in df[c] if x is not None))
        cell = {}
        for a, b, val in zip(df[r], df[c], df[v]):
            if a is not None and b is not None and val is not None:
                cell.setdefault((str(a).strip(), str(b).strip()), []).append(val)
        reps = max((len(x) for x in cell.values()), default=1)
        rows = [[(cell.get((a, b), [])[k] if k < len(cell.get((a, b), [])) else None) for b in cl for k in range(reps)] for a in rl]
        return make_table(name, "grouped", [{"name": b[:100], "reps": reps} for b in cl], rows, row_labels=rl), warns
    if layout == "bygroup":
        r = m["rows"]
        vars_ = [c for c in cols if c != r and describe(df[[c]])[0]["numeric"]]
        rl = list(dict.fromkeys(str(x).strip() for x in df[r] if x is not None))
        cell = {}
        for _, row in df.iterrows():
            if row[r] is None:
                continue
            for v in vars_:
                if row[v] is not None:
                    cell.setdefault((str(row[r]).strip(), v), []).append(row[v])
        reps = max((len(x) for x in cell.values()), default=1)
        rows = [[(cell.get((a, v), [])[k] if k < len(cell.get((a, v), [])) else None) for v in vars_ for k in range(reps)] for a in rl]
        return make_table(name, "grouped", [{"name": v[:100], "reps": reps} for v in vars_], rows, row_labels=rl), warns
    if layout == "long" and t == "contingency":
        a, b = m["rows"], m["cols"]
        sub = df[[a, b]].dropna()
        ct = pd.crosstab(sub[a].map(lambda x: str(x).strip()), sub[b].map(lambda x: str(x).strip()))
        ra = [lv for lv in dict.fromkeys(str(x).strip() for x in df[a] if x is not None)]
        cb = [lv for lv in dict.fromkeys(str(x).strip() for x in df[b] if x is not None)]
        ct = ct.reindex(index=ra, columns=cb, fill_value=0)
        return make_table(name, "contingency", [{"name": c[:100], "reps": 1} for c in cb], ct.values.tolist(), row_labels=ra), warns
    if layout == "long" and t == "survival":
        tc, ec, g = m["time"], m["event"], m.get("group")
        groups = list(dict.fromkeys(str(x).strip() for x in df[g] if x is not None)) if g else ["All subjects"]
        xs, cells = [], []
        for _, row in df.iterrows():
            if row[tc] is None or row[ec] is None or (g and row[g] is None):
                continue
            gi = groups.index(str(row[g]).strip()) if g else 0
            xs.append(row[tc])
            cells.append([row[ec] if j == gi else None for j in range(len(groups))])
        return make_table(name, "survival", [{"name": s[:100], "reps": 1} for s in groups], cells, x=xs, x_title=tc), warns
    if layout == "summary":
        g, mean, sd, n = m.get("group"), m["mean"], m["sd"], m["n"]
        labels = [str(x).strip() if x is not None else "" for x in df[g]] if g else [f"Group {i + 1}" for i in range(len(df))]
        return make_table(name, "summary", [{"name": "Mean", "reps": 1}, {"name": "SEM" if re.search(r"se", sd, re.I) and not re.search(r"sd", sd, re.I) else "SD", "reps": 1},
                                            {"name": "N", "reps": 1}],
                          df[[mean, sd, n]].values.tolist(), row_labels=labels), warns
    # wide layouts
    values = df.values.tolist()
    if t in ("xy", "survival"):
        return make_table(name, t, [{"name": c, "reps": 1} for c in cols[1:]], [r[1:] for r in values], x=[r[0] for r in values], x_title=cols[0]), warns
    if t in ("grouped", "contingency", "parts"):
        return make_table(name, t, [{"name": c, "reps": 1} for c in cols[1:]], [r[1:] for r in values],
                          row_labels=[str(r[0])[:200] if r[0] is not None else "" for r in values]), warns
    if t == "multi":
        info = describe(df)
        out_cols = []
        for c, d in zip(cols, info):
            if d["numeric"]:
                out_cols.append((c, df[c].tolist()))
            elif d.get("categorical"):
                codes, legend = _code(df[c].tolist())
                out_cols.append((c, codes))
                warns.append(f"“{c}” was coded as numbers: {legend}.")
            else:
                warns.append(f"“{c}” contains text labels and was left out.")
        return make_table(name, "multi", [{"name": c, "reps": 1} for c, _ in out_cols],
                          [[col[i] for _, col in out_cols] for i in range(len(df))]), warns
    numeric = [c for c, d in zip(cols, describe(df)) if d["numeric"]]
    left = [c for c in cols if c not in numeric]
    if left:
        warns.append(f"Text column(s) {', '.join('“' + c + '”' for c in left)} were left out.")
    return make_table(name, "column", [{"name": c, "reps": 1} for c in numeric], df[numeric].values.tolist()), warns


DECIMAL_COMMA = re.compile(r"^[+-]?[0-9]+,[0-9]+$")


def notices(df: pd.DataFrame) -> list[str]:
    vals = [str(v).strip() for v in df.values.ravel() if v is not None][:20000]
    dc = [v for v in vals if DECIMAL_COMMA.match(v)]
    out = []
    if dc and len(dc) >= 0.2 * max(1, sum(1 for v in vals if _is_num(v) or DECIMAL_COMMA.match(v))):
        out.append(f"Some numbers use a decimal comma (e.g. “{dc[0]}”). OpenPrism needs a decimal point (“{dc[0].replace(',', '.')}”), "
                   "so these cells are not read as numbers. Export the file with a decimal point (or replace , by . in those "
                   "columns) and import it again.")
    return out


def inspect(raw: bytes, filename: str, preview_rows: int = 6) -> dict:
    from pathlib import Path
    df = read_frame(raw, filename)
    opts = options(df)
    name = Path(filename).stem[:100] or "Imported"
    out = []
    for i, o in enumerate(opts):
        try:
            tbl, warns = build(df.head(400), name, o)
        except Exception:  # noqa: BLE001 - an option that does not apply is simply not offered
            continue
        if not tbl["datasets"] or not any(str(c).strip() for row in tbl["cells"] for c in row):
            continue                         # nothing usable in this arrangement
        prev = {k: tbl[k] for k in ("type", "xTitle", "datasets")}
        prev["cells"] = tbl["cells"][:preview_rows]
        prev["rowLabels"] = tbl["rowLabels"][:preview_rows]
        prev["x"] = tbl["x"][:preview_rows]
        out.append({**o, "id": i, "preview": prev, "warnings": warns})
    return {"columns": list(df.columns), "rows": len(df), "notices": notices(df), "sample": df.head(preview_rows).where(df.head(preview_rows).notna(), None).values.tolist(),
            "options": out}
