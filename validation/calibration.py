"""Statistical calibration by Monte-Carlo simulation (fixed seed).

Accuracy against reference values shows that formulas are computed
correctly; calibration shows that the methods behave as they should:
under a true null hypothesis a test must reject in ≈α of samples (exact
discrete tests: at most α), and a 95% confidence interval must contain the
true value in ≈95% of samples. Each simulation runs through the
application's own analysis code path.

Acceptance: the observed rate must lie inside the 99.9% binomial
interval around the nominal value (or below its upper limit for tests that
are conservative by design).
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from common import analyze, column_table, ct_table, kv, multi_table, number, section, xy_table
from openprism.tables import make_table

SEED = 20251102


def _band(p, n, conf=0.999):
    lo = stats.binom.ppf((1 - conf) / 2, n, p) / n
    hi = stats.binom.ppf(1 - (1 - conf) / 2, n, p) / n
    return lo, hi


def _record(out, area, case, rate, nominal, reps, conservative=False, note=""):
    lo, hi = _band(nominal, reps)
    ok = rate <= hi if conservative else lo <= rate <= hi
    out.append({"area": area, "case": case, "quantity": "rejection rate under H0" if nominal < 0.5 else "coverage of the true value",
                "reference": nominal, "value": rate, "lre": None, "required": f"{lo:.3f}–{hi:.3f}" if not conservative else f"≤ {hi:.3f}",
                "pass": bool(ok), "source": f"Monte-Carlo, {reps} samples, seed {SEED}", "note": note})


def _p(res, sec, row):
    return kv(res, sec, row)


def run_all(reps=1000):
    rng = np.random.default_rng(SEED)
    out = []
    area = "Type I error (α = 0.05)"
    rej = {k: 0 for k in ["student", "welch", "mw", "wsr", "anova", "kw", "fisher", "logrank", "shapiro", "pearson", "friedman", "chisq", "glm", "yuen", "jt", "cmh"]}
    cover = {k: 0 for k in ["tmean", "wilson", "clopper", "cohend", "nls", "slope", "icc", "kmed"]}
    sim_power = 0
    for _ in range(reps):
        a, b = rng.normal(10, 2, 12), rng.normal(10, 2, 12)
        r = analyze("ttest", column_table([a, b]), {})
        rej["student"] += _p(r, "Unpaired t test", "P value") < 0.05
        a2, b2 = rng.normal(10, 1, 8), rng.normal(10, 4, 20)
        r = analyze("ttest", column_table([a2, b2]), {"welch": True})
        rej["welch"] += _p(r, "Unpaired t test", "P value") < 0.05
        a3, b3 = rng.exponential(1, 9), rng.exponential(1, 11)
        r = analyze("ttest", column_table([a3, b3]), {"parametric": False})
        rej["mw"] += _p(r, "Mann Whitney", "P value") < 0.05
        x0 = rng.normal(0, 1, 14)
        r = analyze("ttest", column_table([x0, x0 + rng.standard_t(3, 14)]), {"parametric": False, "paired": True})
        rej["wsr"] += _p(r, "Wilcoxon", "P value") < 0.05
        gs = [rng.normal(5, 1, 7) for _k in range(4)]
        r = analyze("one_way", column_table(gs), {"comparison": "none"})
        rej["anova"] += _p(r, "ANOVA summary", "P value") < 0.05
        gs2 = [rng.lognormal(0, 1, 8) for _k in range(3)]
        r = analyze("one_way", column_table(gs2), {"parametric": False, "comparison": "none"})
        rej["kw"] += _find(r, "P value") < 0.05
        p1 = 0.3
        e1, e2 = rng.binomial(25, p1), rng.binomial(25, p1)
        r = analyze("contingency", ct_table([[e1, 25 - e1], [e2, 25 - e2]]), {})
        rej["fisher"] += _p(r, "Tests", "Fisher's exact") < 0.05
        rej["chisq"] += _p(r, "Tests", "P value") < 0.05
        t1, t2 = rng.exponential(10, 20), rng.exponential(10, 20)
        c1, c2 = rng.uniform(5, 30, 20), rng.uniform(5, 30, 20)
        times = np.r_[np.minimum(t1, c1), np.minimum(t2, c2)]
        ev = np.r_[(t1 <= c1), (t2 <= c2)].astype(int)
        tab = make_table("s", "survival", [{"name": "A", "reps": 1}, {"name": "B", "reps": 1}],
                         [[int(e), None] if k < 20 else [None, int(e)] for k, e in enumerate(ev)], x=[round(float(t), 6) for t in times])
        r = analyze("survival", tab, {})
        rej["logrank"] += _find(r, "P value") < 0.05
        r = analyze("normality", column_table([rng.normal(0, 1, 20)]), {"tests": ["shapiro"]})
        rej["shapiro"] += number(section(r, "Tests for normal")["rows"][0][3]) < 0.05
        xx, yy = rng.normal(size=15), rng.normal(size=15)
        r = analyze("correlation", xy_table(xx, [yy]), {})
        rej["pearson"] += number(section(r, "Correlation")["rows"][0][4]) < 0.05
        M = rng.normal(size=(10, 3)) + rng.normal(size=(10, 1)) * 2
        r = analyze("rm_nonparametric", column_table(list(M.T)), {})
        rej["friedman"] += number(next(x for x in section(r, "Tests")["rows"] if x[0] == "Friedman")[3]) < 0.05
        X = rng.normal(size=30)
        yb = rng.poisson(3, 30)
        r = analyze("glm", multi_table([yb, X], ["y", "x"]), {"dependent": 0, "family": "poisson"})
        rej["glm"] += number(section(r, "Coefficients")["rows"][1][5]) < 0.05
        a4, b4 = rng.standard_t(2, 15), rng.standard_t(2, 15)
        r = analyze("robust_compare", column_table([a4, b4]), {})
        rej["yuen"] += _p(r, "Yuen", "P value") < 0.05
        gs3 = [rng.normal(0, 1, 6) for _k in range(4)]
        r = analyze("trend_tests", column_table(gs3), {"permutations": 0})
        rej["jt"] += number(next(x for x in section(r, "Trend tests")["rows"] if x[0].startswith("Jonckheere"))[3]) < 0.05
        strata = []
        for _s in range(3):
            pp = rng.uniform(0.2, 0.6)
            e1, e2 = rng.binomial(30, pp), rng.binomial(30, pp)
            strata += [[e1, 30 - e1], [e2, 30 - e2]]
        r = analyze("cmh", ct_table(strata), {})
        rej["cmh"] += _p(r, "Pooled", "P value") < 0.05
        # ----- coverage
        mu = 7.3
        v = rng.normal(mu, 2, 9)
        r = analyze("descriptive", column_table([v]))
        cover["tmean"] += _p(r, "Column", "Lower 95%") <= mu <= _p(r, "Column", "Upper 95%")
        k = rng.binomial(40, 0.1)
        r = analyze("proportion", ct_table([[k, 40 - k]]), {})
        row = section(r, "Proportion")["rows"][0]
        cover["wilson"] += number(row[4], 0) <= 0.1 <= number(row[4], 1)
        cover["clopper"] += number(row[5], 0) <= 0.1 <= number(row[5], 1)
        d_true = 0.8
        g1, g2 = rng.normal(0, 1, 15), rng.normal(d_true, 1, 15)
        r = analyze("effect_sizes", column_table([g1, g2]), {})
        lo, hi = number(_kvs(r, "Unpaired", "95% CI of d"), 0), number(_kvs(r, "Unpaired", "95% CI of d"), 1)
        cover["cohend"] += lo <= d_true <= hi
        xs = np.array([0.02, 0.05, 0.1, 0.2, 0.4, 0.8, 1.6])
        ym = 200 * xs / (0.12 + xs) + rng.normal(0, 8, len(xs))
        r = analyze("nonlinear", xy_table(xs, [ym]), {"model": "custom", "equation": "Y = Vm*X/(K + X)", "initial": "Vm=150, K=0.2"})
        ci = _kvs(r, "95% CI", "K")
        cover["nls"] += number(ci, 0) <= 0.12 <= number(ci, 1)
        xl = np.arange(10.0)
        r = analyze("linear", xy_table(xl, [1.5 * xl + 2 + rng.normal(0, 1.5, 10)]), {})
        ci = _kvs(r, "Best-fit", "95% CI slope")
        cover["slope"] += number(ci, 0) <= 1.5 <= number(ci, 1)
        subj = rng.normal(0, 1, 20)[:, None]
        Mi = subj + rng.normal(0, 1, (20, 3))  # true ICC(1) = 0.5
        r = analyze("reliability", column_table(list(Mi.T)), {})
        icc_row = section(r, "Intraclass")["rows"][0]
        cover["icc"] += number(icc_row[6]) <= 0.5 <= number(icc_row[7])
        # power check: simulated rejection vs calculated power (n = 20, d = 2/3)
        pa, pb = rng.normal(0, 1.5, 20), rng.normal(1, 1.5, 20)
        sim_power += stats.ttest_ind(pa, pb).pvalue < 0.05
    labels = {"student": ("Student t test (normal, equal SD)", False), "welch": ("Welch t test (SDs 1 vs 4, n 8 vs 20)", False),
              "mw": ("Mann-Whitney, exact (exponential data)", True), "wsr": ("Wilcoxon signed-rank, exact (t₃ differences)", True),
              "anova": ("One-way ANOVA, 4 groups", False), "kw": ("Kruskal-Wallis (lognormal data)", True),
              "fisher": ("Fisher's exact test (2 × 25)", True), "chisq": ("Chi-square test 2 × 2 (n = 50)", False),
              "logrank": ("Log-rank test (exponential, censoring)", False), "shapiro": ("Shapiro-Wilk on normal data (n = 20)", False),
              "pearson": ("Pearson correlation test (n = 15)", False), "friedman": ("Friedman test (10 × 3)", True),
              "glm": ("Poisson GLM Wald test of a null slope", False), "yuen": ("Yuen trimmed-means test (t₂ heavy tails)", False),
              "jt": ("Jonckheere-Terpstra (no trend)", False), "cmh": ("Cochran-Mantel-Haenszel (3 strata, OR = 1)", False)}
    for key, (lab, cons) in labels.items():
        _record(out, area, lab, rej[key] / reps, 0.05, reps, cons,
                "rank/exact tests are discrete and therefore conservative by design" if cons else "")
    area = "Confidence-interval coverage (95%)"
    clabels = {"tmean": "t interval of a mean (n = 9)", "wilson": "Wilson interval, p = 0.1, n = 40", "cohend": "Cohen's d, noncentral-t interval (n = 15 + 15)",
               "nls": "Michaelis-Menten K, asymptotic interval (7 points)", "slope": "linear-regression slope (10 points)",
               "icc": "ICC(1) interval, 20 subjects × 3 raters"}
    for key, lab in clabels.items():
        _record(out, area, lab, cover[key] / reps, 0.95, reps, False,
                "asymptotic method: small departures from 95% are expected" if key == "nls" else "")
    lo, hi = _band(0.95, reps)
    rate = cover["clopper"] / reps
    out.append({"area": area, "case": "Clopper-Pearson exact interval, p = 0.1, n = 40", "quantity": "coverage of the true value", "reference": 0.95,
                "value": rate, "lre": None, "required": f"≥ {lo:.3f}", "pass": rate >= lo, "source": f"Monte-Carlo, {reps} samples, seed {SEED}",
                "note": "exact interval: guaranteed coverage ≥ 95% (conservative)"})
    # Gray's test under H0 with unequal censoring between groups (allowed by the null hypothesis)
    from openprism.stats.competing import gray_test
    g_rej = 0
    for _ in range(reps):
        n = 60
        g = rng.integers(0, 2, n)
        t1, t2 = rng.exponential(16, n), rng.exponential(12, n)
        c = np.where(g == 1, rng.uniform(2, 12, n), rng.uniform(3, 40, n))
        tt = np.minimum(np.minimum(t1, t2), c)
        code = np.where(np.minimum(t1, t2) > c, 0, np.where(t1 < t2, 1, 2))
        g_rej += gray_test(tt, code, g, 1)[2] < 0.05
    _record(out, "Type I error (α = 0.05)", "Gray's test, 2 groups × 30, unequal censoring", g_rej / reps, 0.05, reps, False,
            "asymptotic χ² test")
    from openprism.stats.multivariate import power
    pw = power({"test": "ttest2", "n": 20, "difference": 1, "sd": 1.5})["power"]
    _record(out, "Power calculation vs simulation", "two-sample t test, n = 20, δ = 1, σ = 1.5", sim_power / reps, pw, reps, False,
            f"calculated power {pw:.4f}")
    out[-1]["quantity"] = "simulated power"
    return out


def _find(r, row):
    for s in r["sections"]:
        for x in s["rows"]:
            if str(x[0]).startswith(row):
                return number(x[1])
    raise KeyError(row)


def _kvs(r, sec, row):
    s = section(r, sec)
    return next(x[1] for x in s["rows"] if str(x[0]).startswith(row))
