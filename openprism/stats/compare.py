"""Comparisons of groups: t tests, nonparametric tests, one-way and two-way ANOVA."""
from __future__ import annotations

import itertools
import math

import numpy as np
from scipy import stats

from .common import (COMPARISON_COLUMNS, MC_METHODS, Result, comparison_rows, fmt, fmt_p, holm_sidak,
                     pairwise_pooled, pairs_overlay, quiet, require, sig, stars, t_ci, bh_fdr)
from .descriptive import selected


def _paired_matrix(table, idx):
    """Rows where every selected column has a value (for paired / RM designs)."""
    cols = [table.Y[i][:, 0] if table.Y[i].shape[1] == 1 else np.nanmean(table.Y[i], axis=1) for i in idx]
    M = np.column_stack(cols)
    return M[np.all(np.isfinite(M), axis=1)]


# ---------------------------------------------------------------------------
# Two groups
# ---------------------------------------------------------------------------

def ttest(table, params):
    idx = selected(table, params)
    require(len(idx) >= 2, "Choose two data sets to compare.")
    idx = idx[:2]
    a_name, b_name = table.names[idx[0]], table.names[idx[1]]
    paired = bool(params.get("paired", False))
    parametric = params.get("parametric", True) not in (False, "false", "no")
    welch = bool(params.get("welch", False))
    alpha = float(params.get("alpha", 0.05))
    alt = params.get("alternative", "two-sided")

    if paired:
        M = _paired_matrix(table, idx)
        require(len(M) >= 2, "Need at least two complete pairs.")
        a, b = M[:, 0], M[:, 1]
    else:
        # values minus a common offset subtracted in exact decimal arithmetic: all statistics
        # below are shift-invariant, so precision is kept for data with a large constant part
        offset, (a, b) = table.shifted(idx)
        require(len(a) >= 2 and len(b) >= 2, "Each group needs at least two values.")

    if parametric and not paired:
        title = "Unpaired t test with Welch's correction" if welch else "Unpaired t test"
    elif parametric:
        title = "Paired t test"
    elif paired:
        title = "Wilcoxon matched-pairs signed rank test"
    else:
        title = "Mann-Whitney test"
    r = Result(title)

    if parametric and not paired:
        res = stats.ttest_ind(b, a, equal_var=not welch, alternative=_flip(alt))
        p = float(res.pvalue)
        ma, mb = a.mean(), b.mean()
        va, vb = a.var(ddof=1), b.var(ddof=1)
        na, nb = len(a), len(b)
        if welch:
            se = math.sqrt(va / na + vb / nb)
            df = (va / na + vb / nb) ** 2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
        else:
            sp = ((na - 1) * va + (nb - 1) * vb) / (na + nb - 2)
            se = math.sqrt(sp * (1 / na + 1 / nb))
            df = na + nb - 2
        diff = mb - ma
        lo, hi = t_ci(diff, se, df, 1 - alpha)
        t = float(res.statistic)
        r2 = t ** 2 / (t ** 2 + df)
        r.kv("Unpaired t test", [
            ("P value", fmt_p(p)), ("P value summary", stars(p, alpha)),
            (f"Significantly different (P < {alpha})?", sig(p, alpha)),
            ("One- or two-tailed P value?", "Two-tailed" if alt == "two-sided" else "One-tailed"),
            ("t, df", f"t={fmt(abs(t))}, df={fmt(df)}"),
        ])
        r.kv("How big is the difference?", [
            (f"Mean of {a_name}", ma + offset), (f"Mean of {b_name}", mb + offset),
            ("Difference between means (B - A) ± SEM", f"{fmt(diff)} ± {fmt(se)}"),
            (f"{int((1 - alpha) * 100)}% confidence interval", f"{fmt(lo)} to {fmt(hi)}"),
            ("R squared (eta squared)", r2),
            ("Cohen's d", diff / math.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))),
            *_hedges(diff, na, nb, va, vb),
            *_bf_row(t, na * nb / (na + nb), na + nb - 2),
        ])
        f = max(va, vb) / min(va, vb) if min(va, vb) > 0 else np.nan
        dfn = (nb - 1) if vb >= va else (na - 1)
        dfd = (na - 1) if vb >= va else (nb - 1)
        pf = min(1.0, 2 * stats.f.sf(f, dfn, dfd)) if np.isfinite(f) else np.nan
        r.kv("F test to compare variances", [
            ("F, DFn, Dfd", f"{fmt(f)}, {dfn}, {dfd}"), ("P value", fmt_p(pf)),
            (f"Significantly different (P < {alpha})?", sig(pf, alpha)),
        ])
    elif parametric:
        res = stats.ttest_rel(b, a, alternative=_flip(alt))
        p = float(res.pvalue)
        d = b - a
        se = d.std(ddof=1) / math.sqrt(len(d))
        lo, hi = t_ci(d.mean(), se, len(d) - 1, 1 - alpha)
        t = float(res.statistic)
        df = len(d) - 1
        rr, rp = stats.pearsonr(a, b) if len(a) > 2 else (np.nan, np.nan)
        r.kv("Paired t test", [
            ("P value", fmt_p(p)), ("P value summary", stars(p, alpha)),
            (f"Significantly different (P < {alpha})?", sig(p, alpha)),
            ("t, df", f"t={fmt(abs(t))}, df={df}"), ("Number of pairs", len(d)),
        ])
        r.kv("How big is the difference?", [
            ("Mean of differences (B - A)", d.mean()), ("SD of differences", d.std(ddof=1)),
            ("SEM of differences", se), (f"{int((1 - alpha) * 100)}% confidence interval", f"{fmt(lo)} to {fmt(hi)}"),
            ("R squared (partial eta squared)", t ** 2 / (t ** 2 + df)),
        ])
        r.kv("How effective was the pairing?", [
            ("Correlation coefficient (r)", rr), ("P value (one tailed)", fmt_p(rp / 2 if np.isfinite(rp) else np.nan)),
            ("Was the pairing significantly effective?", sig(rp / 2, alpha) if np.isfinite(rp) else ""),
        ])
    elif paired:
        d = b - a
        p, exact = signed_rank_p(d, _flip(alt))
        pos = np.sum(stats.rankdata(np.abs(d[d != 0]))[d[d != 0] > 0])
        neg = np.sum(stats.rankdata(np.abs(d[d != 0]))[d[d != 0] < 0])
        r.kv("Wilcoxon matched-pairs signed rank test", [
            ("P value", fmt_p(p)), ("Exact or approximate P value?", "Exact (conditional on ties)" if exact else "Approximate (normal, continuity-corrected)"),
            ("P value summary", stars(p, alpha)), (f"Significantly different (P < {alpha})?", sig(p, alpha)),
            ("Sum of positive, signed ranks (W+)", pos), ("Sum of negative, signed ranks (W-)", -neg),
            ("Sum of signed ranks (W)", pos - neg), ("Number of pairs", len(d)),
            ("Number of ties (ignored)", int(np.sum(d == 0))),
        ])
        r.kv("Median of differences", [(f"Median of {a_name}", np.median(a)), (f"Median of {b_name}", np.median(b)),
                                       ("Median of differences (B - A)", np.median(d))])
    else:
        res = stats.mannwhitneyu(b, a, alternative=_flip(alt))
        p, exact = rank_sum_p(b, a, _flip(alt))
        ranks = stats.rankdata(np.concatenate([a, b]))
        ra, rb = ranks[:len(a)].sum(), ranks[len(a):].sum()
        u = min(res.statistic, len(a) * len(b) - res.statistic)
        hl = np.median(np.subtract.outer(b, a))
        r.kv("Mann Whitney test", [
            ("P value", fmt_p(p)), ("Exact or approximate P value?", "Exact (conditional on ties)" if exact else "Approximate (normal, continuity-corrected)"),
            ("P value summary", stars(p, alpha)), (f"Significantly different (P < {alpha})?", sig(p, alpha)),
            (f"Sum of ranks in {a_name}, {b_name}", f"{fmt(ra)}, {fmt(rb)}"), ("Mann-Whitney U", u),
        ])
        r.kv("Difference between medians", [
            (f"Median of {a_name}, n", f"{fmt(np.median(a))}, {len(a)}"),
            (f"Median of {b_name}, n", f"{fmt(np.median(b))}, {len(b)}"),
            ("Difference: Actual", np.median(b) - np.median(a)), ("Difference: Hodges-Lehmann", hl),
        ])
    r.overlay = {"kind": "pairs", "pairs": [{"a": idx[0], "b": idx[1], "p": p, "stars": stars(p, alpha)}]}
    return r


