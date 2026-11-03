"""Nonlinear & linear regression, correlation, area under the curve."""
from __future__ import annotations

import math

import numpy as np
from scipy import optimize, stats

from ..tables import make_table
from .common import AnalysisError, Result, fmt, fmt_p, quiet, require, sig, stars
from .descriptive import selected
from .models import MODELS
from . import models_extra  # noqa: F401  (registers the extended equation library)


def _numeric_jacobian(f, x, p):
    p = np.asarray(p, float)
    J = np.empty((len(x), len(p)))
    f0 = f(x, *p)
    for j in range(len(p)):
        h = 1e-6 * max(abs(p[j]), 1e-6)
        pp = p.copy()
        pp[j] += h
        J[:, j] = (f(x, *pp) - f0) / h
    return J


def robust_least_squares(g, x, y, p0, sigma=None):
    """Nonlinear least squares that does not stop at the first answer.

    Several algorithms are started from the initial values (Levenberg-Marquardt
    as in curve_fit, LM with tight tolerances, and a trust-region method with
    Jacobian scaling, which escapes from poor starting values); the solution
    with the smallest sum of squares is then polished with tight-tolerance LM
    steps. The covariance matrix comes from a central-difference Jacobian at
    the optimum. Validated against all NIST StRD nonlinear problems from both
    certified starting points (see validation/).
    """
    w = 1.0 / np.asarray(sigma, float) if sigma is not None else 1.0

    def resid(p):
        return (g(x, *p) - y) * w

    def ss(p):
        r = resid(p)
        return float(np.dot(r, r)) if np.all(np.isfinite(r)) else np.inf

    cands = []
    try:
        po, _ = optimize.curve_fit(g, x, y, p0=p0, sigma=sigma, maxfev=20000)
        cands.append(np.asarray(po, float))
    except Exception:  # noqa: BLE001  (other strategies follow)
        pass
    tight = {"xtol": 1e-15, "ftol": 1e-15, "gtol": 1e-15}
    for meth, kw in (("lm", {}), ("trf", {"x_scale": "jac"}), ("lm", {"x_scale": "jac"})):
        try:
            sol = optimize.least_squares(resid, p0, method=meth, max_nfev=4000 * (len(p0) + 1), **tight, **kw)
            cands.append(sol.x)
        except Exception:  # noqa: BLE001
            pass
    cands = [c for c in cands if np.isfinite(ss(c))]
    if not cands:
        raise RuntimeError("The fit did not converge. Try other initial values or constrain a parameter.")
    best = min(cands, key=ss)
    for _ in range(4):
        improved = False
        for kw in ({}, {"x_scale": "jac"}):
            try:
                sol = optimize.least_squares(resid, best, method="lm", max_nfev=2000 * (len(p0) + 1), **tight, **kw)
                if ss(sol.x) < ss(best):
                    best, improved = sol.x, True
            except Exception:  # noqa: BLE001
                pass
        if not improved:
            break
    # covariance from a central-difference Jacobian (as curve_fit: s² · (JᵀJ)⁻¹)
    J = np.empty((len(np.atleast_1d(y)), len(best)))
    for j in range(len(best)):
        h = np.finfo(float).eps ** (1 / 3) * max(abs(best[j]), 1e-8 if best[j] == 0 else abs(best[j]))
        e = np.zeros(len(best))
        e[j] = h
        J[:, j] = (resid(best + e) - resid(best - e)) / (2 * h)
    df = len(np.atleast_1d(y)) - len(best)
    try:
        _, sv, VT = np.linalg.svd(J, full_matrices=False)
        thr = np.finfo(float).eps * max(J.shape) * sv[0]
        sv = sv[sv > thr]
        VT = VT[:sv.size]
        pcov = (VT.T / sv ** 2) @ VT * (ss(best) / df if df > 0 else np.inf)
        if sv.size < len(best):
            pcov = np.full((len(best), len(best)), np.inf)
    except np.linalg.LinAlgError:
        pcov = np.full((len(best), len(best)), np.inf)
    return best, pcov


def fit_model(mkey, x, y, weights="none", constraints=None, initial=None):
    """Least-squares fit. Returns dict with params, se, cov, residual stats.

    *mkey* is a key of MODELS or a model dict (e.g. a user-defined equation)."""
    m = mkey if isinstance(mkey, dict) else MODELS[mkey]
    f = m["f"]
    names = m["params"]
    constraints = constraints or {}
    fixed = {k: float(v) for k, v in constraints.items() if v not in (None, "") and k in names}
    free = [n for n in names if n not in fixed]
    p0_all = list(initial) if initial else list(m["guess"](x, y))
    p0_all = [float(v) if np.isfinite(v) else 1.0 for v in p0_all]
    p0 = [p0_all[names.index(n)] for n in free]

    def full(pf):
        d = dict(zip(free, pf))
        return [d.get(n, fixed.get(n)) for n in names]

    def g(xx, *pf):
        return f(xx, *full(pf))

    sigma = None
    if weights == "1/Y^2":
        sigma = np.abs(y)
        sigma[sigma == 0] = 1e-12
    elif weights == "1/Y":
        sigma = np.sqrt(np.abs(y))
        sigma[sigma == 0] = 1e-12

    with quiet():
        if free:
            popt, pcov = robust_least_squares(g, x, y, p0, sigma)
        else:
            popt, pcov = np.array([]), np.zeros((0, 0))
    yhat = g(x, *popt)
    resid = y - yhat
    w = 1 / sigma ** 2 if sigma is not None else np.ones_like(y)
    ss = float((w * resid ** 2).sum())
    n, k = len(y), len(popt)
    df = n - k
    sst = float((w * (y - np.average(y, weights=w)) ** 2).sum())
    sy_x = math.sqrt(ss / df) if df > 0 else np.nan
    se = np.sqrt(np.diag(pcov)) if k else np.array([])
    aicc = n * math.log(ss / n) + 2 * k + (2 * k * (k + 1)) / (n - k - 1) if n - k - 1 > 0 and ss > 0 else np.nan
    return {
        "model": m["key"], "model_name": m["name"], "names": names, "free": free, "fixed": fixed, "popt": popt, "pcov": pcov, "se": se,
        "full": full(popt), "g": g, "f": f, "ss": ss, "df": df, "n": n, "k": k, "sy_x": sy_x,
        "r2": 1 - ss / sst if sst > 0 else np.nan, "aicc": aicc, "resid": resid, "yhat": yhat,
    }


