"""Administration console: localhost-only access, first-run setup, registration
policy, account management, one-time passwords, quotas and compute limits."""
import pytest

from helpers import H, HA, admin_client, env, login, make_apps, name_ct, register
from openprism.store import derive_auth_key

LOCAL = {"REMOTE_ADDR": "127.0.0.1"}


@pytest.fixture()
def apps(tmp_path):
    return make_apps(tmp_path)


def uid_of(admin, name):
    return next(u["id"] for u in admin.get("/api/admin/overview", environ_base=LOCAL).get_json()["users"] if u["username"] == name)


def test_admin_console_only_from_localhost(apps):
    _, adm, _ = apps
    c = adm.test_client()
    assert c.get("/api/setup/status", environ_base={"REMOTE_ADDR": "192.168.1.20"}).status_code == 403
    assert c.get("/api/setup/status", environ_base={"REMOTE_ADDR": "10.0.0.5"}).status_code == 403
    # DNS-rebinding: loopback address but a foreign Host header
    assert c.get("/api/setup/status", environ_base=LOCAL, headers={"Host": "evil.example:47219"}).status_code == 403
    assert c.get("/api/setup/status", environ_base=LOCAL).status_code == 200
    assert c.get("/api/setup/status", environ_base={"REMOTE_ADDR": "::1"}).status_code == 200


def test_first_run_setup(tmp_path):
    app, adm, store = make_apps(tmp_path, admin=None)
    c = adm.test_client()
    assert c.get("/api/setup/status", environ_base=LOCAL).get_json()["setup"] is False
    r = c.post("/api/setup", json={"username": "boss", "password": "boss password 1", "allowRegistration": False},
               headers=HA, environ_base=LOCAL)
    assert r.status_code == 200
    assert c.get("/api/admin/overview", environ_base=LOCAL).status_code == 200  # signed in after setup
    # cannot run setup twice
    assert c.post("/api/setup", json={"username": "x2x", "password": "another pw 99"}, headers=HA, environ_base=LOCAL).status_code == 409
    st = app.test_client().get("/api/status").get_json()
    assert st["setup"] is True and st["registration"] is False


def test_registration_flag_in_panel(apps):
    app, adm, _ = apps
    a = admin_client(adm)
    assert a.put("/api/admin/settings", json={"allowRegistration": False}, headers=HA, environ_base=LOCAL).status_code == 200
    c = app.test_client()
    r = c.post("/api/auth/register", json={"username": "zed"}, headers=H)
    assert r.status_code == 403
    a.put("/api/admin/settings", json={"allowRegistration": True}, headers=HA, environ_base=LOCAL)
    register(app, "zed")


def test_admin_sees_metadata_only(apps):
    app, adm, _ = apps
    u = register(app, "user2")
    data = env()
    u.post("/api/projects", json={"name": name_ct(), "data": data}, headers=H)
    a = admin_client(adm)
    ov = a.get("/api/admin/overview", environ_base=LOCAL).get_json()
    text = str(ov)
    assert "user2" in text and data["ct"] not in text and "wrapped" not in text
    # admins are not users: the admin password does not work on the user app
    assert login(app, "root", "root password 123")[1].status_code == 401


def test_admin_creates_user_with_chosen_otp(apps):
    app, adm, _ = apps
    a = admin_client(adm)
    r = a.post("/api/admin/users", json={"username": "newbie", "password": "first time pass 1"}, headers=HA, environ_base=LOCAL)
    assert r.status_code == 200
    c, r = login(app, "newbie", "first time pass 1")
    me = r.get_json()
    assert me["mustChange"] is True and me["keys"]["keyState"] == "none"
    assert c.get("/api/projects").status_code == 403  # must set a new password (and create keys) first


def test_otp_reset_keeps_data_locked(apps):
    app, adm, _ = apps
    register(app, "forgetful", "original password 1")
    anon = app.test_client()
    r1 = anon.post("/api/auth/reset-request", json={"username": "forgetful", "note": "lost it"}, headers=H)
    r2 = anon.post("/api/auth/reset-request", json={"username": "nobody-here"}, headers=H)
    assert r1.get_json()["message"] == r2.get_json()["message"]
    a = admin_client(adm)
    ov = a.get("/api/admin/overview", environ_base=LOCAL).get_json()
    assert [q["username"] for q in ov["requests"]] == ["forgetful"]
    uid = uid_of(a, "forgetful")
    assert a.post(f"/api/admin/users/{uid}/otp", json={"password": "temporary pass 77"}, headers=HA, environ_base=LOCAL).status_code == 200
    assert login(app, "forgetful", "original password 1")[1].status_code == 401
    c, r = login(app, "forgetful", "temporary pass 77")
    me = r.get_json()
    assert me["mustChange"] and me["keys"]["keyState"] == "reset"  # recovery key needed for old data
    assert c.get("/api/projects").status_code == 403


