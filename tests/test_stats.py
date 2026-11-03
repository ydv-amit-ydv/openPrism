"""Validation of the statistics engine against SciPy / statsmodels / textbook values."""
import math

import numpy as np
import pytest
from scipy import stats

from openprism.stats import ANALYSES, run
from openprism.stats.common import holm_sidak, pairwise_pooled, stars
from openprism.stats.regression import fit_model
from openprism.stats.survival import km, logrank
from openprism.tables import make_table, parse_table


def column_table(*cols, names=None):
    n = max(len(c) for c in cols)
    cells = [[(c[i] if i < len(c) else None) for c in cols] for i in range(n)]
    names = names or [f"G{i}" for i in range(len(cols))]
    return parse_table(make_table("t", "column", [{"name": nm, "reps": 1} for nm in names], cells))


def kv(result, section_title):
    for s in result["sections"]:
        if s["title"] == section_title:
            return dict((r[0], r[1]) for r in s["rows"])
    raise KeyError(section_title)


def section(result, title):
    return next(s for s in result["sections"] if s["title"].startswith(title))


A = [12.1, 14.3, 11.8, 13.5, 15.2, 12.9, 13.3]
B = [16.2, 18.1, 17.5, 19.0, 16.8, 18.4, 17.1]
C = [13.0, 14.1, 12.2, 15.5, 13.9, 14.4, 12.8]


def test_parse_table_handles_replicates_and_blanks():
    t = parse_table(make_table("x", "xy", [{"name": "a", "reps": 2}], [[1, ""], [2, 3]], x=[0, 1]))
    assert t.Y[0].shape == (2, 2)
    assert np.isnan(t.Y[0][0, 1])
    assert list(t.column_values(0)) == [1, 2, 3]
    x, y = t.xy_points(0)
    assert list(x) == [0, 1, 1] and list(y) == [1, 2, 3]


def test_stars_thresholds():
    assert stars(0.2) == "ns"
    assert stars(0.04) == "*"
    assert stars(0.009) == "**"
    assert stars(0.0009) == "***"
    assert stars(0.00009) == "****"


def test_unpaired_t_matches_scipy():
    r = run("ttest", column_table(A, B), {})
    p = stats.ttest_ind(B, A).pvalue
    out = kv(r, "Unpaired t test")
    assert out["P value"] == ("<0.0001" if p < 1e-4 else f"{p:.4f}")
    assert r["overlay"]["pairs"][0]["p"] == pytest.approx(p)


def test_welch_and_paired_and_nonparametric():
    t = column_table(A, B)
    assert run("ttest", t, {"welch": True})["overlay"]["pairs"][0]["p"] == pytest.approx(stats.ttest_ind(B, A, equal_var=False).pvalue)
    assert run("ttest", t, {"paired": True})["overlay"]["pairs"][0]["p"] == pytest.approx(stats.ttest_rel(B, A).pvalue)
    assert run("ttest", t, {"parametric": False})["overlay"]["pairs"][0]["p"] == pytest.approx(stats.mannwhitneyu(B, A).pvalue)
    assert run("ttest", t, {"paired": True, "parametric": False})["overlay"]["pairs"][0]["p"] == pytest.approx(stats.wilcoxon(B, A).pvalue)


def test_one_way_anova_and_tukey_match_scipy():
    r = run("one_way", column_table(A, B, C), {"comparison": "tukey"})
    F, p = stats.f_oneway(A, B, C)
    assert float(kv(r, "ANOVA summary")["F"]) == pytest.approx(F, rel=1e-3)
    tk = stats.tukey_hsd(A, B, C)
    pairs = {(o["a"], o["b"]): o["p"] for o in r["overlay"]["pairs"]}
    for (i, j), pv in pairs.items():
        assert pv == pytest.approx(tk.pvalue[i, j], abs=2e-3)


def test_dunnett_matches_scipy():
    r = run("one_way", column_table(A, B, C), {"comparison": "dunnett", "control": 0})
    ref = stats.dunnett(B, C, control=A)
    got = [o["p"] for o in r["overlay"]["pairs"]]
    assert got == pytest.approx(list(ref.pvalue), abs=5e-3)