def curve_with_band(fit, xs, level=0.95):
    g = fit["g"]
    y = g(xs, *fit["popt"])
    if fit["k"] == 0 or fit["df"] <= 0 or not np.all(np.isfinite(fit["pcov"])):
        return y, None, None
    J = _numeric_jacobian(g, xs, fit["popt"])
    var = np.einsum("ij,jk,ik->i", J, fit["pcov"], J)
    t = stats.t.ppf(0.5 + level / 2, fit["df"])
    h = t * np.sqrt(np.clip(var, 0, None))
    return y, y - h, y + h


def nonlinear(table, params):
    require(table.type in ("xy",), "Nonlinear regression requires an XY table.")
    mkey = params.get("model", "logagonist4")
    if mkey == "custom":
        from .custom_eq import custom_model
        m = custom_model(params.get("equation", ""), params.get("initial"))
        mkey = m
    else:
        require(mkey in MODELS, f"Unknown model {mkey}")
        m = MODELS[mkey]
    idx = selected(table, params)
    require(idx, "No data.")
    level = float(params.get("ci", 0.95))
    use_means = bool(params.get("fitMeans", False))
    weights = params.get("weights", "none")
    constraints = params.get("constraints") or {}
    try:
        interp = [float(v) for v in str(params.get("interpolate", ""))[:20000].replace(";", ",").split(",") if v.strip()][:1000]
    except ValueError:
        raise AnalysisError("Values to interpolate must be numbers separated by commas.") from None
    compare_key = params.get("compareModel")
    shared = [p.strip() for p in (params.get("shared") or []) if p and p.strip() in m["params"]] \
        if isinstance(params.get("shared"), list) else \
        [p.strip() for p in str(params.get("shared") or "").split(",") if p.strip() in m["params"]]

    r = Result(f"Nonlinear fit: {m['name']}")
    curves = []
    names = [table.names[i] for i in idx]
    rows_best = {n: [] for n in m["params"]}
    rows_se = {n: [] for n in m["params"]}
    rows_ci = {n: [] for n in m["params"]}
    gof = {"Degrees of Freedom": [], "R squared": [], "Sum of Squares": [], "Sy.x": [], "AICc": [],
           "Number of points analyzed": []}
    extra_rows = {}
    resid_tables = []
    xs_all = table.x[np.isfinite(table.x)]
    require(len(xs_all) >= 2, "Need at least two X values.")
    xmin, xmax = float(xs_all.min()), float(xs_all.max())
    pad = (xmax - xmin) * 0.02
    xs = np.linspace(xmin - pad, xmax + pad, 200)
    tcrit_cache = {}
    fits = []
    rout_rows = []
    for i in idx:
        x, y = table.xy_points(i, use_means)
        if params.get("rout") and len(x) > len(m["params"]) + 2:
            keep = rout_outliers(m, x, y, constraints, float(params.get("routQ", 1) or 1) / 100)
            for xv, yv in zip(x[~keep], y[~keep]):
                rout_rows.append([table.names[i], xv, yv])
            x, y = x[keep], y[keep]
        if len(x) < len(m["params"]) - len(constraints) + 1 and len(x) < 2:
            r.warn(f"{table.names[i]}: not enough points.")
            for d in (rows_best, rows_se, rows_ci):
                for n in d:
                    d[n].append("")
            for kk in gof:
                gof[kk].append("")
            fits.append(None)
            continue
        try:
            fit = fit_model(mkey, x, y, weights, constraints)
        except Exception as e:  # noqa: BLE001
            r.warn(f"{table.names[i]}: fit did not converge ({e}).")
            for d in (rows_best, rows_se, rows_ci):
                for n in d:
                    d[n].append("Ambiguous")
            for kk in gof:
                gof[kk].append("")
            fits.append(None)
            continue
        fits.append(fit)
        if _ambiguous(fit):
            r.warn(f"{table.names[i]}: the fit is ambiguous (parameters are highly dependent / poorly "
                   "determined). Consider constraining a parameter or choosing a simpler model.")
        df = fit["df"]
        t = tcrit_cache.setdefault(df, stats.t.ppf(0.5 + level / 2, df) if df > 0 else np.nan)
        for n, val in zip(m["params"], fit["full"]):
            rows_best[n].append(val)
            if n in fit["fixed"]:
                rows_se[n].append("(fixed)")
                rows_ci[n].append("")
            else:
                j = fit["free"].index(n)
                se = fit["se"][j]
                rows_se[n].append(se)
                rows_ci[n].append(f"{fmt(val - t * se)} to {fmt(val + t * se)}" if np.isfinite(se) else "")
        for key in [k for k in m["params"] if k.startswith("Log")]:
            extra = key[3:]
            extra_rows.setdefault(extra, []).append(10 ** fit["full"][m["params"].index(key)])
        if m["key"] in ("exp_decay1", "exp_assoc1"):
            k_ = fit["full"][2]
            extra_rows.setdefault("Half-life", []).append(math.log(2) / k_ if k_ else np.nan)
            extra_rows.setdefault("Tau", []).append(1 / k_ if k_ else np.nan)
        if m["key"] == "exp_growth":
            k_ = fit["full"][1]
            extra_rows.setdefault("Doubling time", []).append(math.log(2) / k_ if k_ else np.nan)
        gof["Degrees of Freedom"].append(df)
        gof["R squared"].append(fit["r2"])
        gof["Sum of Squares"].append(fit["ss"])
        gof["Sy.x"].append(fit["sy_x"])
        gof["AICc"].append(fit["aicc"])
        gof["Number of points analyzed"].append(fit["n"])
        yc, lo, hi = curve_with_band(fit, xs, level)
        curves.append({"dataset": i, "x": _clean(xs), "y": _clean(yc), "lo": _clean(lo), "hi": _clean(hi),
                       "label": _fit_label(m, fit)})
        resid_tables.append((i, x, fit["resid"]))

    if params.get("rout"):
        r.table(f"Outliers removed by ROUT (Q = {params.get('routQ', 1)}%)", ["Data set", "X", "Y"],
                rout_rows or [["(none)", "", ""]])
    cols = [""] + names
    r.table("Best-fit values", cols, [[n] + rows_best[n] for n in m["params"]] +
            [[n] + v for n, v in extra_rows.items()])
    r.table("Std. Error", cols, [[n] + rows_se[n] for n in m["params"]])
    r.table(f"{int(level * 100)}% CI (asymptotic)", cols, [[n] + rows_ci[n] for n in m["params"]])
    if params.get("profile"):
        prow = {n: [] for n in m["params"]}
        for i, fit in zip(idx, fits):
            if fit is None:
                for n in prow:
                    prow[n].append("")
                continue
            x_, y_ = table.xy_points(i, use_means)
            if params.get("rout") and len(x_) > len(m["params"]) + 2:
                keep = rout_outliers(m, x_, y_, constraints, float(params.get("routQ", 1) or 1) / 100)
                x_, y_ = x_[keep], y_[keep]
            pci = profile_ci(mkey, fit, x_, y_, weights, constraints, level)
            for n in m["params"]:
                if n in fit["fixed"]:
                    prow[n].append("(fixed)")
                else:
                    lo, hi = pci.get(n, (None, None))
                    prow[n].append(f"{'-∞ (unbounded)' if lo is None else fmt(lo)} to {'+∞ (unbounded)' if hi is None else fmt(hi)}")
        r.table(f"{int(level * 100)}% CI (profile likelihood)", cols, [[n] + prow[n] for n in m["params"]])
        r.warn("Profile-likelihood intervals can be asymmetric and are more accurate than asymptotic intervals for nonlinear "
               "models. 'Unbounded' means the data do not define that limit.")
    r.table("Goodness of Fit", cols, [[k] + v for k, v in gof.items()])
    r.kv("Equation", [("Model", m["name"]), ("Formula", m["formula"]),
                      ("Weighting", {"none": "No weighting", "1/Y^2": "Relative (1/Y²)", "1/Y": "Poisson (1/Y)"}.get(weights, weights)),
                      ("Fit to", "Means of replicates" if use_means else "Each replicate Y value")])

    # Normality of residuals
    rows = []
    for (i, x, res) in resid_tables:
        if len(res) >= 3:
            w, p = stats.shapiro(res)
            rows.append([table.names[i], f"W = {w:.4f}", fmt_p(p), "Yes" if p >= 0.05 else "No"])
    if rows:
        r.table("Normality of Residuals (Shapiro-Wilk)", ["Data set", "W", "P value", "Passed normality?"], rows)

    # Interpolation of unknowns
    if interp:
        irows = []
        for i, fit in zip(idx, fits):
            if fit is None:
                continue
            for yv in interp:
                xv = _invert(fit, yv, xmin, xmax)
                irows.append([table.names[i], yv, xv])
        r.table("Interpolated X values (from Y)", ["Data set", "Y", "X"], irows)

    # Extra sum-of-squares F test against an alternative model
    if compare_key and compare_key in MODELS and compare_key != m["key"]:
        crow = []
        for i, fit in zip(idx, fits):
            if fit is None:
                continue
            x, y = table.xy_points(i, use_means)
            try:
                alt = fit_model(compare_key, x, y, weights)
            except Exception:  # noqa: BLE001
                continue
            simple, compl = (fit, alt) if fit["k"] < alt["k"] else (alt, fit)
            if compl["df"] <= 0 or simple["k"] == compl["k"]:
                continue
            F = ((simple["ss"] - compl["ss"]) / (simple["df"] - compl["df"])) / (compl["ss"] / compl["df"])
            p = float(stats.f.sf(F, simple["df"] - compl["df"], compl["df"]))
            prob = 1 / (1 + math.exp(-0.5 * (simple["aicc"] - compl["aicc"]))) if np.isfinite(simple["aicc"]) and np.isfinite(compl["aicc"]) else np.nan
            crow.append([table.names[i], simple["model_name"], compl["model_name"], F, fmt_p(p),
                         compl["model_name"] if p < 0.05 else simple["model_name"],
                         f"{prob * 100:.2f}%" if np.isfinite(prob) else ""])
        if crow:
            r.table("Comparison of fits (extra sum-of-squares F test, AICc)",
                    ["Data set", "Null (simpler) model", "Alternative model", "F", "P value", "Preferred model",
                     "AICc probability complex model correct"], crow)

    if shared and len([f for f in fits if f is not None]) >= 2:
        g_curves = _global_fit(r, table, idx, fits, m, shared, constraints, use_means, weights, level, xs)
        if g_curves:
            curves = g_curves

    r.overlay = {"kind": "curves", "curves": curves, "showBand": bool(params.get("plotBand", False))}

    # Residuals output table
    if params.get("residualTable") and resid_tables:
        all_x = sorted(set(float(v) for _, x, _ in resid_tables for v in x))
        cells = []
        for xv in all_x:
            row = []
            for (_, x, res) in resid_tables:
                vals = res[np.isclose(x, xv)]
                row.append(vals[0] if len(vals) else None)
            cells.append(row)
        r.output_tables.append(make_table(f"Residuals of {table.name}", "xy",
                                          [{"name": table.names[i], "reps": 1} for i, _, _ in resid_tables],
                                          cells, x=all_x, x_title=table.x_title))
    return r


