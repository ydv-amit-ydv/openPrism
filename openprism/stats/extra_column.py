"""Additional analyses of column data: variances, distributions, robust and
trend tests, nonparametric repeated measures and post hoc tests, effect sizes,
one-sample tests and intervals, randomness / time-series tests, circular
statistics, reliability and agreement, and P-value adjustment.

Every function takes a parsed table and a parameter dict and returns a
:class:`Result`. Formulas follow the cited textbooks; the validation suite
(``validation/``) compares the results with R.
"""
from __future__ import annotations

import itertools
import math

import numpy as np
from scipy import optimize, special, stats

from .common import AnalysisError, Result, fmt, fmt_p, require, sig, stars
from .descriptive import selected

SEED = 20240611  # fixed seed: Monte-Carlo / permutation results are reproducible


def _alpha(params):
    return float(params.get("alpha", 0.05))


def groups(table, params, min_groups=1, min_n=1):
    idx = selected(table, params)
    names, vals = [], []
    for i in idx:
        v = table.column_values(i)
        if len(v) >= min_n:
            names.append(table.names[i])
            vals.append(v.astype(float))
    require(len(vals) >= min_groups, f"This analysis needs at least {min_groups} data set(s) with {min_n}+ values each.")
    return names, vals


def matched(table, params, min_cols=2):
    """Rows with complete data across the selected columns (subjects × conditions)."""
    idx = selected(table, params)
    require(len(idx) >= min_cols, f"Select at least {min_cols} data sets.")
    M = np.column_stack([table.Y[i][:, 0] if table.Y[i].shape[1] == 1 else np.nanmean(table.Y[i], axis=1) for i in idx])
    keep = np.all(np.isfinite(M), axis=1)
    M = M[keep]
    require(len(M) >= 2, "Need at least two rows (subjects) with values in every selected column.")
    return [table.names[i] for i in idx], M, int((~keep).sum())


def _row(name, stat, df, p, alpha, note=""):
    return [name, fmt(stat), df if isinstance(df, str) else fmt(df), fmt_p(p), stars(p, alpha), note]


TEST_COLS = ["Test", "Statistic", "df", "P value", "Summary", "Notes"]


# ---------------------------------------------------------------- variances
def variance_tests(table, params):
    names, gs = groups(table, params, 2, 2)
    alpha = _alpha(params)
    r = Result("Compare variances")
    r.table("Spread of each group", ["Group", "n", "SD", "Variance", "MAD (scaled to SD)", "IQR"],
            [[nm, len(g), g.std(ddof=1), g.var(ddof=1), stats.median_abs_deviation(g, scale="normal"),
              float(np.subtract(*np.percentile(g, [75, 25])))] for nm, g in zip(names, gs)])
    rows = []
    if len(gs) == 2:
        v1, v2 = gs[1].var(ddof=1), gs[0].var(ddof=1)  # ratio B / A (second / first data set)
        d1, d2 = len(gs[1]) - 1, len(gs[0]) - 1
        F = v1 / v2
        p = 2 * min(stats.f.sf(F, d1, d2), stats.f.cdf(F, d1, d2))
        lo, hi = F / stats.f.ppf(1 - alpha / 2, d1, d2), F / stats.f.ppf(alpha / 2, d1, d2)
        rows.append(_row(f"F test (variance of {names[1]} / {names[0]})", F, f"{d1}, {d2}", min(p, 1.0), alpha,
                         f"ratio {fmt(F)}, {int((1 - alpha) * 100)}% CI {fmt(lo)} to {fmt(hi)}; assumes Gaussian"))
    W, p = stats.levene(*gs, center="mean")
    rows.append(_row("Levene (mean-centered)", W, f"{len(gs) - 1}, {sum(map(len, gs)) - len(gs)}", p, alpha, "robust to mild non-normality"))
    W, p = stats.levene(*gs, center="median")
    rows.append(_row("Brown-Forsythe (median-centered Levene)", W, f"{len(gs) - 1}, {sum(map(len, gs)) - len(gs)}", p, alpha, "recommended general-purpose test"))
    B, p = stats.bartlett(*gs)
    rows.append(_row("Bartlett", B, len(gs) - 1, p, alpha, "assumes Gaussian; very sensitive to non-normality"))
    X, p = stats.fligner(*gs)
    rows.append(_row("Fligner-Killeen", X, len(gs) - 1, p, alpha, "nonparametric, robust to outliers"))
    if len(gs) == 2:
        AB, p = stats.ansari(gs[0], gs[1])
        rows.append(_row("Ansari-Bradley (scale)", AB, "", p, alpha, "nonparametric; assumes equal medians"))
        Z, p = stats.mood(gs[0], gs[1])
        rows.append(_row("Mood's test of scale", Z, "", p, alpha, "nonparametric; assumes equal medians"))
    r.table("Tests of equal variances (H0: all population variances are equal)", TEST_COLS, rows)
    return r


# ---------------------------------------------------------------- distributions
def distribution_tests(table, params):
    names, gs = groups(table, params, 2, 2)
    alpha = _alpha(params)
    r = Result("Compare distributions")
    rows = []
    rng = np.random.default_rng(SEED)
    if len(gs) == 2:
        a, b = gs
        res = stats.ks_2samp(a, b)
        rows.append(_row("Kolmogorov-Smirnov (two-sample)", res.statistic, "", res.pvalue, alpha, "largest gap between the cumulative distributions"))
        res = stats.cramervonmises_2samp(a, b)
        rows.append(_row("Cramér-von Mises (two-sample)", res.statistic, "", res.pvalue, alpha, "integrated squared difference; more sensitive than KS to many small differences"))
        if min(len(a), len(b)) >= 5:
            try:
                res = stats.epps_singleton_2samp(a, b)
                rows.append(_row("Epps-Singleton", res.statistic, "", res.pvalue, alpha, "based on the empirical characteristic function; works with discrete data"))
            except Exception:  # noqa: BLE001
                pass
        res = stats.brunnermunzel(a, b)
        rows.append(_row("Brunner-Munzel", res.statistic, "", res.pvalue, alpha, "tests P(X<Y)=½ without assuming equal shapes (generalized Wilcoxon)"))
        U, p = stats.mannwhitneyu(a, b, alternative="two-sided")
        rows.append(_row("Mann-Whitney U", U, "", p, alpha, "ranks; assumes equal shapes to be read as a shift"))
    res = stats.anderson_ksamp(gs, method=stats.PermutationMethod(n_resamples=9999, rng=rng))
    rows.append(_row(f"Anderson-Darling k-sample ({len(gs)} groups)", res.statistic, "", res.pvalue, alpha, "permutation P value (9 999 resamples, fixed seed)"))
    try:
        stat, p, med, _tab = stats.median_test(*gs)
        rows.append(_row("Mood's median test", stat, len(gs) - 1, p, alpha, f"grand median {fmt(med)}"))
    except ValueError:
        pass
    if len(gs) > 2:
        H, p = stats.kruskal(*gs)
        rows.append(_row("Kruskal-Wallis", H, len(gs) - 1, p, alpha, "difference in mean ranks"))
    r.table("Tests of identical distributions (H0: all groups come from the same distribution)", TEST_COLS, rows)
    if len(gs) > 2:
        pairs = list(itertools.combinations(range(len(gs)), 2))
        raw = [stats.ks_2samp(gs[i], gs[j]).pvalue for i, j in pairs]
        adj = _holm(raw)
        r.table("Pairwise Kolmogorov-Smirnov tests (Holm-adjusted)", ["Comparison", "D", "P value", "Adjusted P", "Summary"],
                [[f"{names[i]} vs. {names[j]}", stats.ks_2samp(gs[i], gs[j]).statistic, fmt_p(p0), fmt_p(pa), stars(pa, alpha)]
                 for (i, j), p0, pa in zip(pairs, raw, adj)])
    return r


