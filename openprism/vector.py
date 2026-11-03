"""Vector export of graphs and layouts to EPS and EMF.

The browser renders every graph and layout as SVG. This module reads that SVG
(paths, shapes, text with sub/superscripts, transforms, nested SVG viewports,
rectangular clip paths, colours and opacity), reduces it to a small list of
drawing operations and writes them as

* EPS — Encapsulated PostScript, level 2 (Illustrator, CorelDRAW, LaTeX, print
  shops). Text uses the standard PostScript fonts (Helvetica / Times / Courier,
  Latin-1 re-encoded; Greek letters from the Symbol font).
* EMF — Windows Enhanced Metafile (Word, PowerPoint, Visio). Text stays editable
  Unicode text; lines, curves and fills stay vectors.

Both formats lack transparency: semi-transparent colours are blended with white
(the usual way figure software flattens them for these formats).
No external programs are needed; the SVG is parsed with ElementTree (no
external entities or DTDs are resolved) and size-limited by the caller.
"""
from __future__ import annotations

import math
import re
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from svgelements import (Arc, Circle, Close, Color, CubicBezier, Ellipse, Line, Matrix, Move, Path, Polygon, Polyline,
                         QuadraticBezier, Rect, SimpleLine)

SVG_NS = "{http://www.w3.org/2000/svg}"
MAX_OPS = 200_000

# ----------------------------------------------------------------------------- font metrics
# Helvetica advance widths (Adobe AFM, 1/1000 em) for ASCII 32..126
_HELV = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278] + [556] * 10 + \
        [278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667, 778,
         722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556, 556, 222,
         222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584]


def text_width(s, size, bold=False):
    w = 0
    for ch in s:
        o = ord(ch)
        w += _HELV[o - 32] if 32 <= o <= 126 else 556 if o < 0x370 else 600
    return w / 1000 * size * (1.05 if bold else 1.0)


# ----------------------------------------------------------------------------- intermediate representation
@dataclass
class PathOp:
    segs: list                     # ('M', (x, y)) | ('L', (x, y)) | ('C', p1, p2, p3) | ('Z',)
    fill: tuple | None             # (r, g, b) 0-255, already blended with white
    stroke: tuple | None
    width: float = 1.0
    dash: list = field(default_factory=list)
    evenodd: bool = False
    clip: tuple | None = None      # (x0, y0, x1, y1)


@dataclass
class TextOp:
    x: float
    y: float
    angle: float                   # degrees, counter-clockwise on the page
    text: str
    size: float
    color: tuple
    family: str = "sans"
    bold: bool = False
    italic: bool = False
    clip: tuple | None = None


@dataclass
class ImageOp:
    x0: float
    y0: float
    x1: float
    y1: float
    data: bytes                    # original PNG / JPEG bytes
    mime: str
    clip: tuple | None = None
    opacity: float = 1.0


def _decode_image(op, gray=False, max_px=4000):
    """RGB (or L) pixels flattened on white, as a Pillow image."""
    import io

    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 60_000_000
    im = Image.open(io.BytesIO(op.data))
    im.load()
    if max(im.size) > max_px:
        k = max_px / max(im.size)
        im = im.resize((max(1, int(im.size[0] * k)), max(1, int(im.size[1] * k))))
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        if op.opacity < 1:
            a = im.getchannel("A").point(lambda v: int(v * op.opacity))
            im.putalpha(a)
        im = Image.alpha_composite(bg, im)
    return im.convert("L" if gray else "RGB")


def _blend(color, alpha):
    if color is None:
        return None
    a = max(0.0, min(1.0, alpha))
    return tuple(int(round(c * a + 255 * (1 - a))) for c in color)


def _parse_style(el):
    st = {}
    for k in ("fill", "stroke", "stroke-width", "stroke-dasharray", "opacity", "fill-opacity", "stroke-opacity", "font-size", "font-family",
              "font-weight", "font-style", "text-anchor", "fill-rule", "visibility", "display", "dominant-baseline", "baseline-shift"):
        if k in el.attrib:
            st[k] = el.attrib[k]
    for part in el.attrib.get("style", "").split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            st[k.strip()] = v.strip()
    return st


def _color(v):
    if v is None or v in ("none", "transparent", ""):
        return None, 0.0
    if v.startswith("url("):
        return (128, 128, 128), 1.0
    try:
        c = Color(v)
    except Exception:  # noqa: BLE001
        return (0, 0, 0), 1.0
    if c.value is None:
        return None, 0.0
    return (c.red, c.green, c.blue), c.alpha / 255.0


def _num(v, default=0.0, ref=None):
    if v is None:
        return default
    v = str(v).strip()
    try:
        if v.endswith("%") and ref is not None:
            return float(v[:-1]) / 100 * ref
        return float(re.sub(r"(px|pt)$", "", v))
    except ValueError:
        return default