def profile_ci(mkey, fit, x, y, weights, constraints, level=0.95):
    """Profile-likelihood confidence intervals (as recommended for nonlinear models).

    For each free parameter the value is fixed at trial values and the other
    parameters re-fitted; the CI limits are where the sum of squares reaches
    SSmin * (1 + F(1, df) / df). Returns {name: (lo, hi)}; None means unbounded."""
    names = fit["names"]
    df = fit["df"]
    if df <= 0:
        return {}
    thr = fit["ss"] * (1 + stats.f.ppf(level, 1, df) / df)
    best = list(fit["full"])
    out = {}
    for j, nm in enumerate(fit["free"]):
        pj = fit["popt"][j]
        se = fit["se"][j] if np.isfinite(fit["se"][j]) and fit["se"][j] > 0 else abs(pj) * 0.1 + 1e-6

        def ss_at(v, nm=nm):
            cons = {**(constraints or {}), nm: v}
            init = list(best)
            init[names.index(nm)] = v
            try:
                return fit_model(mkey, x, y, weights, cons, initial=init)["ss"] - thr
            except Exception:  # noqa: BLE001
                return np.inf
        lims = []
        for direction in (-1, 1):
            step = se
            inner = pj
            found = None
            for _ in range(40):
                v = pj + direction * step
                val = ss_at(v)
                if val > 0:
                    try:
                        a, b = sorted((inner, v))
                        found = optimize.brentq(lambda t: ss_at(t), a, b, xtol=abs(se) * 1e-4 + 1e-12, maxiter=60)
                    except Exception:  # noqa: BLE001
                        found = v
                    break
                inner = v
                step *= 1.8
            lims.append(found)
        out[nm] = (lims[0], lims[1])
    return out


