"""Additional model-based analyses: meta-analysis, robust and quantile
regression, Mann-Kendall trend, cosinor rhythms, generalized linear models,
ordinal regression, regression diagnostics, MANOVA, partial correlation,
cluster analysis and nonparametric two-way ANOVA."""
from __future__ import annotations

import itertools
import math

import numpy as np
from scipy import optimize, stats

from .common import Result, fmt, fmt_p, quiet, require, sig, stars
from .descriptive import selected
from .extra_column import SEED, TEST_COLS, _row


def _alpha(params):
    return float(params.get("alpha", 0.05))


def _clean(a):
    return [float(v) if v is not None and np.isfinite(v) else None for v in np.asarray(a, float)]


def _col(table, i):
    a = table.Y[i]
    return a[:, 0] if a.shape[1] == 1 else np.nanmean(a, axis=1)


# =============================================================== meta-analysis
def _effects_from_table(table, params):
    """Return (labels, yi, vi, measure label, is_ratio) from the selected columns."""
    fmt_ = params.get("format", "es_se")
    idx = selected(table, params)
    cols = [_col(table, i) for i in idx]
    need = {"es_se": 2, "es_ci": 3, "means": 6, "counts": 4}[fmt_]
    require(len(cols) >= need, f"This input format needs {need} columns (in order); {len(cols)} selected.")
    C = np.column_stack(cols[:need])
    keep = np.all(np.isfinite(C), axis=1)
    labels = [lab for lab, k in zip(table.row_labels, keep) if k]
    C = C[keep]
    require(len(C) >= 2, "Need at least two studies (rows) with complete data.")
    measure = params.get("measure", "")
    ratio = False
    if fmt_ == "es_se":
        yi, vi = C[:, 0], C[:, 1] ** 2
        ratio = bool(params.get("logScale"))
        if ratio:
            yi = np.log(yi)
            vi = C[:, 1] ** 2  # SE must already be on the log scale
        label = "Effect"
    elif fmt_ == "es_ci":
        ratio = bool(params.get("logScale"))
        lev = float(params.get("ciLevel", 0.95))
        z = stats.norm.ppf(0.5 + lev / 2)
        if ratio:
            require(np.all(C > 0), "Ratio measures must be positive.")
            yi = np.log(C[:, 0])
            se = (np.log(C[:, 2]) - np.log(C[:, 1])) / (2 * z)
        else:
            yi = C[:, 0]
            se = (C[:, 2] - C[:, 1]) / (2 * z)
        vi = se ** 2
        label = "Effect"
    elif fmt_ == "means":
        m1, s1, n1, m2, s2, n2 = C.T
        if measure == "md":
            yi = m1 - m2
            vi = s1 ** 2 / n1 + s2 ** 2 / n2
            label = "Mean difference"
        else:
            df = n1 + n2 - 2
            sp = np.sqrt(((n1 - 1) * s1 ** 2 + (n2 - 1) * s2 ** 2) / df)
            d = (m1 - m2) / sp
            J = 1 - 3 / (4 * df - 1)
            yi = J * d
            vi = 1 / n1 + 1 / n2 + yi ** 2 / (2 * (n1 + n2))
            label = "Hedges' g (SMD)"
    else:  # counts: events1, n1, events2, n2
        a, n1, c, n2 = C.T
        b, d = n1 - a, n2 - c
        require(np.all(b >= 0) & np.all(d >= 0), "Events cannot exceed totals.")
        zero = (a == 0) | (b == 0) | (c == 0) | (d == 0)
        if measure != "rd":
            a, b, c, d = (np.where(zero, x + 0.5, x) for x in (a, b, c, d))
        if measure == "rr":
            yi = np.log((a / (a + b)) / (c / (c + d)))
            vi = 1 / a - 1 / (a + b) + 1 / c - 1 / (c + d)
            label, ratio = "Risk ratio", True
        elif measure == "rd":
            p1, p2 = a / n1, c / n2
            yi = p1 - p2
            vi = p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2
            label = "Risk difference"
        else:
            yi = np.log(a * d / (b * c))
            vi = 1 / a + 1 / b + 1 / c + 1 / d
            label, ratio = "Odds ratio", True
    require(np.all(vi > 0), "Every study needs a positive variance / standard error.")
    return labels, np.asarray(yi, float), np.asarray(vi, float), label, ratio


def tau2_estimate(yi, vi, method):
    k = len(yi)
    w = 1 / vi
    mu_f = (w * yi).sum() / w.sum()
    Q = (w * (yi - mu_f) ** 2).sum()
    if method == "fixed" or k < 2:
        return 0.0, Q
    if method == "dl":
        c = w.sum() - (w ** 2).sum() / w.sum()
        return max(0.0, (Q - (k - 1)) / c), Q
    if method == "pm":
        def g(t2):
            ww = 1 / (vi + t2)
            m = (ww * yi).sum() / ww.sum()
            return (ww * (yi - m) ** 2).sum() - (k - 1)
        if g(0) <= 0:
            return 0.0, Q
        hi = 1.0
        while g(hi) > 0:
            hi *= 2
        return optimize.brentq(g, 0, hi, xtol=1e-12), Q
    # REML (Fisher scoring, as in metafor)
    t2 = max(0.0, tau2_estimate(yi, vi, "dl")[0])
    for _ in range(500):
        ww = 1 / (vi + t2)
        m = (ww * yi).sum() / ww.sum()
        resid = yi - m
        num = (ww ** 2 * (resid ** 2 - vi)).sum() + (ww ** 2).sum() / ww.sum()
        new = max(0.0, num / (ww ** 2).sum())
        if abs(new - t2) < 1e-10:
            t2 = new
            break
        t2 = new
    return t2, Q


def meta_pool(yi, vi, method="reml", hk=False, level=0.95):
    k = len(yi)
    t2, Q = tau2_estimate(yi, vi, method)
    w = 1 / (vi + t2)
    mu = (w * yi).sum() / w.sum()
    se = math.sqrt(1 / w.sum())
    if hk and k > 1:
        q = (w * (yi - mu) ** 2).sum() / (k - 1)
        se = se * math.sqrt(max(q, 0))  # Hartung-Knapp (no truncation, as metafor's default)
        crit = stats.t.ppf(0.5 + level / 2, k - 1)
        p = 2 * stats.t.sf(abs(mu / se), k - 1)
        stat = mu / se
    else:
        crit = stats.norm.ppf(0.5 + level / 2)
        stat = mu / se
        p = 2 * stats.norm.sf(abs(stat))
    df = k - 1
    I2 = max(0.0, (Q - df) / Q) * 100 if Q > 0 else 0.0
    # I² from tau² (as metafor reports for random-effects models)
    wf = 1 / vi
    s2 = (k - 1) * wf.sum() / (wf.sum() ** 2 - (wf ** 2).sum()) if k > 1 else np.nan
    I2_tau = 100 * t2 / (t2 + s2) if k > 1 else np.nan
    tpi = stats.t.ppf(0.5 + level / 2, k - 2) if k > 2 else np.nan
    pi = (mu - tpi * math.sqrt(t2 + se ** 2), mu + tpi * math.sqrt(t2 + se ** 2)) if k > 2 and method != "fixed" else (np.nan, np.nan)
    zq = stats.norm.ppf(0.5 + level / 2)
    pi_z = (mu - zq * math.sqrt(t2 + se ** 2), mu + zq * math.sqrt(t2 + se ** 2)) if method != "fixed" else (np.nan, np.nan)
    return {"mu": mu, "se": se, "lo": mu - crit * se, "hi": mu + crit * se, "z": stat, "p": p, "tau2": t2, "Q": Q, "df": df,
            "pQ": float(stats.chi2.sf(Q, df)) if df > 0 else np.nan, "I2": I2, "I2_tau": I2_tau, "H2": Q / df if df > 0 else np.nan,
            "w": w / w.sum() * 100, "pi": pi, "pi_z": pi_z}