def _holm(p):
    p = np.asarray(p, float)
    m = len(p)
    out = np.empty(m)
    run = 0.0
    for rank, i in enumerate(np.argsort(p)):
        run = max(run, (m - rank) * p[i])
        out[i] = min(1.0, run)
    return out


# ---------------------------------------------------------------- robust (trimmed means)
def _trim_parts(x, trim):
    x = np.sort(x)
    n = len(x)
    g = int(math.floor(trim * n))
    h = n - 2 * g
    tm = float(stats.trim_mean(x, trim)) if g else float(x.mean())
    w = x.copy()
    if g:
        w[:g] = x[g]
        w[n - g:] = x[n - g - 1]
    sw2 = w.var(ddof=1)
    d = (n - 1) * sw2 / (h * (h - 1))
    return tm, d, h


def yuen(a, b, trim=0.2, level=0.95):
    m1, d1, h1 = _trim_parts(a, trim)
    m2, d2, h2 = _trim_parts(b, trim)
    se = math.sqrt(d1 + d2)
    t = (m1 - m2) / se
    df = (d1 + d2) ** 2 / (d1 ** 2 / (h1 - 1) + d2 ** 2 / (h2 - 1))
    p = 2 * stats.t.sf(abs(t), df)
    q = stats.t.ppf(0.5 + level / 2, df)
    return {"diff": m1 - m2, "t": t, "df": df, "p": p, "lo": m1 - m2 - q * se, "hi": m1 - m2 + q * se, "se": se}


def t1way(gs, trim=0.2):
    """Wilcox's heteroscedastic one-way ANOVA on trimmed means."""
    parts = [_trim_parts(g, trim) for g in gs]
    J = len(gs)
    w = np.array([1 / d for _, d, _ in parts])
    tm = np.array([m for m, _, _ in parts])
    h = np.array([hh for _, _, hh in parts], float)
    U = w.sum()
    xt = (w * tm).sum() / U
    A = (w * (tm - xt) ** 2).sum() / (J - 1)
    lam = ((1 - w / U) ** 2 / (h - 1)).sum()
    B = 2 * (J - 2) / (J ** 2 - 1) * lam
    F = A / (1 + B)
    df2 = 1 / (3 / (J ** 2 - 1) * lam)
    return F, J - 1, df2, float(stats.f.sf(F, J - 1, df2))


def robust_compare(table, params):
    names, gs = groups(table, params, 2, 4)
    alpha = _alpha(params)
    trim = float(params.get("trim", 0.2))
    require(0 <= trim < 0.5, "Trimming must be between 0 and 0.5.")
    r = Result(f"Robust comparison of {int(trim * 100)}% trimmed means")
    r.table("Robust location estimates", ["Group", "n", "Mean", f"{int(trim * 100)}% trimmed mean", "Median", "Winsorized SD", "SE of trimmed mean"],
            [[nm, len(g), g.mean(), _trim_parts(g, trim)[0], np.median(g), math.sqrt(_trim_parts(g, trim)[1] * _trim_parts(g, trim)[2] * (_trim_parts(g, trim)[2] - 1) / (len(g) - 1)),
              math.sqrt(_trim_parts(g, trim)[1])] for nm, g in zip(names, gs)])
    if len(gs) == 2:
        y = yuen(gs[0], gs[1], trim, 1 - alpha)
        r.kv("Yuen-Welch test (two groups)", [
            ("Difference of trimmed means", y["diff"]), (f"{int((1 - alpha) * 100)}% CI", f"{fmt(y['lo'])} to {fmt(y['hi'])}"),
            ("t", y["t"]), ("df (Welch)", y["df"]), ("P value", fmt_p(y["p"])), ("Summary", stars(y["p"], alpha)),
            (f"Significant (P < {alpha})?", sig(y["p"], alpha))])
    else:
        F, d1, d2, p = t1way(gs, trim)
        r.kv("Heteroscedastic one-way ANOVA of trimmed means (Wilcox t1way)", [
            ("F", F), ("df numerator", d1), ("df denominator", d2), ("P value", fmt_p(p)), ("Summary", stars(p, alpha)),
            (f"Significant (P < {alpha})?", sig(p, alpha))])
        pairs = list(itertools.combinations(range(len(gs)), 2))
        ys = [yuen(gs[i], gs[j], trim, 1 - alpha) for i, j in pairs]
        adj = _holm([y["p"] for y in ys])
        r.table("Pairwise Yuen-Welch tests (Holm-adjusted)", ["Comparison", "Diff. of trimmed means", "CI (unadjusted)", "t", "df", "P value", "Adjusted P", "Summary"],
                [[f"{names[i]} vs. {names[j]}", y["diff"], f"{fmt(y['lo'])} to {fmt(y['hi'])}", y["t"], y["df"], fmt_p(y["p"]), fmt_p(pa), stars(pa, alpha)]
                 for (i, j), y, pa in zip(pairs, ys, adj)])
    return r


# ---------------------------------------------------------------- trend across ordered groups
def jonckheere(gs, permutations=0):
    k = len(gs)
    J = 0.0
    for i in range(k):
        for j in range(i + 1, k):
            a, b = gs[i][:, None], gs[j][None, :]
            J += (a < b).sum() + 0.5 * (a == b).sum()
    n = np.array([len(g) for g in gs], float)
    N = n.sum()
    allv = np.concatenate(gs)
    _, t = np.unique(allv, return_counts=True)
    t = t.astype(float)
    mean = (N ** 2 - (n ** 2).sum()) / 4
    var = ((N * (N - 1) * (2 * N + 5) - (n * (n - 1) * (2 * n + 5)).sum() - (t * (t - 1) * (2 * t + 5)).sum()) / 72
           + (n * (n - 1) * (n - 2)).sum() * (t * (t - 1) * (t - 2)).sum() / (36 * N * (N - 1) * (N - 2))
           + (n * (n - 1)).sum() * (t * (t - 1)).sum() / (8 * N * (N - 1)))
    z = (J - mean) / math.sqrt(var)
    out = {"J": J, "mean": mean, "sd": math.sqrt(var), "z": z, "p": 2 * stats.norm.sf(abs(z))}
    if permutations:
        rng = np.random.default_rng(SEED)
        sizes = np.cumsum([len(g) for g in gs])[:-1]
        cnt = 0
        for _ in range(permutations):
            perm = np.split(rng.permutation(allv), sizes)
            Jp = 0.0
            for i in range(k):
                for j in range(i + 1, k):
                    a, b = perm[i][:, None], perm[j][None, :]
                    Jp += (a < b).sum() + 0.5 * (a == b).sum()
            cnt += abs(Jp - mean) >= abs(J - mean) - 1e-9
        out["p_perm"] = (cnt + 1) / (permutations + 1)
    return out