def test_kruskal_and_friedman():
    r = run("one_way", column_table(A, B, C), {"parametric": False})
    H, p = stats.kruskal(A, B, C)
    assert float(kv(r, "Kruskal-Wallis test")["Kruskal-Wallis statistic"]) == pytest.approx(H, rel=1e-3)
    r = run("one_way", column_table(A, B, C), {"parametric": False, "repeated": True})
    chi, p = stats.friedmanchisquare(A, B, C)
    assert float(kv(r, "Friedman test")["Friedman statistic"]) == pytest.approx(chi, rel=1e-3)


def test_repeated_measures_anova_against_statsmodels():
    import pandas as pd
    from statsmodels.stats.anova import AnovaRM
    r = run("one_way", column_table(A, B, C), {"repeated": True, "geisser": False})
    df = pd.DataFrame([{"s": i, "c": c, "y": v} for c, col in enumerate([A, B, C]) for i, v in enumerate(col)])
    ref = AnovaRM(df, "y", "s", within=["c"]).fit().anova_table
    assert float(kv(r, "Repeated measures ANOVA summary")["F"]) == pytest.approx(ref["F Value"].iloc[0], rel=1e-3)


def test_holm_sidak_monotone():
    adj = holm_sidak([0.01, 0.04, 0.03])
    assert adj[0] < adj[2] <= adj[1] <= 1


def test_pairwise_bonferroni_simple():
    comps = pairwise_pooled([1.0, 2.0], [5, 5], ["a", "b"], mse=1.0, df=8, method="bonferroni")
    t = -1 / math.sqrt(0.4)
    assert comps[0]["p"] == pytest.approx(2 * stats.t.sf(abs(t), 8))


def test_two_way_anova_against_statsmodels():
    rng = np.random.default_rng(1)
    cells = []
    for r_ in range(3):
        row = []
        for c in range(2):
            row += list(10 + 2 * r_ + 3 * c + rng.normal(0, 1, 3))
        cells.append(row)
    t = parse_table(make_table("g", "grouped", [{"name": "A", "reps": 3}, {"name": "B", "reps": 3}], cells,
                               row_labels=["r1", "r2", "r3"]))
    res = run("two_way", t, {"comparison": "sidak"})
    tab = section(res, "ANOVA table")
    names = [row[0] for row in tab["rows"]]
    assert names[:3] == ["Interaction", "Row Factor", "Column Factor"]
    assert res["overlay"]["kind"] == "grouped-pairs" and len(res["overlay"]["pairs"]) == 3


def test_nonlinear_four_parameter_recovers_parameters():
    x = np.linspace(-9, -5, 9)
    true = (5, 100, -7.0, 1.2)
    y = true[0] + (true[1] - true[0]) / (1 + 10 ** ((true[2] - x) * true[3]))
    fit = fit_model("logagonist4", x, y)
    assert fit["full"] == pytest.approx(true, rel=1e-4, abs=1e-4)
    assert fit["r2"] == pytest.approx(1.0)


def test_nonlinear_analysis_output_and_interpolation():
    x = np.array([0.5, 1, 2, 4, 8, 16, 32, 64.0])
    y = 120 * x / (6 + x)
    t = parse_table(make_table("e", "xy", [{"name": "v", "reps": 1}], [[v] for v in y], x=x))
    r = run("nonlinear", t, {"model": "mm", "interpolate": "60"})
    best = {row[0]: float(row[1]) for row in section(r, "Best-fit values")["rows"]}
    assert best["Vmax"] == pytest.approx(120, rel=1e-4)
    assert best["Km"] == pytest.approx(6, rel=1e-4)
    interp = section(r, "Interpolated")["rows"][0]
    assert float(interp[2]) == pytest.approx(6, rel=1e-3)  # Y = Vmax/2 at X = Km
    assert r["overlay"]["kind"] == "curves" and len(r["overlay"]["curves"][0]["x"]) == 200


