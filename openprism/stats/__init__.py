"""Registry of all analyses available in OpenPrism."""
from __future__ import annotations

import math

import numpy

from . import advanced, compare, competing, summary, contingency, descriptive, extra_column, extra_counts, extra_models, multivariate, regression, survival
from .common import AnalysisError, full_precision, quiet
from .models import model_list

ALL = ["xy", "column", "grouped", "contingency", "survival", "parts", "multi", "nested", "summary"]

# key: (function, label, category, table types it applies to)
ANALYSES = {
    "descriptive": (descriptive.descriptive, "Descriptive statistics", "Column analyses", [t for t in ALL if t != "summary"]),
    "normality": (descriptive.normality, "Normality and lognormality tests (with Q-Q plot)", "Column analyses", ["column", "xy", "grouped", "multi", "nested"]),
    "one_sample": (descriptive.one_sample, "One sample t and Wilcoxon test", "Column analyses", ["column"]),
    "ttest": (compare.ttest, "t tests (and nonparametric tests)", "Column analyses", ["column"]),
    "one_way": (compare.one_way, "One-way ANOVA (and nonparametric or mixed)", "Column analyses", ["column"]),
    "outliers": (descriptive.outliers, "Identify outliers", "Column analyses", ["column", "multi"]),
    "frequency": (descriptive.frequency, "Frequency distribution", "Column analyses", ["column"]),
    "roc": (regression.roc, "ROC curve", "Column analyses", ["column"]),
    "bland_altman": (multivariate.bland_altman, "Bland-Altman method comparison", "Column analyses", ["column"]),
    "mixed_one_way": (advanced.mixed_one_way, "Repeated measures by mixed-effects model (allows missing values)", "Column analyses", ["column"]),
    "equivalence": (advanced.equivalence, "Equivalence test (TOST)", "Column analyses", ["column"]),
    "bayes_t": (advanced.bayes_t, "Bayesian t test (Bayes factor)", "Column analyses", ["column"]),
    "bootstrap": (advanced.bootstrap, "Bootstrap confidence intervals", "Column analyses", ["column", "multi"]),
    "permutation": (advanced.permutation, "Permutation test (two groups)", "Column analyses", ["column"]),
    "variance_tests": (extra_column.variance_tests, "Compare variances (F, Levene, Brown-Forsythe, Bartlett, Fligner-Killeen)", "Column analyses", ["column"]),
    "distribution_tests": (extra_column.distribution_tests, "Compare distributions (KS, Cramér-von Mises, Anderson-Darling, Brunner-Munzel…)", "Column analyses", ["column"]),
    "robust_compare": (extra_column.robust_compare, "Robust comparison of trimmed means (Yuen, Wilcox)", "Column analyses", ["column"]),
    "trend_tests": (extra_column.trend_tests, "Test for trend across ordered groups (linear trend, Jonckheere-Terpstra)", "Column analyses", ["column"]),
    "np_posthoc": (extra_column.np_posthoc, "Nonparametric multiple comparisons (Dunn, Conover, DSCF)", "Column analyses", ["column"]),
    "rm_nonparametric": (extra_column.rm_nonparametric, "Nonparametric repeated measures (Friedman, Quade, Cochran's Q)", "Column analyses", ["column"]),
    "effect_sizes": (extra_column.effect_sizes, "Effect sizes with confidence intervals (d, g, Cliff's δ, η², ω²)", "Column analyses", ["column"]),
    "one_sample_more": (extra_column.one_sample_more, "Sign test, SD test, percentile CI, tolerance & prediction intervals", "Column analyses", ["column"]),
    "randomness": (extra_column.randomness, "Randomness & autocorrelation (runs, Ljung-Box, ADF, KPSS)", "Column analyses", ["column", "xy"]),
    "circular": (extra_column.circular, "Circular statistics (angles, times of day: Rayleigh, Watson-Williams)", "Column analyses", ["column"]),
    "reliability": (extra_column.reliability, "Reliability & agreement (ICC, Cronbach's α, Lin's CCC, Kendall's W)", "Column analyses", ["column", "multi"]),
    "p_adjust": (extra_column.p_adjust, "Adjust a list of P values (Holm, Hochberg, BH, BY, Storey q…)", "Column analyses", ["column"]),
    "summary_describe": (summary.summary_describe, "Summary data: means, SD, SEM and CIs", "Summary data", ["summary"]),
    "summary_ttest": (summary.summary_ttest, "Unpaired t test from summary data (mean, SD, n)", "Summary data", ["summary"]),
    "summary_anova": (summary.summary_anova, "One-way ANOVA from summary data (mean, SD, n)", "Summary data", ["summary"]),
    "nested": (advanced.nested, "Nested t test / nested one-way ANOVA", "Nested analyses", ["nested"]),
    "two_way": (compare.two_way, "Two-way ANOVA (or mixed model)", "Grouped analyses", ["grouped"]),
    "two_way_rm": (advanced.two_way_rm, "Two-way repeated measures (mixed-effects model)", "Grouped analyses", ["grouped"]),
    "two_way_np": (extra_models.two_way_np, "Nonparametric two-way ANOVA (aligned rank transform)", "Grouped analyses", ["grouped"]),
    "multiple_t": (compare.multiple_t, "Multiple t tests (one per row)", "Grouped analyses", ["grouped"]),
    "nonlinear": (regression.nonlinear, "Nonlinear regression (curve fit)", "XY analyses", ["xy"]),
    "linear": (regression.linear, "Simple linear regression", "XY analyses", ["xy"]),
    "correlation": (regression.correlation, "Correlation (and correlation matrix)", "XY analyses", ["xy", "column", "multi"]),
    "auc": (regression.auc, "Area under curve", "XY analyses", ["xy"]),
    "deming": (advanced.deming, "Deming regression (method comparison)", "XY analyses", ["xy"]),
    "passing_bablok": (advanced.passing_bablok, "Passing-Bablok regression (method comparison)", "XY analyses", ["xy"]),
    "polynomial": (extra_models.polynomial, "Polynomial regression (exact, orders 1-10)", "XY analyses", ["xy"]),
    "robust_regression": (extra_models.robust_regression, "Robust & quantile regression (Theil-Sen, Huber, bisquare, LAD)", "XY analyses", ["xy"]),
    "trend_mk": (extra_models.trend_mk, "Mann-Kendall trend test with Sen's slope", "XY analyses", ["xy", "column"]),
    "cosinor": (extra_models.cosinor, "Cosinor analysis (circadian / periodic rhythms)", "XY analyses", ["xy"]),
    "smooth": (multivariate.smooth, "Smooth, differentiate or integrate curve", "XY analyses", ["xy"]),
    "contingency": (contingency.contingency, "Chi-square (and Fisher's exact) test", "Contingency", ["contingency"]),
    "contingency_more": (extra_counts.contingency_more, "More contingency tests (exact, McNemar, G, trend, symmetry)", "Contingency", ["contingency"]),
    "risk": (extra_counts.risk, "Relative risk, odds ratio, risk difference, NNT (2 × 2)", "Contingency", ["contingency"]),
    "diagnostic": (extra_counts.diagnostic, "Diagnostic test accuracy (sensitivity, specificity, LR)", "Contingency", ["contingency"]),
    "kappa": (extra_counts.kappa, "Inter-rater agreement (Cohen's kappa, weighted)", "Contingency", ["contingency"]),
    "proportion": (extra_counts.proportion, "Proportions with confidence intervals & binomial test", "Contingency", ["contingency"]),
    "cmh": (extra_counts.cmh, "Stratified 2 × 2 tables (Cochran-Mantel-Haenszel)", "Contingency", ["contingency"]),
    "survival": (survival.survival, "Survival curve (Kaplan-Meier)", "Survival", ["survival"]),
    "competing_risks": (extra_counts.competing_risks, "Competing risks: cumulative incidence and Gray's test", "Survival", ["survival"]),
    "fine_gray": (competing.fine_gray_analysis, "Fine-Gray competing-risks regression", "Multiple variables", ["multi"]),
    "survival_more": (extra_counts.survival_more, "Weighted log-rank tests, RMST, survival quantiles", "Survival", ["survival"]),
    "parts": (contingency.parts_of_whole, "Fraction of total", "Parts of whole", ["parts"]),
    "multiple_regression": (multivariate.multiple_regression, "Multiple linear regression", "Multiple variables", ["multi"]),
    "logistic": (multivariate.logistic, "Multiple logistic regression", "Multiple variables", ["multi"]),
    "cox": (multivariate.cox, "Cox proportional hazards regression", "Multiple variables", ["multi"]),
    "pca": (multivariate.pca, "Principal component analysis (PCA)", "Multiple variables", ["multi"]),
    "factorial": (advanced.factorial, "Three-way / n-way ANOVA and ANCOVA", "Multiple variables", ["multi"]),
    "poisson": (advanced.poisson, "Poisson regression (counts)", "Multiple variables", ["multi"]),
    "mixed_model": (extra_models.mixed_model, "Linear mixed-effects model (random intercepts and slopes)", "Multiple variables", ["multi"]),
    "glm": (extra_models.glm, "Generalized linear model (binomial, Poisson, negative binomial, gamma…)", "Multiple variables", ["multi"]),
    "ordinal": (extra_models.ordinal, "Ordinal logistic regression (proportional odds)", "Multiple variables", ["multi"]),
    "regression_diagnostics": (extra_models.regression_diagnostics, "Regression diagnostics (heteroscedasticity, influence, VIF)", "Multiple variables", ["multi"]),
    "manova": (extra_models.manova, "MANOVA / Hotelling's T²", "Multiple variables", ["multi"]),
    "partial_correlation": (extra_models.partial_correlation, "Partial correlation", "Multiple variables", ["multi"]),
    "cluster": (extra_models.cluster, "Cluster analysis (hierarchical, k-means)", "Multiple variables", ["multi"]),
    "meta": (extra_models.meta, "Meta-analysis (fixed & random effects, forest & funnel plots)", "Multiple variables", ["multi"]),
    "transform": (contingency.transform, "Transform", "Data processing", ["xy", "column", "grouped", "multi"]),
    "normalize": (contingency.normalize, "Normalize", "Data processing", ["xy", "column", "grouped", "multi"]),
    "baseline": (contingency.remove_baseline, "Remove baseline", "Data processing", ["xy", "column", "grouped", "multi"]),
    "transpose": (contingency.transpose, "Transpose X and Y", "Data processing", ["xy", "column", "grouped", "multi"]),
}


