"""Reproducibility and metamorphic (invariance) tests.

* Determinism: every analysis gives bit-identical output when repeated, and in
  a fresh Python process (compared by SHA-256 of the full-precision output).
  Resampling methods (bootstrap, permutation, Monte-Carlo exact tests,
  k-means) use fixed seeds, so they are reproducible too.
* Invariance: results that mathematically must not change when the data are
  shifted, rescaled, reordered or relabelled are checked to ≥ 9 digits.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from common import analyze, column_table, ct_table, kv, lre, multi_table, number, section, xy_table
from openprism.tables import make_table

HERE = Path(__file__).parent


def battery():
    """(name, analysis key, table, params) covering every family of analyses."""
    rng = np.random.default_rng(99)
    g = [list(np.round(rng.normal(m, 2, 12), 4)) for m in (10, 11, 13, 12)]
    M = np.round(rng.normal(size=(30, 4)), 4)
    M[:, 0] += M[:, 1]
    x = list(np.arange(1, 13, dtype=float))
    y = [round(2 * v + float(e), 4) for v, e in zip(x, rng.normal(0, 1, 12))]
    surv = make_table("s", "survival", [{"name": "A", "reps": 1}, {"name": "B", "reps": 1}],
                      [[1, None], [1, None], [0, None], [1, None], [None, 1], [None, 0], [None, 1], [None, 1], [1, None], [None, 1]], x=[5, 8, 9, 12, 3, 4, 6, 7, 20, 2])
    return [
        ("descriptive", "descriptive", column_table(g), {}),
        ("t test", "ttest", column_table(g[:2]), {}),
        ("Mann-Whitney exact", "ttest", column_table(g[:2]), {"parametric": False}),
        ("one-way ANOVA + Tukey", "one_way", column_table(g), {"comparison": "tukey"}),
        ("Dunnett", "one_way", column_table(g), {"comparison": "dunnett"}),
        ("Kruskal-Wallis", "one_way", column_table(g), {"parametric": False}),
        ("distributions (permutation AD)", "distribution_tests", column_table(g[:3]), {}),
        ("trend (permutation JT)", "trend_tests", column_table(g), {}),
        ("effect sizes (bootstrap)", "effect_sizes", column_table(g[:2]), {}),
        ("bootstrap CI", "bootstrap", column_table(g[:1]), {"resamples": 2000}),
        ("permutation test", "permutation", column_table(g[:2]), {}),
        ("Fisher-Freeman-Halton Monte Carlo", "contingency_more", ct_table([[3, 1, 4], [1, 5, 2], [6, 2, 1]]), {}),
        ("linear regression", "linear", xy_table(x, [y]), {}),
        ("nonlinear regression", "nonlinear", xy_table(x, [y]), {"model": "custom", "equation": "Y = a*X^b", "initial": "a=1, b=1"}),
        ("polynomial (exact)", "polynomial", xy_table(x, [y]), {"order": 3}),
        ("k-means", "cluster", multi_table([list(M[:, j]) for j in range(4)], ["a", "b", "c", "d"]), {"method": "kmeans", "k": 3}),
        ("survival", "survival", surv, {}),
        ("survival extras", "survival_more", surv, {}),
        ("meta-analysis", "meta", make_table("m", "multi", [{"name": "es", "reps": 1}, {"name": "se", "reps": 1}],
                                              [[0.3, 0.1], [0.5, 0.15], [0.1, 0.2], [0.7, 0.25]], row_labels=list("ABCD")), {}),
    ]


def digest(results):
    return hashlib.sha256(json.dumps(results, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def run_battery():
    return [analyze(key, table, params) for _, key, table, params in battery()]


def _strip(res):
    out = dict(res)
    out.pop("provenance", None)
    return out


def run_all():
    out = []
    first = [_strip(r) for r in run_battery()]
    second = [_strip(r) for r in run_battery()]
    for (name, *_), a, b in zip(battery(), first, second):
        same = json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
        out.append({"area": "Reproducibility", "case": name, "quantity": "bit-identical output when repeated (same process)", "reference": 1.0,
                    "value": 1.0 if same else 0.0, "lre": None, "required": "identical", "pass": same, "source": "repeat", "note": ""})
    code = ("import sys, json; sys.path[:0] = [%r, %r]; import reproducibility as r; "
            "print(r.digest([r._strip(x) for x in r.run_battery()]))") % (str(HERE.parent), str(HERE))
    proc = subprocess.run([sys.executable, "-W", "ignore", "-c", code], capture_output=True, text=True, timeout=600)
    other = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "(failed: " + proc.stderr[-300:] + ")"
    mine = digest(first)
    out.append({"area": "Reproducibility", "case": f"all {len(first)} analyses above", "quantity": "SHA-256 of full-precision output in a fresh process",
                "reference": 1.0, "value": 1.0 if other == mine else 0.0, "lre": None, "required": "identical", "pass": other == mine,
                "source": "subprocess", "note": f"digest {mine[:16]}…"})
    out += invariance()
    return out


def _inv(out, case, a, b, need=9, note=""):
    L = lre(a, b)
    out.append({"area": "Invariance (metamorphic tests)", "case": case, "quantity": "agreement of the invariant quantity", "reference": float(b),
                "value": float(a), "lre": round(L, 2), "required": need, "pass": L >= need, "source": "metamorphic relation", "note": note})


def invariance():
    rng = np.random.default_rng(7)
    out = []
    a, b = rng.normal(5, 1, 15), rng.normal(5.8, 1.3, 13)
    base = analyze("ttest", column_table([a, b]), {})
    p0 = kv(base, "Unpaired t test", "P value")
    from decimal import Decimal
    shift = lambda vals, c: [str(Decimal(repr(float(v))) + Decimal(c)) for v in vals]  # noqa: E731  exact decimal shift
    sh = analyze("ttest", column_table([shift(a, 10 ** 12), shift(b, 10 ** 12)]), {})
    _inv(out, "t test P after adding 10¹² to every value", kv(sh, "Unpaired t test", "P value"), p0, 9,
         "values are entered as exact decimal text; exact decimal centering keeps full precision")
    sc = analyze("ttest", column_table([a * 1000, b * 1000]), {})
    _inv(out, "t test P after multiplying by 1000", kv(sc, "Unpaired t test", "P value"), p0)
    sw = analyze("ttest", column_table([b, a]), {})
    _inv(out, "t test P after swapping the groups", kv(sw, "Unpaired t test", "P value"), p0)
    pa = analyze("ttest", column_table([rng.permutation(a), rng.permutation(b)]), {})
    _inv(out, "t test P after shuffling values within groups", kv(pa, "Unpaired t test", "P value"), p0)
    gs = [rng.normal(m, 1, 10) for m in (1, 1.5, 2, 1.2)]
    F0 = kv(analyze("one_way", column_table(gs), {"comparison": "none"}), "ANOVA summary", "F")
    F1 = kv(analyze("one_way", column_table([shift(g, 10 ** 12) for g in gs]), {"comparison": "none"}), "ANOVA summary", "F")
    _inv(out, "ANOVA F after adding 10¹² (exact decimal centering)", F1, F0, 9)
    F2 = kv(analyze("one_way", column_table(gs[::-1]), {"comparison": "none"}), "ANOVA summary", "F")
    _inv(out, "ANOVA F after reversing group order", F2, F0)
    k0 = _first(analyze("one_way", column_table(gs), {"parametric": False}), "P value")
    k1 = _first(analyze("one_way", column_table([np.exp(g) for g in gs]), {"parametric": False}), "P value")
    _inv(out, "Kruskal-Wallis P after a monotone transform (exp)", k1, k0, 12, "rank tests depend only on the ordering")
    x = rng.normal(size=20)
    y = 0.5 * x + rng.normal(size=20)
    r0 = number(section(analyze("correlation", multi_table([x, y], ["x", "y"]), {}), "Correlation")["rows"][0][1])
    r1 = number(section(analyze("correlation", multi_table([y, x], ["y", "x"]), {}), "Correlation")["rows"][0][1])
    _inv(out, "Pearson r(x, y) = r(y, x)", r1, r0)
    r2 = number(section(analyze("correlation", multi_table([x * 3 + 7, y * -2], ["x", "y"]), {}), "Correlation")["rows"][0][1])
    _inv(out, "|r| after linear rescaling of both variables", abs(r2), abs(r0))
    xs = np.arange(1.0, 11.0)
    ys = 3 * xs + rng.normal(0, 1, 10)
    s0 = kv(analyze("linear", xy_table(xs, [ys]), {}), "Best-fit", "Slope")
    s1 = kv(analyze("linear", xy_table(xs, [ys * 10]), {}), "Best-fit", "Slope")
    _inv(out, "regression slope scales with Y (×10)", s1 / 10, s0)
    c0 = kv(analyze("contingency", ct_table([[12, 5], [3, 15]]), {}), "Tests", "Fisher's exact")
    c1 = kv(analyze("contingency", ct_table([[3, 15], [12, 5]]), {}), "Tests", "Fisher's exact")
    _inv(out, "Fisher exact P after swapping rows", c1, c0)
    return out


def _first(r, row):
    for s in r["sections"]:
        for x in s["rows"]:
            if str(x[0]).startswith(row):
                return number(x[1])
    raise KeyError(row)
