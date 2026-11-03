"""Advanced analyses: mixed-effects models (repeated measures with missing values,
two-way repeated measures, nested designs), n-way ANOVA / ANCOVA, Games-Howell,
Deming and Passing-Bablok regression, Poisson regression, and methods that go
beyond the usual commercial packages: equivalence (TOST), Bayes-factor t tests,
bootstrap confidence intervals and permutation tests.
"""
from __future__ import annotations

import itertools
import math

import numpy as np
from scipy import integrate, stats

from .common import (COMPARISON_COLUMNS, MC_METHODS, AnalysisError, Result, bh_fdr, fmt, fmt_p, holm, holm_sidak,
                     quiet, require, sig, stars, t_ci)
from .descriptive import selected


def _clean(a):
    return [float(v) if v is not None and np.isfinite(v) else None for v in np.asarray(a, float)]


# ---------------------------------------------------------------- shared helpers
def adjust(pvals, method, m=None):
    """Adjust raw P values for multiple comparisons."""
    p = np.asarray(pvals, float)
    m = m or len(p)
    if method == "bonferroni":
        return np.minimum(1, p * m)
    if method == "sidak":
        return 1 - (1 - p) ** m
    if method == "holm-sidak":
        return holm_sidak(p)
    if method == "holm":
        return holm(p)
    if method == "bh":
        return bh_fdr(p)
    if method == "bky":
        return bky_fdr(p)
    return p


def bky_fdr(p, q=0.05):
    """Two-stage step-up method of Benjamini, Krieger & Yekutieli (adaptive FDR); returns q-values
    (approximate: BH q-values scaled by the estimated proportion of true nulls)."""
    p = np.asarray(p, float)
    m = len(p)
    q1 = q / (1 + q)
    bh = bh_fdr(p)
    r = int((bh <= q1).sum())
    if r == 0 or r == m:
        return bh
    m0 = m - r
    return np.minimum(1, bh * m0 / m * (1 + q))


def contrast_table(labels_pairs, est, se, df, method, alpha, k_groups):
    """Pairwise comparisons from model-based estimates (mixed models, GLMs)."""
    est, se = np.asarray(est, float), np.asarray(se, float)
    t = est / se
    if method == "tukey":
        q = np.abs(t) * math.sqrt(2)
        p = stats.studentized_range.sf(q, k_groups, df)
        crit = stats.studentized_range.ppf(1 - alpha, k_groups, df) / math.sqrt(2)
    else:
        raw = 2 * stats.t.sf(np.abs(t), df)
        p = adjust(raw, method)
        m = len(raw)
        a_ind = {"bonferroni": alpha / m, "sidak": 1 - (1 - alpha) ** (1 / m), "holm-sidak": 1 - (1 - alpha) ** (1 / m)}.get(method, alpha)
        crit = stats.t.ppf(1 - a_ind / 2, df)
    rows, pairs = [], []
    for (lab, a, b), e, s, pv in zip(labels_pairs, est, se, p):
        rows.append([lab, e, f"{fmt(e - crit * s)} to {fmt(e + crit * s)}", sig(pv, alpha), stars(pv, alpha), fmt_p(pv)])
        pairs.append({"a": a, "b": b, "p": float(pv), "stars": stars(pv, alpha)})
    return rows, pairs


def _mixedlm(df, formula, group_col):
    import statsmodels.formula.api as smf
    with quiet():
        model = smf.mixedlm(formula, df, groups=df[group_col])
        try:
            res = model.fit(reml=True, method=["lbfgs", "powell", "nm"])
        except Exception as e:  # noqa: BLE001
            if "singular" in str(e).lower():
                raise AnalysisError("The mixed-effects model cannot be estimated: the variation between subjects is zero, so the rows do not "
                                    "behave like matched subjects (e.g. independent groups were entered). For independent groups use "
                                    "ordinary one-way ANOVA; for repeated measures check that each row holds one subject.") from None
            raise AnalysisError(f"The mixed-effects model did not converge ({e}).") from None
    return res


def _wald_terms(res, names_map):
    rows = []
    with quiet():
        wt = res.wald_test_terms(scalar=True)
    tab = wt.table if hasattr(wt, "table") else wt.summary_frame()
    for term, row in tab.iterrows():
        if term == "Intercept" or term not in names_map:
            continue
        chi2 = float(row["statistic"])
        dfn = int(row["df_constraint"]) if "df_constraint" in row else int(row.get("df", 1))
        p = float(row["pvalue"])
        rows.append([names_map[term], chi2, dfn, chi2 / max(dfn, 1), fmt_p(p), stars(p, 0.05)])
    return rows


def _cell_contrasts(res, df_long, design_cols, cells, pairs, rhs):
    """Estimate differences between design cells from the fixed effects."""
    import pandas as pd
    from patsy import dmatrix
    frame = pd.DataFrame(cells, columns=design_cols)
    for c in design_cols:
        frame[c] = pd.Categorical(frame[c], categories=df_long[c].cat.categories)
    X = dmatrix(rhs, frame, return_type="dataframe")
    X = X.reindex(columns=res.fe_params.index, fill_value=0.0).values
    fe = res.fe_params.values
    cov = res.cov_params().loc[res.fe_params.index, res.fe_params.index].values
    est, se = [], []
    for a, b in pairs:
        c = X[a] - X[b]
        est.append(float(c @ fe))
        se.append(float(math.sqrt(max(c @ cov @ c, 1e-300))))
    return est, se