def trend_tests(table, params):
    names, gs = groups(table, params, 3, 1)
    alpha = _alpha(params)
    k = len(gs)
    r = Result("Test for trend across ordered groups")
    n = np.array([len(g) for g in gs], float)
    means = np.array([g.mean() for g in gs])
    N = n.sum()
    sse = sum(((g - g.mean()) ** 2).sum() for g in gs)
    dfe = N - k
    rows = []
    if dfe > 0:
        mse = sse / dfe
        x = np.arange(1, k + 1, dtype=float)
        c = x - x.mean()
        L = (c * means).sum()
        ss_lin = L ** 2 / (c ** 2 / n).sum()
        F = ss_lin / mse
        p = stats.f.sf(F, 1, dfe)
        grand = (n * means).sum() / N
        ss_between = (n * (means - grand) ** 2).sum()
        slope = L / (c ** 2).sum()
        rows.append(_row("Post test for linear trend (ANOVA contrast)", F, f"1, {int(dfe)}", p, alpha, f"slope {fmt(slope)} per group; R² {fmt(ss_lin / (ss_between + sse))}"))
        if k > 2:
            Fn = (ss_between - ss_lin) / (k - 2) / mse
            pn = stats.f.sf(Fn, k - 2, dfe)
            rows.append(_row("Nonlinear (non-trend) variation", Fn, f"{k - 2}, {int(dfe)}", pn, alpha, "significant = means do not follow a straight line"))
    jt = jonckheere(gs, permutations=min(max(int(params.get("permutations", 9999)), 0), 200000) if N <= 400 else 0)
    note = f"J = {fmt(jt['J'])} (expected {fmt(jt['mean'])} under H0); normal approximation with ties correction"
    rows.append(_row("Jonckheere-Terpstra (nonparametric)", jt["z"], "", jt["p"], alpha, note))
    if "p_perm" in jt:
        rows.append(_row("Jonckheere-Terpstra, permutation P", jt["J"], "", jt["p_perm"], alpha, "9 999 permutations, fixed seed"))
    order = np.concatenate([np.full(len(g), j + 1) for j, g in enumerate(gs)])
    rho, p = stats.spearmanr(order, np.concatenate(gs))
    rows.append(_row("Spearman correlation of value with group order", rho, "", p, alpha, ""))
    tau, p = stats.kendalltau(order, np.concatenate(gs))
    rows.append(_row("Kendall tau-b with group order", tau, "", p, alpha, ""))
    if params.get("repeated"):
        try:
            _, M, dropped = matched(table, params, 3)
            res = stats.page_trend_test(M)
            rows.append(_row("Page's L test (repeated measures)", res.statistic, "", res.pvalue, alpha,
                             f"{len(M)} complete rows; one-sided test of increasing trend" + (f"; {dropped} incomplete rows skipped" if dropped else "")))
        except AnalysisError:
            pass
    r.table("Trend tests (groups ordered left to right as in the data table)", TEST_COLS, rows)
    r.table("Group means", ["Group (order)", "n", "Mean", "Median"], [[f"{j + 1}. {nm}", len(g), g.mean(), np.median(g)] for j, (nm, g) in enumerate(zip(names, gs))])
    return r


# ---------------------------------------------------------------- nonparametric repeated measures
def quade(M):
    n, k = M.shape
    rng_ = M.max(axis=1) - M.min(axis=1)
    Q = stats.rankdata(rng_)
    R = np.apply_along_axis(stats.rankdata, 1, M)
    S = Q[:, None] * (R - (k + 1) / 2)
    A = (S ** 2).sum()
    B = (S.sum(axis=0) ** 2).sum() / n
    if A == B:
        return np.nan, k - 1, (n - 1) * (k - 1), np.nan
    F = (n - 1) * B / (A - B)
    return F, k - 1, (n - 1) * (k - 1), float(stats.f.sf(F, k - 1, (n - 1) * (k - 1)))


def rm_nonparametric(table, params):
    names, M, dropped = matched(table, params, 2)
    alpha = _alpha(params)
    n, k = M.shape
    r = Result("Nonparametric repeated measures")
    if dropped:
        r.warn(f"{dropped} row(s) with missing values were excluded (these tests need complete rows).")
    rows = []
    binary = np.isin(M, [0, 1]).all()
    if k >= 3:
        chi, p = stats.friedmanchisquare(*M.T)
        W = chi / (n * (k - 1))
        rows.append(_row("Friedman", chi, k - 1, p, alpha, f"Kendall's W (effect size) = {fmt(W)}"))
        F, d1, d2, p = quade(M)
        rows.append(_row("Quade", F, f"{d1}, {d2}", p, alpha, "weights subjects by their range; often more powerful than Friedman for few conditions"))
        if binary:
            from statsmodels.stats.contingency_tables import cochrans_q
            res = cochrans_q(M)
            rows.append(_row("Cochran's Q (0/1 outcomes)", res.statistic, res.df, res.pvalue, alpha, "matched proportions"))
        res = stats.page_trend_test(M)
        rows.append(_row("Page's L (ordered conditions)", res.statistic, "", res.pvalue, alpha, "one-sided test of increasing trend left to right"))
    else:
        res = stats.wilcoxon(M[:, 0], M[:, 1])
        rows.append(_row("Wilcoxon signed-rank", res.statistic, "", res.pvalue, alpha, ""))
        res = stats.binomtest(int((M[:, 0] > M[:, 1]).sum()), int((M[:, 0] != M[:, 1]).sum()))
        rows.append(_row("Sign test", res.statistic, "", res.pvalue, alpha, "uses only the direction of each change"))
    r.table(f"Tests ({n} subjects × {k} conditions)", TEST_COLS, rows)
    R = np.apply_along_axis(stats.rankdata, 1, M)
    r.table("Mean rank of each condition", ["Condition", "Median", "Mean rank", "Sum of ranks"],
            [[nm, np.median(M[:, j]), R[:, j].mean(), R[:, j].sum()] for j, nm in enumerate(names)])
    if k >= 3:
        pairs = list(itertools.combinations(range(k), 2))
        se = math.sqrt(k * (k + 1) / (6 * n))
        nem = []
        wil = []
        for i, j in pairs:
            q = abs(R[:, i].mean() - R[:, j].mean()) / se * math.sqrt(2)
            nem.append(float(stats.studentized_range.sf(q, k, np.inf)))
            d = M[:, i] - M[:, j]
            wil.append(stats.wilcoxon(M[:, i], M[:, j]).pvalue if np.any(d != 0) else 1.0)
        wadj = _holm(wil)
        r.table("Post hoc comparisons", ["Comparison", "Nemenyi P (all pairs)", "Wilcoxon P", "Wilcoxon P (Holm)", "Summary (Holm)"],
                [[f"{names[i]} vs. {names[j]}", fmt_p(pn), fmt_p(pw), fmt_p(pa), stars(pa, alpha)] for (i, j), pn, pw, pa in zip(pairs, nem, wil, wadj)])
    return r


