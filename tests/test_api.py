"""HTTP API tests (Flask test client)."""
import io

import pytest

from openprism.app import create_app
from sample_tables import TABLES


from helpers import env, make_apps, name_ct, register


class Client:
    """Test client that sends the CSRF header like the real front-end."""

    def __init__(self, c):
        self.c = c

    def __getattr__(self, name):
        meth = getattr(self.c, name)
        if name in ("post", "put", "delete", "patch"):
            def wrapped(*a, **kw):
                kw.setdefault("headers", {})["X-OpenPrism"] = "1"
                return meth(*a, **kw)
            return wrapped
        return meth


@pytest.fixture()
def app(tmp_path):
    return make_apps(tmp_path)[0]


@pytest.fixture()
def client(app):
    return Client(register(app, "alice"))


def test_index_and_catalog(client):
    assert client.get("/").status_code == 200
    cat = client.get("/api/catalog").get_json()
    keys = {a["key"] for a in cat["analyses"]}
    assert {"ttest", "one_way", "two_way", "nonlinear", "survival", "contingency"} <= keys
    assert len(cat["models"]) >= 20


@pytest.mark.parametrize("key", sorted(TABLES))
def test_graphdata_and_descriptive(client, key):
    table = TABLES[key]
    g = client.post("/api/graphdata", json={"table": table, "error": "sem"})
    assert g.status_code == 200 and g.get_json()["datasets"]
    r = client.post("/api/analyze", json={"analysis": "descriptive", "table": table, "params": {}})
    assert r.status_code == 200


def test_analysis_error_is_reported(client):
    table = TABLES["column"]
    r = client.post("/api/analyze", json={"analysis": "nonlinear", "table": table, "params": {}})
    assert r.status_code == 400 and "XY" in r.get_json()["error"]


def test_project_roundtrip(client):
    r = client.post("/api/projects", json={"name": name_ct(), "data": env()}).get_json()
    pid = r["id"]
    lst = client.get("/api/projects").get_json()["projects"]
    assert len(lst) == 1 and "name_ct" in lst[0]
    got = client.get(f"/api/projects/{pid}").get_json()
    assert got["data"]["format"] == "openprism-e2e" and got["version"] == 1
    up = client.put(f"/api/projects/{pid}", json={"data": env(), "baseVersion": 1}).get_json()
    assert up["version"] == 2
    assert client.put(f"/api/projects/{pid}", json={"data": env(), "baseVersion": 1}).status_code == 409
    assert client.put(f"/api/projects/{pid}", json={"name": name_ct(), "baseVersion": 2}).status_code == 200
    dup = client.post(f"/api/projects/{pid}/duplicate", json={"name": name_ct()}).get_json()
    client.delete(f"/api/projects/{pid}")
    client.delete(f"/api/projects/{dup['id']}")
    assert client.get("/api/projects").get_json()["projects"] == []


def test_plaintext_projects_are_refused(client):
    plain = {"version": 1, "name": "p", "tables": []}
    assert client.post("/api/projects", json={"name": name_ct(), "data": plain}).status_code == 400
    assert client.post("/api/projects", json={"name": "visible name", "data": env()}).status_code == 400


def test_import_csv(client):
    data = {"file": (io.BytesIO(b"A,B\n1,2\n3,4\n"), "d.csv"), "type": "column"}
    r = client.post("/api/import", data=data, content_type="multipart/form-data")
    t = r.get_json()
    assert [d["name"] for d in t["datasets"]] == ["A", "B"]
    assert t["cells"] == [["1", "2"], ["3", "4"]]


def test_no_example_endpoints(client):
    assert client.get("/api/examples").status_code == 404


def test_power_endpoint(client):
    r = client.post("/api/power", json={"test": "ttest2", "difference": 1, "sd": 1, "power": 0.8, "alpha": 0.05})
    out = r.get_json()
    assert out["n"] == 17  # classic result: d = 1, 80% power, two-sided alpha 0.05
    assert client.post("/api/power", json={"test": "ttest2", "difference": 1, "sd": 1}).status_code == 400


def test_help_manual_served(client):
    r = client.get("/static/help/manual.html")
    assert r.status_code == 200 and b"OpenPrism" in r.data


# every analysis on every compatible sample table must run without crashing
from openprism.stats import ANALYSES  # noqa: E402


@pytest.mark.parametrize("key", sorted(ANALYSES))
def test_every_analysis_runs_on_compatible_tables(client, key):
    types = ANALYSES[key][3]
    ran = 0
    for tname, table in TABLES.items():
        if table["type"] not in types:
            continue
        params = {}
        if key == "survival" and table["type"] != "survival":
            continue
        if key in ("cox", "fine_gray"):
            params = {"timeVar": 5, "eventVar": 6, "predictors": [0, 1]}
        if key == "logistic":
            params = {"dependent": 4, "predictors": [0, 1]}
        if key == "multiple_regression":
            params = {"dependent": 3, "predictors": [0, 1, 2]}
        if key == "factorial":
            params = {"dependent": 3, "factors": [4], "covariates": [0]}
        if key == "poisson":
            params = {"dependent": 6, "predictors": [0, 1]}
        if key == "p_adjust":
            table = {**table, "datasets": table["datasets"][:1], "cells": [[0.001], [0.02], [0.04], [0.3]], "rowLabels": ["a", "b", "c", "d"]}
        if key == "ordinal":
            table = {"name": "o", "type": "multi", "datasets": [{"name": "y", "reps": 1}, {"name": "x", "reps": 1}],
                     "cells": [[1 + (i * 7 % 3), i] for i in range(30)], "rowLabels": [""] * 30}
            params = {"dependent": 0}
        if key in ("cmh", "kappa", "risk", "diagnostic") and table["type"] == "contingency":
            # these need a specific layout: stratified pairs of rows, a square table, or a 2 × 2 table
            table = {**table, "datasets": table["datasets"][:2],
                     "cells": [[12, 20], [6, 25], [9, 18], [5, 22]] if key == "cmh" else [[12, 5], [3, 15]],
                     "rowLabels": ["a", "b", "c", "d"] if key == "cmh" else ["a", "b"]}
        r = client.post("/api/analyze", json={"analysis": key, "table": table, "params": params})
        assert r.status_code in (200, 400), r.data
        if r.status_code == 200:
            ran += 1
    assert ran > 0