def rout_outliers(m, x, y, constraints, q):
    """ROUT (Motulsky & Brown 2006): robust fit with a Cauchy/Lorentzian loss, then
    flag points whose residuals are significant at false discovery rate Q."""
    names = m["params"]
    fixed = {k: float(v) for k, v in (constraints or {}).items() if str(v).strip() != "" and k in names}
    free = [n for n in names if n not in fixed]
    p0_all = [float(v) if np.isfinite(v) else 1.0 for v in m["guess"](x, y)]
    p0 = [p0_all[names.index(n)] for n in free]
    f = m["f"]

    def full(pf):
        d = dict(zip(free, pf))
        return [d.get(n, fixed.get(n)) for n in names]
    with quiet():
        scale = max(float(np.median(np.abs(y - np.median(y)))) * 0.1, 1e-12)
        sol = optimize.least_squares(lambda pf: f(x, *full(pf)) - y, p0, loss="cauchy", f_scale=scale, max_nfev=20000)
    res = y - f(x, *full(sol.x))
    n, k = len(y), len(free)
    rsdr = np.percentile(np.abs(res), 68.27) * n / max(n - k, 1)
    if rsdr <= 0:
        return np.ones(n, bool)
    t = np.abs(res) / rsdr
    p = 2 * stats.t.sf(t, max(n - k, 1))
    order = np.argsort(p)
    keep = np.ones(n, bool)
    for rank, j in enumerate(order, start=1):
        if p[j] <= q * rank / n:
            keep[j] = False
    return keep


