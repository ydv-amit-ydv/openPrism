"""Comparison of OpenPrism with R (base R and established CRAN packages).

``reference_r.json`` is produced by ``reference.R``; it contains both the
datasets and R's results, so this module needs no R installation.

Required agreement (LRE = number of matching significant digits):
* 6 for closed-form statistics (both programs should agree to ~10+ digits);
* 4 for results of iterative algorithms (GLM, nonlinear and mixed models,
  M-estimators), whose convergence criteria differ between programs;
* 3 where the two programs use different but accepted approximations
  (stated in the note of each check).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from common import analyze, cell, column_table, ct_table, kv, lre, multi_table, number, section, xy_table
from openprism.tables import make_table

REF = json.loads((Path(__file__).parent / "reference_r.json").read_text())
D, R = REF["data"], REF["ref"]
SOURCE = f"{REF['R']}"


class Checks:
    def __init__(self):
        self.out = []

    def add(self, area, case, qty, value, ref, need=6, note="", pkg="base R"):
        L = lre(value, ref)
        self.out.append({"area": area, "case": case, "quantity": qty, "reference": float(ref),
                         "value": None if value is None else float(value), "lre": round(L, 2), "required": need,
                         "pass": L >= need, "source": f"{SOURCE} — {pkg}", "note": note})

    def exact(self, area, case, qty, residual, need=10, note="evaluated independently in exact or 50-digit arithmetic"):
        """A check against a defining equation: *residual* should be ~0 (LRE = digits of absolute accuracy)."""
        L = lre(residual, 0.0)
        self.out.append({"area": area, "case": case, "quantity": qty, "reference": 0.0, "value": float(residual), "lre": round(L, 2),
                         "required": need, "pass": L >= need, "source": "defining equation (independent exact computation)", "note": note})

    def fail(self, area, case, err):
        self.out.append({"area": area, "case": case, "quantity": "(analysis failed)", "reference": float("nan"), "value": None,
                         "lre": 0.0, "required": 1, "pass": False, "source": SOURCE, "note": str(err)})


def ci_of(s):
    return number(s, 0), number(s, 1)


def two_groups(C):
    s = D["sleep"]
    t = column_table([s["g1"], s["g2"]])
    area = "t tests and rank tests"
    r = analyze("ttest", t, {})
    C.add(area, "sleep: Student t test", "|t|", number(kv(r, "Unpaired t test", "t, df")), abs(R["t_student"]["t"]))
    C.add(area, "sleep: Student t test", "P value", kv(r, "Unpaired t test", "P value"), R["t_student"]["p"])
    lo, hi = ci_of(section(r, "How big")["rows"][3][1])
    C.add(area, "sleep: Student t test", "95% CI lower", lo, R["t_student"]["ci"][0])
    C.add(area, "sleep: Student t test", "95% CI upper", hi, R["t_student"]["ci"][1])
    r = analyze("ttest", t, {"welch": True})
    C.add(area, "sleep: Welch t test", "|t|", number(kv(r, "Unpaired t test", "t, df")), abs(R["t_welch"]["t"]))
    C.add(area, "sleep: Welch t test", "df", number(kv_str(r, "Unpaired t test", "t, df"), 1), R["t_welch"]["df"])
    C.add(area, "sleep: Welch t test", "P value", kv(r, "Unpaired t test", "P value"), R["t_welch"]["p"])
    r = analyze("ttest", t, {"paired": True})
    C.add(area, "sleep: paired t test", "|t|", number(kv(r, "Paired t test", "t, df")), abs(R["t_paired"]["t"]))
    C.add(area, "sleep: paired t test", "P value", kv(r, "Paired t test", "P value"), R["t_paired"]["p"])
    lo, hi = ci_of(kv_str(r, "How big", "95% confidence interval"))
    C.add(area, "sleep: paired t test", "95% CI lower", lo, R["t_paired"]["ci"][0])
    C.add(area, "sleep: paired t test", "95% CI upper", hi, R["t_paired"]["ci"][1])
    r = analyze("ttest", t, {"parametric": False})
    C.add(area, "sleep: Mann-Whitney (ties)", "Exact conditional P value", kv(r, "Mann Whitney", "P value"), R["mw_exact"], pkg="coin::wilcox_test (exact)")
    r = analyze("ttest", t, {"parametric": False, "paired": True})
    C.add(area, "sleep: Wilcoxon signed-rank (ties, a zero)", "Exact conditional P value", kv(r, "Wilcoxon", "P value"), R["wsr_exact"], pkg="coin::wilcoxsign_test (exact)")
    C.add(area, "sleep: Wilcoxon signed-rank (ties, a zero)", "V (sum of positive ranks)", kv(r, "Wilcoxon", "Sum of positive"), R["wsr"]["V"])
    r = analyze("one_sample", column_table([list(np.array(s["g2"]) - np.array(s["g1"]))]), {"mu": 0})
    C.add(area, "sleep: one-sample t test of differences", "P value", find_num(r, "P value"), R["t_one"]["p"])
    r = analyze("normality", column_table([s["g1"], s["g2"]]), {"tests": ["shapiro"]})
    sw = section(r, "Tests for normal")["rows"]
    C.add("Normality", "sleep group 1: Shapiro-Wilk", "W", number(sw[0][2]), R["shapiro"]["W1"])
    C.add("Normality", "sleep group 1: Shapiro-Wilk", "P value", number(sw[0][3]), R["shapiro"]["p1"])
    C.add("Normality", "sleep group 2: Shapiro-Wilk", "W", number(sw[1][2]), R["shapiro"]["W2"])
    C.add("Normality", "sleep group 2: Shapiro-Wilk", "P value", number(sw[1][3]), R["shapiro"]["p2"])
    r = analyze("descriptive", column_table([s["g2"]]))
    C.add("Descriptive statistics", "sleep group 2", "Mean", kv(r, "Column", "Mean"), R["desc"]["mean"])
    C.add("Descriptive statistics", "sleep group 2", "SD", kv(r, "Column", "Std. Deviation"), R["desc"]["sd"])
    for lab, q in zip(["25% Percentile", "Median", "75% Percentile"], R["desc"]["q"]):
        C.add("Descriptive statistics", "sleep group 2", f"{lab} (R quantile type 6)", kv(r, "Column", lab), q)
    C.add("Descriptive statistics", "sleep group 2", "95% CI of mean (lower)", kv(r, "Column", "Lower 95% CI"), R["desc"]["ci"][0])
    C.add("Descriptive statistics", "sleep group 2", "95% CI of mean (upper)", kv(r, "Column", "Upper 95% CI"), R["desc"]["ci"][1])
    r = analyze("variance_tests", t, {})
    C.add("Variances", "sleep: F test", "F", cell(r, "Tests of equal", "F test", "Statistic"), R["ftest"]["F"])
    C.add("Variances", "sleep: F test", "P value", cell(r, "Tests of equal", "F test", "P value"), R["ftest"]["p"])


def kv_str(r, sec, row):
    s = section(r, sec)
    return next(x[1] for x in s["rows"] if str(x[0]).startswith(row))


def find_num(r, row):
    for s in r["sections"]:
        for x in s["rows"]:
            if str(x[0]).startswith(row):
                return number(x[1])
    raise KeyError(row)


def distributions(C):
    c = D["cont"]
    t2 = column_table([c["x"], c["y"]])
    t3 = column_table([c["x"], c["y"], c["z"]])
    r = analyze("distribution_tests", t2, {})
    C.add("Distributions and variances", "two samples: Kolmogorov-Smirnov", "D", cell(r, "Tests of identical", "Kolmogorov", "Statistic"), R["ks"]["D"])
    C.add("Distributions and variances", "two samples: Kolmogorov-Smirnov", "Exact P value", cell(r, "Tests of identical", "Kolmogorov", "P value"), R["ks"]["p"])
    r = analyze("variance_tests", t2, {})
    C.add("Distributions and variances", "two samples: Ansari-Bradley", "AB", cell(r, "Tests of equal", "Ansari", "Statistic"), R["ansari"]["AB"])
    C.add("Distributions and variances", "two samples: Ansari-Bradley", "P value", cell(r, "Tests of equal", "Ansari", "P value"), R["ansari"]["p"], 4,
          "both programs use the exact distribution")
    C.add("Distributions and variances", "two samples: Mood scale test", "Z", cell(r, "Tests of equal", "Mood", "Statistic"), R["mood"]["Z"])
    C.add("Distributions and variances", "two samples: Mood scale test", "P value", cell(r, "Tests of equal", "Mood", "P value"), R["mood"]["p"])
    r = analyze("variance_tests", t3, {})
    for nm, key in [("Fligner-Killeen", "fligner"), ("Bartlett", "bartlett")]:
        C.add("Distributions and variances", f"three samples: {nm}", "Statistic", cell(r, "Tests of equal", nm, "Statistic"), R[key]["stat"])
        C.add("Distributions and variances", f"three samples: {nm}", "P value", cell(r, "Tests of equal", nm, "P value"), R[key]["p"])
    C.add("Distributions and variances", "three samples: Brown-Forsythe", "F", cell(r, "Tests of equal", "Brown-Forsythe", "Statistic"), R["bf"]["F"], pkg="car::leveneTest(center = median)")
    C.add("Distributions and variances", "three samples: Brown-Forsythe", "P value", cell(r, "Tests of equal", "Brown-Forsythe", "P value"), R["bf"]["p"], pkg="car::leveneTest")
    C.add("Distributions and variances", "three samples: Levene", "F", cell(r, "Tests of equal", "Levene", "Statistic"), R["levene"]["F"], pkg="car::leveneTest(center = mean)")
    r = analyze("effect_sizes", t2, {})
    e = R["effect"]
    C.add("Effect sizes", "two samples", "Cohen's d", kv(r, "Unpaired", "Cohen's d (pooled"), e["d"], pkg="formula + uniroot(pt(ncp))")
    lo, hi = ci_of(kv_str(r, "Unpaired", "95% CI of d"))
    C.add("Effect sizes", "two samples", "95% CI of d, lower (noncentral t)", lo, e["lo"], 5, pkg="uniroot on pt(ncp)")
    C.add("Effect sizes", "two samples", "95% CI of d, upper (noncentral t)", hi, e["hi"], 5, pkg="uniroot on pt(ncp)")
    C.add("Effect sizes", "two samples", "Hedges' g", kv(r, "Unpaired", "Hedges' g (bias"), e["g"])
    C.add("Effect sizes", "two samples", "Glass's Δ", kv(r, "Unpaired", "Glass"), e["glass"])
    C.add("Effect sizes", "two samples", "Cliff's δ", kv(r, "Unpaired", "Cliff's δ ="), e["cliff"])


def anova(C):
    g = list(D["plant"].values())
    t = column_table(g, list(D["plant"].keys()))
    r = analyze("one_way", t, {"comparison": "tukey"})
    a = R["anova"]
    C.add("ANOVA", "PlantGrowth: one-way ANOVA", "F", kv(r, "ANOVA summary", "F"), a["F"])
    C.add("ANOVA", "PlantGrowth: one-way ANOVA", "P value", kv(r, "ANOVA summary", "P value"), a["p"])
    C.add("ANOVA", "PlantGrowth: one-way ANOVA", "SS between", cell(r, "ANOVA table", "Treatment", "SS"), a["ssb"])
    C.add("ANOVA", "PlantGrowth: one-way ANOVA", "SS within", cell(r, "ANOVA table", "Residual", "SS"), a["ssw"])
    rows = section(r, "Tukey")["rows"]
    names = list(D["plant"].keys())
    for k, rn in enumerate(a["tukey_names"]):
        b_, a_ = rn.split("-")
        row = next(x for x in rows if x[0] in (f"{a_} vs. {b_}", f"{b_} vs. {a_}"))
        sign = 1 if row[0] == f"{b_} vs. {a_}" else -1
        C.add("ANOVA", f"PlantGrowth: Tukey {rn}", "Mean difference", sign * number(row[1]), a["tukey_diff"][k])
        lo, hi = number(row[2], 0), number(row[2], 1)
        C.add("ANOVA", f"PlantGrowth: Tukey {rn}", "Simultaneous CI (lower)", min(sign * lo, sign * hi), a["tukey_lwr"][k], 5, "studentized range quantile (numerical integration)")
        C.add("ANOVA", f"PlantGrowth: Tukey {rn}", "Adjusted P value", number(row[5]), a["tukey_p"][k], 4, "studentized range distribution: different numerical integration in R and SciPy")
    del names
    r = analyze("one_way", t, {"parametric": False})
    C.add("ANOVA", "PlantGrowth: Kruskal-Wallis", "H", find_num(r, "Kruskal-Wallis statistic"), R["kw"]["H"])
    C.add("ANOVA", "PlantGrowth: Kruskal-Wallis", "P value", find_num(r, "P value"), R["kw"]["p"])
    r = analyze("one_way", t, {"welch": True, "comparison": "none"})
    w = kv_str(r, "ANOVA without", "Welch's W")
    C.add("ANOVA", "PlantGrowth: Welch ANOVA", "F", number(w, 0), R["welch_anova"]["F"])
    C.add("ANOVA", "PlantGrowth: Welch ANOVA", "Denominator df", number(w, 2), R["welch_anova"]["df2"])
    C.add("ANOVA", "PlantGrowth: Welch ANOVA", "P value", kv(r, "ANOVA without", "Welch P"), R["welch_anova"]["p"])
    rt = column_table(D["rounding"])
    r = analyze("rm_nonparametric", rt, {})
    C.add("ANOVA", "RoundingTimes: Friedman", "χ²", cell(r, "Tests", "Friedman", "Statistic"), R["friedman"]["chi"])
    C.add("ANOVA", "RoundingTimes: Friedman", "P value", cell(r, "Tests", "Friedman", "P value"), R["friedman"]["p"])
    C.add("ANOVA", "RoundingTimes: Quade", "F", cell(r, "Tests", "Quade", "Statistic"), R["quade"]["F"])
    C.add("ANOVA", "RoundingTimes: Quade", "P value", cell(r, "Tests", "Quade", "P value"), R["quade"]["p"])
    # two-way ANOVA (ToothGrowth)
    tg = D["tooth"]
    supp = sorted(set(tg["supp"]))
    doses = sorted(set(tg["dose"]))
    cells = []
    for dose in doses:
        row = []
        for s in supp:
            row += [v for v, ss, dd in zip(tg["len"], tg["supp"], tg["dose"]) if ss == s and dd == dose]
        cells.append(row)
    t2 = make_table("tooth", "grouped", [{"name": s, "reps": 10} for s in supp], cells, row_labels=[str(d) for d in doses])
    r = analyze("two_way", t2, {"comparison": "none"})
    rows = section(r, "ANOVA table")["rows"] if any(s["title"].startswith("ANOVA table") for s in r["sections"]) else r["sections"][0]["rows"]
    get = {x[0]: x for x in rows}
    for lab, k in [("Column Factor", 0), ("Row Factor", 1), ("Interaction", 2)]:
        C.add("ANOVA", f"ToothGrowth two-way: {lab}", "F", number(get[lab][4], 2), R["twoway"]["F"][k])
        C.add("ANOVA", f"ToothGrowth two-way: {lab}", "P value", number(get[lab][5]), R["twoway"]["p"][k])


def regression(C):
    c = D["cars"]
    t = xy_table(c["speed"], [c["dist"]])
    r = analyze("linear", t, {})
    L = R["lm"]
    C.add("Regression", "cars: linear regression", "Slope", kv(r, "Best-fit", "Slope"), L["b"][1])
    C.add("Regression", "cars: linear regression", "Intercept", kv(r, "Best-fit", "Y-intercept"), L["b"][0])
    C.add("Regression", "cars: linear regression", "Slope SE", kv(r, "Best-fit", "Slope SE"), L["se"][1])
    C.add("Regression", "cars: linear regression", "Intercept SE", kv(r, "Best-fit", "Y-intercept SE"), L["se"][0])
    C.add("Regression", "cars: linear regression", "R²", kv(r, "Best-fit", "R squared"), L["r2"])
    C.add("Regression", "cars: linear regression", "Residual SD", kv(r, "Best-fit", "Sy.x"), L["sigma"])
    C.add("Regression", "cars: linear regression", "F", kv(r, "Best-fit", "F"), L["F"])
    for meth, key in [("pearson", "pearson"), ("spearman", "spearman"), ("kendall", "kendall")]:
        r = analyze("correlation", t, {"method": meth})
        row = section(r, "Correlation")["rows"][0]
        C.add("Correlation", f"cars: {meth}", "Coefficient", number(row[1]), R[key]["r"])
        C.add("Correlation", f"cars: {meth}", "P value", number(row[4]), R[key]["p"], 6 if meth == "pearson" else 4,
              "" if meth == "pearson" else "normal approximation with tie correction in both programs")
        if meth == "pearson":
            C.add("Correlation", "cars: pearson", "95% CI lower", number(row[2], 0), R[key]["ci"][0])
            C.add("Correlation", "cars: pearson", "95% CI upper", number(row[2], 1), R[key]["ci"][1])
    r = analyze("robust_regression", t, {})
    rows = {x[0].split(" (")[0]: x for x in r["sections"][0]["rows"]}
    C.add("Robust regression", "cars: Theil-Sen", "Slope", number(rows["Theil-Sen"][1]), R["theilsen"], pkg="median of pairwise slopes")
    C.add("Robust regression", "cars: Huber M-estimator", "Slope", number(rows["Huber M-estimator"][1]), R["huber"][1], 4, "IRLS with MAD scale; convergence tolerances differ", "MASS::rlm")
    C.add("Robust regression", "cars: Huber M-estimator", "Intercept", number(rows["Huber M-estimator"][3]), R["huber"][0], 4, "IRLS with MAD scale", "MASS::rlm")
    qkey = next(k for k in rows if k.startswith("Quantile"))
    C.add("Robust regression", "cars: median (LAD) regression", "Slope", number(rows[qkey][1]), R["lad"][1], 5, "", "quantreg::rq")
    C.add("Robust regression", "cars: median (LAD) regression", "Intercept", number(rows[qkey][3]), R["lad"][0], 5, "", "quantreg::rq")
    m = D["mtcars"]
    mt = multi_table([m["mpg"], m["wt"], m["hp"], m["qsec"]], ["mpg", "wt", "hp", "qsec"])
    r = analyze("multiple_regression", mt, {"dependent": 0})
    for j, nm in enumerate(["Intercept", "wt", "hp", "qsec"]):
        C.add("Regression", "mtcars: multiple regression", f"{nm} coefficient", cell(r, "Parameter estimates", nm, "Estimate"), R["mlr"]["b"][j])
        C.add("Regression", "mtcars: multiple regression", f"{nm} SE", cell(r, "Parameter estimates", nm, "Std. error"), R["mlr"]["se"][j])
    C.add("Regression", "mtcars: multiple regression", "R²", kv(r, "Goodness", "R squared"), R["mlr"]["r2"])
    C.add("Regression", "mtcars: multiple regression", "Adjusted R²", kv(r, "Goodness", "Adjusted"), R["mlr"]["adj"])
    C.add("Regression", "mtcars: multiple regression", "F", number(kv_str(r, "Is the model", "F (DFn")), R["mlr"]["F"])
    md = multi_table([m["mpg"], m["wt"]], ["mpg", "wt"])
    lm_t = multi_table([D["cars"]["dist"], D["cars"]["speed"]], ["dist", "speed"])
    r = analyze("regression_diagnostics", lm_t, {"dependent": 0})
    C.add("Regression diagnostics", "cars: Breusch-Pagan (studentized)", "Statistic", cell(r, "Assumption", "Breusch-Pagan", "Statistic"), R["bp"]["stat"], pkg="lmtest::bptest")
    C.add("Regression diagnostics", "cars: Breusch-Pagan (studentized)", "P value", cell(r, "Assumption", "Breusch-Pagan", "P value"), R["bp"]["p"], pkg="lmtest::bptest")
    C.add("Regression diagnostics", "cars: Durbin-Watson", "Statistic", cell(r, "Assumption", "Durbin-Watson", "Statistic"), R["dw"], pkg="lmtest::dwtest")
    C.add("Regression diagnostics", "cars: Ramsey RESET (powers 2-3)", "F", cell(r, "Assumption", "Ramsey", "Statistic"), R["reset"]["F"], pkg="lmtest::resettest")
    C.add("Regression diagnostics", "cars: Ramsey RESET (powers 2-3)", "P value", cell(r, "Assumption", "Ramsey", "P value"), R["reset"]["p"], pkg="lmtest::resettest")
    C.add("Regression diagnostics", "cars: Breusch-Godfrey (lag 1)", "LM statistic", cell(r, "Assumption", "Breusch-Godfrey", "Statistic"), R["bg"]["stat"], pkg="lmtest::bgtest")
    del md
    # partial correlation
    pm = multi_table([m["mpg"], m["wt"], m["hp"]], ["mpg", "wt", "hp"])
    r = analyze("partial_correlation", pm, {})
    rows = {x[0]: x for x in section(r, "n =")["rows"]}
    C.add("Correlation", "mtcars: partial correlation mpg–wt | hp", "Partial r", number(rows["mpg – wt"][2]), R["pcor"]["mpg_wt"], pkg="residual method with lm()")
    C.add("Correlation", "mtcars: partial correlation mpg–hp | wt", "Partial r", number(rows["mpg – hp"][2]), R["pcor"]["mpg_hp"], pkg="residual method with lm()")
    C.add("Correlation", "mtcars: partial correlation wt–hp | mpg", "Partial r", number(rows["wt – hp"][2]), R["pcor"]["wt_hp"], pkg="residual method with lm()")
    # nonlinear (Puromycin)
    p = D["puromycin"]
    r = analyze("nonlinear", xy_table(p["conc"], [p["rate"]]), {"model": "custom", "equation": "Y = Vm*X/(K + X)", "initial": "Vm=200, K=0.1"})
    for j, nm in enumerate(["Vm", "K"]):
        C.add("Nonlinear regression", "Puromycin (treated): Michaelis-Menten", nm, kv(r, "Best-fit", nm), R["nls"]["b"][j], 5,
              "R's nls stops at a relative offset of 1e-5; OpenPrism's residual SS is lower (checked below)", pkg="nls()")
        C.add("Nonlinear regression", "Puromycin (treated): Michaelis-Menten", f"SE of {nm}", kv(r, "Std. Error", nm), R["nls"]["se"][j], 5, pkg="nls()")
    C.add("Nonlinear regression", "Puromycin (treated): Michaelis-Menten", "Residual SD", kv(r, "Goodness", "Sy.x"), R["nls"]["sigma"], 6, pkg="nls()")
    x, y = np.array(p["conc"]), np.array(p["rate"])
    rss = lambda b: float(((y - b[0] * x / (b[1] + x)) ** 2).sum())  # noqa: E731
    ours = rss([kv(r, "Best-fit", "Vm"), kv(r, "Best-fit", "K")])
    better = ours <= rss(R["nls"]["b"])
    C.out.append({"area": "Nonlinear regression", "case": "Puromycin: is OpenPrism's optimum at least as good as R's?", "quantity": "residual SS (OpenPrism ≤ R)",
                  "reference": rss(R["nls"]["b"]), "value": ours, "lre": 15.0 if better else 0.0, "required": 1, "pass": better,
                  "source": "direct evaluation of the sum of squares", "note": f"OpenPrism {ours!r} vs R {rss(R['nls']['b'])!r}"})
    # polynomial check against lm(poly)
    # cosinor
    cz = D["cos"]
    r = analyze("cosinor", xy_table(cz["t"], [cz["y"]]), {"period": 24})
    C.add("Rhythms", "simulated 24 h rhythm: cosinor", "MESOR", find_num(r, "MESOR"), R["cosinor"]["mesor"], pkg="lm(y ~ cos + sin)")
    C.add("Rhythms", "simulated 24 h rhythm: cosinor", "Amplitude", find_num(r, "Amplitude"), R["cosinor"]["amp"], pkg="lm(y ~ cos + sin)")
    C.add("Rhythms", "simulated 24 h rhythm: cosinor", "Zero-amplitude F", find_num(r, "F"), R["cosinor"]["F"], pkg="lm(y ~ cos + sin)")
    C.add("Rhythms", "simulated 24 h rhythm: cosinor", "Time of peak", find_num(r, "Time of peak"), R["cosinor"]["peak"], pkg="atan2 of lm coefficients")


def glms(C):
    m = D["mtcars"]
    area = "Generalized linear models"
    mt = multi_table([m["am"], m["wt"], m["hp"]], ["am", "wt", "hp"])
    for fam, link, key in [("binomial", "logit", "logit"), ("binomial", "probit", "probit")]:
        r = analyze("glm", mt, {"dependent": 0, "family": fam, "link": link})
        for j, nm in enumerate(["Intercept", "wt", "hp"]):
            C.add(area, f"mtcars am ~ wt + hp: {link}", f"{nm} β", cell(r, "Coefficients", nm, 1), R[key]["b"][j], 4, "iteratively reweighted least squares", "glm()")
            C.add(area, f"mtcars am ~ wt + hp: {link}", f"{nm} SE", cell(r, "Coefficients", nm, 2), R[key]["se"][j], 4, "", "glm()")
        C.add(area, f"mtcars am ~ wt + hp: {link}", "Deviance", kv(r, "Model fit", "Deviance"), R[key]["dev"], 5, "", "glm()")
    r = analyze("logistic", mt, {"dependent": 0})
    C.add(area, "mtcars: logistic regression analysis", "wt β", cell(r, "Parameter estimates", "wt", 1), R["logit"]["b"][1], 4, "", "glm(binomial)")
    C.add(area, "mtcars: logistic regression analysis", "AIC", kv(r, "Goodness", "AIC"), R["logit"]["aic"], 5, "", "glm(binomial)")
    gm = multi_table([m["mpg"], m["wt"], m["hp"]], ["mpg", "wt", "hp"])
    r = analyze("glm", gm, {"dependent": 0, "family": "gamma", "link": "log"})
    for j, nm in enumerate(["Intercept", "wt", "hp"]):
        C.add(area, "mtcars mpg ~ wt + hp: Gamma (log)", f"{nm} β", cell(r, "Coefficients", nm, 1), R["gamma"]["b"][j], 5, "", "glm(Gamma)")
        C.add(area, "mtcars mpg ~ wt + hp: Gamma (log)", f"{nm} SE", cell(r, "Coefficients", nm, 2), R["gamma"]["se"][j], 4, "dispersion = Pearson χ²/df in both", "glm(Gamma)")
    w = D["warp"]
    r = analyze("glm", multi_table([w["breaks"], w["woolB"], w["tensionM"], w["tensionH"]], ["breaks", "woolB", "tensionM", "tensionH"]), {"dependent": 0, "family": "poisson"})
    for j, nm in enumerate(["Intercept", "woolB", "tensionM", "tensionH"]):
        C.add(area, "warpbreaks: Poisson", f"{nm} β", cell(r, "Coefficients", nm, 1), R["poisson"]["b"][j], 5, "", "glm(poisson)")
        C.add(area, "warpbreaks: Poisson", f"{nm} SE", cell(r, "Coefficients", nm, 2), R["poisson"]["se"][j], 5, "", "glm(poisson)")
    C.add(area, "warpbreaks: Poisson", "Deviance", kv(r, "Model fit", "Deviance"), R["poisson"]["dev"], 5, "", "glm(poisson)")
    C.add(area, "warpbreaks: Poisson", "AIC", kv(r, "Model fit", "AIC"), R["poisson"]["aic"], 5, "", "glm(poisson)")
    q = D["quine"]
    r = analyze("glm", multi_table([q["Days"], q["EthN"], q["SexM"]], ["Days", "EthN", "SexM"]), {"dependent": 0, "family": "negbin"})
    C.add(area, "quine: negative binomial", "α = 1/θ", kv(r, "Model fit", "Negative binomial α"), 1 / R["negbin"]["theta"], 4, "maximum likelihood of θ", "MASS::glm.nb")
    for j, nm in enumerate(["Intercept", "EthN", "SexM"]):
        C.add(area, "quine: negative binomial", f"{nm} β", cell(r, "Coefficients", nm, 1), R["negbin"]["b"][j], 4, "", "MASS::glm.nb")
        C.add(area, "quine: negative binomial", f"{nm} SE", cell(r, "Coefficients", nm, 2), R["negbin"]["se"][j], 3, "SE conditional on θ in both", "MASS::glm.nb")
    r = analyze("ordinal", multi_table([m["gear"], m["wt"], m["hp"]], ["gear", "wt", "hp"]), {"dependent": 0})
    ref_se = _polr_reference_se(np.array(m["gear"]), np.column_stack([m["wt"], m["hp"]]))
    for j, nm in enumerate(["wt", "hp"]):
        C.add(area, "mtcars gear ~ wt + hp: proportional odds", f"{nm} β", cell(r, "Coefficients", nm, 1), R["polr"]["b"][j], 4, "quasi-Newton maximum likelihood", "MASS::polr")
        C.add(area, "mtcars gear ~ wt + hp: proportional odds", f"{nm} SE", cell(r, "Coefficients", nm, 2), R["polr"]["se"][j], 2,
              "polr's Hessian comes from optim() finite differences with step 1e-3; see the independent check", "MASS::polr")
        C.add(area, "mtcars gear ~ wt + hp: proportional odds", f"{nm} SE vs. independent Richardson-extrapolated Hessian", cell(r, "Coefficients", nm, 2), ref_se[j], 5,
              "log-likelihood written independently; Hessian by Richardson extrapolation of central differences", "independent computation")
    th = section(r, "Thresholds")["rows"]
    for j in range(2):
        C.add(area, "mtcars gear ~ wt + hp: proportional odds", f"threshold {j + 1}", number(th[j][1]), R["polr"]["zeta"][j], 4, "", "MASS::polr")


def _polr_reference_se(y, X):
    """Independent SEs for the proportional-odds model: own log-likelihood, own optimizer, extrapolated Hessian."""
    from scipy import optimize
    from scipy.special import expit
    cats = np.unique(y)
    K, p = len(cats), X.shape[1]
    idx = np.searchsorted(cats, y)

    def nll(theta):
        b, z = theta[:p], np.cumsum(np.r_[theta[p], np.exp(theta[p + 1:])])  # increasing thresholds
        eta = X @ b
        cum = np.column_stack([np.zeros(len(y)), expit(z[None, :] - eta[:, None]), np.ones(len(y))])
        pr = cum[np.arange(len(y)), idx + 1] - cum[np.arange(len(y)), idx]
        return -np.log(pr).sum()

    def nll_nat(par):  # natural parametrization (b, zeta) for the Hessian
        b, z = par[:p], par[p:]
        eta = X @ b
        cum = np.column_stack([np.zeros(len(y)), expit(z[None, :] - eta[:, None]), np.ones(len(y))])
        pr = cum[np.arange(len(y)), idx + 1] - cum[np.arange(len(y)), idx]
        return -np.log(pr).sum()
    t0 = np.r_[np.zeros(p), -1.0, np.zeros(K - 2)]
    sol = optimize.minimize(nll, t0, method="BFGS", options={"gtol": 1e-12, "maxiter": 10000})
    sol = optimize.minimize(nll, sol.x, method="Nelder-Mead", options={"xatol": 1e-12, "fatol": 1e-14, "maxiter": 40000})
    th = sol.x
    nat = np.r_[th[:p], np.cumsum(np.r_[th[p], np.exp(th[p + 1:])])]
    n = len(nat)

    def hess(h):
        H = np.empty((n, n))
        for i in range(n):
            for j in range(n):
                e_i, e_j = np.eye(n)[i] * h[i], np.eye(n)[j] * h[j]
                H[i, j] = (nll_nat(nat + e_i + e_j) - nll_nat(nat + e_i - e_j) - nll_nat(nat - e_i + e_j) + nll_nat(nat - e_i - e_j)) / (4 * h[i] * h[j])
        return H
    h = 1e-3 * np.maximum(np.abs(nat), 1e-2)
    H1, H2 = hess(h), hess(h / 2)
    H = (4 * H2 - H1) / 3  # Richardson extrapolation (removes the O(h²) error)
    return np.sqrt(np.diag(np.linalg.inv(H)))[:p]


def counts(C):
    area = "Contingency tables and proportions"
    r = analyze("contingency", ct_table([[3, 1], [1, 3]]), {})
    C.add(area, "Fisher's tea tasting", "Fisher exact P", kv(r, "Tests", "Fisher's exact"), R["fisher"]["p"])
    r = analyze("risk", ct_table([[3, 1], [1, 3]]), {})
    or_ = cell(r, "Rows =", "Odds ratio (conditional", 1)
    lo, hi = ci_of(cell_str(r, "Rows =", "Odds ratio (conditional", 2))
    note = "R's fisher.test finds these roots with uniroot's default tolerance (≈1e-4); see the exact checks below"
    C.add(area, "Fisher's tea tasting", "Conditional MLE odds ratio", or_, R["fisher"]["or"], 4, note, "fisher.test")
    C.add(area, "Fisher's tea tasting", "Exact CI of OR (lower)", lo, R["fisher"]["ci"][0], 4, note, "fisher.test")
    C.add(area, "Fisher's tea tasting", "Exact CI of OR (upper)", hi, R["fisher"]["ci"][1], 2, note, "fisher.test")
    # exact arbiter: the defining equations evaluated in rational arithmetic
    C.exact(area, "Fisher's tea tasting: defining equation of the exact CI", "|P(X ≥ 3; ψ_lower) − 0.025|", abs(_nchg_tail(lo, 3, upper=True) - 0.025))
    C.exact(area, "Fisher's tea tasting: defining equation of the exact CI", "|P(X ≤ 3; ψ_upper) − 0.025|", abs(_nchg_tail(hi, 3, upper=False) - 0.025))
    C.exact(area, "Fisher's tea tasting: defining equation of the conditional MLE", "|E[X; ψ̂] − 3|", abs(_nchg_mean(or_) - 3))
    perf = D["performance"]
    r = analyze("contingency_more", ct_table(perf), {})
    C.add(area, "Presidential approval (paired)", "McNemar χ² (corrected)", cell(r, "Tests", "McNemar with continuity", "Statistic"), R["mcnemar"]["chi"])
    C.add(area, "Presidential approval (paired)", "McNemar P (corrected)", cell(r, "Tests", "McNemar with continuity", "P value"), R["mcnemar"]["p"])
    C.add(area, "Presidential approval (paired)", "McNemar χ² (uncorrected)", cell(r, "Tests", "McNemar (paired", "Statistic"), R["mcnemar"]["chi_nc"])
    r = analyze("contingency_more", ct_table(D["square3"]), {})
    C.add(area, "3 × 3 paired table: Bowker symmetry", "χ²", cell(r, "Tests", "Bowker", "Statistic"), R["bowker"]["chi"], pkg="mcnemar.test (Bowker)")
    C.add(area, "3 × 3 paired table: Bowker symmetry", "P value", cell(r, "Tests", "Bowker", "P value"), R["bowker"]["p"], pkg="mcnemar.test (Bowker)")
    r = analyze("contingency_more", ct_table(D["rc"]), {})
    C.add(area, "3 × 3 table: Pearson χ²", "χ²", cell(r, "Tests", "Pearson", "Statistic"), R["chisq"]["chi"], pkg="chisq.test")
    C.add(area, "3 × 3 table: Pearson χ²", "P value", cell(r, "Tests", "Pearson", "P value"), R["chisq"]["p"], pkg="chisq.test")
    sm = D["smokers"]
    rows = [[s, p - s] for s, p in zip(sm["smokers"], sm["patients"])]
    r = analyze("contingency_more", ct_table(rows), {})
    z = cell(r, "Tests", "Cochran-Armitage", "Statistic")
    C.add(area, "Smokers by group: Cochran-Armitage trend", "χ² = z²", z * z, R["trend"]["chi"], pkg="prop.trend.test")
    C.add(area, "Smokers by group: Cochran-Armitage trend", "P value", cell(r, "Tests", "Cochran-Armitage", "P value"), R["trend"]["p"], pkg="prop.trend.test")
    r = analyze("proportion", ct_table([[682, 925 - 682]]), {"p0": 0.75})
    row = section(r, "Proportion")["rows"][0]
    C.add(area, "682 of 925: exact binomial test vs 0.75", "P value", number(row[9]), R["binom"]["p"], pkg="binom.test")
    C.add(area, "682 of 925: Clopper-Pearson CI", "lower", number(row[5], 0), R["binom"]["ci"][0], pkg="binom.test")
    C.add(area, "682 of 925: Clopper-Pearson CI", "upper", number(row[5], 1), R["binom"]["ci"][1], pkg="binom.test")
    C.add(area, "682 of 925: Wilson CI", "lower", number(row[4], 0), R["wilson"][0], pkg="prop.test(correct = FALSE)")
    C.add(area, "682 of 925: Wilson CI", "upper", number(row[4], 1), R["wilson"][1], pkg="prop.test(correct = FALSE)")
    C.add(area, "682 of 925: Jeffreys CI", "lower", number(row[6], 0), R["jeffreys"][0], pkg="qbeta")
    C.add(area, "682 of 925: Jeffreys CI", "upper", number(row[6], 1), R["jeffreys"][1], pkg="qbeta")
    ucb = [row for tab in D["ucb"] for row in tab]
    r = analyze("cmh", ct_table(ucb), {})
    C.add(area, "UCB admissions: Cochran-Mantel-Haenszel", "CMH χ²", kv(r, "Pooled", "CMH chi-square"), R["cmh"]["chi"], pkg="mantelhaen.test")
    C.add(area, "UCB admissions: Cochran-Mantel-Haenszel", "P value", kv(r, "Pooled", "P value"), R["cmh"]["p"], pkg="mantelhaen.test")
    C.add(area, "UCB admissions: Cochran-Mantel-Haenszel", "MH odds ratio", kv(r, "Pooled", "Mantel-Haenszel odds"), R["cmh"]["or"], pkg="mantelhaen.test")
    lo, hi = ci_of(kv_str(r, "Pooled", "95% CI"))
    C.add(area, "UCB admissions: Cochran-Mantel-Haenszel", "CI lower (Robins-Breslow-Greenland)", lo, R["cmh"]["ci"][0], pkg="mantelhaen.test")
    C.add(area, "UCB admissions: Cochran-Mantel-Haenszel", "CI upper", hi, R["cmh"]["ci"][1], pkg="mantelhaen.test")
    r = analyze("kappa", ct_table(D["kappa"]), {})
    rows = {x[0]: x for x in section(r, "Kappa")["rows"]}
    C.add(area, "3-category agreement: Cohen's κ", "κ", number(rows["Unweighted κ"][1]), R["kappa"]["kappa"], pkg="psych::cohen.kappa")
    C.add(area, "3-category agreement: weighted κ (quadratic)", "κw", number(rows["Quadratic-weighted κ (≈ ICC)"][1]), R["kappa"]["weighted"], pkg="psych::cohen.kappa")
    r = analyze("risk", ct_table(D["risk"]), {})
    C.add(area, "2 × 2 risk table", "Relative risk", cell(r, "Rows =", "Relative risk (risk", 1), R["risk"]["rr"], pkg="formula")
    lo, hi = ci_of(cell_str(r, "Rows =", "Relative risk (risk", 2))
    C.add(area, "2 × 2 risk table", "RR CI lower (Katz log)", lo, R["risk"]["rr_ci"][0], pkg="formula")
    C.add(area, "2 × 2 risk table", "Odds ratio (sample)", cell(r, "Rows =", "Odds ratio", 1), R["risk"]["or"], pkg="formula")
    note = "fisher.test's uniroot tolerance (≈1e-4) limits R's agreement"
    C.add(area, "2 × 2 risk table", "Odds ratio (conditional MLE)", cell(r, "Rows =", "Odds ratio (conditional", 1), R["risk"]["or_cond"], 4, note, pkg="fisher.test")
    lo, hi = ci_of(cell_str(r, "Rows =", "Odds ratio (conditional", 2))
    C.add(area, "2 × 2 risk table", "Exact OR CI upper", hi, R["risk"]["or_cond_ci"][1], 4, note, pkg="fisher.test")
    pv = D["pvals"]
    r = analyze("p_adjust", column_table([pv]), {})
    s = section(r, f"{len(pv)} P values")
    colmap = {"bonferroni": "Bonferroni", "holm": "Holm", "hochberg": "Hochberg", "hommel": "Hommel", "BH": "Benjamini-Hochberg (FDR)", "BY": "Benjamini-Yekutieli (FDR, any dependence)"}
    for key, col in colmap.items():
        j = s["columns"].index(col)
        worst = min(lre(number(row[j]), ref) for row, ref in zip(s["rows"], R["padj"][key]))
        C.out.append({"area": "Multiplicity", "case": f"10 P values: {col}", "quantity": "all adjusted P values (minimum LRE)", "reference": R["padj"][key][0],
                      "value": number(s["rows"][0][j]), "lre": round(worst, 2), "required": 6, "pass": worst >= 6, "source": f"{SOURCE} — p.adjust", "note": ""})


def _nchg_weights(psi):
    """Fisher noncentral hypergeometric for the tea-tasting margins (4, 4; 4), exact rationals."""
    from fractions import Fraction
    from math import comb
    psi = Fraction(psi)
    return {x: comb(4, x) * comb(4, 4 - x) * psi ** x for x in range(0, 5)}


def _nchg_tail(psi, x0, upper):
    w = _nchg_weights(psi)
    tot = sum(w.values())
    return float(sum(v for x, v in w.items() if (x >= x0 if upper else x <= x0)) / tot)


def _nchg_mean(psi):
    w = _nchg_weights(psi)
    return float(sum(x * v for x, v in w.items()) / sum(w.values()))


def cell_str(r, sec, row, col):
    s = section(r, sec)
    return next(x[col] for x in s["rows"] if str(x[0]).startswith(row))


def survival(C):
    a = D["aml"]
    area = "Survival analysis"
    t = make_table("s", "survival", [{"name": "Maintained", "reps": 1}, {"name": "Nonmaintained", "reps": 1}],
                   [[st if m == 1 else None, st if m == 0 else None] for st, m in zip(a["status"], a["maintained"])], x=a["time"])
    r = analyze("survival", t, {})
    C.add(area, "aml: log-rank", "χ²", kv(r, "Curve comparison", "Chi square"), R["logrank"]["chi"], pkg="survival::survdiff")
    med = {x[0]: x for x in section(r, "Median survival")["rows"]}
    C.add(area, "aml: Kaplan-Meier median (Maintained)", "Median", number(med["Maintained"][4]), R["rmst"]["median"][0], pkg="survival::survfit")
    C.add(area, "aml: Kaplan-Meier median (Nonmaintained)", "Median", number(med["Nonmaintained"][4]), R["rmst"]["median"][1], pkg="survival::survfit")
    r = analyze("survival_more", t, {"tau": 40})
    C.add(area, "aml: Peto-Peto / Fleming-Harrington G(1,0)", "χ²", cell(r, "Comparison", "Fleming-Harrington G(1,0)", "Statistic"), R["logrank"]["chi_peto"], pkg="survdiff(rho = 1)")
    rows = {x[0]: x for x in section(r, "Restricted mean")["rows"]}
    for k, nm in enumerate(["Maintained", "Nonmaintained"]):
        C.add(area, f"aml: RMST up to 40 ({nm})", "RMST", number(rows[nm][1]), R["rmst"]["rmean"][k], pkg="print.survfit(rmean = 40)")
        C.add(area, f"aml: RMST up to 40 ({nm})", "SE", number(rows[nm][2]), R["rmst"]["se"][k], pkg="print.survfit(rmean = 40)")
    r = analyze("cox", multi_table([a["time"], a["status"], a["maintained"]], ["time", "status", "maintained"]), {"timeVar": 0, "eventVar": 1})
    row = section(r, "Hazard ratios")["rows"][0]
    C.add(area, "aml: Cox regression (Efron ties)", "β", number(row[1]), _s(R["cox"]["b"]), 5, "Newton-Raphson", "survival::coxph")
    C.add(area, "aml: Cox regression (Efron ties)", "SE", number(row[2]), _s(R["cox"]["se"]), 5, "", "survival::coxph")
    C.add(area, "aml: Cox regression (Efron ties)", "Wald P", number(row[5]), R["cox"]["p"], 5, "", "survival::coxph")


def multivariate(C):
    sf = D["sf"]
    area = "Reliability and agreement"
    r = analyze("reliability", column_table([[row[j] for row in sf] for j in range(4)]), {})
    rows = section(r, "Intraclass")["rows"]
    order = {"ICC1": 0, "ICC2": 1, "ICC3": 2, "ICC1k": 3, "ICC2k": 4, "ICC3k": 5}
    for typ, j in order.items():
        k = R["icc"]["type"].index(typ)
        C.add(area, f"Shrout & Fleiss data: {typ}", "ICC", number(rows[j][1]), R["icc"]["icc"][k], pkg="psych::ICC")
        C.add(area, f"Shrout & Fleiss data: {typ}", "95% CI lower", number(rows[j][6]), R["icc"]["lo"][k], pkg="psych::ICC")
        C.add(area, f"Shrout & Fleiss data: {typ}", "95% CI upper", number(rows[j][7]), R["icc"]["hi"][k], pkg="psych::ICC")
    C.add(area, "Shrout & Fleiss data", "Cronbach's α", kv(r, "Internal", "Cronbach"), R["alpha"], pkg="psych::alpha")
    b = D["bcg"]
    mt = make_table("bcg", "multi", [{"name": n, "reps": 1} for n in ["e1", "n1", "e2", "n2"]], [[b["e1"][i], b["n1"][i], b["e2"][i], b["n2"][i]] for i in range(len(b["e1"]))],
                    row_labels=b["study"])
    area = "Meta-analysis"
    for meth, key in [("reml", "meta_reml"), ("dl", "meta_dl"), ("pm", "meta_pm"), ("fixed", "meta_fe")]:
        r = analyze("meta", mt, {"format": "counts", "measure": "rr", "method": meth})
        ref = R[key]
        case = f"BCG vaccine trials (log RR): {meth.upper()}"
        need = {"reml": 5, "pm": 3}.get(meth, 6)
        note = {"reml": "iterative τ² estimator", "pm": "metafor solves the PM equation to a tolerance of ~1e-5; see the exact check below"}.get(meth, "")
        C.add(area, case, "Pooled log RR", number(kv_str(r, "Pooled estimate", "Log-scale"), 0), ref["b"], need, note, "metafor::rma")
        C.add(area, case, "SE", number(kv_str(r, "Pooled estimate", "Log-scale"), 1), ref["se"], need, note, "metafor::rma")
        if meth != "fixed":
            tau2 = kv(r, "Heterogeneity", "τ² (between")
            C.add(area, case, "τ²", tau2, ref["tau2"], need, note, "metafor::rma")
        if meth == "pm":
            yi, vi = _bcg_yv()
            w = 1 / (vi + tau2)
            m_ = (w * yi).sum() / w.sum()
            C.exact(area, "BCG: Paule-Mandel estimating equation", "|Q(τ̂²) − (k − 1)|", abs((w * (yi - m_) ** 2).sum() - (len(yi) - 1)))
        C.add(area, case, "Q", kv(r, "Heterogeneity", "Cochran's Q"), ref["Q"], 6, "", "metafor::rma")
        if meth != "fixed":
            C.add(area, case, "I² (τ²-based, as metafor)", number(kv_str(r, "Heterogeneity", "I² (from τ²)")), ref["I2"], 5, "", "metafor::rma")
    r = analyze("meta", mt, {"format": "counts", "measure": "rr", "method": "reml", "hartungKnapp": True})
    C.add(area, "BCG: REML with Hartung-Knapp", "SE", number(kv_str(r, "Pooled estimate", "Log-scale"), 1), R["meta_hk"]["se"], 5, "", "metafor::rma(test = 'knha')")
    C.add(area, "BCG: REML with Hartung-Knapp", "P value", kv(r, "Pooled estimate", "P value"), R["meta_hk"]["p"], 5, "", "metafor::rma(test = 'knha')")
    r = analyze("meta", mt, {"format": "counts", "measure": "rr", "method": "reml"})
    lo, hi = ci_of(kv_str(r, "Pooled estimate", "95% prediction interval (normal"))
    C.add(area, "BCG: REML prediction interval (normal quantile)", "lower (RR scale)", lo, float(np.exp(R["meta_pi"][0])), 5, "", "metafor::predict")
    C.add(area, "BCG: REML prediction interval (normal quantile)", "upper (RR scale)", hi, float(np.exp(R["meta_pi"][1])), 5, "", "metafor::predict")
    rf = analyze("meta", mt, {"format": "counts", "measure": "rr", "method": "fixed"})
    C.add(area, "BCG: Egger's regression test", "t (intercept)", kv(rf, "Small-study", "t"), R["egger"]["t"], 6, "", "metafor::regtest(model = 'lm')")
    C.add(area, "BCG: Egger's regression test", "P value", kv(rf, "Small-study", "P value (Egger)"), R["egger"]["p"], 6, "", "metafor::regtest(model = 'lm')")
    # circular
    ang = D["angles"]
    r = analyze("circular", column_table([ang["a"], ang["b"]]), {"unit": "degrees"})
    area = "Circular statistics"
    C.add(area, "von Mises sample: mean direction", "degrees", kv(r, "G1", "Mean direction"), R["circ"]["mean"], pkg="circular::mean.circular")
    C.add(area, "von Mises sample: mean resultant length", "R̄", kv(r, "G1", "Mean resultant"), R["circ"]["rbar"], pkg="circular::rho.circular")
    C.add(area, "von Mises sample: Rayleigh test", "P value", kv(r, "G1", "P value"), R["circ"]["rayleigh_p"], 0.9,
          "two different asymptotic approximations (Zar 2010 vs Greenwood & Durand); they differ only far out in the tail (P ≈ 1e-6 here)", "circular::rayleigh.test")
    C.add(area, "two samples: Watson-Williams (Zar 2010 form)", "F", kv(r, "Watson-Williams", "F"), R["ww_zar"], 6, "κ from the within-sample mean resultant length, exact ML (Bessel ratio inverted with uniroot)", "besselI + uniroot + formula")
    C.add(area, "two samples: Watson-Williams vs circular package", "F", kv(r, "Watson-Williams", "F"), R["ww"]["F"], 2,
          "circular::watson.williams.test estimates κ from the pooled sample with the Best-Fisher approximation (a different published variant)", "circular::watson.williams.test")
    # MANOVA
    ir = D["iris"]
    mt = multi_table([D["species"], ir["Sepal.Length"], ir["Petal.Length"], ir["Sepal.Width"]], ["Species", "SL", "PL", "SW"])
    r = analyze("manova", mt, {"group": 0})
    rows = {x[0]: x for x in section(r, "Multivariate tests")["rows"]}
    C.add("Multivariate", "iris: MANOVA", "Pillai's trace", number(rows["Pillai's trace"][1]), R["manova"]["pillai"], pkg="summary.manova")
    C.add("Multivariate", "iris: MANOVA", "Pillai approx. F", number(rows["Pillai's trace"][2]), R["manova"]["pillai_F"], pkg="summary.manova")
    C.add("Multivariate", "iris: MANOVA", "Wilks' Λ", number(rows["Wilks' lambda"][1]), R["manova"]["wilks"], pkg="summary.manova")
    C.add("Multivariate", "iris: MANOVA", "Wilks approx. F", number(rows["Wilks' lambda"][2]), R["manova"]["wilks_F"], pkg="summary.manova")
    mt = multi_table([ir[k] for k in ["Sepal.Length", "Sepal.Width", "Petal.Length", "Petal.Width"]], ["SL", "SW", "PL", "PW"])
    r = analyze("cluster", mt, {"method": "ward", "k": 3})
    sizes = sorted(int(number(x[1])) for x in section(r, "Cluster sizes")["rows"])
    ok = sizes == [int(v) for v in R["ward_sizes"]]
    C.out.append({"area": "Multivariate", "case": "iris: Ward hierarchical clustering, k = 3", "quantity": "cluster sizes " + str(sizes), "reference": float(R["ward_sizes"][0]),
                  "value": float(sizes[0]), "lre": 15.0 if ok else 0.0, "required": 6, "pass": ok, "source": f"{SOURCE} — hclust(ward.D2)", "note": f"R: {R['ward_sizes']}"})
    # time series
    nile = D["nile"]
    r = analyze("randomness", column_table([nile]), {"lags": 10})
    C.add("Time series and trends", "Nile: Ljung-Box (10 lags)", "Q", cell(r, "G1", "Ljung-Box", "Statistic"), R["ljung"]["Q"], pkg="Box.test")
    p_lb = cell(r, "G1", "Ljung-Box", "P value")
    C.add("Time series and trends", "Nile: Ljung-Box (10 lags)", "P value", p_lb, R["ljung"]["p"], 2,
          "R's Box.test computes 1 − pchisq(Q), which cancels at P ≈ 1e-14; see the exact check", pkg="Box.test")
    C.exact("Time series and trends", "Nile: Ljung-Box P value vs closed-form χ²(10) tail in 50-digit arithmetic", "relative error",
            abs(p_lb - _chi2_sf_even(cell(r, "G1", "Ljung-Box", "Statistic"), 10)) / p_lb, 12)
    r = analyze("trend_mk", column_table([nile]), {})
    row = section(r, "Results")["rows"][0]
    C.add("Time series and trends", "Nile: Mann-Kendall", "Kendall τ (tie-adjusted)", number(row[3]), R["mk"]["tau"], pkg="cor.test(method = 'kendall')")
    C.add("Time series and trends", "Nile: Mann-Kendall", "P value", number(row[5]), R["mk"]["p"], pkg="cor.test(exact = FALSE, continuity = TRUE)")
    # mixed model
    o = D["ortho"]
    r = analyze("mixed_one_way", column_table(list(o.values()), list(o.keys())), {"comparison": "none"})
    vc = find_variance(r)
    if vc:
        C.add("Mixed models", "Orthodont: random intercept (REML)", "Residual SD", vc[0], R["lme"]["sigma"], 4, "REML optimizers differ", "nlme::lme")
        C.add("Mixed models", "Orthodont: random intercept (REML)", "Subject SD", vc[1], R["lme"]["sd_subject"], 4, "", "nlme::lme")


def _s(v):
    return v[0] if isinstance(v, list) else v


def _chi2_sf_even(x, df):
    """Exact upper tail of χ² with even df: exp(−x/2) Σ (x/2)^k / k!  (50-digit decimal)."""
    from decimal import Decimal, localcontext
    from math import factorial
    with localcontext() as ctx:
        ctx.prec = 50
        h = Decimal(repr(x)) / 2
        return float((-h).exp() * sum(h ** k / factorial(k) for k in range(df // 2)))


def _bcg_yv():
    b = D["bcg"]
    e1, n1, e2, n2 = (np.array(b[k], float) for k in ("e1", "n1", "e2", "n2"))
    return np.log((e1 / n1) / (e2 / n2)), 1 / e1 - 1 / n1 + 1 / e2 - 1 / n2


def mixed_slope(C):
    o = D["ortho_long"]
    mt = multi_table([o["distance"], o["age"], o["subject"], o["male"]], ["distance", "age", "subject", "male"])
    r = analyze("mixed_model", mt, {"dependent": 0, "group": 2, "fixed": [1, 3], "randomSlope": 1, "method": "reml"})
    ref = R["lme_slope"]
    area = "Mixed models"
    case = "Orthodont: random intercept + slope (REML)"
    for j, nm in enumerate(["Intercept", "age", "male"]):
        C.add(area, case, f"{nm} estimate", cell(r, "Fixed effects", nm, 1), ref["fixed"][j], 4, "REML optimizers differ", "nlme::lme")
        C.add(area, case, f"{nm} SE", cell(r, "Fixed effects", nm, 2), ref["se"][j], 4, "GLS covariance (X'V⁻¹X)⁻¹ given the variance components", "nlme::lme")
    C.add(area, case, "SD of random intercepts", kv(r, "Random effects", "SD of random intercepts"), ref["sd_int"], 3, "", "nlme::lme")
    C.add(area, case, "SD of random slopes", kv(r, "Random effects", "SD of random slopes"), ref["sd_slope"], 3, "", "nlme::lme")
    C.add(area, case, "Residual SD", kv(r, "Random effects", "Residual SD"), ref["sigma"], 4, "", "nlme::lme")
    C.add(area, case, "REML log likelihood", kv(r, "Random effects", "Log likelihood"), ref["loglik"], 5, "", "nlme::lme")


def extended(C):
    """Checks against lmerTest, DescTools, WRS2, ARTool, clinfun, epiR and coin."""
    o = D["ortho_long"]
    mt = multi_table([o["distance"], o["age"], o["subject"], o["male"]], ["distance", "age", "subject", "male"])
    r = analyze("mixed_model", mt, {"dependent": 0, "group": 2, "fixed": [1, 3], "randomSlope": 1})
    area = "Mixed models"
    for j, nm in enumerate(["Intercept", "age", "male"]):
        C.add(area, "Orthodont random slope: Satterthwaite df", f"{nm} df", cell(r, "Fixed effects", nm, 3), R["lmert"]["df"][j], 4,
              "numerical derivatives of the REML likelihood in both programs", "lmerTest::lmer")
        C.add(area, "Orthodont random slope: Satterthwaite P", f"{nm} P value", cell(r, "Fixed effects", nm, 6), R["lmert"]["p"][j], 3,
              "P ≈ 1e-9…1e-17: far in the tail a tiny df difference changes P's later digits", "lmerTest::lmer")
    r = analyze("mixed_model", mt, {"dependent": 0, "group": 2, "fixed": [1, 3], "factors": [1]})
    for j, nm in enumerate(["age", "male"]):
        C.add(area, f"Orthodont: F test of {nm} ({'4-level factor' if nm == 'age' else '1 df'})", "F", cell(r, "Tests of fixed", nm, 1), R["lmert_f"]["F"][j], 4, "", "lmerTest anova (Satterthwaite)")
        C.add(area, f"Orthodont: F test of {nm} ({'4-level factor' if nm == 'age' else '1 df'})", "denominator df", cell(r, "Tests of fixed", nm, 3), R["lmert_f"]["dendf"][j], 4,
              "Fai & Cornelius multi-df Satterthwaite" if nm == "age" else "", "lmerTest anova (Satterthwaite)")
    g = list(D["plant"].values())
    names = list(D["plant"].keys())
    tp = column_table(g, names)
    for meth, key, pkg in [("dunn", "dunn", "DescTools::DunnTest"), ("conover", "conover", "DescTools::ConoverTest")]:
        r = analyze("np_posthoc", tp, {"method": meth, "adjust": "none"})
        rows = {x[0]: x for x in r["sections"][1]["rows"]}
        for rn, pv in zip(R[key]["names"], R[key]["p"]):
            b_, a_ = rn.split("-")
            row = rows.get(f"{a_} vs. {b_}") or rows.get(f"{b_} vs. {a_}")
            C.add("Nonparametric post hoc", f"PlantGrowth: {meth.title()} {rn}", "unadjusted P", number(row[3]), pv, 6, "", pkg)
    c = D["cont"]
    r = analyze("np_posthoc", tp, {"method": "dscf"})
    rows = {x[0]: x for x in r["sections"][1]["rows"]}
    for rn, pv in zip(R["dscf"]["names"].split(","), R["dscf"]["p"]):
        b_, a_ = rn.split("-")
        row = rows.get(f"{a_} vs. {b_}") or rows.get(f"{b_} vs. {a_}")
        C.add("Nonparametric post hoc", f"PlantGrowth: DSCF {rn}", "P (studentized range)", number(row[4]), pv, 4, "studentized range with infinite df", "PMCMRplus::dscfAllPairsTest")
    r = analyze("rm_nonparametric", column_table(D["rounding"]), {})
    nem = [number(x[1]) for x in section(r, "Post hoc")["rows"]]   # order: 1-2, 1-3, 2-3
    for (lab, ours), ref in zip([("1 vs 2", nem[0]), ("1 vs 3", nem[1]), ("2 vs 3", nem[2])], R["nemenyi"]):
        C.add("Nonparametric post hoc", f"RoundingTimes: Nemenyi {lab}", "P", ours, ref, 4, "", "PMCMRplus::frdAllPairsNemenyiTest")
    r = analyze("trend_tests", column_table([c["x"], c["y"], c["z"]]), {"permutations": 0})
    jt = next(x for x in section(r, "Trend tests")["rows"] if x[0].startswith("Jonckheere-Terpstra (non"))
    C.add("Trend tests", "three samples (no ties): Jonckheere-Terpstra", "two-sided P (normal approx.)", number(jt[3]), R["jt"]["p"], 6, "", "DescTools::JonckheereTerpstraTest")
    C.add("Trend tests", "three samples (no ties): Jonckheere-Terpstra", "J statistic", number(jt[5], 0), R["jt"]["stat"], 6, "", "DescTools::JonckheereTerpstraTest")
    r = analyze("robust_compare", column_table([c["x"], c["y"]]), {})
    area = "Robust tests"
    C.add(area, "two samples: Yuen-Welch (20% trimming)", "|t|", abs(kv(r, "Yuen", "t")), R["yuen"]["t"], 6, "", "WRS2::yuen")
    C.add(area, "two samples: Yuen-Welch (20% trimming)", "df", kv(r, "Yuen", "df"), R["yuen"]["df"], 6, "", "WRS2::yuen")
    C.add(area, "two samples: Yuen-Welch (20% trimming)", "P value", kv(r, "Yuen", "P value"), R["yuen"]["p"], 6, "", "WRS2::yuen")
    C.add(area, "two samples: Yuen-Welch (20% trimming)", "difference of trimmed means", kv(r, "Yuen", "Difference"), R["yuen"]["diff"], 6, "", "WRS2::yuen")
    lo, hi = ci_of(kv_str(r, "Yuen", "95% CI"))
    C.add(area, "two samples: Yuen-Welch (20% trimming)", "95% CI lower", lo, R["yuen"]["ci"][0], 6, "", "WRS2::yuen")
    r = analyze("robust_compare", tp, {})
    C.add(area, "PlantGrowth: Wilcox t1way (trimmed means)", "F", kv(r, "Heteroscedastic", "F"), R["t1way"]["F"], 6, "", "WRS2::t1way")
    C.add(area, "PlantGrowth: Wilcox t1way (trimmed means)", "denominator df", kv(r, "Heteroscedastic", "df denominator"), R["t1way"]["df2"], 6, "", "WRS2::t1way")
    C.add(area, "PlantGrowth: Wilcox t1way (trimmed means)", "P value", kv(r, "Heteroscedastic", "P value"), R["t1way"]["p"], 6, "", "WRS2::t1way")
    tg = D["tooth"]
    supp = sorted(set(tg["supp"]))
    doses = sorted(set(tg["dose"]))
    cells = [[v for s_ in supp for v, ss, dd in zip(tg["len"], tg["supp"], tg["dose"]) if ss == s_ and dd == dose] for dose in doses]
    t2 = make_table("tooth", "grouped", [{"name": s_, "reps": 10} for s_ in supp], cells, row_labels=[str(d) for d in doses])
    r = analyze("two_way_np", t2, {})
    rows = {x[0]: x for x in section(r, "Aligned rank")["rows"]}
    for lab, k in [("Column factor", 0), ("Row factor", 1), ("Interaction", 2)]:
        C.add("Nonparametric two-way ANOVA", f"ToothGrowth ART: {lab}", "F", number(rows[lab][1], 2), R["art"]["F"][k], 6, "", "ARTool::art")
    area = "Agreement and association"
    r = analyze("kappa", ct_table(D["kappa"]), {})
    rows = {x[0]: x for x in section(r, "Kappa")["rows"]}
    for lab, key in [("Unweighted κ", "k"), ("Linear-weighted κ", "kl"), ("Quadratic-weighted κ (≈ ICC)", "kq")]:
        lo, hi = ci_of(rows[lab][3])
        C.add(area, f"3-category agreement: {lab} 95% CI", "lower", lo, R["kappa_ci"][key][1], 4, "asymptotic SE (Fleiss, Cohen & Everitt)", "DescTools::CohenKappa")
        C.add(area, f"3-category agreement: {lab} 95% CI", "upper", hi, R["kappa_ci"][key][2], 4, "", "DescTools::CohenKappa")
        C.add(area, f"3-category agreement: {lab}", "κ", number(rows[lab][1]), R["kappa_ci"][key][0], 6, "", "DescTools::CohenKappa")
    sl = D["sleep"]
    r = analyze("reliability", column_table([sl["g1"], sl["g2"]]), {})
    C.add(area, "sleep: Lin's concordance correlation", "ρc", kv(r, "Lin", "CCC"), R["ccc"][0], 6, "", "DescTools::CCC")
    lo, hi = ci_of(kv_str(r, "Lin", "95% CI"))
    C.add(area, "sleep: Lin's concordance correlation", "95% CI lower (Fisher z)", lo, R["ccc"][1], 6, "", "DescTools::CCC")
    C.add(area, "sleep: Lin's concordance correlation", "95% CI upper", hi, R["ccc"][2], 6, "", "DescTools::CCC")
    sf = D["sf"]
    r = analyze("reliability", column_table([[row[j] for row in sf] for j in range(4)]), {})
    C.add(area, "Shrout & Fleiss data: Kendall's W (ties corrected)", "W", kv(r, "Kendall's coefficient", "W"), R["kendallw"], 6, "", "DescTools::KendallW")
    r = analyze("contingency_more", ct_table(D["rc"]), {})
    C.add(area, "3 × 3 table: Goodman-Kruskal γ", "γ", kv(r, "Measures", "Goodman"), R["assoc"]["gamma"], 6, "", "DescTools::GoodmanKruskalGamma")
    C.add(area, "3 × 3 table: Kendall τ-b", "τ-b", kv(r, "Measures", "Kendall τ-b (ord"), R["assoc"]["taub"], 6, "", "DescTools::KendallTauB")
    C.add(area, "3 × 3 table: G test", "G", cell(r, "Tests", "G test (likelihood", "Statistic"), R["gtest"]["G"], 6, "", "DescTools::GTest")
    C.add(area, "3 × 3 table: G test", "P value", cell(r, "Tests", "G test (likelihood", "P value"), R["gtest"]["p"], 6, "", "DescTools::GTest")
    C.add(area, "3 × 3 table: G test with Williams' correction", "G", cell(r, "Tests", "G test with Williams", "Statistic"), R["gtest"]["Gw"], 6, "", "DescTools::GTest")
    r = analyze("contingency_more", ct_table(D["square3"]), {})
    C.add(area, "3 × 3 paired table: Stuart-Maxwell", "χ²", cell(r, "Tests", "Stuart-Maxwell", "Statistic"), R["stuart"]["stat"], 6, "", "DescTools::StuartMaxwellTest")
    ucb = [row for tab in D["ucb"] for row in tab]
    r = analyze("cmh", ct_table(ucb), {})
    C.add(area, "UCB admissions: Breslow-Day (Tarone) homogeneity", "χ²", kv(r, "Pooled", "Breslow-Day"), R["breslowday"]["stat"], 6, "", "DescTools::BreslowDayTest")
    C.add(area, "UCB admissions: Breslow-Day (Tarone) homogeneity", "P value", kv(r, "Pooled", "P value (homogeneity)"), R["breslowday"]["p"], 6, "", "DescTools::BreslowDayTest")
    area = "Normality, randomness, one-sample"
    r = analyze("normality", column_table([sl["g2"]]), {"tests": ["jb"]})
    row = section(r, "Tests for normal")["rows"][0]
    C.add(area, "sleep group 2: Jarque-Bera", "JB", number(row[2]), R["jb"]["stat"], 6, "", "DescTools::JarqueBeraTest")
    C.add(area, "sleep group 2: Jarque-Bera", "P value", number(row[3]), R["jb"]["p"], 6, "", "DescTools::JarqueBeraTest")
    r = analyze("normality", column_table([c["x"] + c["y"]]), {"tests": ["sf"]})
    row = section(r, "Tests for normal")["rows"][0]
    C.add(area, "31 values: Shapiro-Francia", "W'", number(row[2]), R["sf"]["W"], 6, "", "DescTools::ShapiroFranciaTest")
    C.add(area, "31 values: Shapiro-Francia", "P value (Royston)", number(row[3]), R["sf"]["p"], 6, "", "DescTools::ShapiroFranciaTest")
    r = analyze("randomness", column_table([D["nile"]]), {})
    C.add(area, "Nile: Wald-Wolfowitz runs test (median)", "|z|", abs(cell(r, "G1", "Wald-Wolfowitz", "Statistic")), abs(R["runs"]["z"]), 6, "", "DescTools::RunsTest")
    C.add(area, "Nile: Wald-Wolfowitz runs test (median)", "P value", cell(r, "G1", "Wald-Wolfowitz", "P value"), R["runs"]["p"], 6, "", "DescTools::RunsTest")
    C.add(area, "Nile: von Neumann ratio", "ratio", cell(r, "G1", "von Neumann", "Statistic"), R["vonneumann"]["stat"][0], 6, "", "DescTools::VonNeumannTest")
    C.add(area, "Nile: von Neumann ratio", "P value", cell(r, "G1", "von Neumann", "P value"), R["vonneumann"]["p"], 6, "", "DescTools::VonNeumannTest")
    r = analyze("one_sample_more", column_table([sl["g2"]]), {"median": 1})
    lo, hi = ci_of(kv_str(r, "G1", "95% CI of SD"))
    C.add(area, "sleep group 2: 95% CI of the SD (χ²)", "lower", lo, R["sdci"][0], 6, "", "DescTools::VarCI")
    C.add(area, "sleep group 2: 95% CI of the SD (χ²)", "upper", hi, R["sdci"][1], 6, "", "DescTools::VarCI")
    C.add(area, "sleep group 2: sign test vs median 1", "exact P", kv(r, "G1", "P value (exact binomial)"), R["signtest"], 6, "", "DescTools::SignTest")
    r = analyze("proportion", ct_table([[682, 925 - 682]]), {})
    row = section(r, "Proportion")["rows"][0]
    C.add("Contingency tables and proportions", "682 of 925: Agresti-Coull CI", "lower", number(row[7], 0), R["agresti"][0], 6, "", "DescTools::BinomCI")
    C.add("Contingency tables and proportions", "682 of 925: Agresti-Coull CI", "upper", number(row[7], 1), R["agresti"][1], 6, "", "DescTools::BinomCI")
    r = analyze("diagnostic", ct_table([[90, 15], [10, 185]]), {"ciMethod": "clopper"})
    rows = {x[0].split(" (")[0]: x for x in r["sections"][0]["rows"]}
    for lab, key in [("Sensitivity", "se"), ("Specificity", "sp")]:
        C.add("Diagnostic accuracy", f"2 × 2: {lab}", "estimate", number(rows[lab][1]), R["diag"][key][0], 6, "", "epiR::epi.tests")
        C.add("Diagnostic accuracy", f"2 × 2: {lab} (Clopper-Pearson)", "CI lower", number(rows[lab][2], 0), R["diag"][key][1], 6, "", "epiR::epi.tests")
        C.add("Diagnostic accuracy", f"2 × 2: {lab} (Clopper-Pearson)", "CI upper", number(rows[lab][2], 1), R["diag"][key][2], 6, "", "epiR::epi.tests")
    for lab, key in [("Positive likelihood ratio LR+", "lrpos"), ("Negative likelihood ratio LR−", "lrneg")]:
        C.add("Diagnostic accuracy", f"2 × 2: {lab}", "estimate", number(rows[lab][1]), R["diag"][key][0], 6, "", "epiR::epi.tests")
        C.add("Diagnostic accuracy", f"2 × 2: {lab}", "CI lower (log method)", number(rows[lab][2], 0), R["diag"][key][1], 6, "", "epiR::epi.tests")
    a = D["aml"]
    tsv = make_table("s", "survival", [{"name": "Maintained", "reps": 1}, {"name": "Nonmaintained", "reps": 1}],
                     [[st if m == 1 else None, st if m == 0 else None] for st, m in zip(a["status"], a["maintained"])], x=a["time"])
    r = analyze("survival_more", tsv, {})
    for lab, key in [("Tarone-Ware", "tw"), ("Peto-Peto", "pp"), ("Gehan-Breslow-Wilcoxon", "gehan")]:
        C.add("Survival analysis", f"aml: {lab}", "χ²", cell(r, "Comparison", lab, "Statistic"), R["weighted_lr"][key], 6,
              "hypergeometric variance (Klein & Moeschberger 7.3)", "independent R implementation")


def competing(C):
    cr = D["cr"]
    t = make_table("cr", "survival", [{"name": "All", "reps": 1}], [[s] for s in cr["status"]], x=cr["time"])
    for tp, ref in zip(R["cuminc"]["times"], R["cuminc"]["est"]):
        r = analyze("competing_risks", t, {"horizon": tp})
        C.add("Survival analysis", f"simulated competing risks: cumulative incidence at t = {tp}", "CIF", number(kv_str(r, "All at time", "Cumulative incidence")) / 100, ref, 6, "", "cmprsk::cuminc")
    if "gray" not in R:
        return
    gd, gr = D["gray"], R["gray"]
    names = ["G0", "G1", "G2"]
    # cmprsk's exact handling of tied event times in the variance is not published; ours uses the usual
    # (n - d)/(n - 1) correction, which agrees to 3-5 digits on heavily tied data and to ~14 digits without ties.
    for label, times, ref, lre in [("tied times", gd["time"], gr["tied"], 3), ("no ties", gd["time_untied"], gr["untied"], 9)]:
        cells = [[None] * 3 for _ in times]
        for i, (g, s_) in enumerate(zip(gd["group"], gd["status"])):
            cells[i][int(g)] = int(s_)
        r = analyze("competing_risks", make_table("gray", "survival", [{"name": nm, "reps": 1} for nm in names], cells, x=list(times)), {})
        rows = next(s_ for s_ in r["sections"] if s_["title"].startswith("Gray"))["rows"]
        for row, rv, what in zip(rows, ref, ["event of interest", "competing event"]):
            C.add("Survival analysis", f"simulated 3 groups ({label}): Gray's test, {what}", "χ²", number(row[1]), rv, lre,
                  "many ties (times rounded to 0.1); tie correction differs slightly from cmprsk's unpublished rule" if label == "tied times" else "", "cmprsk::cuminc")
    cols = [gd["time"], gd["status"], gd["x"], [int(g == 1) for g in gd["group"]], [int(g == 2) for g in gd["group"]]]
    tab = multi_table(cols, ["time", "status", "x", "g1", "g2"])
    for cause, key in [(1, "fg1"), (2, "fg2")]:
        r = analyze("fine_gray", tab, {"timeVar": 0, "eventVar": 1, "cause": cause})
        rows = r["sections"][0]["rows"]
        for row, b, se in zip(rows, gr[key]["b"], gr[key]["se"]):
            C.add("Survival analysis", f"Fine-Gray (cause {cause}): {row[0]}", "β", number(row[1]), b, 6, "", "cmprsk::crr")
            C.add("Survival analysis", f"Fine-Gray (cause {cause}): {row[0]}", "robust SE", number(row[2]), se, 6, "sandwich incl. censoring term", "cmprsk::crr")
    r = analyze("fine_gray", tab, {"timeVar": 0, "eventVar": 1})
    C.add("Survival analysis", "Fine-Gray (cause 1)", "pseudo log-likelihood", kv(r, "Model", "Pseudo log-likelihood"), gr["fg1"]["ll"], 9, "", "cmprsk::crr")


def find_variance(r):
    res = sub = None
    for s in r["sections"]:
        for x in s["rows"]:
            lab = str(x[0]).lower()
            if "residual" in lab and ("sd" in lab or "standard deviation" in lab):
                res = number(x[1])
            if "subject" in lab and ("sd" in lab or "standard deviation" in lab):
                sub = number(x[1])
    return (res, sub) if res is not None and sub is not None else None


def power(C):
    from openprism.stats.multivariate import power as pw
    area = "Power and sample size"
    r = pw({"test": "ttest2", "n": 20, "difference": 1, "sd": 1.5})
    C.add(area, "two-sample t test, n = 20, δ = 1, σ = 1.5", "Power", r["power"], R["power"]["t"], 6, "both rejection tails (strict = TRUE)", "power.t.test")
    r = pw({"test": "anova", "n": 5, "f": 0.5, "groups": 4})
    C.add(area, "one-way ANOVA, 4 groups, n = 5, f = 0.5", "Power", r["power"], R["power"]["anova"], 6, "", "power.anova.test")
    r = pw({"test": "logrank", "hr": 0.5, "pevent": 1, "power": 0.8})
    C.add(area, "log-rank, HR 0.5, 80% power, α 0.05 (Schoenfeld)", "events (exact)", r["nExact"] * 2, 4 * (1.959963984540054 + 0.8416212335729143) ** 2 / math.log(0.5) ** 2, 6,
          "closed form 4(z₀.₉₇₅ + z₀.₈)² / ln(HR)² = 65.35 → 66 events (Collett 2015)", "textbook formula")
    r = pw({"test": "mcnemar", "p10": 0.15, "p01": 0.05, "power": 0.9})
    C.add(area, "McNemar, p10 0.15 vs p01 0.05, 90% power (Connor)", "pairs (exact)", r["nExact"], 205.9620841, 6, "Connor (1987) formula", "textbook formula")
    r = pw({"test": "ttest2", "power": 0.8, "difference": 1, "sd": 1.5})
    C.add(area, "two-sample t test, power 0.8: n per group", "n (exact, before rounding up)", r["nExact"], R["power"]["n_t"], 4, "R's uniroot tolerance", "power.t.test")


def run_all():
    C = Checks()
    for fn in (two_groups, distributions, anova, regression, glms, counts, survival, multivariate, mixed_slope, extended, competing, power):
        try:
            fn(C)
        except Exception as e:  # noqa: BLE001  (report, keep going)
            import traceback
            C.fail(fn.__name__, "(module)", f"{type(e).__name__}: {e} @ {traceback.format_exc().splitlines()[-3].strip()}")
    return C.out
