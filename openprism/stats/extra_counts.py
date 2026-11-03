"""Additional analyses of counts and survival data: exact and paired
contingency tests, agreement (kappa), diagnostic accuracy, risk measures,
proportions with confidence intervals, stratified (Mantel-Haenszel) analysis,
and weighted log-rank tests / restricted mean survival time."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from .common import Result, fmt, fmt_p, require, stars
from .contingency import _matrix
from .descriptive import selected
from .extra_column import SEED, TEST_COLS, _row


def _alpha(params):
    return float(params.get("alpha", 0.05))


def _table(table, params, square=False, two_by_two=False, min_rows=2):
    idx = selected(table, params)
    require(len(idx) >= 2, "Select at least two outcome columns.")
    M, labels = _matrix(table, idx)
    require(M.shape[0] >= min_rows, f"Need at least {min_rows} row(s).")
    require(np.all(M >= 0) and np.allclose(M, np.round(M)), "Contingency tables hold counts (non-negative whole numbers).")
    if two_by_two:
        require(M.shape == (2, 2), "This analysis needs a 2 × 2 table (two rows, two columns).")
    if square:
        require(M.shape[0] == M.shape[1], "This analysis needs a square table (same categories in rows and columns).")
    return M.astype(float), labels, [table.names[i] for i in idx]


# ---------------------------------------------------------------- confidence intervals of a proportion
def prop_ci(x, n, level=0.95, method="wilson"):
    if n == 0:
        return np.nan, np.nan
    a = 1 - level
    z = stats.norm.ppf(1 - a / 2)
    p = x / n
    if method == "wilson":
        c = (p + z * z / (2 * n)) / (1 + z * z / n)
        h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
        return max(0.0, c - h), min(1.0, c + h)
    if method == "clopper":
        lo = stats.beta.ppf(a / 2, x, n - x + 1) if x > 0 else 0.0
        hi = stats.beta.ppf(1 - a / 2, x + 1, n - x) if x < n else 1.0
        return float(lo), float(hi)
    if method == "jeffreys":
        lo = stats.beta.ppf(a / 2, x + 0.5, n - x + 0.5) if x > 0 else 0.0
        hi = stats.beta.ppf(1 - a / 2, x + 0.5, n - x + 0.5) if x < n else 1.0
        return float(lo), float(hi)
    if method == "agresti":
        nt = n + z * z
        pt = (x + z * z / 2) / nt
        h = z * math.sqrt(pt * (1 - pt) / nt)
        return max(0.0, pt - h), min(1.0, pt + h)
    h = z * math.sqrt(p * (1 - p) / n)  # Wald
    return max(0.0, p - h), min(1.0, p + h)


def _ci(lo, hi):
    return f"{fmt(lo)} to {fmt(hi)}"


# ---------------------------------------------------------------- more contingency tests
def contingency_more(table, params):
    M, labels, names = _table(table, params)
    alpha = _alpha(params)
    r = Result("Contingency tests")
    rows = []
    R, C = M.shape
    N = M.sum()
    E = np.outer(M.sum(1), M.sum(0)) / N
    chi, p, dof, _ = stats.chi2_contingency(M, correction=False)
    rows.append(_row("Pearson chi-square", chi, dof, p, alpha, ""))
    nz = M > 0
    G = 2 * (M[nz] * np.log(M[nz] / E[nz])).sum()
    q = 1 + (N * (1 / M.sum(1)).sum() - 1) * (N * (1 / M.sum(0)).sum() - 1) / (6 * N * dof) if dof > 0 else 1
    rows.append(_row("G test (likelihood ratio)", G, dof, stats.chi2.sf(G, dof), alpha, ""))
    rows.append(_row("G test with Williams' correction", G / q, dof, stats.chi2.sf(G / q, dof), alpha, "better for small samples"))
    if (R, C) == (2, 2):
        a, b, c, d = M.ravel()
        rows.append(_row("Fisher's exact test", stats.fisher_exact(M).statistic, "", stats.fisher_exact(M).pvalue, alpha, "conditional on both margins"))
        chi_y, p_y, _, _ = stats.chi2_contingency(M, correction=True)
        rows.append(_row("Chi-square with Yates' correction", chi_y, 1, p_y, alpha, "conservative"))
        try:
            bn = stats.barnard_exact(M)
            rows.append(_row("Barnard's exact test", bn.statistic, "", bn.pvalue, alpha, "unconditional; usually more powerful than Fisher"))
            bs = stats.boschloo_exact(M)
            rows.append(_row("Boschloo's exact test", bs.statistic, "", bs.pvalue, alpha, "unconditional; uniformly more powerful than Fisher"))
        except Exception:  # noqa: BLE001
            pass
        nd = b + c
        if nd > 0:
            mc = (b - c) ** 2 / nd
            mcc = (abs(b - c) - 1) ** 2 / nd
            rows.append(_row("McNemar (paired: rows = test 1, columns = test 2)", mc, 1, stats.chi2.sf(mc, 1), alpha, f"discordant pairs {int(b)} vs {int(c)}"))
            rows.append(_row("McNemar with continuity correction", mcc, 1, stats.chi2.sf(mcc, 1), alpha, ""))
            rows.append(_row("McNemar exact (binomial)", min(b, c), "", stats.binomtest(int(b), int(nd), 0.5).pvalue, alpha, "recommended when discordant pairs < 25"))
    else:
        # Fisher-Freeman-Halton exact test by Monte-Carlo (fixed seed)
        rt = stats.random_table(M.sum(1).astype(int), M.sum(0).astype(int), seed=SEED)
        obs = rt.logpmf(M.astype(int))
        sims = rt.rvs(20000)
        lp = np.array([rt.logpmf(s) for s in sims])
        pmc = ((lp <= obs + 1e-7).sum() + 1) / (len(sims) + 1)
        rows.append(_row("Fisher-Freeman-Halton exact (Monte Carlo, 20 000 tables)", np.exp(obs), "", pmc, alpha, "for r × c tables with small counts"))
    if R == C and R >= 2:
        from statsmodels.stats.contingency_tables import SquareTable
        st = SquareTable(M, shift_zeros=False)
        try:
            sy = st.symmetry()
            rows.append(_row("Bowker test of symmetry (paired categories)", sy.statistic, sy.df, sy.pvalue, alpha, "generalizes McNemar"))
            hm = st.homogeneity()
            rows.append(_row("Stuart-Maxwell marginal homogeneity", hm.statistic, hm.df, hm.pvalue, alpha, ""))
        except Exception:  # noqa: BLE001
            pass
    if C == 2 and R >= 3:
        x = M[:, 0]
        n = M.sum(1)
        s = np.arange(R, dtype=float)
        pbar = x.sum() / n.sum()
        T = (s * (x - n * pbar)).sum()
        V = pbar * (1 - pbar) * ((n * s ** 2).sum() - (n * s).sum() ** 2 / n.sum())
        z = T / math.sqrt(V)
        rows.append(_row("Cochran-Armitage test for trend (rows ordered, scores 1…k)", z, "", 2 * stats.norm.sf(abs(z)), alpha, f"proportion in '{names[0]}' changes with row order"))
    r.table("Tests", TEST_COLS, rows)
    # association measures
    assoc = [("Cramér's V", math.sqrt(chi / (N * (min(R, C) - 1)))), ("Contingency coefficient C", math.sqrt(chi / (chi + N))),
             ("Phi (2×2) / φ", math.sqrt(chi / N) * (np.sign(M[0, 0] * M[1, 1] - M[0, 1] * M[1, 0]) if (R, C) == (2, 2) else 1))]
    conc = disc = 0.0
    for i in range(R):
        for j in range(C):
            conc += M[i, j] * M[i + 1:, j + 1:].sum()
            disc += M[i, j] * M[i + 1:, :j].sum()
    if conc + disc > 0:
        assoc.append(("Goodman-Kruskal γ (ordinal rows and columns)", (conc - disc) / (conc + disc)))
    rr_ = np.repeat(np.arange(R), M.sum(1).astype(int))
    cc_ = np.concatenate([np.repeat(np.arange(C), M[i].astype(int)) for i in range(R)])
    tb = stats.kendalltau(rr_, cc_)
    assoc.append(("Kendall τ-b (ordinal)", tb.statistic))
    assoc.append(("P value of τ-b", fmt_p(tb.pvalue)))
    try:
        sd = stats.somersd(rr_, cc_)
        assoc.append(("Somers' d (columns given rows)", sd.statistic))
    except Exception:  # noqa: BLE001
        pass
    r.kv("Measures of association", assoc)
    if (E < 5).any():
        r.warn("Some expected counts are below 5: prefer the exact tests.")
    return r


# ---------------------------------------------------------------- agreement (kappa)
def kappa(table, params):
    from statsmodels.stats.inter_rater import cohens_kappa
    M, labels, names = _table(table, params, square=True)
    alpha = _alpha(params)
    level = 1 - alpha
    z = stats.norm.ppf(0.5 + level / 2)
    k = M.shape[0]
    r = Result("Inter-rater agreement (Cohen's kappa)")
    rows = []
    for wt, lab in ([(None, "Unweighted κ")] + ([("linear", "Linear-weighted κ"), ("quadratic", "Quadratic-weighted κ (≈ ICC)")] if k > 2 else [])):
        res = cohens_kappa(M, wt=wt)
        se = float(res["std_kappa"])
        rows.append([lab, float(res["kappa"]), se, _ci(res["kappa"] - z * se, res["kappa"] + z * se), float(res["z_value"]), fmt_p(float(res["pvalue_two_sided"]))])
    r.table(f"Kappa (rows = rater 1, columns = rater 2; {int(M.sum())} subjects)", ["Statistic", "κ", "SE", f"{int(round(level * 100))}% CI", "z (H0: κ = 0)", "P value"], rows)
    N = M.sum()
    po = np.trace(M) / N
    pe = (M.sum(0) * M.sum(1)).sum() / N ** 2
    kmax = (np.minimum(M.sum(0), M.sum(1)).sum() / N - pe) / (1 - pe) if pe < 1 else np.nan
    r.kv("Agreement", [("Observed agreement", po), ("Agreement expected by chance", pe), ("Maximum possible κ given the marginals", kmax),
                       ("PABAK (prevalence- and bias-adjusted κ)", (k * po - 1) / (k - 1)),
                       ("Interpretation (Landis & Koch)", "<0 poor, 0–0.2 slight, 0.21–0.4 fair, 0.41–0.6 moderate, 0.61–0.8 substantial, >0.8 almost perfect")])
    return r


# ---------------------------------------------------------------- diagnostic accuracy
def diagnostic(table, params):
    M, labels, names = _table(table, params, two_by_two=True)
    alpha = _alpha(params)
    level = 1 - alpha
    method = params.get("ciMethod", "wilson")
    tp, fp, fn, tn = M[0, 0], M[0, 1], M[1, 0], M[1, 1]
    z = stats.norm.ppf(0.5 + level / 2)
    pct = f"{int(round(level * 100))}%"

    def pr(x, n, lab):
        v = x / n if n else np.nan
        lo, hi = prop_ci(x, n, level, method)
        return [lab, v, _ci(lo, hi), f"{int(x)} / {int(n)}"]
    rows = [pr(tp, tp + fn, "Sensitivity (true positive rate)"), pr(tn, tn + fp, "Specificity (true negative rate)"),
            pr(tp, tp + fp, "Positive predictive value (at this prevalence)"), pr(tn, tn + fn, "Negative predictive value (at this prevalence)"),
            pr(tp + tn, M.sum(), "Accuracy"), pr(tp + fn, M.sum(), "Prevalence in this sample")]
    sens, spec = tp / (tp + fn), tn / (tn + fp)

    def ratio_ci(est, se):
        return _ci(est * math.exp(-z * se), est * math.exp(z * se)) if np.isfinite(se) and est > 0 else ""
    lrp = sens / (1 - spec) if spec < 1 else np.inf
    lrn = (1 - sens) / spec if spec > 0 else np.inf
    se_lrp = math.sqrt(1 / tp - 1 / (tp + fn) + 1 / fp - 1 / (fp + tn)) if tp and fp else np.nan
    se_lrn = math.sqrt(1 / fn - 1 / (tp + fn) + 1 / tn - 1 / (fp + tn)) if fn and tn else np.nan
    dor = (tp * tn) / (fp * fn) if fp and fn else np.inf
    se_dor = math.sqrt(1 / tp + 1 / fp + 1 / fn + 1 / tn) if min(tp, fp, fn, tn) > 0 else np.nan
    rows += [["Positive likelihood ratio LR+", lrp, ratio_ci(lrp, se_lrp), ""], ["Negative likelihood ratio LR−", lrn, ratio_ci(lrn, se_lrn), ""],
             ["Diagnostic odds ratio", dor, ratio_ci(dor, se_dor), ""], ["Youden's J (sens + spec − 1)", sens + spec - 1, "", ""]]
    r = Result("Diagnostic test accuracy")
    r.table(f"Rows: test positive / negative; columns: disease present / absent ({ {'wilson': 'Wilson', 'clopper': 'Clopper-Pearson exact', 'jeffreys': 'Jeffreys', 'agresti': 'Agresti-Coull'}.get(method, method)} intervals)",
            ["Measure", "Value", f"{pct} CI", "Counts"], rows)
    prev = params.get("prevalence")
    if prev not in (None, ""):
        pv = float(prev)
        ppv = sens * pv / (sens * pv + (1 - spec) * (1 - pv))
        npv = spec * (1 - pv) / ((1 - sens) * pv + spec * (1 - pv))
        r.kv(f"Predictive values at a prevalence of {fmt(pv * 100)}%", [("PPV", ppv), ("NPV", npv),
                                                                        ("Post-test probability after a positive result", ppv),
                                                                        ("Post-test probability after a negative result", 1 - npv)])
    return r


# ---------------------------------------------------------------- risk measures
def newcombe_diff(x1, n1, x2, n2, level=0.95):
    p1, p2 = x1 / n1, x2 / n2
    l1, u1 = prop_ci(x1, n1, level, "wilson")
    l2, u2 = prop_ci(x2, n2, level, "wilson")
    d = p1 - p2
    lo = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return lo, hi


def risk(table, params):
    M, labels, names = _table(table, params, two_by_two=True)
    alpha = _alpha(params)
    level = 1 - alpha
    z = stats.norm.ppf(0.5 + level / 2)
    a, b, c, d = M.ravel()
    n1, n2 = a + b, c + d
    p1, p2 = a / n1, c / n2
    pct = f"{int(round(level * 100))}%"
    r = Result("Risk and odds")
    rows = [[f"Risk in '{labels[0]}' ({names[0]})", p1, _ci(*prop_ci(a, n1, level))], [f"Risk in '{labels[1]}'", p2, _ci(*prop_ci(c, n2, level))]]
    rd = p1 - p2
    lo, hi = newcombe_diff(a, n1, c, n2, level)
    rows.append(["Risk difference (absolute risk reduction if negative)", rd, f"{_ci(lo, hi)} (Newcombe)"])
    if rd != 0:
        nnt = 1 / abs(rd)
        if lo > 0 or hi < 0:
            nci = _ci(1 / max(abs(lo), abs(hi)), 1 / min(abs(lo), abs(hi)))
        else:
            nci = "CI of difference includes 0: NNT ranges to ∞"
        rows.append([f"Number needed to {'harm' if rd > 0 else 'treat'}", nnt, nci])
    aa, bb, cc, dd = (x + 0.5 for x in (a, b, c, d)) if min(a, b, c, d) == 0 else (a, b, c, d)
    rr = (aa / (aa + bb)) / (cc / (cc + dd))
    se = math.sqrt(1 / aa - 1 / (aa + bb) + 1 / cc - 1 / (cc + dd))
    rows.append(["Relative risk (risk ratio)", rr, f"{_ci(rr * math.exp(-z * se), rr * math.exp(z * se))} (Katz log)"])
    rows.append(["Relative risk reduction (1 − RR)", 1 - rr, ""])
    orr = (aa * dd) / (bb * cc)
    se_o = math.sqrt(1 / aa + 1 / bb + 1 / cc + 1 / dd)
    rows.append(["Odds ratio", orr, f"{_ci(orr * math.exp(-z * se_o), orr * math.exp(z * se_o))} (Woolf)"])
    try:
        from scipy.stats.contingency import odds_ratio
        cond = odds_ratio(M.astype(int), kind="conditional")
        ci = cond.confidence_interval(level)
        rows.append(["Odds ratio (conditional MLE)", cond.statistic, f"{_ci(ci.low, ci.high)} (exact)"])
    except Exception:  # noqa: BLE001
        pass
    if rr > 1:
        rows.append(["Attributable fraction among the exposed", (rr - 1) / rr, ""])
    r.table(f"Rows = groups (first row = exposed/treated), columns = outcome (first column = event); {pct} CIs", ["Measure", "Value", "CI"], rows)
    fe = stats.fisher_exact(M)
    chi, pc, _, _ = stats.chi2_contingency(M, correction=False)
    zt = (p1 - p2) / math.sqrt((a + c) / (n1 + n2) * (1 - (a + c) / (n1 + n2)) * (1 / n1 + 1 / n2)) if 0 < a + c < n1 + n2 else np.nan
    r.kv("Tests (H0: same risk in both groups)", [("Fisher's exact P", fmt_p(fe.pvalue)), ("Chi-square P", fmt_p(pc)), ("z test of two proportions", zt),
                                                 ("Summary (Fisher)", stars(fe.pvalue, alpha))])
    if min(a, b, c, d) == 0:
        r.warn("A cell is zero: 0.5 was added to every cell for the ratio estimates (Haldane-Anscombe).")
    return r


# ---------------------------------------------------------------- proportions
def proportion(table, params):
    M, labels, names = _table(table, params, min_rows=1)
    require(M.shape[1] >= 2, "Enter successes in the first column and failures in the second.")
    alpha = _alpha(params)
    level = 1 - alpha
    p0 = float(params.get("p0", 0.5) or 0.5)
    pct = f"{int(round(level * 100))}%"
    rows = []
    for lab, row in zip(labels, M):
        x, n = row[0], row[0] + row[1]
        if n == 0:
            continue
        bt = stats.binomtest(int(x), int(n), p0)
        rows.append([lab, int(x), int(n), x / n] + [_ci(*prop_ci(x, n, level, m)) for m in ("wilson", "clopper", "jeffreys", "agresti", "wald")]
                    + [fmt_p(bt.pvalue), stars(bt.pvalue, alpha)])
    r = Result("Proportions with confidence intervals")
    r.table(f"Proportion in '{names[0]}' ({pct} CIs; binomial test vs. {fmt(p0)})",
            ["Row", "Successes", "Total", "Proportion", "Wilson", "Clopper-Pearson (exact)", "Jeffreys", "Agresti-Coull", "Wald (not recommended)", "P (exact binomial)", "Summary"], rows)
    r.kv("Which interval?", [("Wilson / Jeffreys", "best general choice (coverage close to nominal)"), ("Clopper-Pearson", "guaranteed coverage, conservative"),
                             ("Wald", "shown only for comparison: poor coverage for small n or extreme p")])
    return r


# ---------------------------------------------------------------- stratified 2×2 (Mantel-Haenszel)
def cmh(table, params):
    from statsmodels.stats.contingency_tables import StratifiedTable
    M, labels, names = _table(table, params)
    require(M.shape[1] == 2 and M.shape[0] % 2 == 0 and M.shape[0] >= 4, "Enter one 2 × 2 table per stratum: rows in pairs (exposed, unexposed), two outcome columns.")
    alpha = _alpha(params)
    tabs = [M[i:i + 2] for i in range(0, M.shape[0], 2)]
    st = StratifiedTable(tabs)
    ci = st.oddsratio_pooled_confint(alpha=alpha)
    t = st.test_null_odds(correction=bool(params.get("correction", False)))
    bd = st.test_equal_odds(adjust=True)
    r = Result("Cochran-Mantel-Haenszel analysis of stratified 2 × 2 tables")
    rows = []
    for j, T in enumerate(tabs):
        a, b, c, d = T.ravel()
        o = a * d / (b * c) if b * c > 0 else np.inf
        rows.append([f"Stratum {j + 1} ({labels[2 * j]} / {labels[2 * j + 1]})", int(a), int(b), int(c), int(d), o])
    r.table("Strata", ["Stratum", "a", "b", "c", "d", "Odds ratio"], rows)
    r.kv("Pooled estimate", [("Mantel-Haenszel odds ratio", st.oddsratio_pooled), (f"{int(round((1 - alpha) * 100))}% CI", _ci(*ci)),
                             ("Mantel-Haenszel risk ratio", st.riskratio_pooled),
                             ("CMH chi-square (H0: common OR = 1)", t.statistic), ("P value", fmt_p(t.pvalue)), ("Summary", stars(t.pvalue, alpha)),
                             ("Breslow-Day-Tarone test of homogeneous ORs", bd.statistic), ("P value (homogeneity)", fmt_p(bd.pvalue)),
                             ("Interpretation", "If homogeneity is rejected, the strata have different odds ratios and the pooled OR may mislead.")])
    return r


# ---------------------------------------------------------------- survival extras
def _surv_groups(table, idx):
    from .survival import _groups
    return _groups(table, idx)


def weighted_logrank(groups, rho=0.0, gamma=0.0, kind="fh"):
    allt = np.unique(np.concatenate([g[0][g[1] == 1] for g in groups]))
    tt = np.concatenate([g[0] for g in groups])
    ee = np.concatenate([g[1] for g in groups])
    k = len(groups)
    O = np.zeros(k)
    E = np.zeros(k)
    V = np.zeros((k, k))
    S = 1.0
    Speto = 1.0
    for t in allt:
        n_j = np.array([(g[0] >= t).sum() for g in groups], float)
        d_j = np.array([((g[0] == t) & (g[1] == 1)).sum() for g in groups], float)
        n, d = n_j.sum(), d_j.sum()
        if kind == "fh":
            w = S ** rho * (1 - S) ** gamma  # pooled KM just before t (left-continuous)
        elif kind == "tw":
            w = math.sqrt(n)
        elif kind == "peto":
            w = Speto * (1 - d / (n + 1))  # Peto-Peto: S~(t) INCLUDING the current time (Klein & Moeschberger 7.3)
        else:
            w = 1.0
        if n >= 2:
            O += w * d_j
            E += w * d * n_j / n
            fac = d * (n - d) / (n * n * (n - 1))
            V += w * w * fac * (np.diag(n_j) * n - np.outer(n_j, n_j))
        S *= 1 - d / n
        Speto *= 1 - d / (n + 1)
    del tt, ee
    diff = (O - E)[:-1]
    try:
        chi = float(diff @ np.linalg.solve(V[:-1, :-1], diff))
    except np.linalg.LinAlgError:
        chi = np.nan
    return chi, float(stats.chi2.sf(chi, k - 1)) if np.isfinite(chi) else np.nan


def rmst(t, e, tau):
    """Restricted mean survival time up to tau with its variance (Klein & Moeschberger)."""
    order = np.argsort(t, kind="stable")
    t, e = t[order], e[order]
    times = np.unique(t[(e == 1) & (t <= tau)])
    S = 1.0
    pts = [(0.0, 1.0)]
    info = []
    for tt in times:
        n = (t >= tt).sum()
        d = ((t == tt) & (e == 1)).sum()
        S *= 1 - d / n
        pts.append((tt, S))
        info.append((tt, n, d))
    area = 0.0
    for (t0, s0), (t1, _) in zip(pts, pts[1:] + [(tau, None)]):
        area += s0 * (min(t1, tau) - t0)
    var = 0.0
    for j, (tt, n, d) in enumerate(info):
        # area under the curve from tt to tau
        a_j = 0.0
        seg = [p for p in pts if p[0] >= tt]
        for (t0, s0), (t1, _) in zip(seg, seg[1:] + [(tau, None)]):
            a_j += s0 * (min(t1, tau) - t0)
        if n - d > 0:
            var += a_j ** 2 * d / (n * (n - d))
    return area, var


def survival_more(table, params):
    from .survival import km
    require(table.type == "survival", "This analysis needs a Survival table.")
    alpha = _alpha(params)
    level = 1 - alpha
    idx = selected(table, params)
    groups = [g for g in _surv_groups(table, idx)]
    names = [table.names[i] for i in idx]
    require(all(len(g[0]) for g in groups), "Every selected group needs subjects.")
    r = Result("Survival: weighted log-rank tests, RMST and quantiles")
    z = stats.norm.ppf(0.5 + level / 2)
    if len(groups) >= 2:
        rows = []
        for lab, kw, note in [("Log-rank (Mantel-Cox)", {"kind": "lr"}, "equal weight at all times"),
                              ("Gehan-Breslow-Wilcoxon", {"kind": "tw_g"}, "weight = number at risk (early differences)"),
                              ("Tarone-Ware", {"kind": "tw"}, "weight = √(number at risk)"),
                              ("Peto-Peto", {"kind": "peto"}, "weight = Peto survival estimate (early differences)"),
                              ("Fleming-Harrington G(1,0)", {"kind": "fh", "rho": 1, "gamma": 0}, "emphasizes early differences"),
                              ("Fleming-Harrington G(0,1)", {"kind": "fh", "rho": 0, "gamma": 1}, "emphasizes late differences (delayed effects)"),
                              ("Fleming-Harrington G(1,1)", {"kind": "fh", "rho": 1, "gamma": 1}, "emphasizes middle differences")]:
            if kw["kind"] == "tw_g":
                from .survival import logrank
                chi, p, _, _ = logrank(groups, "gehan")
            else:
                chi, p = weighted_logrank(groups, kw.get("rho", 0), kw.get("gamma", 0), kw["kind"])
            rows.append(_row(lab, chi, len(groups) - 1, p, alpha, note))
        if len(groups) >= 3:
            chi_t, p_t = _logrank_trend(groups)
            rows.append(_row("Log-rank test for trend (groups in table order)", chi_t, 1, p_t, alpha, "ordered groups, scores 1…k"))
        r.table("Comparison of survival curves", TEST_COLS, rows)
    tau_p = params.get("tau")
    tau = float(tau_p) if tau_p not in (None, "") else min(float(g[0].max()) for g in groups)
    rows = []
    est = []
    for nm, (t, e) in zip(names, groups):
        a, v = rmst(t, e, tau)
        se = math.sqrt(v)
        est.append((a, v))
        rows.append([nm, a, se, _ci(a - z * se, a + z * se), tau - a])
    r.table(f"Restricted mean survival time up to τ = {fmt(tau)}", ["Group", "RMST", "SE", f"{int(round(level * 100))}% CI", "Restricted mean time lost"], rows)
    if len(groups) == 2:
        (a1, v1), (a2, v2) = est
        d = a1 - a2
        se = math.sqrt(v1 + v2)
        p = 2 * stats.norm.sf(abs(d / se)) if se > 0 else np.nan
        lr = math.log(a1 / a2)
        sel = math.sqrt(v1 / a1 ** 2 + v2 / a2 ** 2)
        r.kv(f"RMST comparison ({names[0]} − {names[1]})", [("Difference", d), (f"{int(round(level * 100))}% CI", _ci(d - z * se, d + z * se)), ("P value", fmt_p(p)),
                                                           ("Ratio", a1 / a2), ("CI of ratio", _ci(math.exp(lr - z * sel), math.exp(lr + z * sel))),
                                                           ("Why RMST?", "valid without proportional hazards; easy to interpret as time gained")])
    qrows = []
    for nm, (t, e) in zip(names, groups):
        curve = km(t, e, level)
        row = [nm]
        for q in (0.75, 0.5, 0.25):
            est_ = next((c[0] for c in curve if c[1] <= q + 1e-12), None)
            lo = next((c[0] for c in curve if c[3] <= q + 1e-12), None)
            hi = next((c[0] for c in curve if c[2] <= q + 1e-12), None)
            row += [est_ if est_ is not None else "not reached", f"{fmt(lo) if lo is not None else 'NR'} to {fmt(hi) if hi is not None else 'NR'}"]
        qrows.append(row)
    r.table("Survival quantiles (time when survival falls to 75%, 50% = median, 25%) with log-log CIs", ["Group", "75% surv.", "CI", "Median", "CI", "25% surv.", "CI"], qrows)
    plots = []
    traces = []
    for nm, (t, e) in zip(names, groups):
        order = np.argsort(t)
        tt, ee = t[order], e[order]
        H, xs, ys = 0.0, [0.0], [0.0]
        for u in np.unique(tt[ee == 1]):
            n = (tt >= u).sum()
            d = ((tt == u) & (ee == 1)).sum()
            H += d / n
            xs += [float(u), float(u)]
            ys += [ys[-1], H]
        traces.append({"type": "scatter", "mode": "lines", "x": xs, "y": ys, "name": nm})
    plots.append({"title": "Nelson-Aalen cumulative hazard", "xTitle": table.x_title or "Time", "yTitle": "Cumulative hazard", "traces": traces})
    r.overlay = {"kind": "plot", "plots": plots}
    return r


def _logrank_trend(groups):
    allt = np.unique(np.concatenate([g[0][g[1] == 1] for g in groups]))
    k = len(groups)
    O, E = np.zeros(k), np.zeros(k)
    V = np.zeros((k, k))
    for t in allt:
        n_j = np.array([(g[0] >= t).sum() for g in groups], float)
        d_j = np.array([((g[0] == t) & (g[1] == 1)).sum() for g in groups], float)
        n, d = n_j.sum(), d_j.sum()
        if n < 2:
            continue
        O += d_j
        E += d * n_j / n
        V += d * (n - d) / (n * n * (n - 1)) * (np.diag(n_j) * n - np.outer(n_j, n_j))
    s = np.arange(1, k + 1, dtype=float)
    U = s @ (O - E)
    var = s @ V @ s
    chi = U ** 2 / var
    return chi, float(stats.chi2.sf(chi, 1))


# ---------------------------------------------------------------- competing risks
def cumulative_incidence(t, code):
    """Aalen-Johansen cumulative incidence of cause 1 (code 1) with competing cause(s) (code ≥ 2).

    Returns [(time, CIF1, naive 1−KM treating competing events as censored, CIF of competing events)]."""
    order = np.argsort(t, kind="stable")
    t, code = t[order], code[order]
    S = 1.0
    S_naive = 1.0
    F1 = F2 = 0.0
    out = [(0.0, 0.0, 0.0, 0.0)]
    for u in np.unique(t[code > 0]):
        n = (t >= u).sum()
        d1 = ((t == u) & (code == 1)).sum()
        d2 = ((t == u) & (code >= 2)).sum()
        F1 += S * d1 / n
        F2 += S * d2 / n
        S *= 1 - (d1 + d2) / n
        S_naive *= 1 - d1 / n
        out.append((float(u), F1, 1 - S_naive, F2))
    return out


def competing_risks(table, params):
    require(table.type == "survival", "Competing-risks analysis needs a Survival table (codes 1 = event of interest, 2 = competing event, 0 = censored).")
    idx = selected(table, params)
    r = Result("Competing risks: cumulative incidence (Aalen-Johansen)")
    traces = []
    horizon = params.get("horizon")
    for i in idx:
        ev = table.Y[i][:, 0]
        m = np.isfinite(table.x) & np.isfinite(ev)
        t, code = table.x[m], ev[m].astype(int)
        if not len(t):
            continue
        require(np.all(np.isin(code, [0, 1, 2, 3, 4, 5])), "Use 0 = censored, 1 = event of interest, 2 (or more) = competing event.")
        cif = cumulative_incidence(t, code)
        nm = table.names[i]
        rows = [[u, f1 * 100, naive * 100, f2 * 100] for u, f1, naive, f2 in cif[1:]]
        r.table(f"{nm}: {len(t)} subjects, {int((code == 1).sum())} events of interest, {int((code >= 2).sum())} competing, {int((code == 0).sum())} censored",
                ["Time", "Cumulative incidence (%)", "1 − Kaplan-Meier, competing censored (%)", "Cumulative incidence of competing events (%)"], rows)
        if horizon not in (None, ""):
            h_ = float(horizon)
            last = [c for c in cif if c[0] <= h_][-1]
            r.kv(f"{nm} at time {fmt(h_)}", [("Cumulative incidence", f"{fmt(last[1] * 100)}%"), ("1 − KM (biased upward when competing events exist)", f"{fmt(last[2] * 100)}%")])
        xs, ys = [0.0], [0.0]
        for u, f1, _, _ in cif[1:]:
            xs += [u, u]
            ys += [ys[-1], f1 * 100]
        traces.append({"type": "scatter", "mode": "lines", "x": xs, "y": ys, "name": nm})
    require(traces, "No data.")
    if len(traces) >= 2:
        from .competing import gray_section
        gray_section(r, table, [i for i in idx if np.isfinite(table.Y[i][:, 0]).any()])
    r.kv("Notes", [("Why not 1 − Kaplan-Meier?", "Treating competing events as censored assumes those subjects could still have the event of interest; this overestimates its probability."),
                   ("Comparing groups", "Gray's test compares whole cumulative incidence curves (one test per event type). For covariates use Fine-Gray regression (Multiple variables table); for effects on the cause-specific hazard, Cox regression with competing events coded as censored.")])
    r.overlay = {"kind": "plot", "plots": [{"title": "Cumulative incidence", "xTitle": table.x_title or "Time", "yTitle": "Cumulative incidence (%)", "traces": traces}]}
    return r