def _hedges(diff, na, nb, va, vb):
    """Hedges' g (small-sample corrected d) with an approximate 95% CI."""
    sp = math.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
    if sp == 0:
        return []
    d = diff / sp
    j = 1 - 3 / (4 * (na + nb) - 9)
    g = d * j
    se = math.sqrt((na + nb) / (na * nb) + g ** 2 / (2 * (na + nb)))
    return [("Hedges' g", g), ("95% CI of Hedges' g", f"{fmt(g - 1.96 * se)} to {fmt(g + 1.96 * se)}")]


def _bf_row(t, n_eff, df):
    try:
        from .advanced import _jzs_bf10
        return [("Bayes factor BF10 (JZS, r = 0.707)", _jzs_bf10(t, n_eff, df))]
    except Exception:  # noqa: BLE001
        return []


def _flip(alt):
    return {"greater": "greater", "less": "less"}.get(alt, "two-sided")


def multiple_t(table, params):
    """Multiple unpaired t tests: one per row of a grouped table (two columns)."""
    idx = selected(table, params)
    require(len(idx) >= 2, "Need two data sets (columns).")
    a_i, b_i = idx[:2]
    alpha = float(params.get("alpha", 0.05))
    method = params.get("correction", "holm-sidak")
    welch = bool(params.get("welch", False))
    rows, ps = [], []
    for r_ in range(table.nrows):
        a = table.Y[a_i][r_]
        b = table.Y[b_i][r_]
        a, b = a[np.isfinite(a)], b[np.isfinite(b)]
        if len(a) < 2 or len(b) < 2:
            continue
        res = stats.ttest_ind(a, b, equal_var=not welch)
        rows.append([table.row_labels[r_], a.mean(), b.mean(), a.mean() - b.mean(), float(res.statistic)])
        ps.append(float(res.pvalue))
    require(rows, "No rows with at least two replicates in each group.")
    if method == "bh":
        adj = bh_fdr(ps)
    elif method == "bonferroni":
        adj = [min(1, p * len(ps)) for p in ps]
    elif method == "none":
        adj = ps
    else:
        adj = holm_sidak(ps)
    res = Result("Multiple unpaired t tests")
    res.table("Results", ["Row", f"Mean {table.names[a_i]}", f"Mean {table.names[b_i]}", "Difference", "t",
                          "P value", "Adjusted P", "Summary"],
              [row + [fmt_p(p), fmt_p(q), stars(q, alpha)] for row, p, q in zip(rows, ps, adj)])
    return res