def _var_components(res):
    v_subj = float(res.cov_re.iloc[0, 0]) if res.cov_re.size else 0.0
    v_res = float(res.scale)
    icc = v_subj / (v_subj + v_res) if v_subj + v_res > 0 else np.nan
    return v_subj, v_res, icc


# ---------------------------------------------------------------- mixed one-way RM
def mixed_one_way(table, params):
    """Repeated measures one-way analysis by a mixed-effects model (rows = subjects).
    Unlike RM ANOVA, subjects with missing values are kept."""
    import pandas as pd
    idx = selected(table, params)
    require(len(idx) >= 2, "Need at least two data sets.")
    alpha = float(params.get("alpha", 0.05))
    method = params.get("comparison", "tukey")
    names = [table.names[i] for i in idx]
    recs = []
    for j, i in enumerate(idx):
        col = table.Y[i][:, 0] if table.Y[i].shape[1] == 1 else np.nanmean(table.Y[i], axis=1)
        for r, v in enumerate(col):
            if np.isfinite(v):
                recs.append({"y": v, "treat": f"t{j}", "subject": f"s{r}"})
    df = pd.DataFrame(recs)
    require(df["subject"].nunique() >= 3, "Need at least three subjects (rows).")
    df["treat"] = pd.Categorical(df["treat"], categories=[f"t{j}" for j in range(len(idx))])
    res = _mixedlm(df, "y ~ C(treat)", "subject")
    n_obs, n_subj = len(df), df["subject"].nunique()
    v_subj, v_res, icc = _var_components(res)
    r = Result("Mixed-effects model (repeated measures, one factor)")
    terms = _wald_terms(res, {"C(treat)": "Treatment"})
    r.table("Fixed effects (Wald test)", ["Source", "Chi-square", "DF", "F (= χ²/DF)", "P value", "Summary"], terms)
    r.kv("Random effects", [("Subjects (rows)", n_subj), ("Observations", n_obs),
                            ("Missing values (kept in model)", int(n_subj * len(idx) - n_obs)),
                            ("SD of subjects (random intercept)", math.sqrt(max(v_subj, 0))), ("SD of residual", math.sqrt(v_res)),
                            ("Intraclass correlation", icc), ("Log likelihood (REML)", res.llf)])
    cells = [[f"t{j}"] for j in range(len(idx))]
    pairs = list(itertools.combinations(range(len(idx)), 2))
    est, se = _cell_contrasts(res, df, ["treat"], cells, pairs, "C(treat)")
    dfd = max(1, n_obs - n_subj - len(idx) + 1)
    if method not in ("none", ""):
        rows, ov = contrast_table([(f"{names[a]} vs. {names[b]}", idx[a], idx[b]) for a, b in pairs], est, se, dfd,
                                  method if method != "dunnett" else "holm-sidak", alpha, len(idx))
        r.table(f"{MC_METHODS.get(method, method)} multiple comparisons (model-based)", COMPARISON_COLUMNS, rows)
        r.overlay = {"kind": "pairs", "pairs": ov}
    r.warn("Fixed effects are tested with Wald chi-square tests; comparisons use model-based standard errors with "
           "residual degrees of freedom (approximate).")
    return r


