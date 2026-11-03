"""start.py server commands: --new ×3, --continue ×3, --exportdata, --reset ×3 --loadolddata (run as real commands)."""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

from helpers import H, env, make_apps, name_ct, register

HERE = Path(__file__).resolve().parents[1]
NEW = ["--new"] * 3
CONT = ["--continue"] * 3
RESET = ["--reset"] * 3


def install(root: Path) -> Path:
    """A throw-away copy of the launcher (start.py + version + schema)."""
    app = root / "openprism"
    (app / "openprism").mkdir(parents=True)
    shutil.copy2(HERE / "start.py", app / "start.py")
    shutil.copy2(HERE / "openprism" / "__init__.py", app / "openprism" / "__init__.py")
    shutil.copy2(HERE / "openprism" / "store.py", app / "openprism" / "store.py")
    return app


def sh(app, args, answer=""):
    e = {k: v for k, v in os.environ.items() if k != "OPENPRISM_DATA"}
    return subprocess.run([sys.executable, str(app / "start.py"), *args], capture_output=True, text=True, input=answer,
                          env={**e, "OPENPRISM_NO_START": "1"}, cwd=str(app))


def seed(data: Path, users=("alice", "bob")):
    app, _, _ = make_apps(data)
    first = None
    for u in users:
        c = register(app, u)
        first = first or c
    assert first.post("/api/projects", json={"name": name_ct(), "data": env()}, headers=H).status_code == 200


def accounts(data: Path):
    con = sqlite3.connect(data / "openprism.db")
    try:
        return sorted(r[0] for r in con.execute("SELECT username FROM users"))
    finally:
        con.close()


def test_new_continue_export_reset_cycle(tmp_path):
    app = install(tmp_path / "v1")
    data = tmp_path / "srv-data"
    assert "three times" in sh(app, ["--new", "--newserveruserdata", str(data)]).stderr
    assert "Saved data folder" in sh(app, []).stdout                        # no flag: help + saved folder
    r = sh(app, NEW + ["--newserveruserdata", str(data)])
    assert r.returncode == 0 and (data / ".openprism-data").exists(), r.stderr
    assert json.loads((app / "openprism.conf").read_text())["data"] == str(data.resolve())
    seed(data)                                                              # the server is used
    assert sh(app, CONT).returncode == 0
    backups = tmp_path / "backups"
    r = sh(app, ["--exportdata", str(backups)])
    assert r.returncode == 0 and "Backed up 2 account(s) and 1 project(s)" in r.stdout
    zips = list(backups.glob("openprism-backup-*.zip"))
    assert len(zips) == 1
    # the user deletes the old copy, clones the new version and loads the backup into a new folder
    shutil.rmtree(app)
    app2 = install(tmp_path / "v2")
    data2 = tmp_path / "srv-data-2"
    assert "three times" in sh(app2, ["--reset", "--loadolddata", str(backups), "--newserveruserdata", str(data2)]).stderr
    r = sh(app2, RESET + ["--loadolddata", str(backups), "--newserveruserdata", str(data2)])
    assert r.returncode == 0 and "OK" in r.stdout, r.stderr
    assert accounts(data2) == ["alice", "bob"]
    assert json.loads((app2 / "openprism.conf").read_text())["data"] == str(data2.resolve())
    r = sh(app2, RESET + ["--loadolddata", str(zips[0])])                   # a single .zip; saved folder reused
    assert r.returncode == 0 and accounts(data2) == ["alice", "bob"]


def test_new_on_existing_data_asks_confirm_three_times(tmp_path):
    app = install(tmp_path / "a")
    data = tmp_path / "d"
    assert sh(app, NEW + ["--newserveruserdata", str(data)]).returncode == 0
    seed(data)
    r = sh(app, NEW + ["--newserveruserdata", str(data)], answer="CONFIRM\nCONFIRM\nno\n")
    assert r.returncode != 0 and "Cancelled" in r.stderr and accounts(data) == ["alice", "bob"]
    r = sh(app, NEW + ["--newserveruserdata", str(data)], answer="CONFIRM\nCONFIRM\nCONFIRM\n")
    assert r.returncode == 0 and not (data / "openprism.db").exists()


