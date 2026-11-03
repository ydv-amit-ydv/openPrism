"""Accuracy tests against the NIST Statistical Reference Datasets (StRD).

The certified values were computed by NIST with 500-digit arithmetic
(https://www.itl.nist.gov/div898/strd/). For each quantity we report the log
relative error (LRE = number of correct significant digits), the standard
yard-stick of McCullough (1998, 1999) for assessing statistical software.

All computations run through the same code path as the application
(``openprism.stats.run``), with full-precision output enabled.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from common import analyze, cell, column_table, kv, lre, multi_table, number, xy_table

HERE = Path(__file__).parent / "nist"

# Minimum LRE accepted, by NIST difficulty level (conventional thresholds:
# a well-implemented double-precision routine should reach these).
THRESH = {
    "univ": {"lower": 9, "average": 8, "higher": 7},
    "anova": {"lower": 9, "average": 7, "higher": 5},
    "lls": {"lower": 8, "average": 7, "higher": 6},
    "nls": {"lower": 4, "average": 4, "higher": 4},  # parameters / RSS of nonlinear fits
}

NLS = {
    "Misra1a": "Y = b1*(1-exp(-b2*X))",
    "Chwirut2": "Y = exp(-b1*X)/(b2+b3*X)",
    "Chwirut1": "Y = exp(-b1*X)/(b2+b3*X)",
    "Lanczos3": "Y = b1*exp(-b2*X) + b3*exp(-b4*X) + b5*exp(-b6*X)",
    "Gauss1": "Y = b1*exp(-b2*X) + b3*exp(-(X-b4)**2/b5**2) + b6*exp(-(X-b7)**2/b8**2)",
    "Gauss2": "Y = b1*exp(-b2*X) + b3*exp(-(X-b4)**2/b5**2) + b6*exp(-(X-b7)**2/b8**2)",
    "DanWood": "Y = b1*X**b2",
    "Misra1b": "Y = b1*(1-(1+b2*X/2)**(-2))",
    "Kirby2": "Y = (b1 + b2*X + b3*X**2)/(1 + b4*X + b5*X**2)",
    "Hahn1": "Y = (b1+b2*X+b3*X**2+b4*X**3)/(1+b5*X+b6*X**2+b7*X**3)",
    "MGH17": "Y = b1 + b2*exp(-X*b4) + b3*exp(-X*b5)",
    "Lanczos1": "Y = b1*exp(-b2*X) + b3*exp(-b4*X) + b5*exp(-b6*X)",
    "Lanczos2": "Y = b1*exp(-b2*X) + b3*exp(-b4*X) + b5*exp(-b6*X)",
    "Gauss3": "Y = b1*exp(-b2*X) + b3*exp(-(X-b4)**2/b5**2) + b6*exp(-(X-b7)**2/b8**2)",
    "Misra1c": "Y = b1*(1-(1+2*b2*X)**(-0.5))",
    "Misra1d": "Y = b1*b2*X*((1+b2*X)**(-1))",
    "Roszman1": "Y = b1 - b2*X - arctan(b3/(X-b4))/pi",
    "ENSO": "Y = b1 + b2*cos(2*pi*X/12) + b3*sin(2*pi*X/12) + b5*cos(2*pi*X/b4) + b6*sin(2*pi*X/b4) + b8*cos(2*pi*X/b7) + b9*sin(2*pi*X/b7)",
    "MGH09": "Y = b1*(X**2+X*b2)/(X**2+X*b3+b4)",
    "Thurber": "Y = (b1 + b2*X + b3*X**2 + b4*X**3)/(1 + b5*X + b6*X**2 + b7*X**3)",
    "BoxBOD": "Y = b1*(1-exp(-b2*X))",
    "Rat42": "Y = b1/(1+exp(b2-b3*X))",
    "MGH10": "Y = b1*exp(b2/(X+b3))",
    "Eckerle4": "Y = (b1/b2)*exp(-0.5*((X-b3)/b2)**2)",
    "Rat43": "Y = b1/((1+exp(b2-b3*X))**(1/b4))",
    "Bennett5": "Y = b1*(b2+X)**(-1/b3)",
}


def _lines(path):
    return Path(path).read_text().replace("\r", "").splitlines()


def _range(lines, label):
    for ln in lines[:15]:
        m = re.search(label + r".*?lines\s+(\d+)\s+to\s+(\d+)", ln, re.I)
        if m:
            return int(m.group(1)), int(m.group(2))
    raise ValueError(label)


def _difficulty(lines):
    for ln in lines[:40]:
        m = re.search(r"(lower|average|higher)\s+level\s+of\s+difficulty", ln, re.I)
        if m:
            return m.group(1).lower()
    return "average"


def _data(lines, ncol=None):
    a, b = _range(lines, "Data")
    rows = [[float(v) for v in ln.split()] for ln in lines[a - 1:b] if ln.strip()]
    return np.array(rows)


def _text(lines):
    """Data block as the original decimal text tokens (what a user would paste)."""
    a, b = _range(lines, "Data")
    return [ln.split() for ln in lines[a - 1:b] if ln.strip()]


# Documented exceptions: quantities that cannot be computed to the usual accuracy
# in IEEE double precision by any program, whatever the algorithm.
LIMITS = {
    ("Lanczos1", "Residual sum of squares"): (2, "The certified RSS is 1.4e-25: the residuals (~1e-13) are at the round-off level of the "
                                                  "data (~4e-16 × |y|), so only 2-3 digits of the RSS are representable in double precision. "
                                                  "The parameters themselves agree to 10.5 digits."),
    ("Lanczos1", "standard errors (minimum LRE)"): (2, "Standard errors are proportional to √RSS (see the RSS note), so they inherit its round-off limit."),
}


def _check(out, area, case, qty, value, ref, need, note=""):
    key = (case.split(" ")[0], qty)
    if key in LIMITS:
        need, note = LIMITS[key]
    L = lre(value, ref)
    out.append({"area": area, "case": case, "quantity": qty, "reference": float(ref), "value": float(value) if value is not None else None,
                "lre": round(L, 2), "required": need, "pass": L >= need, "source": "NIST StRD (certified, 500-digit arithmetic)", "note": note})


def univariate(out):
    for f in sorted(HERE.glob("univ_*.dat")):
        lines = _lines(f)
        name = f.stem[5:]
        diff = _difficulty(lines)
        need = THRESH["univ"][diff]
        cert = "\n".join(lines[:60])
        mean = float(re.search(r"ybar:\s+([-\d.E+]+)", cert).group(1))
        sd = float(re.search(r"\s s:\s+([-\d.E+]+)", cert).group(1))
        y = _data(lines)[:, 0]
        res = analyze("descriptive", column_table([list(y)]))
        _check(out, "Univariate summary statistics", f"{name} ({diff})", "Mean", kv(res, "Column statistics", "Mean"), mean, need)
        _check(out, "Univariate summary statistics", f"{name} ({diff})", "Standard deviation", kv(res, "Column statistics", "Std. Deviation"), sd, need)


def anova(out):
    for f in sorted(HERE.glob("anova_*.dat")):
        lines = _lines(f)
        name = f.stem[6:]
        diff = _difficulty(lines)
        need = THRESH["anova"][diff]
        txt = "\n".join(lines[:60])
        btw = re.search(r"Between\s+\S+\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)", txt)
        wth = re.search(r"Within\s+\S+\s+(\d+)\s+(\S+)\s+(\S+)", txt)
        r2 = float(re.search(r"R-Squared\s+(\S+)", txt).group(1))
        rsd = float(re.search(r"Standard Deviation\s+(\S+)", txt).group(1))
        D = _data(lines)
        groups = {}
        for g, v in D:
            groups.setdefault(g, []).append(repr(float(v)))
        res = analyze("one_way", column_table(list(groups.values())), {"comparison": "none"})
        case = f"{name} ({diff})"
        _check(out, "One-way ANOVA", case, "Between-groups SS", cell(res, "ANOVA table", "Treatment", "SS"), float(btw.group(2)), need)
        _check(out, "One-way ANOVA", case, "Within-groups SS", cell(res, "ANOVA table", "Residual", "SS"), float(wth.group(2)), need)
        _check(out, "One-way ANOVA", case, "F statistic", kv(res, "ANOVA summary", "F"), float(btw.group(4)), need)
        _check(out, "One-way ANOVA", case, "R²", kv(res, "ANOVA summary", "R squared"), r2, need)
        ms_w = cell(res, "ANOVA table", "Residual", "MS")
        _check(out, "One-way ANOVA", case, "Residual SD", ms_w ** 0.5, rsd, need)


LLS_DEGREE = {"Norris": 1, "Pontius": 2, "NoInt1": 1, "NoInt2": 1, "Filip": 10, "Wampler1": 5, "Wampler2": 5, "Wampler3": 5, "Wampler4": 5, "Wampler5": 5}


def linear(out):
    for f in sorted(HERE.glob("lls_*.dat")):
        lines = _lines(f)
        name = f.stem[4:]
        diff = _difficulty(lines)
        need = THRESH["lls"][diff]
        txt = "\n".join(lines[:60])
        params = re.findall(r"^\s+B(\d+)\s+(\S+)\s+(\S+)", txt, re.M)
        rsd = float(re.search(r"Residual\s+Standard Deviation\s+(\S+)", txt, re.S).group(1))
        r2 = float(re.search(r"R-Squared\s+(\S+)", txt).group(1))
        D = _data(lines)
        T = _text(lines)
        y = D[:, 0]
        case = f"{name} ({diff})"
        if name in ("Norris", "NoInt1", "NoInt2"):
            origin = name.startswith("NoInt")
            res = analyze("linear", xy_table([t[1] for t in T], [[t[0] for t in T]]), {"throughOrigin": origin})
            est = {"1": kv(res, "Best-fit values", "Slope"), "0": kv(res, "Best-fit values", "Y-intercept")}
            se = {"1": kv(res, "Best-fit values", "Slope SE"), "0": kv(res, "Best-fit values", "Y-intercept SE")}
            got_rsd = kv(res, "Best-fit values", "Sy.x")
            got_r2 = kv(res, "Best-fit values", "R squared")
            if origin:
                params = [p for p in params if p[0] == "1"]
        elif name != "Longley":
            deg = LLS_DEGREE[name]
            res = analyze("polynomial", xy_table([t[1] for t in T], [[t[0] for t in T]]), {"order": deg})
            keys = [r[0] for r in next(sec for sec in res["sections"] if sec["title"].startswith("Coefficients"))["rows"]]
            est = {str(j): cell(res, "Coefficients", keys[j], 1, 0) for j in range(deg + 1)}
            se = {str(j): cell(res, "Coefficients", keys[j], 1, 1) for j in range(deg + 1)}
            got_rsd = cell(res, "Goodness of fit", "Sy.x")
            got_r2 = cell(res, "Goodness of fit", "R squared")
        else:
            if name == "Longley":
                X = D[:, 1:]
                names = [f"x{j}" for j in range(1, X.shape[1] + 1)]
            else:
                x = D[:, 1]
                X = np.column_stack([x ** j for j in range(1, LLS_DEGREE[name] + 1)])
                names = ["x"] + [f"x^{j}" for j in range(2, X.shape[1] + 1)]
            cols = [[t[0] for t in T]] + [[t[j + 1] for t in T] for j in range(X.shape[1])]
            res = analyze("multiple_regression", multi_table(cols, ["y"] + names), {"dependent": 0})
            est = {str(j): cell(res, "Parameter estimates", "Intercept" if j == 0 else names[j - 1], "Estimate") for j in range(X.shape[1] + 1)}
            se = {str(j): cell(res, "Parameter estimates", "Intercept" if j == 0 else names[j - 1], "Std. error") for j in range(X.shape[1] + 1)}
            exact = lambda nm: next(r for r in res["sections"] if r["title"] == "Parameter estimates")  # noqa: E731
            del exact
            got_rsd = kv(res, "Goodness of fit", "Sy.x")
            got_r2 = kv(res, "Goodness of fit", "R squared")
        for b, e, s in params:
            _check(out, "Linear regression", case, f"B{b} estimate", est[b], float(e), need)
            if float(s) != 0:
                _check(out, "Linear regression", case, f"B{b} standard error", se[b], float(s), need)
        _check(out, "Linear regression", case, "Residual SD", got_rsd, rsd, need)
        _check(out, "Linear regression", case, "R²", got_r2, r2, need)


def nonlinear(out):
    for f in sorted(HERE.glob("nls_*.dat")):
        name = f.stem[4:]
        if name not in NLS:
            continue
        lines = _lines(f)
        diff = _difficulty(lines)
        need = THRESH["nls"][diff]
        txt = "\n".join(lines[:60])
        rows = re.findall(r"^\s+(b\d+)\s+=\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)", txt, re.M)
        rss = float(re.search(r"Residual Sum of Squares:\s+(\S+)", txt).group(1))
        D = _data(lines)
        y, x = D[:, 0], D[:, 1]
        T = _text(lines)
        table = xy_table([t[1] for t in T], [[t[0] for t in T]])
        for start in (1, 2):
            init = ", ".join(f"{b}={s1 if start == 1 else s2}" for b, s1, s2, _, _ in rows)
            case = f"{name} ({diff}), start {start}"
            try:
                res = analyze("nonlinear", table, {"model": "custom", "equation": NLS[name], "initial": init})
                got = {b: kv(res, "Best-fit values", b) for b, *_ in rows}
                ses = {b: kv(res, "Std. Error", b) for b, *_ in rows}
                got_rss = kv(res, "Goodness of Fit", "Sum of Squares")
            except Exception as e:  # noqa: BLE001  (a failed fit is a failed check)
                got = {b: float("nan") for b, *_ in rows}
                ses = dict(got)
                got_rss = float("nan")
                case += f" — fit failed: {e}"
            got, ses = _canonical(name, rows, got, ses)
            worst = min(lre(got[b], float(c)) for b, _, _, c, _ in rows)
            worst_se = min(lre(ses[b], float(s)) for b, _, _, _, s in rows)
            out.append({"area": "Nonlinear regression", "case": case, "quantity": f"all {len(rows)} parameters (minimum LRE)",
                        "reference": float(rows[0][3]), "value": got[rows[0][0]], "lre": round(worst, 2), "required": need, "pass": worst >= need,
                        "source": "NIST StRD (certified, 500-digit arithmetic)",
                        "note": "terms are exchangeable: best-matching ordering compared" if name in EXCHANGEABLE else ""})
            need_se, note_se = LIMITS.get((name, "standard errors (minimum LRE)"), (need - 1, ""))
            out.append({"area": "Nonlinear regression", "case": case, "quantity": "standard errors (minimum LRE)",
                        "reference": float(rows[0][4]), "value": ses[rows[0][0]], "lre": round(worst_se, 2), "required": need_se, "pass": worst_se >= need_se,
                        "source": "NIST StRD (certified, 500-digit arithmetic)", "note": note_se})
            _check(out, "Nonlinear regression", case, "Residual sum of squares", got_rss, rss, need)


# Models whose terms can be exchanged without changing the fitted curve: the
# certified solution is one of several equivalent orderings, so compare the
# ordering that matches best (the residual sum of squares is unaffected).
EXCHANGEABLE = {"Lanczos1": [("b1", "b2"), ("b3", "b4"), ("b5", "b6")], "Lanczos2": [("b1", "b2"), ("b3", "b4"), ("b5", "b6")],
                "Lanczos3": [("b1", "b2"), ("b3", "b4"), ("b5", "b6")], "MGH17": [("b2", "b4"), ("b3", "b5")]}


def _canonical(name, rows, got, ses):
    import itertools
    groups = EXCHANGEABLE.get(name)
    if not groups:
        return got, ses
    cert = {b: float(c) for b, _, _, c, _ in rows}
    best, best_score = (got, ses), -1.0
    for perm in itertools.permutations(range(len(groups))):
        g2, s2 = dict(got), dict(ses)
        for src, dst in zip(perm, range(len(groups))):
            for a, b in zip(groups[src], groups[dst]):
                g2[b], s2[b] = got[a], ses[a]
        score = min(lre(g2[b], cert[b]) for b in cert)
        if score > best_score:
            best, best_score = (g2, s2), score
    return best


def run_all():
    out = []
    univariate(out)
    anova(out)
    linear(out)
    nonlinear(out)
    return out