# ---------------------------------------------------------------------------
# One-way ANOVA family
# ---------------------------------------------------------------------------

def one_way(table, params):
    idx = selected(table, params)
    require(len(idx) >= 2, "One-way ANOVA needs at least two data sets.")
    alpha = float(params.get("alpha", 0.05))
    rm = bool(params.get("repeated", False))
    parametric = params.get("parametric", True) not in (False, "false", "no")
    method = params.get("comparison", "tukey")
    control = int(params.get("control", 0))
    names = [table.names[i] for i in idx]

    if not parametric:
        return _friedman(table, idx, names, alpha) if rm else _kruskal(table, idx, names, alpha, control, method)
    if rm and params.get("mixed"):
        from .advanced import mixed_one_way
        return mixed_one_way(table, params)
    if rm:
        return _rm_anova(table, idx, names, alpha, method, control, bool(params.get("geisser", True)))

    # deviations from a common offset, subtracted exactly: every statistic below is
    # shift-invariant, so this keeps full precision for data with a large constant part
    offset, groups = table.shifted(idx)
    require(all(len(g) >= 1 for g in groups) and sum(len(g) for g in groups) > len(groups),
            "Not enough data in each group.")
    ns = [len(g) for g in groups]
    means = [g.mean() for g in groups]
    N, k = sum(ns), len(groups)
    grand = np.concatenate(groups).mean()
    ss_b = sum(n * (m - grand) ** 2 for n, m in zip(ns, means))
    ss_w = sum(((g - g.mean()) ** 2).sum() for g in groups)
    df_b, df_w = k - 1, N - k
    ms_b, ms_w = ss_b / df_b, ss_w / df_w
    F = ms_b / ms_w
    p = float(stats.f.sf(F, df_b, df_w))
    r = Result("Ordinary one-way ANOVA")
    r.kv("ANOVA summary", [
        ("F", F), ("P value", fmt_p(p)), ("P value summary", stars(p, alpha)),
        (f"Significant diff. among means (P < {alpha})?", sig(p, alpha)),
        ("R squared", ss_b / (ss_b + ss_w)),
    ])
    with quiet():
        valid = [g for g in groups if len(g) >= 2]
        if len(valid) >= 2:
            bf = stats.levene(*valid, center="median")
            bart = stats.bartlett(*valid)
            r.kv("Tests for equal variances", [
                ("Brown-Forsythe test F (DFn, DFd)", f"{fmt(bf.statistic)} ({df_b}, {df_w})"),
                ("Brown-Forsythe P value", fmt_p(bf.pvalue)),
                ("Bartlett's statistic (corrected)", bart.statistic), ("Bartlett's P value", fmt_p(bart.pvalue)),
                ("Are SDs significantly different?", sig(min(bf.pvalue, 1), alpha)),
            ])
    r.table("ANOVA table", ["Source of variation", "SS", "DF", "MS", "F (DFn, DFd)", "P value"], [
        ["Treatment (between columns)", ss_b, df_b, ms_b, f"F ({df_b}, {df_w}) = {fmt(F)}", fmt_p(p)],
        ["Residual (within columns)", ss_w, df_w, ms_w, "", ""],
        ["Total", ss_b + ss_w, N - 1, "", "", ""],
    ])
    if params.get("welch"):
        from .advanced import brown_forsythe_anova
        wf, wdf2, wp = _welch_anova(groups)
        bf, bdf1, bdf2, bp = brown_forsythe_anova(groups)
        r.kv("ANOVA without assuming equal SDs", [("Welch's W (DFn, DFd)", f"{fmt(wf)} ({df_b}, {fmt(wdf2)})"), ("Welch P value", fmt_p(wp)),
                                                   ("Brown-Forsythe F* (DFn, DFd)", f"{fmt(bf)} ({bdf1}, {fmt(bdf2)})"), ("Brown-Forsythe P value", fmt_p(bp))])
    if method == "games-howell":
        from .advanced import games_howell
        rows, ov = games_howell(groups, names, alpha, idx)
        r.table("Games-Howell multiple comparisons (unequal SDs)", COMPARISON_COLUMNS, rows)
        r.overlay = {"kind": "pairs", "pairs": ov}
    elif method in ("t3", "t2"):
        from .advanced import unequal_var_posthoc
        rows, ov = unequal_var_posthoc(groups, names, alpha, idx, method)
        r.table(("Dunnett T3" if method == "t3" else "Tamhane T2") + " multiple comparisons (unequal SDs)", COMPARISON_COLUMNS, rows)
        r.overlay = {"kind": "pairs", "pairs": ov}
    else:
        _add_comparisons(r, means, ns, names, ms_w, df_w, method, control, alpha, idx)
    r.table("Data summary", ["Group", "N", "Mean", "SD", "SEM"],
            [[nm, n, m + offset, g.std(ddof=1) if n > 1 else "", g.std(ddof=1) / math.sqrt(n) if n > 1 else ""]
             for nm, n, m, g in zip(names, ns, means, groups)])
    return r