def test_constrained_fit():
    x = np.array([0.5, 1, 2, 4, 8, 16.0])
    y = 100 * x / (5 + x)
    fit = fit_model("mm", x, y, constraints={"Km": "5"})
    assert fit["full"][1] == 5 and fit["full"][0] == pytest.approx(100, rel=1e-6)


def test_linear_regression_matches_linregress():
    x = np.arange(10.0)
    y = 2 * x + 1 + np.array([0.1, -0.2, 0.05, 0.3, -0.1, 0.0, 0.2, -0.3, 0.1, -0.05])
    t = parse_table(make_table("l", "xy", [{"name": "y", "reps": 1}], [[v] for v in y], x=x))
    r = run("linear", t, {})
    lr = stats.linregress(x, y)
    rows = {row[0]: row[1] for row in section(r, "Best-fit values")["rows"]}
    assert float(rows["Slope"]) == pytest.approx(lr.slope, rel=1e-3)
    assert float(rows["R squared"]) == pytest.approx(lr.rvalue ** 2, rel=1e-3)


def test_correlation():
    x = np.arange(10.0)
    y = x ** 1.5
    t = parse_table(make_table("c", "xy", [{"name": "y", "reps": 1}], [[v] for v in y], x=x))
    r = run("correlation", t, {"method": "spearman"})
    assert float(section(r, "Correlation")["rows"][0][1]) == pytest.approx(1.0)


def test_kaplan_meier_textbook():
    # classic example: times with censoring
    t = np.array([6, 6, 6, 6, 7, 9, 10, 10, 11, 13, 16, 17, 19, 20, 22, 23, 25, 32, 32, 34, 35.0])
    e = np.array([1, 1, 1, 0, 1, 0, 1, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0])
    c = km(t, e)
    s = {tt: sv for tt, sv, *_ in c}
    assert s[6] == pytest.approx(0.857, abs=1e-3)
    assert s[7] == pytest.approx(0.807, abs=1e-3)
    assert s[10] == pytest.approx(0.753, abs=1e-3)
    assert s[23] == pytest.approx(0.448, abs=1e-3)


def test_logrank_two_groups_against_known_value():
    # Gehan leukemia data (6-MP vs placebo): log-rank chi-square ≈ 16.79
    t1 = np.array([6, 6, 6, 6, 7, 9, 10, 10, 11, 13, 16, 17, 19, 20, 22, 23, 25, 32, 32, 34, 35.0])
    e1 = np.array([1, 1, 1, 0, 1, 0, 1, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0])
    t2 = np.array([1, 1, 2, 2, 3, 4, 4, 5, 5, 8, 8, 8, 8, 11, 11, 12, 12, 15, 17, 22, 23.0])
    e2 = np.ones(21, int)
    chi, p, O, E = logrank([(t1, e1), (t2, e2)])
    assert chi == pytest.approx(16.79, abs=0.05)
    assert p < 0.0001


def test_survival_analysis_endpoint_shape():
    x = [5, 8, 12, 3, 9, 15]
    cells = [[1, None], [0, None], [1, None], [None, 1], [None, 1], [None, 0]]
    t = parse_table(make_table("s", "survival", [{"name": "a", "reps": 1}, {"name": "b", "reps": 1}], cells, x=x))
    r = run("survival", t, {})
    assert r["overlay"]["kind"] == "km" and len(r["overlay"]["curves"]) == 2


def test_contingency_fisher_and_chi_square():
    t = parse_table(make_table("c", "contingency", [{"name": "y", "reps": 1}, {"name": "n", "reps": 1}],
                               [[42, 58], [18, 82]], row_labels=["e", "u"]))
    r = run("contingency", t, {})
    tests = kv(r, "Tests")
    p = stats.fisher_exact([[42, 58], [18, 82]])[1]
    assert tests["Fisher's exact test P value"] == ("<0.0001" if p < 1e-4 else f"{p:.4f}")
    eff = kv(r, "Effect size")
    assert float(eff["Odds ratio"]) == pytest.approx((42 * 82) / (58 * 18), rel=1e-3)