def _fit_label(m, fit):
    parts = []
    for n, v in zip(m["params"], fit["full"]):
        if n.startswith("Log") and n[3:]:
            parts.append(f"{n[3:]} = {10 ** v:.3g}")
    if m["key"] == "line":
        parts.append(f"Y = {fmt(fit['full'][1])}X + {fmt(fit['full'][0])}")
    if m["key"] in ("mm", "onesite_total"):
        parts.append(f"{m['params'][1]} = {fmt(fit['full'][1])}")
    parts.append(f"R² = {fit['r2']:.4f}")
    return ", ".join(parts)


def _global_fit(r, table, idx, fits, m, shared, constraints, use_means, weights, level, xs):
    """Fit all data sets at once with some parameters shared, and test whether
    sharing is justified (extra sum-of-squares F test vs. separate fits)."""
    names = m["params"]
    fixed = {k: float(v) for k, v in (constraints or {}).items() if str(v).strip() != "" and k in names}
    local = [n for n in names if n not in shared and n not in fixed]
    shr = [n for n in shared if n not in fixed]
    data = []
    for i, fit in zip(idx, fits):
        if fit is None:
            continue
        x, y = table.xy_points(i, use_means)
        data.append((i, x, y, fit))
    # parameter vector: shared params first, then local params for each data set
    p0 = [float(np.mean([d[3]["full"][names.index(n)] for d in data])) for n in shr]
    for d in data:
        p0 += [float(d[3]["full"][names.index(n)]) for n in local]
    f = m["f"]

    def unpack(p, j):
        vals = dict(zip(shr, p[:len(shr)]))
        off = len(shr) + j * len(local)
        vals.update(zip(local, p[off:off + len(local)]))
        vals.update(fixed)
        return [vals[n] for n in names]

    def sig_w(y):
        if weights == "1/Y^2":
            return np.where(np.abs(y) > 0, np.abs(y), 1e-12)
        if weights == "1/Y":
            return np.sqrt(np.where(np.abs(y) > 0, np.abs(y), 1e-12))
        return np.ones_like(y)

    def resid(p):
        return np.concatenate([(d[2] - f(d[1], *unpack(p, j))) / sig_w(d[2]) for j, d in enumerate(data)])

    with quiet():
        sol = optimize.least_squares(resid, p0, method="lm", max_nfev=20000)
    res = sol.fun
    ss = float((res ** 2).sum())
    n = len(res)
    k = len(p0)
    df = n - k
    try:
        cov = np.linalg.inv(sol.jac.T @ sol.jac) * (ss / df) if df > 0 else np.full((k, k), np.nan)
    except np.linalg.LinAlgError:
        cov = np.full((k, k), np.nan)
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    t = stats.t.ppf(0.5 + level / 2, df) if df > 0 else np.nan
    cols = [""] + [table.names[d[0]] for d in data]
    best, ses = [], []
    for nme in names:
        row_b, row_s = [nme + (" (shared)" if nme in shr else "")], [nme]
        for j, _ in enumerate(data):
            row_b.append(unpack(sol.x, j)[names.index(nme)])
            if nme in fixed:
                row_s.append("(fixed)")
            elif nme in shr:
                row_s.append(se[shr.index(nme)])
            else:
                row_s.append(se[len(shr) + j * len(local) + local.index(nme)])
        best.append(row_b)
        ses.append(row_s)
    r.table(f"Global fit — shared: {', '.join(shared)}", cols, best)
    r.table("Global fit — Std. Error", cols, ses)
    ci = []
    for nme in shr:
        v, e = sol.x[shr.index(nme)], se[shr.index(nme)]
        ci.append([nme, v, f"{fmt(v - t * e)} to {fmt(v + t * e)}"])
    if ci:
        r.table(f"Shared parameters with {int(level * 100)}% CI", ["Parameter", "Best-fit value", "CI"], ci)
    ss_sep = sum(d[3]["ss"] for d in data)
    df_sep = sum(d[3]["df"] for d in data)
    if df > df_sep and ss_sep > 0 and df_sep > 0:
        F = ((ss - ss_sep) / (df - df_sep)) / (ss_sep / df_sep)
        p = float(stats.f.sf(F, df - df_sep, df_sep))
        r.kv("Do the shared parameters differ between data sets?", [
            ("Null hypothesis", f"{', '.join(shared)} the same for all data sets"),
            ("Alternative hypothesis", "Different for each data set"),
            ("F (DFn, DFd)", f"{fmt(F)} ({df - df_sep}, {df_sep})"), ("P value", fmt_p(p)),
            ("Conclusion", "Reject null: parameters differ (use separate fits)" if p < 0.05
             else "Do not reject null: one shared value fits all data sets"),
            ("Global sum of squares", ss), ("Separate fits sum of squares", ss_sep),
        ])
    curves = []
    for j, d in enumerate(data):
        pv = unpack(sol.x, j)
        curves.append({"dataset": d[0], "x": _clean(xs), "y": _clean(f(xs, *pv)), "lo": None, "hi": None,
                       "label": "global fit"})
    return curves


def _ambiguous(fit):
    C = fit["pcov"]
    if fit["k"] < 2:
        return False
    if not np.all(np.isfinite(C)):
        return True
    try:
        Ci = np.linalg.inv(C)
    except np.linalg.LinAlgError:
        return True
    dep = 1 - 1 / (np.diag(C) * np.diag(Ci))
    return bool(np.nanmax(dep) > 0.9999)