def _welch_anova(groups):
    ns = np.array([len(g) for g in groups], float)
    m = np.array([g.mean() for g in groups])
    v = np.array([g.var(ddof=1) for g in groups])
    w = ns / v
    k = len(groups)
    mw = (w * m).sum() / w.sum()
    a = (w * (m - mw) ** 2).sum() / (k - 1)
    tmp = ((1 - w / w.sum()) ** 2 / (ns - 1)).sum()
    b = 1 + 2 * (k - 2) / (k ** 2 - 1) * tmp
    F = a / b
    df2 = (k ** 2 - 1) / (3 * tmp)
    return F, df2, float(stats.f.sf(F, k - 1, df2))


def _add_comparisons(r, means, ns, names, mse, df, method, control, alpha, idx):
    if method in (None, "", "none"):
        return
    comps = pairwise_pooled(means, ns, names, mse, df, method=method, control=control, alpha=alpha)
    r.table(f"{MC_METHODS.get(method, method)}'s multiple comparisons test", COMPARISON_COLUMNS,
            comparison_rows(comps, alpha))
    for c in comps:
        c["a"], c["b"] = idx[c["a"]], idx[c["b"]]
    r.overlay = {"kind": "pairs", "pairs": pairs_overlay(comps)}


def _rm_anova(table, idx, names, alpha, method, control, geisser):
    M = _paired_matrix(table, idx)
    require(len(M) >= 2, "Repeated measures ANOVA needs at least two complete subjects (rows).")
    n, k = M.shape
    grand = M.mean()
    ss_treat = n * ((M.mean(axis=0) - grand) ** 2).sum()
    ss_subj = k * ((M.mean(axis=1) - grand) ** 2).sum()
    ss_tot = ((M - grand) ** 2).sum()
    ss_res = ss_tot - ss_treat - ss_subj
    df_t, df_s, df_r = k - 1, n - 1, (k - 1) * (n - 1)
    ms_t, ms_s, ms_r = ss_treat / df_t, ss_subj / df_s, ss_res / df_r
    F = ms_t / ms_r
    # Greenhouse-Geisser epsilon
    S = np.cov(M, rowvar=False)
    C = np.eye(k) - 1 / k
    Sc = C @ S @ C
    eps = (np.trace(Sc) ** 2) / ((k - 1) * np.sum(Sc ** 2)) if np.sum(Sc ** 2) > 0 else 1.0
    eps = min(1.0, max(1 / (k - 1), eps))
    e = eps if geisser else 1.0
    p = float(stats.f.sf(F, df_t * e, df_r * e))
    Fs = ms_s / ms_r
    ps = float(stats.f.sf(Fs, df_s, df_r))
    r = Result("Repeated measures one-way ANOVA")
    r.kv("Repeated measures ANOVA summary", [
        ("Assume sphericity?", "No" if geisser else "Yes"), ("F", F), ("P value", fmt_p(p)),
        ("P value summary", stars(p, alpha)), (f"Statistically significant (P < {alpha})?", sig(p, alpha)),
        ("Geisser-Greenhouse's epsilon", eps), ("R squared", ss_treat / (ss_treat + ss_res)),
    ])
    r.kv("Was the matching effective?", [("F", Fs), ("P value", fmt_p(ps)), ("Is there significant matching?", sig(ps, alpha))])
    r.table("ANOVA table", ["Source", "SS", "DF", "MS", "F (DFn, DFd)", "P value"], [
        ["Treatment (between columns)", ss_treat, df_t, ms_t,
         f"F ({fmt(df_t * e)}, {fmt(df_r * e)}) = {fmt(F)}", fmt_p(p)],
        ["Individual (between rows)", ss_subj, df_s, ms_s, f"F ({df_s}, {df_r}) = {fmt(Fs)}", fmt_p(ps)],
        ["Residual (random)", ss_res, df_r, ms_r, "", ""],
        ["Total", ss_tot, n * k - 1, "", "", ""],
    ])
    _add_comparisons(r, list(M.mean(axis=0)), [n] * k, names, ms_r, df_r, method, control, alpha, idx)
    return r