def _area(op):
    xs = [pt[0] for sg in op.segs for pt in sg[1:]]
    ys = [pt[1] for sg in op.segs for pt in sg[1:]]
    return (max(xs) - min(xs)) * (max(ys) - min(ys)) if xs else 0.0


class Reader:
    """Walks an SVG tree and produces PathOp / TextOp lists in page pixels."""

    def __init__(self, svg_text):
        if len(svg_text) > 30_000_000:
            raise ValueError("SVG too large")
        if "<!ENTITY" in svg_text or "<!DOCTYPE" in svg_text:
            raise ValueError("SVG with a DTD is not accepted")
        self.root = ET.fromstring(svg_text)
        self.width = _num(self.root.attrib.get("width"), 0) or 800
        self.height = _num(self.root.attrib.get("height"), 0) or 600
        vb = self.root.attrib.get("viewBox")
        self.ops = []
        self.clips = {}
        for cp in self.root.iter(f"{SVG_NS}clipPath"):
            r = cp.find(f"{SVG_NS}rect")
            if r is not None and cp.attrib.get("id"):
                self.clips[cp.attrib["id"]] = (_num(r.attrib.get("x")), _num(r.attrib.get("y")), _num(r.attrib.get("width")), _num(r.attrib.get("height")),
                                               Matrix(r.attrib.get("transform", "")))
        m = Matrix()
        if vb:
            x, y, w, h = (float(t) for t in re.split(r"[ ,]+", vb.strip()))
            m = Matrix(f"translate({-x},{-y})") * Matrix(f"scale({self.width / w},{self.height / h})")
        base = {"fill": "black", "stroke": "none", "stroke-width": "1", "font-size": "16", "font-family": "sans-serif", "opacity": "1",
                "fill-opacity": "1", "stroke-opacity": "1"}
        self._walk(self.root, m, base, None, 1.0)
        self._reorder_translucent()

    def _reorder_translucent(self):
        """EPS/EMF have no transparency. A translucent fill (e.g. a confidence band) is flattened against
        white and would hide the lines, markers and text drawn before it, which stay visible through it in
        the SVG. Such fills are therefore moved back beneath those small or stroke-only items (but stay above
        large opaque areas such as bars and backgrounds), which keeps everything visible."""
        page = self.width * self.height
        ops = self.ops
        i = 0
        while i < len(ops):
            op = ops[i]
            if isinstance(op, PathOp) and getattr(op, "translucent", False):
                j = i
                while j > 0:
                    prev = ops[j - 1]
                    if isinstance(prev, ImageOp):
                        break
                    small = isinstance(prev, TextOp) or prev.fill is None or getattr(prev, "translucent", False) or _area(prev) < 0.01 * page
                    if not small or prev.clip != op.clip:
                        break
                    j -= 1
                if j < i:
                    ops.insert(j, ops.pop(i))
            i += 1

    # ------------------------------------------------------------------ helpers
    def _clip_rect(self, ref, m):
        cid = re.match(r"url\(#([^)]+)\)", ref or "")
        if not cid or cid.group(1) not in self.clips:
            return None
        x, y, w, h, t = self.clips[cid.group(1)]
        mm = t * m
        pts = [mm.point_in_matrix_space((px, py)) for px, py in ((x, y), (x + w, y), (x, y + h), (x + w, y + h))]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    @staticmethod
    def _intersect(a, b):
        if a is None:
            return b
        if b is None:
            return a
        return (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))

    def _walk(self, el, m, style, clip, opacity):
        tag = el.tag.replace(SVG_NS, "")
        if tag in ("defs", "clipPath", "mask", "pattern", "linearGradient", "radialGradient", "style", "script", "title", "desc", "metadata", "symbol", "marker", "foreignObject"):
            return
        st = {**{k: v for k, v in style.items() if k not in ("opacity", "transform", "display")}, **_parse_style(el)}
        if st.get("display") == "none" or st.get("visibility") == "hidden":
            return
        op = opacity * _num(st.get("opacity"), 1.0)
        if el is not self.root and "transform" in el.attrib:
            m = Matrix(el.attrib["transform"]) * m
        if tag == "svg" and el is not self.root:
            x, y = _num(el.attrib.get("x")), _num(el.attrib.get("y"))
            w, h = _num(el.attrib.get("width"), 0), _num(el.attrib.get("height"), 0)
            vb = el.attrib.get("viewBox")
            inner = Matrix(f"translate({x},{y})")
            if vb and w and h:
                vx, vy, vw, vh = (float(t) for t in re.split(r"[ ,]+", vb.strip()))
                s = min(w / vw, h / vh)
                inner = Matrix(f"translate({-vx},{-vy})") * Matrix(f"scale({s})") * Matrix(f"translate({x + (w - vw * s) / 2},{y + (h - vh * s) / 2})")
            pts = [m.point_in_matrix_space(p) for p in ((x, y), (x + w, y + h))]
            clip = self._intersect(clip, (min(pts[0][0], pts[1][0]), min(pts[0][1], pts[1][1]), max(pts[0][0], pts[1][0]), max(pts[0][1], pts[1][1]))) if w and h else clip
            m = inner * m
        if "clip-path" in el.attrib or "clip-path" in st:
            clip = self._intersect(clip, self._clip_rect(el.attrib.get("clip-path") or st.get("clip-path"), m))
        if len(self.ops) > MAX_OPS:
            raise ValueError("Drawing too complex for vector export")
        if tag == "text":
            self._text(el, m, st, clip, op)
            return
        if tag == "image":
            self._image(el, m, clip, op)
            return
        shape = self._shape(el, tag)
        if shape is not None:
            self._path(shape, m, st, clip, op)
        for child in el:
            self._walk(child, m, st, clip, op)

    @staticmethod
    def _shape(el, tag):
        a = el.attrib
        try:
            if tag == "path" and a.get("d"):
                return Path(a["d"])
            if tag == "rect":
                w, h = _num(a.get("width")), _num(a.get("height"))
                if w <= 0 or h <= 0:
                    return None
                return Path(Rect(_num(a.get("x")), _num(a.get("y")), w, h, _num(a.get("rx"), 0), _num(a.get("ry"), 0)))
            if tag == "circle":
                return Path(Circle(_num(a.get("cx")), _num(a.get("cy")), _num(a.get("r"))))
            if tag == "ellipse":
                return Path(Ellipse(_num(a.get("cx")), _num(a.get("cy")), _num(a.get("rx")), _num(a.get("ry"))))
            if tag == "line":
                return Path(SimpleLine(_num(a.get("x1")), _num(a.get("y1")), _num(a.get("x2")), _num(a.get("y2"))))
            if tag in ("polyline", "polygon") and a.get("points"):
                return Path((Polygon if tag == "polygon" else Polyline)(a["points"]))
        except Exception:  # noqa: BLE001  (malformed geometry is skipped)
            return None
        return None

    def _path(self, path, m, st, clip, op):
        fill, fa = _color(st.get("fill"))
        stroke, sa = _color(st.get("stroke"))
        fa *= _num(st.get("fill-opacity"), 1.0) * op
        sa *= _num(st.get("stroke-opacity"), 1.0) * op
        sw = _num(st.get("stroke-width"), 1.0)
        scale = math.sqrt(abs(m.a * m.d - m.b * m.c)) or 1.0
        if fill is None or fa <= 0.003:
            fill = None
        if stroke is None or sa <= 0.003 or sw <= 0:
            stroke = None
        if fill is None and stroke is None:
            return
        segs = []
        p = Path(path) * m
        p.reify()  # apply the transform to the coordinates (svgelements multiplies lazily)
        for s in p:
            if isinstance(s, Move):
                segs.append(("M", (s.end.x, s.end.y)))
            elif isinstance(s, Close):
                segs.append(("Z",))
            elif isinstance(s, Line):
                segs.append(("L", (s.end.x, s.end.y)))
            elif isinstance(s, CubicBezier):
                segs.append(("C", (s.control1.x, s.control1.y), (s.control2.x, s.control2.y), (s.end.x, s.end.y)))
            elif isinstance(s, QuadraticBezier):
                a, c, e = s.start, s.control, s.end
                segs.append(("C", (a.x + 2 / 3 * (c.x - a.x), a.y + 2 / 3 * (c.y - a.y)), (e.x + 2 / 3 * (c.x - e.x), e.y + 2 / 3 * (c.y - e.y)), (e.x, e.y)))
            elif isinstance(s, Arc):
                for cb in s.as_cubic_curves():
                    segs.append(("C", (cb.control1.x, cb.control1.y), (cb.control2.x, cb.control2.y), (cb.end.x, cb.end.y)))
        if not segs or all(sg[0] == "M" for sg in segs):
            return
        if segs[0][0] != "M":
            segs.insert(0, ("M", (p.first_point.x, p.first_point.y)))
        dash = []
        da = st.get("stroke-dasharray")
        if da and da != "none":
            dash = [v * scale for v in (_num(t) for t in re.split(r"[ ,]+", da.strip()) if t) if v >= 0]
            if len(dash) % 2:
                dash *= 2
            if not any(dash):
                dash = []
        po = PathOp(segs, _blend(fill, fa) if fill else None, _blend(stroke, sa) if stroke else None, sw * scale, dash,
                    st.get("fill-rule") == "evenodd", clip)
        po.translucent = bool(fill) and fa < 0.98 and (stroke is None or sa < 0.98)
        self.ops.append(po)

    def _image(self, el, m, clip, op):
        import base64
        href = el.attrib.get("href") or el.attrib.get("{http://www.w3.org/1999/xlink}href") or ""
        mm = re.match(r"data:(image/(?:png|jpeg|jpg));base64,(.*)$", href.strip(), re.S)
        if not mm:
            return  # only embedded PNG/JPEG data (no external references are ever fetched)
        try:
            data = base64.b64decode(mm.group(2), validate=False)
        except Exception:  # noqa: BLE001
            return
        x, y = _num(el.attrib.get("x")), _num(el.attrib.get("y"))
        w, h = _num(el.attrib.get("width")), _num(el.attrib.get("height"))
        if w <= 0 or h <= 0:
            return
        par = el.attrib.get("preserveAspectRatio", "xMidYMid meet")
        if not par.startswith("none"):
            try:
                import io

                from PIL import Image
                iw, ih = Image.open(io.BytesIO(data)).size
                k = min(w / iw, h / ih)
                x, y, w, h = x + (w - iw * k) / 2, y + (h - ih * k) / 2, iw * k, ih * k
            except Exception:  # noqa: BLE001
                return
        pts = [m.point_in_matrix_space(p) for p in ((x, y), (x + w, y + h))]
        self.ops.append(ImageOp(min(pts[0][0], pts[1][0]), min(pts[0][1], pts[1][1]), max(pts[0][0], pts[1][0]), max(pts[0][1], pts[1][1]),
                                data, mm.group(1).replace("jpg", "jpeg"), clip, op * _num(el.attrib.get("opacity"), 1.0)))

    def _text(self, el, m, st, clip, op):
        # collect runs: (text, size, dy, font props, color) — tspans may change size/baseline
        base_size = _num(st.get("font-size"), 16)
        x = _num(el.attrib.get("x"))
        y = _num(el.attrib.get("y"))
        runs = []

        def props(s, size_ref):
            size = _num(s.get("font-size"), size_ref, ref=size_ref)
            fam = s.get("font-family", "sans-serif").lower()
            family = "serif" if ("times" in fam or ("serif" in fam and "sans" not in fam)) else "mono" if ("mono" in fam or "courier" in fam) else "sans"
            bold = s.get("font-weight", "normal") in ("bold", "bolder", "600", "700", "800", "900")
            italic = s.get("font-style", "normal") in ("italic", "oblique")
            col, a = _color(s.get("fill", "black"))
            a *= _num(s.get("fill-opacity"), 1.0) * op
            return size, family, bold, italic, _blend(col or (0, 0, 0), a)

        def collect(node, s, size_ref, dy_acc):
            if node.text:
                runs.append((node.text, *props(s, size_ref), dy_acc))
            for ch in node:
                if ch.tag.replace(SVG_NS, "") != "tspan":
                    continue
                cs = {**s, **_parse_style(ch)}
                size_here = props(s, size_ref)[0]
                csz = _num(cs.get("font-size"), size_here, ref=size_here)
                dy = ch.attrib.get("dy")
                d = 0.0
                if dy:
                    d = _num(dy.replace("em", ""), 0) * csz if dy.strip().endswith("em") else _num(dy)
                new_line = "x" in ch.attrib and runs
                if new_line:
                    runs.append(("\n", *props(cs, size_here), dy_acc + d))
                collect(ch, cs, size_here, dy_acc + d)
                if ch.tail:
                    runs.append((ch.tail, *props(s, size_ref), dy_acc + d))
                dy_acc += d
        collect(el, st, base_size, 0.0)
        runs = [(t.replace("​", "").replace("\xa0", " "), *rest) for t, *rest in runs]
        runs = [r for r in runs if r[0]]
        if not runs:
            return
        anchor = st.get("text-anchor", "start")
        # split into lines (Plotly multi-line labels use tspans with x and dy)
        lines, cur = [], []
        for r in runs:
            if r[0] == "\n":
                lines.append(cur)
                cur = [r[:0] + ("",) + r[1:]]
                continue
            cur.append(r)
        lines.append(cur)
        ang = math.degrees(math.atan2(m.b, m.a))
        sx = math.hypot(m.a, m.b) or 1.0
        for line in lines:
            line = [r for r in line if r[0] != "" or len(line) == 1]
            if not line:
                continue
            total = sum(text_width(t, sz, b) for t, sz, fam, b, it, col, dy in line)
            off = {"middle": -total / 2, "end": -total}.get(anchor, 0.0)
            cx = x + off
            for t, sz, fam, b, it, col, dy in line:
                if t.strip() == "" and not t:
                    continue
                px, py = m.point_in_matrix_space((cx, y + dy))
                self.ops.append(TextOp(px, py, -ang, t, sz * sx, col, fam, b, it, clip))
                cx += text_width(t, sz, b)