def test_normality_and_descriptive():
    rng = np.random.default_rng(3)
    v = list(rng.normal(10, 2, 40))
    r = run("descriptive", column_table(v), {})
    rows = {row[0]: row[1] for row in r["sections"][0]["rows"]}
    assert float(rows["Mean"]) == pytest.approx(np.mean(v), rel=1e-3)
    assert float(rows["Std. Deviation"]) == pytest.approx(np.std(v, ddof=1), rel=1e-3)
    r = run("normality", column_table(v), {})
    assert any(row[1] == "Shapiro-Wilk" for row in r["sections"][0]["rows"])


def test_outliers_grubbs_detects_obvious_outlier():
    r = run("outliers", column_table([10, 11, 10.5, 9.8, 10.2, 10.1, 30]), {"method": "grubbs"})
    assert section(r, "Outliers")["rows"][0][1] == "30"
    assert r["outputTables"][0]["cells"][-1] != ["30"]


def test_roc_auc_matches_mann_whitney():
    ctrl = [1, 2, 3, 4, 5.0]
    pat = [3, 4, 5, 6, 7.0]
    r = run("roc", column_table(ctrl, pat), {})
    auc = stats.mannwhitneyu(pat, ctrl).statistic / 25
    assert float(kv(r, "Area under the ROC curve")["Area"]) == pytest.approx(auc, rel=1e-3)


def test_transform_and_normalize_create_tables():
    t = column_table([1, 10, 100], [2, 20, 200])
    r = run("transform", t, {"function": "log10"})
    assert r["outputTables"][0]["cells"][1][0] == "1"
    r = run("normalize", t, {})
    assert r["outputTables"][0]["cells"][2] == ["100", "100"]


def test_every_registered_analysis_is_callable():
    assert all(callable(v[0]) for v in ANALYSES.values())


# ---------------------------------------------------------------- new analyses
from sample_tables import TABLES  # noqa: E402


def _rows(res, title):
    return {r[0]: r[1:] for r in section(res, title)["rows"]}


def test_multiple_regression_matches_statsmodels():
    import statsmodels.api as sm
    t = parse_table(TABLES["multi"])
    r = run("multiple_regression", t, {"dependent": 3, "predictors": [0, 1]})
    X = sm.add_constant(np.column_stack([t.Y[0][:, 0], t.Y[1][:, 0]]))
    ref = sm.OLS(t.Y[3][:, 0], X).fit()
    rows = _rows(r, "Parameter estimates")
    assert float(rows["Age"][0]) == pytest.approx(ref.params[1], rel=1e-3)
    assert float(kv(r, "Goodness of fit")["R squared"]) == pytest.approx(ref.rsquared, rel=1e-3)


def test_logistic_regression_odds_ratio():
    import statsmodels.api as sm
    t = parse_table(TABLES["multi"])
    r = run("logistic", t, {"dependent": 4, "predictors": [0]})
    ref = sm.Logit(t.Y[4][:, 0], sm.add_constant(t.Y[0][:, 0])).fit(disp=0)
    assert float(_rows(r, "Parameter estimates")["Age"][2]) == pytest.approx(math.exp(ref.params[1]), rel=1e-3)


def test_cox_regression_matches_statsmodels():
    from statsmodels.duration.hazard_regression import PHReg
    t = parse_table(TABLES["multi"])
    r = run("cox", t, {"timeVar": 5, "eventVar": 6, "predictors": [0]})
    ref = PHReg(t.Y[5][:, 0], t.Y[0][:, [0]], status=t.Y[6][:, 0], ties="efron").fit()
    assert float(_rows(r, "Hazard ratios")["Age"][2]) == pytest.approx(math.exp(ref.params[0]), rel=1e-3)


