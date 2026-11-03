"""Competing risks: Gray's K-sample test and the Fine-Gray subdistribution hazards model.

Written from the published formulas:

* Gray RJ (1988). A class of K-sample tests for comparing the cumulative
  incidence of a competing risk. Annals of Statistics 16:1141-1154
  (notation as restated in the SAS/STAT PROC LIFETEST documentation).
* Fine JP, Gray RJ (1999). A proportional hazards model for the
  subdistribution of a competing risk. JASA 94:496-509 (weights, pseudo
  likelihood and the sandwich variance with the censoring term psi_i).

Event codes: 0 = censored, ``cause`` (default 1) = event of interest, any
other positive code = competing event. Validated against R cmprsk
(cuminc()$Tests and crr()).
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from .common import require


def _km_censoring(t, censored):
    """Kaplan-Meier of the censoring distribution, returned as G(s) for any s (right-continuous)."""
    times = np.unique(t[censored])
    G = []
    s = 1.0
    for u in times:
        n = (t >= u).sum()
        s *= 1 - ((t == u) & censored).sum() / n
        G.append(s)
    G = np.array(G)

    def at(x, left=False):
        x = np.asarray(x, float)
        k = np.searchsorted(times, x, side="left" if left else "right")
        out = np.ones_like(x)
        out[k > 0] = G[k[k > 0] - 1]
        return out
    return at


# ---------------------------------------------------------------- Gray's test
def gray_test(t, code, group, cause=1, rho=0.0):
    """Gray's K-sample test for equality of the cumulative incidence of ``cause``.

    Score: z_k = sum_t L(t) [d_1k(t) - R_k(t) d_1.(t) / R.(t)] with the
    subdistribution risk sets R_k(t) = Y_k(t) (1 - F_1k(t-)) / S_k(t-).
    Covariance: Gray's (1988) estimator under H0, with h_r = Y_r / S_r(t-),
    the pooled cumulative incidence dF0 = d_1. / h., and the cause-1 and
    cause-2 martingale terms of the Aalen-Johansen estimator. Results agree
    with R cmprsk::cuminc to ~14 significant digits without ties (about 5
    with tied event times).

    Returns (chi-square, df, P, z vector, covariance, group labels)."""
    t = np.asarray(t, float)
    code = np.asarray(code, int)
    labels = list(dict.fromkeys(group))
    gi = np.array([labels.index(g) for g in group])
    K = len(labels)
    require(K >= 2, "Gray's test needs at least two groups.")
    ev1 = code == cause
    ev2 = (code > 0) & ~ev1
    require(ev1.any(), "There are no events of the chosen type.")
    times = np.unique(t[code > 0])                       # all failure times (any cause)
    m = len(times)
    Y = np.zeros((K, m))
    d1 = np.zeros((K, m))
    d2 = np.zeros((K, m))
    for k in range(K):
        tk, e1, e2 = t[gi == k], ev1[gi == k], ev2[gi == k]
        Y[k] = (tk[None, :] >= times[:, None]).sum(1)
        d1[k] = ((tk[None, :] == times[:, None]) & e1[None, :]).sum(1)
        d2[k] = ((tk[None, :] == times[:, None]) & e2[None, :]).sum(1)
    tau = np.array([t[gi == k].max() for k in range(K)])  # last observation time of each group
    inside = times[None, :] <= tau[:, None]
    Ysafe = np.where(Y > 0, Y, 1)
    S = np.cumprod(1 - (d1 + d2) / Ysafe, axis=1)        # S_k(t), all-cause Kaplan-Meier
    Sm = np.hstack([np.ones((K, 1)), S[:, :-1]])          # S_k(t-)
    F1 = np.cumsum(Sm * d1 / Ysafe, axis=1)               # Aalen-Johansen F_1k(t)
    F1m = np.hstack([np.zeros((K, 1)), F1[:, :-1]])
    ok = inside & (Sm > 0)
    Smsafe = np.where(Sm > 0, Sm, 1)
    R = np.where(ok, Y * (1 - F1m) / Smsafe, 0.0)
    h = np.where(ok, Y / Smsafe, 0.0)
    Rdot, hdot = R.sum(0), h.sum(0)
    d1dot = d1.sum(0)
    dGam0 = np.where(Rdot > 0, d1dot / np.where(Rdot > 0, Rdot, 1), 0.0)   # pooled subdistribution hazard
    dF0 = np.where(hdot > 0, d1dot / np.where(hdot > 0, hdot, 1), 0.0)     # pooled cumulative incidence (H0)
    G0 = 1 - np.cumsum(dF0)
    G0m = np.concatenate([[1.0], G0[:-1]])
    L = (G0m ** rho) if rho else np.ones(m)
    z = np.array([(L * inside[k] * (d1[k] - R[k] * dGam0)).sum() for k in range(K)])
    frac = np.where(hdot > 0, h / np.where(hdot > 0, hdot, 1), 0.0)
    Ydot = Y.sum(0)
    V = np.zeros((K, K))
    for r in range(K):
        a = np.zeros((K, m))
        b = np.zeros((K, m))
        ratio = np.where(S[r] > 0, G0 / np.where(S[r] > 0, S[r], 1), 0.0)
        for k in range(K):
            dk = np.where(inside[k], L * h[k] * ((k == r) - frac[r]), 0.0)
            c = np.cumsum(dk * dF0 / np.where(G0m > 0, G0m, 1))
            ctau = c[inside[k]][-1] if inside[k].any() else 0.0
            a[k] = dk + (1 - ratio) * (ctau - c)
            b[k] = -ratio * (ctau - c)
        hr = np.where(h[r] > 0, h[r], np.inf)
        # dF0 / h_r and dF_2r / h_r, with the usual (n - d) / (n - 1) correction for tied events
        w1 = dF0 / hr * np.where(Ydot > 1, (Ydot - d1dot) / np.maximum(Ydot - 1, 1), 1.0)
        w2 = (Sm[r] * d2[r] / Ysafe[r]) / hr * np.where(Y[r] > 1, (Y[r] - d2[r]) / np.maximum(Y[r] - 1, 1), 1.0)
        for k in range(K):
            for k2 in range(K):
                lim = inside[k] & inside[k2]
                V[k, k2] += ((a[k] * a[k2] * w1 + b[k] * b[k2] * w2) * lim).sum()
    zz, VV = z[:-1], V[:-1, :-1]
    chi = float(zz @ np.linalg.solve(VV, zz))
    df = K - 1
    return chi, df, float(stats.chi2.sf(chi, df)), z, V, labels


# ---------------------------------------------------------------- Fine-Gray
def fine_gray(t, code, Z, cause=1, maxiter=50, tol=1e-10):
    """Fine-Gray proportional subdistribution hazards regression.

    Returns dict(beta, var (sandwich), naive_var, loglik, loglik0, n, events)."""
    t = np.asarray(t, float)
    code = np.asarray(code, int)
    Z = np.asarray(Z, float).reshape(len(t), -1)
    n, p = Z.shape
    ev = code == cause
    cens = code == 0
    require(ev.sum() >= 2, "Need at least two events of interest.")
    G = _km_censoring(t, cens)
    utimes = np.unique(t[ev])
    K = len(utimes)
    dk = np.array([((t == u) & ev).sum() for u in utimes])
    # weights W[j, k] = w_j(u_k) * Y_j(u_k)
    Gu = G(utimes, left=True)
    GX = G(t, left=True)
    W = np.zeros((n, K))
    atrisk = t[:, None] >= utimes[None, :]
    W[atrisk] = 1.0
    comp = (~ev & ~cens)[:, None] & ~atrisk
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(GX[:, None] > 0, Gu[None, :] / GX[:, None], 0.0)
    W[comp] = np.broadcast_to(ratio, W.shape)[comp]
    # Z at each event (sum over tied events)
    Zev = np.array([Z[(t == u) & ev].sum(0) for u in utimes])   # K x p

    def parts(beta):
        eta = Z @ beta
        r = np.exp(eta - eta.max())
        scale = math.exp(eta.max())
        S0 = (W * r[:, None]).sum(0)                       # K
        S1 = (W * r[:, None]).T @ Z                        # K x p
        S2 = np.einsum("jk,j,ja,jb->kab", W, r, Z, Z)      # K x p x p
        Zbar = S1 / S0[:, None]
        ll = float((Zev @ beta).sum() - (dk * (np.log(S0) + math.log(scale))).sum())
        U = (Zev - dk[:, None] * Zbar).sum(0)
        I = (dk[:, None, None] * (S2 / S0[:, None, None] - np.einsum("ka,kb->kab", Zbar, Zbar))).sum(0)
        return ll, U, I, r * scale, S0 * scale, Zbar

    beta = np.zeros(p)
    ll0 = parts(beta)[0]
    ll = ll0
    for _ in range(maxiter):
        ll, U, I, *_ = parts(beta)
        step = np.linalg.solve(I, U)
        # step halving keeps the pseudo-likelihood increasing
        for _h in range(30):
            nb = beta + step
            if parts(nb)[0] >= ll - 1e-12:
                break
            step /= 2
        beta = nb
        if np.max(np.abs(step)) < tol:
            break
    ll, U, I, er, S0, Zbar = parts(beta)
    Iinv = np.linalg.inv(I)
    dL = dk / S0                                           # baseline subdistribution hazard increments
    # eta_i = sum_k (Z_i - Zbar_k) W_ik [dN_i(u_k) - e^{bZ_i} dL_k]
    dN = (t[:, None] == utimes[None, :]) & ev[:, None]
    dM = dN - W * er[:, None] * dL[None, :]                # w_i dM_i (W already contains w_i Y_i)
    eta = np.einsum("ik,ika->ia", dM, Z[:, None, :] - Zbar[None, :, :])
    # psi_i = sum_u q(u)/pi(u) dM^c_i(u); q(u) = -sum_j sum_k (Z_j - Zbar_k) w_j dM_j(u_k) I(u_k >= u > X_j)
    ctimes = np.unique(t[cens])
    psi = np.zeros((n, p))
    if len(ctimes):
        contrib = dM[:, :, None] * (Z[:, None, :] - Zbar[None, :, :])   # n x K x p
        pi = (t[None, :] >= ctimes[:, None]).sum(1)
        dLc = np.array([((t == u) & cens).sum() for u in ctimes]) / pi
        for c_i, u in enumerate(ctimes):
            sel = (t < u)[:, None] & (utimes >= u)[None, :]
            q = -(contrib * sel[:, :, None]).sum((0, 1))
            dMc = ((t == u) & cens).astype(float) - (t >= u) * dLc[c_i]
            psi += np.outer(dMc, q / pi[c_i])
    Sig = (eta + psi).T @ (eta + psi)
    var = Iinv @ Sig @ Iinv
    return {"beta": beta, "var": var, "naive_var": Iinv, "loglik": ll, "loglik0": ll0, "n": n, "events": int(ev.sum()),
            "competing": int((~ev & ~cens).sum()), "censored": int(cens.sum())}


# ---------------------------------------------------------------- analyses (table interface)
def gray_section(r, table, idx, cause=1):
    """Add Gray's test comparing the cumulative incidence across the selected survival-table columns."""
    from .common import fmt, fmt_p
    tt, cc, gg = [], [], []
    for i in idx:
        ev = table.Y[i][:, 0]
        m = np.isfinite(table.x) & np.isfinite(ev)
        tt.append(table.x[m])
        cc.append(ev[m].astype(int))
        gg += [table.names[i]] * int(m.sum())
    t, code = np.concatenate(tt), np.concatenate(cc)
    rows = []
    for c in sorted(set(code[code > 0].tolist())):
        if not np.any(code == c):
            continue
        chi, df, p, *_ = gray_test(t, code, gg, cause=c)
        lab = "Event of interest (code 1)" if c == cause else f"Competing event (code {c})"
        rows.append([lab, chi, df, fmt_p(p)])
    r.table("Gray's test: are the cumulative incidence curves the same in all groups?", ["Event type", "χ²", "df", "P value"], rows)
    return rows


