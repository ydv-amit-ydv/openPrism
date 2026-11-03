#!/usr/bin/env python3
"""OpenPrism server launcher — needs only Python 3.10+.

    python3 start.py --new --new --new --newserveruserdata USERPATH
        Set up a NEW server that keeps its data (accounts, projects, settings, certificate, logs) in USERPATH.
        The first run also installs the Python packages into .venv/ next to this file.

    python3 start.py --continue --continue --continue
        Daily (re)start: start the server with the data folder chosen before (saved in openprism.conf).

    python3 start.py --exportdata BACKUPPATH
        Save all server data as a timestamped backup .zip in the folder BACKUPPATH (the server must be stopped).

    python3 start.py --reset --reset --reset --loadolddata BACKUP --newserveruserdata USERPATH
        Start the server with its data in USERPATH, filled from an old backup (BACKUP = a backup .zip or the
        folder holding it; the newest one is used). The backup is checked before anything is deleted.

Typical update:  --exportdata ~/backups  →  delete the old folder and clone the new version  →
                 --reset --reset --reset --loadolddata ~/backups --newserveruserdata ~/openprism-data
Repeating a flag three times is the confirmation. Without any flag this help and the saved data folder are shown.
Stop a running server (Ctrl+C) before --exportdata, --reset or --new. Other options go to the server, e.g. --port 8443.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV = HERE / ".venv"
REQ = HERE / "requirements.txt"
STAMP = VENV / ".requirements.sha256"
CONF = HERE / "openprism.conf"           # remembers the data folder (not in git)
MARK = ".openprism-data"                 # marks a folder as OpenPrism's own data folder
DATA = Path(os.environ.get("OPENPRISM_DATA") or HERE / "projects").resolve()
DB = DATA / "openprism.db"
PIDFILE = DATA / "server.pid"


def use_data(path: Path):
    global DATA, DB, PIDFILE
    DATA = Path(path).resolve()
    DB = DATA / "openprism.db"
    PIDFILE = DATA / "server.pid"
WIN = os.name == "nt"
EXPORT_FORMAT = "openprism-server-export-1"


def say(msg=""):
    print(msg, flush=True)


def fail(msg):
    sys.exit(f"\n  {msg}\n")


# ---------------------------------------------------------------- environment
def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if WIN else "bin/python")


def create_venv():
    say("  Creating a private Python environment in .venv/ …")
    try:
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    except subprocess.CalledProcessError:
        shutil.rmtree(VENV, ignore_errors=True)
        fail("Could not create the environment. On Debian/Ubuntu install the venv module first:\n"
             "      sudo apt install python3-venv\n  then run  python3 start.py  again.")


def install_requirements():
    want = hashlib.sha256(REQ.read_bytes()).hexdigest()
    if STAMP.exists() and STAMP.read_text().strip() == want:
        return
    say("  Installing the required packages (first run only, about a minute) …")
    py = str(venv_python())
    subprocess.run([py, "-m", "pip", "install", "--quiet", "--upgrade", "pip"], check=False)
    r = subprocess.run([py, "-m", "pip", "install", "--quiet", "-r", str(REQ)])
    if r.returncode != 0:
        fail("Installing the packages failed (see the messages above). Check the internet connection and run\n"
             "      python3 start.py\n  again.")
    STAMP.write_text(want)
    say("  Packages installed.")


# ---------------------------------------------------------------- safety checks
def running_server():
    """(pid, port) of a server using this data folder, or None. run.py writes the marker file."""
    try:
        info = json.loads(PIDFILE.read_text())
        pid = int(info["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    try:
        if WIN:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True).stdout
            alive = str(pid) in out
        else:
            os.kill(pid, 0)
            alive = True
    except (OSError, ProcessLookupError):
        alive = False
    if not alive:
        PIDFILE.unlink(missing_ok=True)
        return None
    return pid, info.get("port")


def require_stopped(action):
    r = running_server()
    if r:
        fail(f"The OpenPrism server is running (process {r[0]}, port {r[1]}). Stop it first (Ctrl+C in its window), then {action}.")


def data_files():
    return [p for p in DATA.iterdir() if p.name != ".gitkeep"] if DATA.exists() else []


def this_schema() -> int:
    """Database schema version this copy of the code understands (read from the source, no imports needed)."""
    import re
    try:
        m = re.search(r"^SCHEMA_VERSION\s*=\s*(\d+)", (HERE / "openprism" / "store.py").read_text(), re.M)
        return int(m.group(1)) if m else 0
    except OSError:
        return 0


def db_schema(db_path: Path) -> int | None:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT value FROM settings WHERE key = 'schema'").fetchone()
    except sqlite3.DatabaseError:
        return None
    finally:
        con.close()
    try:
        return int(row[0]) if row else None
    except (TypeError, ValueError):
        return None


def counts(db_path: Path):
    """(users, projects) in a database file, for messages and checks."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        users = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        projects = con.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        ok = con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()
    if ok != "ok":
        raise ValueError(f"database integrity check failed: {ok}")
    return users, projects


