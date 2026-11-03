"""Security tests: setup gate, end-to-end encryption contract, isolation between
users, CSRF, throttling, input limits and hardening headers."""
import json
import sqlite3

import pytest

from helpers import H, b64, change_password, env, login, make_apps, name_ct, register, wrap
from openprism import store as store_mod
from openprism.store import derive_auth_key


@pytest.fixture()
def apps(tmp_path):
    return make_apps(tmp_path)


@pytest.fixture()
def app(apps):
    return apps[0]


def test_server_refuses_users_until_setup(tmp_path):
    app, adm, store = make_apps(tmp_path, admin=None)
    c = app.test_client()
    assert c.get("/api/status").get_json()["setup"] is False
    assert c.get("/api/auth/me").status_code == 503
    assert c.post("/api/auth/register", json={}, headers=H).status_code == 503
    assert c.get("/").status_code == 200  # the page itself loads and explains the situation


def test_api_requires_login(app):
    c = app.test_client()
    for path in ("/api/projects", "/api/catalog"):
        assert c.get(path).status_code == 401
    assert c.post("/api/analyze", json={}, headers=H).status_code == 401
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/auth/me").get_json()["auth"] is False


def test_server_never_receives_password(app, tmp_path):
    """Registration/login carry only the derived authentication key; the database holds
    an scrypt hash of it and opaque wrapped keys."""
    pw = "a very secret password 1"
    register(app, "alice", pw)
    db = sqlite3.connect(tmp_path / "openprism.db")
    row = db.execute("SELECT pw_hash, wrapped_key, recovery_key FROM users").fetchone()
    blob = " ".join(str(x) for x in row)
    assert pw not in blob and row[0].startswith("scrypt:")
    dump = "\n".join(db.iterdump())
    assert pw not in dump


def test_kdf_params_do_not_reveal_accounts(app):
    register(app, "alice")
    c = app.test_client()
    real = c.get("/api/auth/kdf?username=alice").get_json()
    fake1 = c.get("/api/auth/kdf?username=nobody").get_json()
    fake2 = c.get("/api/auth/kdf?username=nobody").get_json()
    assert set(real) == set(fake1) and fake1 == fake2 and len(fake1["salt"]) == len(real["salt"])


def test_csrf_header_and_origin_required(app):
    c = register(app, "alice")
    assert c.post("/api/projects", json={"name": name_ct(), "data": env()}).status_code == 403
    r = c.post("/api/projects", json={"name": name_ct(), "data": env()}, headers={**H, "Origin": "https://evil.example"})
    assert r.status_code == 403
    ok = c.post("/api/projects", json={"name": name_ct(), "data": env()}, headers={**H, "Origin": "http://localhost"})
    assert ok.status_code == 200


def test_users_cannot_access_each_others_projects(app):
    a = register(app, "alice")
    b = register(app, "bob")
    data = env()
    pid = a.post("/api/projects", json={"name": name_ct(), "data": data}, headers=H).get_json()["id"]
    assert b.get("/api/projects").get_json()["projects"] == []
    assert b.get(f"/api/projects/{pid}").status_code == 404
    assert b.put(f"/api/projects/{pid}", json={"data": env(), "force": True}, headers=H).status_code == 404
    assert b.post(f"/api/projects/{pid}/duplicate", json={"name": name_ct()}, headers=H).status_code == 404
    assert b.delete(f"/api/projects/{pid}", headers=H).status_code == 404
    assert a.get(f"/api/projects/{pid}").get_json()["data"]["ct"] == data["ct"]


def test_only_ciphertext_is_stored(app, tmp_path):
    a = register(app, "alice")
    a.post("/api/projects", json={"name": name_ct(), "data": env()}, headers=H)
    for bad in [{"tables": [{"cells": [["42"]]}]}, {"format": "openprism-e2e", "v": 1, "iv": "short", "ct": "x"}]:
        assert a.post("/api/projects", json={"name": name_ct(), "data": bad}, headers=H).status_code == 400
    assert a.post("/api/projects", json={"name": "Plain name", "data": env()}, headers=H).status_code == 400
    db = sqlite3.connect(tmp_path / "openprism.db")
    data, nm = db.execute("SELECT data, name_ct FROM projects").fetchone()
    assert json.loads(data)["format"] == "openprism-e2e" and "iv" in json.loads(nm)


def test_session_cookie_flags(app):
    c = app.test_client()
    salt = b64(16)
    r = c.post("/api/auth/register", json={"username": "carol", "auth": derive_auth_key("pw long 123", salt), "salt": salt,
                                           "iter": store_mod.KDF_ITER, "wrappedKey": wrap(), "recoveryKey": wrap()}, headers=H)
    cookie = r.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie


