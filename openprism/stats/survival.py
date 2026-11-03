"""Kaplan-Meier survival analysis with log-rank and Gehan-Breslow-Wilcoxon tests.

Survival table layout (Prism style): X column = elapsed time; each data set
column holds 1 (event / death) or 0 (censored) for the subjects belonging to
that group, blank otherwise.
"""
from __future__ import annotations

import itertools
import math

import numpy as np
from scipy import stats

from .common import Result, fmt, fmt_p, require, sig, stars
from .descriptive import selected


def _groups(table, idx):
    out = []
    for i in idx:
        ev = table.Y[i][:, 0]
        m = np.isfinite(table.x) & np.isfinite(ev)
        out.append((table.x[m], (ev[m] > 0).astype(int)))
    return out


def km(t, e, level=0.95):
    order = np.argsort(t, kind="stable")
    t, e = t[order], e[order]
    times = np.unique(t[e == 1])
    n_at = len(t)
    s = 1.0
    var_sum = 0.0
    z = stats.norm.ppf(0.5 + level / 2)
    curve = [(0.0, 1.0, 1.0, 1.0, len(t), 0)]
    for tt in times:
        n = (t >= tt).sum()
        d = ((t == tt) & (e == 1)).sum()
        s *= 1 - d / n
        if n - d > 0:
            var_sum += d / (n * (n - d))
        # asymmetrical CI (log-log transform)
        if 0 < s < 1 and var_sum > 0:
            se_ll = math.sqrt(var_sum) / abs(math.log(s))
            lo = s ** math.exp(z * se_ll)
            hi = s ** math.exp(-z * se_ll)
        else:
            lo = hi = s
        curve.append((float(tt), s, lo, hi, int(n), int(d)))
    del n_at
    return curve


def median_survival(curve):
    for tt, s, *_ in curve:
        if s <= 0.5:
            return tt
    return np.nan


def logrank(groups, weights="logrank"):
    allt = np.unique(np.concatenate([g[0][g[1] == 1] for g in groups]))
    k = len(groups)
    O = np.zeros(k)
    E = np.zeros(k)
    V = np.zeros((k, k))
    for tt in allt:
        n_j = np.array([(g[0] >= tt).sum() for g in groups], float)
        d_j = np.array([((g[0] == tt) & (g[1] == 1)).sum() for g in groups], float)
        n, d = n_j.sum(), d_j.sum()
        if n < 2:
            continue
        w = n if weights == "gehan" else 1.0
        O += w * d_j
        E += w * d_j.sum() * n_j / n
        fac = d * (n - d) / (n * n * (n - 1))
        V += w * w * fac * (np.diag(n_j) * n - np.outer(n_j, n_j))
    diff = (O - E)[:-1]
    Vr = V[:-1, :-1]
    try:
        chi = float(diff @ np.linalg.solve(Vr, diff))
    except np.linalg.LinAlgError:
        chi = np.nan
    p = float(stats.chi2.sf(chi, k - 1)) if np.isfinite(chi) else np.nan
    return chi, p, O, E


def _nice_step(raw):
    if raw <= 0:
        return 1.0
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def survival(table, params):
    require(table.type == "survival", "Survival analysis requires a Survival table.")
    idx = selected(table, params)
    require(idx, "No data.")
    alpha = float(params.get("alpha", 0.05))
    level = float(params.get("ci", 0.95))
    groups = _groups(table, idx)
    names = [table.names[i] for i in idx]
    r = Result("Survival analysis (Kaplan-Meier)")
    curves = []
    med_rows = []
    for i, nm, (t, e) in zip(idx, names, groups):
        c = km(t, e, level)
        med = median_survival(c)
        censored = t[e == 0]
        ci_s = []
        for tc in censored:
            s_at = [s for (tt, s, *_rest) in c if tt <= tc][-1]
            ci_s.append(s_at)
        curves.append({"dataset": i, "t": [p[0] for p in c], "s": [p[1] for p in c], "lo": [p[2] for p in c],
                       "hi": [p[3] for p in c], "censorT": [float(v) for v in censored], "censorS": ci_s})
        med_rows.append([nm, len(t), int(e.sum()), int((e == 0).sum()), med if np.isfinite(med) else "Undefined"])
        r.table(f"Survival proportions: {nm}", ["Time", "At risk", "Events", "Survival %", "Lower CI %", "Upper CI %"],
                [[p[0], p[4], p[5], p[1] * 100, p[2] * 100, p[3] * 100] for p in c])
    r.table("Median survival", ["Group", "Subjects", "Events", "Censored", "Median survival"], med_rows)
    if len(groups) >= 2:
        chi, p, O, E = logrank(groups)
        chi_g, p_g, _, _ = logrank(groups, "gehan")
        out = [("Log-rank (Mantel-Cox) test", ""), ("Chi square", chi), ("df", len(groups) - 1),
               ("P value", fmt_p(p)), ("P value summary", stars(p, alpha)),
               ("Are the survival curves sig different?", sig(p, alpha)),
               ("Gehan-Breslow-Wilcoxon test", ""), ("Chi square", chi_g), ("P value", fmt_p(p_g)),
               ("Are the survival curves sig different?", sig(p_g, alpha))]
        if len(groups) == 2:
            hr = (O[0] / E[0]) / (O[1] / E[1]) if E[0] > 0 and E[1] > 0 and O[1] > 0 else np.nan
            if np.isfinite(hr) and hr > 0:
                se = math.sqrt(1 / E[0] + 1 / E[1])
                z = stats.norm.ppf(0.5 + level / 2)
                out += [("Hazard Ratio (logrank)", ""), (f"Ratio ({names[0]}/{names[1]})", hr),
                        (f"{int(level * 100)}% CI of ratio", f"{fmt(hr * math.exp(-z * se))} to {fmt(hr * math.exp(z * se))}")]
            m1, m2 = median_survival(km(*groups[0])), median_survival(km(*groups[1]))
            if np.isfinite(m1) and np.isfinite(m2) and m2 > 0:
                out += [("Ratio of median survival", m1 / m2)]
        elif len(groups) >= 3:
            # log-rank test for trend
            sc = np.arange(1, len(groups) + 1, dtype=float)
            _, _, O, E = logrank(groups)
            # pairwise comparisons (Bonferroni)
            rows = []
            pairs = list(itertools.combinations(range(len(groups)), 2))
            for a, b in pairs:
                _, pp, _, _ = logrank([groups[a], groups[b]])
                pa = min(1.0, pp * len(pairs))
                rows.append([f"{names[a]} vs. {names[b]}", fmt_p(pp), fmt_p(pa), stars(pa, alpha)])
            r.table("Pairwise log-rank comparisons", ["Comparison", "P value", "Bonferroni adjusted P", "Summary"], rows)
            del sc
        r.kv("Curve comparison", out)
        r.table("Observed vs. expected events", ["Group", "Observed", "Expected"],
                [[nm, o, e] for nm, o, e in zip(names, O, E)])
    maxt = max((float(t.max()) for t, _ in groups if len(t)), default=0.0)
    step = _nice_step(maxt / 5) if maxt > 0 else 1.0
    times = [round(k * step, 10) for k in range(int(maxt // step) + 1)]
    at_risk = [[int((t >= tt).sum()) for tt in times] for t, _ in groups]
    r.table("Number at risk", ["Group"] + [fmt(tt) for tt in times], [[nm] + row for nm, row in zip(names, at_risk)])
    r.overlay = {"kind": "km", "curves": curves, "atRisk": {"times": times, "counts": at_risk, "names": names}}
    return r