def _invert(fit, yv, xmin, xmax):
    """Find X such that f(X) = yv, preferring roots inside the data range and
    rejecting sign changes caused by poles / discontinuities."""
    g = fit["g"]
    p = fit["popt"]
    span = (xmax - xmin) or 1.0
    f1 = lambda xx: float(g(np.array([xx]), *p)[0]) - yv  # noqa: E731
    with quiet():
        yspan = np.ptp(g(np.linspace(xmin, xmax, 200), *p)) or 1.0
    for lo, hi in ((xmin, xmax), (xmin - span, xmax + span)):
        grid = np.linspace(lo, hi, 4001)
        with quiet():
            vals = g(grid, *p) - yv
        idx = np.where(np.isfinite(vals[:-1]) & np.isfinite(vals[1:]) & (np.sign(vals[:-1]) != np.sign(vals[1:])))[0]
        # nearest to the data range centre first
        idx = sorted(idx, key=lambda k: abs(grid[k] - (xmin + xmax) / 2))
        for k in idx:
            try:
                root = optimize.brentq(f1, grid[k], grid[k + 1])
            except Exception:  # noqa: BLE001
                continue
            if abs(f1(root)) <= 1e-6 * max(1.0, abs(yv), yspan):
                return root
    return "Out of range"


def _clean(a):
    if a is None:
        return None
    return [float(v) if np.isfinite(v) else None for v in a]


def linear(table, params):
    require(table.type == "xy", "Linear regression requires an XY table.")
    idx = selected(table, params)
    level = float(params.get("ci", 0.95))
    use_means = bool(params.get("fitMeans", False))
    through_origin = bool(params.get("throughOrigin", False))
    r = Result("Simple linear regression")
    names = [table.names[i] for i in idx]
    rows = {k: [] for k in ["Slope", "Y-intercept", "X-intercept", "1/Slope", "Slope SE", "Y-intercept SE",
                            f"{int(level * 100)}% CI slope", f"{int(level * 100)}% CI Y-intercept",
                            "R squared", "Sy.x", "F", "DFn, DFd", "P value", "Deviation from zero?",
                            "Equation", "Number of X values", "Runs test P value"]}
    curves = []
    slope_info = []
    xs_all = table.x[np.isfinite(table.x)]
    require(len(xs_all) >= 2, "Need at least 2 X values.")
    xs = np.linspace(xs_all.min(), xs_all.max(), 100)
    for i in idx:
        x, y = table.xy_points(i, use_means)
        if len(x) < 3:
            r.warn(f"{table.names[i]}: needs at least 3 points.")
            for k in rows:
                rows[k].append("")
            continue
        n = len(x)
        if through_origin:
            b1 = (x * y).sum() / (x * x).sum()
            b0 = 0.0
            res = y - b1 * x
            df = n - 1
            s2 = (res ** 2).sum() / df
            se1 = math.sqrt(s2 / (x * x).sum())
            se0 = np.nan
            sst = (y ** 2).sum()
        else:
            lr = stats.linregress(x, y)
            b1, b0 = lr.slope, lr.intercept
            res = y - (b0 + b1 * x)
            df = n - 2
            s2 = (res ** 2).sum() / df
            se1, se0 = lr.stderr, lr.intercept_stderr
            sst = ((y - y.mean()) ** 2).sum()
        ss = (res ** 2).sum()
        r2 = 1 - ss / sst if sst > 0 else np.nan
        t = stats.t.ppf(0.5 + level / 2, df)
        F = (b1 / se1) ** 2 if se1 > 0 else np.inf
        p = float(stats.f.sf(F, 1, df))
        rows["Slope"].append(b1)
        rows["Y-intercept"].append(b0)
        rows["X-intercept"].append(-b0 / b1 if b1 else np.nan)
        rows["1/Slope"].append(1 / b1 if b1 else np.nan)
        rows["Slope SE"].append(se1)
        rows["Y-intercept SE"].append(se0)
        rows[f"{int(level * 100)}% CI slope"].append(f"{fmt(b1 - t * se1)} to {fmt(b1 + t * se1)}")
        rows[f"{int(level * 100)}% CI Y-intercept"].append(
            f"{fmt(b0 - t * se0)} to {fmt(b0 + t * se0)}" if np.isfinite(se0) else "")
        rows["R squared"].append(r2)
        rows["Sy.x"].append(math.sqrt(s2))
        rows["F"].append(F)
        rows["DFn, DFd"].append(f"1, {df}")
        rows["P value"].append(fmt_p(p))
        rows["Deviation from zero?"].append("Significant" if p < 0.05 else "Not significant")
        rows["Equation"].append(f"Y = {fmt(b1)}*X + {fmt(b0)}")
        rows["Number of X values"].append(len(np.unique(x)))
        rows["Runs test P value"].append(fmt_p(_runs_test(x, res)))
        yc = b0 + b1 * xs
        sxx = ((x - x.mean()) ** 2).sum()
        h = t * np.sqrt(s2 * (1 / n + (xs - x.mean()) ** 2 / sxx)) if not through_origin else \
            t * np.sqrt(s2 * xs ** 2 / (x * x).sum())
        curves.append({"dataset": i, "x": _clean(xs), "y": _clean(yc), "lo": _clean(yc - h), "hi": _clean(yc + h),
                       "label": f"Y = {fmt(b1)}X {'+' if b0 >= 0 else '-'} {fmt(abs(b0))}, R² = {r2:.4f}"})
        slope_info.append((b1, se1, df, ss, x, y))
    r.table("Best-fit values", [""] + names, [[k] + v for k, v in rows.items()])

    if len(slope_info) >= 2 and not through_origin:
        # ANCOVA style test: are slopes equal?
        ss_sep = sum(s[3] for s in slope_info)
        df_sep = sum(s[2] for s in slope_info)
        Xs = np.concatenate([s[4] for s in slope_info])
        Ys = np.concatenate([s[5] for s in slope_info])
        gid = np.concatenate([[j] * len(s[4]) for j, s in enumerate(slope_info)])
        # common slope, separate intercepts
        xc = np.concatenate([s[4] - s[4].mean() for s in slope_info])
        yc_ = np.concatenate([s[5] - s[5].mean() for s in slope_info])
        b_common = (xc * yc_).sum() / (xc * xc).sum()
        ss_common = ((yc_ - b_common * xc) ** 2).sum()
        df_common = len(Xs) - len(slope_info) - 1
        Fs = ((ss_common - ss_sep) / (df_common - df_sep)) / (ss_sep / df_sep)
        ps = float(stats.f.sf(Fs, df_common - df_sep, df_sep))
        out = [("Are the slopes equal?", ""), ("F (DFn, DFd)", f"{fmt(Fs)} ({df_common - df_sep}, {df_sep})"),
               ("P value", fmt_p(ps)), ("Conclusion", "Slopes differ significantly" if ps < 0.05 else
                                        "Slopes not significantly different")]
        if ps >= 0.05:
            lr = stats.linregress(Xs, Ys)
            ss_one = ((Ys - (lr.intercept + lr.slope * Xs)) ** 2).sum()
            df_one = len(Xs) - 2
            Fi = ((ss_one - ss_common) / (df_one - df_common)) / (ss_common / df_common)
            pi = float(stats.f.sf(Fi, df_one - df_common, df_common))
            out += [("Are the elevations or intercepts equal?", ""),
                    ("F (DFn, DFd)", f"{fmt(Fi)} ({df_one - df_common}, {df_common})"), ("P value", fmt_p(pi)),
                    ("Pooled slope", b_common)]
        r.kv("Comparison of regression lines", out)
        del gid
    r.overlay = {"kind": "curves", "curves": curves, "showBand": bool(params.get("plotBand", False))}
    return r


