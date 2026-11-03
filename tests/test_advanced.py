"""Validation of mixed models, nested designs, n-way ANOVA, method-comparison
regression, Poisson regression, ROUT and the beyond-Prism methods."""
import math

import numpy as np
import pytest
from scipy import stats

from openprism.stats import run
from openprism.tables import make_table, parse_table

rng = np.random.default_rng(5)


def col_table(*cols):
    n = max(len(c) for c in cols)
    cells = [[(c[i] if i < len(c) else None) for c in cols] for i in range(n)]
    return parse_table(make_table("t", "column", [{"name": f"G{i}", "reps": 1} for i in range(len(cols))], cells))


def kv(res, title):
    for s in res["sections"]:
        if s["title"].startswith(title):
            return {r[0]: r[1] for r in s["rows"]}
    raise KeyError(title)


def sec(res, title):
    return next(s for s in res["sections"] if s["title"].startswith(title))


A = list(rng.normal(10, 2, 12))
B = list(rng.normal(12, 4, 15))
C3 = list(rng.normal(11, 3, 10))


def test_games_howell_two_groups_equals_welch():
    r = run("one_way", col_table(A, B), {"comparison": "games-howell"})
    p = r["overlay"]["pairs"][0]["p"]
    assert p == pytest.approx(stats.ttest_ind(A, B, equal_var=False).pvalue, rel=1e-4)


def test_brown_forsythe_anova_two_groups_equals_welch_t_squared():
    from openprism.stats.advanced import brown_forsythe_anova
    F, d1, d2, p = brown_forsythe_anova([np.array(A), np.array(B)])
    t = stats.ttest_ind(A, B, equal_var=False)
    assert F == pytest.approx(t.statistic ** 2, rel=1e-6) and p == pytest.approx(t.pvalue, rel=1e-6)


def test_mixed_one_way_matches_statsmodels_and_allows_missing():
    import pandas as pd
    import statsmodels.formula.api as smf
    subj = rng.normal(0, 3, 12)
    cols = [list(subj + rng.normal(m, 1, 12)) for m in (10, 11, 13)]
    cols[2][3] = None  # missing value — RM ANOVA would drop the whole subject
    r = run("mixed_one_way", col_table(*cols), {"comparison": "tukey"})
    recs = [{"y": v, "t": j, "s": i} for j, c in enumerate(cols) for i, v in enumerate(c) if v is not None]
    df = pd.DataFrame(recs)
    ref = smf.mixedlm("y ~ C(t)", df, groups=df["s"]).fit(reml=True)
    chi = float(ref.wald_test_terms(scalar=True).table.loc["C(t)", "statistic"])
    assert float(sec(r, "Fixed effects")["rows"][0][1]) == pytest.approx(chi, rel=1e-2)
    assert kv(r, "Random effects")["Missing values (kept in model)"] == "1"
    assert r["overlay"]["kind"] == "pairs" and len(r["overlay"]["pairs"]) == 3


def test_nested_t_balanced_equals_t_on_subject_means():
    groups = []
    for mu in (10, 12):
        subjects = [rng.normal(mu + rng.normal(0, 1.5), 0.5, 4) for _ in range(5)]
        groups.append(subjects)
    cells = [[groups[g][s][r] for g in range(2) for s in range(5)] for r in range(4)]
    t = parse_table(make_table("n", "nested", [{"name": "Ctrl", "reps": 5}, {"name": "Drug", "reps": 5}], cells))
    res = run("nested", t, {})
    means = [[np.mean(s) for s in g] for g in groups]
    ref = stats.ttest_ind(means[1], means[0])
    assert res["overlay"]["pairs"][0]["p"] == pytest.approx(ref.pvalue, rel=2e-2)
    assert float(kv(res, "Variance components")["Intraclass correlation"]) > 0.3


def test_three_way_anova_matches_statsmodels():
    import pandas as pd
    import statsmodels.formula.api as smf
    from statsmodels.stats.anova import anova_lm
    n = 48
    f1, f2, f3 = rng.integers(0, 2, n), rng.integers(0, 2, n), rng.integers(0, 3, n)
    y = 5 + 2 * f1 + f2 * f3 + rng.normal(0, 1, n)
    t = parse_table(make_table("m", "multi", [{"name": nm, "reps": 1} for nm in ("Y", "Sex", "Drug", "Dose")],
                               np.column_stack([y, f1, f2, f3]).tolist()))
    r = run("factorial", t, {"dependent": 0, "factors": [1, 2, 3]})
    df = pd.DataFrame({"y": y, "a": f1.astype(str), "b": f2.astype(str), "c": f3.astype(str)})
    ref = anova_lm(smf.ols("y ~ C(a, Sum)*C(b, Sum)*C(c, Sum)", df).fit(), typ=3)
    rows = {row[0]: row for row in sec(r, "ANOVA table")["rows"]}
    assert float(rows["Sex"][1]) == pytest.approx(ref.loc["C(a, Sum)", "sum_sq"], rel=1e-3)
    assert "Sex × Drug × Dose" in rows


