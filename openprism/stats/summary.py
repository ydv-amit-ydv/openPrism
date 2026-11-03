"""Analyses of summary data: one row per group with mean, SD (or SEM) and n.

Typical use: results taken from a paper, or Prism tables entered as
"mean, SD, N". The t test and ANOVA computed from summaries are exactly the
tests computed from the raw data (a property the test-suite checks).
"""
from __future__ import annotations

import itertools
import math

import numpy as np
from scipy import stats

from .common import (COMPARISON_COLUMNS, Result, comparison_rows, fmt, fmt_p, pairwise_pooled, require, sig, stars,
                     tukey_p, tukey_q_crit)


def summary_rows(table, params=None):
    """[(label, mean, sd, n)] from a summary table; the 2nd column may hold SEM (header contains 'SEM')."""
    require(table.type == "summary", "This analysis needs a Summary data table (mean, SD or SEM, n).")
    require(len(table.Y) >= 3, "A summary table needs three columns: mean, SD (or SEM) and n.")
    is_sem = "SEM" in str(table.names[1]).upper() or "SE" == str(table.names[1]).strip().upper()
    rows = []
    for r in range(table.nrows):
        m, s, n = (float(table.Y[k][r, 0]) for k in range(3))
        if not (np.isfinite(m) and np.isfinite(s) and np.isfinite(n)):
            continue
        require(n >= 1 and float(n).is_integer(), f"n must be a whole number ≥ 1 (row “{table.row_labels[r]}”).")
        require(s >= 0, f"SD/SEM cannot be negative (row “{table.row_labels[r]}”).")
        sd = s * math.sqrt(n) if is_sem else s
        rows.append((table.row_labels[r], m, sd, int(n)))
    sel = (params or {}).get("rows")
    if sel:
        rows = [rows[i] for i in sel if 0 <= i < len(rows)]
    require(rows, "Enter at least one row with mean, SD and n.")
    return rows, is_sem


def summary_describe(table, params):
    rows, is_sem = summary_rows(table, params)
    level = float(params.get("ci", 0.95))
    out = []
    for lab, m, sd, n in rows:
        se = sd / math.sqrt(n)
        h = stats.t.ppf(0.5 + level / 2, n - 1) * se if n > 1 else np.nan
        out.append([lab, n, m, sd, se, f"{fmt(m - h)} to {fmt(m + h)}" if n > 1 else "", sd / m * 100 if m else np.nan])
    r = Result("Summary data")
    r.table(f"Groups (column 2 entered as {'SEM' if is_sem else 'SD'})", ["Group", "n", "Mean", "SD", "SEM", f"{int(level * 100)}% CI of mean", "CV (%)"], out)
    return r


def summary_ttest(table, params):
    rows, _ = summary_rows(table, params)
    require(len(rows) >= 2, "Enter two groups (two rows).")
    (la, ma, sa, na), (lb, mb, sb, nb) = rows[:2]
    require(na >= 2 and nb >= 2, "Each group needs n ≥ 2.")
    welch = bool(params.get("welch", False))
    alpha = float(params.get("alpha", 0.05))
    va, vb = sa ** 2, sb ** 2
    if welch:
        se = math.sqrt(va / na + vb / nb)
        df = (va / na + vb / nb) ** 2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
    else:
        sp2 = ((na - 1) * va + (nb - 1) * vb) / (na + nb - 2)
        se = math.sqrt(sp2 * (1 / na + 1 / nb))
        df = na + nb - 2
    diff = mb - ma
    t = diff / se
    p = float(2 * stats.t.sf(abs(t), df))
    q = stats.t.ppf(1 - alpha / 2, df)
    sp = math.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
    d = diff / sp
    J = 1 - 3 / (4 * (na + nb) - 9)
    r = Result("Unpaired t test from summary data" + (" (Welch)" if welch else ""))
    r.kv("Unpaired t test", [("P value", fmt_p(p)), ("P value summary", stars(p, alpha)), (f"Significantly different (P < {alpha})?", sig(p, alpha)),
                             ("t, df", f"t={fmt(abs(t))}, df={fmt(df)}")])
    r.kv("How big is the difference?", [(f"Mean of {la}", ma), (f"Mean of {lb}", mb), ("Difference between means (B - A) ± SEM", f"{fmt(diff)} ± {fmt(se)}"),
                                         (f"{int(round((1 - alpha) * 100))}% confidence interval", f"{fmt(diff - q * se)} to {fmt(diff + q * se)}"),
                                         ("R squared (eta squared)", t ** 2 / (t ** 2 + df)), ("Cohen's d", d), ("Hedges' g", d * J)])
    F = max(va, vb) / min(va, vb) if min(va, vb) > 0 else np.nan
    dfn, dfd = (nb - 1, na - 1) if vb >= va else (na - 1, nb - 1)
    pf = min(1.0, 2 * stats.f.sf(F, dfn, dfd)) if np.isfinite(F) else np.nan
    r.kv("F test to compare variances", [("F, DFn, Dfd", f"{fmt(F)}, {dfn}, {dfd}"), ("P value", fmt_p(pf)), (f"Significantly different (P < {alpha})?", sig(pf, alpha))])
    return r