# ---------------------------------------------------------------- nonparametric post hoc
P_ADJUST = {"holm": "Holm", "bonferroni": "Bonferroni", "bh": "Benjamini-Hochberg FDR", "hochberg": "Hochberg", "none": "None"}


def adjust_p(p, method):
    from statsmodels.stats.multitest import multipletests
    p = np.asarray(p, float)
    if method == "none" or len(p) == 0:
        return p
    m = {"holm": "holm", "bonferroni": "bonferroni", "bh": "fdr_bh", "hochberg": "simes-hochberg", "by": "fdr_by",
         "sidak": "sidak", "holm-sidak": "holm-sidak", "hommel": "hommel", "bky": "fdr_tsbky"}[method]
    return multipletests(p, method=m)[1]


def np_posthoc(table, params):
    names, gs = groups(table, params, 3, 1)
    alpha = _alpha(params)
    method = params.get("method", "dunn")
    adj = params.get("adjust", "holm")
    k = len(gs)
    allv = np.concatenate(gs)
    N = len(allv)
    ranks = stats.rankdata(allv)
    sizes = np.array([len(g) for g in gs])
    splits = np.split(ranks, np.cumsum(sizes)[:-1])
    Rbar = np.array([s.mean() for s in splits])
    _, t = np.unique(allv, return_counts=True)
    tie = (t ** 3 - t).sum()
    H, pH = stats.kruskal(*gs)
    r = Result("Nonparametric multiple comparisons")
    r.kv("Kruskal-Wallis test", [("H", H), ("df", k - 1), ("P value", fmt_p(pH)), ("Summary", stars(pH, alpha)),
                                 ("Epsilon² (effect size)", H / ((N ** 2 - 1) / (N + 1)))])
    pairs = list(itertools.combinations(range(k), 2))
    rows = []
    if method == "dunn":
        title = "Dunn's test"
        raw = []
        for i, j in pairs:
            se = math.sqrt((N * (N + 1) / 12 - tie / (12 * (N - 1))) * (1 / sizes[i] + 1 / sizes[j]))
            z = (Rbar[i] - Rbar[j]) / se
            raw.append(2 * stats.norm.sf(abs(z)))
            rows.append([f"{names[i]} vs. {names[j]}", Rbar[i] - Rbar[j], z])
        ps = raw
    elif method == "conover":
        title = "Conover-Iman test"
        S2 = ((ranks ** 2).sum() - N * (N + 1) ** 2 / 4) / (N - 1)
        raw = []
        for i, j in pairs:
            se = math.sqrt(S2 * (N - 1 - H) / (N - k) * (1 / sizes[i] + 1 / sizes[j]))
            tt = (Rbar[i] - Rbar[j]) / se
            raw.append(2 * stats.t.sf(abs(tt), N - k))
            rows.append([f"{names[i]} vs. {names[j]}", Rbar[i] - Rbar[j], tt])
        ps = raw
    elif method == "dscf":
        title = "Dwass-Steel-Critchlow-Fligner test"
        adj = "none"  # family-wise error is controlled by the studentized range distribution
        raw = []
        for i, j in pairs:
            a, b = gs[i], gs[j]
            v = np.concatenate([a, b])
            rk = stats.rankdata(v)
            m = len(v)
            _, tt = np.unique(v, return_counts=True)
            W = rk[:len(a)].sum()
            E = len(a) * (m + 1) / 2
            var = len(a) * len(b) / 12 * ((m + 1) - (tt ** 3 - tt).sum() / (m * (m - 1)))
            z = (W - E) / math.sqrt(var)
            raw.append(float(stats.studentized_range.sf(abs(z) * math.sqrt(2), k, np.inf)))
            rows.append([f"{names[i]} vs. {names[j]}", Rbar[i] - Rbar[j], z * math.sqrt(2)])
        ps = raw
    else:
        title = "Pairwise Mann-Whitney tests"
        raw = []
        for i, j in pairs:
            U, p = stats.mannwhitneyu(gs[i], gs[j], alternative="two-sided")
            raw.append(p)
            rows.append([f"{names[i]} vs. {names[j]}", np.median(gs[i]) - np.median(gs[j]), U])
        ps = raw
    pa = adjust_p(ps, adj)
    stat_name = {"dunn": "z", "conover": "t", "dscf": "W* (studentized)", "mw": "U"}.get(method, "Statistic")
    diff_name = "Median difference" if method == "mw" else "Mean rank difference"
    r.table(f"{title} — adjustment: {P_ADJUST.get(adj, 'family-wise (studentized range)') if method != 'dscf' else 'built in (studentized range)'}",
            ["Comparison", diff_name, stat_name, "Unadjusted P", "Adjusted P", "Summary", "Significant?"],
            [row + [fmt_p(p0), fmt_p(p1), stars(p1, alpha), sig(p1, alpha)] for row, p0, p1 in zip(rows, raw, pa)])
    r.table("Mean ranks", ["Group", "n", "Median", "Mean rank"], [[nm, len(g), np.median(g), rb] for nm, g, rb in zip(names, gs, Rbar)])
    return r


# ---------------------------------------------------------------- effect sizes
def _nct_ci(t, df, level):
    """CI of the noncentrality parameter by inverting the noncentral t distribution."""
    lo_q, hi_q = 0.5 + level / 2, 0.5 - level / 2

    def solve(q):
        f = lambda nc: stats.nct.cdf(t, df, nc) - q  # noqa: E731
        a, b = t - 10 - abs(t), t + 10 + abs(t)
        try:
            return optimize.brentq(f, a, b)
        except ValueError:
            return np.nan
    return solve(lo_q), solve(hi_q)


def _ncf_ci(F, d1, d2, level):
    """CI of the noncentrality parameter λ of a noncentral F distribution."""
    def solve(q):
        f = lambda lam: stats.ncf.cdf(F, d1, d2, lam) - q  # noqa: E731
        if f(0) < q:
            return 0.0
        hi = max(10.0, F * d1 * 4)
        while f(hi) > 0 and hi < 1e7:
            hi *= 2
        return optimize.brentq(f, 0, hi)
    return solve(0.5 + level / 2), solve(0.5 - level / 2)


def hedges_j(df):
    return math.exp(special.gammaln(df / 2) - math.log(math.sqrt(df / 2)) - special.gammaln((df - 1) / 2))