def _kruskal(table, idx, names, alpha, control, method):
    groups = [table.column_values(i) for i in idx]
    require(all(len(g) >= 1 for g in groups), "Every group needs data.")
    H, p = stats.kruskal(*groups)
    r = Result("Kruskal-Wallis test")
    allv = np.concatenate(groups)
    ranks = stats.rankdata(allv)
    N = len(allv)
    ns = [len(g) for g in groups]
    pos = np.cumsum([0] + ns)
    mean_ranks = [ranks[pos[i]:pos[i + 1]].mean() for i in range(len(groups))]
    r.kv("Kruskal-Wallis test", [
        ("P value", fmt_p(p)), ("Exact or approximate P value?", "Approximate"),
        ("P value summary", stars(p, alpha)), (f"Do the medians vary signif. (P < {alpha})?", sig(p, alpha)),
        ("Number of groups", len(groups)), ("Kruskal-Wallis statistic", H),
    ])
    r.table("Data summary", ["Group", "N", "Median", "Mean rank"],
            [[nm, n, np.median(g), mr] for nm, n, g, mr in zip(names, ns, groups, mean_ranks)])
    # Dunn's test with tie correction
    _, counts = np.unique(allv, return_counts=True)
    tie = (counts ** 3 - counts).sum() / (12 * (N - 1))
    var = N * (N + 1) / 12 - tie
    if method == "dunnett":
        pairs = [(control, j) for j in range(len(groups)) if j != control]
    else:
        pairs = list(itertools.combinations(range(len(groups)), 2))
    rows, overlay = [], []
    m = len(pairs)
    for a, b in pairs:
        diff = mean_ranks[a] - mean_ranks[b]
        z = diff / math.sqrt(var * (1 / ns[a] + 1 / ns[b]))
        praw = 2 * stats.norm.sf(abs(z))
        padj = min(1.0, praw * m)
        rows.append([f"{names[a]} vs. {names[b]}", diff, sig(padj, alpha), stars(padj, alpha), fmt_p(padj)])
        overlay.append({"a": idx[a], "b": idx[b], "p": padj, "stars": stars(padj, alpha)})
    r.table("Dunn's multiple comparisons test", ["Comparison", "Mean rank diff.", "Significant?", "Summary", "Adjusted P"], rows)
    r.overlay = {"kind": "pairs", "pairs": overlay}
    return r