def test_pca_eigenvalues_sum_to_number_of_variables_when_standardized():
    t = parse_table(TABLES["multi"])
    r = run("pca", t, {"datasets": [0, 1, 2, 3]})
    eig = [float(row[1]) for row in section(r, "Eigenvalues")["rows"]]
    assert sum(eig) == pytest.approx(4, rel=1e-3)
    assert r["outputTables"][0]["type"] == "multi"


def test_bland_altman_limits():
    t = parse_table(TABLES["methods"])
    r = run("bland_altman", t, {})
    a, b = t.Y[0][:, 0], t.Y[1][:, 0]
    d = a - b
    out = kv(r, "Bias and limits of agreement")
    assert float(out["Bias (mean difference)"]) == pytest.approx(d.mean(), rel=1e-3)
    lo, hi = [float(v) for v in out["95% limits of agreement"].split(" to ")]
    assert lo == pytest.approx(d.mean() - 1.96 * d.std(ddof=1), rel=1e-3)


def test_custom_equation_fit_matches_builtin():
    x = np.array([0.5, 1, 2, 4, 8, 16, 32.0])
    y = 80 * x / (3 + x)
    t = parse_table(make_table("e", "xy", [{"name": "v", "reps": 1}], [[v] for v in y], x=x))
    r = run("nonlinear", t, {"model": "custom", "equation": "Y = Vmax*X/(Km + X)", "initial": "Vmax=50, Km=1"})
    best = {row[0]: float(row[1]) for row in section(r, "Best-fit values")["rows"]}
    assert best["Vmax"] == pytest.approx(80, rel=1e-4) and best["Km"] == pytest.approx(3, rel=1e-4)


def test_custom_equation_rejects_code():
    from openprism.stats.common import AnalysisError
    from openprism.stats.custom_eq import custom_model
    for bad in ['Y = __import__("os").system("x")', "Y = X.__class__", "Y = [X]", "Y = lambda: X"]:
        with pytest.raises(AnalysisError):
            custom_model(bad)


def test_global_fit_shared_parameter():
    x = np.linspace(-9, -5, 9)
    f = lambda x, ec: 100 / (1 + 10 ** ((ec - x) * 1.0))  # noqa: E731
    cells = [[f(v, -7.0), f(v, -6.0)] for v in x]
    t = parse_table(make_table("g", "xy", [{"name": "a", "reps": 1}, {"name": "b", "reps": 1}], cells, x=x))
    r = run("nonlinear", t, {"model": "logagonist4", "shared": ["Bottom", "Top", "HillSlope"]})
    rows = {row[0]: row[1:] for row in section(r, "Global fit — shared")["rows"]}
    assert float(rows["LogEC50"][0]) == pytest.approx(-7, abs=1e-3)
    assert float(rows["LogEC50"][1]) == pytest.approx(-6, abs=1e-3)
    assert rows["Top (shared)"][0] == rows["Top (shared)"][1]


def test_smoothing_and_derivative():
    x = np.linspace(0, 10, 21)
    t = parse_table(make_table("s", "xy", [{"name": "y", "reps": 1}], [[v * v] for v in x], x=x))
    r = run("smooth", t, {"operation": "derivative"})
    mid = r["outputTables"][0]["cells"][10][0]
    assert float(mid) == pytest.approx(10, rel=1e-2)  # d(x^2)/dx at x=5
    r = run("smooth", t, {"operation": "integral"})
    assert float(r["outputTables"][0]["cells"][-1][0]) == pytest.approx(1000 / 3, rel=1e-2)


def test_normality_has_qq_plot():
    r = run("normality", column_table(A, B), {})
    assert r["overlay"]["kind"] == "plot" and r["overlay"]["plots"][0]["title"] == "Normal Q-Q plot"


def test_power_classic_values():
    from openprism.stats.multivariate import power
    assert power({"test": "ttest2", "difference": 0.5, "sd": 1, "power": 0.8})["n"] == 64
    assert power({"test": "ttest2", "difference": 1, "sd": 1, "n": 17})["power"] == pytest.approx(0.807, abs=0.01)
    assert power({"test": "corr", "r": 0.3, "power": 0.8})["n"] in (84, 85)