def copy_db(src: Path, dest: Path):
    """Consistent copy of a (possibly WAL-mode) SQLite database."""
    s = sqlite3.connect(str(src))
    try:
        d = sqlite3.connect(str(dest))
        with d:
            s.backup(d)
        d.close()
    finally:
        s.close()


# ---------------------------------------------------------------- export / import
def export(output: str | None) -> Path:
    if not output:
        fail("Say where to save the backup.")
    out = Path(output).expanduser().resolve()
    if out.is_dir():
        out = out / f"openprism-backup-{datetime.datetime.now():%Y%m%d-%H%M%S}.zip"
    if out.suffix.lower() != ".zip":
        out = out.with_suffix(out.suffix + ".zip") if out.suffix else out.with_suffix(".zip")
    if not DB.exists():
        fail(f"There is no server data to export in {DATA}.")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / "openprism.db"
        copy_db(DB, snap)
        users, projects = counts(snap)
        manifest = {"format": EXPORT_FORMAT, "created": datetime.datetime.now().isoformat(timespec="seconds"),
                    "openprism": _version(), "schema": db_schema(snap), "users": users, "projects": projects}
        part = out.with_name(out.name + ".part")
        with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifest.json", json.dumps(manifest, indent=2))
            z.write(snap, "openprism.db")
            tls = DATA / "tls"
            if tls.is_dir():
                for f in tls.iterdir():
                    if f.is_file():
                        z.write(f, f"tls/{f.name}")
        part.replace(out)
    try:
        os.chmod(out, 0o600)        # contains password hashes and the TLS key
    except OSError:
        pass
    verify_export(out)
    say(f"  Backed up {users} account(s) and {projects} project(s) to\n      {out}")
    return out


def verify_export(path: Path):
    with tempfile.TemporaryDirectory() as tmp:
        db = _extract_db(path, Path(tmp))
        counts(db)


def _extract_db(src: Path, tmp: Path) -> Path:
    """Database file from an export: .zip (OpenPrism export or any zip holding openprism.db), a .db file, or a folder."""
    if src.is_dir():
        cand = src / "openprism.db"
        if not cand.exists():
            fail(f"{src} does not contain openprism.db.")
        for sub in ("tls",):
            if (src / sub).is_dir():
                shutil.copytree(src / sub, tmp / sub)
        shutil.copy2(cand, tmp / "openprism.db")
        return tmp / "openprism.db"
    if zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as z:
            names = z.namelist()
            mf = next((n for n in names if n.rsplit("/", 1)[-1] == "manifest.json"), None)
            if mf:
                (tmp / "manifest.json").write_bytes(z.read(mf)[:100000])
            dbn = next((n for n in names if n.rsplit("/", 1)[-1] == "openprism.db"), None)
            if not dbn:
                fail(f"{src} is not an OpenPrism export (no openprism.db inside).")
            root = dbn[: -len("openprism.db")]
            for n in names:
                if not n.startswith(root) or n.endswith("/"):
                    continue
                rel = n[len(root):]
                if rel == "openprism.db" or rel.startswith("tls/"):
                    target = (tmp / rel).resolve()
                    if tmp.resolve() not in target.parents:
                        fail(f"{src} contains an unsafe path ({n}).")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(n) as fsrc, open(target, "wb") as fdst:
                        shutil.copyfileobj(fsrc, fdst)
        return tmp / "openprism.db"
    with open(src, "rb") as f:
        if f.read(16) == b"SQLite format 3\x00":
            shutil.copy2(src, tmp / "openprism.db")
            return tmp / "openprism.db"
    fail(f"{src} is not a .zip export, an openprism.db file or a folder containing one.")


