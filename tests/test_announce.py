"""Administrator announcement: public on the sign-in screen, plain text, admin-only to change."""
from helpers import H, HA, admin_client, make_apps, register

LOCAL = {"REMOTE_ADDR": "127.0.0.1"}


def test_announcement_lifecycle(tmp_path):
    app, adm, _ = make_apps(tmp_path)
    anon = app.test_client()
    assert anon.get("/api/status").get_json()["announcement"] is None
    ad = admin_client(adm)
    msg = "On 1 March the server is reset.\nPlease download your projects. <b>not html</b>"
    assert ad.put("/api/admin/settings", json={"announcement": {"text": msg, "level": "urgent"}}, headers=HA, environ_base=LOCAL).status_code == 200
    a = anon.get("/api/status").get_json()["announcement"]          # visible before signing in
    assert a["text"] == msg and a["level"] == "urgent" and a["id"]
    assert ad.get("/api/admin/overview", environ_base=LOCAL).get_json()["announcement"]["text"] == msg
    u = register(app, "alice")
    assert u.get("/api/status").get_json()["announcement"]["id"] == a["id"]
    # users cannot change it
    assert u.put("/api/admin/settings", json={"announcement": {"text": "hacked"}}, headers=H).status_code in (403, 404, 405)
    # changing the text gives a new id (so hidden banners reappear); empty text removes it
    ad.put("/api/admin/settings", json={"announcement": {"text": "Updated", "level": "info"}}, headers=HA, environ_base=LOCAL)
    assert anon.get("/api/status").get_json()["announcement"]["id"] != a["id"]
    ad.put("/api/admin/settings", json={"announcement": {"text": "   "}}, headers=HA, environ_base=LOCAL)
    assert anon.get("/api/status").get_json()["announcement"] is None
    assert ad.put("/api/admin/settings", json={"announcement": {"text": "x" * 2001}}, headers=HA, environ_base=LOCAL).status_code == 400
    assert ad.put("/api/admin/settings", json={"announcement": {"text": "x", "level": "party"}}, headers=HA, environ_base=LOCAL).status_code == 400