# ---------------------------------------------------------------- two-way RM (mixed)
def two_way_rm(table, params):
    """Two-way ANOVA with repeated measures fitted as a mixed-effects model.
    rm = 'rows'  : each subcolumn is one subject measured at every row (repeated across rows)
    rm = 'cols'  : replicate k of each row is the same subject in every data set (repeated across columns)
    rm = 'both'  : subcolumn k is the same subject everywhere."""
    import pandas as pd
    idx = selected(table, params)
    rm = params.get("rm", "rows")
    alpha = float(params.get("alpha", 0.05))
    method = params.get("comparison", "sidak")
    recs = []
    for ci in idx:
        for ri in range(table.nrows):
            for k, v in enumerate(table.Y[ci][ri]):
                if not np.isfinite(v):
                    continue
                subj = {"rows": f"c{ci}k{k}", "cols": f"r{ri}k{k}", "both": f"k{k}"}[rm]
                recs.append({"y": v, "row": f"r{ri}", "col": f"c{ci}", "subject": subj})
    df = pd.DataFrame(recs)
    require(len(df) > 0 and df["subject"].nunique() >= 3, "Need at least three subjects (replicate subcolumns).")
    df["row"] = pd.Categorical(df["row"], categories=sorted(df["row"].unique(), key=lambda s: int(s[1:])))
    df["col"] = pd.Categorical(df["col"], categories=sorted(df["col"].unique(), key=lambda s: int(s[1:])))
    res = _mixedlm(df, "y ~ C(row, Sum) * C(col, Sum)", "subject")
    v_subj, v_res, icc = _var_components(res)
    r = Result("Two-way repeated measures (mixed-effects model)")
    terms = _wald_terms(res, {"C(row, Sum)": "Row factor", "C(col, Sum)": "Column factor",
                              "C(row, Sum):C(col, Sum)": "Interaction"})
    r.table("Fixed effects (Wald test)", ["Source", "Chi-square", "DF", "F (= χ²/DF)", "P value", "Summary"], terms)
    r.kv("Random effects", [("Repeated measures", {"rows": "across rows (subcolumns are subjects)", "cols": "across data sets", "both": "across rows and data sets"}[rm]),
                            ("Subjects", df["subject"].nunique()), ("Observations", len(df)),
                            ("SD of subjects", math.sqrt(max(v_subj, 0))), ("SD of residual", math.sqrt(v_res)),
                            ("Intraclass correlation", icc)])
    if method not in ("none", ""):
        rows_all, ov = [], []
        dfd = max(1, len(df) - df["subject"].nunique() - df["row"].nunique() * df["col"].nunique() + 1)
        labs, cells, pairs = [], [], []
        for rlev in df["row"].cat.categories:
            cols = [c for c in df["col"].cat.categories if ((df["row"] == rlev) & (df["col"] == c)).any()]
            for a, b in itertools.combinations(cols, 2):
                ia = len(cells); cells.append([rlev, a])
                ib = len(cells); cells.append([rlev, b])
                pairs.append((ia, ib))
                labs.append((f"{table.row_labels[int(rlev[1:])]}: {table.names[int(a[1:])]} vs. {table.names[int(b[1:])]}",
                             int(rlev[1:]), int(a[1:]), int(b[1:])))
        if pairs:
            est, se = _cell_contrasts(res, df, ["row", "col"], cells, pairs, "C(row, Sum) * C(col, Sum)")
            rows_all, ovp = contrast_table([(l[0], l[2], l[3]) for l in labs], est, se, dfd,
                                           method if method != "tukey" else "sidak", alpha, 2)
            ov = [{**o, "row": l[1]} for o, l in zip(ovp, labs)]
            r.table(f"{MC_METHODS.get(method, method)} multiple comparisons within rows", COMPARISON_COLUMNS, rows_all)
            r.overlay = {"kind": "grouped-pairs", "pairs": ov}
    return r


# ---------------------------------------------------------------- nested
def nested(table, params):
    """Nested t test / nested one-way ANOVA. Data sets = groups, subcolumns = subjects
    (e.g. animals) within a group, rows = replicate measurements of each subject."""
    import pandas as pd
    idx = selected(table, params)
    require(len(idx) >= 2, "Need at least two groups (data sets).")
    alpha = float(params.get("alpha", 0.05))
    method = params.get("comparison", "tukey")
    names = [table.names[i] for i in idx]
    recs = []
    for j, i in enumerate(idx):
        for k in range(table.Y[i].shape[1]):
            for v in table.Y[i][:, k]:
                if np.isfinite(v):
                    recs.append({"y": v, "group": f"g{j}", "subject": f"g{j}s{k}"})
    df = pd.DataFrame(recs)
    require(df["subject"].nunique() >= len(idx) + 1, "Each group needs subjects (subcolumns) with values.")
    df["group"] = pd.Categorical(df["group"], categories=[f"g{j}" for j in range(len(idx))])
    res = _mixedlm(df, "y ~ C(group)", "subject")
    v_subj, v_res, icc = _var_components(res)
    n_subj = df["subject"].nunique()
    dfd = max(1, n_subj - len(idx))  # the experimental unit is the subject
    title = "Nested t test" if len(idx) == 2 else "Nested one-way ANOVA"
    r = Result(f"{title} (mixed-effects model)")
    cells = [[f"g{j}"] for j in range(len(idx))]
    if len(idx) == 2:
        est, se = _cell_contrasts(res, df, ["group"], cells, [(1, 0)], "C(group)")
        t = est[0] / se[0]
        p = float(2 * stats.t.sf(abs(t), dfd))
        lo, hi = t_ci(est[0], se[0], dfd, 1 - alpha)
        r.kv("Nested t test", [("P value", fmt_p(p)), ("P value summary", stars(p, alpha)),
                               (f"Significantly different (P < {alpha})?", sig(p, alpha)), ("t, df", f"t={abs(t):.4f}, df={dfd}"),
                               (f"Difference ({names[1]} - {names[0]})", est[0]), (f"{int((1 - alpha) * 100)}% CI", f"{fmt(lo)} to {fmt(hi)}")])
        r.overlay = {"kind": "pairs", "pairs": [{"a": idx[0], "b": idx[1], "p": p, "stars": stars(p, alpha)}]}
    else:
        terms = _wald_terms(res, {"C(group)": "Between groups"})
        r.table("Between groups (Wald test)", ["Source", "Chi-square", "DF", "F (= χ²/DF)", "P value", "Summary"], terms)
        pairs = list(itertools.combinations(range(len(idx)), 2))
        est, se = _cell_contrasts(res, df, ["group"], cells, pairs, "C(group)")
        if method not in ("none", ""):
            rows, ov = contrast_table([(f"{names[a]} vs. {names[b]}", idx[a], idx[b]) for a, b in pairs], est, se, dfd,
                                      method if method != "dunnett" else "holm-sidak", alpha, len(idx))
            r.table(f"{MC_METHODS.get(method, method)} multiple comparisons", COMPARISON_COLUMNS, rows)
            r.overlay = {"kind": "pairs", "pairs": ov}
    r.kv("Variance components", [("Subjects (experimental units)", n_subj), ("Measurements", len(df)),
                                 ("SD between subjects", math.sqrt(max(v_subj, 0))), ("SD within subjects (replicates)", math.sqrt(v_res)),
                                 ("Intraclass correlation", icc),
                                 ("Interpretation", "Replicates are strongly clustered by subject — analyzing them as independent would inflate significance."
                                  if icc > 0.1 else "Little clustering by subject.")])
    subj_means = df.groupby(["group", "subject"], observed=True)["y"].mean().reset_index()
    r.table("Subject means", ["Group", "Subject", "Mean"],
            [[names[int(g[1:])], s.split("s")[-1], m] for g, s, m in subj_means.itertuples(index=False)])
    return r