def check_compatible(tmp: Path, db: Path, src: Path):
    """The import only works when this code understands the data format; refuse clearly otherwise."""
    manifest = {}
    if (tmp / "manifest.json").exists():
        try:
            manifest = json.loads((tmp / "manifest.json").read_text())
        except ValueError:
            fail(f"{src}: the manifest inside the export is damaged.")
        if manifest.get("format") != EXPORT_FORMAT:
            fail(f"{src} was made by a different, incompatible OpenPrism version (format “{manifest.get('format')}”;\n"
                 f"  this version reads “{EXPORT_FORMAT}”). Import it with the OpenPrism version that created it.")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    except sqlite3.DatabaseError as e:
        fail(f"{src} cannot be read: {e}.")
    finally:
        con.close()
    missing = {"settings", "users", "projects"} - tables
    if missing:
        fail(f"{src} is not an OpenPrism server database (missing: {', '.join(sorted(missing))}).")
    theirs, ours = db_schema(db), this_schema()
    if theirs is None:
        fail(f"{src} has no schema version, so it is not known whether this version can read it. Nothing was changed.")
    if ours and theirs > ours:
        fail(f"{src} was made by a newer OpenPrism (data schema {theirs}; this version understands up to {ours}).\n"
             "  Install the newer version first, then import. Nothing was changed.")
    return manifest, theirs, ours


def find_backup(path: str) -> Path:
    """A backup .zip, a database file, or a folder: a folder holding openprism.db, or the newest backup .zip in it."""
    src = Path(path).expanduser().resolve()
    if not src.exists():
        fail(f"{src} does not exist.")
    if src.is_dir() and not (src / "openprism.db").exists():
        zips = sorted(src.glob("openprism-backup-*.zip")) or sorted(src.glob("*.zip"), key=lambda p: p.stat().st_mtime)
        if not zips:
            fail(f"No backup (.zip) was found in {src}.")
        src = zips[-1]
    return src


def load_backup(src: Path, tmp: Path):
    """Open and check a backup without touching the current data. Returns (db, users, projects, manifest)."""
    db = _extract_db(src, tmp)
    manifest, theirs, ours = check_compatible(tmp, db, src)
    try:
        users, projects = counts(db)
    except (sqlite3.DatabaseError, ValueError) as e:
        fail(f"{src} cannot be loaded: {e}. Nothing was deleted.")
    say(f"  Backup {src}\n      {users} account(s), {projects} project(s)"
        + (f", saved {manifest.get('created')} by OpenPrism {manifest.get('openprism')}" if manifest else "")
        + f" — data format {theirs} (this version reads up to {ours}): OK")
    return db, users, projects


def install_backup(db: Path, tmp: Path):
    DATA.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db, DB)
    try:
        os.chmod(DB, 0o600)
    except OSError:
        pass
    if (tmp / "tls").is_dir():
        shutil.copytree(tmp / "tls", DATA / "tls", dirs_exist_ok=True)


# ---------------------------------------------------------------- data folder
def saved_data():
    """The data folder chosen with --new / --reset (openprism.conf); older installs used projects/."""
    try:
        return Path(json.loads(CONF.read_text())["data"]).resolve()
    except (OSError, ValueError, KeyError, TypeError):
        legacy = HERE / "projects"
        return legacy.resolve() if (legacy / "openprism.db").exists() else None


def save_data(path: Path):
    CONF.write_text(json.dumps({"data": str(path), "saved": datetime.datetime.now().isoformat(timespec="seconds")}, indent=2))


def is_openprism_folder(p: Path) -> bool:
    return (p / MARK).exists() or (p / "openprism.db").exists()


