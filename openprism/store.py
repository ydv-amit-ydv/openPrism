"""Persistent storage: server settings, administrators, users, sessions,
end-to-end encrypted projects, password-reset requests and login throttling.

End-to-end encryption model
---------------------------
The browser derives 64 bytes from the user's password with PBKDF2-SHA-256
(600 000 iterations, per-user random salt):

* bytes  0..31 — the *key-encryption key* (KEK). Never sent to the server.
* bytes 32..63 — the *authentication key*. Sent at sign-in; the server stores
  only an scrypt hash of it.

A random 256-bit *data key* encrypts every project (contents **and** name)
with AES-256-GCM in the browser. The server keeps the data key only in
wrapped form: once encrypted with the KEK and once with a *recovery key* that
the user writes down at registration. Hence neither the server, its database
nor its administrators can read any project.

Administrators are a separate class of accounts (table ``admins``) that can
only sign in on the localhost-only administration port. They manage accounts
and limits but have no access to user data.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import shutil
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,31}$")
PASSWORD_MIN, PASSWORD_MAX = 8, 256
KDF_ITER = 600_000

SESSION_IDLE = 7 * 24 * 3600
SESSION_ABSOLUTE = 30 * 24 * 3600
ADMIN_SESSION_IDLE = 2 * 3600

MB = 1024 * 1024
MAX_PROJECT_BYTES = 25 * MB
MAX_PROJECTS = 500
WARN_FRACTION = 0.5
HARD_MAX_QUOTA = 4096 * MB
MAX_NAME_CT = 2048                   # encrypted project name (base64 JSON)

DEFAULT_LIMITS = {"quota_mb": 256, "project_mb": 25, "mem_mb": 1024, "cpu_s": 60, "rate_per_min": 600}
LIMIT_BOUNDS = {"quota_mb": (1, HARD_MAX_QUOTA // MB), "project_mb": (1, 25), "mem_mb": (128, 16384),
                "cpu_s": (5, 3600), "rate_per_min": (5, 10000)}

FAIL_LIMIT = 5
LOCK_BASE = 60
LOCK_MAX = 3600
SCHEMA_VERSION = 2
MAX_SHARES_IN = 50          # pending shared projects per recipient
MAX_SHARES_OUT = 50         # pending shares per sender
MAX_SHARE_BYTES_IN = 256 * 1024 * 1024

_DUMMY_HASH = generate_password_hash("not-a-real-password-x", method="scrypt")

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS admins (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  pw_hash TEXT NOT NULL,
  created REAL NOT NULL,
  last_login REAL
);
CREATE TABLE IF NOT EXISTS admin_sessions (
  token_hash TEXT PRIMARY KEY,
  admin_id INTEGER NOT NULL REFERENCES admins(id) ON DELETE CASCADE,
  created REAL NOT NULL,
  last_seen REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  pw_hash TEXT NOT NULL,          -- scrypt(authentication key)
  kdf_salt TEXT NOT NULL,         -- base64, used by the browser for PBKDF2
  kdf_iter INTEGER NOT NULL,
  wrapped_key TEXT,               -- data key encrypted with the password KEK (opaque JSON)
  recovery_key TEXT,              -- data key encrypted with the recovery key (opaque JSON)
  key_state TEXT NOT NULL DEFAULT 'none',   -- none | ok | reset (password reset: KEK no longer matches)
  created REAL NOT NULL,
  pw_changed REAL NOT NULL,
  last_login REAL,
  disabled INTEGER NOT NULL DEFAULT 0,
  must_change INTEGER NOT NULL DEFAULT 0,
  limits TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created REAL NOT NULL,
  last_seen REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name_ct TEXT NOT NULL,          -- encrypted name (opaque)
  data TEXT NOT NULL,             -- encrypted contents (opaque)
  size INTEGER NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS projects_user ON projects(user_id, updated);
CREATE TABLE IF NOT EXISTS reset_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL,
  user_id INTEGER,
  note TEXT,
  ip TEXT,
  created REAL NOT NULL,
  status TEXT NOT NULL DEFAULT 'open'
);
CREATE TABLE IF NOT EXISTS admin_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  admin TEXT NOT NULL,
  action TEXT NOT NULL,
  target TEXT
);
CREATE TABLE IF NOT EXISTS shares (
  id TEXT PRIMARY KEY,
  from_user INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  to_user INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  envelope TEXT NOT NULL,         -- {eph, salt, wrapped, name_ct, note_ct, data}: all ciphertext for the recipient
  size INTEGER NOT NULL,
  created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS shares_to ON shares(to_user, created);
CREATE INDEX IF NOT EXISTS shares_from ON shares(from_user, created);
CREATE TABLE IF NOT EXISTS throttle (
  key TEXT PRIMARY KEY,
  failures INTEGER NOT NULL,
  locked_until REAL NOT NULL,
  lock_level INTEGER NOT NULL DEFAULT 0,
  updated REAL NOT NULL
);
"""


class StoreError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def derive_auth_key(password: str, salt_b64: str, iterations: int = KDF_ITER) -> str:
    """Same derivation as the browser: PBKDF2-SHA-256, 64 bytes; bytes 32..63 authenticate.

    Used only for administrator-issued one-time passwords (which never unlock data)."""
    raw = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt_b64), iterations, dklen=64)
    return b64(raw[32:])


