"""Two Flask applications sharing one database:

* ``create_app()``       — the user application (main port, may listen on 0.0.0.0).
* ``create_admin_app()`` — the administration console (separate port, bound to
  127.0.0.1 and refusing any request that is not from the local machine).

Until an administrator has completed the first-run setup on the admin console,
the user application refuses all API access.

Security summary (details in SECURITY.md): end-to-end encrypted projects (the
server never receives passwords or keys), hashed session tokens in HttpOnly
SameSite=Strict cookies, CSRF header + Origin checks, throttled sign-in,
strict Content-Security-Policy, per-user quotas and OS-enforced RAM/CPU limits
for every computation.
"""
from __future__ import annotations

import functools
import json
import io
import ipaddress
import os
import re
import threading
import time
import traceback
from collections import defaultdict, deque
from pathlib import Path

from flask import Response, Flask, g, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from . import __version__
from .sandbox import LimitError, last_stats, run_limited
from .stats import AnalysisError, catalog, run
from .stats.graphdata import graph_data
from .stats.multivariate import power
from .store import Store, StoreError
from .tables import make_table, parse_table

HERE = Path(__file__).resolve().parent
COOKIE = "op_session"
ADMIN_COOKIE = "op_admin"
MAX_TABLE_CELLS = 2_000_000
MAX_DATASETS = 2000
MAX_CONCURRENT_PER_USER = 4

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
       "font-src 'self' data:; connect-src 'self' data: blob:; worker-src 'self' blob:; frame-src 'self'; "
       "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'self'")


# ------------------------------------------------------------------ helpers
def analysis_job(table: dict, key: str, params: dict) -> dict:
    """Parse + analyze (runs entirely inside the resource sandbox)."""
    return run(key, parse_table(table), params)


def vector_job(svg: str, fmt: str, title: str, gray: bool = False, transparent: bool = False):
    """SVG -> EPS / EMF (runs inside the resource sandbox)."""
    from .vector import convert
    data, mime, ext = convert(svg, fmt, title, gray=gray, background=not transparent)
    return {"data": data, "mime": mime, "ext": ext}


def graph_job(table: dict, err: str) -> dict:
    return graph_data(parse_table(table), err)


def parse_upload(raw: bytes, filename: str, ttype: str, has_header: bool) -> dict:
    """Parse an uploaded CSV/Excel file into a table (runs inside the resource sandbox)."""
    import pandas as pd

    name = Path(filename).stem[:100] or "Imported"
    if filename.lower().endswith(".pzfx"):
        from .pzfx import read
        try:
            tables, warnings = read(raw)
        except ValueError as e:
            raise AnalysisError(str(e)) from None
        return {"tables": tables, "warnings": warnings}
    try:
        if filename.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(raw), header=0 if has_header else None, nrows=200_000)
        else:
            text = raw.decode("utf-8-sig", errors="replace")
            sep = "\t" if text.count("\t") > text.count(",") else ","
            df = pd.read_csv(io.StringIO(text), sep=sep, header=0 if has_header else None, nrows=200_000)
    except Exception:  # noqa: BLE001
        raise AnalysisError("Could not read the file. Is it a valid CSV or Excel file?") from None
    if df.shape[1] > MAX_DATASETS or df.size > MAX_TABLE_CELLS:
        raise AnalysisError("The file has too many columns or cells.")
    cols = [str(c)[:100] for c in df.columns]
    values = df.astype(object).where(df.notna(), None).values.tolist()
    if ttype in ("xy", "survival"):
        return make_table(name, ttype, [{"name": c, "reps": 1} for c in cols[1:]], [r[1:] for r in values],
                          x=[r[0] for r in values], x_title=cols[0] if has_header else "X")
    if ttype == "multi":
        return make_table(name, "multi", [{"name": c, "reps": 1} for c in cols], values)
    if ttype == "summary":  # columns: group, mean, SD (or SEM), n
        if len(cols) < 4:
            raise AnalysisError("A summary-data file needs four columns: group, mean, SD (or SEM), n.")
        return make_table(name, "summary", [{"name": "Mean", "reps": 1}, {"name": "SEM" if "SE" in cols[2].upper() else "SD", "reps": 1}, {"name": "N", "reps": 1}],
                          [r[1:4] for r in values], row_labels=[str(r[0])[:200] if r[0] is not None else "" for r in values])
    if ttype in ("grouped", "contingency", "parts"):
        return make_table(name, ttype, [{"name": c, "reps": 1} for c in cols[1:]], [r[1:] for r in values],
                          row_labels=[str(r[0])[:200] if r[0] is not None else "" for r in values])
    return make_table(name, "column", [{"name": c, "reps": 1} for c in cols], values)


