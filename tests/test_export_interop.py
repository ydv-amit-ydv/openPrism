"""Vector export (EPS, EMF), GraphPad Prism .pzfx exchange and compute timing."""
import struct
from pathlib import Path

import pytest

from helpers import H, make_apps, register
from openprism.pzfx import read, write
from openprism.vector import Reader, to_emf, to_eps

SVG = (Path(__file__).parent / "fixtures_plot.svg").read_text()


def test_svg_reader_extracts_paths_and_text():
    r = Reader(SVG)
    texts = [o.text for o in r.ops if type(o).__name__ == "TextOp"]
    assert "Response (%) ± SEM" in texts and "50" in texts           # rotated title, subscript run
    rotated = [o for o in r.ops if type(o).__name__ == "TextOp" and o.text.startswith("Response")]
    assert abs(rotated[0].angle - 90) < 1e-6
    assert sum(type(o).__name__ == "PathOp" for o in r.ops) > 30


def test_eps_is_well_formed():
    eps = to_eps(SVG).decode("latin-1")
    assert eps.startswith("%!PS-Adobe-3.0 EPSF-3.0") and "%%BoundingBox: 0 0 390 300" in eps and eps.rstrip().endswith("%%EOF")
    assert eps.count("gsave") == eps.count("grestore")
    assert "(Response \\(%\\) \\261 SEM)" in eps                   # ± re-encoded to Latin-1, parentheses escaped
    assert "/Symbol findfont" in eps                                 # Greek α via the Symbol font


def test_emf_records_are_consistent():
    emf = to_emf(SVG)
    typ, size = struct.unpack_from("<II", emf, 0)
    assert typ == 1 and struct.unpack_from("<I", emf, 40)[0] == 0x464D4520      # EMR_HEADER, " EMF"
    n_bytes, n_recs = struct.unpack_from("<II", emf, 48)
    assert n_bytes == len(emf)
    off, count, last = 0, 0, None
    while off < len(emf):
        last, sz = struct.unpack_from("<II", emf, off)
        assert sz >= 8 and sz % 4 == 0
        off += sz
        count += 1
    assert off == len(emf) and count == n_recs and last == 14       # ends with EMR_EOF


def test_vector_reader_rejects_dtd():
    with pytest.raises(ValueError):
        Reader('<!DOCTYPE svg [<!ENTITY x "y">]><svg xmlns="http://www.w3.org/2000/svg"/>')


def test_pzfx_round_trip_and_summary_data():
    t = [{"name": "Dose", "type": "xy", "xTitle": "log[M]", "datasets": [{"name": "A", "reps": 2}], "rowLabels": ["", ""],
          "x": ["-9", "-8"], "cells": [["1", "2"], ["3", ""]], "excluded": {"1,0": True}},
         {"name": "Groups", "type": "column", "datasets": [{"name": "c", "reps": 1}, {"name": "d", "reps": 1}], "rowLabels": ["", "", ""],
          "x": ["", "", ""], "cells": [["1.5", "2"], ["2.5", "3"], ["", "4"]], "excluded": {}}]
    back, warnings = read(write(t))
    assert not warnings
    for a, b in zip(t, back):
        for k in ("name", "type", "datasets", "cells", "excluded"):
            assert a[k] == b[k], k
    with pytest.raises(ValueError):
        read(b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e "x">]><GraphPadPrismFile/>')


def test_endpoints(tmp_path):
    app, _, _ = make_apps(tmp_path)
    c = register(app, "exporter")
    for fmt, magic in (("eps", b"%!PS-Adobe"), ("emf", b"\x01\x00\x00\x00")):
        r = c.post("/api/convert", json={"svg": SVG, "format": fmt}, headers=H)
        assert r.status_code == 200 and r.data.startswith(magic) and "X-OpenPrism-Compute" in r.headers
    assert c.post("/api/convert", json={"svg": SVG, "format": "exe"}, headers=H).status_code == 400
    tables = [{"name": "T", "type": "column", "datasets": [{"name": "a", "reps": 1}], "rowLabels": [""], "x": [""], "cells": [["1"]]}]
    r = c.post("/api/export/pzfx", json={"tables": tables}, headers=H)
    assert r.status_code == 200 and b"GraphPadPrismFile" in r.data
    up = c.post("/api/import", data={"file": (__import__("io").BytesIO(r.data), "x.pzfx"), "type": "column"}, headers=H, content_type="multipart/form-data")
    assert up.status_code == 200 and up.get_json()["tables"][0]["cells"] == [["1"]]
    r = c.post("/api/analyze", json={"analysis": "descriptive", "table": tables[0]}, headers=H)
    wall = dict(p.split("=") for p in r.headers["X-OpenPrism-Compute"].split(";"))["wall"]
    assert float(wall) < 10