def test_ancova_covariate():
    n = 40
    g = rng.integers(0, 2, n)
    cov = rng.normal(50, 10, n)
    y = 3 * g + 0.5 * cov + rng.normal(0, 1, n)
    t = parse_table(make_table("m", "multi", [{"name": x, "reps": 1} for x in ("Y", "Group", "Age")], np.column_stack([y, g, cov]).tolist()))
    r = run("factorial", t, {"dependent": 0, "factors": [1], "covariates": [2]})
    slope = float(sec(r, "Covariate slopes")["rows"][0][1])
    assert slope == pytest.approx(0.5, abs=0.05)


def test_two_way_rm_runs_and_reports_terms():
    cells = []
    subj = rng.normal(0, 2, 4)
    for r_ in range(3):
        row = []
        for c in range(2):
            row += list(10 + r_ + 2 * c + subj + rng.normal(0, 0.5, 4))
        cells.append(row)
    t = parse_table(make_table("g", "grouped", [{"name": "A", "reps": 4}, {"name": "B", "reps": 4}], cells, row_labels=["t1", "t2", "t3"]))
    r = run("two_way_rm", t, {"rm": "both", "comparison": "sidak"})
    names = [row[0] for row in sec(r, "Fixed effects")["rows"]]
    assert {"Row factor", "Column factor", "Interaction"} <= set(names)
    assert r["overlay"]["kind"] == "grouped-pairs" and len(r["overlay"]["pairs"]) == 3


def test_deming_and_passing_bablok_on_exact_line():
    x = np.arange(1.0, 15)
    t = parse_table(make_table("x", "xy", [{"name": "y", "reps": 1}], [[2 * v + 1] for v in x], x=x))
    d = run("deming", t, {})
    assert float(sec(d, "Best-fit")["rows"][0][1]) == pytest.approx(2, rel=1e-6)
    t2 = parse_table(make_table("x", "xy", [{"name": "y", "reps": 1}], [[1.5 * v + 2] for v in x], x=x))
    pb = run("passing_bablok", t2, {})
    row = sec(pb, "Best-fit")["rows"][0]
    assert float(row[1]) == pytest.approx(1.5) and float(row[3]) == pytest.approx(2)


def test_poisson_matches_statsmodels():
    import statsmodels.api as sm
    x = rng.normal(0, 1, 80)
    y = rng.poisson(np.exp(0.5 + 0.8 * x))
    t = parse_table(make_table("p", "multi", [{"name": "Count", "reps": 1}, {"name": "X", "reps": 1}], np.column_stack([y, x]).tolist()))
    r = run("poisson", t, {"dependent": 0, "predictors": [1]})
    ref = sm.GLM(y, sm.add_constant(x), family=sm.families.Poisson()).fit()
    rr = float(sec(r, "Parameter estimates")["rows"][1][3])
    assert rr == pytest.approx(math.exp(ref.params[1]), rel=1e-3)


def test_tost_matches_statsmodels():
    from statsmodels.stats.weightstats import ttost_ind
    a, b = np.array(A), np.array(A) + 0.2 + rng.normal(0, 0.5, len(A))
    r = run("equivalence", col_table(list(a), list(b)), {"lower": -2, "upper": 2})
    p_ref = ttost_ind(b, a, -2, 2, usevar="unequal")[0]
    assert float(kv(r, "Two one-sided")["TOST P value"].replace("<", "")) == pytest.approx(p_ref, abs=1e-3) or p_ref < 1e-4


def test_bayes_factor_behaviour():
    from openprism.stats.advanced import _jzs_bf10
    assert _jzs_bf10(0.0, 50, 98) < 1 / 3          # evidence for the null with no effect
    assert _jzs_bf10(5.0, 50, 98) > 100            # strong evidence for an effect
    assert _jzs_bf10(2.0, 25, 98) < _jzs_bf10(3.0, 25, 98)


def test_permutation_exact_matches_scipy():
    a, b = [1.1, 2.3, 1.9, 2.8, 2.0], [3.2, 2.9, 4.1, 3.5, 3.3]
    r = run("permutation", col_table(a, b), {})
    ref = stats.permutation_test((b, a), lambda x, y: np.mean(x) - np.mean(y), permutation_type="independent",
                                 n_resamples=np.inf, alternative="two-sided").pvalue
    assert float(kv(r, "Permutation")["Two-tailed P value"]) == pytest.approx(ref, abs=1e-4)