def meta(table, params):
    labels, yi, vi, label, ratio = _effects_from_table(table, params)
    method = params.get("method", "reml")
    hk = bool(params.get("hartungKnapp"))
    alpha = _alpha(params)
    level = 1 - alpha
    pct = f"{int(round(level * 100))}%"
    k = len(yi)
    back = (lambda v: math.exp(v)) if ratio else (lambda v: v)  # noqa: E731
    res = meta_pool(yi, vi, method, hk, level)
    fixed = meta_pool(yi, vi, "fixed", False, level)
    mname = {"fixed": "Fixed effect (inverse variance)", "dl": "Random effects (DerSimonian-Laird)", "reml": "Random effects (REML)", "pm": "Random effects (Paule-Mandel)"}[method]
    r = Result(f"Meta-analysis: {label}")
    z = stats.norm.ppf(0.5 + level / 2)
    se = np.sqrt(vi)
    r.table("Studies", ["Study", label + (" (ratio)" if ratio else ""), f"{pct} CI", "SE" + (" (log scale)" if ratio else ""), "Weight (%)"],
            [[lab, back(y), f"{fmt(back(y - z * s))} to {fmt(back(y + z * s))}", s, w] for lab, y, s, w in zip(labels, yi, se, res["w"])])
    out = [("Model", mname + (" with Hartung-Knapp adjustment" if hk else "")), ("Number of studies", k),
           (f"Pooled {label.lower()}", back(res["mu"])), (f"{pct} CI", f"{fmt(back(res['lo']))} to {fmt(back(res['hi']))}"),
           ("t" if hk else "z", res["z"]), ("P value", fmt_p(res["p"])), ("Summary", stars(res["p"], alpha))]
    if method != "fixed":
        out += [(f"{pct} prediction interval (a new study; t, k−2 df, Higgins 2009)", f"{fmt(back(res['pi'][0]))} to {fmt(back(res['pi'][1]))}" if np.isfinite(res["pi"][0]) else "needs ≥3 studies"),
                (f"{pct} prediction interval (normal quantile, metafor default)", f"{fmt(back(res['pi_z'][0]))} to {fmt(back(res['pi_z'][1]))}"),
                ("Fixed-effect estimate for comparison", f"{fmt(back(fixed['mu']))} ({fmt(back(fixed['lo']))} to {fmt(back(fixed['hi']))})")]
    if ratio:
        out.append(("Log-scale estimate (SE)", f"{fmt(res['mu'])} ({fmt(res['se'])})"))
    r.kv("Pooled estimate", out)
    r.kv("Heterogeneity", [("Cochran's Q", res["Q"]), ("df", res["df"]), ("P value", fmt_p(res["pQ"])),
                           ("τ² (between-study variance)", res["tau2"]), ("τ", math.sqrt(res["tau2"])),
                           ("I² (from Q, Higgins & Thompson)", f"{fmt(res['I2'])}%"),
                           ("I² (from τ²)", f"{fmt(res['I2_tau'])}%"), ("H²", res["H2"]),
                           ("Interpretation of I²", "≈25% low, ≈50% moderate, ≈75% high heterogeneity")])
    if k >= 3:
        import statsmodels.api as sm
        prec = 1 / se
        with quiet():
            eg = sm.OLS(yi / se, sm.add_constant(prec)).fit()
        tau_b, p_b = stats.kendalltau((yi - fixed["mu"]) / np.sqrt(vi - 1 / (1 / vi).sum()), vi)
        r.kv("Small-study effects / publication bias", [
            ("Egger's regression intercept", eg.params[0]), ("t", eg.tvalues[0]), ("df", k - 2), ("P value (Egger)", fmt_p(eg.pvalues[0])),
            ("Begg's rank correlation (Kendall τ)", tau_b), ("P value (Begg)", fmt_p(p_b)),
            ("Note", "These tests have low power with fewer than 10 studies.")])
        rows = []
        for j in range(k):
            m = np.arange(k) != j
            rr = meta_pool(yi[m], vi[m], method, hk, level)
            rows.append([labels[j], back(rr["mu"]), f"{fmt(back(rr['lo']))} to {fmt(back(rr['hi']))}", fmt_p(rr["p"]), rr["tau2"], f"{fmt(rr['I2'])}%"])
        r.table("Leave-one-out sensitivity analysis (study omitted)", ["Omitted", "Pooled", f"{pct} CI", "P", "τ²", "I²"], rows)
    # plots: forest + funnel
    lo_all = [back(y - z * s) for y, s in zip(yi, se)] + [back(res["lo"])]
    hi_all = [back(y + z * s) for y, s in zip(yi, se)] + [back(res["hi"])]
    est = [back(y) for y in yi] + [back(res["mu"])]
    names = list(labels) + [f"Pooled ({'RE' if method != 'fixed' else 'FE'})"]
    forest = {"title": "Forest plot", "xTitle": label + (" (log scale)" if ratio else ""), "yTitle": "", "xLog": ratio, "yCategory": True, "yReversed": True,
              "traces": [{"type": "scatter", "mode": "markers", "x": _clean(est[:-1]), "y": names[:-1], "name": "Studies",
                          "errorX": {"plus": _clean(np.array(hi_all[:-1]) - np.array(est[:-1])), "minus": _clean(np.array(est[:-1]) - np.array(lo_all[:-1]))},
                          "symbol": "square", "sizes": [float(4 + 16 * math.sqrt(w / max(res["w"]))) for w in res["w"]]},
                         {"type": "scatter", "mode": "markers", "x": [est[-1]], "y": [names[-1]], "name": "Pooled", "symbol": "diamond", "size": 16,
                          "errorX": {"plus": [hi_all[-1] - est[-1]], "minus": [est[-1] - lo_all[-1]]}}],
              "vlines": [{"x": 1 if ratio else 0, "dash": "dot"}, {"x": est[-1], "dash": "dash"}]}
    smax = float(se.max()) * 1.1
    grid = np.linspace(0, smax, 40)
    funnel = {"title": "Funnel plot", "xTitle": label + (" (log)" if ratio else ""), "yTitle": "Standard error", "yReversed": True,
              "traces": [{"type": "scatter", "mode": "markers", "x": _clean(yi), "y": _clean(se), "name": "Studies"},
                         {"type": "scatter", "mode": "lines", "x": _clean(fixed["mu"] - 1.959964 * grid), "y": _clean(grid), "name": "95% limits", "dash": "dot"},
                         {"type": "scatter", "mode": "lines", "x": _clean(fixed["mu"] + 1.959964 * grid), "y": _clean(grid), "name": "", "dash": "dot", "showlegend": False}],
              "vlines": [{"x": fixed["mu"], "dash": "dash"}]}
    r.overlay = {"kind": "plot", "plots": [forest, funnel]}
    return r


# =============================================================== robust / quantile regression (XY)
def robust_regression(table, params):
    import statsmodels.api as sm
    require(table.type == "xy", "Robust regression needs an XY table.")
    alpha = _alpha(params)
    q = float(params.get("quantile", 0.5))
    idx = selected(table, params)
    r = Result("Robust and nonparametric regression")
    curves = []
    for i in idx:
        x, y = table.xy_points(i)
        if len(x) < 4:
            r.warn(f"{table.names[i]}: needs at least 4 points.")
            continue
        X = sm.add_constant(x)
        rows = []
        with quiet():
            ols = sm.OLS(y, X).fit()
            ci = ols.conf_int(alpha)
            rows.append(["Least squares (OLS, for reference)", ols.params[1], f"{fmt(ci[1][0])} to {fmt(ci[1][1])}", ols.params[0], "sensitive to outliers"])
            ts = stats.theilslopes(y, x, alpha=1 - alpha)
            rows.append(["Theil-Sen (median of pairwise slopes)", ts.slope, f"{fmt(ts.low_slope)} to {fmt(ts.high_slope)}", ts.intercept, "breakdown 29%; CI from Kendall's tau"])
            ss = stats.siegelslopes(y, x)
            rows.append(["Siegel repeated medians", ss.slope, "", ss.intercept, "breakdown 50%"])
            hub = sm.RLM(y, X, M=sm.robust.norms.HuberT()).fit()
            hc = hub.conf_int(alpha)
            rows.append(["Huber M-estimator (IRLS)", hub.params[1], f"{fmt(hc[1][0])} to {fmt(hc[1][1])}", hub.params[0], "down-weights large residuals"])
            bis = sm.RLM(y, X, M=sm.robust.norms.TukeyBiweight()).fit()
            bc = bis.conf_int(alpha)
            rows.append(["Tukey bisquare M-estimator", bis.params[1], f"{fmt(bc[1][0])} to {fmt(bc[1][1])}", bis.params[0], "ignores gross outliers"])
            qr = sm.QuantReg(y, X).fit(q=q)
            qc = qr.conf_int(alpha)
            rows.append([f"Quantile regression (τ = {fmt(q)}{', LAD/median' if q == 0.5 else ''})", qr.params[1], f"{fmt(qc[1][0])} to {fmt(qc[1][1])}", qr.params[0], "models a percentile of Y instead of the mean"])
        r.table(f"{table.names[i]} (n = {len(x)})", ["Method", "Slope", f"{int(round((1 - alpha) * 100))}% CI of slope", "Intercept", "Notes"], rows)
        w = hub.weights
        if np.any(w < 0.5):
            r.warn(f"{table.names[i]}: {int((w < 0.5).sum())} point(s) received Huber weight < 0.5 (potential outliers).")
        xs = np.linspace(x.min(), x.max(), 60)
        curves.append({"dataset": i, "x": _clean(xs), "y": _clean(ts.intercept + ts.slope * xs), "lo": None, "hi": None, "label": f"Theil-Sen: Y = {fmt(ts.slope)}X + {fmt(ts.intercept)}"})
    r.overlay = {"kind": "curves", "curves": curves, "showBand": False}
    return r