def prepare_folder(path: str) -> Path:
    """Check a data folder before it is used: safe location, OpenPrism's own or empty, readable and writable."""
    p = Path(path).expanduser().resolve()
    if p == HERE or p in HERE.parents:
        fail(f"{p} contains the OpenPrism program itself; choose a separate folder for the server data.")
    if p.exists() and not p.is_dir():
        fail(f"{p} is a file, not a folder.")
    if p.exists() and any(p.iterdir()) and not is_openprism_folder(p):
        fail(f"{p} already contains other files. Choose an empty folder (or a new one) for the server data —\n"
             "  OpenPrism only ever deletes a folder it created itself.")
    try:
        p.mkdir(parents=True, exist_ok=True)
        probe = p / ".write-test"
        probe.write_text("ok")
        ok = probe.read_text() == "ok"
        probe.unlink()
    except OSError as e:
        fail(f"The server cannot write to {p} ({e.strerror or e}). Choose a folder this user account may write to,\n"
             "  or give it permission first (e.g.  sudo chown -R $USER " + str(p) + "  on Linux).")
    if not ok:
        fail(f"Files written to {p} cannot be read back; choose another folder.")
    free = shutil.disk_usage(p).free
    if free < 200 * 1024 * 1024:
        fail(f"Only {free // (1024 * 1024)} MB are free at {p}; at least 200 MB are needed.")
    try:
        os.chmod(p, 0o700)               # only the server's user account may look inside
    except OSError:
        pass
    return p


def clear_folder(p: Path):
    for f in p.iterdir():
        shutil.rmtree(f) if f.is_dir() and not f.is_symlink() else f.unlink()
    (p / MARK).write_text(json.dumps({"created": datetime.datetime.now().isoformat(timespec="seconds"), "openprism": _version()}))


def require_stopped_at(paths, action):
    for d in {x for x in paths if x}:
        use_data(d)
        require_stopped(action)


# ---------------------------------------------------------------- main
def _version():
    try:
        txt = (HERE / "openprism" / "__init__.py").read_text()
        return txt.split('__version__ = "', 1)[1].split('"', 1)[0]
    except (OSError, IndexError):
        return "?"


def _value(args, flag):
    """Value after a flag (removed from args)."""
    if flag in args:
        i = args.index(flag)
        if i + 1 >= len(args) or args[i + 1].startswith("--"):
            fail(f"{flag} needs a path.")
        v = args[i + 1]
        del args[i:i + 2]
        return v
    return None


COMMANDS = """
      python3 start.py --new --new --new --newserveruserdata USERPATH                    new server, data in USERPATH
      python3 start.py --continue --continue --continue                                  daily restart (saved data folder)
      python3 start.py --exportdata BACKUPPATH                                           back up all data to BACKUPPATH
      python3 start.py --reset --reset --reset --loadolddata BACKUP --newserveruserdata USERPATH
                                                                                         start with an old backup in USERPATH"""


def confirm_three_times(what):
    say(f"\n  {what}")
    for i in range(1, 4):
        try:
            ans = input(f"  Type CONFIRM ({i} of 3): ").strip()
        except EOFError:
            ans = ""
        if ans != "CONFIRM":
            fail("Cancelled — nothing was changed.")


def start_server(data: Path, args):
    if os.environ.get("OPENPRISM_NO_START") == "1":      # used by the automated tests
        return
    if not venv_python().exists():
        create_venv()
    install_requirements()
    os.chdir(HERE)
    env = {**os.environ, "OPENPRISM_DATA": str(data)}
    cmd = [str(venv_python()), str(HERE / "run.py"), *args]
    if WIN:
        sys.exit(subprocess.call(cmd, env=env))
    os.execve(cmd[0], cmd, env)