# ----------------------------------------------------------------------------- EPS writer
_SYMBOL = {"α": "a", "β": "b", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "h", "θ": "q", "ι": "i", "κ": "k", "λ": "l", "μ": "m", "ν": "n",
           "ξ": "x", "π": "p", "ρ": "r", "σ": "s", "τ": "t", "υ": "u", "φ": "f", "χ": "c", "ψ": "y", "ω": "w", "Γ": "G", "Δ": "D", "Θ": "Q",
           "Λ": "L", "Ξ": "X", "Π": "P", "Σ": "S", "Φ": "F", "Ψ": "Y", "Ω": "W", "≤": "\xa3", "≥": "\xb3", "≠": "\xb9", "≈": "\xbb",
           "∞": "\xa5", "→": "\xae", "←": "\xac", "↑": "\xad", "↓": "\xaf", "√": "\xd6", "∑": "\xe5", "∫": "\xf2", "∂": "\xb6", "•": "\xb7"}
_ASCII = {"−": "-", "–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"', "…": "...",
          " ": " ", " ": " ", " ": " ", " ": " ", "′": "'", "″": '"', "·": "\xb7", "•": "\xb7"}
_FONTS = {("sans", False, False): "Helvetica", ("sans", True, False): "Helvetica-Bold", ("sans", False, True): "Helvetica-Oblique",
          ("sans", True, True): "Helvetica-BoldOblique", ("serif", False, False): "Times-Roman", ("serif", True, False): "Times-Bold",
          ("serif", False, True): "Times-Italic", ("serif", True, True): "Times-BoldItalic", ("mono", False, False): "Courier",
          ("mono", True, False): "Courier-Bold", ("mono", False, True): "Courier-Oblique", ("mono", True, True): "Courier-BoldOblique"}