def effect_sizes(table, params):
    names, gs = groups(table, params, 2, 2)
    alpha = _alpha(params)
    level = 1 - alpha
    pct = f"{int(round(level * 100))}%"
    r = Result("Effect sizes")
    if len(gs) == 2:
        a, b = gs
        n1, n2 = len(a), len(b)
        m1, m2 = a.mean(), b.mean()
        s1, s2 = a.std(ddof=1), b.std(ddof=1)
        df = n1 + n2 - 2
        sp = math.sqrt(((n1 - 1) * s1 ** 2 + (n2 - 1) * s2 ** 2) / df)
        d = (m2 - m1) / sp
        t = d / math.sqrt(1 / n1 + 1 / n2)
        lo, hi = _nct_ci(t, df, level)
        f = math.sqrt(1 / n1 + 1 / n2)
        J = hedges_j(df)
        U = stats.mannwhitneyu(b, a, alternative="two-sided").statistic
        cles = U / (n1 * n2)
        cliff = 2 * cles - 1
        rows = [
            ("Difference of means (B − A)", m2 - m1),
            ("Cohen's d (pooled SD)", d), (f"{pct} CI of d (noncentral t)", f"{fmt(lo * f)} to {fmt(hi * f)}"),
            ("Hedges' g (bias-corrected d)", d * J), (f"{pct} CI of g", f"{fmt(lo * f * J)} to {fmt(hi * f * J)}"),
            ("Glass's Δ (SD of A = control)", (m2 - m1) / s1),
            ("Cohen's d using average SD (d_av)", (m2 - m1) / math.sqrt((s1 ** 2 + s2 ** 2) / 2)),
            ("Point-biserial correlation r", t / math.sqrt(t ** 2 + df)),
            ("Common-language effect size P(B > A)", cles),
            ("Cliff's δ = rank-biserial correlation", cliff),
            ("Ratio of means (B / A)", m2 / m1 if m1 else np.nan),
            ("Variance ratio (B / A)", s2 ** 2 / s1 ** 2),
        ]
        # bootstrap CI for Cliff's delta (percentile, fixed seed)
        rng = np.random.default_rng(SEED)
        Sg = np.sign(b[:, None] - a[None, :])  # Cliff's δ of a resample = mean of the resampled sign matrix
        boots = np.array([Sg[np.ix_(rng.integers(0, n2, n2), rng.integers(0, n1, n1))].mean() for _ in range(2000)])
        rows.insert(10, (f"{pct} CI of Cliff's δ (bootstrap, 2 000 resamples)", f"{fmt(np.percentile(boots, 100 * alpha / 2))} to {fmt(np.percentile(boots, 100 * (1 - alpha / 2)))}"))
        r.kv(f"Unpaired: {names[1]} (B) vs. {names[0]} (A)", rows)
        if n1 == n2:
            dd = b - a
            dz = dd.mean() / dd.std(ddof=1)
            tz = dz * math.sqrt(n1)
            lz, hz = _nct_ci(tz, n1 - 1, level)
            r.kv("If the data are paired (row by row)", [
                ("Cohen's d_z (mean difference / SD of differences)", dz),
                (f"{pct} CI of d_z", f"{fmt(lz / math.sqrt(n1))} to {fmt(hz / math.sqrt(n1))}"),
                ("Hedges' g_z", dz * hedges_j(n1 - 1)),
                ("Cohen's d_rm (corrected for correlation)", dz * math.sqrt(2 * (1 - np.corrcoef(a, b)[0, 1])))])
        r.kv("Conventional benchmarks (Cohen 1988 — use field-specific ones when available)", [
            ("|d| ≈ 0.2", "small"), ("|d| ≈ 0.5", "medium"), ("|d| ≈ 0.8", "large"), ("|Cliff's δ| 0.147 / 0.33 / 0.474", "small / medium / large")])
    k = len(gs)
    if k >= 2:
        allv = np.concatenate(gs)
        N = len(allv)
        grand = allv.mean()
        ssb = sum(len(g) * (g.mean() - grand) ** 2 for g in gs)
        ssw = sum(((g - g.mean()) ** 2).sum() for g in gs)
        sst = ssb + ssw
        dfb, dfw = k - 1, N - k
        msw = ssw / dfw
        F = (ssb / dfb) / msw
        eta = ssb / sst
        lo_l, hi_l = _ncf_ci(F, dfb, dfw, level)
        H, _ = stats.kruskal(*gs)
        r.kv("Variance explained (one-way ANOVA layout)", [
            ("η² (eta squared)", eta), (f"{pct} CI of η² (noncentral F)", f"{fmt(lo_l / (lo_l + N))} to {fmt(hi_l / (hi_l + N))}"),
            ("ω² (omega squared, less biased)", max(0.0, (ssb - dfb * msw) / (sst + msw))),
            ("ε² (epsilon squared)", max(0.0, (ssb - dfb * msw) / sst)),
            ("Cohen's f", math.sqrt(eta / (1 - eta)) if eta < 1 else np.inf),
            ("Rank ε² (Kruskal-Wallis)", H / ((N ** 2 - 1) / (N + 1))),
            ("Benchmarks for η²", "0.01 small, 0.06 medium, 0.14 large")])
    return r


# ---------------------------------------------------------------- one-sample tests & intervals
def tolerance_factor(n, coverage, conf):
    """Two-sided normal tolerance factor (Howe 1969)."""
    z = stats.norm.ppf((1 + coverage) / 2)
    chi = stats.chi2.ppf(1 - conf, n - 1)
    return math.sqrt((n - 1) * (1 + 1 / n) * z ** 2 / chi)


def one_sample_more(table, params):
    names, gs = groups(table, params, 1, 2)
    alpha = _alpha(params)
    m0 = float(params.get("median", 0) or 0)
    s0 = params.get("sd0")
    s0 = float(s0) if s0 not in (None, "") else None
    cov = float(params.get("coverage", 0.95))
    conf = float(params.get("confidence", 0.95))
    q = float(params.get("quantile", 0.5))
    r = Result("One-sample tests and intervals")
    for nm, g in zip(names, gs):
        n = len(g)
        rows = []
        above, below = int((g > m0).sum()), int((g < m0).sum())
        if above + below:
            bt = stats.binomtest(above, above + below, 0.5)
            rows.append((f"Sign test vs. median {fmt(m0)}", ""))
            rows.append(("Values above / below", f"{above} / {below} ({n - above - below} equal, ignored)"))
            rows.append(("P value (exact binomial)", fmt_p(bt.pvalue)))
            rows.append(("Summary", stars(bt.pvalue, alpha)))
        if s0:
            chi = (n - 1) * g.var(ddof=1) / s0 ** 2
            p = 2 * min(stats.chi2.sf(chi, n - 1), stats.chi2.cdf(chi, n - 1))
            rows += [(f"Chi-square test of SD = {fmt(s0)}", ""), ("Chi-square", chi), ("df", n - 1), ("P value", fmt_p(min(1, p))), ("Summary", stars(p, alpha))]
        s = g.std(ddof=1)
        sd_lo = math.sqrt((n - 1) * s ** 2 / stats.chi2.ppf(1 - alpha / 2, n - 1))
        sd_hi = math.sqrt((n - 1) * s ** 2 / stats.chi2.ppf(alpha / 2, n - 1))
        rows += [("Confidence interval of the SD", ""), ("SD", s), (f"{int((1 - alpha) * 100)}% CI of SD (chi-square)", f"{fmt(sd_lo)} to {fmt(sd_hi)}")]
        # distribution-free CI of a quantile (order statistics, exact binomial)
        xs = np.sort(g)
        lo_i = int(stats.binom.ppf(alpha / 2, n, q))
        hi_i = int(stats.binom.ppf(1 - alpha / 2, n, q)) + 1
        qv = float(np.quantile(g, q))
        ci_q = f"{fmt(xs[lo_i - 1])} to {fmt(xs[hi_i - 1])}" if lo_i >= 1 and hi_i <= n else "not available (too few values)"
        rows += [(f"Distribution-free CI of the {fmt(q * 100)}th percentile", ""), ("Percentile", qv), (f"{int((1 - alpha) * 100)}% CI (order statistics)", ci_q)]
        k2 = tolerance_factor(n, cov, conf)
        mu = g.mean()
        tq = stats.t.ppf(1 - alpha / 2, n - 1)
        rows += [(f"Tolerance interval (contains {fmt(cov * 100)}% of the population with {fmt(conf * 100)}% confidence; assumes Gaussian)", ""),
                 ("k factor (Howe)", k2), ("Interval", f"{fmt(mu - k2 * s)} to {fmt(mu + k2 * s)}"),
                 (f"{int((1 - alpha) * 100)}% prediction interval for one new value", f"{fmt(mu - tq * s * math.sqrt(1 + 1 / n))} to {fmt(mu + tq * s * math.sqrt(1 + 1 / n))}")]
        r.kv(nm, rows)
    return r