def summary_anova(table, params):
    rows, _ = summary_rows(table, params)
    require(len(rows) >= 2, "Enter at least two groups (rows).")
    names = [x[0] for x in rows]
    means = [x[1] for x in rows]
    sds = [x[2] for x in rows]
    ns = [x[3] for x in rows]
    alpha = float(params.get("alpha", 0.05))
    method = params.get("comparison", "tukey")
    k, N = len(rows), sum(ns)
    require(N > k, "Not enough data (total n must exceed the number of groups).")
    grand = sum(n * m for n, m in zip(ns, means)) / N
    ssb = sum(n * (m - grand) ** 2 for n, m in zip(ns, means))
    ssw = sum((n - 1) * s ** 2 for n, s in zip(ns, sds))
    dfb, dfw = k - 1, N - k
    msw = ssw / dfw
    F = (ssb / dfb) / msw
    p = float(stats.f.sf(F, dfb, dfw))
    r = Result("One-way ANOVA from summary data")
    r.kv("ANOVA summary", [("F", F), ("P value", fmt_p(p)), ("P value summary", stars(p, alpha)), (f"Significant diff. among means (P < {alpha})?", sig(p, alpha)),
                           ("R squared", ssb / (ssb + ssw))])
    r.table("ANOVA table", ["Source of variation", "SS", "DF", "MS", "F (DFn, DFd)", "P value"], [
        ["Treatment (between columns)", ssb, dfb, ssb / dfb, f"F ({dfb}, {dfw}) = {fmt(F)}", fmt_p(p)],
        ["Residual (within columns)", ssw, dfw, msw, "", ""], ["Total", ssb + ssw, N - 1, "", "", ""]])
    if all(n >= 2 for n in ns):
        w = np.array([n / s ** 2 if s > 0 else np.inf for n, s in zip(ns, sds)])
        if np.all(np.isfinite(w)):
            mw = (w * np.array(means)).sum() / w.sum()
            A = (w * (np.array(means) - mw) ** 2).sum() / (k - 1)
            lam = ((1 - w / w.sum()) ** 2 / (np.array(ns) - 1)).sum()
            Fw = A / (1 + 2 * (k - 2) / (k ** 2 - 1) * lam)
            df2 = (k ** 2 - 1) / (3 * lam)
            pw = float(stats.f.sf(Fw, k - 1, df2))
            r.kv("ANOVA without assuming equal SDs", [("Welch's W (DFn, DFd)", f"{fmt(Fw)} ({k - 1}, {fmt(df2)})"), ("Welch P value", fmt_p(pw))])
    if method == "games-howell":
        rows_ = []
        for a, b in itertools.combinations(range(k), 2):
            va, vb = sds[a] ** 2 / ns[a], sds[b] ** 2 / ns[b]
            se = math.sqrt(va + vb)
            dfab = (va + vb) ** 2 / (va ** 2 / (ns[a] - 1) + vb ** 2 / (ns[b] - 1))
            diff = means[a] - means[b]
            qv = abs(diff) / se * math.sqrt(2)
            pab = tukey_p(qv, k, dfab)
            h = tukey_q_crit(alpha, k, dfab) / math.sqrt(2) * se
            rows_.append({"label": f"{names[a]} vs. {names[b]}", "diff": diff, "lo": diff - h, "hi": diff + h, "p": pab, "stars": stars(pab, alpha)})
        r.table("Games-Howell multiple comparisons (unequal SDs)", COMPARISON_COLUMNS, comparison_rows(rows_, alpha))
    elif method != "none" and k > 2:
        comps = pairwise_pooled(means, ns, names, msw, dfw, method=method, control=int(params.get("control", 0)), alpha=alpha)
        r.table(f"{ {'tukey': 'Tukey', 'dunnett': 'Dunnett', 'bonferroni': 'Bonferroni', 'sidak': 'Šídák', 'holm-sidak': 'Holm-Šídák', 'fisher': 'Fisher LSD', 'bh': 'BH FDR', 'holm': 'Holm', 'bky': 'BKY FDR'}.get(method, method)}'s multiple comparisons test",
                COMPARISON_COLUMNS, comparison_rows(comps, alpha))
    r.table("Data summary", ["Group", "N", "Mean", "SD", "SEM"], [[nm, n, m, s, s / math.sqrt(n)] for nm, n, m, s in zip(names, ns, means, sds)])
    return r