def _ps_str(s):
    out = []
    for ch in s:
        o = ord(ch)
        if ch in "()\\":
            out.append("\\" + ch)
        elif 32 <= o <= 126:
            out.append(ch)
        else:
            out.append("\\%03o" % (o & 0xFF))
    return "(" + "".join(out) + ")"


def _ps_runs(text):
    """Split text into (fontkind, latin1-or-symbol string) runs."""
    runs, cur, kind = [], [], None
    for ch in text:
        ch = _ASCII.get(ch, ch)
        if ch in _SYMBOL:
            k, c = "sym", _SYMBOL[ch]
        elif ord(ch[0]) < 256:
            k, c = "lat", ch
        else:
            k, c = "lat", "?"
        if k != kind and cur:
            runs.append((kind, "".join(cur)))
            cur = []
        kind = k
        cur.append(c)
    if cur:
        runs.append((kind, "".join(cur)))
    return runs


def _eps_image(op, X, Y, k, gray):
    import base64
    import zlib
    if op.mime == "image/jpeg" and op.opacity >= 1 and not gray:
        from PIL import Image
        import io
        im = Image.open(io.BytesIO(op.data))
        if im.mode in ("RGB", "L"):
            W, H = im.size
            data, filt, cs = op.data, "/DCTDecode filter", "/DeviceRGB" if im.mode == "RGB" else "/DeviceGray"
            decode = "[0 1 0 1 0 1]" if im.mode == "RGB" else "[0 1]"
        else:
            im = None
    else:
        im = None
    if im is None or op.mime != "image/jpeg" or gray or op.opacity < 1:
        px = _decode_image(op, gray)
        W, H = px.size
        data, filt = zlib.compress(px.tobytes(), 9), "/FlateDecode filter"
        cs, decode = ("/DeviceGray", "[0 1]") if gray else ("/DeviceRGB", "[0 1 0 1 0 1]")
    enc = base64.a85encode(data, wrapcol=76).decode("ascii")
    w_pt, h_pt = (op.x1 - op.x0) * k, (op.y1 - op.y0) * k
    return (f"gsave {X(op.x0):.3f} {Y(op.y1):.3f} translate {w_pt:.3f} {h_pt:.3f} scale {cs} setcolorspace\n"
            f"<< /ImageType 1 /Width {W} /Height {H} /BitsPerComponent 8 /Decode {decode} /ImageMatrix [{W} 0 0 -{H} 0 {H}] "
            f"/DataSource currentfile /ASCII85Decode filter {filt} >> image\n{enc}~>\ngrestore")