def test_folder_safety(tmp_path):
    app = install(tmp_path / "a")
    foreign = tmp_path / "my-documents"
    foreign.mkdir()
    (foreign / "thesis.docx").write_text("important")
    r = sh(app, NEW + ["--newserveruserdata", str(foreign)])
    assert r.returncode != 0 and "other files" in r.stderr and (foreign / "thesis.docx").exists()
    assert sh(app, NEW + ["--newserveruserdata", str(app)]).returncode != 0           # not the program folder
    assert sh(app, NEW + ["--newserveruserdata", str(tmp_path)]).returncode != 0      # not a parent of it
    (tmp_path / "afile").write_text("x")
    assert sh(app, NEW + ["--newserveruserdata", str(tmp_path / "afile")]).returncode != 0
    if os.name != "nt" and os.geteuid() != 0:                                         # root can write anywhere
        ro = tmp_path / "readonly"
        ro.mkdir()
        os.chmod(ro, 0o500)
        r = sh(app, NEW + ["--newserveruserdata", str(ro / "data")])
        assert r.returncode != 0 and "cannot write" in r.stderr


def test_bad_or_newer_backup_deletes_nothing(tmp_path):
    app = install(tmp_path / "a")
    data = tmp_path / "d"
    assert sh(app, NEW + ["--newserveruserdata", str(data)]).returncode == 0
    seed(data)
    (tmp_path / "junk.zip").write_text("not a zip")
    r = sh(app, RESET + ["--loadolddata", str(tmp_path / "junk.zip")])
    assert r.returncode != 0 and accounts(data) == ["alice", "bob"]
    other = tmp_path / "other"
    seed(other, users=("zoe",))
    con = sqlite3.connect(other / "openprism.db")
    con.execute("UPDATE settings SET value = '999' WHERE key = 'schema'")
    con.commit()
    con.close()
    newer = tmp_path / "newer.zip"
    with zipfile.ZipFile(newer, "w") as z:
        z.write(other / "openprism.db", "openprism.db")
    r = sh(app, RESET + ["--loadolddata", str(newer)])
    assert r.returncode != 0 and "newer OpenPrism" in r.stderr and accounts(data) == ["alice", "bob"]


def test_refusals_and_running_server(tmp_path):
    app = install(tmp_path / "a")
    assert "No data folder" in sh(app, CONT).stderr                           # nothing set up yet
    assert sh(app, ["--exportdata", str(tmp_path / "b")]).returncode != 0     # nothing to back up
    data = tmp_path / "d"
    assert sh(app, NEW + ["--newserveruserdata", str(data)]).returncode == 0
    seed(data)
    r = sh(app, RESET + ["--exportolddata", str(tmp_path)])
    assert r.returncode != 0 and "--loadolddata" in r.stderr and accounts(data) == ["alice", "bob"]
    for old in (["--selfpurge"], ["--export", "x"], ["--import", "x"], ["--data", "x"], ["--update"]):
        r = sh(app, old)
        assert r.returncode != 0 and "--continue" in r.stderr
    assert sh(app, NEW + CONT + ["--newserveruserdata", str(data)]).returncode != 0   # one command at a time
    assert sh(app, RESET).returncode != 0                                     # --reset needs a backup to load
    (data / "server.pid").write_text(json.dumps({"pid": os.getpid(), "port": 1}))
    for cmd in (CONT, ["--exportdata", str(tmp_path / "b")], RESET + ["--loadolddata", str(tmp_path)]):
        r = sh(app, cmd)
        assert r.returncode != 0 and "running" in r.stderr
    assert accounts(data) == ["alice", "bob"]


def test_legacy_projects_folder_is_found(tmp_path):
    """Installations from before openprism.conf kept the data in projects/: --exportdata still finds them."""
    app = install(tmp_path / "a")
    seed(app / "projects")
    r = sh(app, ["--exportdata", str(tmp_path / "b")])
    assert r.returncode == 0 and "2 account(s)" in r.stdout