def _friedman(table, idx, names, alpha):
    M = _paired_matrix(table, idx)
    require(len(M) >= 2 and M.shape[1] >= 3, "Friedman test needs ≥ 3 columns and ≥ 2 complete rows.")
    chi, p = stats.friedmanchisquare(*M.T)
    n, k = M.shape
    R = np.apply_along_axis(stats.rankdata, 1, M)
    rank_sums = R.sum(axis=0)
    r = Result("Friedman test")
    r.kv("Friedman test", [
        ("P value", fmt_p(p)), ("P value summary", stars(p, alpha)),
        (f"Are medians signif. different (P < {alpha})?", sig(p, alpha)),
        ("Number of groups", k), ("Friedman statistic", chi),
    ])
    rows, overlay = [], []
    pairs = list(itertools.combinations(range(k), 2))
    se = math.sqrt(k * (k + 1) / (6 * n))
    for a, b in pairs:
        diff = rank_sums[a] - rank_sums[b]
        z = (diff / n) / se
        padj = min(1.0, 2 * stats.norm.sf(abs(z)) * len(pairs))
        rows.append([f"{names[a]} vs. {names[b]}", diff, sig(padj, alpha), stars(padj, alpha), fmt_p(padj)])
        overlay.append({"a": idx[a], "b": idx[b], "p": padj, "stars": stars(padj, alpha)})
    r.table("Dunn's multiple comparisons test", ["Comparison", "Rank sum diff.", "Significant?", "Summary", "Adjusted P"], rows)
    r.overlay = {"kind": "pairs", "pairs": overlay}
    return r


# ---------------------------------------------------------------------------
# Two-way ANOVA (grouped tables)
# ---------------------------------------------------------------------------

