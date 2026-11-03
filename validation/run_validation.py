"""Run the complete validation suite and write the reports.

    python validation/run_validation.py [--reps 2000]

Outputs
    validation/results.json                    every check, machine-readable
    docs/VALIDATION.md                         report for the repository
    openprism/static/help/validation.html      the same report inside the app (Help → Validation report)

Suites
    nist             NIST StRD certified values (univariate, ANOVA, linear and nonlinear regression)
    r                R 4.x and CRAN reference packages (reference_r.json, regenerate with reference.R)
    calibration      Monte-Carlo type I error, CI coverage and power (fixed seed)
    reproducibility  determinism across runs/processes and metamorphic invariances
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import platform
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(ROOT), str(HERE)]

import calibration  # noqa: E402
import nist  # noqa: E402
import rcases  # noqa: E402
import reproducibility  # noqa: E402

SUITES = {
    "nist": ("Accuracy: NIST Statistical Reference Datasets", nist.run_all),
    "r": ("Agreement with R and established CRAN packages", rcases.run_all),
    "calibration": ("Statistical calibration (Monte-Carlo)", None),
    "reproducibility": ("Reproducibility and invariance", reproducibility.run_all),
}


def versions():
    import numpy
    import scipy
    import statsmodels

    from openprism import __version__
    return {"OpenPrism": __version__, "Python": platform.python_version(), "NumPy": numpy.__version__, "SciPy": scipy.__version__,
            "statsmodels": statsmodels.__version__, "Platform": f"{platform.system()} {platform.machine()}",
            "R reference": f"{rcases.REF['R']} (generated {rcases.REF['generated']})",
            "R packages": _packages()}


def _packages():
    pk = rcases.REF["packages"]
    if isinstance(pk, list):  # jsonlite exports the named vector as an array, in this order
        pk = dict(zip(["survival", "MASS", "metafor", "psych", "car", "lmtest", "quantreg", "circular", "nlme", "coin"], pk))
    return ", ".join(f"{k} {v}" for k, v in pk.items())


def run(reps):
    results = {}
    for key, (title, fn) in SUITES.items():
        t0 = time.time()
        checks = calibration.run_all(reps) if key == "calibration" else fn()
        results[key] = {"title": title, "checks": checks, "seconds": round(time.time() - t0, 1)}
        print(f"{title}: {sum(c['pass'] for c in checks)}/{len(checks)} passed ({results[key]['seconds']} s)", flush=True)
    return results


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.10g}"
    return str(v)


def summary_rows(results):
    rows = []
    for key, s in results.items():
        ch = s["checks"]
        lres = [c["lre"] for c in ch if isinstance(c.get("lre"), (int, float))]
        rows.append((s["title"], len(ch), sum(c["pass"] for c in ch),
                     f"{statistics.median(lres):.1f}" if lres else "—", f"{min(lres):.1f}" if lres else "—"))
    return rows


INTRO = """OpenPrism's statistical results were evaluated in four independent ways:

1. **Accuracy against certified values.** The NIST Statistical Reference Datasets (StRD) give certified results computed with
   500-digit arithmetic for deliberately difficult problems: univariate statistics, one-way ANOVA, linear regression (including the
   ill-conditioned 10th-degree Filip polynomial and the Longley data) and 26 nonlinear regression problems, each from two starting points.
   Accuracy is reported as the log relative error (LRE), the number of correct significant digits (McCullough 1998, 1999).
2. **Agreement with R.** About 290 results from base R 4.x and established CRAN packages (survival, MASS, metafor, psych, car,
   lmtest, quantreg, circular, nlme, coin) on classic datasets. Where R itself is known to be inexact (root-finding tolerances,
   `1 − pchisq()` cancellation, coarse numerical Hessians), the result is additionally checked against its *defining equation*
   evaluated in exact or 50-digit arithmetic.
3. **Statistical calibration.** Monte-Carlo simulation through the application's own code: tests must reject at the nominal
   rate when the null hypothesis is true, and 95% confidence intervals must cover the true value 95% of the time.
4. **Reproducibility.** Every analysis gives bit-identical output when repeated and in a fresh process (resampling methods use
   fixed seeds), and invariances that must hold mathematically (shift, scale, ordering, relabelling) hold to ≥ 9 digits.

All checks run through `openprism.stats.run`, the same code path the application uses, with full-precision output.
Rerun everything with `python validation/run_validation.py`; the automated test-suite runs the same checks.
"""

FINDINGS = """While building this suite the following problems were found **and fixed**:

* Derived data tables (outputs of transforms, normalization, residuals…) were stored with only 6 significant digits; they now keep 15.
* Data with a large constant part (e.g. 1 000 000 000 000.4) lost up to 10 digits in ANOVA, t tests and SDs, because such numbers
  cannot be held exactly in binary. Values are now centred on a common offset in exact decimal arithmetic before conversion
  (NIST SmLs07–09: from 3 to 15 correct digits).