# =============================================================== Mann-Kendall trend + Sen slope
def mann_kendall(x, t=None, alpha=0.05):
    n = len(x)
    if t is None:
        t = np.arange(n, dtype=float)
    S = 0
    for i in range(n - 1):
        S += np.sign(x[i + 1:] - x[i]).sum()
    _, tp = np.unique(x, return_counts=True)
    var = (n * (n - 1) * (2 * n + 5) - (tp * (tp - 1) * (2 * tp + 5)).sum()) / 18
    z = (S - np.sign(S)) / math.sqrt(var) if S != 0 else 0.0
    p = 2 * stats.norm.sf(abs(z))
    slopes = []
    for i in range(n - 1):
        dt = t[i + 1:] - t[i]
        ok = dt != 0
        slopes.extend(((x[i + 1:] - x[i])[ok] / dt[ok]).tolist())
    slopes = np.sort(slopes)
    N = len(slopes)
    med = float(np.median(slopes)) if N else np.nan
    C = stats.norm.ppf(1 - alpha / 2) * math.sqrt(var)
    M1, M2 = int(round((N - C) / 2)), int(round((N + C) / 2)) + 1
    lo = slopes[M1 - 1] if 1 <= M1 <= N else np.nan
    hi = slopes[M2 - 1] if 1 <= M2 <= N else np.nan
    denom = math.sqrt((n * (n - 1) / 2 - (tp * (tp - 1)).sum() / 2) * (n * (n - 1) / 2))
    return {"S": S, "var": var, "z": z, "p": p, "tau": S / denom if denom else np.nan, "slope": med, "lo": lo, "hi": hi,
            "intercept": float(np.median(x - med * t)) if N else np.nan}


def trend_mk(table, params):
    alpha = _alpha(params)
    idx = selected(table, params)
    r = Result("Mann-Kendall trend test with Sen's slope")
    curves = []
    rows = []
    for i in idx:
        if table.type == "xy":
            order = np.argsort(table.x, kind="stable")
            t, v = table.x[order], table.row_means(i)[order]
            m = np.isfinite(t) & np.isfinite(v)
            t, v = t[m], v[m]
        else:
            v = _col(table, i)
            v = v[np.isfinite(v)]
            t = np.arange(1, len(v) + 1, dtype=float)
        if len(v) < 4:
            r.warn(f"{table.names[i]}: needs at least 4 values.")
            continue
        mk = mann_kendall(v, t, alpha)
        rows.append([table.names[i], len(v), mk["S"], mk["tau"], mk["z"], fmt_p(mk["p"]), stars(mk["p"], alpha),
                     "increasing" if mk["p"] < alpha and mk["S"] > 0 else "decreasing" if mk["p"] < alpha else "no significant trend",
                     mk["slope"], f"{fmt(mk['lo'])} to {fmt(mk['hi'])}"])
        if table.type == "xy":
            xs = np.linspace(t.min(), t.max(), 50)
            curves.append({"dataset": i, "x": _clean(xs), "y": _clean(mk["intercept"] + mk["slope"] * xs), "lo": None, "hi": None, "label": f"Sen slope {fmt(mk['slope'])}"})
    require(rows, "No data set had enough values.")
    r.table("Results", ["Data set", "n", "S", "Kendall τ", "Z", "P value", "Summary", "Trend", "Sen's slope", f"{int(round((1 - alpha) * 100))}% CI of slope"], rows)
    r.kv("Notes", [("Assumption", "Observations are independent (no serial correlation). Check with the runs / Ljung-Box tests."),
                   ("Ties", "The variance of S is corrected for tied values.")])
    if curves:
        r.overlay = {"kind": "curves", "curves": curves, "showBand": False}
    return r


# =============================================================== cosinor
def cosinor(table, params):
    require(table.type == "xy", "Cosinor analysis needs an XY table (X = time).")
    alpha = _alpha(params)
    tau = float(params.get("period", 24) or 24)
    H = int(params.get("harmonics", 1) or 1)
    level = 1 - alpha
    idx = selected(table, params)
    r = Result(f"Cosinor analysis (period {fmt(tau)})")
    curves = []
    for i in idx:
        t, y = table.xy_points(i)
        n = len(t)
        p = 1 + 2 * H
        if n <= p + 1:
            r.warn(f"{table.names[i]}: needs more than {p + 1} points.")
            continue
        cols = [np.ones(n)]
        for h in range(1, H + 1):
            cols += [np.cos(2 * math.pi * h * t / tau), np.sin(2 * math.pi * h * t / tau)]
        X = np.column_stack(cols)
        if np.linalg.matrix_rank(X) < p:
            r.warn(f"{table.names[i]}: these time points cannot separate {H} harmonic(s) of period {fmt(tau)} "
                   "(too few different times within one period); use fewer harmonics or check the period.")
            continue
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        fit = X @ beta
        rss = ((y - fit) ** 2).sum()
        tss = ((y - y.mean()) ** 2).sum()
        df = n - p
        s2 = rss / df
        cov = s2 * np.linalg.inv(X.T @ X)
        F = ((tss - rss) / (2 * H)) / s2
        pF = stats.f.sf(F, 2 * H, df)
        tcrit = stats.t.ppf(0.5 + level / 2, df)
        M, seM = beta[0], math.sqrt(cov[0, 0])
        rows = [("Zero-amplitude test (is there a rhythm?)", ""), ("F", F), ("df", f"{2 * H}, {df}"), ("P value", fmt_p(pF)), ("Summary", stars(pF, alpha)),
                ("Percent rhythm (R²)", (1 - rss / tss) * 100),
                ("MESOR (rhythm-adjusted mean)", M), (f"{int(level * 100)}% CI of MESOR", f"{fmt(M - tcrit * seM)} to {fmt(M + tcrit * seM)}")]
        b, g = beta[1], beta[2]
        A = math.hypot(b, g)
        # delta-method SEs (as in the R package 'cosinor')
        vb, vg, cbg = cov[1, 1], cov[2, 2], cov[1, 2]
        seA = math.sqrt((b ** 2 * vb + g ** 2 * vg + 2 * b * g * cbg)) / A
        phi = math.atan2(-g, b)
        sephi = math.sqrt(g ** 2 * vb + b ** 2 * vg - 2 * b * g * cbg) / A ** 2
        peak = (-phi % (2 * math.pi)) * tau / (2 * math.pi)
        rows += [("Amplitude (fundamental)", A), (f"{int(level * 100)}% CI of amplitude (delta method)", f"{fmt(A - tcrit * seA)} to {fmt(A + tcrit * seA)}"),
                 ("Acrophase φ (radians, cos(ωt + φ) convention)", phi),
                 ("Time of peak (acrophase in time units)", peak),
                 (f"{int(level * 100)}% CI of peak time", f"{fmt((peak - tcrit * sephi * tau / (2 * math.pi)) % tau)} to {fmt((peak + tcrit * sephi * tau / (2 * math.pi)) % tau)}"),
                 ("Equation", f"Y = {fmt(M)} + {fmt(A)}·cos(2π(t − {fmt(peak)})/{fmt(tau)})" if H == 1 else f"{H} harmonics")]
        if H > 1:
            for h in range(2, H + 1):
                bh, gh = beta[2 * h - 1], beta[2 * h]
                rows.append((f"Amplitude of harmonic {h} (period {fmt(tau / h)})", math.hypot(bh, gh)))
            ts_ = np.linspace(0, tau, 2000)
            Xs = np.column_stack([np.ones_like(ts_)] + [f(2 * math.pi * h * ts_ / tau) for h in range(1, H + 1) for f in (np.cos, np.sin)])
            ys = Xs @ beta
            rows += [("Global peak time", ts_[np.argmax(ys)]), ("Peak-to-trough amplitude / 2", (ys.max() - ys.min()) / 2)]
        r.kv(f"{table.names[i]} (n = {n})", rows)
        xs = np.linspace(t.min(), t.max(), 200)
        Xs = np.column_stack([np.ones_like(xs)] + [f(2 * math.pi * h * xs / tau) for h in range(1, H + 1) for f in (np.cos, np.sin)])
        curves.append({"dataset": i, "x": _clean(xs), "y": _clean(Xs @ beta), "lo": None, "hi": None, "label": f"cosinor, period {fmt(tau)}"})
    require(r.sections, " ".join(r.warnings) or "No data set had enough points.")
    r.overlay = {"kind": "curves", "curves": curves, "showBand": False}
    return r


# =============================================================== GLM
FAMILIES = {
    "gaussian": ("Gaussian (normal)", ["identity", "log", "inverse_power"]),
    "binomial": ("Binomial (0/1 or proportion)", ["logit", "probit", "cloglog", "log"]),
    "poisson": ("Poisson (counts)", ["log", "identity", "sqrt"]),
    "negbin": ("Negative binomial (over-dispersed counts)", ["log"]),
    "gamma": ("Gamma (positive, skewed)", ["log", "inverse_power", "identity"]),
    "invgauss": ("Inverse Gaussian", ["log", "inverse_squared"]),
}


