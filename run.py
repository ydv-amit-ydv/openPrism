#!/usr/bin/env python3
"""Start OpenPrism.

    python run.py
        Main application on https://0.0.0.0:5000 (reachable from the lab network)
        and the administration console on http://127.0.0.1:47219 (this machine only).
        On the first run, open the administration console to set up the server.

Options:
    --port 5000 --host 0.0.0.0        main application address
    --admin-port 47219                administration console port (always bound to 127.0.0.1)
    --http                            plain HTTP on the main port (only behind an HTTPS reverse proxy!)
    --cert FILE --key FILE            use your own TLS certificate instead of the self-signed one
    --desktop                         open the application in a native window (pip install pywebview)

Console administration (works even if the web console is unreachable):
    python run.py admin create  <name>   create an administrator (asks for a password)
    python run.py admin list             list administrators
    python run.py admin reset-admin <name>   set a new password for an administrator
"""
import argparse
import datetime
import getpass
import ipaddress
import os
import socket
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def data_dir(arg):
    d = Path(arg or os.environ.get("OPENPRISM_DATA") or os.environ.get("OPENPRISM_PROJECTS") or HERE / "projects").resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


def lan_addresses():
    addrs = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        addrs.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addrs.add(info[4][0])
    except OSError:
        pass
    return sorted(a for a in addrs if not a.startswith("127."))


def ensure_certificate(ddir: Path):
    """Create (once) a self-signed certificate valid for localhost, this host name and its LAN IPs.
    HTTPS is required by browsers for the end-to-end encryption (WebCrypto) to work on a network."""
    tls = ddir / "tls"
    cert, key = tls / "cert.pem", tls / "key.pem"
    if cert.exists() and key.exists():
        return str(cert), str(key)
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    tls.mkdir(parents=True, exist_ok=True)
    pkey = ec.generate_private_key(ec.SECP256R1())
    host = socket.gethostname()
    names = [x509.DNSName("localhost"), x509.DNSName(host), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
    for a in lan_addresses():
        names.append(x509.IPAddress(ipaddress.ip_address(a)))
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"OpenPrism on {host}")])
    now = datetime.datetime.now(datetime.timezone.utc)
    c = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(pkey.public_key())
         .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1))
         .not_valid_after(now + datetime.timedelta(days=3650))
         .add_extension(x509.SubjectAlternativeName(names), critical=False)
         .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
         .sign(pkey, hashes.SHA256()))
    key.write_bytes(pkey.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption()))
    os.chmod(key, 0o600)
    cert.write_bytes(c.public_bytes(serialization.Encoding.PEM))
    return str(cert), str(key)


def admin_cli(argv):
    ap = argparse.ArgumentParser(prog="run.py admin", description="Manage OpenPrism administrators")
    ap.add_argument("action", choices=["create", "list", "reset-admin"])
    ap.add_argument("username", nargs="?")
    a = ap.parse_args(argv)
    from openprism.store import Store, StoreError
    store = Store(data_dir(None) / "openprism.db")
    try:
        if a.action == "list":
            for ad in store.list_admins():
                print(ad["username"])
            return
        if not a.username:
            sys.exit("Give an administrator name.")
        pw = getpass.getpass("New administrator password: ")
        if pw != getpass.getpass("Repeat password: "):
            sys.exit("Passwords do not match.")
        if a.action == "create":
            if not store.is_setup():
                store.setup(a.username, pw)
            else:
                store.create_admin(a.username, pw)
            store.log("console", "create administrator", a.username)
            print(f"Administrator '{a.username}' created.")
        else:
            with store.conn() as c:
                row = c.execute("SELECT id FROM admins WHERE username=?", (a.username,)).fetchone()
            if not row:
                sys.exit("No such administrator.")
            store.validate_password(pw, a.username)
            from werkzeug.security import generate_password_hash
            with store.conn() as c:
                c.execute("UPDATE admins SET pw_hash=? WHERE id=?", (generate_password_hash(pw, method="scrypt"), row["id"]))
            store.log("console", "reset administrator password", a.username)
            print("Password changed.")
    except StoreError as e:
        sys.exit(str(e))