def main():
    if sys.version_info < (3, 10):
        fail(f"OpenPrism needs Python 3.10 or newer (this is {sys.version.split()[0]}).")
    args = sys.argv[1:]
    if args[:1] in (["-h"], ["--help"]):
        say(__doc__)
        return
    gone = [a for a in ("--update", "--preserve", "--export", "--import", "--input", "--output", "--data", "--yes", "--selfpurge") if a in args]
    if gone:
        fail(f"{' '.join(gone)} no longer exist{'s' if len(gone) == 1 else ''}. The commands are:" + COMMANDS)
    n = {f: args.count(f) for f in ("--new", "--continue", "--reset")}
    export_to = _value(args, "--exportdata")
    if "--exportolddata" in args:
        fail("--exportolddata was renamed: use  --loadolddata BACKUP  (it loads an old backup)." + COMMANDS)
    old = _value(args, "--loadolddata")
    newpath = _value(args, "--newserveruserdata")
    args = [a for a in args if a not in n]
    chosen = [f for f, k in n.items() if k] + (["--exportdata"] if export_to else [])
    saved = saved_data()

    if not chosen:
        if old or newpath:
            fail("--loadolddata / --newserveruserdata belong to --reset or --new:" + COMMANDS)
        say(__doc__)
        say(f"  Saved data folder: {saved or '(none yet — set up a server with --new or --reset)'}")
        return
    if len(chosen) > 1:
        fail(f"Use one command at a time (got {' '.join(chosen)})." + COMMANDS)
    cmd = chosen[0]
    if cmd != "--exportdata" and n[cmd] < 3:
        fail(f"Give {cmd} three times to confirm, e.g.:" + COMMANDS)

    if cmd == "--exportdata":
        if args or old or newpath:
            fail("--exportdata only takes the backup folder:  python3 start.py --exportdata ~/openprism-backups")
        if not saved or not (saved / "openprism.db").exists():
            fail("There are no server data to back up yet.")
        use_data(saved)
        require_stopped("back up")
        folder = Path(export_to).expanduser().resolve()
        if folder.exists() and not folder.is_dir():
            fail(f"{folder} is a file; give a folder for the backup.")
        folder.mkdir(parents=True, exist_ok=True)
        out = export(str(folder))
        say("\n  Next: you may now delete the old OpenPrism folder, get the new version, and start it with\n"
            f"      python3 start.py --reset --reset --reset --loadolddata {out} --newserveruserdata USERPATH")
        return

    if cmd == "--continue":
        if old or newpath:
            fail("--continue uses the saved data folder; to choose another one use --new or --reset." + COMMANDS)
        if not saved:
            fail("No data folder has been set up yet. Start a new server with\n"
                 "      python3 start.py --new --new --new --newserveruserdata ~/openprism-data")
        if not saved.is_dir():
            fail(f"The saved data folder {saved} is missing. Restore it, or set up again with --new or --reset.")
        use_data(saved)
        require_stopped("start it again")
        return start_server(saved, args)

    if cmd == "--new":
        if old:
            fail("--new starts an empty server; to load a backup use --reset --reset --reset --loadolddata …")
        if not newpath:
            fail("Say where the new server keeps its data:\n      python3 start.py --new --new --new --newserveruserdata ~/openprism-data")
        target = prepare_folder(newpath)
        require_stopped_at([target, saved], "set up a new server")
        use_data(target)
        if DB.exists():
            try:
                u, pr = counts(DB)
                what = f"{target} already holds an OpenPrism server with {u} account(s) and {pr} project(s)."
            except (sqlite3.DatabaseError, ValueError):
                what = f"{target} already holds OpenPrism server data."
            confirm_three_times(what + " A NEW server deletes all of it (back it up first with --exportdata).")
        clear_folder(target)
        save_data(target)
        say(f"  New server: data will be kept in {target}\n  The first start runs the setup in the administration console.")
        return start_server(target, args)

    # --reset ×3 --loadolddata BACKUP [--newserveruserdata USERPATH]
    if not old:
        fail("--reset needs the backup to load:\n"
             "      python3 start.py --reset --reset --reset --loadolddata ~/openprism-backups --newserveruserdata ~/openprism-data\n"
             "  For an empty new server use  --new --new --new --newserveruserdata USERPATH .")
    target_s = newpath or (str(saved) if saved else None)
    if not target_s:
        fail("Say where the server keeps its data:  … --newserveruserdata ~/openprism-data")
    target = prepare_folder(target_s)
    require_stopped_at([target, saved], "reset")
    src = find_backup(old)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        db, users, projects = load_backup(src, tmp)      # checked before anything is deleted
        use_data(target)
        clear_folder(target)
        install_backup(db, tmp)
    save_data(target)
    say(f"  Loaded {users} account(s) and {projects} project(s) into {target}")
    return start_server(target, args)


if __name__ == "__main__":
    main()