# ---------------------------------------------------------------- n-way ANOVA / ANCOVA
def factorial(table, params):
    """General linear model: n-way ANOVA (categorical factors, e.g. three-way ANOVA)
    with optional continuous covariates (ANCOVA). Multiple-variables table."""
    import pandas as pd
    import statsmodels.formula.api as smf
    from statsmodels.stats.anova import anova_lm

    dep = int(params.get("dependent", 0))
    factors = [int(f) for f in (params.get("factors") or []) if int(f) != dep]
    covs = [int(c) for c in (params.get("covariates") or []) if int(c) != dep and int(c) not in factors]
    require(factors, "Choose at least one categorical factor.")
    require(len(factors) <= 4, "At most four factors.")
    interactions = params.get("interactions", "all")
    alpha = float(params.get("alpha", 0.05))
    cols = {"y": table.Y[dep][:, 0]}
    fnames, cnames = [], []
    for j, f in enumerate(factors):
        cols[f"F{j}"] = table.Y[f][:, 0]
        fnames.append(table.names[f])
    for j, cidx in enumerate(covs):
        cols[f"X{j}"] = table.Y[cidx][:, 0]
        cnames.append(table.names[cidx])
    df = pd.DataFrame(cols).dropna()
    require(len(df) > len(factors) + len(covs) + 2, "Not enough complete rows.")
    for j in range(len(factors)):
        df[f"F{j}"] = df[f"F{j}"].map(lambda v: fmt(v)).astype("category")
        require(df[f"F{j}"].nunique() >= 2, f"Factor '{fnames[j]}' needs at least two levels.")
    fterms = [f"C(F{j}, Sum)" for j in range(len(factors))]
    rhs = " * ".join(fterms) if interactions == "all" else " + ".join(fterms)
    if covs:
        rhs += " + " + " + ".join(f"X{j}" for j in range(len(covs)))
    with quiet():
        model = smf.ols(f"y ~ {rhs}", data=df).fit()
        tab = anova_lm(model, typ=3)
    label = {f"C(F{j}, Sum)": fnames[j] for j in range(len(factors))}
    label.update({f"X{j}": f"{cnames[j]} (covariate)" for j in range(len(covs))})

    def pretty(term):
        return " × ".join(label.get(p, p) for p in term.split(":"))
    rows = []
    ss_tot = sum(tab.loc[k, "sum_sq"] for k in tab.index if k != "Intercept")
    for k in tab.index:
        if k == "Intercept":
            continue
        rr = tab.loc[k]
        if k == "Residual":
            rows.append(["Residual", rr["sum_sq"], int(rr["df"]), rr["sum_sq"] / rr["df"], "", "", "", ""])
        else:
            pe = rr["sum_sq"] / (rr["sum_sq"] + tab.loc["Residual", "sum_sq"])
            rows.append([pretty(k), rr["sum_sq"], int(rr["df"]), rr["sum_sq"] / rr["df"],
                         f"F ({int(rr['df'])}, {int(tab.loc['Residual', 'df'])}) = {fmt(rr['F'])}", fmt_p(rr["PR(>F)"]),
                         stars(rr["PR(>F)"], alpha), pe])
    nf = len(factors)
    r = Result(f"{'Three' if nf == 3 else 'Four' if nf == 4 else 'Two' if nf == 2 else 'One'}-way ANOVA"
               + (" with covariates (ANCOVA)" if covs else "") + f": {table.names[dep]}")
    r.table("ANOVA table (Type III)", ["Source", "SS", "DF", "MS", "F (DFn, DFd)", "P value", "Summary", "Partial η²"], rows)
    r.kv("Model", [("R squared", model.rsquared), ("Adjusted R squared", model.rsquared_adj),
                   ("Observations", int(model.nobs)), ("Residual SD", math.sqrt(model.mse_resid)),
                   ("% of total variation explained", (1 - tab.loc['Residual', 'sum_sq'] / ss_tot) * 100 if ss_tot else np.nan)])
    if covs:
        r.table("Covariate slopes", ["Covariate", "Slope", "Std. error", "P value"],
                [[cnames[j], model.params[f"X{j}"], model.bse[f"X{j}"], fmt_p(model.pvalues[f"X{j}"])] for j in range(len(covs))])
    # cell means
    g = df.groupby([f"F{j}" for j in range(nf)], observed=True)["y"].agg(["count", "mean", "std"]).reset_index()
    r.table("Cell means", fnames + ["N", "Mean", "SD"], g.values.tolist())
    return r