def _runs_test(x, res):
    order = np.argsort(x)
    s = np.sign(res[order])
    s = s[s != 0]
    if len(s) < 3:
        return np.nan
    n1, n2 = (s > 0).sum(), (s < 0).sum()
    if n1 == 0 or n2 == 0:
        return np.nan
    runs = 1 + (np.diff(s) != 0).sum()
    mu = 2 * n1 * n2 / (n1 + n2) + 1
    var = 2 * n1 * n2 * (2 * n1 * n2 - n1 - n2) / ((n1 + n2) ** 2 * (n1 + n2 - 1))
    if var <= 0:
        return np.nan
    z = (runs - mu) / math.sqrt(var)
    return float(stats.norm.cdf(z))  # one-tailed: too few runs


def correlation(table, params):
    method = params.get("method", "pearson")
    alpha = float(params.get("alpha", 0.05))
    if table.type == "xy" and not params.get("matrix"):
        series = [("X", table.x)] + [(table.names[i], table.row_means(i)) for i in selected(table, params)]
    else:
        idx = selected(table, params)
        series = [(table.names[i], table.Y[i][:, 0] if table.Y[i].shape[1] == 1 else table.row_means(i)) for i in idx]
    require(len(series) >= 2, "Need at least two variables.")
    r = Result({"pearson": "Correlation (Pearson r)", "spearman": "Correlation (Spearman r)", "kendall": "Correlation (Kendall τ-b)"}.get(method, "Correlation"))
    names = [s[0] for s in series]
    k = len(series)
    R = np.full((k, k), np.nan)
    rows = []
    for a in range(k):
        for b in range(k):
            va, vb = series[a][1], series[b][1]
            m = np.isfinite(va) & np.isfinite(vb)
            if m.sum() < 3:
                continue
            if method == "spearman":
                rr, p = stats.spearmanr(va[m], vb[m])
            elif method == "kendall":
                rr, p = stats.kendalltau(va[m], vb[m])
            else:
                rr, p = stats.pearsonr(va[m], vb[m])
            R[a, b] = rr
            if b > a and (table.type != "xy" or a == 0 or params.get("matrix")):
                n = m.sum()
                z = np.arctanh(np.clip(rr, -0.999999, 0.999999))
                se = 1 / math.sqrt(n - 3) if n > 3 else np.nan
                if method == "spearman" and n > 3:
                    se = math.sqrt((1 + rr ** 2 / 2) / (n - 3))  # Bonett & Wright (2000)
                elif method == "kendall" and n > 4:
                    se = math.sqrt(0.437 / (n - 4))  # Fieller, Hartley & Pearson (1957)
                zc = stats.norm.ppf(1 - alpha / 2)
                lo, hi = np.tanh(z - zc * se), np.tanh(z + zc * se)
                rows.append([f"{names[a]} vs. {names[b]}", rr, f"{fmt(lo)} to {fmt(hi)}", rr ** 2, fmt_p(p),
                             stars(p, alpha), sig(p, alpha), int(n)])
    r.table("Correlation", ["Pair", "r", f"{int((1 - alpha) * 100)}% CI", "R squared", "P (two-tailed)", "Summary",
                            "Significant?", "Number of XY pairs"], rows)
    r.table("Correlation matrix", [""] + names, [[names[a]] + list(R[a]) for a in range(k)])
    z = [[None if not np.isfinite(v) else float(v) for v in row] for row in R]
    r.overlay = {"kind": "plot", "plots": [{"title": "Correlation matrix", "xTitle": "", "yTitle": "", "yReversed": True,
                                            "traces": [{"type": "heatmap", "z": z, "x": names, "y": names, "zmin": -1, "zmax": 1}]}]}
    return r