def inspect_upload(raw: bytes, filename: str) -> dict:
    """Recognise the layout of a CSV/Excel file and propose table types (runs inside the sandbox)."""
    from .detect import inspect
    if filename.lower().endswith(".pzfx"):
        return {"pzfx": True, "options": []}
    try:
        return inspect(raw, filename)
    except ValueError as e:
        raise AnalysisError(str(e)) from None
    except Exception:  # noqa: BLE001
        raise AnalysisError("Could not read the file. Is it a valid CSV or Excel file?") from None


def build_upload(raw: bytes, filename: str, option: dict) -> dict:
    """Create the data table for the import option the user chose."""
    from .detect import build, read_frame
    try:
        df = read_frame(raw, filename)
    except Exception:  # noqa: BLE001
        raise AnalysisError("Could not read the file. Is it a valid CSV or Excel file?") from None
    if df.shape[1] > MAX_DATASETS or df.size > MAX_TABLE_CELLS:
        raise AnalysisError("The file has too many columns or cells.")
    mapping = option.get("mapping") or {}
    if not isinstance(mapping, dict) or any(v is not None and v not in df.columns for v in mapping.values()):
        raise AnalysisError("The chosen columns are not in this file.")
    if option.get("type") not in ("xy", "column", "grouped", "contingency", "survival", "parts", "multi", "summary"):
        raise AnalysisError("Unknown table type.")
    if option.get("layout") not in ("wide", "long", "bygroup", "summary"):
        raise AnalysisError("Unknown layout.")
    name = Path(filename).stem[:100] or "Imported"
    try:
        table, warnings = build(df, name, {"type": option["type"], "layout": option["layout"], "mapping": mapping})
    except (KeyError, ValueError, IndexError):
        raise AnalysisError("These data cannot be arranged this way; choose another option.") from None
    return {**table, "warnings": warnings}


def _env_flag(name, default):
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


def _data_dir(data_dir):
    d = Path(data_dir or os.environ.get("OPENPRISM_DATA") or os.environ.get("OPENPRISM_PROJECTS")
             or HERE.parent / "projects").resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


class BusyError(LimitError):
    """Rate or concurrency limit: the same request may simply be retried a moment later."""


class UserGate:
    """Per-user request rate (sliding minute) and concurrency limits for computations."""

    def __init__(self):
        self.lock = threading.Lock()
        self.hits = defaultdict(deque)
        self.running = defaultdict(int)

    def enter(self, user_id, per_min):
        now = time.time()
        with self.lock:
            q = self.hits[user_id]
            while q and q[0] < now - 60:
                q.popleft()
            if len(q) >= per_min:
                raise BusyError("Too many calculations per minute for your account. Please wait a moment.")
            if self.running[user_id] >= MAX_CONCURRENT_PER_USER:
                raise BusyError("You already have calculations running. Please wait for them to finish.")
            q.append(now)
            self.running[user_id] += 1

    def leave(self, user_id):
        with self.lock:
            self.running[user_id] = max(0, self.running[user_id] - 1)