def test_bootstrap_ci_contains_estimate():
    r = run("bootstrap", col_table(A, B), {"resamples": 2000})
    lo, hi = [float(v) for v in sec(r, "95% percentile")["rows"][0][4].split(" to ")]
    assert lo < np.mean(A) < hi


def test_rout_removes_outlier():
    x = np.linspace(0, 10, 15)
    y = 2 * x + 1 + rng.normal(0, 0.2, 15)
    y[7] += 15
    t = parse_table(make_table("x", "xy", [{"name": "y", "reps": 1}], [[v] for v in y], x=x))
    r = run("nonlinear", t, {"model": "line", "rout": True, "routQ": 1})
    out = sec(r, "Outliers removed by ROUT")["rows"]
    assert len(out) == 1 and float(out[0][1]) == pytest.approx(x[7])
    best = {row[0]: float(row[1]) for row in sec(r, "Best-fit values")["rows"]}
    assert best["Slope"] == pytest.approx(2, abs=0.1)


def test_new_models_fit():
    from openprism.stats.models import MODELS
    from openprism.stats.regression import fit_model
    assert len(MODELS) >= 45
    x = np.linspace(-9, -5, 12)
    y = MODELS["logagonist5"]["f"](x, 5, 100, -7, 1.2, 0.7)
    fit = fit_model("logagonist5", x, y)
    assert fit["r2"] > 0.999


def test_km_number_at_risk():
    x = [5, 8, 12, 3, 9, 15]
    cells = [[1, None], [0, None], [1, None], [None, 1], [None, 1], [None, 0]]
    t = parse_table(make_table("s", "survival", [{"name": "a", "reps": 1}, {"name": "b", "reps": 1}], cells, x=x))
    r = run("survival", t, {})
    ar = r["overlay"]["atRisk"]
    assert ar["counts"][0][0] == 3 and ar["counts"][1][0] == 3 and ar["times"][0] == 0


def test_all_equations_recover_their_parameters():
    import warnings
    from openprism.stats import models_extra
    from openprism.stats.models import MODELS
    from openprism.stats.regression import fit_model
    assert len(MODELS) >= 100
    failures = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for key, m in MODELS.items():
            x = models_extra.x_for_domain(m["domain"])
            y = m["f"](x, *m["example"])
            fit = fit_model(key, x, y, constraints=m.get("example_constraints"))
            if not fit["r2"] > 0.999:
                failures.append(key)
    assert failures == []


def test_profile_ci_linear_equals_exact_t_interval():
    """For a linear model the profile-likelihood CI equals the exact t interval."""
    x = np.linspace(0, 10, 12)
    y = 2 * x + 1 + rng.normal(0, 1, 12)
    t = parse_table(make_table("x", "xy", [{"name": "y", "reps": 1}], [[v] for v in y], x=x))
    r = run("nonlinear", t, {"model": "line", "profile": True})
    prof = {row[0]: row[1] for row in sec(r, "95% CI (profile")["rows"]}
    lo, hi = [float(v) for v in prof["Slope"].split(" to ")]
    lr = stats.linregress(x, y)
    tc = stats.t.ppf(0.975, 10)
    assert lo == pytest.approx(lr.slope - tc * lr.stderr, rel=1e-3)
    assert hi == pytest.approx(lr.slope + tc * lr.stderr, rel=1e-3)


def test_profile_ci_is_asymmetric_for_nonlinear():
    x = np.array([0.5, 1, 2, 4, 8, 16.0])
    y = 100 * x / (5 + x) + np.array([1, -2, 1.5, -1, 2, -1.5])
    t = parse_table(make_table("e", "xy", [{"name": "v", "reps": 1}], [[v] for v in y], x=x))
    r = run("nonlinear", t, {"model": "mm", "profile": True})
    best = {row[0]: float(row[1]) for row in sec(r, "Best-fit values")["rows"]}
    lo, hi = [float(v) for v in {row[0]: row[1] for row in sec(r, "95% CI (profile")["rows"]}["Km"].split(" to ")]
    assert lo < best["Km"] < hi and abs((hi - best["Km"]) - (best["Km"] - lo)) > 0.01


def test_tamhane_t2_and_dunnett_t3():
    r2 = run("one_way", col_table(A, B, C3), {"comparison": "t2"})
    r3 = run("one_way", col_table(A, B, C3), {"comparison": "t3"})
    p_raw = stats.ttest_ind(A, B, equal_var=False).pvalue
    p2 = r2["overlay"]["pairs"][0]["p"]
    p3 = r3["overlay"]["pairs"][0]["p"]
    assert p2 == pytest.approx(1 - (1 - p_raw) ** 3, rel=1e-4)
    assert p_raw < p3 <= p2 + 1e-9  # T3 is never more conservative than T2