def fine_gray_analysis(table, params):
    from .common import Result, fmt, fmt_p, stars
    from .multivariate import _forest, _pick, _var

    require(table.type == "multi", "Fine-Gray regression needs a Multiple variables table (time, event code, covariates).")
    tvar = int(_pick(params, "timeVar", 0))
    evar = int(_pick(params, "eventVar", 1))
    cause = int(_pick(params, "cause", 1))
    preds = [int(p) for p in (params.get("predictors") or []) if int(p) not in (tvar, evar)]
    if not preds:
        preds = [i for i in range(len(table.Y)) if i not in (tvar, evar)]
    require(preds, "Choose at least one covariate.")
    M = np.column_stack([_var(table, tvar), _var(table, evar)] + [_var(table, j) for j in preds])
    M = M[np.all(np.isfinite(M), axis=1)]
    require(len(M) > len(preds) + 2, "Not enough complete rows.")
    t, code, X = M[:, 0], M[:, 1], M[:, 2:]
    require(np.all(code == np.round(code)) and np.all(code >= 0), "Event codes must be whole numbers: 0 = censored, 1 = event of interest, 2 (or more) = competing event.")
    require(np.any(code == cause), f"No events with code {cause}.")
    require(np.all(t >= 0), "Times cannot be negative.")
    code = code.astype(int)
    names = [table.names[j] for j in preds]
    alpha = float(params.get("alpha", 0.05))
    f = fine_gray(t, code, X, cause=cause)
    se = np.sqrt(np.diag(f["var"]))
    q = stats.norm.ppf(1 - alpha / 2)
    rows = []
    lo, hi = [], []
    for k, nm in enumerate(names):
        b = f["beta"][k]
        zv = b / se[k]
        p = float(2 * stats.norm.sf(abs(zv)))
        lo.append(math.exp(b - q * se[k]))
        hi.append(math.exp(b + q * se[k]))
        rows.append([nm, b, se[k], math.exp(b), f"{fmt(lo[-1])} to {fmt(hi[-1])}", zv, fmt_p(p), stars(p, alpha)])
    r = Result("Fine-Gray competing-risks regression")
    r.table("Subdistribution hazard ratios (robust standard errors)", ["Covariate", "β", "Std. error", "SHR", f"{int(round((1 - alpha) * 100))}% CI", "z", "P value", "Summary"], rows)
    bb = f["beta"]
    W = float(bb @ np.linalg.solve(f["var"], bb))
    lr = 2 * (f["loglik"] - f["loglik0"])
    r.kv("Model", [("Subjects", f["n"]), (f"Events of interest (code {cause})", f["events"]), ("Competing events", f["competing"]), ("Censored", f["censored"]),
                   ("Pseudo log-likelihood", f["loglik"]), ("Pseudo log-likelihood (no covariates)", f["loglik0"]),
                   ("Wald χ² (df), robust", f"{fmt(W)} ({len(names)})"), ("Wald P value", fmt_p(float(stats.chi2.sf(W, len(names))))),
                   ("Pseudo likelihood-ratio χ²", lr)])
    r.kv("How to read this", [("SHR", "Subdistribution hazard ratio: SHR > 1 means a higher cumulative incidence of the event of interest per unit of the covariate, accounting for competing events."),
                              ("Not a cause-specific HR", "For effects on the event rate among subjects still event-free, fit a Cox model with competing events coded as censored."),
                              ("Standard errors", "Robust (sandwich) variance including the estimated censoring distribution (Fine & Gray 1999); the pseudo likelihood-ratio statistic is not χ²-distributed, use the Wald test.")])
    r.overlay = {"kind": "plot", "plots": [_forest(names, np.exp(f["beta"]), lo, hi, "Subdistribution hazard ratio")]}
    return r