def _common(app, csrf_header):
    """Security headers, CSRF guard and JSON error handling shared by both apps."""

    @app.after_request
    def _headers(resp):
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "SAMEORIGIN"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        resp.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        if request.is_secure:
            resp.headers["Strict-Transport-Security"] = "max-age=31536000"
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
            st = getattr(g, "compute_stats", None)
            if st:  # lets the browser's activity log show how much server work each request took
                resp.headers["X-OpenPrism-Compute"] = f"wall={st['wall']:.4f};cpu={st['cpu']:.4f}" + (f";peak={st['peakMb']:.0f}" if st.get("peakMb") else "")
        return resp

    def csrf_check():
        if request.path.startswith("/api/") and request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.headers.get(csrf_header) != "1":
                return jsonify({"error": "Missing request header."}), 403
            origin = request.headers.get("Origin")
            if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
                return jsonify({"error": "Cross-origin request refused."}), 403
        return None

    @app.errorhandler(AnalysisError)
    def _analysis_error(e):
        return jsonify({"error": str(e)}), 400

    @app.errorhandler(LimitError)
    def _limit_error(e):
        resp = jsonify({"error": str(e), "limit": True})
        if isinstance(e, BusyError):
            resp.headers["Retry-After"] = "1"
            resp.headers["X-OpenPrism-Busy"] = "1"
        return resp, 429

    @app.errorhandler(StoreError)
    def _store_error(e):
        return jsonify({"error": str(e)}), e.status

    @app.errorhandler(HTTPException)
    def _http_error(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": e.description if e.code < 500 else "Server error."}), e.code
        return e

    @app.errorhandler(Exception)
    def _unhandled(e):  # never leak internals to the client
        app.logger.error("Unhandled error on %s: %s", request.path, traceback.format_exc(limit=5))
        return jsonify({"error": "Server error."}), 500

    return csrf_check


def body_json():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise StoreError("Expected a JSON object.")
    return data


# ===================================================================== users
from flask.json.provider import DefaultJSONProvider


class _FiniteJSON(DefaultJSONProvider):
    """Never emit NaN/Infinity (invalid JSON that makes browsers reject the whole response)."""

    def dumps(self, obj, **kw):
        from .stats import finite_json
        return super().dumps(finite_json(obj), **kw)


def create_app(data_dir: str | os.PathLike | None = None, secure_cookies: bool | None = None,
               trust_proxy: bool | None = None, store: Store | None = None) -> Flask:
    app = Flask(__name__, static_folder=str(HERE / "static"), static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024
    app.json = _FiniteJSON(app)
    store = store or Store(_data_dir(data_dir) / "openprism.db")
    app.config["STORE"] = store
    app.config["SECURE_COOKIES"] = _env_flag("OPENPRISM_SECURE_COOKIES", False) if secure_cookies is None else secure_cookies
    if _env_flag("OPENPRISM_TRUST_PROXY", False) if trust_proxy is None else trust_proxy:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    if _env_flag("OPENPRISM_PRELOAD", True):
        from .stats import preload
        preload()  # once per process: forked calculation workers then start with everything imported
    csrf_check = _common(app, "X-OpenPrism")
    gate = UserGate()
    PUBLIC = {"/api/health", "/api/status"}
    PW_CHANGE_ALLOWED = {"/api/auth/me", "/api/auth/password", "/api/auth/logout", "/api/auth/logout-all",
                         "/api/health", "/api/status"}

    @app.before_request
    def _guard():
        if request.path in ("/static/admin.html", "/static/js/adminapp.js"):
            return jsonify({"error": "Not found."}), 404
        blocked = csrf_check()
        if blocked:
            return blocked
        if request.path.startswith("/api/") and request.path not in PUBLIC and not store.is_setup():
            return jsonify({"error": "This server has not been set up yet. The administrator must complete the setup "
                                     "on the server's administration console.", "setup": False}), 503
        g.user_id, g.token_hash = store.session_user(request.cookies.get(COOKIE))
        g.user = store.get_user(g.user_id) if g.user_id else None
        if g.user and g.user["disabled"]:
            store.end_session(g.token_hash)
            g.user_id = g.user = None
        if g.user and g.user["must_change"] and request.path.startswith("/api/") and request.path not in PW_CHANGE_ALLOWED:
            return jsonify({"error": "You must set a new password first.", "mustChange": True}), 403
        return None

    def login_required(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            if not g.user_id:
                return jsonify({"error": "Please sign in.", "auth": False}), 401
            return fn(*a, **kw)
        return wrapper

    def compute(fn, *args):
        lim = g.user["limits"]
        gate.enter(g.user_id, lim["rate_per_min"])
        try:
            out = run_limited(fn, *args, mem_mb=lim["mem_mb"], cpu_s=lim["cpu_s"])
            st = last_stats()
            if st:
                g.compute_stats = st
            return out
        finally:
            gate.leave(g.user_id)

    def set_cookie(resp, token):
        resp.set_cookie(COOKIE, token, max_age=30 * 24 * 3600, httponly=True, samesite="Strict",
                        secure=app.config["SECURE_COOKIES"] or request.is_secure, path="/")
        return resp

    def user_payload(u):
        return {"auth": True, "username": u["username"], "created": u["created"], "mustChange": u["must_change"],
                "limits": u["limits"], "keys": store.key_material(u)}

    def check_table(t):
        if not isinstance(t, dict):
            raise AnalysisError("Invalid table.")
        cells = t.get("cells") or []
        ds = t.get("datasets") or []
        if not isinstance(cells, list) or not isinstance(ds, list) or len(ds) > MAX_DATASETS:
            raise AnalysisError("Invalid table.")
        try:
            width = sum(min(int(d.get("reps", 1) or 1), 1000) for d in ds if isinstance(d, dict))
        except (TypeError, ValueError):
            raise AnalysisError("Invalid table.") from None
        if len(cells) * max(width, 1) > MAX_TABLE_CELLS:
            raise AnalysisError("The table is too large to analyze.")
        return t

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": __version__}

    @app.get("/api/status")
    def status():
        return {"setup": store.is_setup(), "registration": store.registration_open(), "version": __version__,
                "announcement": store.announcement()}

    # ------------------------------------------------------------- auth
    @app.get("/api/auth/kdf")
    def kdf():
        """Key-derivation parameters for a user ID (fake but stable for unknown IDs)."""
        return store.kdf_params(request.args.get("username", "")[:64])

    @app.get("/api/auth/me")
    def me():
        if not g.user_id:
            return {"auth": False, "registration": store.registration_open()}
        return user_payload(g.user)

    @app.post("/api/auth/register")
    def register():
        if not store.registration_open():
            return jsonify({"error": "Self-registration is disabled on this server. Ask the administrator for an account."}), 403
        d = body_json()
        ip_key = f"reg:{request.remote_addr}"
        store.check_throttle([ip_key])
        uid = store.create_user(d.get("username"), d.get("auth"), d.get("salt"), d.get("wrappedKey"), d.get("recoveryKey"),
                                int(d.get("iter") or 0))
        store.record_failure([ip_key])  # rate-limits account creation per IP
        resp = jsonify(user_payload(store.get_user(uid)))
        return set_cookie(resp, store.new_session(uid))

    @app.post("/api/auth/login")
    def login():
        d = body_json()
        username = d.get("username") if isinstance(d.get("username"), str) else ""
        keys = [f"user:{username.lower()[:64]}", f"ip:{request.remote_addr}"]
        store.check_throttle(keys)
        uid = store.authenticate(username, d.get("auth"))
        if not uid:
            store.record_failure(keys)
            return jsonify({"error": "Incorrect user ID or password."}), 401
        store.clear_failures(keys[:1])
        resp = jsonify(user_payload(store.get_user(uid)))
        return set_cookie(resp, store.new_session(uid))

    @app.post("/api/auth/reset-request")
    def reset_request():
        d = body_json()
        key = [f"reset:{request.remote_addr}"]
        store.check_throttle(key)
        store.record_failure(key)
        store.request_reset(d.get("username"), d.get("note"), request.remote_addr)
        return {"ok": True, "message": "If this user ID exists, an administrator has been notified and will give you a one-time password."}

    @app.post("/api/auth/logout")
    def logout():
        if g.token_hash:
            store.end_session(g.token_hash)
        resp = jsonify({"auth": False})
        resp.delete_cookie(COOKIE, path="/")
        return resp

    @app.post("/api/auth/logout-all")
    @login_required
    def logout_all():
        store.end_all_sessions(g.user_id)
        resp = jsonify({"auth": False})
        resp.delete_cookie(COOKIE, path="/")
        return resp

    @app.post("/api/auth/password")
    @login_required
    def change_password():
        d = body_json()
        keys = [f"pw:{g.user_id}"]
        store.check_throttle(keys)
        try:
            store.set_credentials(g.user_id, d.get("oldAuth"), d.get("newAuth"), d.get("salt"), d.get("wrappedKey"),
                                  d.get("recoveryKey"), keep_token_hash=g.token_hash)
        except StoreError as e:
            if e.status == 403:
                store.record_failure(keys)
            raise
        store.clear_failures(keys)
        return user_payload(store.get_user(g.user_id))

    @app.post("/api/auth/recovery")
    @login_required
    def new_recovery():
        d = body_json()
        keys = [f"pw:{g.user_id}"]
        store.check_throttle(keys)
        try:
            store.set_recovery(g.user_id, d.get("auth"), d.get("recoveryKey"))
        except StoreError as e:
            if e.status == 403:
                store.record_failure(keys)
            raise
        return user_payload(store.get_user(g.user_id))

    @app.post("/api/auth/delete-account")
    @login_required
    def delete_account():
        d = body_json()
        keys = [f"pw:{g.user_id}"]
        store.check_throttle(keys)
        try:
            store.delete_user_self(g.user_id, d.get("auth"))
        except StoreError as e:
            if e.status == 403:
                store.record_failure(keys)
            raise
        resp = jsonify({"deleted": True})
        resp.delete_cookie(COOKIE, path="/")
        return resp

    # --------------------------------------------------------- projects
    @app.get("/api/projects")
    @login_required
    def list_projects():
        return jsonify(store.list_projects(g.user_id))

    @app.post("/api/projects")
    @login_required
    def create_project():
        d = body_json()
        return jsonify(store.create_project(g.user_id, d.get("name"), d.get("data")))

    @app.get("/api/projects/<pid>")
    @login_required
    def get_project(pid):
        return jsonify(store.get_project(g.user_id, pid))

    @app.put("/api/projects/<pid>")
    @login_required
    def update_project(pid):
        d = body_json()
        return jsonify(store.update_project(g.user_id, pid, data=d.get("data"), name_ct=d.get("name"),
                                            base_version=d.get("baseVersion"), force=bool(d.get("force"))))

    @app.post("/api/projects/<pid>/duplicate")
    @login_required
    def duplicate_project(pid):
        return jsonify(store.duplicate_project(g.user_id, pid, body_json().get("name")))

    @app.delete("/api/projects/<pid>")
    @login_required
    def delete_project(pid):
        store.delete_project(g.user_id, pid)
        return {"deleted": True}

    # --------------------------------------------------------- analysis
    @app.get("/api/catalog")
    @login_required
    def api_catalog():
        return catalog()

    # ---------------------------------------------------------------- sharing (end-to-end encrypted copies)
    @app.get("/api/sharing/keys")
    @login_required
    def sharing_keys():
        return {**store.get_share_keys(g.user_id), "enabled": store.sharing_enabled()}

    @app.put("/api/sharing/keys")
    @login_required
    def sharing_set_keys():
        d = body_json()
        store.set_share_keys(g.user_id, d.get("pub"), d.get("priv"))
        return {"ok": True}

    @app.get("/api/sharing/pubkey")
    @login_required
    def sharing_pubkey():
        gate.enter(g.user_id, 30)  # rate-limited: looking up colleagues' keys is a rare action
        gate.leave(g.user_id)
        return store.public_key(request.args.get("username", ""))

    @app.post("/api/sharing/send")
    @login_required
    def sharing_send():
        d = body_json()
        return store.create_share(g.user_id, d.get("to"), d.get("share"))

    @app.get("/api/sharing/inbox")
    @login_required
    def sharing_inbox():
        return {"shares": store.list_shares(g.user_id, "inbox"), "enabled": store.sharing_enabled()}

    @app.get("/api/sharing/sent")
    @login_required
    def sharing_sent():
        return {"shares": store.list_shares(g.user_id, "sent")}

    @app.get("/api/sharing/<sid>")
    @login_required
    def sharing_get(sid):
        return store.get_share(g.user_id, sid)

    @app.delete("/api/sharing/<sid>")
    @login_required
    def sharing_delete(sid):
        store.delete_share(g.user_id, sid)
        return {"ok": True}

    @app.post("/api/convert")
    @login_required
    def api_convert():
        """Vector conversion of a graph or layout (SVG drawn by the browser) to EPS or EMF.
        Nothing is stored: the file goes straight back to the user."""
        body = body_json()
        svg, fmt = body.get("svg"), body.get("format")
        if not isinstance(svg, str) or fmt not in ("eps", "emf") or len(svg) > 20 * 1024 * 1024:
            raise AnalysisError("Invalid conversion request.")
        title = str(body.get("title") or "OpenPrism figure")[:120]
        try:
            out = compute(vector_job, svg, fmt, title, bool(body.get("gray")), bool(body.get("transparent")))
        except (AnalysisError, LimitError):
            raise
        except Exception:  # noqa: BLE001
            raise AnalysisError("This drawing could not be converted.") from None
        resp = Response(out["data"], mimetype=out["mime"])
        resp.headers["Content-Disposition"] = f'attachment; filename="figure.{out["ext"]}"'
        return resp

    @app.post("/api/analyze")
    @login_required
    def api_analyze():
        body = body_json()
        try:
            table = check_table(body.get("table"))
            params = body.get("params") or {}
            if not isinstance(params, dict):
                raise AnalysisError("Invalid parameters.")
            return jsonify(compute(analysis_job, table, str(body.get("analysis")), params))
        except (AnalysisError, LimitError):
            raise
        except Exception:  # noqa: BLE001
            app.logger.error("Analysis error: %s", traceback.format_exc(limit=3))
            return jsonify({"error": "The analysis failed for these data. Check the values and options."}), 400

    @app.post("/api/graphdata")
    @login_required
    def api_graphdata():
        body = body_json()
        table = check_table(body.get("table"))
        err = body.get("error", "sem")
        return jsonify(compute(graph_job, table, err if isinstance(err, str) else "sem"))

    @app.post("/api/power")
    @login_required
    def api_power():
        return jsonify(compute(power, body_json()))

    @app.post("/api/import")
    @login_required
    def api_import():
        f = request.files.get("file")
        if f is None:
            return jsonify({"error": "No file uploaded"}), 400
        if request.form.get("inspect") == "1" or request.form.get("option"):
            raw = f.read(30 * 1024 * 1024 + 1)
            if len(raw) > 30 * 1024 * 1024:
                return jsonify({"error": "File is too large (max 30 MB)."}), 413
            if request.form.get("inspect") == "1":
                return jsonify(compute(inspect_upload, raw, f.filename or "Imported"))
            try:
                option = json.loads(request.form.get("option") or "{}")
            except ValueError:
                raise AnalysisError("Invalid import option.") from None
            if not isinstance(option, dict):
                raise AnalysisError("Invalid import option.")
            return jsonify(compute(build_upload, raw, f.filename or "Imported", option))
        ttype = request.form.get("type", "column")
        if ttype not in ("xy", "column", "grouped", "contingency", "survival", "parts", "multi", "nested", "summary"):
            ttype = "column"
        has_header = request.form.get("header", "1") == "1"
        raw = f.read(30 * 1024 * 1024 + 1)
        if len(raw) > 30 * 1024 * 1024:
            return jsonify({"error": "File is too large (max 30 MB)."}), 413
        return jsonify(compute(parse_upload, raw, f.filename or "Imported", ttype, has_header))

    @app.post("/api/export/pzfx")
    @login_required
    def api_export_pzfx():
        """Data tables → GraphPad Prism XML (.pzfx). Nothing is stored."""
        body = body_json()
        tables = body.get("tables")
        if not isinstance(tables, list) or not tables or len(tables) > 500:
            raise AnalysisError("No tables to export.")
        for t in tables:
            check_table(t)
        from .pzfx import write
        data = compute(write, tables, str(body.get("name") or "OpenPrism project")[:200])
        resp = Response(data, mimetype="application/xml")
        resp.headers["Content-Disposition"] = 'attachment; filename="project.pzfx"'
        return resp

    return app


# ===================================================================== admin
def _is_loopback(addr):
    try:
        return ipaddress.ip_address((addr or "").split("%")[0]).is_loopback
    except ValueError:
        return False


def create_admin_app(data_dir: str | os.PathLike | None = None, store: Store | None = None, port: int | None = None) -> Flask:
    """Administration console. Answers only requests from the local machine
    (loopback address *and* a localhost Host header, against DNS rebinding)."""
    app = Flask(__name__ + ".admin", static_folder=str(HERE / "static"), static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
    store = store or Store(_data_dir(data_dir) / "openprism.db")
    app.config["STORE"] = store
    csrf_check = _common(app, "X-OpenPrism-Admin")
    allowed_hosts = {"localhost", "127.0.0.1", "[::1]", "::1"}

    @app.before_request
    def _local_only():
        m = re.match(r"^(\[[^\]]+\]|[^:]+)(:\d+)?$", request.host or "")
        host = m.group(1) if m else ""
        if not _is_loopback(request.remote_addr) or host.lower() not in allowed_hosts:
            return jsonify({"error": "The administration console is only available on the server itself (localhost)."}), 403
        blocked = csrf_check()
        if blocked:
            return blocked
        g.admin_id, g.admin_th = store.admin_session(request.cookies.get(ADMIN_COOKIE))
        g.admin = store.get_admin(g.admin_id) if g.admin_id else None
        return None

    def admin_required(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            if not g.admin:
                return jsonify({"error": "Administrator sign-in required.", "auth": False}), 401
            return fn(*a, **kw)
        return wrapper

    def set_cookie(resp, token):
        resp.set_cookie(ADMIN_COOKIE, token, max_age=2 * 3600, httponly=True, samesite="Strict", path="/")
        return resp

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "admin.html")

    @app.get("/api/setup/status")
    def setup_status():
        return {"setup": store.is_setup(), "auth": bool(g.admin), "username": g.admin["username"] if g.admin else None,
                "version": __version__}

    @app.post("/api/setup")
    def setup():
        d = body_json()
        store.setup(d.get("username"), d.get("password"), bool(d.get("allowRegistration", True)), d.get("limits") or {})
        aid = store.admin_authenticate(d.get("username"), d.get("password"))
        store.log(d.get("username"), "server setup", "")
        return set_cookie(jsonify({"ok": True}), store.new_admin_session(aid))

    @app.post("/api/admin/login")
    def admin_login():
        d = body_json()
        keys = [f"admin:{str(d.get('username', '')).lower()[:64]}"]
        store.check_throttle(keys)
        aid = store.admin_authenticate(d.get("username"), d.get("password"))
        if not aid:
            store.record_failure(keys)
            return jsonify({"error": "Incorrect administrator name or password."}), 401
        store.clear_failures(keys)
        store.log(d.get("username"), "sign in", "")
        return set_cookie(jsonify({"ok": True}), store.new_admin_session(aid))

    @app.post("/api/admin/logout")
    def admin_logout():
        if g.admin_th:
            store.end_admin_session(g.admin_th)
        resp = jsonify({"ok": True})
        resp.delete_cookie(ADMIN_COOKIE, path="/")
        return resp

    @app.post("/api/admin/password")
    @admin_required
    def admin_password():
        d = body_json()
        store.admin_change_password(g.admin_id, d.get("old"), d.get("new"))
        store.log(g.admin["username"], "changed own password", "")
        return {"ok": True}

    @app.get("/api/admin/overview")
    @admin_required
    def overview():
        return jsonify(store.admin_overview())

    @app.put("/api/admin/settings")
    @admin_required
    def settings():
        d = body_json()
        if "allowSharing" in d:
            store.set_setting("allow_sharing", "1" if d["allowSharing"] else "0")
            store.log(g.admin["username"], "sharing between users", "on" if d["allowSharing"] else "off")
        if isinstance(d.get("announcement"), dict):
            a = store.set_announcement(d["announcement"].get("text"), d["announcement"].get("level", "info"))
            store.log(g.admin["username"], "announcement", f"{a['level']}: {a['text'][:80]}" if a else "removed")
        if "allowRegistration" in d:
            store.set_setting("allow_registration", "1" if d["allowRegistration"] else "0")
            store.log(g.admin["username"], "self-registration", "on" if d["allowRegistration"] else "off")
        if isinstance(d.get("defaults"), dict):
            import json as _json
            store.set_setting("default_limits", _json.dumps(store._clamp_limits(d["defaults"])))
            store.log(g.admin["username"], "default limits", "")
        return {"ok": True}

    @app.post("/api/admin/users")
    @admin_required
    def create_user():
        d = body_json()
        uid = store.admin_create_user(d.get("username"), d.get("password"))
        store.log(g.admin["username"], "create user", d.get("username"))
        return {"id": uid}

    @app.put("/api/admin/users/<int:uid>")
    @admin_required
    def update_user(uid):
        d = body_json()
        name = store.admin_update_user(uid, limits=d.get("limits"), disabled=d.get("disabled"))
        store.log(g.admin["username"], "update user", f"{name}: {', '.join(d)}")
        return {"ok": True}

    @app.delete("/api/admin/users/<int:uid>")
    @admin_required
    def delete_user(uid):
        name = store.admin_delete_user(uid)
        store.log(g.admin["username"], "delete user", name)
        return {"ok": True}

    @app.post("/api/admin/users/<int:uid>/otp")
    @admin_required
    def set_otp(uid):
        d = body_json()
        name = store.admin_set_otp(uid, d.get("password"))
        store.log(g.admin["username"], "one-time password", name)
        return {"ok": True, "username": name}

    @app.post("/api/admin/requests/<int:rid>/dismiss")
    @admin_required
    def dismiss(rid):
        store.dismiss_request(rid)
        store.log(g.admin["username"], "dismiss reset request", rid)
        return {"ok": True}

    @app.get("/api/admin/backup")
    @admin_required
    def backup():
        import sqlite3
        import tempfile

        from flask import send_file
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        src = sqlite3.connect(store.path)
        dst = sqlite3.connect(tmp.name)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        store.log(g.admin["username"], "database backup", "")
        data = Path(tmp.name).read_bytes()
        os.unlink(tmp.name)
        return send_file(io.BytesIO(data), mimetype="application/octet-stream", as_attachment=True,
                         download_name=f"openprism-backup-{time.strftime('%Y%m%d-%H%M%S')}.db")

    @app.post("/api/admin/admins")
    @admin_required
    def add_admin():
        d = body_json()
        store.create_admin(d.get("username"), d.get("password"))
        store.log(g.admin["username"], "add administrator", d.get("username"))
        return {"ok": True}

    @app.delete("/api/admin/admins/<int:aid>")
    @admin_required
    def del_admin(aid):
        store.delete_admin(g.admin_id, aid)
        store.log(g.admin["username"], "delete administrator", aid)
        return {"ok": True}

    return app