def _family(name, link):
    import statsmodels.api as sm
    L = sm.families.links
    links = {"identity": L.Identity(), "log": L.Log(), "logit": L.Logit(), "probit": L.Probit(), "cloglog": L.CLogLog(),
             "inverse_power": L.InversePower(), "sqrt": L.Sqrt(), "inverse_squared": L.InverseSquared()}
    lk = links[link]
    return {"gaussian": sm.families.Gaussian, "binomial": sm.families.Binomial, "poisson": sm.families.Poisson,
            "gamma": sm.families.Gamma, "invgauss": sm.families.InverseGaussian}[name](lk)


def _xy(table, params, dep_key="dependent"):
    from .multivariate import _design, _pick, _predictors
    dep = int(_pick(params, dep_key, 0))
    preds = _predictors(table, params, dep)
    y, X, _ = _design(table, dep, preds)
    return y, X, [table.names[j] for j in preds], table.names[dep]


def glm(table, params):
    import statsmodels.api as sm
    y, X, names, yname = _xy(table, params)
    fam = params.get("family", "gaussian")
    require(fam in FAMILIES, "Unknown family.")
    link = params.get("link") or FAMILIES[fam][1][0]
    if link not in FAMILIES[fam][1]:
        link = FAMILIES[fam][1][0]
    alpha = _alpha(params)
    require(len(y) > X.shape[1] + 1, "Not enough complete rows.")
    if fam == "binomial":
        require(np.all((y >= 0) & (y <= 1)), "Binomial outcome must be 0/1 (or a proportion between 0 and 1).")
    if fam in ("poisson", "negbin"):
        require(np.all(y >= 0), "Counts cannot be negative.")
    if fam in ("gamma", "invgauss"):
        require(np.all(y > 0), "This family needs strictly positive values.")
    Xc = sm.add_constant(X, has_constant="add")
    with quiet():
        if fam == "negbin":
            nb = sm.NegativeBinomial(y, Xc).fit(disp=0, maxiter=500)
            a_nb = float(nb.params[-1])
            model = sm.GLM(y, Xc, family=sm.families.NegativeBinomial(alpha=a_nb)).fit()
            null = sm.GLM(y, np.ones((len(y), 1)), family=sm.families.NegativeBinomial(alpha=a_nb)).fit()
        else:
            model = sm.GLM(y, Xc, family=_family(fam, link)).fit()
            null = sm.GLM(y, np.ones((len(y), 1)), family=_family(fam, link)).fit()
    ci = model.conf_int(alpha)
    expo = link in ("log", "logit")
    lab = {"log": "exp(β) = rate/mean ratio", "logit": "exp(β) = odds ratio"}.get(link, "")
    rows = []
    for j, nm in enumerate(["Intercept"] + names):
        row = [nm, model.params[j], model.bse[j], f"{fmt(ci[j][0])} to {fmt(ci[j][1])}", model.tvalues[j], fmt_p(model.pvalues[j]), stars(model.pvalues[j], alpha)]
        if expo:
            row += [math.exp(model.params[j]), f"{fmt(math.exp(ci[j][0]))} to {fmt(math.exp(ci[j][1]))}"]
        rows.append(row)
    r = Result(f"Generalized linear model: {yname} — {FAMILIES[fam][0]}, {link} link")
    cols = ["Variable", "Estimate β", "SE", f"{int(round((1 - alpha) * 100))}% CI (Wald)", "z", "P value", "Summary"] + ([lab, "CI of exp(β)"] if expo else [])
    r.table("Coefficients", cols, rows)
    lr = null.deviance - model.deviance
    dfm = X.shape[1]
    pear = float((model.resid_pearson ** 2).sum())
    out = [("Observations", int(model.nobs)), ("Deviance", model.deviance), ("Residual df", model.df_resid), ("Null deviance", null.deviance),
           ("Likelihood-ratio χ² vs. intercept-only", lr), ("df", dfm), ("P value", fmt_p(stats.chi2.sf(lr, dfm))),
           ("Pearson χ²", pear), ("Dispersion (Pearson χ² / df)", pear / model.df_resid if model.df_resid else np.nan),
           ("Log-likelihood", model.llf), ("AIC", model.aic), ("BIC", model.bic_llf if hasattr(model, "bic_llf") else np.nan),
           ("Pseudo R² (McFadden)", 1 - model.llf / null.llf if null.llf else np.nan)]
    if fam == "negbin":
        out.insert(1, ("Negative binomial α (over-dispersion, MLE)", a_nb))
    r.kv("Model fit", out)
    if fam == "poisson" and model.df_resid and pear / model.df_resid > 1.5:
        r.warn("The data are over-dispersed (Pearson χ²/df > 1.5): standard errors are too small. Consider the negative binomial family.")
    return r


def ordinal(table, params):
    from statsmodels.miscmodels.ordinal_model import OrderedModel
    y, X, names, yname = _xy(table, params)
    alpha = _alpha(params)
    distr = params.get("distr", "logit")
    cats = np.unique(y)
    require(3 <= len(cats) <= 30, "The outcome must have 3–30 ordered categories (use logistic regression for two).")
    import pandas as pd
    yc = pd.Series(pd.Categorical(y, categories=cats, ordered=True))
    with quiet():
        model = OrderedModel(yc, X, distr=distr).fit(method="bfgs", disp=False, maxiter=2000)
    ci = model.conf_int(alpha)
    ci = np.asarray(ci)
    p = len(names)
    rows = []
    for j, nm in enumerate(names):
        row = [nm, model.params.iloc[j], model.bse.iloc[j], f"{fmt(ci[j][0])} to {fmt(ci[j][1])}", model.tvalues.iloc[j], fmt_p(model.pvalues.iloc[j]), stars(model.pvalues.iloc[j], alpha)]
        if distr == "logit":
            row += [math.exp(model.params.iloc[j]), f"{fmt(math.exp(ci[j][0]))} to {fmt(math.exp(ci[j][1]))}"]
        rows.append(row)
    r = Result(f"Ordinal regression ({'proportional odds, logit' if distr == 'logit' else 'probit'}): {yname}")
    r.table("Coefficients", ["Variable", "Estimate", "SE", "CI", "z", "P value", "Summary"] + (["Odds ratio", "CI of OR"] if distr == "logit" else []), rows)
    th = model.model.transform_threshold_params(model.params.values)
    r.table("Thresholds (cut points between categories)", ["Between", "Threshold"],
            [[f"{fmt(cats[j])} | {fmt(cats[j + 1])}", th[j + 1]] for j in range(len(cats) - 1)])
    ll0 = _ordinal_null_ll(y, cats)
    lr = 2 * (model.llf - ll0)
    r.kv("Model fit", [("Observations", len(y)), ("Categories", len(cats)), ("Log-likelihood", model.llf), ("AIC", model.aic),
                       ("Likelihood-ratio χ² vs. thresholds only", lr), ("df", p), ("P value", fmt_p(stats.chi2.sf(lr, p))),
                       ("Pseudo R² (McFadden)", 1 - model.llf / ll0)])
    return r


def _ordinal_null_ll(y, cats):
    counts = np.array([(y == c).sum() for c in cats], float)
    return float((counts * np.log(counts / counts.sum())).sum())