# ---------------------------------------------------------------- Games-Howell & Brown-Forsythe
def games_howell(groups, names, alpha, idx):
    k = len(groups)
    rows, ov = [], []
    for a, b in itertools.combinations(range(k), 2):
        ga, gb = groups[a], groups[b]
        na, nb = len(ga), len(gb)
        va, vb = ga.var(ddof=1) / na, gb.var(ddof=1) / nb
        se = math.sqrt(va + vb)
        dfw = (va + vb) ** 2 / (va ** 2 / (na - 1) + vb ** 2 / (nb - 1))
        diff = ga.mean() - gb.mean()
        q = abs(diff) / se * math.sqrt(2)
        p = float(stats.studentized_range.sf(q, k, dfw))
        crit = stats.studentized_range.ppf(1 - alpha, k, dfw) / math.sqrt(2)
        rows.append([f"{names[a]} vs. {names[b]}", diff, f"{fmt(diff - crit * se)} to {fmt(diff + crit * se)}",
                     sig(p, alpha), stars(p, alpha), fmt_p(p)])
        ov.append({"a": idx[a], "b": idx[b], "p": p, "stars": stars(p, alpha)})
    return rows, ov


def _psmm(c, m, df):
    """CDF of the studentized maximum modulus |T|max of m comparisons with df degrees of freedom."""
    if not np.isfinite(df) or df > 1e4:
        return (2 * stats.norm.cdf(c) - 1) ** m
    def integrand(s_):
        return (2 * stats.norm.cdf(c * s_) - 1) ** m * stats.chi.pdf(s_ * math.sqrt(df), df) * math.sqrt(df)
    val, _ = integrate.quad(integrand, 0, np.inf, limit=200)
    return min(1.0, max(0.0, val))


def unequal_var_posthoc(groups, names, alpha, idx, method):
    """Tamhane T2 (Welch t + Šídák) or Dunnett T3 (Welch t + studentized maximum modulus)."""
    k = len(groups)
    pairs = list(itertools.combinations(range(k), 2))
    m = len(pairs)
    rows, ov = [], []
    for a, b in pairs:
        ga, gb = groups[a], groups[b]
        va, vb = ga.var(ddof=1) / len(ga), gb.var(ddof=1) / len(gb)
        se = math.sqrt(va + vb)
        dfw = (va + vb) ** 2 / (va ** 2 / (len(ga) - 1) + vb ** 2 / (len(gb) - 1))
        diff = ga.mean() - gb.mean()
        t = abs(diff) / se
        if method == "t3":
            p = 1 - _psmm(t, m, dfw)
            lo_c, hi_c = 0.0, 50.0
            for _ in range(60):
                mid = (lo_c + hi_c) / 2
                if _psmm(mid, m, dfw) < 1 - alpha:
                    lo_c = mid
                else:
                    hi_c = mid
            crit = hi_c
        else:
            p = 1 - (1 - 2 * stats.t.sf(t, dfw)) ** m
            crit = stats.t.ppf(1 - (1 - (1 - alpha) ** (1 / m)) / 2, dfw)
        p = float(min(1.0, max(0.0, p)))
        rows.append([f"{names[a]} vs. {names[b]}", diff, f"{fmt(diff - crit * se)} to {fmt(diff + crit * se)}",
                     sig(p, alpha), stars(p, alpha), fmt_p(p)])
        ov.append({"a": idx[a], "b": idx[b], "p": p, "stars": stars(p, alpha)})
    return rows, ov


def brown_forsythe_anova(groups):
    n = np.array([len(g) for g in groups], float)
    m = np.array([g.mean() for g in groups])
    v = np.array([g.var(ddof=1) for g in groups])
    N = n.sum()
    grand = (n * m).sum() / N
    denom = ((1 - n / N) * v).sum()
    F = (n * (m - grand) ** 2).sum() / denom
    c = (1 - n / N) * v / denom
    df2 = 1 / (c ** 2 / (n - 1)).sum()
    return F, len(groups) - 1, df2, float(stats.f.sf(F, len(groups) - 1, df2))