def two_way(table, params):
    import pandas as pd
    import statsmodels.formula.api as smf
    from statsmodels.stats.anova import anova_lm

    idx = selected(table, params)
    alpha = float(params.get("alpha", 0.05))
    method = params.get("comparison", "sidak")
    compare = params.get("compareWithin", "rows")  # compare columns within each row
    recs = []
    for ci in idx:
        for ri in range(table.nrows):
            for v in table.Y[ci][ri]:
                if np.isfinite(v):
                    recs.append({"y": v, "col": f"c{ci}", "row": f"r{ri}"})
    df = pd.DataFrame(recs)
    require(len(df) > 0, "No data.")
    require(df["col"].nunique() >= 2 or df["row"].nunique() >= 2, "Need at least two rows or two columns.")
    reps = df.groupby(["row", "col"]).size()
    interaction = reps.min() >= 2 and bool(params.get("interaction", True))
    formula = "y ~ C(row, Sum) * C(col, Sum)" if interaction else "y ~ C(row, Sum) + C(col, Sum)"
    with quiet():
        model = smf.ols(formula, data=df).fit()
        tab = anova_lm(model, typ=3)
    r = Result("Two-way ANOVA (ordinary)")
    label = {"C(row, Sum)": "Row Factor", "C(col, Sum)": "Column Factor",
             "C(row, Sum):C(col, Sum)": "Interaction", "Residual": "Residual"}
    rows = []
    ss_total = sum(tab.loc[k, "sum_sq"] for k in tab.index if k != "Intercept")
    for key in ["C(row, Sum):C(col, Sum)", "C(row, Sum)", "C(col, Sum)", "Residual"]:
        if key not in tab.index:
            continue
        rr = tab.loc[key]
        ms = rr["sum_sq"] / rr["df"]
        if key == "Residual":
            rows.append([label[key], rr["sum_sq"], int(rr["df"]), ms, "", "", ""])
        else:
            p = rr["PR(>F)"]
            rows.append([label[key], rr["sum_sq"], int(rr["df"]), ms,
                         f"F ({int(rr['df'])}, {int(tab.loc['Residual', 'df'])}) = {fmt(rr['F'])}", fmt_p(p),
                         f"{rr['sum_sq'] / ss_total * 100:.2f}"])
    r.table("ANOVA table", ["Source of variation", "SS", "DF", "MS", "F (DFn, DFd)", "P value", "% of total variation"], rows)
    summ = []
    for key in ["C(row, Sum):C(col, Sum)", "C(row, Sum)", "C(col, Sum)"]:
        if key in tab.index:
            p = tab.loc[key, "PR(>F)"]
            summ.append([label[key], fmt_p(p), stars(p, alpha), sig(p, alpha)])
    r.table("Summary", ["Source of variation", "P value", "P value summary", "Significant?"], summ)
    if not interaction:
        r.warn("No replicates (or interaction disabled): fitted a main-effects-only model.")

    mse = model.mse_resid
    dfe = model.df_resid
    if method not in ("none", "", None):
        cell = df.groupby(["row", "col"])["y"].agg(["mean", "count"])
        overlay = []
        all_rows = []
        groups = sorted(df["row"].unique(), key=lambda s: int(s[1:])) if compare == "rows" else \
            sorted(df["col"].unique(), key=lambda s: int(s[1:]))
        fam = 0
        plans = []
        for g in groups:
            sub = cell.xs(g, level=0 if compare == "rows" else 1)
            keys = sorted(sub.index, key=lambda s: int(s[1:]))
            plans.append((g, sub, keys))
            fam += len(keys) * (len(keys) - 1) // 2
        for g, sub, keys in plans:
            if len(keys) < 2:
                continue
            means = [sub.loc[k, "mean"] for k in keys]
            ns = [sub.loc[k, "count"] for k in keys]
            if compare == "rows":
                nm = [table.names[int(k[1:])] for k in keys]
                gname = table.row_labels[int(g[1:])]
            else:
                nm = [table.row_labels[int(k[1:])] for k in keys]
                gname = table.names[int(g[1:])]
            fam_size = fam if method != "tukey" else None
            comps = pairwise_pooled(means, ns, nm, mse, dfe, method=method if method != "dunnett" else "sidak",
                                    alpha=alpha, family_size=fam_size)
            for c in comps:
                all_rows.append([f"{gname}: {c['label']}", c["diff"], f"{fmt(c['lo'])} to {fmt(c['hi'])}",
                                 sig(c["p"], alpha), c["stars"], fmt_p(c["p"])])
                if compare == "rows":
                    overlay.append({"row": int(g[1:]), "a": int(keys[c["a"]][1:]), "b": int(keys[c["b"]][1:]),
                                    "p": c["p"], "stars": c["stars"]})
        r.table(f"{MC_METHODS.get(method, method)}'s multiple comparisons test", COMPARISON_COLUMNS, all_rows)
        r.overlay = {"kind": "grouped-pairs", "pairs": overlay}
    return r