def to_eps(svg_text, title="OpenPrism figure", gray=False, background=True):
    rd = Reader(svg_text)
    if gray:
        _grayscale(rd.ops)
    W, H = rd.width, rd.height
    k = 0.75  # px -> pt
    X = lambda x: x * k  # noqa: E731
    Y = lambda y: (H - y) * k  # noqa: E731
    used = sorted({_FONTS[(t.family, t.bold, t.italic)] for t in rd.ops if isinstance(t, TextOp)})
    level = 3 if any(isinstance(o, ImageOp) for o in rd.ops) else 2  # images use FlateDecode (PostScript 3)
    lines = ["%!PS-Adobe-3.0 EPSF-3.0", f"%%BoundingBox: 0 0 {math.ceil(W * k)} {math.ceil(H * k)}", f"%%HiResBoundingBox: 0 0 {W * k:.3f} {H * k:.3f}",
             "%%Creator: OpenPrism", f"%%Title: {title[:200]}", f"%%LanguageLevel: {level}", "%%DocumentData: Clean7Bit", "%%Pages: 1", "%%EndComments",
             "%%BeginProlog", "/OPdict 40 dict def OPdict begin",
             "/m {moveto} bind def /l {lineto} bind def /c {curveto} bind def /h {closepath} bind def",
             "/rg {setrgbcolor} bind def /w {setlinewidth} bind def",
             "/reenc { findfont dup length dict begin {1 index /FID ne {def} {pop pop} ifelse} forall /Encoding ISOLatin1Encoding def currentdict end definefont pop } bind def",
             "end", "%%EndProlog", "%%Page: 1 1", "OPdict begin", "save", "1 setlinejoin 0 setlinecap 10 setmiterlimit"]
    for f in used:
        lines.append(f"/{f}-L1 /{f} reenc")
    if background:
        lines.append("1 1 1 rg newpath 0 0 m %.3f 0 l %.3f %.3f l 0 %.3f l h fill" % (W * k, W * k, H * k, H * k))
    cur_clip = None
    for op in rd.ops:
        if op.clip != cur_clip:
            if cur_clip is not None:
                lines.append("grestore")
            if op.clip is not None:
                x0, y0, x1, y1 = op.clip
                lines.append("gsave newpath %.3f %.3f m %.3f %.3f l %.3f %.3f l %.3f %.3f l h clip newpath" % (X(x0), Y(y0), X(x1), Y(y0), X(x1), Y(y1), X(x0), Y(y1)))
            cur_clip = op.clip
        if isinstance(op, ImageOp):
            lines.append(_eps_image(op, X, Y, k, gray))
            continue
        if isinstance(op, PathOp):
            parts = ["newpath"]
            for sg in op.segs:
                if sg[0] == "M":
                    parts.append("%.3f %.3f m" % (X(sg[1][0]), Y(sg[1][1])))
                elif sg[0] == "L":
                    parts.append("%.3f %.3f l" % (X(sg[1][0]), Y(sg[1][1])))
                elif sg[0] == "C":
                    parts.append("%.3f %.3f %.3f %.3f %.3f %.3f c" % (X(sg[1][0]), Y(sg[1][1]), X(sg[2][0]), Y(sg[2][1]), X(sg[3][0]), Y(sg[3][1])))
                else:
                    parts.append("h")
            path = " ".join(parts)
            if op.fill and op.stroke:
                lines.append(f"{path} gsave {op.fill[0] / 255:.4f} {op.fill[1] / 255:.4f} {op.fill[2] / 255:.4f} rg {'eofill' if op.evenodd else 'fill'} grestore")
                path = ""
            elif op.fill:
                lines.append(f"{path} {op.fill[0] / 255:.4f} {op.fill[1] / 255:.4f} {op.fill[2] / 255:.4f} rg {'eofill' if op.evenodd else 'fill'}")
            if op.stroke:
                dash = "[%s] 0 setdash" % " ".join("%.3f" % (d * k) for d in op.dash) if op.dash else "[] 0 setdash"
                lines.append(f"{path} {op.stroke[0] / 255:.4f} {op.stroke[1] / 255:.4f} {op.stroke[2] / 255:.4f} rg {op.width * k:.3f} w {dash} stroke")
        else:
            font = _FONTS[(op.family, op.bold, op.italic)]
            body = [f"gsave {X(op.x):.3f} {Y(op.y):.3f} translate {op.angle:.3f} rotate 0 0 moveto {op.color[0] / 255:.4f} {op.color[1] / 255:.4f} {op.color[2] / 255:.4f} rg"]
            for kind, s in _ps_runs(op.text):
                fname = "Symbol" if kind == "sym" else f"{font}-L1"
                body.append(f"/{fname} findfont {op.size * k:.3f} scalefont setfont {_ps_str(s)} show")
            body.append("grestore")
            lines.append(" ".join(body))
    if cur_clip is not None:
        lines.append("grestore")
    lines += ["restore", "end", "showpage", "%%Trailer", "%%EOF", ""]
    return "\n".join(lines).encode("latin-1")