# ---------------------------------------------------------------- method comparison regression
def deming(table, params):
    require(table.type == "xy", "Deming regression requires an XY table (X = method 1, Y = method 2).")
    idx = selected(table, params)
    ratio = float(params.get("ratio", 1) or 1)   # SD(Y error) / SD(X error)
    lam = ratio ** 2
    r = Result("Deming regression (errors in X and Y)")
    rows, curves = [], []
    for i in idx:
        x, y = table.xy_points(i, use_means=True)
        n = len(x)
        if n < 3:
            continue

        def fit(x, y):
            mx, my = x.mean(), y.mean()
            sxx, syy, sxy = ((x - mx) ** 2).sum(), ((y - my) ** 2).sum(), ((x - mx) * (y - my)).sum()
            b = (syy - lam * sxx + math.sqrt((syy - lam * sxx) ** 2 + 4 * lam * sxy ** 2)) / (2 * sxy)
            return b, my - b * mx
        b, a = fit(x, y)
        jk = np.array([fit(np.delete(x, j), np.delete(y, j)) for j in range(n)])  # jackknife SE
        se_b = math.sqrt((n - 1) / n * ((jk[:, 0] - jk[:, 0].mean()) ** 2).sum())
        se_a = math.sqrt((n - 1) / n * ((jk[:, 1] - jk[:, 1].mean()) ** 2).sum())
        t = stats.t.ppf(0.975, n - 2)
        rows.append([table.names[i], b, f"{fmt(b - t * se_b)} to {fmt(b + t * se_b)}", a, f"{fmt(a - t * se_a)} to {fmt(a + t * se_a)}",
                     "Yes" if (b - t * se_b) <= 1 <= (b + t * se_b) else "No", "Yes" if (a - t * se_a) <= 0 <= (a + t * se_a) else "No", n])
        xs = np.linspace(x.min(), x.max(), 50)
        curves.append({"dataset": i, "x": _clean(xs), "y": _clean(a + b * xs), "lo": None, "hi": None,
                       "label": f"Y = {fmt(b)}X {'+' if a >= 0 else '-'} {fmt(abs(a))} (Deming)"})
    require(rows, "Need at least three points.")
    r.table("Best-fit values (jackknife CIs)", ["Data set", "Slope", "95% CI slope", "Intercept", "95% CI intercept",
                                                "CI of slope includes 1?", "CI of intercept includes 0?", "N"], rows)
    r.kv("Assumption", [("SD of Y error / SD of X error", ratio)])
    r.overlay = {"kind": "curves", "curves": curves, "showBand": False}
    return r