* Polynomial and ill-conditioned multiple regression lost all digits on NIST Filip. These fits are now solved from the exact
  decimal data in 80-digit arithmetic (Filip: from 0 to ≥ 10.5 digits for every coefficient).
* The nonlinear fitter failed to converge on two NIST problems from the first starting values and stopped early on others.
  It now combines Levenberg-Marquardt and a trust-region method and keeps the best solution: all 52 NIST nonlinear fits converge
  to the certified solution (≥ 5 digits for every parameter, median 8.5).
* Mann-Whitney and Wilcoxon P values were labelled "exact" when ties forced an approximation; both now compute the exact
  conditional distribution with ties (as StatXact / R `coin`) and label the method truthfully.
* The Peto-Peto weighted log-rank test used Peto's survival estimate at the previous event time instead of the current one
  (Klein & Moeschberger §7.3); it now agrees with an independent implementation to 15 digits.
* The aligned-rank-transform ANOVA could break ties between values that are equal in exact arithmetic but differ by one unit
  in the last place after alignment; aligned values are now rounded to 12 significant digits before ranking (ARTool agreement:
  from 2.5 to 14.7 digits).
* Numbers were parsed leniently ("1,5" was read as 15). Only the strict mathematical format is now accepted (decimal point, no
  thousands separators); anything else is flagged and reported, never reinterpreted.
"""


def write_markdown(results, vers, path):
    lines = ["# Validation report", "", f"*Generated {dt.date.today().isoformat()} by `validation/run_validation.py`.*", "", INTRO, "## Summary", "",
             "| Suite | Checks | Passed | Median LRE | Minimum LRE |", "| --- | ---: | ---: | ---: | ---: |"]
    for t, n, p, med, mn in summary_rows(results):
        lines.append(f"| {t} | {n} | {p} | {med} | {mn} |")
    total = sum(len(s["checks"]) for s in results.values())
    passed = sum(c["pass"] for s in results.values() for c in s["checks"])
    lines += ["", f"**{passed} of {total} checks passed.** LRE = number of correct significant digits (15 = identical in double precision).", "",
              "## Problems found and fixed", "", FINDINGS, "## Software", ""]
    lines += [f"* **{k}:** {v}" for k, v in vers.items()]
    for key, s in results.items():
        lines += ["", f"## {s['title']}", ""]
        areas = {}
        for c in s["checks"]:
            areas.setdefault(c["area"], []).append(c)
        for area, chk in areas.items():
            lres = [c["lre"] for c in chk if isinstance(c.get("lre"), (int, float))]
            stat = f" — LRE min {min(lres):.1f}, median {statistics.median(lres):.1f}" if lres else ""
            lines += [f"### {area} ({sum(c['pass'] for c in chk)}/{len(chk)} passed{stat})", "",
                      "| Case | Quantity | Reference | OpenPrism | LRE | Required | Pass | Note |", "| --- | --- | ---: | ---: | ---: | ---: | :---: | --- |"]
            for c in chk:
                note = (c.get("note") or "").replace("|", "\\|")
                src = c.get("source", "")
                lines.append(f"| {c['case']} | {c['quantity']} | {_fmt(c['reference'])} | {_fmt(c['value'])} | {_fmt(c.get('lre'))} | {c['required']} | "
                             f"{'✓' if c['pass'] else '✗'} | {note}{' — ' if note and src else ''}{src} |")
            lines.append("")
    lines += ["## References", "",
              "* McCullough, B. D. (1998). Assessing the reliability of statistical software: Part I. *The American Statistician* 52, 358–366.",
              "* McCullough, B. D. (1999). Assessing the reliability of statistical software: Part II. *The American Statistician* 53, 149–159.",
              "* NIST Statistical Reference Datasets, https://www.itl.nist.gov/div898/strd/",
              "* R Core Team. R: A language and environment for statistical computing. R Foundation for Statistical Computing, Vienna."]
    Path(path).write_text("\n".join(lines) + "\n")


def write_html(results, vers, path):
    def esc(s):
        return html.escape(str(s))
    total = sum(len(s["checks"]) for s in results.values())
    passed = sum(c["pass"] for s in results.values() for c in s["checks"])
    import re
    md_bold = lambda s: re.sub(r"(?<![*])[*]([^*]+)[*](?![*])", r"<i>\1</i>", re.sub(r"[*][*](.+?)[*][*]", r"<b>\1</b>", re.sub(r"`([^`]+)`", r"<code>\1</code>", esc(s))))  # noqa: E731
    intro = "".join(f"<p>{md_bold(p)}</p>" for p in INTRO.strip().split("\n\n")[:1])
    items = re.findall(r"^\d\. (.+?)(?=^\d\. |\n\n|\Z)", INTRO, re.S | re.M)
    intro += "<ol>" + "".join(f"<li>{md_bold(' '.join(i.split()))}</li>" for i in items) + "</ol>"
    intro += f"<p>{md_bold(INTRO.strip().split(chr(10) + chr(10))[-1])}</p>"
    fixes = "<ul>" + "".join(f"<li>{md_bold(' '.join(x.split()))}</li>" for x in re.findall(r"^\* (.+?)(?=^\* |\Z)", FINDINGS, re.S | re.M)) + "</ul>"
    nav = []
    body = [f'<h1 class="title">Validation report</h1><p class="lead">OpenPrism {esc(vers["OpenPrism"])} · generated {dt.date.today().isoformat()} · '
            f'<b>{passed} of {total} checks passed</b></p>', intro,
            '<table><tr><th>Suite</th><th>Checks</th><th>Passed</th><th>Median LRE</th><th>Minimum LRE</th></tr>' +
            "".join(f"<tr><td>{esc(t)}</td><td>{n}</td><td>{p}</td><td>{med}</td><td>{mn}</td></tr>" for t, n, p, med, mn in summary_rows(results)) + "</table>",
            '<section id="fixed"><h2>Problems found and fixed</h2><p>' + md_bold(FINDINGS.split(chr(10))[0]) + "</p>" + fixes + "</section>",
            '<section id="software"><h2>Software</h2><table>' + "".join(f"<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in vers.items()) + "</table></section>"]
    nav += ['<li><a href="#fixed">Problems found and fixed</a></li>', '<li><a href="#software">Software</a></li>']
    for key, s in results.items():
        nav.append(f'<li class="h">{esc(s["title"])}</li>')
        areas = {}
        for c in s["checks"]:
            areas.setdefault(c["area"], []).append(c)
        body.append(f'<h2>{esc(s["title"])}</h2>')
        for area, chk in areas.items():
            aid = key + "-" + re.sub(r"[^a-z0-9]+", "-", area.lower()).strip("-")
            ok = sum(c["pass"] for c in chk)
            nav.append(f'<li><a href="#{aid}">{esc(area)} <span class="cnt">{ok}/{len(chk)}</span></a></li>')
            lres = [c["lre"] for c in chk if isinstance(c.get("lre"), (int, float))]
            stat = f" · LRE min {min(lres):.1f}, median {statistics.median(lres):.1f}" if lres else ""
            rows = "".join(
                f'<tr class="{"ok" if c["pass"] else "bad"}"><td>{esc(c["case"])}</td><td>{esc(c["quantity"])}</td><td class="n">{esc(_fmt(c["reference"]))}</td>'
                f'<td class="n">{esc(_fmt(c["value"]))}</td><td class="n">{esc(_fmt(c.get("lre")))}</td><td class="n">{esc(c["required"])}</td>'
                f'<td class="c">{"✓" if c["pass"] else "✗"}</td><td class="s">{esc(c.get("note") or "")}<br><span>{esc(c.get("source", ""))}</span></td></tr>' for c in chk)
            body.append(f'<section id="{aid}"><h3>{esc(area)} — {ok}/{len(chk)} passed{stat}</h3><div class="wrap"><table class="v"><tr><th>Case</th><th>Quantity</th>'
                        f'<th>Reference</th><th>OpenPrism</th><th>LRE</th><th>Required</th><th></th><th>Note / source</th></tr>{rows}</table></div></section>')
    css = (Path(ROOT / "openprism/static/help/manual.html").read_text().split("<style>")[1].split("</style>")[0])
    css += """