# =============================================================== regression diagnostics
def regression_diagnostics(table, params):
    import statsmodels.api as sm
    from statsmodels.stats import diagnostic as dg
    from statsmodels.stats.outliers_influence import OLSInfluence, variance_inflation_factor
    from statsmodels.stats.stattools import durbin_watson, jarque_bera
    y, X, names, yname = _xy(table, params)
    alpha = _alpha(params)
    require(len(y) > X.shape[1] + 2, "Not enough complete rows.")
    Xc = sm.add_constant(X, has_constant="add")
    with quiet():
        m = sm.OLS(y, Xc).fit()
    r = Result(f"Regression diagnostics: {yname}")
    rows = []
    bp = dg.het_breuschpagan(m.resid, Xc)
    rows.append(_row("Breusch-Pagan (heteroscedasticity)", bp[0], X.shape[1], bp[1], alpha, "H0: constant variance (studentized, Koenker)"))
    try:
        wt = dg.het_white(m.resid, Xc)
        rows.append(_row("White (heteroscedasticity, general)", wt[0], "", wt[1], alpha, "H0: constant variance"))
    except Exception:  # noqa: BLE001
        pass
    try:
        rs = dg.linear_reset(m, power=3, use_f=True)
        rows.append(_row("Ramsey RESET (functional form)", float(rs.fvalue), f"{int(rs.df_num)}, {int(rs.df_denom)}", float(rs.pvalue), alpha, "H0: no omitted nonlinearity"))
    except Exception:  # noqa: BLE001
        pass
    jb, pjb, sk, ku = jarque_bera(m.resid)
    rows.append(_row("Jarque-Bera (normality of residuals)", jb, 2, pjb, alpha, f"skewness {fmt(sk)}, kurtosis {fmt(ku)}"))
    sw = stats.shapiro(m.resid)
    rows.append(_row("Shapiro-Wilk (normality of residuals)", sw.statistic, "", sw.pvalue, alpha, ""))
    dw = durbin_watson(m.resid)
    rows.append(["Durbin-Watson (autocorrelation, in row order)", fmt(dw), "", "", "", "≈2 none; <1.5 positive; >2.5 negative"])
    try:
        rb = dg.acorr_breusch_godfrey(m, nlags=1)
        rows.append(_row("Breusch-Godfrey (lag 1 autocorrelation)", rb[0], 1, rb[1], alpha, ""))
    except Exception:  # noqa: BLE001
        pass
    r.table("Assumption tests", TEST_COLS, rows)
    if X.shape[1] > 1:
        vifs = [variance_inflation_factor(Xc, j) for j in range(1, Xc.shape[1])]
        r.table("Multicollinearity", ["Variable", "VIF", "Tolerance (1/VIF)", "Assessment"],
                [[nm, v, 1 / v, "OK" if v < 5 else "moderate" if v < 10 else "severe"] for nm, v in zip(names, vifs)])
    r.kv("Model", [("R²", m.rsquared), ("Adjusted R²", m.rsquared_adj), ("Condition number", float(np.linalg.cond(Xc))),
                   ("Observations", int(m.nobs))])
    inf = OLSInfluence(m)
    cook = inf.cooks_distance[0]
    lev = inf.hat_matrix_diag
    sr = inf.resid_studentized_external
    n, p = Xc.shape
    flag = np.where((cook > 4 / n) | (lev > 2 * p / n) | (np.abs(sr) > 3))[0]
    r.table("Influential or unusual observations (Cook's D > 4/n, leverage > 2p/n, or |studentized residual| > 3)",
            ["Row (complete cases)", "Y", "Fitted", "Studentized residual", "Leverage", "Cook's distance", "DFFITS"],
            [[int(j) + 1, y[j], m.fittedvalues[j], sr[j], lev[j], cook[j], inf.dffits[0][j]] for j in flag] or [["none", "", "", "", "", "", ""]])
    qq = stats.probplot(m.resid, dist="norm")
    r.overlay = {"kind": "plot", "plots": [
        {"title": "Residuals vs. fitted", "xTitle": "Fitted", "yTitle": "Residual", "traces": [{"type": "scatter", "mode": "markers", "x": _clean(m.fittedvalues), "y": _clean(m.resid), "name": "residuals"}], "hlines": [{"y": 0, "dash": "dot"}]},
        {"title": "Normal Q-Q of residuals", "xTitle": "Theoretical quantile", "yTitle": "Residual", "traces": [
            {"type": "scatter", "mode": "markers", "x": _clean(qq[0][0]), "y": _clean(qq[0][1]), "name": "residuals"},
            {"type": "scatter", "mode": "lines", "x": _clean(qq[0][0]), "y": _clean(qq[1][1] + qq[1][0] * qq[0][0]), "name": "reference", "dash": "dot"}]},
        {"title": "Cook's distance", "xTitle": "Observation", "yTitle": "Cook's D", "traces": [{"type": "bar", "x": list(range(1, n + 1)), "y": _clean(cook), "name": "Cook's D"}], "hlines": [{"y": 4 / n, "dash": "dot", "label": "4/n"}]}]}
    return r


# =============================================================== MANOVA
def manova(table, params):
    import pandas as pd
    from statsmodels.multivariate.manova import MANOVA
    alpha = _alpha(params)
    g = int(params.get("group", 0))
    deps = [int(d) for d in (params.get("dependents") or []) if int(d) != g]
    if not deps:
        deps = [i for i in range(len(table.Y)) if i != g]
    require(len(deps) >= 2, "Choose at least two dependent variables.")
    M = np.column_stack([_col(table, g)] + [_col(table, d) for d in deps])
    M = M[np.all(np.isfinite(M), axis=1)]
    grp = M[:, 0]
    levels = np.unique(grp)
    require(len(levels) >= 2, "The grouping variable needs at least two different codes.")
    df = pd.DataFrame(M[:, 1:], columns=[f"y{j}" for j in range(len(deps))])
    df["g"] = [f"g{fmt(v)}" for v in grp]
    with quiet():
        mv = MANOVA.from_formula(" + ".join(df.columns[:-1]) + " ~ g", data=df).mv_test()
    tab = mv.results["g"]["stat"]
    r = Result("MANOVA (one-way)")
    rows = []
    for test in ["Wilks' lambda", "Pillai's trace", "Hotelling-Lawley trace", "Roy's greatest root"]:
        rr = tab.loc[test]
        p = float(rr["Pr > F"])
        rows.append([test, float(rr["Value"]), float(rr["F Value"]), f"{fmt(float(rr['Num DF']))}, {fmt(float(rr['Den DF']))}", fmt_p(p), stars(p, alpha)])
    r.table(f"Multivariate tests: {len(levels)} groups (codes in '{table.names[g]}'), {len(deps)} dependent variables",
            ["Test", "Value", "Approx. F", "df", "P value", "Summary"], rows)
    if len(levels) == 2:
        A, B = M[grp == levels[0], 1:], M[grp == levels[1], 1:]
        n1, n2, p = len(A), len(B), A.shape[1]
        S = ((n1 - 1) * np.cov(A, rowvar=False) + (n2 - 1) * np.cov(B, rowvar=False)) / (n1 + n2 - 2)
        d = A.mean(0) - B.mean(0)
        T2 = n1 * n2 / (n1 + n2) * d @ np.linalg.solve(S, d)
        F = (n1 + n2 - p - 1) / (p * (n1 + n2 - 2)) * T2
        pv = stats.f.sf(F, p, n1 + n2 - p - 1)
        r.kv("Hotelling's T² (two groups)", [("T²", T2), ("F", F), ("df", f"{p}, {n1 + n2 - p - 1}"), ("P value", fmt_p(pv)),
                                             ("Mahalanobis distance D", math.sqrt(d @ np.linalg.solve(S, d)))])
    uni = []
    for j, dd in enumerate(deps):
        F, p = stats.f_oneway(*[M[grp == lv, j + 1] for lv in levels])
        uni.append([table.names[dd], F, fmt_p(p), stars(p, alpha)])
    r.table("Follow-up univariate one-way ANOVAs (not adjusted)", ["Variable", "F", "P value", "Summary"], uni)
    r.table("Group means", ["Group code", "n"] + [table.names[d] for d in deps],
            [[fmt(lv), int((grp == lv).sum())] + list(M[grp == lv, 1:].mean(0)) for lv in levels])
    try:
        boxm = _box_m([M[grp == lv, 1:] for lv in levels])
        r.kv("Box's M test (equal covariance matrices)", [("M", boxm[0]), ("Chi-square", boxm[1]), ("df", boxm[2]), ("P value", fmt_p(boxm[3])),
                                                          ("Note", "very sensitive; Pillai's trace is robust when this fails")])
    except Exception:  # noqa: BLE001
        pass
    return r


def _box_m(groups_):
    k = len(groups_)
    p = groups_[0].shape[1]
    ns = np.array([len(x) for x in groups_])
    covs = [np.cov(x, rowvar=False) for x in groups_]
    N = ns.sum()
    Sp = sum((n - 1) * c for n, c in zip(ns, covs)) / (N - k)
    M = (N - k) * np.log(np.linalg.det(Sp)) - sum((n - 1) * np.log(np.linalg.det(c)) for n, c in zip(ns, covs))
    c1 = ((1 / (ns - 1)).sum() - 1 / (N - k)) * (2 * p ** 2 + 3 * p - 1) / (6 * (p + 1) * (k - 1))
    chi = M * (1 - c1)
    df = p * (p + 1) * (k - 1) / 2
    return M, chi, df, float(stats.chi2.sf(chi, df))