# ---------------------------------------------------------------------------
# Exact conditional distributions of rank statistics (valid with ties)
# ---------------------------------------------------------------------------
EXACT_MAX = 50


def _tail_p(dist, support, obs, center, alternative):
    """dist: probabilities over integer support (doubled statistic)."""
    tol = 1e-7
    if alternative == "greater":
        return float(dist[support >= obs - tol].sum())
    if alternative == "less":
        return float(dist[support <= obs + tol].sum())
    return float(min(1.0, dist[np.abs(support - center) >= abs(obs - center) - tol].sum()))


def rank_sum_p(x, y, alternative="two-sided"):
    """P value of the Wilcoxon-Mann-Whitney test for H1: x tends to be larger (alternative='greater').

    Exact conditional permutation distribution of the rank sum of *x* using mid-ranks
    (dynamic programming over doubled ranks), as StatXact / R coin; normal
    approximation with tie and continuity correction for large samples."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    n1, n2 = len(x), len(y)
    N = n1 + n2
    r2 = np.rint(2 * stats.rankdata(np.concatenate([x, y]))).astype(int)
    obs = int(r2[:n1].sum())
    if N <= EXACT_MAX:
        S = int(r2.sum())
        dp = np.zeros((n1 + 1, S + 1))
        dp[0, 0] = 1.0
        for v in r2:
            dp[1:, v:] += dp[:-1, :S + 1 - v].copy()
        dist = dp[n1] / dp[n1].sum()
        support = np.arange(S + 1)
        return _tail_p(dist, support, obs, n1 * (N + 1), alternative), True
    _, t = np.unique(np.concatenate([x, y]), return_counts=True)
    mu = n1 * (N + 1) / 2
    var = n1 * n2 / 12 * ((N + 1) - (t ** 3 - t).sum() / (N * (N - 1)))
    w = obs / 2 - mu
    if alternative == "greater":
        z = (w - 0.5) / math.sqrt(var)
        return float(stats.norm.sf(z)), False
    if alternative == "less":
        z = (w + 0.5) / math.sqrt(var)
        return float(stats.norm.cdf(z)), False
    z = (abs(w) - 0.5) / math.sqrt(var)
    return float(min(1.0, 2 * stats.norm.sf(z))), False


def signed_rank_p(d, alternative="two-sided"):
    """Wilcoxon signed-rank P for H1: differences tend to be positive (alternative='greater').

    Zero differences are dropped (Wilcoxon's method); with tied |d| the exact
    conditional distribution over the 2^n sign patterns is computed with mid-ranks."""
    d = np.asarray(d, float)
    d = d[d != 0]
    n = len(d)
    if n == 0:
        return 1.0, True
    r2 = np.rint(2 * stats.rankdata(np.abs(d))).astype(int)
    obs = int(r2[d > 0].sum())
    S = int(r2.sum())
    if n <= EXACT_MAX:
        dist = np.zeros(S + 1)
        dist[0] = 1.0
        for v in r2:
            new = dist.copy()
            new[v:] += dist[:S + 1 - v]
            dist = new
        dist /= dist.sum()
        return _tail_p(dist, np.arange(S + 1), obs, S / 2, alternative), True
    _, t = np.unique(np.abs(d), return_counts=True)
    mu = n * (n + 1) / 4
    var = n * (n + 1) * (2 * n + 1) / 24 - (t ** 3 - t).sum() / 48
    w = obs / 2 - mu
    if alternative == "greater":
        return float(stats.norm.sf((w - 0.5) / math.sqrt(var))), False
    if alternative == "less":
        return float(stats.norm.cdf((w + 0.5) / math.sqrt(var))), False
    return float(min(1.0, 2 * stats.norm.sf((abs(w) - 0.5) / math.sqrt(var)))), False