# ---------------------------------------------------------------- randomness & time series
def runs_test(x):
    med = np.median(x)
    s = x[x != med] > med
    n1, n2 = int(s.sum()), int((~s).sum())
    if n1 == 0 or n2 == 0:
        return np.nan, np.nan, np.nan
    runs = 1 + int((s[1:] != s[:-1]).sum())
    n = n1 + n2
    mu = 2 * n1 * n2 / n + 1
    var = 2 * n1 * n2 * (2 * n1 * n2 - n) / (n ** 2 * (n - 1))
    z = (runs - mu) / math.sqrt(var) if var > 0 else np.nan
    return runs, z, 2 * stats.norm.sf(abs(z)) if np.isfinite(z) else np.nan


def randomness(table, params):
    from statsmodels.stats.diagnostic import acorr_ljungbox
    from statsmodels.stats.stattools import durbin_watson
    from statsmodels.tsa.stattools import acf, adfuller, kpss
    alpha = _alpha(params)
    idx = selected(table, params)
    r = Result("Randomness, autocorrelation and stationarity")
    plots = []
    for i in idx:
        if table.type == "xy":
            order = np.argsort(table.x, kind="stable")
            v = table.row_means(i)[order]
        else:
            v = table.Y[i][:, 0] if table.Y[i].shape[1] == 1 else table.row_means(i)
        v = v[np.isfinite(v)]
        nm = table.names[i]
        if len(v) < 6:
            r.warn(f"{nm}: need at least 6 values in sequence.")
            continue
        n = len(v)
        rows = []
        runs, z, p = runs_test(v)
        rows.append(_row("Wald-Wolfowitz runs test (above/below median)", z, "", p, alpha, f"{runs} runs"))
        lag = min(max(int(params.get("lags") or min(10, max(1, n // 5))), 1), max(1, n - 2))
        lb = acorr_ljungbox(v, lags=[lag], return_df=True)
        rows.append(_row(f"Ljung-Box Q (lags 1-{lag})", float(lb["lb_stat"].iloc[0]), lag, float(lb["lb_pvalue"].iloc[0]), alpha, "H0: no autocorrelation"))
        c = v - v.mean()
        vn = (np.diff(v) ** 2).sum() / (c ** 2).sum()
        zvn = (vn - 2) / math.sqrt(4 * (n - 2) / ((n - 1) * (n + 1)))
        rows.append(_row("von Neumann ratio test", vn, "", 2 * stats.norm.sf(abs(zvn)), alpha, "≈2 for independent values; <2 positive, >2 negative serial correlation"))
        rows.append(["Durbin-Watson statistic (mean-centered)", fmt(durbin_watson(c)), "", "", "", "≈2 means no lag-1 autocorrelation"])
        if n >= 10:
            try:
                adf = adfuller(v, autolag="AIC")
                rows.append(_row("Augmented Dickey-Fuller", adf[0], adf[2], adf[1], alpha, "H0: unit root (non-stationary); small P = stationary"))
            except Exception:  # noqa: BLE001
                pass
            try:
                kp = kpss(v, regression="c", nlags="auto")
                rows.append(_row("KPSS (level)", kp[0], kp[2], kp[1], alpha, "H0: stationary; P is interpolated within 0.01–0.10"))
            except Exception:  # noqa: BLE001
                pass
        r.table(f"{nm} (n = {n}, in table order)", TEST_COLS, rows)
        nl = min(n - 1, max(lag, 10))
        ac = acf(v, nlags=nl, fft=False)
        bound = 1.959964 / math.sqrt(n)
        plots.append({"title": f"Autocorrelation: {nm}", "xTitle": "Lag", "yTitle": "ACF",
                      "traces": [{"type": "bar", "x": list(range(1, nl + 1)), "y": [float(a) for a in ac[1:]], "name": nm}],
                      "hlines": [{"y": bound, "dash": "dot", "label": "95%"}, {"y": -bound, "dash": "dot"}, {"y": 0}]})
    require(r.sections, "No data set had enough values.")
    r.overlay = {"kind": "plot", "plots": plots}
    return r


# ---------------------------------------------------------------- circular statistics
def _a1inv(x):
    """κ such that I1(κ)/I0(κ) = x (maximum-likelihood concentration of a von Mises distribution)."""
    if not 0 < x < 1:
        return 0.0 if x <= 0 else np.inf
    f = lambda k: special.i1e(k) / special.i0e(k) - x  # noqa: E731
    try:
        hi = 1.0
        while f(hi) < 0 and hi < 1e8:
            hi *= 2
        return optimize.brentq(f, 1e-12, hi, xtol=1e-14, rtol=1e-15)
    except ValueError:
        return _a1inv_approx(x)


def _a1inv_approx(x):
    if x < 0.53:
        return 2 * x + x ** 3 + 5 * x ** 5 / 6
    if x < 0.85:
        return -0.4 + 1.39 * x + 0.43 / (1 - x)
    return 1 / (x ** 3 - 4 * x ** 2 + 3 * x)


def circular(table, params):
    names, gs = groups(table, params, 1, 2)
    alpha = _alpha(params)
    unit = params.get("unit", "degrees")
    period = {"degrees": 360.0, "radians": 2 * math.pi, "hours": 24.0}.get(unit) or float(params.get("period", 24) or 24)
    to_rad = 2 * math.pi / period
    mu0 = params.get("expected")
    mu0 = float(mu0) * to_rad if mu0 not in (None, "") else None
    r = Result(f"Circular statistics (period = {fmt(period)} {unit if unit != 'custom' else 'units'})")
    rows = []
    summ = []
    for nm, g in zip(names, gs):
        th = g * to_rad
        n = len(th)
        C, S = np.cos(th).sum(), np.sin(th).sum()
        R = math.hypot(C, S)
        rbar = R / n
        mean = math.atan2(S, C) % (2 * math.pi)
        z = R ** 2 / n
        p = math.exp(math.sqrt(1 + 4 * n + 4 * (n ** 2 - R ** 2)) - (1 + 2 * n))
        p = min(1.0, max(p, 0.0))
        # Zar (2010) eq. 26.24/26.25 confidence interval of the mean direction
        chi = stats.chi2.ppf(1 - alpha, 1)
        ci = "not defined (data too dispersed)"
        if rbar <= 0.9 and rbar > math.sqrt(chi / (2 * n)):
            d = math.acos(math.sqrt(2 * n * (2 * R ** 2 - n * chi) / (4 * n - chi)) / R)
            ci = f"{fmt((mean - d) % (2 * math.pi) / to_rad)} to {fmt((mean + d) % (2 * math.pi) / to_rad)}"
        elif rbar > 0.9:
            d = math.acos(math.sqrt(n ** 2 - (n ** 2 - R ** 2) * math.exp(chi / n)) / R)
            ci = f"{fmt((mean - d) % (2 * math.pi) / to_rad)} to {fmt((mean + d) % (2 * math.pi) / to_rad)}"
        out = [("n", n), ("Mean direction", mean / to_rad), (f"{int((1 - alpha) * 100)}% CI of mean direction", ci),
               ("Mean resultant length R̄ (0 = uniform, 1 = identical)", rbar),
               ("Circular variance (1 − R̄)", 1 - rbar), ("Circular SD", math.sqrt(-2 * math.log(rbar)) / to_rad if rbar > 0 else np.inf),
               ("Angular deviation", math.sqrt(2 * (1 - rbar)) / to_rad), ("Concentration κ (von Mises estimate)", _a1inv(rbar)),
               ("Circular median", _circ_median(th) / to_rad),
               ("Rayleigh test (H0: uniform)", ""), ("Rayleigh Z", z), ("P value", fmt_p(p)), ("Summary", stars(p, alpha))]
        if mu0 is not None:
            V = R * math.cos(mean - mu0)
            u = V * math.sqrt(2 / n)
            pv = float(stats.norm.sf(u))
            out += [(f"V test (H0: uniform; H1: clustered around {fmt(mu0 / to_rad)})", ""), ("V", V), ("u", u), ("P value (one-sided)", fmt_p(pv)), ("Summary", stars(pv, alpha))]
        r.kv(nm, out)
        summ.append((n, R, th))
        rows.append([nm, n, mean / to_rad, rbar, fmt_p(p)])
    if len(gs) >= 2:
        N = sum(s[0] for s in summ)
        Rs = sum(s[1] for s in summ)
        allth = np.concatenate([s[2] for s in summ])
        Rall = math.hypot(np.cos(allth).sum(), np.sin(allth).sum())
        k = len(gs)
        kappa = _a1inv(Rs / N)
        K = 1 + 3 / (8 * kappa) if kappa > 0 else np.nan
        F = K * (N - k) * (Rs - Rall) / ((k - 1) * (N - Rs))
        p = stats.f.sf(F, k - 1, N - k)
        r.kv("Watson-Williams test (H0: equal mean directions; assumes von Mises with equal κ)", [
            ("F", F), ("df", f"{k - 1}, {N - k}"), ("Pooled κ", kappa), ("P value", fmt_p(p)), ("Summary", stars(p, alpha)),
            ("Valid?", "yes" if Rs / N > 0.45 else "questionable: data are dispersed (pooled R̄ < 0.45)")])
    r.table("Summary", ["Data set", "n", "Mean direction", "R̄", "Rayleigh P"], rows)
    return r


def _circ_median(th):
    best, arg = np.inf, 0.0
    for c in th:
        d = np.abs(np.angle(np.exp(1j * (th - c)))).sum()
        if d < best - 1e-12:
            best, arg = d, c
    return arg % (2 * math.pi)


# ---------------------------------------------------------------- reliability & agreement
def icc_table(M, alpha=0.05):
    n, k = M.shape
    grand = M.mean()
    ssr = k * ((M.mean(axis=1) - grand) ** 2).sum()
    ssc = n * ((M.mean(axis=0) - grand) ** 2).sum()
    sst = ((M - grand) ** 2).sum()
    sse = sst - ssr - ssc
    msr, msc = ssr / (n - 1), ssc / (k - 1)
    mse = sse / ((n - 1) * (k - 1))
    msw = (ssc + sse) / (n * (k - 1))
    q = 1 - alpha / 2
    out = []
    # ICC(1,1), ICC(1,k): one-way random
    F1 = msr / msw
    d1, d2 = n - 1, n * (k - 1)
    fl, fu = F1 / stats.f.ppf(q, d1, d2), F1 * stats.f.ppf(q, d2, d1)
    out.append(["ICC(1) single — one-way random, absolute", (msr - msw) / (msr + (k - 1) * msw), F1, d1, d2, stats.f.sf(F1, d1, d2), (fl - 1) / (fl + k - 1), (fu - 1) / (fu + k - 1)])
    # ICC(2,1): two-way random, absolute agreement
    F3 = msr / mse
    e1, e2 = n - 1, (n - 1) * (k - 1)
    icc2 = (msr - mse) / (msr + (k - 1) * mse + k * (msc - mse) / n)
    a = k * icc2 / (n * (1 - icc2))
    b = 1 + k * icc2 * (n - 1) / (n * (1 - icc2))
    v = (a * msc + b * mse) ** 2 / ((a * msc) ** 2 / (k - 1) + (b * mse) ** 2 / ((n - 1) * (k - 1)))
    f2u, f2l = stats.f.ppf(q, n - 1, v), stats.f.ppf(q, v, n - 1)
    l2 = n * (msr - f2u * mse) / (f2u * (k * msc + (k * n - k - n) * mse) + n * msr)
    u2 = n * (f2l * msr - mse) / (k * msc + (k * n - k - n) * mse + n * f2l * msr)
    out.append(["ICC(2,1) single — two-way random, absolute agreement", icc2, F3, e1, e2, stats.f.sf(F3, e1, e2), l2, u2])
    fl3, fu3 = F3 / stats.f.ppf(q, e1, e2), F3 * stats.f.ppf(q, e2, e1)
    out.append(["ICC(3,1) single — two-way mixed, consistency", (msr - mse) / (msr + (k - 1) * mse), F3, e1, e2, stats.f.sf(F3, e1, e2), (fl3 - 1) / (fl3 + k - 1), (fu3 - 1) / (fu3 + k - 1)])
    out.append([f"ICC(1,k) average of {k} — one-way random", (msr - msw) / msr, F1, d1, d2, stats.f.sf(F1, d1, d2), 1 - 1 / fl, 1 - 1 / fu])
    out.append([f"ICC(2,k) average of {k} — two-way random, absolute", (msr - mse) / (msr + (msc - mse) / n), F3, e1, e2, stats.f.sf(F3, e1, e2),
                l2 * k / (1 + l2 * (k - 1)), u2 * k / (1 + u2 * (k - 1))])
    out.append([f"ICC(3,k) average of {k} — two-way mixed, consistency", (msr - mse) / msr, F3, e1, e2, stats.f.sf(F3, e1, e2), 1 - 1 / fl3, 1 - 1 / fu3])
    return out


def lin_ccc(x, y, level=0.95):
    n = len(x)
    mx, my = x.mean(), y.mean()
    sx2, sy2 = x.var(), y.var()
    sxy = ((x - mx) * (y - my)).mean()
    rc = 2 * sxy / (sx2 + sy2 + (mx - my) ** 2)
    rr = sxy / math.sqrt(sx2 * sy2)
    u = (mx - my) / (sx2 * sy2) ** 0.25
    var_z = 1 / (n - 2) * ((1 - rr ** 2) * rc ** 2 / ((1 - rc ** 2) * rr ** 2)
                           + 2 * rc ** 3 * (1 - rc) * u ** 2 / (rr * (1 - rc ** 2) ** 2)
                           - rc ** 4 * u ** 4 / (2 * rr ** 2 * (1 - rc ** 2) ** 2))
    z = math.atanh(rc)
    zc = stats.norm.ppf(0.5 + level / 2)
    se = math.sqrt(var_z)
    return rc, math.tanh(z - zc * se), math.tanh(z + zc * se), rr, (my / mx if mx else np.nan)


def reliability(table, params):
    names, M, dropped = matched(table, params, 2)
    alpha = _alpha(params)
    n, k = M.shape
    pct = f"{int(round((1 - alpha) * 100))}%"
    r = Result("Reliability and agreement")
    if dropped:
        r.warn(f"{dropped} row(s) with missing values were excluded.")
    rows = icc_table(M, alpha)
    r.table(f"Intraclass correlation (rows = {n} subjects, columns = {k} raters or measurements)",
            ["Type (Shrout & Fleiss / McGraw & Wong)", "ICC", "F", "df1", "df2", "P value", f"{pct} CI lower", f"{pct} CI upper"],
            [[t, ic, F, d1, d2, fmt_p(p), lo, hi] for t, ic, F, d1, d2, p, lo, hi in rows])
    tot = M.sum(axis=1)
    if k >= 2:
        alpha_c = k / (k - 1) * (1 - M.var(axis=0, ddof=1).sum() / tot.var(ddof=1))
        df1, df2 = n - 1, (n - 1) * (k - 1)
        lo = 1 - (1 - alpha_c) * stats.f.ppf(1 - alpha / 2, df1, df2)
        hi = 1 - (1 - alpha_c) * stats.f.ppf(alpha / 2, df1, df2)
        Z = (M - M.mean(axis=0)) / M.std(axis=0, ddof=1)
        std_alpha = k / (k - 1) * (1 - k / Z.sum(axis=1).var(ddof=1))
        r.kv("Internal consistency", [("Cronbach's α", alpha_c), (f"{pct} CI (Feldt)", f"{fmt(lo)} to {fmt(hi)}"),
                                      ("Standardized α (from correlations)", std_alpha),
                                      ("Interpretation (rule of thumb)", "≥0.9 excellent, ≥0.8 good, ≥0.7 acceptable, <0.6 poor")])
        if k >= 3:
            item_rows = []
            for j in range(k):
                rest = np.delete(M, j, axis=1)
                kk = k - 1
                a_del = kk / (kk - 1) * (1 - rest.var(axis=0, ddof=1).sum() / rest.sum(axis=1).var(ddof=1)) if kk > 1 else np.nan
                item_rows.append([names[j], M[:, j].mean(), M[:, j].std(ddof=1), np.corrcoef(M[:, j], rest.sum(axis=1))[0, 1], a_del])
            r.table("Item statistics", ["Item / rater", "Mean", "SD", "Corrected item-total r", "α if deleted"], item_rows)
    if k == 2:
        rc, lo, hi, rr, _ = lin_ccc(M[:, 0], M[:, 1], 1 - alpha)
        r.kv("Lin's concordance correlation (agreement on the identity line)", [
            ("CCC ρc", rc), (f"{pct} CI (Fisher z)", f"{fmt(lo)} to {fmt(hi)}"), ("Pearson r (precision)", rr), ("Bias correction factor Cb (accuracy)", rc / rr if rr else np.nan)])
    R = np.apply_along_axis(stats.rankdata, 0, M)
    Rs = R.sum(axis=1)
    S = ((Rs - Rs.mean()) ** 2).sum()
    T = 0.0
    for j in range(k):
        _, t = np.unique(M[:, j], return_counts=True)
        T += (t ** 3 - t).sum()
    W = 12 * S / (k ** 2 * (n ** 3 - n) - k * T)
    chi = k * (n - 1) * W
    r.kv("Kendall's coefficient of concordance (rank agreement among raters)", [("W", W), ("Chi-square", chi), ("df", n - 1), ("P value", fmt_p(stats.chi2.sf(chi, n - 1)))])
    if np.all(M == np.round(M)) and len(np.unique(M)) <= 20:
        from statsmodels.stats.inter_rater import aggregate_raters, fleiss_kappa
        tab, cats = aggregate_raters(M.astype(int))
        r.kv("Fleiss' kappa (ratings treated as categories)", [("κ", fleiss_kappa(tab, method="fleiss")), ("Categories", ", ".join(str(int(c)) for c in cats)),
                                                               ("Interpretation (Landis & Koch)", "<0 poor, 0–0.2 slight, 0.21–0.4 fair, 0.41–0.6 moderate, 0.61–0.8 substantial, >0.8 almost perfect")])
    return r


# ---------------------------------------------------------------- P-value adjustment
def storey_q(p, lam=0.5):
    p = np.asarray(p, float)
    m = len(p)
    pi0 = min(1.0, (p > lam).sum() / ((1 - lam) * m)) if m else 1.0
    order = np.argsort(p)
    q = np.empty(m)
    prev = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        prev = min(prev, pi0 * m * p[i] / rank)
        q[i] = prev
    return q, pi0


def p_adjust(table, params):
    idx = selected(table, params)
    require(idx, "No data.")
    alpha = _alpha(params)
    labels, ps = [], []
    for i in idx:
        v = table.Y[i][:, 0]
        for rl, x in zip(table.row_labels, v):
            if np.isfinite(x):
                labels.append(f"{table.names[i]}: {rl}" if len(idx) > 1 else rl)
                ps.append(float(x))
    p = np.array(ps)
    require(len(p) >= 1, "Enter P values (one per row).")
    require(np.all((p >= 0) & (p <= 1)), "All values must be P values between 0 and 1.")
    methods = [("bonferroni", "Bonferroni"), ("sidak", "Šídák"), ("holm", "Holm"), ("holm-sidak", "Holm-Šídák"),
               ("hochberg", "Hochberg"), ("hommel", "Hommel"), ("bh", "Benjamini-Hochberg (FDR)"), ("by", "Benjamini-Yekutieli (FDR, any dependence)"),
               ("bky", "Two-stage BKY (FDR)")]
    adj = {k: adjust_p(p, k) for k, _ in methods}
    q, pi0 = storey_q(p, float(params.get("lambda", 0.5)))
    r = Result("Adjusted P values")
    r.table(f"{len(p)} P values", ["Row", "P"] + [lab for _, lab in methods] + [f"Storey q (π0 = {fmt(pi0)})"],
            [[labels[i], fmt_p(p[i]) if p[i] >= 0.0001 else fmt(p[i])] + [fmt(adj[k][i]) for k, _ in methods] + [fmt(q[i])] for i in range(len(p))])
    r.table(f"Number of discoveries at {alpha}", ["Method", "Controls", "Significant"],
            [[lab, "FDR" if k in ("bh", "by", "bky") else "family-wise error", int((adj[k] < alpha).sum())] for k, lab in methods]
            + [["Unadjusted", "nothing", int((p < alpha).sum())], ["Storey q", "positive FDR", int((q < alpha).sum())]])
    return r