def _valid_b64(s, min_len=16, max_len=200):
    if not isinstance(s, str) or not (min_len <= len(s) <= max_len):
        return False
    try:
        base64.b64decode(s, validate=True)
        return True
    except (ValueError, TypeError):
        return False


def _valid_wrap(s):
    """A wrapped key is an opaque JSON envelope {iv, ct} produced by the browser."""
    if not isinstance(s, str) or len(s) > 2000:
        return False
    try:
        d = json.loads(s)
    except ValueError:
        return False
    return isinstance(d, dict) and _valid_b64(d.get("iv"), 12, 40) and _valid_b64(d.get("ct"), 16, 400)


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate_old()
        with self.conn() as c:
            c.executescript(SCHEMA)
            cols = {r[1] for r in c.execute("PRAGMA table_info(users)")}
            for col in ("share_pub", "share_priv"):  # sharing keys (added in 0.8)
                if col not in cols:
                    c.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
            if not self._get(c, "secret"):
                self._set(c, "secret", secrets.token_hex(32))
                self._set(c, "schema", str(SCHEMA_VERSION))
        try:
            self.path.chmod(0o600)
        except OSError:  # pragma: no cover
            pass

    def _migrate_old(self):
        """Databases from before end-to-end encryption cannot be upgraded (their
        projects are not encrypted with user keys): keep a backup and start fresh."""
        if not self.path.exists():
            return
        c = sqlite3.connect(self.path)
        try:
            cols = {r[1] for r in c.execute("PRAGMA table_info(users)")}
        finally:
            c.close()
        if cols and "kdf_salt" not in cols:
            backup = self.path.with_suffix(f".pre-e2e-{int(time.time())}.bak")
            shutil.move(self.path, backup)
            for ext in ("-wal", "-shm"):
                p = Path(str(self.path) + ext)
                if p.exists():
                    p.unlink()

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        c.execute("PRAGMA journal_mode = WAL")
        try:
            yield c
        finally:
            c.close()

    # -------------------------------------------------------------- settings
    @staticmethod
    def _get(c, key, default=None):
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    @staticmethod
    def _set(c, key, value):
        c.execute("INSERT INTO settings(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (key, str(value)))

    def setting(self, key, default=None):
        with self.conn() as c:
            return self._get(c, key, default)

    def set_setting(self, key, value):
        with self.conn() as c:
            self._set(c, key, value)

    def is_setup(self):
        with self.conn() as c:
            return c.execute("SELECT COUNT(*) n FROM admins").fetchone()["n"] > 0

    ANNOUNCE_LEVELS = ("info", "warning", "urgent")

    def announcement(self):
        """The administrator's message to all users (shown on the sign-in screen and in the app), or None."""
        import json as _json
        try:
            a = _json.loads(self.setting("announcement", "") or "null")
        except ValueError:
            return None
        return a if isinstance(a, dict) and a.get("text") else None

    def set_announcement(self, text, level="info"):
        import json as _json
        text = str(text or "").strip()
        if len(text) > 2000:
            raise StoreError("The announcement is too long (2000 characters at most).", 400)
        if level not in self.ANNOUNCE_LEVELS:
            raise StoreError("Unknown announcement level.", 400)
        if not text:
            self.set_setting("announcement", "")
            return None
        a = {"text": text, "level": level, "id": secrets.token_hex(6), "updated": int(time.time())}
        self.set_setting("announcement", _json.dumps(a))
        return a

    def registration_open(self):
        return self.setting("allow_registration", "1") == "1"

    def default_limits(self):
        try:
            d = json.loads(self.setting("default_limits", "{}"))
        except ValueError:
            d = {}
        return self._clamp_limits({**DEFAULT_LIMITS, **d})

    @staticmethod
    def _clamp_limits(d):
        out = {}
        for k, (lo, hi) in LIMIT_BOUNDS.items():
            try:
                out[k] = max(lo, min(hi, int(d.get(k, DEFAULT_LIMITS[k]))))
            except (TypeError, ValueError):
                out[k] = DEFAULT_LIMITS[k]
        return out

    # ------------------------------------------------------------ throttling
    def check_throttle(self, keys):
        now = time.time()
        with self.conn() as c:
            for k in keys:
                row = c.execute("SELECT locked_until FROM throttle WHERE key=?", (k,)).fetchone()
                if row and row["locked_until"] > now:
                    wait = int(row["locked_until"] - now) + 1
                    raise StoreError(f"Too many failed attempts. Try again in {wait} s.", 429)

    def record_failure(self, keys):
        now = time.time()
        with self.conn() as c:
            for k in keys:
                row = c.execute("SELECT failures, lock_level, updated FROM throttle WHERE key=?", (k,)).fetchone()
                stale = row is not None and now - row["updated"] > 3600
                failures = (row["failures"] if row and not stale else 0) + 1
                level = row["lock_level"] if row and not stale else 0
                locked = 0.0
                if failures >= FAIL_LIMIT:
                    locked = now + min(LOCK_MAX, LOCK_BASE * (2 ** level))
                    level += 1
                    failures = 0
                c.execute("INSERT INTO throttle(key, failures, locked_until, lock_level, updated) VALUES(?,?,?,?,?) "
                          "ON CONFLICT(key) DO UPDATE SET failures=excluded.failures, locked_until=excluded.locked_until, "
                          "lock_level=excluded.lock_level, updated=excluded.updated", (k, failures, locked, level, now))

    def clear_failures(self, keys):
        with self.conn() as c:
            for k in keys:
                c.execute("DELETE FROM throttle WHERE key=?", (k,))

    # ------------------------------------------------------------- validation
    @staticmethod
    def validate_username(username):
        if not isinstance(username, str) or not USERNAME_RE.match(username):
            raise StoreError("User ID must be 3-32 characters: letters, digits, '.', '_' or '-', starting with a letter or digit.")
        return username

    @staticmethod
    def validate_password(pw, username=""):
        """Plain passwords are only seen for administrators and admin-issued one-time passwords."""
        if not isinstance(pw, str) or not (PASSWORD_MIN <= len(pw) <= PASSWORD_MAX):
            raise StoreError(f"Password must be {PASSWORD_MIN}-{PASSWORD_MAX} characters.")
        if username and pw.lower() == username.lower():
            raise StoreError("Password must differ from the user ID.")
        if len(set(pw)) < 4:
            raise StoreError("Password is too simple.")
        return pw

    @staticmethod
    def _check_auth_key(auth):
        if not _valid_b64(auth, 40, 48):
            raise StoreError("Invalid credentials format.")
        return auth

    # ------------------------------------------------------------- admins
    def setup(self, username, password, allow_registration=True, limits=None):
        with self.conn() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                if c.execute("SELECT COUNT(*) n FROM admins").fetchone()["n"]:
                    raise StoreError("The server is already set up.", 409)
                self.validate_username(username)
                self.validate_password(password, username)
                now = time.time()
                c.execute("INSERT INTO admins(username, pw_hash, created) VALUES(?,?,?)",
                          (username, generate_password_hash(password, method="scrypt"), now))
                self._set(c, "allow_registration", "1" if allow_registration else "0")
                self._set(c, "default_limits", json.dumps(self._clamp_limits(limits or {})))
                self._set(c, "setup_time", str(now))
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise

    def create_admin(self, username, password):
        self.validate_username(username)
        self.validate_password(password, username)
        with self.conn() as c:
            try:
                c.execute("INSERT INTO admins(username, pw_hash, created) VALUES(?,?,?)",
                          (username, generate_password_hash(password, method="scrypt"), time.time()))
            except sqlite3.IntegrityError:
                raise StoreError("This administrator name is already taken.", 409) from None

    def list_admins(self):
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT id, username, created, last_login FROM admins ORDER BY username")]

    def delete_admin(self, acting_id, admin_id):
        with self.conn() as c:
            if c.execute("SELECT COUNT(*) n FROM admins").fetchone()["n"] <= 1:
                raise StoreError("There must be at least one administrator.")
            if acting_id == admin_id:
                raise StoreError("You cannot delete your own administrator account.")
            c.execute("DELETE FROM admins WHERE id=?", (admin_id,))

    def admin_authenticate(self, username, password):
        if not isinstance(username, str) or not isinstance(password, str) or len(password) > PASSWORD_MAX:
            return None
        with self.conn() as c:
            row = c.execute("SELECT id, pw_hash FROM admins WHERE username=?", (username,)).fetchone()
        if row is None:
            check_password_hash(_DUMMY_HASH, password)
            return None
        if not check_password_hash(row["pw_hash"], password):
            return None
        with self.conn() as c:
            c.execute("UPDATE admins SET last_login=? WHERE id=?", (time.time(), row["id"]))
        return row["id"]

    def admin_change_password(self, admin_id, old, new):
        with self.conn() as c:
            row = c.execute("SELECT username, pw_hash FROM admins WHERE id=?", (admin_id,)).fetchone()
        if not row or not check_password_hash(row["pw_hash"], old or ""):
            raise StoreError("Current password is incorrect.", 403)
        self.validate_password(new, row["username"])
        with self.conn() as c:
            c.execute("UPDATE admins SET pw_hash=? WHERE id=?", (generate_password_hash(new, method="scrypt"), admin_id))

    def get_admin(self, admin_id):
        with self.conn() as c:
            row = c.execute("SELECT id, username FROM admins WHERE id=?", (admin_id,)).fetchone()
        return dict(row) if row else None

    def new_admin_session(self, admin_id):
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self.conn() as c:
            c.execute("INSERT INTO admin_sessions VALUES(?,?,?,?)", (_h(token), admin_id, now, now))
            c.execute("DELETE FROM admin_sessions WHERE last_seen < ?", (now - ADMIN_SESSION_IDLE,))
        return token

    def admin_session(self, token):
        if not token or not isinstance(token, str) or len(token) > 100:
            return None, None
        th = _h(token)
        now = time.time()
        with self.conn() as c:
            row = c.execute("SELECT admin_id, last_seen FROM admin_sessions WHERE token_hash=?", (th,)).fetchone()
            if not row or row["last_seen"] < now - ADMIN_SESSION_IDLE:
                c.execute("DELETE FROM admin_sessions WHERE token_hash=?", (th,))
                return None, None
            c.execute("UPDATE admin_sessions SET last_seen=? WHERE token_hash=?", (now, th))
        return row["admin_id"], th

    def end_admin_session(self, th):
        with self.conn() as c:
            c.execute("DELETE FROM admin_sessions WHERE token_hash=?", (th,))

    # ----------------------------------------------------------------- users
    def kdf_params(self, username):
        """Salt + iterations for the browser's key derivation. For unknown users a
        deterministic fake salt is returned so accounts cannot be enumerated."""
        if isinstance(username, str):
            with self.conn() as c:
                row = c.execute("SELECT kdf_salt, kdf_iter FROM users WHERE username=?", (username,)).fetchone()
                secret = self._get(c, "secret", "")
            if row:
                return {"salt": row["kdf_salt"], "iter": row["kdf_iter"]}
        else:
            secret, username = self.setting("secret", ""), ""
        fake = hmac.new(secret.encode(), f"salt:{str(username).lower()}".encode(), hashlib.sha256).digest()[:16]
        return {"salt": b64(fake), "iter": KDF_ITER}

    def create_user(self, username, auth, salt, wrapped_key, recovery_key, iterations=KDF_ITER):
        """Register a user. Only the authentication key (never the password) is received."""
        self.validate_username(username)
        self._check_auth_key(auth)
        if not _valid_b64(salt, 16, 64) or iterations != KDF_ITER:
            raise StoreError("Invalid key derivation parameters.")
        if not (_valid_wrap(wrapped_key) and _valid_wrap(recovery_key)):
            raise StoreError("Invalid encryption keys.")
        now = time.time()
        limits = json.dumps(self.default_limits())
        with self.conn() as c:
            if c.execute("SELECT 1 FROM admins WHERE username=?", (username,)).fetchone():
                raise StoreError("This user ID is already taken.", 409)
            try:
                cur = c.execute(
                    "INSERT INTO users(username, pw_hash, kdf_salt, kdf_iter, wrapped_key, recovery_key, key_state, created, "
                    "pw_changed, last_login, limits) VALUES(?,?,?,?,?,?,'ok',?,?,?,?)",
                    (username, generate_password_hash(auth, method="scrypt"), salt, iterations, wrapped_key, recovery_key,
                     now, now, now, limits))
            except sqlite3.IntegrityError:
                raise StoreError("This user ID is already taken.", 409) from None
            return cur.lastrowid

    def authenticate(self, username, auth):
        if not isinstance(username, str) or not isinstance(auth, str) or len(auth) > 64:
            check_password_hash(_DUMMY_HASH, "x")
            return None
        with self.conn() as c:
            row = c.execute("SELECT id, pw_hash, disabled FROM users WHERE username=?", (username,)).fetchone()
        if row is None:
            check_password_hash(_DUMMY_HASH, auth)
            return None
        if not check_password_hash(row["pw_hash"], auth):
            return None
        if row["disabled"]:
            raise StoreError("This account has been disabled. Contact the administrator.", 403)
        with self.conn() as c:
            c.execute("UPDATE users SET last_login=? WHERE id=?", (time.time(), row["id"]))
        return row["id"]

    def get_user(self, user_id):
        with self.conn() as c:
            row = c.execute("SELECT id, username, created, disabled, must_change, last_login, limits, key_state, "
                            "kdf_salt, kdf_iter, wrapped_key, recovery_key FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            return None
        u = dict(row)
        u["limits"] = self.limits_from(row["limits"])
        u["disabled"], u["must_change"] = bool(u["disabled"]), bool(u["must_change"])
        return u

    @staticmethod
    def key_material(u):
        """What the browser needs to unlock the data key (all opaque to the server)."""
        return {"salt": u["kdf_salt"], "iter": u["kdf_iter"], "wrappedKey": u["wrapped_key"],
                "recoveryKey": u["recovery_key"], "keyState": u["key_state"]}

    @classmethod
    def limits_from(cls, text):
        try:
            d = json.loads(text) if text else {}
        except ValueError:
            d = {}
        return cls._clamp_limits({**DEFAULT_LIMITS, **(d if isinstance(d, dict) else {})})

    def set_credentials(self, user_id, old_auth, new_auth, salt, wrapped_key, recovery_key=None, keep_token_hash=None):
        """Password change (also completes a one-time-password reset). The browser
        re-wraps the data key with the new KEK — projects need no re-encryption."""
        self._check_auth_key(new_auth)
        if not _valid_b64(salt, 16, 64) or not _valid_wrap(wrapped_key) or (recovery_key is not None and not _valid_wrap(recovery_key)):
            raise StoreError("Invalid encryption keys.")
        with self.conn() as c:
            row = c.execute("SELECT pw_hash FROM users WHERE id=?", (user_id,)).fetchone()
        if not row or not isinstance(old_auth, str) or not check_password_hash(row["pw_hash"], old_auth):
            raise StoreError("Current password is incorrect.", 403)
        if hmac.compare_digest(old_auth, new_auth):
            raise StoreError("The new password must be different.")
        with self.conn() as c:
            sets = "pw_hash=?, kdf_salt=?, kdf_iter=?, wrapped_key=?, key_state='ok', must_change=0, pw_changed=?"
            args = [generate_password_hash(new_auth, method="scrypt"), salt, KDF_ITER, wrapped_key, time.time()]
            if recovery_key is not None:
                sets += ", recovery_key=?"
                args.append(recovery_key)
            c.execute(f"UPDATE users SET {sets} WHERE id=?", (*args, user_id))
            c.execute("DELETE FROM sessions WHERE user_id=? AND token_hash<>?", (user_id, keep_token_hash or ""))

    def set_recovery(self, user_id, auth, recovery_key):
        if not _valid_wrap(recovery_key):
            raise StoreError("Invalid recovery key data.")
        with self.conn() as c:
            row = c.execute("SELECT pw_hash FROM users WHERE id=?", (user_id,)).fetchone()
            if not row or not isinstance(auth, str) or not check_password_hash(row["pw_hash"], auth):
                raise StoreError("Password is incorrect.", 403)
            c.execute("UPDATE users SET recovery_key=? WHERE id=?", (recovery_key, user_id))

    def delete_user_self(self, user_id, auth):
        with self.conn() as c:
            row = c.execute("SELECT pw_hash FROM users WHERE id=?", (user_id,)).fetchone()
            if not row or not isinstance(auth, str) or not check_password_hash(row["pw_hash"], auth):
                raise StoreError("Password is incorrect.", 403)
            c.execute("DELETE FROM users WHERE id=?", (user_id,))

    # -------------------------------------------------------------- sessions
    def new_session(self, user_id):
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self.conn() as c:
            c.execute("INSERT INTO sessions(token_hash, user_id, created, last_seen) VALUES(?,?,?,?)",
                      (_h(token), user_id, now, now))
            c.execute("DELETE FROM sessions WHERE last_seen < ? OR created < ?", (now - SESSION_IDLE, now - SESSION_ABSOLUTE))
        return token

    def session_user(self, token):
        if not token or not isinstance(token, str) or len(token) > 100:
            return None, None
        th = _h(token)
        now = time.time()
        with self.conn() as c:
            row = c.execute("SELECT user_id, created, last_seen FROM sessions WHERE token_hash=?", (th,)).fetchone()
            if not row:
                return None, None
            if row["last_seen"] < now - SESSION_IDLE or row["created"] < now - SESSION_ABSOLUTE:
                c.execute("DELETE FROM sessions WHERE token_hash=?", (th,))
                return None, None
            if now - row["last_seen"] > 300:
                c.execute("UPDATE sessions SET last_seen=? WHERE token_hash=?", (now, th))
        return row["user_id"], th

    def end_session(self, token_hash):
        with self.conn() as c:
            c.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))

    def end_all_sessions(self, user_id):
        with self.conn() as c:
            c.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))

    # -------------------------------------------------------------- projects
    @staticmethod
    def _clean_name_ct(name_ct):
        if not isinstance(name_ct, str) or not _valid_wrap(name_ct) or len(name_ct) > MAX_NAME_CT:
            raise StoreError("Encrypted project name is malformed.")
        return name_ct

    @staticmethod
    def _serialize(data):
        """Only end-to-end encrypted envelopes are accepted — plaintext projects are refused."""
        if not (isinstance(data, dict) and data.get("format") == "openprism-e2e" and data.get("v") == 1
                and _valid_b64(data.get("iv"), 12, 40) and isinstance(data.get("ct"), str)):
            raise StoreError("Projects must be end-to-end encrypted by the browser.")
        text = json.dumps({"format": "openprism-e2e", "v": 1, "iv": data["iv"], "ct": data["ct"]}, separators=(",", ":"))
        if len(text) > MAX_PROJECT_BYTES:
            raise StoreError(f"Project is larger than {MAX_PROJECT_BYTES // MB} MB.", 413)
        return text

    def _quota(self, c, user_id):
        row = c.execute("SELECT limits FROM users WHERE id=?", (user_id,)).fetchone()
        lim = self.limits_from(row["limits"] if row else None)
        return lim["quota_mb"] * MB, min(lim["project_mb"] * MB, MAX_PROJECT_BYTES)

    def _check_quota(self, c, user_id, add_bytes, replacing_id=None):
        quota, max_project = self._quota(c, user_id)
        if add_bytes > max_project:
            raise StoreError(f"This project is larger than your per-project limit of {max_project // MB} MB.", 413)
        row = c.execute("SELECT COUNT(*) n, COALESCE(SUM(size),0) s FROM projects WHERE user_id=? AND id<>?",
                        (user_id, replacing_id or "")).fetchone()
        if replacing_id is None and row["n"] >= MAX_PROJECTS:
            raise StoreError(f"You have reached the limit of {MAX_PROJECTS} projects. Delete some first.", 413)
        if row["s"] + add_bytes > quota:
            raise StoreError(f"Your storage quota ({quota // MB} MB) is full. Download old projects to your computer "
                             "and delete them from the server to free space.", 413)

    def list_projects(self, user_id):
        with self.conn() as c:
            rows = c.execute("SELECT id, name_ct, size, version, created, updated FROM projects "
                             "WHERE user_id=? ORDER BY updated DESC", (user_id,)).fetchall()
            usage = c.execute("SELECT COALESCE(SUM(size),0) s FROM projects WHERE user_id=?", (user_id,)).fetchone()["s"]
            quota, max_project = self._quota(c, user_id)
        return {"projects": [dict(r) for r in rows], "usage": usage, "quota": quota,
                "warnAt": int(quota * WARN_FRACTION), "maxProjectBytes": max_project, "maxProjects": MAX_PROJECTS}

    def get_project(self, user_id, pid):
        with self.conn() as c:
            row = c.execute("SELECT id, name_ct, data, version, updated FROM projects WHERE id=? AND user_id=?",
                            (pid, user_id)).fetchone()
        if not row:
            raise StoreError("Project not found.", 404)
        return {"id": row["id"], "name_ct": row["name_ct"], "version": row["version"], "updated": row["updated"],
                "data": json.loads(row["data"])}

    def create_project(self, user_id, name_ct, data):
        name_ct = self._clean_name_ct(name_ct)
        text = self._serialize(data)
        pid = secrets.token_hex(16)
        now = time.time()
        with self.conn() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                self._check_quota(c, user_id, len(text))
                c.execute("INSERT INTO projects(id, user_id, name_ct, data, size, version, created, updated) "
                          "VALUES(?,?,?,?,?,1,?,?)", (pid, user_id, name_ct, text, len(text), now, now))
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
        return {"id": pid, "version": 1, "updated": now}

    def update_project(self, user_id, pid, data=None, name_ct=None, base_version=None, force=False):
        with self.conn() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                row = c.execute("SELECT version FROM projects WHERE id=? AND user_id=?", (pid, user_id)).fetchone()
                if not row:
                    raise StoreError("Project not found.", 404)
                if not force and base_version is not None and int(base_version) != row["version"]:
                    raise StoreError("This project was changed elsewhere (another tab or device).", 409)
                sets, args = [], []
                if name_ct is not None:
                    sets.append("name_ct=?")
                    args.append(self._clean_name_ct(name_ct))
                if data is not None:
                    text = self._serialize(data)
                    self._check_quota(c, user_id, len(text), replacing_id=pid)
                    sets += ["data=?", "size=?"]
                    args += [text, len(text)]
                now = time.time()
                sets += ["version=version+1", "updated=?"]
                args.append(now)
                c.execute(f"UPDATE projects SET {', '.join(sets)} WHERE id=? AND user_id=?", (*args, pid, user_id))
                ver = c.execute("SELECT version FROM projects WHERE id=?", (pid,)).fetchone()
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
        return {"id": pid, "version": ver["version"], "updated": now}

    def duplicate_project(self, user_id, pid, name_ct):
        p = self.get_project(user_id, pid)
        return self.create_project(user_id, name_ct, p["data"])

    def delete_project(self, user_id, pid):
        with self.conn() as c:
            cur = c.execute("DELETE FROM projects WHERE id=? AND user_id=?", (pid, user_id))
        if cur.rowcount == 0:
            raise StoreError("Project not found.", 404)

    # ------------------------------------------------------------------ sharing (end-to-end encrypted)
    # Each user has an ECDH P-256 key pair made in the browser. The server keeps the public key
    # and the PRIVATE key encrypted with the user's data key (it cannot use it). A share is a copy
    # of a project encrypted for one recipient; the server stores and forwards only ciphertext.
    def sharing_enabled(self):
        return self.setting("allow_sharing", "1") == "1"

    @staticmethod
    def _valid_pub(pub):
        return _valid_b64(pub, 80, 200)       # SubjectPublicKeyInfo of a P-256 key (91 bytes)

    @staticmethod
    def _valid_ct_json(s, max_len=4000):
        if not isinstance(s, str) or len(s) > max_len:
            return False
        try:
            d = json.loads(s)
        except ValueError:
            return False
        return isinstance(d, dict) and _valid_b64(d.get("iv"), 12, 40) and _valid_b64(d.get("ct"), 16, max_len)

    def set_share_keys(self, user_id, pub, priv):
        if not self._valid_pub(pub) or not self._valid_ct_json(priv, 2000):
            raise StoreError("Invalid sharing keys.")
        with self.conn() as c:
            c.execute("UPDATE users SET share_pub=?, share_priv=? WHERE id=?", (pub, priv, user_id))

    def get_share_keys(self, user_id):
        with self.conn() as c:
            row = c.execute("SELECT share_pub, share_priv FROM users WHERE id=?", (user_id,)).fetchone()
        return {"pub": row["share_pub"], "priv": row["share_priv"]} if row else {"pub": None, "priv": None}

    def public_key(self, username):
        if not self.sharing_enabled():
            raise StoreError("Sharing is turned off on this server.", 403)
        with self.conn() as c:
            row = c.execute("SELECT username, share_pub FROM users WHERE username=? AND disabled=0", (str(username or "")[:64],)).fetchone()
        if not row or not row["share_pub"]:
            raise StoreError("No user with this name can receive shared projects yet (they need to sign in once).", 404)
        return {"username": row["username"], "pub": row["share_pub"]}

    def create_share(self, from_id, to_username, env):
        if not self.sharing_enabled():
            raise StoreError("Sharing is turned off on this server.", 403)
        if not isinstance(env, dict):
            raise StoreError("Malformed share.")
        ok = (self._valid_pub(env.get("eph")) and _valid_b64(env.get("salt"), 16, 64) and self._valid_ct_json(env.get("wrapped"), 400)
              and self._valid_ct_json(env.get("name_ct"), MAX_NAME_CT) and (env.get("note_ct") in (None, "") or self._valid_ct_json(env.get("note_ct"), 4000)))
        if not ok:
            raise StoreError("Shares must be end-to-end encrypted by the browser.")
        data_text = self._serialize(env.get("data"))  # same rules as projects: ciphertext envelope only
        envelope = json.dumps({"eph": env["eph"], "salt": env["salt"], "wrapped": env["wrapped"], "name_ct": env["name_ct"],
                               "note_ct": env.get("note_ct") or "", "data": json.loads(data_text)}, separators=(",", ":"))
        size = len(envelope)
        with self.conn() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                to = c.execute("SELECT id, share_pub FROM users WHERE username=? AND disabled=0", (str(to_username or "")[:64],)).fetchone()
                if not to or not to["share_pub"]:
                    raise StoreError("This user cannot receive shared projects.", 404)
                if to["id"] == from_id:
                    raise StoreError("You cannot share a project with yourself.")
                if env.get("recipientPub") not in (None, to["share_pub"]):
                    raise StoreError("The recipient's key changed while you were sharing. Please try again.", 409)
                _, max_project = self._quota(c, from_id)
                if size > max_project + 64 * 1024:
                    raise StoreError(f"Shared projects are limited to {max_project // MB} MB.", 413)
                n_in, s_in = c.execute("SELECT COUNT(*), COALESCE(SUM(size),0) FROM shares WHERE to_user=?", (to["id"],)).fetchone()
                n_out = c.execute("SELECT COUNT(*) FROM shares WHERE from_user=?", (from_id,)).fetchone()[0]
                if n_in >= MAX_SHARES_IN or s_in + size > MAX_SHARE_BYTES_IN:
                    raise StoreError("The recipient's inbox for shared projects is full.", 413)
                if n_out >= MAX_SHARES_OUT:
                    raise StoreError(f"You have {MAX_SHARES_OUT} shares waiting to be accepted. Withdraw some first.", 413)
                sid = secrets.token_hex(16)
                c.execute("INSERT INTO shares(id, from_user, to_user, envelope, size, created) VALUES(?,?,?,?,?,?)",
                          (sid, from_id, to["id"], envelope, size, time.time()))
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
        return {"id": sid, "size": size}

    def list_shares(self, user_id, box):
        col, other = ("to_user", "from_user") if box == "inbox" else ("from_user", "to_user")
        with self.conn() as c:
            rows = c.execute(f"SELECT s.id, s.size, s.created, s.envelope, u.username AS other FROM shares s JOIN users u ON u.id = s.{other} "
                             f"WHERE s.{col}=? ORDER BY s.created DESC", (user_id,)).fetchall()
        out = []
        for r in rows:
            env = json.loads(r["envelope"])
            item = {"id": r["id"], "size": r["size"], "created": r["created"], ("from" if box == "inbox" else "to"): r["other"]}
            if box == "inbox":  # what the recipient needs to decrypt the name and note (not the data)
                item.update({"eph": env["eph"], "salt": env["salt"], "wrapped": env["wrapped"], "name_ct": env["name_ct"], "note_ct": env.get("note_ct", "")})
            out.append(item)
        return out

    def get_share(self, user_id, sid):
        with self.conn() as c:
            row = c.execute("SELECT s.envelope, u.username AS sender FROM shares s JOIN users u ON u.id=s.from_user "
                            "WHERE s.id=? AND s.to_user=?", (str(sid)[:64], user_id)).fetchone()
        if not row:
            raise StoreError("Shared project not found.", 404)
        return {**json.loads(row["envelope"]), "from": row["sender"]}

    def delete_share(self, user_id, sid):
        with self.conn() as c:
            cur = c.execute("DELETE FROM shares WHERE id=? AND (to_user=? OR from_user=?)", (str(sid)[:64], user_id, user_id))
        if cur.rowcount == 0:
            raise StoreError("Shared project not found.", 404)

    # ------------------------------------------------------------------ admin
    def log(self, admin, action, target=""):
        with self.conn() as c:
            c.execute("INSERT INTO admin_log(ts, admin, action, target) VALUES(?,?,?,?)",
                      (time.time(), admin, action, str(target)[:200]))

    def admin_overview(self):
        with self.conn() as c:
            users = c.execute(
                "SELECT u.id, u.username, u.created, u.last_login, u.disabled, u.must_change, u.key_state, u.limits, "
                "COUNT(p.id) AS projects, COALESCE(SUM(p.size),0) AS usage, "
                "(SELECT COUNT(*) FROM sessions s WHERE s.user_id=u.id) AS sessions "
                "FROM users u LEFT JOIN projects p ON p.user_id=u.id GROUP BY u.id ORDER BY u.username COLLATE NOCASE").fetchall()
            reqs = c.execute("SELECT id, username, user_id, note, created FROM reset_requests WHERE status='open' "
                             "ORDER BY created DESC LIMIT 200").fetchall()
            log = c.execute("SELECT ts, admin, action, target FROM admin_log ORDER BY id DESC LIMIT 200").fetchall()
        out = []
        for u in users:
            d = dict(u)
            d["limits"] = self.limits_from(u["limits"])
            d["disabled"], d["must_change"] = bool(u["disabled"]), bool(u["must_change"])
            out.append(d)
        try:
            db_size = self.path.stat().st_size
        except OSError:
            db_size = 0
        return {"users": out, "requests": [dict(r) for r in reqs], "log": [dict(r) for r in log],
                "defaults": self.default_limits(), "bounds": LIMIT_BOUNDS, "dbSize": db_size,
                "totalUsage": sum(u["usage"] for u in out), "allowRegistration": self.registration_open(),
                "allowSharing": self.sharing_enabled(), "pendingShares": self._count_shares(),
                "announcement": self.announcement(),
                "admins": self.list_admins()}

    def _count_shares(self):
        with self.conn() as c:
            return c.execute("SELECT COUNT(*) FROM shares").fetchone()[0]

    def _user_row(self, c, user_id):
        row = c.execute("SELECT id, username FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            raise StoreError("No such user.", 404)
        return row

    def admin_update_user(self, user_id, limits=None, disabled=None):
        with self.conn() as c:
            row = self._user_row(c, user_id)
            if limits is not None:
                if not isinstance(limits, dict):
                    raise StoreError("Invalid limits.")
                clean = {}
                for k, v in limits.items():
                    if k not in LIMIT_BOUNDS:
                        continue
                    try:
                        v = int(v)
                    except (TypeError, ValueError):
                        raise StoreError(f"Invalid value for {k}.") from None
                    lo, hi = LIMIT_BOUNDS[k]
                    if not lo <= v <= hi:
                        raise StoreError(f"{k} must be between {lo} and {hi}.")
                    clean[k] = v
                c.execute("UPDATE users SET limits=? WHERE id=?", (json.dumps({**self.limits_from(None), **clean}), user_id))
            if disabled is not None:
                c.execute("UPDATE users SET disabled=? WHERE id=?", (int(bool(disabled)), user_id))
                if disabled:
                    c.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        return row["username"]

    def admin_delete_user(self, user_id):
        with self.conn() as c:
            row = self._user_row(c, user_id)
            c.execute("DELETE FROM users WHERE id=?", (user_id,))
        return row["username"]

    def admin_create_user(self, username, otp):
        """Create an account with an administrator-chosen one-time password. The user's
        encryption keys are created by their browser at the first sign-in."""
        self.validate_username(username)
        self.validate_password(otp, username)
        salt = b64(secrets.token_bytes(16))
        auth = derive_auth_key(otp, salt)
        now = time.time()
        with self.conn() as c:
            if c.execute("SELECT 1 FROM admins WHERE username=?", (username,)).fetchone():
                raise StoreError("This user ID is already taken.", 409)
            try:
                cur = c.execute(
                    "INSERT INTO users(username, pw_hash, kdf_salt, kdf_iter, key_state, created, pw_changed, must_change, limits) "
                    "VALUES(?,?,?,?,'none',?,?,1,?)",
                    (username, generate_password_hash(auth, method="scrypt"), salt, KDF_ITER, now, now,
                     json.dumps(self.default_limits())))
            except sqlite3.IntegrityError:
                raise StoreError("This user ID is already taken.", 409) from None
        return cur.lastrowid

    def admin_set_otp(self, user_id, otp):
        """Replace the user's password with a one-time password. This restores sign-in only:
        the data key stays wrapped with the old password; the user needs the recovery key."""
        with self.conn() as c:
            row = self._user_row(c, user_id)
        self.validate_password(otp, row["username"])
        salt = b64(secrets.token_bytes(16))
        auth = derive_auth_key(otp, salt)
        with self.conn() as c:
            c.execute("UPDATE users SET pw_hash=?, kdf_salt=?, kdf_iter=?, pw_changed=?, must_change=1, disabled=0, "
                      "key_state=CASE WHEN key_state='none' THEN 'none' ELSE 'reset' END WHERE id=?",
                      (generate_password_hash(auth, method="scrypt"), salt, KDF_ITER, time.time(), user_id))
            c.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
            c.execute("UPDATE reset_requests SET status='done' WHERE user_id=? AND status='open'", (user_id,))
            c.execute("DELETE FROM throttle WHERE key=?", (f"user:{row['username'].lower()}",))
        return row["username"]

    def request_reset(self, username, note, ip):
        if not isinstance(username, str) or not USERNAME_RE.match(username):
            return
        note = re.sub(r"[\x00-\x1f\x7f]", " ", str(note or ""))[:300]
        with self.conn() as c:
            row = c.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
            if not row:
                return
            if c.execute("SELECT id FROM reset_requests WHERE user_id=? AND status='open'", (row["id"],)).fetchone():
                return
            c.execute("INSERT INTO reset_requests(username, user_id, note, ip, created) VALUES(?,?,?,?,?)",
                      (username, row["id"], note, ip, time.time()))

    def dismiss_request(self, req_id):
        with self.conn() as c:
            c.execute("UPDATE reset_requests SET status='dismissed' WHERE id=?", (req_id,))
