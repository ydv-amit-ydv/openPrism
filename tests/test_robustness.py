"""Every analysis on degenerate data: clear messages, never crashes, always strict (browser-parsable) JSON."""
import copy
import json

import pytest

from sample_tables import TABLES
from openprism.stats import ANALYSES, AnalysisError, run
from openprism.tables import parse_table


def _variants(t):
    cells = t["cells"]
    v = copy.deepcopy(t); v["cells"] = [[None] * len(r) for r in cells]; yield "empty", v
    v = copy.deepcopy(t); v["cells"] = [[(5 if c not in (None, "") else c) for c in r] for r in cells]; yield "constant", v
    v = copy.deepcopy(t); v["cells"] = cells[:1]; v["rowLabels"] = (t.get("rowLabels") or [""] * len(cells))[:1]
    if t.get("x") is not None:
        v["x"] = t["x"][:1]
    yield "one row", v
    v = copy.deepcopy(t); v["cells"] = [[(c if (i + j) % 3 else None) for j, c in enumerate(r)] for i, r in enumerate(cells)]; yield "holes", v


@pytest.mark.parametrize("key", sorted(ANALYSES))
def test_degenerate_data_never_crash(key):
    types = ANALYSES[key][3]
    for name, table in TABLES.items():
        if table["type"] not in types:
            continue
        for vname, tv in _variants(table):
            try:
                out = run(key, parse_table(tv), {})
            except AnalysisError as e:
                assert str(e) and "Traceback" not in str(e)
                continue
            json.dumps(out, allow_nan=False)          # NaN / Infinity would make the browser reject the response


def test_not_a_number_is_sent_as_null():
    t = copy.deepcopy(TABLES["column"])
    t["cells"] = [[(5 if c is not None else c) for c in r] for r in t["cells"]]
    out = run("ttest", parse_table(t), {"datasets": [0, 1]})
    s = json.dumps(out, allow_nan=False)
    assert '"p": null' in s


def test_blank_optional_fields_mean_automatic():
    out = run("frequency", parse_table(TABLES["column"]), {"binWidth": "", "binStart": "", "mode": "count", "cumulative": False})
    assert out["sections"]


def test_degenerate_message_is_specific():
    t = copy.deepcopy(TABLES["column"])
    t["cells"] = [[(5 if c is not None else c) for c in r] for r in t["cells"]]
    with pytest.raises(AnalysisError, match="identical"):
        run("robust_compare", parse_table(t), {})


def test_polynomial_order_too_high_explained():
    with pytest.raises(AnalysisError, match="different X values"):
        run("polynomial", parse_table(TABLES["enzyme"]), {"order": 9})


def test_api_responses_are_strict_json(tmp_path):
    from helpers import H, make_apps, register
    app, _, _ = make_apps(tmp_path)
    u = register(app, "zed")
    t = copy.deepcopy(TABLES["column"])
    t["cells"] = [[(5 if c is not None else c) for c in r] for r in t["cells"]]
    r = u.post("/api/analyze", json={"analysis": "one_way", "table": t, "params": {}}, headers=H)
    assert r.status_code == 200
    json.loads(r.data, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))


def test_column_choices_must_exist():
    with pytest.raises(AnalysisError, match="does not exist"):
        run("multiple_regression", parse_table(TABLES["multi"]), {"dependent": -1})
    with pytest.raises(AnalysisError, match="does not exist"):
        run("cox", parse_table(TABLES["multi"]), {"timeVar": 99, "eventVar": 1})


@pytest.mark.parametrize("key,params", [("bootstrap", {"statistic": "nonsense"}), ("meta", {"method": 7}),
                                        ("smooth", {"operation": True}), ("normalize", {"zero": "abc"})])
def test_unknown_option_values_give_a_message(key, params):
    types = ANALYSES[key][3]
    t = next(t for t in TABLES.values() if t["type"] in types)
    with pytest.raises(AnalysisError, match="invalid value"):
        run(key, parse_table(t), params)


def test_absurd_iteration_counts_are_capped():
    import time
    t0 = time.time()
    run("randomness", parse_table(TABLES["column"]), {"lags": 10 ** 9})
    run("trend_tests", parse_table(TABLES["column"]), {"permutations": 10 ** 9})
    assert time.time() - t0 < 30