def auc(table, params):
    require(table.type == "xy", "Area under curve requires an XY table.")
    idx = selected(table, params)
    baseline = float(params.get("baseline", 0) or 0)
    r = Result("Area under curve")
    rows = {k: [] for k in ["Baseline", "Total Area", "Std. Error", "95% CI", "Total Peak Area",
                            "Number of Peaks", "Peak X", "Peak Y"]}
    for i in idx:
        x = table.x
        y = table.row_means(i)
        reps = np.isfinite(table.Y[i]).sum(axis=1)
        sd = np.nanstd(table.Y[i], axis=1, ddof=1) if table.Y[i].shape[1] > 1 else np.zeros_like(y)
        m = np.isfinite(x) & np.isfinite(y)
        x, y, sd, reps = x[m], y[m], sd[m], reps[m]
        o = np.argsort(x)
        x, y, sd, reps = x[o], y[o], sd[o], reps[o]
        if len(x) < 2:
            for k in rows:
                rows[k].append("")
            continue
        yb = y - baseline
        area = float(np.trapezoid(yb, x))
        # SE of area (Gagnon & Peterson 1998)
        dx = np.diff(x)
        w = np.zeros(len(x))
        w[:-1] += dx / 2
        w[1:] += dx / 2
        with quiet():
            sem2 = np.where(reps > 1, np.nan_to_num(sd) ** 2 / np.maximum(reps, 1), 0)
        se = math.sqrt(float((w ** 2 * sem2).sum()))
        pos = np.clip(yb, 0, None)
        peak_area = float(np.trapezoid(pos, x))
        above = yb > 0
        npk = int((np.diff(above.astype(int)) == 1).sum() + (1 if above[0] else 0))
        j = int(np.argmax(y))
        rows["Baseline"].append(baseline)
        rows["Total Area"].append(area)
        rows["Std. Error"].append(se)
        rows["95% CI"].append(f"{fmt(area - 1.96 * se)} to {fmt(area + 1.96 * se)}")
        rows["Total Peak Area"].append(peak_area)
        rows["Number of Peaks"].append(npk)
        rows["Peak X"].append(x[j])
        rows["Peak Y"].append(y[j])
    r.table("Area under curve", [""] + [table.names[i] for i in idx], [[k] + v for k, v in rows.items()])
    return r


def roc(table, params):
    idx = selected(table, params)
    require(len(idx) >= 2, "ROC needs two data sets: controls (first) and patients (second).")
    ctrl, pat = table.column_values(idx[0]), table.column_values(idx[1])
    require(len(ctrl) > 0 and len(pat) > 0, "Both groups need values.")
    higher = params.get("direction", "higher") == "higher"
    if not higher:
        ctrl, pat = -ctrl, -pat
    U = stats.mannwhitneyu(pat, ctrl).statistic
    A = U / (len(ctrl) * len(pat))
    n1, n2 = len(pat), len(ctrl)
    q1, q2 = A / (2 - A), 2 * A * A / (1 + A)
    se = math.sqrt((A * (1 - A) + (n1 - 1) * (q1 - A * A) + (n2 - 1) * (q2 - A * A)) / (n1 * n2))
    z = (A - 0.5) / se if se > 0 else np.inf
    p = float(2 * stats.norm.sf(abs(z)))
    thresholds = np.unique(np.concatenate([ctrl, pat]))
    pts = []
    rows = []
    for th in np.concatenate([[-np.inf], thresholds, [np.inf]]):
        sens = (pat > th).mean()
        spec = (ctrl <= th).mean()
        pts.append((1 - spec, sens))
        if np.isfinite(th):
            lr = sens / (1 - spec) if spec < 1 else np.inf
            rows.append([f"> {fmt(th if higher else -th)}", sens * 100, spec * 100, lr])
    pts = sorted(set(pts))
    r = Result("ROC curve")
    r.kv("Area under the ROC curve", [("Area", A), ("Std. Error", se),
                                      ("95% confidence interval", f"{fmt(max(0, A - 1.96 * se))} to {fmt(min(1, A + 1.96 * se))}"),
                                      ("P value", fmt_p(p)), ("Controls (n)", n2), ("Patients (n)", n1)])
    r.table("Sensitivity and specificity", ["Cutoff", "Sensitivity %", "Specificity %", "Likelihood ratio"], rows)
    r.overlay = {"kind": "roc", "x": [float(a) * 100 for a, _ in pts], "y": [float(b) * 100 for _, b in pts], "auc": A}
    return r