# =============================================================== partial correlation
def partial_correlation(table, params):
    alpha = _alpha(params)
    idx = selected(table, params)
    require(len(idx) >= 3, "Select at least three variables.")
    M = np.column_stack([_col(table, i) for i in idx])
    M = M[np.all(np.isfinite(M), axis=1)]
    n, k = M.shape
    require(n > k + 1, "Not enough complete rows.")
    method = params.get("method", "pearson")
    if method == "spearman":
        M = np.apply_along_axis(stats.rankdata, 0, M)
    P = np.linalg.inv(np.corrcoef(M, rowvar=False))
    D = np.sqrt(np.diag(P))
    R = -P / np.outer(D, D)
    np.fill_diagonal(R, 1)
    g = k - 2
    names = [table.names[i] for i in idx]
    rows = []
    for a, b in itertools.combinations(range(k), 2):
        rr = R[a, b]
        dfree = n - 2 - g
        t = rr * math.sqrt(dfree / (1 - rr ** 2)) if abs(rr) < 1 else np.inf
        p = 2 * stats.t.sf(abs(t), dfree)
        zc = stats.norm.ppf(1 - alpha / 2) / math.sqrt(n - g - 3) if n - g - 3 > 0 else np.nan
        z = math.atanh(max(min(rr, 0.999999), -0.999999))
        rows.append([f"{names[a]} – {names[b]}", np.corrcoef(M[:, a], M[:, b])[0, 1], rr, f"{fmt(math.tanh(z - zc))} to {fmt(math.tanh(z + zc))}", t, dfree, fmt_p(p), stars(p, alpha)])
    r = Result(f"Partial correlation ({'Pearson' if method == 'pearson' else 'Spearman'}; each pair controlled for all other variables)")
    r.table(f"n = {n} complete rows", ["Pair", "Ordinary r", "Partial r", f"{int(round((1 - alpha) * 100))}% CI", "t", "df", "P value", "Summary"], rows)
    r.table("Partial correlation matrix", [""] + names, [[names[a]] + list(R[a]) for a in range(k)])
    return r


# =============================================================== cluster analysis
def _kmeans(X, k, n_init=25, seed=SEED):
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(n_init):
        C = [X[rng.integers(len(X))]]
        for _j in range(1, k):
            d2 = np.min(((X[:, None, :] - np.array(C)[None]) ** 2).sum(-1), axis=1)
            C.append(X[rng.choice(len(X), p=d2 / d2.sum())] if d2.sum() > 0 else X[rng.integers(len(X))])
        C = np.array(C)
        for _it in range(300):
            lab = np.argmin(((X[:, None, :] - C[None]) ** 2).sum(-1), axis=1)
            newC = np.array([X[lab == j].mean(0) if np.any(lab == j) else C[j] for j in range(k)])
            if np.allclose(newC, C):
                break
            C = newC
        wss = sum(((X[lab == j] - C[j]) ** 2).sum() for j in range(k))
        if best is None or wss < best[0] - 1e-12:
            best = (wss, lab.copy(), C.copy())
    return best


def _silhouette(X, lab):
    from scipy.spatial.distance import cdist
    D = cdist(X, X)
    s = np.zeros(len(X))
    for i in range(len(X)):
        same = lab == lab[i]
        if same.sum() <= 1:
            continue
        a = D[i, same].sum() / (same.sum() - 1)
        b = min(D[i, lab == c].mean() for c in np.unique(lab) if c != lab[i])
        s[i] = (b - a) / max(a, b)
    return s


def cluster(table, params):
    from scipy.cluster.hierarchy import dendrogram, fcluster, linkage
    idx = selected(table, params)
    require(len(idx) >= 1, "Select variables.")
    M = np.column_stack([_col(table, i) for i in idx])
    keep = np.all(np.isfinite(M), axis=1)
    X = M[keep]
    labels = [lab for lab, kk in zip(table.row_labels, keep) if kk]
    require(len(X) >= 3, "Need at least three complete rows (observations).")
    if params.get("standardize", True):
        sd = X.std(0, ddof=1)
        X = (X - X.mean(0)) / np.where(sd > 0, sd, 1)
    k = int(params.get("k", 3) or 3)
    require(2 <= k < len(X), "Number of clusters must be between 2 and the number of rows − 1.")
    method = params.get("method", "ward")
    r = Result("Cluster analysis")
    plots = []
    if method == "kmeans":
        wss, lab, C = _kmeans(X, k)
        title = f"k-means (k = {k}, 25 k-means++ starts, fixed seed)"
    else:
        Z = linkage(X, method=method)
        lab = fcluster(Z, k, criterion="maxclust") - 1
        title = f"Hierarchical clustering ({method} linkage, Euclidean distance), cut into {k} clusters"
        dn = dendrogram(Z, no_plot=True, labels=labels)
        traces = [{"type": "scatter", "mode": "lines", "x": list(map(float, xs)), "y": list(map(float, ys)), "name": "", "showlegend": False, "color": "#444"}
                  for xs, ys in zip(dn["icoord"], dn["dcoord"])]
        plots.append({"title": "Dendrogram", "xTitle": "", "yTitle": "Distance", "traces": traces,
                      "xTicks": {"vals": [5 + 10 * j for j in range(len(dn["ivl"]))], "text": list(dn["ivl"])}})
        r.table("Merge heights (agglomeration schedule, last 10)", ["Step", "Cluster A", "Cluster B", "Distance", "Size"],
                [[j + 1, int(a), int(b), d, int(s)] for j, (a, b, d, s) in enumerate(Z)][-10:])
    sil = _silhouette(X, lab)
    tot = ((X - X.mean(0)) ** 2).sum()
    wss = sum(((X[lab == j] - X[lab == j].mean(0)) ** 2).sum() for j in np.unique(lab))
    nk = len(np.unique(lab))
    ch = ((tot - wss) / (nk - 1)) / (wss / (len(X) - nk)) if nk > 1 and wss > 0 else np.nan
    r.kv(title, [("Observations", len(X)), ("Variables", len(idx)), ("Standardized", "yes" if params.get("standardize", True) else "no"),
                 ("Mean silhouette width (−1…1, higher = better separated)", sil.mean()),
                 ("Between-cluster SS / total SS", (tot - wss) / tot if tot else np.nan), ("Calinski-Harabasz index", ch)])
    r.table("Cluster sizes and means (original units)", ["Cluster", "n", "Mean silhouette"] + [table.names[i] for i in idx],
            [[j + 1, int((lab == j).sum()), sil[lab == j].mean()] + list(M[keep][lab == j].mean(0)) for j in np.unique(lab)])
    r.table("Membership", ["Row", "Cluster", "Silhouette"], [[lb, int(c) + 1, s] for lb, c, s in zip(labels, lab, sil)])
    if X.shape[1] >= 2:
        U, S, Vt = np.linalg.svd(X - X.mean(0), full_matrices=False)
        sc = U * S
        plots.append({"title": "Clusters on the first two principal components", "xTitle": "PC1", "yTitle": "PC2",
                      "traces": [{"type": "scatter", "mode": "markers", "x": _clean(sc[lab == j, 0]), "y": _clean(sc[lab == j, 1]), "name": f"Cluster {j + 1}",
                                  "text": [lb for lb, c in zip(labels, lab) if c == j]} for j in np.unique(lab)]})
    r.overlay = {"kind": "plot", "plots": plots}
    return r


# =============================================================== nonparametric two-way ANOVA
def two_way_np(table, params):
    import pandas as pd
    import statsmodels.formula.api as smf
    from statsmodels.stats.anova import anova_lm
    alpha = _alpha(params)
    idx = selected(table, params)
    recs = []
    for ci in idx:
        for ri in range(table.nrows):
            for v in table.Y[ci][ri]:
                if np.isfinite(v):
                    recs.append({"y": v, "B": f"c{ci}", "A": f"r{ri}"})
    df = pd.DataFrame(recs)
    require(len(df) > 0 and df["A"].nunique() >= 2 and df["B"].nunique() >= 2, "Need at least two rows and two data sets.")
    require(df.groupby(["A", "B"]).size().min() >= 2, "Every cell needs at least two replicates.")
    form = "y ~ C(A, Sum) * C(B, Sum)"
    keys = [("C(A, Sum)", "Row factor"), ("C(B, Sum)", "Column factor"), ("C(A, Sum):C(B, Sum)", "Interaction")]
    r = Result("Nonparametric two-way ANOVA")
    # Aligned rank transform (Wobbrock et al. 2011)
    cell = df.groupby(["A", "B"])["y"].transform("mean")
    resid = df["y"] - cell
    gm = df["y"].mean()
    mA = df.groupby("A")["y"].transform("mean") - gm
    mB = df.groupby("B")["y"].transform("mean") - gm
    inter = cell - df.groupby("A")["y"].transform("mean") - df.groupby("B")["y"].transform("mean") + gm
    rows = []
    with quiet():
        for (key, lab), eff in zip(keys, [mA, mB, inter]):
            d2 = df.copy()
            # aligned values are computed; values that are equal in exact arithmetic can differ by one
            # unit in the last place, so they are rounded to 12 significant digits before ranking (ties stay ties)
            al = (resid + eff).to_numpy()
            d2["y"] = stats.rankdata(np.array([float(f"{v:.12g}") for v in al]))
            tab = anova_lm(smf.ols(form, data=d2).fit(), typ=3)
            rr = tab.loc[key]
            rows.append([lab, f"F ({int(rr['df'])}, {int(tab.loc['Residual', 'df'])}) = {fmt(rr['F'])}", fmt_p(rr["PR(>F)"]), stars(rr["PR(>F)"], alpha), sig(rr["PR(>F)"], alpha)])
    r.table("Aligned rank transform (ART) ANOVA", ["Source", "F (DFn, DFd)", "P value", "Summary", "Significant?"], rows)
    d3 = df.copy()
    d3["y"] = stats.rankdata(df["y"])
    with quiet():
        tab = anova_lm(smf.ols(form, data=d3).fit(), typ=2)
    ms_total = ((d3["y"] - d3["y"].mean()) ** 2).sum() / (len(d3) - 1)
    rows = []
    for key, lab in keys:
        Hs = tab.loc[key, "sum_sq"] / ms_total
        dfk = int(tab.loc[key, "df"])
        p = stats.chi2.sf(Hs, dfk)
        rows.append([lab, Hs, dfk, fmt_p(p), stars(p, alpha)])
    r.table("Scheirer-Ray-Hare test (rank-based extension of Kruskal-Wallis)", ["Source", "H", "df", "P value", "Summary"], rows)
    r.kv("Which one?", [("ART ANOVA", "recommended: valid for interactions, any design with replicates"),
                        ("Scheirer-Ray-Hare", "classic but low power; interaction test is unreliable")])
    return r