class AccessLog:
    """WSGI middleware: one line per request (no query strings, no bodies, no cookies)."""

    def __init__(self, app, logger):
        self.app, self.log = app, logger

    def __call__(self, environ, start_response):
        t0 = time.time()
        status_holder = {}

        def sr(status, headers, exc_info=None):
            status_holder["s"] = status.split(" ", 1)[0]
            return start_response(status, headers, exc_info)
        try:
            return self.app(environ, sr)
        finally:
            if not environ.get("PATH_INFO", "").startswith("/static/"):
                self.log.info("%s %s %s %s %.0fms", environ.get("REMOTE_ADDR", "-"), environ.get("REQUEST_METHOD"),
                              environ.get("PATH_INFO", ""), status_holder.get("s", "-"), (time.time() - t0) * 1000)


def setup_logging(ddir: Path):
    import logging
    from logging.handlers import RotatingFileHandler
    logs = ddir / "logs"
    logs.mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fh = RotatingFileHandler(logs / "openprism.log", maxBytes=10 * 1024 * 1024, backupCount=10)
    fh.setFormatter(fmt)
    root.addHandler(fh)
    return logging.getLogger("openprism.access")


def _redirecting_adapter(cert, key, port):
    """TLS adapter that answers a plain http:// request with a redirect to https:// instead of
    silently dropping the connection (which looks to the user as if the server were blocked)."""
    import socket
    from cheroot import errors
    from cheroot.ssl.builtin import BuiltinSSLAdapter

    class Adapter(BuiltinSSLAdapter):
        def wrap(self, sock):
            try:
                old = sock.gettimeout()
                sock.settimeout(10)
                first = sock.recv(1, socket.MSG_PEEK)
                sock.settimeout(old)
            except OSError:
                first = b""
            if first and first[0] != 0x16:            # not a TLS ClientHello: plain HTTP
                try:
                    sock.settimeout(5)
                    head = b""
                    while b"\r\n\r\n" not in head and len(head) < 16384:
                        chunk = sock.recv(4096)
                        if not chunk:
                            break
                        head += chunk
                    lines = head.decode("latin-1", "replace").split("\r\n")
                    parts = lines[0].split(" ")
                    path = parts[1] if len(parts) > 1 and parts[1].startswith("/") else "/"
                    host = next((ln.split(":", 1)[1].strip() for ln in lines[1:] if ln.lower().startswith("host:")), "")
                    host = host.rsplit(":", 1)[0] if host and not host.endswith("]") else host
                    if not host or any(c in host for c in " /\\\r\n"):
                        host = "localhost"
                    loc = f"https://{host}:{port}{path}"
                    body = f"OpenPrism uses https. Continue at {loc}\n"
                    sock.sendall((f"HTTP/1.1 301 Moved Permanently\r\nLocation: {loc}\r\nContent-Type: text/plain\r\n"
                                  f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n{body}").encode("latin-1", "replace"))
                except OSError:
                    pass
                try:
                    sock.close()
                except OSError:
                    pass
                raise errors.FatalSSLAlert("plain http request redirected to https")
            return super().wrap(sock)

    return Adapter(cert, key)


def serve(app, host, port, ssl_context=None, name=""):
    """Production server: cheroot (multi-threaded, TLS); falls back to werkzeug."""
    try:
        from cheroot import wsgi
        srv = wsgi.Server((host, port), app, numthreads=int(os.environ.get("OPENPRISM_THREADS", 32)),
                          request_queue_size=128, timeout=180, server_name=f"openprism-{name}")
        if ssl_context:
            srv.ssl_adapter = _redirecting_adapter(ssl_context[0], ssl_context[1], port)
        srv.prepare()
        t = threading.Thread(target=srv.serve, name=name, daemon=True)
        t.start()
        srv.shutdown = srv.stop
        return srv
    except ImportError:
        from werkzeug.serving import make_server
        srv = make_server(host, port, app, threaded=True, ssl_context=ssl_context)
        threading.Thread(target=srv.serve_forever, name=name, daemon=True).start()
        return srv


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "admin":
        admin_cli(sys.argv[2:])
        return
    ap = argparse.ArgumentParser(description="OpenPrism scientific graphing & statistics server")
    ap.add_argument("--host", default=os.environ.get("OPENPRISM_HOST", "0.0.0.0"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("OPENPRISM_PORT", 5000)))
    ap.add_argument("--admin-port", type=int, default=int(os.environ.get("OPENPRISM_ADMIN_PORT", 47219)))
    ap.add_argument("--http", action="store_true", default=os.environ.get("OPENPRISM_HTTP") == "1",
                    help="serve plain HTTP on the main port (only behind an HTTPS reverse proxy)")
    ap.add_argument("--cert")
    ap.add_argument("--key")
    ap.add_argument("--desktop", action="store_true")
    a = ap.parse_args()

    from openprism.app import create_admin_app, create_app
    from openprism.store import Store

    ddir = data_dir(None)
    store = Store(ddir / "openprism.db")
    ssl_ctx = None
    if not a.http:
        ssl_ctx = (a.cert, a.key) if a.cert and a.key else ensure_certificate(ddir)
    app = create_app(store=store, secure_cookies=not a.http and None)
    admin = create_admin_app(store=store)

    access = setup_logging(ddir)
    try:
        main_srv = serve(AccessLog(app, access), a.host, a.port, ssl_ctx, "main")
    except OSError as e:
        hint = (" On macOS, port 5000 is used by AirPlay Receiver (System Settings → General → AirDrop & Handoff)."
                if a.port == 5000 and sys.platform == "darwin" else "")
        raise SystemExit(f"\n  Port {a.port} is already in use ({e}).{hint}\n"
                         f"  Start OpenPrism on another port, e.g.:  python run.py --port 8443\n")
    admin_srv = serve(AccessLog(admin, access), "127.0.0.1", a.admin_port, None, "admin")
    scheme = "http" if a.http else "https"
    urls = [f"{scheme}://localhost:{a.port}/"]
    if a.host in ("0.0.0.0", "::"):
        urls += [f"{scheme}://{ip}:{a.port}/" for ip in lan_addresses()]
    print("\n  OpenPrism", end="")
    try:
        from openprism import __version__
        print(f" {__version__}")
    except ImportError:
        print()
    print("  ─────────────────────────────────────────────────────────────")
    print("  Application (users):       " + "\n                             ".join(urls))
    print(f"  Administration (this computer only): http://127.0.0.1:{a.admin_port}/")
    print(f"  Data directory:            {ddir}   (logs in {ddir / 'logs'})")
    if not store.is_setup():
        print("\n  ► FIRST RUN: open the administration console above on this computer to")
        print("    create the administrator and configure the server. Users cannot sign in before that.")
    if ssl_ctx and len(urls) > 1:
        print("\n  Other devices on the same network: open one of the https:// addresses above")
        print("  (typing http:// also works, it is redirected). If they cannot connect at all, the")
        print("  computer's firewall is blocking Python for this port; see “Using it from other devices” in README.md.")
    if ssl_ctx and not (a.cert and a.key):
        print("\n  HTTPS uses a self-signed certificate: browsers will warn once; choose “Advanced → Proceed”.")
        print("  (Use --cert/--key for a real certificate.)")
    py = "python" if os.name == "nt" else "python3"
    print("\n  Server commands (stop this server with Ctrl+C first):")
    print(f"    {py} start.py --continue --continue --continue            restart with the same data folder")
    print(f"    {py} start.py --exportdata BACKUPPATH                     back up all data to BACKUPPATH")
    print(f"    {py} start.py --new --new --new --newserveruserdata USERPATH          new empty server in USERPATH")
    print(f"    {py} start.py --reset --reset --reset --loadolddata BACKUP --newserveruserdata USERPATH")
    print("                                                                  start in USERPATH with an old backup")
    print("  Press Ctrl+C to stop.\n")
    pidfile = ddir / "server.pid"
    try:
        import json as _json
        pidfile.write_text(_json.dumps({"pid": os.getpid(), "port": a.port}))
    except OSError:
        pidfile = None

    if a.desktop:
        try:
            import webview  # type: ignore
        except ImportError:
            raise SystemExit("Desktop mode needs pywebview:  pip install pywebview")
        webview.create_window("OpenPrism", urls[0], width=1440, height=900, min_size=(900, 600))
        webview.start()
        return
    import signal
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    try:
        while not stop.wait(3600):
            pass
    except KeyboardInterrupt:
        pass
    print("Stopping…")
    main_srv.shutdown()
    admin_srv.shutdown()
    if pidfile:
        try:
            pidfile.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
