"""Synthetic, reproducible tables used only by the test-suite (not shipped in the app)."""
from __future__ import annotations

import numpy as np

from openprism.tables import make_table

_rng = np.random.default_rng(42)


def _round(a, d=2):
    return [[None if v is None else round(float(v), d) for v in row] for row in a]


def _dose_response():
    x = np.array([-9, -8.5, -8, -7.5, -7, -6.5, -6, -5.5, -5])
    def f(x, b, t, ec, h):
        return b + (t - b) / (1 + 10 ** ((ec - x) * h))
    ctrl = f(x, 5, 100, -7.2, 1.1)
    drug = f(x, 4, 95, -6.4, 1.0)
    cells = []
    for i in range(len(x)):
        cells.append(list(ctrl[i] + _rng.normal(0, 4, 3)) + list(drug[i] + _rng.normal(0, 4, 3)))
    return make_table("Dose response", "xy", [{"name": "Control", "reps": 3}, {"name": "+ Antagonist", "reps": 3}],
                      _round(cells), x=x, x_title="log[Agonist], M")


def _column():
    g = [_rng.normal(m, s, n) for m, s, n in [(20, 3, 10), (24, 3.5, 10), (31, 4, 9), (22, 3, 10)]]
    n = max(len(v) for v in g)
    cells = [[(v[i] if i < len(v) else None) for v in g] for i in range(n)]
    return make_table("Treatment groups", "column",
                      [{"name": nm, "reps": 1} for nm in ["Vehicle", "Drug A", "Drug B", "Drug C"]], _round(cells))


def _paired():
    before = _rng.normal(140, 12, 10)
    after = before - _rng.normal(8, 6, 10)
    return make_table("Blood pressure (paired)", "column", [{"name": "Before", "reps": 1}, {"name": "After", "reps": 1}],
                      _round(np.column_stack([before, after]).tolist(), 1))


def _grouped():
    rows = ["Week 1", "Week 2", "Week 4", "Week 8"]
    eff = {"Wild type": [10, 14, 18, 22], "Knockout": [10, 11, 12, 13], "Rescue": [10, 13, 16, 20]}
    cells = []
    for r in range(4):
        row = []
        for k, v in eff.items():
            row += list(v[r] + _rng.normal(0, 1.5, 3))
        cells.append(row)
    return make_table("Body weight gain", "grouped", [{"name": k, "reps": 3} for k in eff], _round(cells),
                      row_labels=rows)


def _linear():
    x = np.arange(0, 11)
    a = 2.1 * x + 3 + _rng.normal(0, 1.3, len(x))
    b = 1.2 * x + 4 + _rng.normal(0, 1.3, len(x))
    return make_table("Standard curve", "xy", [{"name": "Assay 1", "reps": 1}, {"name": "Assay 2", "reps": 1}],
                      _round(np.column_stack([a, b]).tolist()), x=x, x_title="Concentration (µg/mL)")


def _decay():
    x = np.linspace(0, 60, 13)
    y = (100 - 8) * np.exp(-0.08 * x) + 8
    cells = [list(v + _rng.normal(0, 2.5, 2)) for v in y]
    return make_table("Radioactive decay", "xy", [{"name": "Counts", "reps": 2}], _round(cells), x=x,
                      x_title="Time (min)")


def _survival():
    rows_x, cells = [], []
    groups = [("Standard", 14, 0.06), ("New therapy", 14, 0.03)]
    for gi, (_, n, lam) in enumerate(groups):
        t = _rng.exponential(1 / lam, n)
        c = _rng.uniform(5, 60, n)
        for ti, ci in zip(t, c):
            tt = min(ti, ci, 60)
            ev = 1 if ti <= min(ci, 60) else 0
            rows_x.append(round(float(tt), 1))
            row = [None] * len(groups)
            row[gi] = ev
            cells.append(row)
    return make_table("Survival study", "survival", [{"name": g[0], "reps": 1} for g in groups], cells, x=rows_x,
                      x_title="Months")


def _contingency():
    return make_table("Exposure vs. disease", "contingency",
                      [{"name": "Disease", "reps": 1}, {"name": "No disease", "reps": 1}],
                      [[42, 58], [18, 82]], row_labels=["Exposed", "Not exposed"])


def _parts():
    return make_table("Cell populations", "parts", [{"name": "Count", "reps": 1}],
                      [[412], [233], [120], [85], [40]],
                      row_labels=["T cells", "B cells", "NK cells", "Monocytes", "Other"])