def test_registration_validation_and_duplicates(app):
    c = app.test_client()
    salt = b64(16)
    good = {"auth": derive_auth_key("pw long 123", salt), "salt": salt, "iter": store_mod.KDF_ITER, "wrappedKey": wrap(), "recoveryKey": wrap()}
    for u in ("ab", "../etc", "a b c"):
        assert c.post("/api/auth/register", json={**good, "username": u}, headers=H).status_code == 400
    assert c.post("/api/auth/register", json={**good, "username": "dave", "iter": 1000}, headers=H).status_code == 400
    assert c.post("/api/auth/register", json={**good, "username": "dave", "wrappedKey": "x"}, headers=H).status_code == 400
    assert c.post("/api/auth/register", json={**good, "username": "dave", "auth": "short"}, headers=H).status_code == 400
    register(app, "dave")
    assert c.post("/api/auth/register", json={**good, "username": "DAVE"}, headers=H).status_code == 409
    assert c.post("/api/auth/register", json={**good, "username": "root"}, headers=H).status_code == 409  # admin name


def test_bruteforce_lockout(app):
    register(app, "erin", "erins password 9")
    c = app.test_client()
    for _ in range(store_mod.FAIL_LIMIT):
        assert login(app, "erin", "wrong password", c)[1].status_code == 401
    assert login(app, "erin", "erins password 9", c)[1].status_code == 429


def test_login_returns_wrapped_keys_and_logout(app):
    register(app, "frank", "franks password 9")
    c, r = login(app, "frank", "franks password 9")
    keys = r.get_json()["keys"]
    assert keys["keyState"] == "ok" and json.loads(keys["wrappedKey"])["iv"]
    assert c.get("/api/projects").status_code == 200
    c.post("/api/auth/logout", headers=H)
    assert c.get("/api/projects").status_code == 401


def test_password_change_revokes_other_sessions(app):
    a1 = register(app, "gina", "ginas password 1")
    a2, _ = login(app, "gina", "ginas password 1")
    assert change_password(a1, "gina", "wrong old pw", "new password 22").status_code == 403
    assert change_password(a1, "gina", "ginas password 1", "new password 22").status_code == 200
    assert a1.get("/api/projects").status_code == 200
    assert a2.get("/api/projects").status_code == 401
    assert login(app, "gina", "ginas password 1")[1].status_code == 401
    assert login(app, "gina", "new password 22")[1].status_code == 200


def test_delete_account_removes_projects(app):
    c = register(app, "hank", "hanks password 1")
    pid = c.post("/api/projects", json={"name": name_ct(), "data": env()}, headers=H).get_json()["id"]
    kdf = c.get("/api/auth/kdf?username=hank").get_json()
    assert c.post("/api/auth/delete-account", json={"auth": derive_auth_key("nope nope 1", kdf["salt"])}, headers=H).status_code == 403
    assert c.post("/api/auth/delete-account", json={"auth": derive_auth_key("hanks password 1", kdf["salt"])}, headers=H).status_code == 200
    assert c.get("/api/projects").status_code == 401
    c2 = register(app, "hank", "hanks password 2")
    assert c2.get(f"/api/projects/{pid}").status_code == 404


def test_malformed_and_oversized_inputs(app, monkeypatch):
    c = register(app, "jack")
    assert c.post("/api/projects", data="not json", headers={**H, "Content-Type": "application/json"}).status_code == 400
    assert c.post("/api/projects", json=[1, 2], headers=H).status_code == 400
    monkeypatch.setattr(store_mod, "MAX_PROJECT_BYTES", 1000)
    assert c.post("/api/projects", json={"name": name_ct(), "data": env(5000)}, headers=H).status_code == 413
    huge = {"name": "t", "type": "column", "datasets": [{"name": "a", "reps": 1000}] * 2000, "cells": [[]] * 10}
    assert c.post("/api/analyze", json={"analysis": "descriptive", "table": huge}, headers=H).status_code == 400
    assert c.post("/api/analyze", json={"analysis": "nonexistent", "table": {"type": "column"}}, headers=H).status_code == 400


def test_custom_equation_limits(app):
    c = register(app, "kim")
    table = {"name": "t", "type": "xy", "datasets": [{"name": "a", "reps": 1}], "x": ["1", "2", "3", "4"], "cells": [["1"], ["2"], ["3"], ["4"]]}
    for eq in ["Y = " + "+".join(["A*X"] * 400), 'Y = __import__("os").system("id")', "Y = X" + "(" * 5000]:
        r = c.post("/api/analyze", json={"analysis": "nonlinear", "table": table, "params": {"model": "custom", "equation": eq}}, headers=H)
        assert r.status_code == 400


def test_security_headers(app):
    r = app.test_client().get("/")
    csp = r.headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "object-src 'none'" in csp and "frame-ancestors 'self'" in csp
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert app.test_client().get("/api/health").headers["Cache-Control"] == "no-store"


def test_user_app_has_no_admin_api(app):
    c = register(app, "mallory")
    for path in ("/api/admin/overview", "/api/setup/status"):
        assert c.get(path).status_code == 404
    assert c.post("/api/admin/login", json={"username": "root", "password": "root password 123"}, headers=H).status_code == 404