def catalog():
    from ..guide import CHOOSER, G
    from ..plain import plain
    return {
        "analyses": [{"key": k, "label": v[1], "category": v[2], "tableTypes": v[3], "guide": G.get(k), "plain": plain(k)} for k, v in ANALYSES.items()],
        "models": model_list(),
        "chooser": CHOOSER,
    }


_PRELOADED = False


def preload():
    """Import every lazily imported module and run each analysis family once on tiny data.

    Called once in the server process before it serves requests. Calculations
    run in forked children, which inherit everything already imported — without
    this, each request paid ~0.1–0.6 s to import statsmodels sub-packages again.
    """
    global _PRELOADED
    if _PRELOADED:
        return
    _PRELOADED = True
    import importlib
    import warnings
    for mod in ("pandas", "patsy", "scipy.stats", "scipy.optimize", "scipy.special", "scipy.cluster.hierarchy", "scipy.spatial.distance",
                "statsmodels.api", "statsmodels.formula.api", "statsmodels.stats.anova", "statsmodels.stats.diagnostic", "statsmodels.stats.multitest",
                "statsmodels.stats.power", "statsmodels.stats.proportion", "statsmodels.stats.contingency_tables", "statsmodels.stats.inter_rater",
                "statsmodels.stats.outliers_influence", "statsmodels.stats.stattools", "statsmodels.duration.hazard_regression",
                "statsmodels.miscmodels.ordinal_model", "statsmodels.multivariate.manova", "statsmodels.nonparametric.smoothers_lowess",
                "statsmodels.tsa.stattools", "statsmodels.regression.mixed_linear_model", "svgelements"):
        try:
            importlib.import_module(mod)
        except Exception:  # noqa: BLE001  (optional modules)
            pass
    from ..tables import make_table, parse_table
    col = parse_table(make_table("w", "column", [{"name": "a", "reps": 1}, {"name": "b", "reps": 1}, {"name": "c", "reps": 1}],
                                 [[1, 2, 3], [2, 3, 5], [3, 5, 4], [4, 4, 7], [5, 7, 6], [6, 6, 9]]))
    multi = parse_table(make_table("w", "multi", [{"name": n, "reps": 1} for n in "ygx"],
                                   [[i % 3 + 1, i % 4, i * 0.7 + (i % 3)] for i in range(24)]))
    xy = parse_table(make_table("w", "xy", [{"name": "y", "reps": 1}], [[v] for v in (1, 3, 4, 6, 7, 9, 12, 13)], x=list(range(1, 9))))
    grouped = parse_table(make_table("w", "grouped", [{"name": "a", "reps": 2}, {"name": "b", "reps": 2}], [[1, 2, 3, 4], [2, 3, 5, 6], [3, 3, 4, 7]], row_labels=["r1", "r2", "r3"]))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for key, table, params in [("ttest", col, {}), ("one_way", col, {}), ("two_way", grouped, {}), ("glm", multi, {"dependent": 2, "family": "poisson"}),
                                   ("multiple_regression", multi, {"dependent": 2}), ("mixed_model", multi, {"dependent": 2, "group": 1, "fixed": [0]}),
                                   ("nonlinear", xy, {"model": "custom", "equation": "Y = a*X^b"}), ("linear", xy, {}), ("normality", col, {}),
                                   ("correlation", xy, {}), ("factorial", multi, {"dependent": 2, "factors": [0]}), ("logistic", multi, {"dependent": 1}),
                                   ("mixed_one_way", col, {}), ("cox", multi, {})]:
            try:
                run(key, table, params)
            except Exception:  # noqa: BLE001  (warm-up only)
                pass