# ----------------------------------------------------------------------------- EMF writer
S = 16  # logical units per pixel (sub-pixel precision with integer coordinates)


class _Emf:
    def __init__(self):
        self.recs = []
        self.handles = 1
        self.bounds = None

    def rec(self, typ, payload=b""):
        data = struct.pack("<II", typ, 8 + len(payload)) + payload
        self.recs.append(data)

    def handle(self):
        h = self.handles
        self.handles += 1
        return h


def _rect(pts):
    xs = [p[0] for p in pts] or [0]
    ys = [p[1] for p in pts] or [0]
    return struct.pack("<iiii", int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))


def _colorref(c):
    return c[0] | (c[1] << 8) | (c[2] << 16)


def to_emf(svg_text, title="OpenPrism figure", gray=False, background=True):
    rd = Reader(svg_text)
    if gray:
        _grayscale(rd.ops)
    W, H = rd.width, rd.height
    e = _Emf()
    P = lambda x, y: (int(round(x * S)), int(round(y * S)))  # noqa: E731
    e.rec(17, struct.pack("<I", 8))                                   # SETMAPMODE MM_ANISOTROPIC
    e.rec(9, struct.pack("<ii", int(W * S), int(H * S)))              # SETWINDOWEXTEX
    e.rec(10, struct.pack("<ii", 0, 0))                               # SETWINDOWORGEX
    e.rec(11, struct.pack("<ii", int(round(W)), int(round(H))))       # SETVIEWPORTEXTEX (device px)
    e.rec(12, struct.pack("<ii", 0, 0))                               # SETVIEWPORTORGEX
    e.rec(18, struct.pack("<I", 1))                                   # SETBKMODE TRANSPARENT
    e.rec(22, struct.pack("<I", 24))                                  # SETTEXTALIGN TA_BASELINE|TA_LEFT
    e.rec(58, struct.pack("<f", 10.0))                                # SETMITERLIMIT
    if background:  # white page
        bg = e.handle()
        e.rec(39, struct.pack("<IIII", bg, 0, 0xFFFFFF, 0))
        e.rec(37, struct.pack("<I", bg))
        e.rec(37, struct.pack("<I", 0x80000008))                      # NULL_PEN
        e.rec(43, struct.pack("<iiii", 0, 0, int(W * S), int(H * S))) # RECTANGLE
        e.rec(37, struct.pack("<I", 0x80000005))                      # NULL_BRUSH
        e.rec(40, struct.pack("<I", bg))
    fill_mode = None
    cur_clip = None
    for op in rd.ops:
        if op.clip != cur_clip:
            if cur_clip is not None:
                e.rec(34, struct.pack("<i", -1))                      # RESTOREDC
            if op.clip is not None:
                e.rec(33)                                             # SAVEDC
                x0, y0 = P(op.clip[0], op.clip[1])
                x1, y1 = P(op.clip[2], op.clip[3])
                e.rec(30, struct.pack("<iiii", x0, y0, x1, y1))       # INTERSECTCLIPRECT
            cur_clip = op.clip
        if isinstance(op, ImageOp):
            px = _decode_image(op, gray, max_px=3000).convert("RGB")
            W_, H_ = px.size
            raw = px.tobytes()
            stride = (W_ * 3 + 3) // 4 * 4
            rows = []
            for yy in range(H_ - 1, -1, -1):  # bottom-up DIB, BGR
                line = bytearray(raw[yy * W_ * 3:(yy + 1) * W_ * 3])
                line[0::3], line[2::3] = line[2::3], line[0::3]
                rows.append(bytes(line).ljust(stride, b"\0"))
            bits = b"".join(rows)
            bmi = struct.pack("<IiiHHIIiiII", 40, W_, H_, 1, 24, 0, len(bits), 3780, 3780, 0, 0)
            x0, y0 = P(op.x0, op.y0)
            x1, y1 = P(op.x1, op.y1)
            head = 8 + 16 + 24 + 16 + 8 + 8
            payload = struct.pack("<iiii", x0, y0, x1, y1) + struct.pack("<iiiiii", x0, y0, 0, 0, W_, H_) + \
                struct.pack("<IIII", head, len(bmi), head + len(bmi), len(bits)) + struct.pack("<II", 0, 0x00CC0020) + struct.pack("<ii", x1 - x0, y1 - y0)
            e.rec(81, payload + bmi + bits)                              # STRETCHDIBITS
            continue
        if isinstance(op, PathOp):
            pts_all = []
            body = []
            for sg in op.segs:
                if sg[0] == "M":
                    p = P(*sg[1])
                    pts_all.append(p)
                    body.append((27, struct.pack("<ii", *p)))         # MOVETOEX
                elif sg[0] == "L":
                    p = P(*sg[1])
                    pts_all.append(p)
                    body.append((54, struct.pack("<ii", *p)))         # LINETO
                elif sg[0] == "C":
                    ps = [P(*sg[1]), P(*sg[2]), P(*sg[3])]
                    pts_all += ps
                    body.append((5, _rect(ps) + struct.pack("<I", 3) + b"".join(struct.pack("<ii", *q) for q in ps)))  # POLYBEZIERTO
                else:
                    body.append((61, b""))                            # CLOSEFIGURE
            pen = brush = None
            if op.stroke:
                pen = e.handle()
                style = 0x10000 | 0x200 | 0x1000                       # PS_GEOMETRIC | ENDCAP_FLAT | JOIN_ROUND
                entries = [max(1, int(round(d * S))) for d in op.dash] if op.dash else []
                if entries:
                    style |= 7                                        # PS_USERSTYLE
                lp = struct.pack("<IIIIII", style, max(1, int(round(op.width * S))), 0, _colorref(op.stroke), 0, len(entries)) + b"".join(struct.pack("<I", v) for v in entries)
                e.rec(95, struct.pack("<IIIII", pen, 0, 0, 0, 0) + lp)  # EXTCREATEPEN
                e.rec(37, struct.pack("<I", pen))
            else:
                e.rec(37, struct.pack("<I", 0x80000008))
            if op.fill:
                brush = e.handle()
                e.rec(39, struct.pack("<IIII", brush, 0, _colorref(op.fill), 0))  # CREATEBRUSHINDIRECT
                e.rec(37, struct.pack("<I", brush))
                mode = 1 if op.evenodd else 2
                if mode != fill_mode:
                    e.rec(19, struct.pack("<I", mode))                # SETPOLYFILLMODE
                    fill_mode = mode
            else:
                e.rec(37, struct.pack("<I", 0x80000005))
            e.rec(59)                                                 # BEGINPATH
            for typ, pl in body:
                e.rec(typ, pl)
            e.rec(60)                                                 # ENDPATH
            r = _rect(pts_all)
            e.rec(63 if (op.fill and op.stroke) else 62 if op.fill else 64, r)
            for hnd in (pen, brush):
                if hnd:
                    e.rec(37, struct.pack("<I", 0x80000005 if hnd == brush else 0x80000008))
                    e.rec(40, struct.pack("<I", hnd))
        else:
            font = e.handle()
            face = {"sans": "Arial", "serif": "Times New Roman", "mono": "Courier New"}[op.family]
            esc = int(round(op.angle * 10))
            lf = struct.pack("<iiiiiBBBBBBBB", -int(round(op.size * S)), 0, esc, esc, 700 if op.bold else 400, 1 if op.italic else 0, 0, 0, 1, 0, 0, 4, 0)
            lf += face.encode("utf-16-le").ljust(64, b"\0")
            lf = lf.ljust(320, b"\0")                                 # LOGFONTW + empty EXTLOGFONT tail
            e.rec(82, struct.pack("<I", font) + lf)                   # EXTCREATEFONTINDIRECTW
            e.rec(37, struct.pack("<I", font))
            e.rec(24, struct.pack("<I", _colorref(op.color)))         # SETTEXTCOLOR
            text = op.text
            u = text.encode("utf-16-le")
            n = len(u) // 2
            x, y = P(op.x, op.y)
            wpx = text_width(text, op.size, op.bold)
            bounds = _rect([(x, y - op.size * S), (x + wpx * S, y + op.size * S * 0.3)])
            off_str = 8 + 16 + 4 + 8 + 40
            spad = (len(u) + 3) // 4 * 4
            off_dx = off_str + spad
            dx = b"".join(struct.pack("<i", int(round(text_width(ch, op.size, op.bold) * S))) for ch in text) if n == len(text) else \
                b"".join(struct.pack("<i", int(round(op.size * 0.55 * S))) for _ in range(n))
            emrtext = struct.pack("<iiIIIiiiiI", x, y, n, off_str, 0, 0, 0, -1, -1, off_dx)
            payload = bounds + struct.pack("<Iff", 1, 0.0, 0.0) + emrtext + u.ljust(spad, b"\0") + dx
            e.rec(84, payload)                                        # EXTTEXTOUTW
            e.rec(37, struct.pack("<I", 0x8000000D))                  # SYSTEM_FONT
            e.rec(40, struct.pack("<I", font))
    if cur_clip is not None:
        e.rec(34, struct.pack("<i", -1))
    e.rec(14, struct.pack("<III", 0, 16, 20))                         # EOF
    desc = (f"OpenPrism\0{title[:120]}\0\0").encode("utf-16-le")
    desc = desc.ljust((len(desc) + 3) // 4 * 4, b"\0")
    hdr_size = 108 + len(desc)
    body = b"".join(e.recs)
    n_bytes = hdr_size + len(body)
    frame = (0, 0, int(round(W * 2540 / 96)), int(round(H * 2540 / 96)))   # .01 mm
    header = struct.pack("<II", 1, hdr_size) + struct.pack("<iiii", 0, 0, int(round(W)) - 1, int(round(H)) - 1) + struct.pack("<iiii", *frame)
    header += struct.pack("<IIIIHHIIIiiiiIII", 0x464D4520, 0x10000, n_bytes, len(e.recs) + 1, e.handles, 0, len(desc) // 2, 108, 0,
                          960, 480, 254, 127, 0, 0, 0)
    header += struct.pack("<ii", 254000, 127000) + desc
    assert len(header) == hdr_size
    return header + body


def convert(svg_text, fmt, title="OpenPrism figure", gray=False, background=True):
    if fmt == "eps":
        return to_eps(svg_text, title, gray, background), "application/postscript", "eps"
    if fmt == "emf":
        return to_emf(svg_text, title, gray, background), "image/emf", "emf"
    raise ValueError("Unsupported format")


def _grayscale(ops):
    def g(c):
        if c is None:
            return None
        v = int(round(0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]))
        return (v, v, v)
    for op in ops:
        if isinstance(op, PathOp):
            op.fill, op.stroke = g(op.fill), g(op.stroke)
        elif isinstance(op, TextOp):
            op.color = g(op.color)  # images are converted pixel by pixel when written
