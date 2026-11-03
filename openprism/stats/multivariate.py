"""Multiple-variables analyses (multiple / logistic / Cox regression, PCA),
Bland-Altman method comparison, smoothing, and power / sample-size.

Analyses here return a generic ``plot`` overlay that the front-end can draw as
an "Analysis plot" graph::

    {"kind": "plot", "plots": [{"title", "xTitle", "yTitle", "traces": [...],
                                "hlines": [{"y", "label", "dash"}], "vlines": [...]}]}
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from ..tables import make_table
from .common import AnalysisError, Result, fmt, fmt_p, quiet, require, sig, stars
from .descriptive import selected


def _clean(a):
    return [float(v) if v is not None and np.isfinite(v) else None for v in np.asarray(a, float)]


def _var(table, i):
    i = int(i)
    require(0 <= i < len(table.Y), "A chosen variable does not exist in this table; open ⚙ Parameters and choose it again.")
    a = table.Y[i]
    return a[:, 0] if a.shape[1] == 1 else np.nanmean(a, axis=1)


def _design(table, dep, preds):
    cols = [_var(table, dep)] + [_var(table, j) for j in preds]
    M = np.column_stack(cols)
    keep = np.all(np.isfinite(M), axis=1)
    return M[keep, 0], M[keep, 1:], keep


def _pick(params, key, default=None):
    v = params.get(key, default)
    return None if v in (None, "") else v


def _predictors(table, params, dep):
    preds = params.get("predictors")
    if not preds:
        preds = [i for i in range(len(table.Y)) if i != dep]
    preds = [int(p) for p in preds if int(p) != dep and 0 <= int(p) < len(table.Y)]
    require(preds, "Choose at least one independent (X) variable.")
    return preds


# ---------------------------------------------------------------- multiple linear regression
def multiple_regression(table, params):
    import statsmodels.api as sm

    dep = int(_pick(params, "dependent", 0))
    preds = _predictors(table, params, dep)
    y, X, keep = _design(table, dep, preds)
    names = [table.names[j] for j in preds]
    require(len(y) > len(preds) + 1, "Not enough complete rows for this many variables.")
    Xc = sm.add_constant(X, has_constant="add")
    with quiet():
        model = sm.OLS(y, Xc).fit()
    alpha = float(params.get("alpha", 0.05))
    r = Result(f"Multiple linear regression: {table.names[dep]}")
    from .precise import scaled_condition
    cond = scaled_condition(X)
    if cond > 1e6 and len(y) * X.shape[1] ** 2 <= 4e6:
        try:
            model = _exact_model(table, dep, preds, keep, len(y))
            r.warn(f"The predictors are nearly collinear (scaled condition number {fmt(cond)}). The fit was computed "
                   "from the exact decimal data in 80-digit arithmetic so the estimates keep full precision, but "
                   "individual coefficients may still be poorly determined (see VIF).")
        except ZeroDivisionError as e:
            r.warn(f"Exact solution impossible: {e}.")
    ci = model.conf_int(alpha)
    vif = []
    for j in range(X.shape[1]):
        if X.shape[1] == 1:
            vif.append(1.0)
            continue
        others = np.delete(X, j, axis=1)
        with quiet():
            rr = sm.OLS(X[:, j], sm.add_constant(others)).fit().rsquared
        vif.append(1 / (1 - rr) if rr < 1 else np.inf)
    rows = [["Intercept", model.params[0], model.bse[0], f"{fmt(ci[0][0])} to {fmt(ci[0][1])}", model.tvalues[0],
             fmt_p(model.pvalues[0]), stars(model.pvalues[0], alpha), ""]]
    for j, nm in enumerate(names):
        k = j + 1
        rows.append([nm, model.params[k], model.bse[k], f"{fmt(ci[k][0])} to {fmt(ci[k][1])}", model.tvalues[k],
                     fmt_p(model.pvalues[k]), stars(model.pvalues[k], alpha), vif[j]])
    r.table("Parameter estimates", ["Variable", "Estimate", "Std. error", f"{int((1 - alpha) * 100)}% CI", "|t|",
                                    "P value", "Summary", "VIF (multicollinearity)"],
            [[row[0], row[1], row[2], row[3], abs(row[4]), *row[5:]] for row in rows])
    n, k = len(y), X.shape[1] + 1
    aicc = model.aic + 2 * k * (k + 1) / (n - k - 1) if n - k - 1 > 0 else np.nan
    r.kv("Goodness of fit", [
        ("Degrees of freedom", int(model.df_resid)), ("R squared", model.rsquared),
        ("Adjusted R squared", model.rsquared_adj), ("Multiple R", math.sqrt(max(model.rsquared, 0))),
        ("Sum of squares", model.ssr), ("Sy.x (RMSE)", math.sqrt(model.mse_resid)), ("AICc", aicc),
        ("Number of observations", n), ("Rows skipped (missing values)", int((~keep).sum())),
    ])
    r.kv("Is the model better than intercept-only?", [
        ("F (DFn, DFd)", f"{fmt(model.fvalue)} ({int(model.df_model)}, {int(model.df_resid)})"),
        ("P value", fmt_p(model.f_pvalue)), (f"Significant (P < {alpha})?", sig(model.f_pvalue, alpha)),
    ])
    eq = f"{table.names[dep]} = {fmt(model.params[0])}" + "".join(
        f" {'+' if b >= 0 else '-'} {fmt(abs(b))}×{nm}" for b, nm in zip(model.params[1:], names))
    r.kv("Equation", [("Fitted model", eq)])
    resid = model.resid
    if len(resid) >= 3:
        w, p = stats.shapiro(resid)
        r.kv("Normality of residuals", [("Shapiro-Wilk W", w), ("P value", fmt_p(p)),
                                        ("Passed normality test (α=0.05)?", "Yes" if p >= 0.05 else "No")])
    if any(v > 10 for v in vif):
        r.warn("Some VIF values exceed 10: predictors are strongly correlated (multicollinearity), so individual "
               "coefficients are unreliable.")
    pred = model.fittedvalues
    lo, hi = float(min(pred.min(), y.min())), float(max(pred.max(), y.max()))
    r.overlay = {"kind": "plot", "plots": [
        {"title": "Actual vs. predicted", "xTitle": f"Predicted {table.names[dep]}", "yTitle": f"Actual {table.names[dep]}",
         "traces": [{"type": "scatter", "mode": "markers", "x": _clean(pred), "y": _clean(y), "name": "Observations"},
                    {"type": "scatter", "mode": "lines", "x": [lo, hi], "y": [lo, hi], "name": "Line of identity", "dash": "dot", "color": "#888"}]},
        {"title": "Residual plot", "xTitle": f"Predicted {table.names[dep]}", "yTitle": "Residual",
         "traces": [{"type": "scatter", "mode": "markers", "x": _clean(pred), "y": _clean(resid), "name": "Residuals"}],
         "hlines": [{"y": 0, "dash": "dot"}]},
        _qq_plot([("Residuals", resid)]),
    ]}
    return r


def _exact_model(table, dep, preds, keep, n):
    """OLS solved from the exact decimal input in high precision, exposing the attributes used above."""
    from types import SimpleNamespace

    from .precise import exact_ols, to_dec

    def dec(i):
        raw = table.raw[i]
        vals = table.Y[i]
        if vals.shape[1] != 1:  # replicates are averaged: no exact text available
            return [to_dec("", v) for v in _var(table, i)[keep]]
        return [to_dec(t, v) for t, v, k in zip(raw[:, 0], vals[:, 0], keep) if k]
    yd = dec(dep)
    cols = [dec(j) for j in preds]
    X = [list(r) for r in zip(*cols)]
    e = exact_ols(yd, X)
    p = e["p"]
    df = e["df"]
    t = e["beta"] / e["se"]
    pv = 2 * stats.t.sf(np.abs(t), df)
    msr = (e["tss"] - e["rss"]) / (p - 1)
    mse = e["rss"] / df
    F = msr / mse
    llf = -n / 2 * (math.log(2 * math.pi) + math.log(e["rss"] / n) + 1)

    def conf_int(alpha):
        q = stats.t.ppf(1 - alpha / 2, df)
        return np.column_stack([e["beta"] - q * e["se"], e["beta"] + q * e["se"]])
    return SimpleNamespace(params=e["beta"], bse=e["se"], tvalues=t, pvalues=pv, conf_int=conf_int, df_resid=df, df_model=p - 1,
                           rsquared=e["r2"], rsquared_adj=1 - (1 - e["r2"]) * (n - 1) / df, ssr=e["rss"], mse_resid=mse,
                           fvalue=F, f_pvalue=float(stats.f.sf(F, p - 1, df)), aic=-2 * llf + 2 * p,
                           resid=e["resid"], fittedvalues=e["fitted"])


# ---------------------------------------------------------------- logistic regression
def logistic(table, params):
    import statsmodels.api as sm

    dep = int(_pick(params, "dependent", 0))
    preds = _predictors(table, params, dep)
    y, X, keep = _design(table, dep, preds)
    require(set(np.unique(y)) <= {0.0, 1.0}, f"The dependent variable ({table.names[dep]}) must contain only 0 and 1.")
    require(0 < y.sum() < len(y), "The outcome needs both 0s and 1s.")
    names = [table.names[j] for j in preds]
    alpha = float(params.get("alpha", 0.05))
    with quiet():
        try:
            model = sm.Logit(y, sm.add_constant(X, has_constant="add")).fit(disp=0, maxiter=200)
        except Exception as e:  # noqa: BLE001
            raise AnalysisError(f"Logistic model did not converge ({e}). Perfect separation is a common cause.") from None
    ci = np.asarray(model.conf_int(alpha))
    rows = []
    for k, nm in enumerate(["Intercept"] + names):
        b = model.params[k]
        rows.append([nm, b, model.bse[k], math.exp(b), f"{fmt(math.exp(ci[k][0]))} to {fmt(math.exp(ci[k][1]))}",
                     abs(model.tvalues[k]), fmt_p(model.pvalues[k]), stars(model.pvalues[k], alpha)])
    r = Result(f"Multiple logistic regression: {table.names[dep]}")
    r.table("Parameter estimates", ["Variable", "β (log odds)", "Std. error", "Odds ratio", f"{int((1 - alpha) * 100)}% CI of OR",
                                    "|z|", "P value", "Summary"], rows)
    prob = model.predict()
    auc = stats.mannwhitneyu(prob[y == 1], prob[y == 0]).statistic / ((y == 1).sum() * (y == 0).sum())
    cut = float(params.get("cutoff", 0.5))
    pred = (prob >= cut).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum()); tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum()); fn = int(((pred == 0) & (y == 1)).sum())
    r.kv("Goodness of fit", [
        ("Number of observations", len(y)), ("Number of 1s / 0s", f"{int(y.sum())} / {int(len(y) - y.sum())}"),
        ("Tjur's R squared", prob[y == 1].mean() - prob[y == 0].mean()), ("McFadden pseudo R squared", model.prsquared),
        ("Log likelihood", model.llf), ("AIC", model.aic),
        ("Likelihood ratio test vs. intercept-only (χ², df)", f"{fmt(model.llr)}, {int(model.df_model)}"),
        ("Likelihood ratio P value", fmt_p(model.llr_pvalue)), ("Area under ROC curve", auc),
    ])
    r.table(f"Classification (cutoff = {cut})", ["", "Predicted 0", "Predicted 1", "% correct"], [
        ["Observed 0", tn, fp, 100 * tn / max(1, tn + fp)], ["Observed 1", fn, tp, 100 * tp / max(1, tp + fn)],
        ["Overall", "", "", 100 * (tp + tn) / len(y)]])
    # ROC points
    thr = np.unique(np.concatenate([[-np.inf], prob, [np.inf]]))
    fx = [float(((prob >= t_) & (y == 0)).sum() / max(1, (y == 0).sum()) * 100) for t_ in thr[::-1]]
    fy = [float(((prob >= t_) & (y == 1)).sum() / max(1, (y == 1).sum()) * 100) for t_ in thr[::-1]]
    plots = [{"title": f"ROC curve (AUC = {auc:.3f})", "xTitle": "100% - Specificity%", "yTitle": "Sensitivity%",
              "traces": [{"type": "scatter", "mode": "lines", "x": fx, "y": fy, "name": "Model", "shape": "hv"},
                         {"type": "scatter", "mode": "lines", "x": [0, 100], "y": [0, 100], "dash": "dot", "color": "#888", "name": "Chance"}]}]
    if len(preds) == 1:
        xs = np.linspace(X[:, 0].min(), X[:, 0].max(), 200)
        ps = model.predict(sm.add_constant(xs[:, None], has_constant="add"))
        plots.insert(0, {"title": "Fitted probability", "xTitle": names[0], "yTitle": f"P({table.names[dep]} = 1)",
                         "traces": [{"type": "scatter", "mode": "markers", "x": _clean(X[:, 0]), "y": _clean(y), "name": "Observed"},
                                    {"type": "scatter", "mode": "lines", "x": _clean(xs), "y": _clean(ps), "name": "Logistic fit"}]})
    plots.append(_forest([n for n in names], [math.exp(b) for b in model.params[1:]],
                         [math.exp(c[0]) for c in ci[1:]], [math.exp(c[1]) for c in ci[1:]], "Odds ratio"))
    r.overlay = {"kind": "plot", "plots": plots}
    return r


def _forest(names, est, lo, hi, label):
    return {"title": f"{label}s with confidence intervals", "xTitle": f"{label} (log scale)", "yTitle": "", "xLog": True,
            "traces": [{"type": "scatter", "mode": "markers", "x": _clean(est), "y": list(names), "name": label,
                        "errorX": {"plus": _clean(np.array(hi) - np.array(est)), "minus": _clean(np.array(est) - np.array(lo))},
                        "symbol": "square", "size": 10}],
            "vlines": [{"x": 1, "dash": "dot"}], "yCategory": True}


# ---------------------------------------------------------------- Cox proportional hazards
def cox(table, params):
    from statsmodels.duration.hazard_regression import PHReg

    tvar = int(_pick(params, "timeVar", 0))
    evar = int(_pick(params, "eventVar", 1))
    preds = [int(p) for p in (params.get("predictors") or []) if int(p) not in (tvar, evar)]
    if not preds:
        preds = [i for i in range(len(table.Y)) if i not in (tvar, evar)]
    require(preds, "Choose at least one covariate.")
    cols = [_var(table, tvar), _var(table, evar)] + [_var(table, j) for j in preds]
    M = np.column_stack(cols)
    M = M[np.all(np.isfinite(M), axis=1)]
    require(len(M) > len(preds) + 2, "Not enough complete rows.")
    t, e, X = M[:, 0], M[:, 1], M[:, 2:]
    require(set(np.unique(e)) <= {0.0, 1.0}, "The event variable must be 1 (event) or 0 (censored).")
    names = [table.names[j] for j in preds]
    alpha = float(params.get("alpha", 0.05))
    with quiet():
        res = PHReg(t, X, status=e, ties="efron").fit()
    ci = np.asarray(res.conf_int(alpha))
    rows = []
    for k, nm in enumerate(names):
        rows.append([nm, res.params[k], res.bse[k], math.exp(res.params[k]),
                     f"{fmt(math.exp(ci[k][0]))} to {fmt(math.exp(ci[k][1]))}", fmt_p(res.pvalues[k]), stars(res.pvalues[k], alpha)])
    r = Result("Cox proportional hazards regression")
    r.table("Hazard ratios", ["Covariate", "β", "Std. error", "Hazard ratio", f"{int((1 - alpha) * 100)}% CI", "P value", "Summary"], rows)
    lr = 2 * (res.llf - _cox_null_ll(t, e))
    p_lr = float(stats.chi2.sf(lr, len(preds)))
    r.kv("Model", [("Subjects", len(t)), ("Events", int(e.sum())), ("Censored", int((e == 0).sum())),
                   ("Log partial likelihood", res.llf), ("Likelihood ratio χ² (df)", f"{fmt(lr)} ({len(preds)})"),
                   ("P value", fmt_p(p_lr)), ("Concordance (Harrell's C)", _harrell_c(t, e, X @ res.params))])
    r.warn("Hazard ratios are per one-unit increase of each covariate. Check the proportional hazards assumption.")
    r.overlay = {"kind": "plot", "plots": [_forest(names, np.exp(res.params), np.exp(ci[:, 0]), np.exp(ci[:, 1]), "Hazard ratio")]}
    return r


def _cox_null_ll(t, e):
    """Efron log partial likelihood at beta = 0: -sum over event times of sum_j log(n_at_risk - j)."""
    ll = 0.0
    for tt in np.unique(t[e == 1]):
        d = int(((t == tt) & (e == 1)).sum())
        n = int((t >= tt).sum())
        ll -= sum(math.log(n - j) for j in range(d))
    return ll


def _harrell_c(t, e, risk):
    conc = disc = 0.0
    for i in np.where(e == 1)[0]:  # vectorized over j
        later = t > t[i]
        conc += float((risk[i] > risk[later]).sum()) + 0.5 * float((risk[i] == risk[later]).sum())
        disc += float((risk[i] < risk[later]).sum()) + 0.5 * float((risk[i] == risk[later]).sum())
    return conc / (conc + disc) if conc + disc else np.nan


# ---------------------------------------------------------------- PCA
def pca(table, params):
    idx = selected(table, params)
    require(len(idx) >= 2, "PCA needs at least two variables.")
    M = np.column_stack([_var(table, i) for i in idx])
    keep = np.all(np.isfinite(M), axis=1)
    M = M[keep]
    require(len(M) >= 3, "Need at least three complete rows.")
    names = [table.names[i] for i in idx]
    scale = params.get("scale", "standardize") == "standardize"
    Z = M - M.mean(axis=0)
    if scale:
        sd = M.std(axis=0, ddof=1)
        require(np.all(sd > 0), "A variable has zero variance.")
        Z = Z / sd
    U, S, Vt = np.linalg.svd(Z, full_matrices=False)
    eig = S ** 2 / (len(M) - 1)
    prop = eig / eig.sum()
    k = len(eig)
    scores = U * S
    loadings = Vt.T * np.sqrt(eig)  # correlations between variables and PCs when standardized
    r = Result("Principal component analysis")
    pcs = [f"PC{j + 1}" for j in range(k)]
    r.table("Eigenvalues", ["Component", "Eigenvalue", "% of variance", "Cumulative %"],
            [[pcs[j], eig[j], prop[j] * 100, prop[:j + 1].sum() * 100] for j in range(k)])
    r.table("Loadings" + (" (correlation of variable with component)" if scale else ""), ["Variable"] + pcs,
            [[nm] + list(loadings[v]) for v, nm in enumerate(names)])
    r.table("Eigenvectors (coefficients)", ["Variable"] + pcs, [[nm] + list(Vt.T[v]) for v, nm in enumerate(names)])
    kaiser = int((eig > 1).sum()) if scale else None
    pa = _parallel_analysis(Z.shape, eig, scale)
    r.kv("How many components?", [("Kaiser rule (eigenvalue > 1)", kaiser if kaiser is not None else "n/a (unscaled)"),
                                  ("Parallel analysis (95th percentile)", pa),
                                  ("Components for 80% of variance", int(np.searchsorted(np.cumsum(prop), 0.8) + 1))])
    labels = [lab for lab, kk in zip(table.row_labels, keep) if kk]
    r.output_tables.append(make_table(f"PC scores of {table.name}", "multi", [{"name": p, "reps": 1} for p in pcs],
                                      scores.tolist(), row_labels=labels))
    sc = max(np.abs(scores[:, :2]).max(), 1e-9) / max(np.abs(loadings[:, :2]).max(), 1e-9) * 0.8 if k >= 2 else 1
    biplot = {"title": "Biplot", "xTitle": f"PC1 ({prop[0] * 100:.1f}%)", "yTitle": f"PC2 ({prop[1] * 100:.1f}%)" if k > 1 else "",
              "traces": [{"type": "scatter", "mode": "markers", "x": _clean(scores[:, 0]), "y": _clean(scores[:, 1] if k > 1 else np.zeros(len(M))),
                          "text": labels, "name": "Scores (rows)"}], "hlines": [{"y": 0, "dash": "dot"}], "vlines": [{"x": 0, "dash": "dot"}]}
    for v, nm in enumerate(names):
        biplot["traces"].append({"type": "scatter", "mode": "lines+text", "x": [0, float(loadings[v, 0] * sc)],
                                 "y": [0, float(loadings[v, 1] * sc) if k > 1 else 0], "text": ["", nm], "textposition": "top center",
                                 "color": "#c0392b", "name": nm, "showlegend": False})
    r.overlay = {"kind": "plot", "plots": [
        {"title": "Scree plot", "xTitle": "Principal component", "yTitle": "Eigenvalue",
         "traces": [{"type": "bar", "x": pcs, "y": _clean(eig), "name": "Eigenvalue"},
                    {"type": "scatter", "mode": "lines+markers", "x": pcs, "y": _clean(pa_curve(Z.shape, scale)), "name": "Parallel analysis", "dash": "dot"}],
         "hlines": [{"y": 1, "dash": "dot", "label": "Kaiser"}] if scale else [], "xCategory": True},
        biplot,
        {"title": "Loadings (PC1 vs PC2)", "xTitle": "PC1 loading", "yTitle": "PC2 loading",
         "traces": [{"type": "scatter", "mode": "markers+text", "x": _clean(loadings[:, 0]), "y": _clean(loadings[:, 1] if k > 1 else np.zeros(len(names))),
                     "text": names, "textposition": "top center", "name": "Variables"}],
         "hlines": [{"y": 0, "dash": "dot"}], "vlines": [{"x": 0, "dash": "dot"}]},
    ]}
    return r


def pa_curve(shape, scale, reps=200):
    n, p = shape
    reps = max(20, min(reps, int(2_000_000 / max(n * p, 1))))  # bound the cost for big tables
    rng = np.random.default_rng(0)
    eigs = np.empty((reps, p))
    for k in range(reps):
        Z = rng.standard_normal((n, p))
        Z = Z - Z.mean(0)
        if scale:
            Z = Z / Z.std(0, ddof=1)
        s = np.linalg.svd(Z, compute_uv=False)
        eigs[k] = s ** 2 / (n - 1)
    return np.percentile(eigs, 95, axis=0)


def _parallel_analysis(shape, eig, scale):
    if not scale:
        return "n/a (unscaled)"
    ref = pa_curve(shape, scale)
    n = 0
    for e_, r_ in zip(eig, ref):
        if e_ > r_:
            n += 1
        else:
            break
    return n


# ---------------------------------------------------------------- Bland-Altman
def bland_altman(table, params):
    idx = selected(table, params)
    require(len(idx) >= 2, "Bland-Altman needs two data sets (method A and method B).")
    a, b = _var(table, idx[0]), _var(table, idx[1])
    m = np.isfinite(a) & np.isfinite(b)
    a, b = a[m], b[m]
    require(len(a) >= 3, "Need at least three paired values.")
    kind = params.get("difference", "diff")
    avg = (a + b) / 2
    if kind == "ratio":
        require(np.all(b != 0), "Ratio requires non-zero values in the second data set.")
        d = a / b
        lab = f"{table.names[idx[0]]} / {table.names[idx[1]]}"
    elif kind == "percent":
        d = (a - b) / avg * 100
        lab = f"% difference (A-B)/average"
    else:
        d = a - b
        lab = f"{table.names[idx[0]]} - {table.names[idx[1]]}"
    n = len(d)
    bias, sd = d.mean(), d.std(ddof=1)
    z = 1.959964
    lo, hi = bias - z * sd, bias + z * sd
    t = stats.t.ppf(0.975, n - 1)
    se_b = sd / math.sqrt(n)
    se_l = math.sqrt(3 * sd ** 2 / n)
    reg = stats.linregress(avg, d)
    r = Result("Bland-Altman method comparison")
    r.kv("Bias and limits of agreement", [
        ("Difference plotted", lab), ("Number of pairs", n), ("Bias (mean difference)", bias),
        ("SD of bias", sd), ("95% CI of bias", f"{fmt(bias - t * se_b)} to {fmt(bias + t * se_b)}"),
        ("95% limits of agreement", f"{fmt(lo)} to {fmt(hi)}"),
        ("95% CI of lower limit", f"{fmt(lo - t * se_l)} to {fmt(lo + t * se_l)}"),
        ("95% CI of upper limit", f"{fmt(hi - t * se_l)} to {fmt(hi + t * se_l)}"),
        ("Is the bias significant? (paired t, P)", fmt_p(stats.ttest_1samp(d, 0 if kind != "ratio" else 1).pvalue)),
        ("Proportional bias (slope of difference vs. average)", reg.slope), ("Slope P value", fmt_p(reg.pvalue)),
    ])
    if reg.pvalue < 0.05:
        r.warn("The difference changes with the magnitude (proportional bias). Consider plotting ratios or % differences.")
    r.overlay = {"kind": "plot", "plots": [{
        "title": "Bland-Altman plot", "xTitle": "Average of both methods", "yTitle": lab,
        "traces": [{"type": "scatter", "mode": "markers", "x": _clean(avg), "y": _clean(d), "name": "Pairs"}],
        "hlines": [{"y": float(bias), "label": f"Bias {fmt(bias)}"}, {"y": float(lo), "dash": "dash", "label": f"-1.96 SD {fmt(lo)}"},
                   {"y": float(hi), "dash": "dash", "label": f"+1.96 SD {fmt(hi)}"}]}]}
    return r


# ---------------------------------------------------------------- smoothing, derivative, integral
def smooth(table, params):
    require(table.type == "xy", "Smoothing requires an XY table.")
    idx = selected(table, params)
    what = params.get("operation", "lowess")
    r = Result({"lowess": "LOWESS smoothing", "moving": "Moving-average smoothing", "derivative": "Derivative",
                "integral": "Cumulative integral (area)"}[what])
    curves, cells = [], {}
    allx = set()
    for i in idx:
        x = table.x
        y = table.row_means(i)
        m = np.isfinite(x) & np.isfinite(y)
        x, y = x[m], y[m]
        o = np.argsort(x)
        x, y = x[o], y[o]
        if len(x) < 3:
            continue
        if what == "lowess":
            from statsmodels.nonparametric.smoothers_lowess import lowess
            frac = min(1.0, max(0.05, float(params.get("frac", 0.4))))
            out = lowess(y, x, frac=frac, return_sorted=True)
            sx, sy = out[:, 0], out[:, 1]
        elif what == "moving":
            k = max(1, min(int(params.get("window", 3)), 1001))
            pad = k // 2
            yp = np.pad(y, pad, mode="edge")
            sy = np.convolve(yp, np.ones(k) / k, mode="valid")[:len(y)]
            sx = x
        elif what == "derivative":
            sx, sy = x, np.gradient(y, x)
        else:
            sx = x
            sy = np.concatenate([[0], np.cumsum((y[1:] + y[:-1]) / 2 * np.diff(x))])
        for xv, yv in zip(sx, sy):
            cells.setdefault(float(xv), {})[i] = float(yv)
            allx.add(float(xv))
        if what in ("lowess", "moving"):
            curves.append({"dataset": i, "x": _clean(sx), "y": _clean(sy), "lo": None, "hi": None})
    xs = sorted(allx)
    r.table("Result", ["X"] + [table.names[i] for i in idx], [[xv] + [cells[xv].get(i, "") for i in idx] for xv in xs])
    r.output_tables.append(make_table(f"{r.title} of {table.name}", "xy", [{"name": table.names[i], "reps": 1} for i in idx],
                                      [[cells[xv].get(i) for i in idx] for xv in xs], x=xs, x_title=table.x_title))
    if curves:
        r.overlay = {"kind": "curves", "curves": curves, "showBand": False}
    return r


# ---------------------------------------------------------------- Q-Q plots
def _qq_plot(series):
    traces = []
    lo, hi = np.inf, -np.inf
    for name, v in series:
        v = np.sort(np.asarray(v, float))
        v = v[np.isfinite(v)]
        n = len(v)
        if n < 3:
            continue
        pp = (np.arange(1, n + 1) - 0.375) / (n + 0.25)  # Blom
        q = stats.norm.ppf(pp) * v.std(ddof=1) + v.mean()
        traces.append({"type": "scatter", "mode": "markers", "x": _clean(q), "y": _clean(v), "name": name})
        lo, hi = min(lo, q.min(), v.min()), max(hi, q.max(), v.max())
    if np.isfinite(lo):
        traces.append({"type": "scatter", "mode": "lines", "x": [float(lo), float(hi)], "y": [float(lo), float(hi)],
                       "dash": "dot", "color": "#888", "name": "Line of identity"})
    return {"title": "Normal Q-Q plot", "xTitle": "Predicted (normal distribution)", "yTitle": "Actual", "traces": traces}


def qq_overlay(table, idx):
    return {"kind": "plot", "plots": [_qq_plot([(table.names[i], table.column_values(i)) for i in idx])]}


# ---------------------------------------------------------------- power & sample size
def power(params):
    """Power / sample size for common designs. Leave exactly one of n / power blank to solve for it."""
    from statsmodels.stats.power import FTestAnovaPower, NormalIndPower, TTestIndPower, TTestPower
    from statsmodels.stats.proportion import proportion_effectsize

    test = params.get("test", "ttest2")
    alpha = float(params.get("alpha", 0.05))
    alt = "two-sided" if params.get("tails", "2") in ("2", 2, "two-sided") else "larger"
    n = params.get("n")
    pw = params.get("power")
    n = float(n) if n not in (None, "") else None
    pw = float(pw) if pw not in (None, "") else None
    if (n is None) == (pw is None):
        raise AnalysisError("Fill in either the sample size or the power (leave the other blank).")
    ratio = float(params.get("ratio", 1) or 1)
    groups = int(params.get("groups", 3) or 3)

    def num(k):
        v = params.get(k)
        if v in (None, ""):
            raise AnalysisError(f"Please enter a value for '{k}'.")
        return float(v)

    if test in ("ttest2", "paired", "onesample"):
        es = abs(num("difference")) / num("sd")
        solver = TTestIndPower() if test == "ttest2" else TTestPower()
        kw = {"ratio": ratio} if test == "ttest2" else {}
        label = "Cohen's d"
    elif test == "anova":
        es = num("f")
        solver = FTestAnovaPower()
        kw = {"k_groups": groups}
        label = "Cohen's f"
    elif test == "prop2":
        es = abs(proportion_effectsize(num("p1"), num("p2")))
        solver = NormalIndPower()
        kw = {"ratio": ratio}
        label = "Cohen's h"
    elif test == "corr":
        rr = num("r")
        es = abs(math.atanh(rr))
        label = "Fisher z of r"
        solver = None
        kw = {}
    elif test == "logrank":   # Schoenfeld (1983): events needed for a hazard ratio
        hr, pev = num("hr"), num("pevent")
        require(hr > 0 and hr != 1, "The hazard ratio must be positive and different from 1.")
        require(0 < pev <= 1, "The probability of an event must be between 0 and 1.")
        es, label, solver, kw = abs(math.log(hr)), "|ln hazard ratio|", None, {}
    elif test == "mannwhitney":   # Noether (1987), from the shift expressed as Cohen's d (normal data)
        d_ = abs(num("difference")) / num("sd")
        es, label, solver, kw = abs(stats.norm.cdf(d_ / math.sqrt(2)) - 0.5), "P(Y > X) − ½", None, {}
    elif test == "mcnemar":   # Connor (1987): paired proportions, discordant cell probabilities
        p10, p01 = num("p10"), num("p01")
        require(0 < p10 + p01 <= 1 and p10 != p01, "Enter two different discordant proportions whose sum is at most 1.")
        es, label, solver, kw = abs(p10 - p01), "difference of discordant proportions", None, {}
    elif test == "oneprop":   # one proportion vs. a hypothetical value (normal approximation)
        p0, p1 = num("p0"), num("p1")
        require(0 < p0 < 1 and 0 < p1 < 1 and p0 != p1, "Proportions must be between 0 and 1 and differ.")
        es, label, solver, kw = abs(p1 - p0), "difference of proportions", None, {}
    else:
        raise AnalysisError("Unknown test")
    require(es > 0, "The effect size must be larger than zero.")

    def power_at(nn):
        zc = stats.norm.ppf(1 - alpha / (2 if alt == "two-sided" else 1))
        if test == "logrank":
            q1, q2 = 1 / (1 + ratio), ratio / (1 + ratio)
            events = nn * (1 + ratio) * pev
            return float(stats.norm.cdf(math.sqrt(events * q1 * q2) * es - zc))
        if test == "mannwhitney":
            c = 1 / (1 + ratio)
            return float(stats.norm.cdf(math.sqrt(12 * nn * (1 + ratio) * c * (1 - c)) * es - zc))
        if test == "mcnemar":
            pd = p10 + p01
            return float(stats.norm.cdf((math.sqrt(nn) * es - zc * math.sqrt(pd)) / math.sqrt(pd - es ** 2)))
        if test == "oneprop":
            return float(stats.norm.cdf((math.sqrt(nn) * es - zc * math.sqrt(p0 * (1 - p0))) / math.sqrt(p1 * (1 - p1))))
        if solver is None:  # correlation via Fisher z
            return float(stats.norm.cdf(es * math.sqrt(max(nn - 3, 0)) - zc))
        if test == "anova":
            return float(solver.power(effect_size=es, nobs=nn * groups, alpha=alpha, **kw))
        return float(solver.power(effect_size=es, nobs1=nn, alpha=alpha, alternative=alt, **kw))

    with quiet():
        n_exact = None
        if pw is None:
            result_power = power_at(n)
            result_n = n
        else:
            lo_, hi_ = 2.0, 2.0
            while power_at(hi_) < pw and hi_ < 1e7:
                hi_ *= 2
            for _ in range(80):
                mid = (lo_ + hi_) / 2
                if power_at(mid) < pw:
                    lo_ = mid
                else:
                    hi_ = mid
            n_exact = hi_
            result_n = math.ceil(hi_)
            result_power = power_at(result_n)
    ns = np.unique(np.round(np.linspace(3 if solver is None else 2, max(result_n * 2.2, 10), 60)))
    curve = [power_at(v) for v in ns]
    per_group = test in ("ttest2", "prop2", "anova", "logrank", "mannwhitney")
    total = (result_n * (1 + ratio) if test in ("ttest2", "prop2", "logrank", "mannwhitney") else result_n * groups if test == "anova" else result_n)
    extra = {"events": math.ceil(result_n * (1 + ratio) * pev)} if test == "logrank" else {}
    return {**extra, "effectSize": es, "effectLabel": label, "n": result_n, "power": result_power, "total": math.ceil(total),
            "perGroup": per_group, "curve": {"n": [float(v) for v in ns], "power": curve}, "nExact": n_exact}