# =============================================================== polynomial regression (exact)
def polynomial(table, params):
    """Polynomial regression solved exactly (decimal input, 80-digit arithmetic)."""
    from decimal import localcontext

    from .precise import PREC, exact_ols, to_dec
    require(table.type == "xy", "Polynomial regression needs an XY table.")
    order = int(params.get("order", 2) or 2)
    require(1 <= order <= 10, "Order must be between 1 and 10.")
    alpha = _alpha(params)
    level = 1 - alpha
    idx = selected(table, params)
    r = Result(f"Polynomial regression (order {order})")
    curves = []
    cols = {f"B{j}" + (" (intercept)" if j == 0 else f" (X^{j})" if j > 1 else " (X)"): [] for j in range(order + 1)}
    out_rows = {k: [] for k in ["Degrees of freedom", "R squared", "Adjusted R squared", "Sum of squares", "Sy.x", "F (vs. horizontal line)", "P value",
                                f"Extra SS F test vs. order {order - 1}", "P value (higher order needed?)", "AICc", "Number of points"]}
    names = []
    for i in idx:
        xd, yd, xf, yf = [], [], [], []
        for rr in range(table.nrows):
            if not np.isfinite(table.x[rr]):
                continue
            for k in range(table.Y[i].shape[1]):
                v = table.Y[i][rr, k]
                if np.isfinite(v):
                    xd.append(to_dec(table.x_raw[rr] if rr < len(table.x_raw) else "", table.x[rr]))
                    yd.append(to_dec(table.raw[i][rr, k], v))
                    xf.append(float(table.x[rr]))
                    yf.append(float(v))
        n = len(yd)
        if n <= order + 1:
            r.warn(f"{table.names[i]}: needs more than {order + 1} points.")
            continue
        if len(set(xf)) <= order:
            r.warn(f"{table.names[i]}: a polynomial of order {order} needs at least {order + 1} different X values "
                   f"(there are {len(set(xf))}); choose a lower order.")
            continue
        with localcontext() as ctx:
            ctx.prec = PREC
            X = [[x ** j for j in range(1, order + 1)] for x in xd]
            fit = exact_ols(yd, X)
            fit0 = exact_ols(yd, [row[:-1] for row in X]) if order > 1 else None
        names.append(table.names[i])
        q = stats.t.ppf(0.5 + level / 2, fit["df"])
        for j, key in enumerate(cols):
            b, s = fit["beta"][j], fit["se"][j]
            cols[key].append(f"{fmt(b)} ± {fmt(s)} (CI {fmt(b - q * s)} to {fmt(b + q * s)})")
        p = order + 1
        F = ((fit["tss"] - fit["rss"]) / order) / (fit["rss"] / fit["df"])
        aicc = n * math.log(fit["rss"] / n) + 2 * p + 2 * p * (p + 1) / (n - p - 1) if n - p - 1 > 0 and fit["rss"] > 0 else np.nan
        vals = [fit["df"], fit["r2"], 1 - (1 - fit["r2"]) * (n - 1) / fit["df"], fit["rss"], fit["sy_x"], F, fmt_p(stats.f.sf(F, order, fit["df"]))]
        if fit0:
            Fe = (fit0["rss"] - fit["rss"]) / (fit["rss"] / fit["df"])
            vals += [Fe, fmt_p(stats.f.sf(Fe, 1, fit["df"]))]
        else:
            vals += ["", ""]
        vals += [aicc, n]
        for key, v in zip(out_rows, vals):
            out_rows[key].append(v)
        xs = np.linspace(min(xf), max(xf), 120)
        Xs = np.column_stack([xs ** j for j in range(order + 1)])
        yc = Xs @ fit["beta"]
        h = q * np.sqrt(np.clip(np.einsum("ij,jk,ik->i", Xs, fit["cov"], Xs), 0, None))
        curves.append({"dataset": i, "x": _clean(xs), "y": _clean(yc), "lo": _clean(yc - h), "hi": _clean(yc + h),
                       "label": f"order {order}, R² = {fit['r2']:.4f}"})
    require(names, " ".join(r.warnings) or "No data set had enough points.")
    r.table(f"Coefficients (estimate ± SE, {int(round(level * 100))}% CI)", [""] + names, [[k] + v for k, v in cols.items()])
    r.table("Goodness of fit", [""] + names, [[k] + v for k, v in out_rows.items()])
    r.kv("Method", [("Computation", "exact least squares from the decimal data (80-digit arithmetic)"),
                    ("Why it matters", "high-order polynomials are numerically ill-conditioned; ordinary double-precision fits can lose all digits"),
                    ("Choosing the order", "use the lowest order for which the extra-SS F test of the next order is not significant, or the smallest AICc")])
    r.overlay = {"kind": "curves", "curves": curves, "showBand": bool(params.get("plotBand", False))}
    return r