def passing_bablok(table, params):
    """Nonparametric method-comparison regression (Passing & Bablok 1983)."""
    require(table.type == "xy", "Passing-Bablok regression requires an XY table (X = method 1, Y = method 2).")
    idx = selected(table, params)
    r = Result("Passing-Bablok regression")
    rows, curves = [], []
    for i in idx:
        x, y = table.xy_points(i, use_means=True)
        n = len(x)
        if n < 3:
            continue
        ii, jj = np.triu_indices(n, 1)
        dx, dy = x[jj] - x[ii], y[jj] - y[ii]
        ok = ~((dx == 0) & (dy == 0))
        with np.errstate(divide="ignore", invalid="ignore"):
            s = np.where(dx[ok] != 0, dy[ok] / dx[ok], np.sign(dy[ok]) * np.inf)
        s = s[s != -1]
        s.sort()
        N = len(s)
        K = int((s < -1).sum())  # offset so the estimator is not biased by negative slopes
        require(N > 0, "All points are identical.")
        if N % 2:
            b = float(s[(N + 1) // 2 + K - 1])
        else:
            b = float((s[N // 2 + K - 1] + s[N // 2 + K]) / 2)
        a = float(np.median(y - b * x))
        C = 1.959964 * math.sqrt(n * (n - 1) * (2 * n + 5) / 18)
        M1 = int(round((N - C) / 2))
        M2 = N - M1 + 1
        blo = float(s[max(0, M1 + K - 1)]) if N else np.nan
        bhi = float(s[min(N - 1, M2 + K - 1)]) if N else np.nan
        alo, ahi = float(np.median(y - bhi * x)), float(np.median(y - blo * x))
        rows.append([table.names[i], b, f"{fmt(blo)} to {fmt(bhi)}", a, f"{fmt(alo)} to {fmt(ahi)}",
                     "Yes" if blo <= 1 <= bhi else "No", "Yes" if alo <= 0 <= ahi else "No", n])
        xs = np.linspace(x.min(), x.max(), 50)
        curves.append({"dataset": i, "x": _clean(xs), "y": _clean(a + b * xs), "lo": None, "hi": None,
                       "label": f"Y = {fmt(b)}X {'+' if a >= 0 else '-'} {fmt(abs(a))} (Passing-Bablok)"})
    require(rows, "Need at least three points.")
    r.table("Best-fit values", ["Data set", "Slope", "95% CI slope", "Intercept", "95% CI intercept",
                                "Slope CI includes 1?", "Intercept CI includes 0?", "N"], rows)
    r.warn("If the slope CI includes 1 and the intercept CI includes 0, the two methods agree within the precision of the data.")
    r.overlay = {"kind": "curves", "curves": curves, "showBand": False}
    return r


# ---------------------------------------------------------------- Poisson regression
def poisson(table, params):
    import statsmodels.api as sm
    dep = int(params.get("dependent", 0))
    preds = [int(p) for p in (params.get("predictors") or []) if int(p) != dep] or [i for i in range(len(table.Y)) if i != dep]
    offset_idx = params.get("offset")
    cols = [table.Y[dep][:, 0]] + [table.Y[j][:, 0] for j in preds]
    if offset_idx not in (None, "", -1, "-1"):
        cols.append(table.Y[int(offset_idx)][:, 0])
    M = np.column_stack(cols)
    M = M[np.all(np.isfinite(M), axis=1)]
    y, X = M[:, 0], M[:, 1:1 + len(preds)]
    require(np.all(y >= 0) and np.allclose(y, np.round(y)), "The dependent variable must contain counts (0, 1, 2, …).")
    off = np.log(M[:, -1]) if offset_idx not in (None, "", -1, "-1") else None
    with quiet():
        res = sm.GLM(y, sm.add_constant(X, has_constant="add"), family=sm.families.Poisson(), offset=off).fit()
    ci = np.asarray(res.conf_int())
    names = ["Intercept"] + [table.names[j] for j in preds]
    r = Result(f"Poisson regression: {table.names[dep]}")
    r.table("Parameter estimates", ["Variable", "β", "Std. error", "Rate ratio", "95% CI of rate ratio", "P value", "Summary"],
            [[nm, b, se, math.exp(b), f"{fmt(math.exp(c[0]))} to {fmt(math.exp(c[1]))}", fmt_p(p), stars(p, 0.05)]
             for nm, b, se, c, p in zip(names, res.params, res.bse, ci, res.pvalues)])
    disp = res.pearson_chi2 / res.df_resid if res.df_resid > 0 else np.nan
    r.kv("Goodness of fit", [("Observations", int(res.nobs)), ("Deviance", res.deviance), ("Pearson χ² / df (dispersion)", disp),
                             ("Log likelihood", res.llf), ("AIC", res.aic)])
    if np.isfinite(disp) and disp > 1.5:
        r.warn("The data are over-dispersed (dispersion > 1.5): standard errors are too small; interpret P values with care.")
    return r


# ---------------------------------------------------------------- beyond the usual: equivalence, Bayes, bootstrap, permutation
def equivalence(table, params):
    """Two one-sided tests (TOST): is the difference between two groups within ±margin?"""
    idx = selected(table, params)
    require(len(idx) >= 2, "Choose two data sets.")
    a, b = table.column_values(idx[0]), table.column_values(idx[1])
    require(len(a) >= 2 and len(b) >= 2, "Each group needs at least two values.")
    lo_m = float(params.get("lower", -abs(float(params.get("margin", 1) or 1))))
    hi_m = float(params.get("upper", abs(float(params.get("margin", 1) or 1))))
    require(lo_m < hi_m, "The lower margin must be below the upper margin.")
    alpha = float(params.get("alpha", 0.05))
    na, nb = len(a), len(b)
    va, vb = a.var(ddof=1), b.var(ddof=1)
    se = math.sqrt(va / na + vb / nb)
    dfw = (va / na + vb / nb) ** 2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
    d = b.mean() - a.mean()
    p1 = float(stats.t.sf((d - lo_m) / se, dfw))
    p2 = float(stats.t.cdf((d - hi_m) / se, dfw))
    p = max(p1, p2)
    lo, hi = t_ci(d, se, dfw, 1 - 2 * alpha)
    r = Result("Equivalence test (TOST)")
    r.kv("Two one-sided tests (Welch)", [
        (f"Difference ({table.names[idx[1]]} - {table.names[idx[0]]})", d),
        ("Equivalence margins", f"{fmt(lo_m)} to {fmt(hi_m)}"),
        (f"{int((1 - 2 * alpha) * 100)}% CI of difference", f"{fmt(lo)} to {fmt(hi)}"),
        ("P (difference > lower margin)", fmt_p(p1)), ("P (difference < upper margin)", fmt_p(p2)),
        ("TOST P value", fmt_p(p)), (f"Equivalent (P < {alpha})?", "Yes — the groups are equivalent within the margins" if p < alpha else "Not shown"),
    ])
    r.warn("Equivalence margins must be chosen from scientific or clinical reasoning before seeing the data.")
    return r


def _jzs_bf10(t, n_eff, df, r=math.sqrt(2) / 2):
    """JZS Bayes factor (Rouder et al. 2009) with a Cauchy(0, r) prior on effect size."""
    def integrand(g):
        return ((1 + n_eff * g * r ** 2) ** -0.5 * (1 + t ** 2 / ((1 + n_eff * g * r ** 2) * df)) ** (-(df + 1) / 2)
                * (2 * math.pi) ** -0.5 * g ** -1.5 * math.exp(-1 / (2 * g)))
    num, _ = integrate.quad(integrand, 0, np.inf, limit=200)
    den = (1 + t ** 2 / df) ** (-(df + 1) / 2)
    return num / den


def bayes_t(table, params):
    idx = selected(table, params)
    require(len(idx) >= 2, "Choose two data sets.")
    paired = params.get("paired") in (True, "true")
    rscale = float(params.get("rscale", math.sqrt(2) / 2) or math.sqrt(2) / 2)
    if paired:
        M = np.column_stack([table.Y[i][:, 0] for i in idx[:2]])
        M = M[np.all(np.isfinite(M), axis=1)]
        d = M[:, 1] - M[:, 0]
        require(len(d) >= 3, "Need at least three pairs.")
        t = float(stats.ttest_1samp(d, 0).statistic)
        n_eff, df = len(d), len(d) - 1
        eff = d.mean() / d.std(ddof=1)
    else:
        a, b = table.column_values(idx[0]), table.column_values(idx[1])
        require(len(a) >= 2 and len(b) >= 2, "Each group needs at least two values.")
        t = float(stats.ttest_ind(b, a).statistic)
        n_eff, df = len(a) * len(b) / (len(a) + len(b)), len(a) + len(b) - 2
        sp = math.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / df)
        eff = (b.mean() - a.mean()) / sp
    bf = _jzs_bf10(t, n_eff, df, rscale)
    verdict = ("Extreme" if bf > 100 else "Very strong" if bf > 30 else "Strong" if bf > 10 else "Moderate" if bf > 3 else "Anecdotal") \
        + " evidence for a difference" if bf >= 1 else \
        ("Extreme" if bf < 0.01 else "Very strong" if bf < 1 / 30 else "Strong" if bf < 0.1 else "Moderate" if bf < 1 / 3 else "Anecdotal") \
        + " evidence for NO difference"
    r = Result("Bayesian t test (JZS Bayes factor)")
    r.kv("Bayes factor", [("Design", "Paired" if paired else "Unpaired"), ("t", t), ("Effect size (Cohen's d)", eff),
                          ("Prior: Cauchy scale r", rscale), ("BF10 (difference vs. no difference)", bf), ("BF01", 1 / bf if bf else np.inf),
                          ("Interpretation (Jeffreys/Lee & Wagenmakers)", verdict)])
    r.warn("Unlike a P value, a Bayes factor can also quantify evidence FOR the null hypothesis.")
    return r


def bootstrap(table, params):
    idx = selected(table, params)
    stat = params.get("statistic", "mean")
    n_boot = int(min(max(int(params.get("resamples", 5000) or 5000), 200), 20000))
    level = float(params.get("ci", 0.95))
    rng = np.random.default_rng(int(params.get("seed", 1) or 1))
    f = {"mean": np.mean, "median": np.median, "sd": lambda v, axis=None: np.std(v, ddof=1, axis=axis)}[stat]
    r = Result(f"Bootstrap confidence intervals ({stat})")
    rows = []
    for i in idx:
        v = table.column_values(i)
        if len(v) < 3:
            continue
        bs = f(rng.choice(v, (n_boot, len(v)), replace=True), axis=1)
        lo, hi = np.percentile(bs, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
        rows.append([table.names[i], len(v), f(v), bs.std(ddof=1), f"{fmt(lo)} to {fmt(hi)}"])
    r.table(f"{int(level * 100)}% percentile bootstrap CI ({n_boot} resamples)", ["Data set", "N", stat.capitalize(), "Bootstrap SE", "CI"], rows)
    if len(idx) >= 2:
        a, b = table.column_values(idx[0]), table.column_values(idx[1])
        if len(a) >= 3 and len(b) >= 3:
            da = f(rng.choice(a, (n_boot, len(a))), axis=1)
            db = f(rng.choice(b, (n_boot, len(b))), axis=1)
            diff = db - da
            lo, hi = np.percentile(diff, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
            r.kv(f"Difference of {stat}s ({table.names[idx[1]]} - {table.names[idx[0]]})",
                 [("Estimate", f(b) - f(a)), (f"{int(level * 100)}% CI", f"{fmt(lo)} to {fmt(hi)}"),
                  ("CI excludes 0?", "Yes" if lo > 0 or hi < 0 else "No")])
    return r


def permutation(table, params):
    idx = selected(table, params)
    require(len(idx) >= 2, "Choose two data sets.")
    a, b = table.column_values(idx[0]), table.column_values(idx[1])
    require(len(a) >= 2 and len(b) >= 2, "Each group needs at least two values.")
    stat = params.get("statistic", "mean")
    f = np.mean if stat == "mean" else np.median
    obs = f(b) - f(a)
    pooled = np.concatenate([a, b])
    na = len(a)
    n_total = math.comb(len(pooled), na)
    rng = np.random.default_rng(1)
    if n_total <= 20000:
        diffs = []
        for comb in itertools.combinations(range(len(pooled)), na):
            mask = np.zeros(len(pooled), bool)
            mask[list(comb)] = True
            diffs.append(f(pooled[~mask]) - f(pooled[mask]))
        diffs = np.array(diffs)
        kind = f"exact ({n_total} permutations)"
    else:
        diffs = np.empty(20000)
        for k in range(20000):
            p = rng.permutation(pooled)
            diffs[k] = f(p[na:]) - f(p[:na])
        kind = "Monte Carlo (20 000 random permutations)"
    p = float((np.abs(diffs) >= abs(obs) - 1e-12).mean())
    r = Result("Permutation test")
    r.kv("Permutation test", [("Statistic", f"difference of {stat}s"), ("Observed difference", obs), ("Method", kind),
                              ("Two-tailed P value", fmt_p(max(p, 1 / len(diffs)))), ("Summary", stars(p, 0.05))])
    r.warn("Permutation tests make no distributional assumption; they assume exchangeability under the null hypothesis.")
    return r
