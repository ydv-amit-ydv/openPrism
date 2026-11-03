"""End-to-end encrypted sharing between users: only ciphertext, strict isolation, limits."""
import json
import sqlite3

from helpers import H, HA, admin_client, b64, env, make_apps, name_ct, register

LOCAL = {"REMOTE_ADDR": "127.0.0.1"}
PUB = b64(91)


def keys(c):
    priv = json.dumps({"iv": b64(12), "ct": b64(150)})
    assert c.put("/api/sharing/keys", json={"pub": b64(91), "priv": priv}, headers=H).status_code == 200


def share_body(to, data=None):
    return {"to": to, "share": {"eph": b64(91), "salt": b64(16), "wrapped": json.dumps({"iv": b64(12), "ct": b64(48)}),
                                "name_ct": name_ct(), "note_ct": "", "data": data or env()}}


def test_share_flow_and_isolation(tmp_path):
    app, adm, _ = make_apps(tmp_path)
    a, b, m = register(app, "alice"), register(app, "bob"), register(app, "mallory")
    keys(a); keys(b)
    assert a.get("/api/sharing/pubkey?username=bob").get_json()["username"] == "bob"
    assert a.get("/api/sharing/pubkey?username=nobody").status_code == 404
    assert a.get("/api/sharing/pubkey?username=mallory").status_code == 404      # no key yet: cannot receive
    r = a.post("/api/sharing/send", json=share_body("bob"), headers=H)
    assert r.status_code == 200
    sid = r.get_json()["id"]
    inbox = b.get("/api/sharing/inbox").get_json()["shares"]
    assert [s["id"] for s in inbox] == [sid] and inbox[0]["from"] == "alice" and "data" not in inbox[0]
    assert a.get("/api/sharing/sent").get_json()["shares"][0]["to"] == "bob"
    assert m.get(f"/api/sharing/{sid}").status_code == 404                        # nobody else can fetch it
    assert a.get(f"/api/sharing/{sid}").status_code == 404                        # not even the sender (recipient only)
    assert m.delete(f"/api/sharing/{sid}", headers=H).status_code == 404
    full = b.get(f"/api/sharing/{sid}").get_json()
    assert full["data"]["format"] == "openprism-e2e" and full["from"] == "alice"
    assert b.delete(f"/api/sharing/{sid}", headers=H).status_code == 200
    assert b.get("/api/sharing/inbox").get_json()["shares"] == []


def test_share_requires_ciphertext_and_limits(tmp_path):
    app, adm, _ = make_apps(tmp_path)
    a, b = register(app, "alice"), register(app, "bob")
    keys(a); keys(b)
    assert a.post("/api/sharing/send", json=share_body("bob", {"tables": [{"cells": [["42"]]}]}), headers=H).status_code == 400
    bad = share_body("bob"); bad["share"]["name_ct"] = "My secret project"
    assert a.post("/api/sharing/send", json=bad, headers=H).status_code == 400
    assert a.post("/api/sharing/send", json=share_body("alice"), headers=H).status_code == 400   # not to oneself
    stale = share_body("bob"); stale["share"]["recipientPub"] = b64(91)
    assert a.post("/api/sharing/send", json=stale, headers=H).status_code == 409                   # recipient key changed
    import openprism.store as st
    old = st.MAX_SHARES_OUT
    st.MAX_SHARES_OUT = 2
    try:
        codes = [a.post("/api/sharing/send", json=share_body("bob"), headers=H).status_code for _ in range(3)]
    finally:
        st.MAX_SHARES_OUT = old
    assert codes == [200, 200, 413]
    db = sqlite3.connect(tmp_path / "openprism.db")
    for (envelope,) in db.execute("SELECT envelope FROM shares"):
        e = json.loads(envelope)
        assert set(e) == {"eph", "salt", "wrapped", "name_ct", "note_ct", "data"} and e["data"]["format"] == "openprism-e2e"


def test_admin_can_turn_sharing_off(tmp_path):
    app, adm, _ = make_apps(tmp_path)
    a, b = register(app, "alice"), register(app, "bob")
    keys(a); keys(b)
    ad = admin_client(adm)
    assert ad.put("/api/admin/settings", json={"allowSharing": False}, headers=HA, environ_base=LOCAL).status_code == 200
    assert a.post("/api/sharing/send", json=share_body("bob"), headers=H).status_code == 403
    assert ad.get("/api/admin/overview", environ_base=LOCAL).get_json()["allowSharing"] is False