# =============================================================== general linear mixed model
def mixed_model(table, params):
    """Linear mixed-effects model with random intercepts and optional random slope (statsmodels MixedLM)."""
    import pandas as pd
    import statsmodels.formula.api as smf
    alpha = _alpha(params)
    dep = int(params.get("dependent", 0))
    require(0 <= dep < len(table.Y), "Choose the dependent variable.")
    grp = int(params.get("group", 1))
    fixed = [int(v) for v in (params.get("fixed") or []) if int(v) not in (dep, grp)]
    if not fixed:  # like the other regression analyses: default to every other variable
        fixed = [i for i in range(len(table.Y)) if i not in (dep, grp)]
    factors = {int(v) for v in (params.get("factors") or [])}
    slope = params.get("randomSlope")
    slope = int(slope) if slope not in (None, "", "none") else None
    method = params.get("method", "reml")
    require(fixed, "Choose at least one fixed-effect variable.")
    names = {i: f"v{i}" for i in [dep, grp, *fixed]}
    cols = {names[i]: _col(table, i) for i in names}
    df = pd.DataFrame(cols).dropna()
    require(len(df) >= len(fixed) + 4, "Not enough complete rows.")
    df[names[grp]] = df[names[grp]].astype(str)
    require(df[names[grp]].nunique() >= 3, "The grouping (subject) variable needs at least 3 different values.")
    terms = [f"C({names[i]})" if i in factors else names[i] for i in fixed]
    formula = f"{names[dep]} ~ " + " + ".join(terms)
    re_formula = f"~{names[slope]}" if slope is not None and slope in fixed and slope not in factors else None
    reml = method != "ml"
    with quiet():
        md = smf.mixedlm(formula, df, groups=df[names[grp]], re_formula=re_formula)
        fit = md.fit(reml=reml, method=["lbfgs", "bfgs", "powell"], maxiter=2000)
    label = {f"v{i}": table.names[i] for i in names}

    def nice(term):
        out = term
        for k in sorted(label, key=len, reverse=True):
            out = out.replace(f"C({k})[T.", f"{label[k]} = ").replace(k, label[k])
        return out.replace("]", "")
    r = Result(f"Linear mixed-effects model: {table.names[dep]}")
    z = stats.norm.ppf(1 - alpha / 2)
    fe = fit.fe_params
    # GLS covariance of the fixed effects given the variance components, (Σ Xᵢ'Vᵢ⁻¹Xᵢ)⁻¹,
    # the convention of nlme, lme4 and SAS (statsmodels' default uses the joint information matrix)
    q = np.asarray(fit.cov_re).shape[0]
    beta = np.asarray(fe, float)
    use_satt = params.get("ddf", "satterthwaite") == "satterthwaite"
    try:
        C, test = satterthwaite(md, fit, reml, q)
    except Exception:  # noqa: BLE001  (fall back to large-sample tests)
        C, test, use_satt = None, None, False
    if C is None:
        G = np.asarray(fit.cov_re, float)
        A = sum(Xi.T @ np.linalg.solve(Zi @ G @ Zi.T + float(fit.scale) * np.eye(len(Xi)), Xi) for Xi, Zi in zip(md.exog_li, md.exog_re_li))
        C = np.linalg.inv(A)
    se_fe = np.sqrt(np.diag(C))
    rows = []
    pct = f"{int(round((1 - alpha) * 100))}%"
    for j, term in enumerate(fe.index):
        b, se = float(fe[term]), float(se_fe[j])
        if use_satt:
            tval, ddf_j = test(np.eye(len(beta))[j], beta)
            p = float(2 * stats.t.sf(abs(tval), ddf_j))
            crit = stats.t.ppf(1 - alpha / 2, ddf_j)
        else:
            ddf_j, p, crit = np.inf, float(2 * stats.norm.sf(abs(b / se))), z
        rows.append([nice(term), b, se, ddf_j, f"{fmt(b - crit * se)} to {fmt(b + crit * se)}", b / se, fmt_p(p), stars(p, alpha)])
    r.table("Fixed effects" + (" (t tests with Satterthwaite degrees of freedom)" if use_satt else " (large-sample z tests)"),
            ["Term", "Estimate", "SE", "df", f"{pct} CI", "t" if use_satt else "z", "P value", "Summary"], rows)
    # F test per term (factors with several levels: Satterthwaite multi-df test, Fai & Cornelius 1996)
    if use_satt:
        frows = []
        for i in fixed:
            key = f"C({names[i]})" if i in factors else names[i]
            cols_ = [j for j, term in enumerate(fe.index) if term == key or term.startswith(key + "[")]
            if not cols_:
                continue
            L = np.eye(len(beta))[cols_]
            F, ddf = test(L, beta) if len(cols_) > 1 else (test(L[0], beta)[0] ** 2, test(L[0], beta)[1])
            pF = float(stats.f.sf(F, len(cols_), ddf))
            frows.append([table.names[i], F, len(cols_), ddf, fmt_p(pF), stars(pF, alpha)])
        r.table("Tests of fixed effects (F, Satterthwaite denominator df)", ["Term", "F", "Num df", "Den df", "P value", "Summary"], frows)
    cov = fit.cov_re
    vc = [("Groups (subjects)", int(df[names[grp]].nunique())), ("Observations", len(df)),
          ("SD of random intercepts", math.sqrt(max(float(cov.iloc[0, 0]), 0)))]
    if re_formula:
        sd_s = math.sqrt(max(float(cov.iloc[1, 1]), 0))
        corr = float(cov.iloc[0, 1]) / (math.sqrt(float(cov.iloc[0, 0])) * sd_s) if sd_s > 0 and cov.iloc[0, 0] > 0 else np.nan
        vc += [(f"SD of random slopes ({table.names[slope]})", sd_s), ("Correlation intercept–slope", corr)]
    vc += [("Residual SD", math.sqrt(float(fit.scale)))]
    if not re_formula:
        var_u = float(cov.iloc[0, 0])
        vc.append(("Intraclass correlation", var_u / (var_u + float(fit.scale))))
    vc += [("Estimation", "REML" if reml else "maximum likelihood"), ("Log likelihood", float(fit.llf))]
    if not reml:
        k = len(fe) + (3 if re_formula else 1) + 1
        vc += [("AIC", -2 * fit.llf + 2 * k), ("BIC", -2 * fit.llf + k * math.log(len(df)))]
    vc.append(("Converged", "yes" if fit.converged else "no — interpret with caution"))
    r.kv("Random effects and fit", vc)
    if re_formula:
        with quiet():
            f0 = smf.mixedlm(formula, df, groups=df[names[grp]]).fit(reml=reml, method=["lbfgs", "bfgs", "powell"], maxiter=2000)
        lr = max(0.0, 2 * (fit.llf - f0.llf))
        p = 0.5 * stats.chi2.sf(lr, 1) + 0.5 * stats.chi2.sf(lr, 2)
        r.kv("Is the random slope needed? (likelihood-ratio test)", [
            ("χ² (random intercept + slope vs. intercept only)", lr), ("P value (50:50 mixture of χ²₁ and χ²₂)", fmt_p(p)), ("Summary", stars(p, alpha)),
            ("Interpretation", "Significant: subjects differ in how strongly they respond to " + table.names[slope] + "." if p < alpha
             else "Not significant: a random-intercept model is adequate.")])
    if not fit.converged:
        r.warn("The optimizer did not fully converge. Try maximum likelihood, rescale predictors, or drop the random slope.")
    return r


# =============================================================== Satterthwaite degrees of freedom
class _MixedLik:
    """REML / ML log-likelihood of a linear mixed model as a function of its variance
    parameters θ = (unique elements of G, σ²), for Satterthwaite's approximation."""

    def __init__(self, md, reml, q):
        self.X = md.exog_li
        self.Z = md.exog_re_li
        self.y = md.endog_li
        self.reml = reml
        self.q = q
        self.idx = [(i, j) for i in range(q) for j in range(i, q)]

    def unpack(self, th):
        G = np.zeros((self.q, self.q))
        for v, (i, j) in zip(th[:-1], self.idx):
            G[i, j] = G[j, i] = v
        return G, th[-1]

    def parts(self, th):
        G, s2 = self.unpack(th)
        p = self.X[0].shape[1]
        A = np.zeros((p, p))
        b = np.zeros(p)
        logdet = 0.0
        cache = []
        for Xi, Zi, yi in zip(self.X, self.Z, self.y):
            Vi = Zi @ G @ Zi.T + s2 * np.eye(len(yi))
            L = np.linalg.cholesky(Vi)
            logdet += 2 * np.log(np.diag(L)).sum()
            ViX = np.linalg.solve(Vi, Xi)
            A += Xi.T @ ViX
            b += ViX.T @ yi
            cache.append((Vi, Xi, yi))
        return A, b, logdet, cache

    def cov_beta(self, th):
        return np.linalg.inv(self.parts(th)[0])

    def nll(self, th):
        try:
            A, b, logdet, cache = self.parts(th)
        except np.linalg.LinAlgError:
            return np.inf
        beta = np.linalg.solve(A, b)
        quad = sum(float((yi - Xi @ beta) @ np.linalg.solve(Vi, yi - Xi @ beta)) for Vi, Xi, yi in cache)
        val = 0.5 * (logdet + quad)
        if self.reml:
            val += 0.5 * np.linalg.slogdet(A)[1]
        return val


def satterthwaite(md, fit, reml, q):
    """Covariance of β and a function returning (estimate, F or t, df) for a contrast matrix L."""
    lik = _MixedLik(md, reml, q)
    G = np.asarray(fit.cov_re, float)
    th = np.array([G[i, j] for i, j in lik.idx] + [float(fit.scale)])
    # parameters at the boundary (zero variance) are held fixed, as lmerTest does for singular fits
    free = [k for k, (i, j) in enumerate(lik.idx) if not (i == j and th[k] < 1e-10 * max(th[-1], 1e-300))] + [len(th) - 1]
    C = lik.cov_beta(th)
    n = len(free)
    h = np.array([1e-4 * max(abs(th[k]), 1e-6 * th[-1]) for k in free])

    def at(delta):
        t2 = th.copy()
        t2[free] += delta
        return t2

    H = np.zeros((n, n))
    f0 = lik.nll(th)
    for a in range(n):
        ea = np.eye(n)[a] * h[a]
        H[a, a] = (lik.nll(at(ea)) - 2 * f0 + lik.nll(at(-ea))) / h[a] ** 2
        for c in range(a + 1, n):
            ec = np.eye(n)[c] * h[c]
            H[a, c] = H[c, a] = (lik.nll(at(ea + ec)) - lik.nll(at(ea - ec)) - lik.nll(at(-ea + ec)) + lik.nll(at(-ea - ec))) / (4 * h[a] * h[c])
    try:
        Acov = np.linalg.inv(H)
    except np.linalg.LinAlgError:
        Acov = np.linalg.pinv(H)
    dC = [(lik.cov_beta(at(np.eye(n)[a] * h[a])) - lik.cov_beta(at(-np.eye(n)[a] * h[a]))) / (2 * h[a]) for a in range(n)]

    def df_for(lvec):
        var = float(lvec @ C @ lvec)
        g = np.array([float(lvec @ D @ lvec) for D in dC])
        den = float(g @ Acov @ g)
        return 2 * var ** 2 / den if den > 0 else np.inf

    def test(L, beta):
        L = np.atleast_2d(L)
        qn = L.shape[0]
        M = L @ C @ L.T
        Lb = L @ beta
        if qn == 1:
            se = math.sqrt(float(M[0, 0]))
            return float(Lb[0]) / se, df_for(L[0])
        F = float(Lb @ np.linalg.solve(M, Lb)) / qn
        w, P = np.linalg.eigh(M)
        nus = [df_for(P[:, m] @ L) for m in range(qn)]
        E = sum(nu / (nu - 2) for nu in nus if nu > 2)
        nu = 2 * E / (E - qn) if E > qn else np.inf
        return F, nu
    return C, test
