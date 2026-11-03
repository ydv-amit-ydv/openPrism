"""Regenerate the generated parts of the manual from openprism/guide.py.

    python tools/build_manual.py

Writes, between marker comments in openprism/static/help/manual.html:
  * the complete test finder (goal → first-choice test → alternatives),
  * the analysis reference: one uniform card per analysis (what, when, data,
    how, results, assumptions, alternatives, references) — the same text the
    analysis dialog shows under "About this analysis",
  * sections on full screen / focus mode, the command palette, reproducibility
    and validation,
and the matching table-of-contents entries. Idempotent.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from openprism.guide import CHOOSER, G  # noqa: E402
from openprism.stats import ANALYSES  # noqa: E402

MANUAL = ROOT / "openprism/static/help/manual.html"
TYPES = {"xy": "XY", "column": "Column", "grouped": "Grouped", "contingency": "Contingency", "survival": "Survival", "parts": "Parts of whole",
         "multi": "Multiple variables", "nested": "Nested", "summary": "Summary data", "—": "—"}
FIELDS = [("what", "What it does"), ("when", "When to use it"), ("data", "Data layout"), ("how", "How to run it"),
          ("results", "Reading the results"), ("assume", "Assumptions"), ("alt", "Alternatives"), ("ref", "References")]

FEATURES = """
<section id="screen"><h2>Full screen, focus mode &amp; small screens</h2>
<p>OpenPrism works best with as much screen as possible. Click <b>⛶ Full screen</b> at the top right (or press <kbd>F11</kbd>, or <i>View → Full screen</i>).
The button then reads <b>⤡ Exit full screen</b>, and a small <i>Exit full screen</i> button stays in the bottom-right corner; <kbd>Esc</kbd> also leaves full screen.
</p>
<p><b>Focus mode</b> (<i>View → Focus mode</i>, <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>F</kbd>) hides the navigator and toolbar so tables, graphs and layouts get the whole
window — useful on laptops and when presenting. Menus, dialogs and pop-ups automatically fit inside short or narrow windows.</p>
</section>
<section id="palette"><h2>Command palette</h2>
<p>Press <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd> (or <i>View → Command palette</i>) and type a few letters of any command or analysis — “welch”, “export tiff”,
“kappa”, “full screen” — then <kbd>Enter</kbd>. Analyses can also be found by what they are used for (e.g. “agreement”, “rhythm”).</p>
</section>
<section id="test-wizard"><h2>Which test should I use? (guided)</h2>
<p><i>Analysis → Which test should I use?</i> (also the 🧭 toolbar button) lists research goals for the type of the current table. Type words describing your
goal to filter, then click a test to open it with the right settings. Blue buttons are first choices when assumptions hold; grey buttons are the alternatives for
non-Gaussian data, outliers or unequal SDs. The complete list is in the <a href="#test-finder">test finder</a> below.</p>
</section>
<section id="number-format"><h2>Number format (strict)</h2>
<p>Numbers use the mathematical format: an optional sign, digits, a decimal <b>point</b>, and optionally an exponent —
<code>12.5</code>, <code>-0.03</code>, <code>.5</code>, <code>1.2e-6</code>, <code>3E4</code>. Commas, spaces and other characters are <b>never</b>
interpreted: <code>1,5</code>, <code>1,234.5</code>, <code>1 000</code>, <code>12%</code> or <code>inf</code> are not numbers. Such cells are shaded red in
the grid (hover for an explanation), a message appears when they are pasted, and every analysis reports how many cells it ignored and shows examples.
This rule exists because spreadsheets in different countries write numbers differently, and silently guessing (reading <code>1,5</code> as 15 or as 1.5)
would corrupt results. When pasting from a spreadsheet that uses decimal commas, change its number format (or the system locale) to a decimal point first.
Cells are separated by tabs when pasting (as all spreadsheets copy them); CSV files are read with <i>Import</i>.</p>
</section>
<section id="formulas"><h2>Calculated columns</h2>
<p><i>Data → Add calculated column (formula)</i> adds a data set computed from the others, row by row (and replicate by replicate):
<code>(B - A) / A * 100</code>, <code>log10(C)</code>, <code>B / mean</code>… Refer to data sets by their letters. Operators: <code>+ - * / ^</code>
(with the usual precedence; <code>-A^2</code> is −(A²)); functions <code>log10, ln, log2, exp, sqrt, abs, round, floor, ceil, min, max, pow, logit, invlogit,
sin, cos, tan</code>; constants <code>pi, e</code>. A preview shows the first rows. The column recalculates whenever its inputs change; its cells cannot be
typed over (right-click the column header to edit the formula or convert it to ordinary values). Formulas are evaluated by a small parser — they can never run code.
Letters refer to positions: if you insert or delete data sets, check the formula.</p>
</section>
<section id="sharing"><h2>Sharing projects with colleagues</h2>
<p><i>File → Share a copy with a colleague</i> sends a copy of the open project to another user of the same server. The copy is encrypted in your
browser for your colleague's personal key, so the server — and its administrators — can neither read it nor redirect it. Your colleague finds it under
<i>File → Shared with me</i> and saves it as their own project (re-encrypted with their own key); later changes are not synchronized, so share again to send an update.
Pending shares can be withdrawn under <i>File → Shares I sent</i>.</p>
<p><b>Verifying keys.</b> The share dialog shows the recipient's key fingerprint. For sensitive data, ask your colleague to read the fingerprint shown in
their <i>Account</i> dialog and check that it matches. OpenPrism remembers the fingerprint and warns you if a colleague's key ever changes (which happens
after a password reset without the recovery key — or would happen if someone tried to intercept). Administrators can turn sharing off in the admin console.</p>
<p class="note"><b>Cryptography.</b> Each user has an ECDH P-256 key pair; the private key is stored on the server only encrypted with the user's data key.
A share is encrypted with a fresh AES-256-GCM key, which is wrapped for the recipient with an ephemeral ECDH key agreement and HKDF-SHA256.</p>
</section>
<section id="toolbar"><h2>Toolbar, menus &amp; keyboard</h2>
<p>The toolbar adapts to the window: <b>full</b> (icon above label), <b>compact</b> (one slim row; only the main buttons keep their labels) or
<b>icons only</b>, chosen automatically to fit; the ⇔ button at its right end (or <i>View → Toolbar</i>) fixes a size. Buttons that do not apply to the
current item are hidden, and the <i>Analyze</i> group offers the quick tests that fit the current table type (e.g. t test and ANOVA for column tables,
curve fit and linear regression for XY tables). Every button shows its keyboard shortcut in its tooltip.</p>
<p>Menus that do not fit the menu bar move into <b>More ▾</b>. Keyboard: <kbd>F10</kbd> opens the first menu, <kbd>←</kbd>/<kbd>→</kbd> switch menus,
<kbd>↑</kbd>/<kbd>↓</kbd> move, <kbd>Enter</kbd> runs, <kbd>Esc</kbd> closes.</p>
</section>
<section id="activity"><h2>Calculation activity &amp; speed</h2>
<p>The indicator in the top bar shows when work is going on — <i>“⚙ Computing: One-way ANOVA · 0.4 s”</i> with a spinner — and otherwise the
duration of the last calculation. Click it (or <i>View → Calculation activity log</i>) for the log of this session: every analysis, import, export and
graph summary with the time you waited, the time spent in the server's isolated calculation worker and the CPU time it used. Only names and timings are
logged, never data.</p>
<p>Speed: graph summary values (means, SD, SEM, CIs, medians, IQRs) are calculated directly in your browser, so graphs redraw instantly; they are tested
to agree with the server to 15 digits. Statistical tests run on the server, which loads all statistical libraries once at start-up so each calculation
starts immediately (typically 5–30 ms). Large data tables (thousands of rows) only render the visible rows, so scrolling and editing stay fast.</p>
</section>
<section id="newcomers"><h2>New to statistics? Start here</h2>
<p><b>Guided tour.</b> New accounts are offered a one-minute tour that walks through the four steps — data, analysis, graph, figure —
on a small example (you can keep or remove the example at the end). Replay it any time from <i>Help → Guided tour</i> or
<i>My account → Replay the guided tour</i>. Arrow keys move between steps, Esc ends the tour.</p>
<p><b>Examples.</b> The start page offers ready-made examples (three treatment groups, a dose-response curve, survival of two groups,
a two-factor experiment), each with its analysis and graph, so you can change values and watch everything update.</p>
<p><b>Smart import.</b> <i>Import</i> (or dragging a CSV/Excel file onto the window) looks at your columns and proposes how to arrange
them, explaining why in plain words and showing a preview — for example “<i>“Treatment” contains group names and “Weight” the measured
values; each group becomes one column</i>”. Files in <i>long format</i> (one row per measurement with a group column and a value column, the
usual export of Excel, REDCap or lab instruments) are rearranged automatically: one grouping column → groups side by side (Column table),
two grouping columns → rows × columns (Grouped table), two category columns → counts (Contingency table), a time column with a 0/1
event column → Survival table, columns named mean / SD / n → Summary data. Pick another option if the suggestion does not fit.
Numbers written with a decimal comma (1,5) are not reinterpreted: the import explains how to fix the file.</p>
<p><b>Recommended analyses.</b> The Analyze dialog starts with the analyses recommended for your data (e.g. three groups → one-way
ANOVA) and shows only the analyses that fit the table; specialist methods appear when you tick <i>Show advanced analyses</i>.
Every analysis has an <i>In plain words</i> box — the question it answers, an everyday example, and a check of whether it suits your
data (for instance “tick exactly two data sets” for a t test). The full description is under <i>About this analysis</i>.</p>
<p><b>Graph types explained.</b> Under <i>Graph type</i> each graph is described in one sentence (what it shows and when to use it).</p>
<p><b>Table types as pictures.</b> <i>New data table</i> shows each table type as a small example of what the data look like, with
everyday names: groups side by side (Column), X and Y values (XY), two ways of grouping (Grouped), counts in categories (Contingency),
time until an event (Survival), several variables per subject (Multiple variables)…</p>
</section>
<section id="interop"><h2>Exchanging data with GraphPad Prism</h2>
<p><i>File → Import CSV / Excel / GraphPad Prism</i> reads Prism XML project files (<code>.pzfx</code>; in Prism use <i>File → Save As</i> and choose
the .pzfx format). All data tables are imported with their type, replicate subcolumns, row titles, X values and excluded values; tables entered as
summary data (mean with SD/SEM and N) are imported as their means, with a warning. Prism's analyses and graphs are recreated in OpenPrism from the data.</p>
<p><i>File → Export all data tables to GraphPad Prism (.pzfx)</i> writes every data table to a .pzfx file that Prism opens, so colleagues who use
Prism can continue with your data.</p>
</section>
<section id="figures"><h2>Shapes, templates &amp; vector formats</h2>
<p><b>Shapes on layouts:</b> <i>Add to page → Shapes</i> adds lines, arrows (with heads at the end, start or both), rectangles, ellipses and
significance brackets. Choose colour, fill, line width, dashes and direction in the inspector; shapes move and resize like any item and are exported as
vectors. (Freehand drawing is intentionally not included.)</p>
<p><b>Images on layouts:</b> <i>Add to page → Add image</i> places a PNG or JPEG (microscopy images, blots, photos, schematics) on the page. It moves and
resizes like any item, keeps its proportions unless you choose <i>Stretch</i>, and is stored inside the encrypted project (very large images are
downscaled to 3000 pixels, enough for 600 dpi at 5 inches). Images are included in every export format, including PDF, EPS and EMF.</p>
<p><b>Style templates:</b> format a graph, click <i>★ Save as template</i>, then apply it to any graph — or to all graphs of the same table type — from
<i>Templates…</i>. Templates keep fonts, colours, symbols, axes and sizes, not titles or data. Use <i>Export all…</i> / <i>Import…</i> to share a lab or
journal style as a small JSON file.</p>
<p><b>EPS and EMF:</b> besides TIFF, PNG, JPEG, WEBP, PDF and SVG, graphs and layouts export as <b>EPS</b> (Encapsulated PostScript — Illustrator,
CorelDRAW, LaTeX, printers) and <b>EMF</b> (Windows Enhanced Metafile — Word, PowerPoint, Visio). Both stay fully vector with editable text. These formats
have no transparency, so semi-transparent fills (e.g. confidence bands) are blended with white and drawn beneath lines and symbols.</p>
</section>
<section id="reproducibility"><h2>Reproducibility, all digits &amp; methods text</h2>
<p>Every result ends with a <b>🔁 Reproducible</b> line: OpenPrism, NumPy, SciPy and statsmodels versions and a SHA-256 fingerprint of the analysed data.
The same data and settings always give bit-identical results — resampling methods (bootstrap, permutation and Monte-Carlo exact tests, k-means) use fixed seeds.</p>
<p><b>All digits</b> in the results header shows every significant digit (15–17) instead of rounded values — useful for checking against other software.
<b>📝 Methods</b> produces a paragraph for the methods section of a paper with the test, its settings, the software versions and the data fingerprint.</p>
<p>Numerical care built in: values with a large constant part (e.g. 1 000 000 000 000.4) are centred in exact decimal arithmetic before analysis; polynomial and
ill-conditioned regressions are solved from the exact decimal data in 80-digit arithmetic; the curve fitter tries several algorithms and keeps the best fit.</p>
</section>
<section id="validation"><h2>Validation of results</h2>
<p>OpenPrism's statistics are checked automatically against (1) NIST Statistical Reference Datasets with certified values, (2) R and established CRAN packages
(survival, MASS, metafor, psych, car, lmtest, quantreg, circular, nlme, coin), (3) Monte-Carlo calibration of type I error and confidence-interval coverage and
(4) reproducibility and invariance tests — about 700 checks. See the <a href="validation.html">validation report</a> (also under <i>Help</i>) for every value,
the number of correct digits (LRE) and the problems the suite found and that were fixed. Anyone can rerun it: <code>python validation/run_validation.py</code>.</p>
<p class="note"><b>Still validate for regulated work.</b> No validation suite covers every situation. For regulated (GLP/GMP, clinical) use, validate the analyses
you rely on against your reference software and keep the validation report with your records.</p>
</section>
"""


def esc(s):
    return html.escape(s or "")


def link_tests(text):
    return esc(text)


def finder():
    rows = "".join(f"<tr><td>{esc(goal)}</td><td>{esc(TYPES.get(tt, tt))}</td><td><b>{esc(main)}</b></td><td>{esc(alt)}</td></tr>" for goal, main, alt, tt in CHOOSER)
    return (f'<section id="test-finder"><h2>Test finder: every goal, every test</h2>'
            f'<p>First choice when its assumptions hold, and the alternatives when they do not (non-Gaussian data, outliers, unequal SDs, ordinal data). '
            f'Each test is described in the <a href="#analysis-reference">analysis reference</a>. In the app, use <a href="#test-wizard">Which test should I use?</a>.</p>'
            f'<table><tr><th>Goal</th><th>Table</th><th>First choice</th><th>Alternatives</th></tr>{rows}</table></section>\n')


def reference(existing_ids):
    cats = {}
    for key, (fn, label, cat, types) in ANALYSES.items():
        cats.setdefault(cat, []).append((key, label, types))
    parts = ['<section id="analysis-reference"><h2>Analysis reference</h2><p>One card per analysis, in the same format: what it does, when to use it, '
             'how to lay out the data, how to run it, how to read the results, assumptions, alternatives and key references. The same text appears in each '
             'analysis dialog under <i>About this analysis</i>. Detailed chapters, where available, are linked from the card.</p>']
    toc = ['<li class="h">Analysis reference</li>', '<li><a href="#analysis-reference">All analyses (A–Z by group)</a></li>']
    for cat, items in cats.items():
        parts.append(f"<h3>{esc(cat)}</h3>")
        for key, label, types in items:
            gd = G.get(key, {})
            anchor = "" if key in existing_ids else f'<a id="{key}"></a>'
            more = f' <a href="#{key}">Detailed chapter →</a>' if key in existing_ids else ""
            rows = "".join(f"<tr><th>{lab}</th><td>{esc(gd.get(f))}</td></tr>" for f, lab in FIELDS if gd.get(f))
            parts.append(f'<div class="refcard" id="ref-{key}">{anchor}<h4>{esc(label)}</h4>'
                         f'<p class="hint">Table types: {esc(", ".join(TYPES.get(t, t) for t in types))} · menu: Analysis → {esc(label)}{more}</p>'
                         f'<table class="ref">{rows}</table></div>')
            toc.append(f'<li class="sub"><a href="#ref-{key}">{esc(label.split(" (")[0])}</a></li>')
    parts.append("</section>\n")
    return "".join(parts), toc


def replace_block(s, name, content):
    start, end = f"<!-- GENERATED:{name} -->", f"<!-- /GENERATED:{name} -->"
    block = f"{start}\n{content}\n{end}"
    if start in s:
        return re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _m: block, s, flags=re.S)
    return None


def main():
    s = MANUAL.read_text()
    s_wo = re.sub(r"<!-- GENERATED:(\w+) -->.*?<!-- /GENERATED:\1 -->", "", s, flags=re.S)
    existing = set(re.findall(r'<section id="([\w-]+)"', s_wo))
    ref_html, ref_toc = reference(existing)
    body = FEATURES + finder() + ref_html
    toc = "\n    ".join(['<li class="h">Working faster &amp; reproducibly</li>', '<li><a href="#screen">Full screen &amp; focus mode</a></li>',
                         '<li><a href="#number-format">Number format (strict)</a></li>', '<li><a href="#formulas">Calculated columns</a></li>',
                         '<li><a href="#sharing">Sharing projects with colleagues</a></li>', '<li><a href="#toolbar">Toolbar, menus &amp; keyboard</a></li>', '<li><a href="#activity">Calculation activity &amp; speed</a></li>',
                         '<li><a href="#newcomers">New to statistics? Start here</a></li>', '<li><a href="#interop">Exchanging data with Prism (.pzfx)</a></li>', '<li><a href="#figures">Shapes, templates, EPS &amp; EMF</a></li>',
                         '<li><a href="#palette">Command palette</a></li>', '<li><a href="#test-wizard">Which test should I use?</a></li>',
                         '<li><a href="#reproducibility">Reproducibility &amp; all digits</a></li>', '<li><a href="#validation">Validation of results</a></li>',
                         '<li><a href="#test-finder">Test finder (complete)</a></li>'] + ref_toc)
    new = replace_block(s, "body", body)
    if new is None:
        anchor = '<section id="analyze">'
        new = s.replace(anchor, f"<!-- GENERATED:body -->\n{body}\n<!-- /GENERATED:body -->\n" + anchor, 1)
    s = new
    new = replace_block(s, "toc", "    " + toc)
    if new is None:
        i = s.index('<li><a href="#choosing-a-test">')
        j = s.index("</li>", i) + 5
        new = s[:j] + f"\n<!-- GENERATED:toc -->\n    {toc}\n<!-- /GENERATED:toc -->" + s[j:]
    s = new
    if ".refcard" not in s:
        s = s.replace("</style>", ".refcard { border: 1px solid var(--border); border-radius: 10px; padding: 4px 14px 2px; margin: 14px 0; scroll-margin-top: 10px; }\n"
                      ".refcard h4 { margin: 10px 0 0; font-size: 16px; } .refcard .hint { color: var(--muted); font-size: 12.5px; margin: 2px 0 6px; }\n"
                      "table.ref { width: 100%; font-size: 13.5px; } table.ref th { width: 150px; white-space: nowrap; }\nnav li.sub a { padding-left: 16px; font-size: 12.5px; }\n</style>", 1)
    MANUAL.write_text(s)
    ids = re.findall(r'id="([\w-]+)"', s)
    dup = {i for i in ids if ids.count(i) > 1}
    broken = set(re.findall(r'href="#([\w-]+)"', s)) - set(ids)
    print(f"manual: {len(G)} reference cards; duplicate ids: {sorted(dup) or 'none'}; broken links: {sorted(broken) or 'none'}")
    return 1 if dup or broken else 0


if __name__ == "__main__":
    sys.exit(main())
