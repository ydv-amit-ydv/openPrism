"""Smart import: the layout of a spreadsheet is recognised and turned into the right table."""
import io
import json

import pytest

from openprism.detect import build, inspect, read_frame

FILES = {
    "wide_groups.csv": ("Control,Drug A,Drug B\n12.1,15.3,18.2\n11.8,14.9,19.1\n12.5,16.0,17.7\n", "column", "wide"),
    "long_groups.csv": ("Treatment,Weight\nControl,20.1\nControl,21.3\nDrug,25.2\nDrug,24.8\nPlacebo,19.9\nPlacebo,20.4\n", "column", "long"),
    "xy.csv": ("Dose,Response 1,Response 2\n0.1,5,6\n1,20,22\n10,60,58\n100,95,97\n", "xy", "wide"),
    "surv.csv": ("Patient,Days,Status,Arm\n1,120,1,A\n2,300,0,A\n3,45,1,B\n4,500,0,B\n5,80,1,B\n6,210,1,A\n", "survival", "long"),
    "summary.csv": ("Group,Mean,SD,N\nControl,10.2,2.1,12\nDrug,13.5,2.4,11\n", "summary", "summary"),
    "ct_long.csv": ("Smoker,Cancer\nyes,yes\nyes,no\nno,no\nno,no\nyes,yes\nno,yes\n", "contingency", "long"),
    "ct_wide.csv": (",Disease,Healthy\nExposed,30,70\nUnexposed,10,90\n", "contingency", "wide"),
    "two_factor.csv": ("Sex,Strain,Weight\nM,WT,25\nM,KO,22\nF,WT,20\nF,KO,18\nM,WT,26\nF,KO,17\n", "grouped", "long"),
    "multi.csv": ("Age,BMI,Smoker,Cholesterol\n45,24.5,1,210\n52,28.1,0,240\n38,22.0,0,190\n61,30.2,1,260\n", "multi", "wide"),
    "semicolon.csv": ("Dose;Effect\n1;5\n2;9\n4;17\n", "xy", "wide"),
    "tabs.tsv": ("A\tB\n1\t2\n3\t4\n5\t6\n", "column", "wide"),
}


@pytest.mark.parametrize("fname", sorted(FILES))
def test_recognised_layout(fname):
    text, ttype, layout = FILES[fname]
    r = inspect(text.encode(), fname)
    best = r["options"][0]
    assert (best["type"], best["layout"]) == (ttype, layout), [(o["type"], o["layout"]) for o in r["options"]]
    assert best["why"] and best["preview"]["datasets"]
    df = read_frame(text.encode(), fname)
    table, _ = build(df, "t", best)
    assert table["type"] == ttype and table["cells"]


def test_long_format_is_reshaped():
    df = read_frame(FILES["two_factor.csv"][0].encode(), "x.csv")
    t, _ = build(df, "t", {"type": "grouped", "layout": "long", "mapping": {"rows": "Sex", "cols": "Strain", "value": "Weight"}})
    assert t["rowLabels"] == ["M", "F"] and [d["name"] for d in t["datasets"]] == ["WT", "KO"]
    assert t["datasets"][0]["reps"] == 2 and t["cells"][0][:2] == ["25", "26"]


def test_survival_long_format():
    df = read_frame(FILES["surv.csv"][0].encode(), "x.csv")
    t, _ = build(df, "t", {"type": "survival", "layout": "long", "mapping": {"time": "Days", "event": "Status", "group": "Arm"}})
    assert t["x"][:3] == ["120", "300", "45"] and t["cells"][0] == ["1", ""] and t["cells"][2] == ["", "1"]


def test_numbers_kept_verbatim_and_decimal_comma_explained():
    r = inspect("Name;Value\nA;1,5\nB;2,5\n".encode(), "x.csv")
    assert not r["options"] and "decimal comma" in r["notices"][0]
    r = inspect("A,B\n0.10000000000000001,2\n3,4\n".encode(), "x.csv")
    assert r["options"][0]["preview"]["cells"][0][0] == "0.10000000000000001"


def test_import_api_inspect_and_build(tmp_path):
    from helpers import H, make_apps, register
    app, _, _ = make_apps(tmp_path)
    u = register(app, "zed")
    data = FILES["long_groups.csv"][0].encode()
    r = u.post("/api/import", data={"file": (io.BytesIO(data), "w.csv"), "inspect": "1"}, headers=H, content_type="multipart/form-data")
    opt = r.get_json()["options"][0]
    r = u.post("/api/import", data={"file": (io.BytesIO(data), "w.csv"), "option": json.dumps({k: opt[k] for k in ("type", "layout", "mapping")})},
               headers=H, content_type="multipart/form-data")
    t = r.get_json()
    assert r.status_code == 200 and [d["name"] for d in t["datasets"]] == ["Control", "Drug", "Placebo"]
    bad = {"type": "column", "layout": "long", "mapping": {"group": "nope", "value": "Weight"}}
    r = u.post("/api/import", data={"file": (io.BytesIO(data), "w.csv"), "option": json.dumps(bad)}, headers=H, content_type="multipart/form-data")
    assert r.status_code == 400
    # the old import path still works
    r = u.post("/api/import", data={"file": (io.BytesIO(data), "w.csv"), "type": "multi"}, headers=H, content_type="multipart/form-data")
    assert r.status_code == 200