def _mm():
    x = np.array([0.5, 1, 2, 4, 8, 16, 32, 64])
    y = 120 * x / (6 + x)
    return make_table("Enzyme kinetics", "xy", [{"name": "Velocity", "reps": 3}],
                      _round([list(v + _rng.normal(0, 3, 3)) for v in y]), x=x, x_title="[Substrate] (µM)")


EXAMPLES = {
    "column": {"name": "Four treatment groups", "type": "column", "description": "One-way ANOVA, t tests, dot plots",
               "table": _column()},
    "paired": {"name": "Paired before/after", "type": "column", "description": "Paired t test, before-after plot",
               "table": _paired()},
    "doseresponse": {"name": "Dose-response curves", "type": "xy", "description": "Nonlinear regression, EC50",
                     "table": _dose_response()},
    "linear": {"name": "Standard curve", "type": "xy", "description": "Linear regression, interpolation",
               "table": _linear()},
    "decay": {"name": "Exponential decay", "type": "xy", "description": "One-phase decay, half-life",
              "table": _decay()},
    "enzyme": {"name": "Michaelis-Menten kinetics", "type": "xy", "description": "Vmax and Km",
               "table": _mm()},
    "grouped": {"name": "Grouped (two-way)", "type": "grouped", "description": "Two-way ANOVA, grouped bars",
                "table": _grouped()},
    "survival": {"name": "Kaplan-Meier survival", "type": "survival", "description": "Log-rank test",
                 "table": _survival()},
    "contingency": {"name": "2×2 contingency", "type": "contingency", "description": "Fisher's exact, odds ratio",
                    "table": _contingency()},
    "parts": {"name": "Parts of whole", "type": "parts", "description": "Pie / donut charts",
              "table": _parts()},
}


def _multi():
    rng = np.random.default_rng(7)
    n = 80
    age = rng.normal(55, 10, n)
    bmi = rng.normal(27, 4, n)
    chol = rng.normal(200, 30, n)
    sbp = 90 + 0.6 * age + 1.1 * bmi + rng.normal(0, 8, n)
    logit = -12 + 0.12 * age + 0.15 * bmi
    outcome = (rng.uniform(size=n) < 1 / (1 + np.exp(-logit))).astype(int)
    hazard = np.exp(0.04 * (age - 55) + 0.08 * (bmi - 27))
    time = rng.exponential(30 / hazard)
    event = (time < 40).astype(int)
    time = np.minimum(time, 40)
    cols = [age, bmi, chol, sbp, outcome, time, event]
    names = ["Age", "BMI", "Cholesterol", "SBP", "Outcome", "Time", "Event"]
    return make_table("Patients", "multi", [{"name": nm, "reps": 1} for nm in names],
                      _round(np.column_stack(cols).tolist(), 3))


def _methods():
    rng = np.random.default_rng(11)
    truth = rng.uniform(50, 150, 30)
    a = truth + rng.normal(0, 4, 30)
    b = truth * 1.02 + 1.5 + rng.normal(0, 4, 30)
    return make_table("Method comparison", "column", [{"name": "Method A", "reps": 1}, {"name": "Method B", "reps": 1}],
                      _round(np.column_stack([a, b]).tolist(), 1))


def _nested():
    rng = np.random.default_rng(3)
    cells = []
    subj = [rng.normal(m, 1.5, 4) for m in (10, 10, 10, 13, 13, 13)]
    for r in range(5):
        cells.append([float(subj[k][0] + subj[k][1] * 0 + rng.normal(0, 0.5)) + subj[k][r % 4] * 0 for k in range(6)])
    return make_table("Nested", "nested", [{"name": "Control", "reps": 3}, {"name": "Treated", "reps": 3}], _round(cells))


EXAMPLES["nested"] = {"name": "Nested", "type": "nested", "description": "", "table": _nested()}
EXAMPLES["multi"] = {"name": "Patients", "type": "multi", "description": "", "table": _multi()}
EXAMPLES["methods"] = {"name": "Methods", "type": "column", "description": "", "table": _methods()}
TABLES = {k: v["table"] for k, v in EXAMPLES.items()}

# summary data (mean, SD, n per group)
TABLES["summary"] = make_table("Summary from a paper", "summary", [{"name": "Mean", "reps": 1}, {"name": "SD", "reps": 1}, {"name": "N", "reps": 1}],
                               [[10.2, 2.1, 8], [12.9, 2.6, 9], [15.1, 3.0, 8]], row_labels=["Control", "Drug A", "Drug B"])