table.v { font-size: 12.5px; } table.v td.n { font-family: ui-monospace, Menlo, Consolas, monospace; text-align: right; white-space: nowrap; }
table.v td.c { text-align: center; font-weight: 700; } tr.ok td.c { color: #1b8a4a; } tr.bad td.c, tr.bad td { color: #c0392b; }
table.v td.s { color: var(--muted); font-size: 12px; } table.v td.s span { font-style: italic; }
.wrap { overflow-x: auto; } nav .cnt { float: right; color: var(--muted); font-size: 11px; }
"""
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenPrism validation report</title><style>{css}</style></head>
<body><nav><h1>Validation</h1><div class="sub"><a href="manual.html">← Manual</a></div><ol>{''.join(nav)}</ol></nav>
<main>{''.join(body)}</main></body></html>
"""
    Path(path).write_text(page)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=2000, help="Monte-Carlo samples per calibration check")
    args = ap.parse_args()
    import warnings
    warnings.simplefilter("ignore")
    vers = versions()
    results = run(args.reps)
    (HERE / "results.json").write_text(json.dumps({"versions": vers, "generated": dt.datetime.now().isoformat(timespec="seconds"), "suites": results},
                                                  indent=1, default=str))
    write_markdown(results, vers, ROOT / "docs/VALIDATION.md")
    write_html(results, vers, ROOT / "openprism/static/help/validation.html")
    total = sum(len(s["checks"]) for s in results.values())
    passed = sum(c["pass"] for s in results.values() for c in s["checks"])
    print(f"{passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
