"""Test helpers that emulate the browser side of the end-to-end encryption protocol."""
import base64
import json
import os

from openprism.app import create_admin_app, create_app
from openprism.store import KDF_ITER, Store, derive_auth_key

H = {"X-OpenPrism": "1"}
HA = {"X-OpenPrism-Admin": "1"}


def b64(n):
    return base64.b64encode(os.urandom(n)).decode()


def wrap():
    """An opaque wrapped-key envelope as the browser would produce it."""
    return json.dumps({"iv": b64(12), "ct": b64(48)})


def env(payload_len=64):
    return {"format": "openprism-e2e", "v": 1, "iv": b64(12), "ct": b64(payload_len)}


def name_ct():
    return json.dumps({"iv": b64(12), "ct": b64(32)})


def make_apps(tmp_path, admin=("root", "root password 123"), registration=True):
    store = Store(tmp_path / "openprism.db")
    if admin:
        store.setup(admin[0], admin[1], allow_registration=registration)
    app = create_app(store=store)
    app.testing = True
    adm = create_admin_app(store=store)
    adm.testing = True
    return app, adm, store


def register(app, user, pw="a long password 1"):
    c = app.test_client()
    salt = b64(16)
    auth = derive_auth_key(pw, salt)
    r = c.post("/api/auth/register", json={"username": user, "auth": auth, "salt": salt, "iter": KDF_ITER,
                                           "wrappedKey": wrap(), "recoveryKey": wrap()}, headers=H)
    assert r.status_code == 200, r.data
    return c


def login(app, user, pw, client=None):
    c = client or app.test_client()
    kdf = c.get(f"/api/auth/kdf?username={user}").get_json()
    auth = derive_auth_key(pw, kdf["salt"], kdf["iter"])
    return c, c.post("/api/auth/login", json={"username": user, "auth": auth}, headers=H)


def change_password(c, user, old_pw, new_pw):
    kdf = c.get(f"/api/auth/kdf?username={user}").get_json()
    old = derive_auth_key(old_pw, kdf["salt"], kdf["iter"])
    salt = b64(16)
    new = derive_auth_key(new_pw, salt)
    return c.post("/api/auth/password", json={"oldAuth": old, "newAuth": new, "salt": salt, "wrappedKey": wrap(),
                                              "recoveryKey": wrap()}, headers=H)


def admin_client(adm, user="root", pw="root password 123"):
    c = adm.test_client()
    r = c.post("/api/admin/login", json={"username": user, "password": pw}, headers=HA,
               environ_base={"REMOTE_ADDR": "127.0.0.1"})
    assert r.status_code == 200, r.data
    return c
