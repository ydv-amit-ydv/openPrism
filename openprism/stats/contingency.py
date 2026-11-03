"""Contingency tables, parts of whole, transforms and normalization."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from ..tables import make_table
from .common import Result, fmt, fmt_p, require, sig, stars
from .descriptive import selected


def _matrix(table, idx):
    M = np.column_stack([table.Y[i][:, 0] for i in idx])
    keep = np.any(np.isfinite(M), axis=1)
    M = np.nan_to_num(M[keep])
    labels = [lab for lab, k in zip(table.row_labels, keep) if k]
    return M, labels


def contingency(table, params):
    idx = selected(table, params)
    require(len(idx) >= 2, "Contingency analysis needs at least two outcome columns.")
    M, labels = _matrix(table, idx)
    require(M.shape[0] >= 2, "Need at least two rows (groups).")
    alpha = float(params.get("alpha", 0.05))
    yates = bool(params.get("yates", False))
    r = Result("Contingency table analysis")
    chi, p, dof, expected = stats.chi2_contingency(M, correction=yates and M.shape == (2, 2))
    N = M.sum()
    out = [("Chi-square", chi), ("df", dof), ("P value", fmt_p(p)), ("P value summary", stars(p, alpha)),
           (f"Significant (P < {alpha})?", sig(p, alpha)), ("Total N", N),
           ("Cramér's V", math.sqrt(chi / (N * (min(M.shape) - 1))) if N > 0 else np.nan)]
    if M.shape == (2, 2):
        a, b, c, d = M.ravel()
        orr, pf = stats.fisher_exact(M)
        out = [("Fisher's exact test P value", fmt_p(pf)), ("Fisher summary", stars(pf, alpha))] + out
        z = 1.959964
        eff = []
        if a * d > 0 and b * c > 0:
            se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
            o = (a * d) / (b * c)
            eff.append(("Odds ratio", o))
            eff.append(("95% CI of odds ratio (Woolf)", f"{fmt(o * math.exp(-z * se))} to {fmt(o * math.exp(z * se))}"))
        if (a + b) > 0 and (c + d) > 0 and a > 0 and c > 0:
            rr = (a / (a + b)) / (c / (c + d))
            se = math.sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d))
            eff.append(("Relative risk", rr))
            eff.append(("95% CI of relative risk (Katz)", f"{fmt(rr * math.exp(-z * se))} to {fmt(rr * math.exp(z * se))}"))
        p1, p2 = a / (a + b) if a + b else np.nan, c / (c + d) if c + d else np.nan
        eff.append(("Attributable risk (difference)", p1 - p2))
        if p1 != p2:
            eff.append(("Number needed to treat / harm", 1 / abs(p1 - p2)))
        eff += [("Sensitivity", a / (a + c) if a + c else np.nan), ("Specificity", d / (b + d) if b + d else np.nan),
                ("Positive predictive value", a / (a + b) if a + b else np.nan),
                ("Negative predictive value", d / (c + d) if c + d else np.nan)]
        r.kv("Effect size", eff)
    r.kv("Tests", out)
    if (expected < 5).any():
        r.warn("Some expected values are less than 5; the chi-square approximation may be inaccurate"
               + (" — use Fisher's exact test." if M.shape == (2, 2) else "."))
    names = [table.names[i] for i in idx]
    r.table("Observed", [""] + names + ["Total"], [[lab] + list(row) + [row.sum()] for lab, row in zip(labels, M)])
    r.table("Expected", [""] + names, [[lab] + list(row) for lab, row in zip(labels, expected)])
    r.table("Percent of row total", [""] + names,
            [[lab] + list(row / row.sum() * 100 if row.sum() else row) for lab, row in zip(labels, M)])
    # chi-square for trend (rows ordered) for 2 columns
    if M.shape[1] == 2 and M.shape[0] > 2:
        sc = np.arange(M.shape[0], dtype=float)
        n_i = M.sum(axis=1)
        p_hat = M[:, 0].sum() / N
        num = (M[:, 0] * sc).sum() - p_hat * (n_i * sc).sum()
        den = p_hat * (1 - p_hat) * ((n_i * sc ** 2).sum() - (n_i * sc).sum() ** 2 / N)
        if den > 0:
            ct = num ** 2 / den
            r.kv("Chi-square test for trend", [("Chi-square", ct), ("df", 1), ("P value", fmt_p(stats.chi2.sf(ct, 1)))])
    return r


def parts_of_whole(table, params):
    idx = selected(table, params)
    r = Result("Fraction of total")
    for i in idx:
        v = table.Y[i][:, 0]
        m = np.isfinite(v)
        tot = v[m].sum()
        r.table(table.names[i], ["Category", "Value", "Fraction", "Percent"],
                [[lab, val, val / tot, val / tot * 100] for lab, val, ok in zip(table.row_labels, v, m) if ok] +
                [["Total", tot, 1, 100]])
        if params.get("chiSquare"):
            exp_ = params.get("expected")
            obs = v[m]
            e = np.full(len(obs), obs.sum() / len(obs)) if not exp_ else np.array(exp_[:len(obs)], float) / 100 * obs.sum()
            chi, p = stats.chisquare(obs, e)
            r.kv("Chi-square goodness of fit", [("Chi-square", chi), ("df", len(obs) - 1), ("P value", fmt_p(p))])
    return r


# ---------------------------------------------------------------------------
# Data manipulations that create new tables
# ---------------------------------------------------------------------------

TRANSFORMS = {
    "log10": ("Y = log10(Y)", lambda y, k: np.log10(np.where(y > 0, y, np.nan))),
    "ln": ("Y = ln(Y)", lambda y, k: np.log(np.where(y > 0, y, np.nan))),
    "pow10": ("Y = 10^Y", lambda y, k: 10.0 ** y),
    "exp": ("Y = e^Y", lambda y, k: np.exp(y)),
    "sqrt": ("Y = sqrt(Y)", lambda y, k: np.sqrt(np.where(y >= 0, y, np.nan))),
    "square": ("Y = Y^2", lambda y, k: y ** 2),
    "reciprocal": ("Y = 1/Y", lambda y, k: np.where(y != 0, 1 / np.where(y != 0, y, 1), np.nan)),
    "abs": ("Y = |Y|", lambda y, k: np.abs(y)),
    "times": ("Y = Y*K", lambda y, k: y * k),
    "plus": ("Y = Y+K", lambda y, k: y + k),
    "logit": ("Y = logit(Y) (Y as fraction)", lambda y, k: np.log(y / (1 - y))),
    "zscore": ("Y = Z score within column", None),
}

X_TRANSFORMS = {
    "none": lambda x: x, "log10": lambda x: np.log10(np.where(x > 0, x, np.nan)),
    "ln": lambda x: np.log(np.where(x > 0, x, np.nan)), "reciprocal": lambda x: 1 / x,
    "times": None,
}


def _rebuild(table, newY, name, x=None):
    cells = []
    for r_ in range(table.nrows):
        row = []
        for arr in newY:
            row.extend(list(arr[r_]))
        cells.append(row)
    return make_table(name, table.type, [{"name": nm, "reps": arr.shape[1]} for nm, arr in zip(table.names, newY)],
                      cells, x=table.x if x is None else x, row_labels=table.row_labels, x_title=table.x_title)


def transform(table, params):
    key = params.get("function", "log10")
    k = float(params.get("k", 1) or 1)
    xkey = params.get("xFunction", "none")
    label, fn = TRANSFORMS.get(key, TRANSFORMS["log10"])
    newY = []
    with np.errstate(all="ignore"):
        for arr in table.Y:
            if key == "zscore":
                v = arr[np.isfinite(arr)]
                newY.append((arr - v.mean()) / v.std(ddof=1) if len(v) > 1 else arr * np.nan)
            else:
                newY.append(fn(arr, k))
        x = X_TRANSFORMS.get(xkey, X_TRANSFORMS["none"])(table.x) if xkey != "times" else table.x * k
    r = Result("Transform")
    r.kv("Transform", [("Y transform", label), ("X transform", xkey), ("K", k)])
    r.output_tables.append(_rebuild(table, newY, f"Transform of {table.name}", x))
    return r


def normalize(table, params):
    mode = params.get("zero", "min")  # min | first | value
    mode100 = params.get("hundred", "max")  # max | last | value
    as_fraction = params.get("result", "percent") == "fraction"
    newY = []
    rows = []
    for nm, arr in zip(table.names, table.Y):
        means = np.nanmean(arr, axis=1) if np.isfinite(arr).any() else np.full(arr.shape[0], np.nan)
        fin = means[np.isfinite(means)]
        if not len(fin):
            newY.append(arr)
            continue
        z = {"min": fin.min(), "first": fin[0], "value": float(params.get("zeroValue", 0) or 0)}[mode]
        h = {"max": fin.max(), "last": fin[-1], "value": float(params.get("hundredValue", 100) or 100)}[mode100]
        scale = 1 if as_fraction else 100
        newY.append((arr - z) / (h - z) * scale if h != z else arr * np.nan)
        rows.append([nm, z, h])
    r = Result("Normalize")
    r.table("Normalization constants", ["Data set", "0% defined as", "100% defined as"], rows)
    r.output_tables.append(_rebuild(table, newY, f"Normalized {table.name}"))
    return r


def remove_baseline(table, params):
    which = params.get("baseline", "first")  # first column or first row
    newY = []
    if which == "firstcol" and table.Y:
        base = np.nanmean(table.Y[0], axis=1, keepdims=True)
        newY = [arr - base for arr in table.Y[1:]]
        names = table.names[1:]
        t = _rebuild(type(table)(**{**table.__dict__, "names": names, "Y": newY}), newY, f"Baseline-subtracted {table.name}")
    else:
        for arr in table.Y:
            fin = np.where(np.isfinite(np.nanmean(arr, axis=1)))[0] if np.isfinite(arr).any() else []
            base = np.nanmean(arr[fin[0]]) if len(fin) else 0
            newY.append(arr - base)
        t = _rebuild(table, newY, f"Baseline-subtracted {table.name}")
    r = Result("Remove baseline")
    r.kv("Method", [("Baseline", "First data set column" if which == "firstcol" else "First row of each data set")])
    r.output_tables.append(t)
    return r


def transpose(table, params):
    cols = []
    for arr in table.Y:
        cols.append(np.nanmean(arr, axis=1) if arr.shape[1] > 1 else arr[:, 0])
    M = np.column_stack(cols) if cols else np.zeros((0, 0))
    cells = M.T.tolist()
    r = Result("Transpose")
    r.output_tables.append(make_table(f"Transpose of {table.name}", "column" if table.type != "grouped" else "grouped",
                                      [{"name": lab, "reps": 1} for lab in table.row_labels], cells,
                                      row_labels=table.names))
    return r