def provenance(key, table, params):
    """What is needed to reproduce a result exactly: software versions and a data fingerprint."""
    import hashlib
    import json
    import platform

    import numpy
    import scipy
    import statsmodels

    from .. import __version__
    h = hashlib.sha256()
    h.update(json.dumps([table.type, table.names, table.row_labels], ensure_ascii=False).encode())
    h.update(numpy.ascontiguousarray(table.x, dtype=float).tobytes())
    for y in table.Y:
        h.update(numpy.ascontiguousarray(y, dtype=float).tobytes())
    return {"software": f"OpenPrism {__version__}", "numpy": numpy.__version__, "scipy": scipy.__version__,
            "statsmodels": statsmodels.__version__, "python": platform.python_version(), "analysis": key,
            "dataSha256": h.hexdigest(), "params": json.loads(json.dumps(params, default=str)),
            "deterministic": True}


def finite_json(o):
    """Replace NaN / ±inf (not valid JSON, browsers reject the whole response) by None, recursively."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: finite_json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [finite_json(v) for v in o]
    if isinstance(o, numpy.generic):
        return finite_json(o.item())
    return o


def _degenerate_message(table, e):
    vals = numpy.concatenate([y.ravel() for y in table.Y]) if table.Y else numpy.array([])
    vals = vals[numpy.isfinite(vals)]
    if vals.size == 0:
        why = "there are no numeric values to analyze"
    elif numpy.ptp(vals) == 0:
        why = "all values are identical, so there is no variability to analyze"
    elif table.nrows < 3 or vals.size < 4:
        why = "there are too few values"
    elif isinstance(e, numpy.linalg.LinAlgError) or "singular" in str(e).lower():
        why = "a variable is constant or a combination of other variables (the model cannot be estimated)"
    else:
        why = "the data do not allow this calculation (for example a group without variability or too few values per group)"
    return f"This analysis cannot be computed for these data: {why}."


_ONE_COLUMN = ("control", "dependent", "eventVar", "group", "randomSlope", "timeVar", "offset")
_MANY_COLUMNS = ("covariates", "dependents", "factors", "fixed", "predictors", "datasets")


def _check_columns(table, params):
    """Column choices must point at existing data sets (a negative index would silently pick the last one)."""
    n = len(getattr(table, "Y", []) or [])

    def ok(v):
        try:
            i = int(v)
        except (TypeError, ValueError):
            return False
        return i == v and 0 <= i < n

    for k in _ONE_COLUMN:
        if k in params and not ok(params[k]):
            raise AnalysisError(f"The chosen column for “{k}” does not exist in this table; open ⚙ Parameters and choose it again.")
    for k in _MANY_COLUMNS:
        if k in params:
            v = params[k]
            if not isinstance(v, (list, tuple)) or not all(ok(x) for x in v):
                raise AnalysisError(f"A chosen column for “{k}” does not exist in this table; open ⚙ Parameters and choose again.")


def run(key, table, params):
    if key not in ANALYSES:
        raise AnalysisError(f"Unknown analysis '{key}'")
    fn = ANALYSES[key][0]
    # a blank optional field in a dialog means "not set / automatic"
    params = {k: v for k, v in dict(params or {}).items() if v is not None and not (isinstance(v, str) and v.strip() == "")}
    full = params.pop("_digits", None) == "full"
    _check_columns(table, params)
    with quiet(), full_precision(full):
        try:
            out = fn(table, params).to_dict()
        except AnalysisError:
            raise
        except (TypeError, KeyError, AttributeError) as e:
            raise AnalysisError("An option of this analysis has an invalid value; open ⚙ Parameters and check the choices.") from e
        except (ZeroDivisionError, FloatingPointError, ArithmeticError, ValueError, IndexError, numpy.linalg.LinAlgError) as e:
            # degenerate data (all values identical, too few rows, a variable that is a combination of others…)
            raise AnalysisError(_degenerate_message(table, e)) from e
    out = finite_json(out)
    bad = getattr(table, "invalid", [])
    if bad:
        ex = ", ".join(f"“{t}”" for _, _, t in bad[:4])
        out.setdefault("warnings", []).insert(0, f"{len(bad)}{'+' if len(bad) >= 1000 else ''} cell(s) are not valid numbers and were ignored ({ex}{'…' if len(bad) > 4 else ''}). "
                                                 "Use a decimal point and no thousands separators, e.g. 1234.5 or 1.2e-3.")
    out["provenance"] = provenance(key, table, params)
    out["fullPrecision"] = full
    return out


__all__ = ["ANALYSES", "catalog", "run", "AnalysisError"]