def test_disable_enable_and_delete_user(apps):
    app, adm, _ = apps
    u = register(app, "troll")
    a = admin_client(adm)
    uid = uid_of(a, "troll")
    assert a.put(f"/api/admin/users/{uid}", json={"disabled": True}, headers=HA, environ_base=LOCAL).status_code == 200
    assert u.get("/api/projects").status_code == 401
    assert login(app, "troll", "a long password 1")[1].status_code == 403
    a.put(f"/api/admin/users/{uid}", json={"disabled": False}, headers=HA, environ_base=LOCAL)
    assert login(app, "troll", "a long password 1")[1].status_code == 200
    assert a.delete(f"/api/admin/users/{uid}", headers=HA, environ_base=LOCAL).status_code == 200
    assert login(app, "troll", "a long password 1")[1].status_code == 401


def test_admin_accounts_management(apps):
    _, adm, _ = apps
    a = admin_client(adm)
    assert a.post("/api/admin/admins", json={"username": "second", "password": "second admin 1"}, headers=HA, environ_base=LOCAL).status_code == 200
    ov = a.get("/api/admin/overview", environ_base=LOCAL).get_json()
    me = next(x for x in ov["admins"] if x["username"] == "root")
    assert a.delete(f"/api/admin/admins/{me['id']}", headers=HA, environ_base=LOCAL).status_code == 400
    other = next(x for x in ov["admins"] if x["username"] == "second")
    assert a.delete(f"/api/admin/admins/{other['id']}", headers=HA, environ_base=LOCAL).status_code == 200


def test_admin_requires_csrf_header_and_login(apps):
    _, adm, _ = apps
    c = adm.test_client()
    assert c.get("/api/admin/overview", environ_base=LOCAL).status_code == 401
    assert c.post("/api/admin/login", json={"username": "root", "password": "root password 123"}, environ_base=LOCAL).status_code == 403


def test_storage_quota_and_warning(apps):
    app, adm, _ = apps
    u = register(app, "hoarder")
    a = admin_client(adm)
    uid = uid_of(a, "hoarder")
    lst = u.get("/api/projects").get_json()
    assert lst["quota"] == 256 * 1024 * 1024 and lst["warnAt"] == 128 * 1024 * 1024
    assert a.put(f"/api/admin/users/{uid}", json={"limits": {"quota_mb": 1}}, headers=HA, environ_base=LOCAL).status_code == 200
    assert a.put(f"/api/admin/users/{uid}", json={"limits": {"quota_mb": 999999}}, headers=HA, environ_base=LOCAL).status_code == 400
    assert u.post("/api/projects", json={"name": name_ct(), "data": env(600_000)}, headers=H).status_code == 200
    r = u.post("/api/projects", json={"name": name_ct(), "data": env(600_000)}, headers=H)
    assert r.status_code == 413 and "quota" in r.get_json()["error"]


def test_rate_limit_per_user(apps):
    app, adm, _ = apps
    u = register(app, "spammer")
    a = admin_client(adm)
    a.put(f"/api/admin/users/{uid_of(a, 'spammer')}", json={"limits": {"rate_per_min": 5}}, headers=HA, environ_base=LOCAL)
    table = {"name": "t", "type": "column", "datasets": [{"name": "a", "reps": 1}], "cells": [["1"], ["2"], ["3"]]}
    codes = [u.post("/api/analyze", json={"analysis": "descriptive", "table": table}, headers=H).status_code for _ in range(7)]
    assert codes[:5] == [200] * 5 and codes[5] == 429


def test_memory_limit_enforced(apps, monkeypatch):
    from openprism import sandbox
    if not sandbox.AVAILABLE:
        pytest.skip("sandbox not available on this platform")
    app, adm, _ = apps
    u = register(app, "bigdata")
    a = admin_client(adm)
    a.put(f"/api/admin/users/{uid_of(a, 'bigdata')}", json={"limits": {"mem_mb": 128}}, headers=HA, environ_base=LOCAL)
    import numpy as np
    from openprism.stats import ANALYSES
    from openprism.stats.common import Result

    def hog(table, params):  # allocates ~800 MB
        np.ones(100_000_000).sum()
        return Result("never")
    monkeypatch.setitem(ANALYSES, "_hog", (hog, "hog", "test", ["column"]))
    table = {"name": "t", "type": "column", "datasets": [{"name": "a", "reps": 1}], "cells": [["1"], ["2"]]}
    r = u.post("/api/analyze", json={"analysis": "_hog", "table": table}, headers=H)
    assert r.status_code == 429 and r.get_json().get("limit")


def test_default_limits_apply_to_new_users(apps):
    app, adm, _ = apps
    a = admin_client(adm)
    a.put("/api/admin/settings", json={"defaults": {"quota_mb": 64}}, headers=HA, environ_base=LOCAL)
    u = register(app, "late")
    assert u.get("/api/projects").get_json()["quota"] == 64 * 1024 * 1024
    assert derive_auth_key  # imported helper sanity
