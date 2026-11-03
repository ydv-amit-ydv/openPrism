"""Shared helpers: result builder, P value formatting, multiple-comparison logic."""
from __future__ import annotations

import contextlib
import functools
import contextvars
import itertools
import math
import warnings

import numpy as np
from scipy import stats


class AnalysisError(ValueError):
    """Raised for user-facing problems (not enough data, wrong table type...)."""


def num(v, digits=4):
    """JSON-safe number (None for nan/inf)."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    if not math.isfinite(f):
        return None
    return round(f, 10) if abs(f) >= 1e-10 or f == 0 else f


_FULL = contextvars.ContextVar("openprism_full_precision", default=False)


@contextlib.contextmanager
def full_precision(on=True):
    """Within this context, results are reported with all significant digits (repr of the double)."""
    token = _FULL.set(bool(on))
    try:
        yield
    finally:
        _FULL.reset(token)


def fmt(v, digits=4):
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if math.isnan(f):
        return ""
    if math.isinf(f):
        return "∞" if f > 0 else "-∞"
    if f == 0:
        return "0"
    if _FULL.get():
        return str(int(f)) if f.is_integer() and abs(f) < 1e15 else repr(f)
    a = abs(f)
    if a >= 1e6 or a < 1e-4:
        return f"{f:.{digits}e}"
    if float(f).is_integer():
        return str(int(f))
    if a < 1:
        return f"{f:.{digits}g}"
    return f"{f:.{max(digits, int(math.log10(a)) + 1)}g}"


def fmt_p(p):
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return ""
    if _FULL.get():
        return repr(float(p))
    if p < 0.0001:
        return "<0.0001"
    if p < 0.001:
        return f"{p:.4f}"
    return f"{p:.4f}"


def stars(p, alpha=0.05):
    """GraphPad-style significance summary."""
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return ""
    if p >= alpha:
        return "ns"
    if p < 0.0001:
        return "****"
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    return "*"


def sig(p, alpha=0.05):
    return "Yes" if p is not None and p < alpha else "No"


class Result:
    """Structured analysis output understood by the front-end."""

    def __init__(self, title: str):
        self.title = title
        self.sections: list[dict] = []
        self.overlay: dict | None = None
        self.output_tables: list[dict] = []
        self.warnings: list[str] = []

    def kv(self, title: str, pairs):
        self.sections.append({"title": title, "kind": "kv",
                              "rows": [[k, fmt(v) if not isinstance(v, str) else v] for k, v in pairs]})
        return self

    def table(self, title: str, columns, rows):
        self.sections.append({"title": title, "kind": "table", "columns": list(columns),
                              "rows": [[fmt(c) if not isinstance(c, str) else c for c in r] for r in rows]})
        return self

    def warn(self, msg: str):
        self.warnings.append(msg)

    def to_dict(self):
        return {"title": self.title, "sections": self.sections, "overlay": self.overlay,
                "outputTables": self.output_tables, "warnings": self.warnings}


def require(cond, msg):
    if not cond:
        raise AnalysisError(msg)


def t_ci(mean, se, df, level=0.95):
    if df <= 0 or not np.isfinite(se):
        return (np.nan, np.nan)
    t = stats.t.ppf(0.5 + level / 2, df)
    return (mean - t * se, mean + t * se)


@contextlib.contextmanager
def quiet():
    """Context manager that silences numpy / scipy runtime warnings."""
    with warnings.catch_warnings(), np.errstate(all="ignore"):
        warnings.simplefilter("ignore")
        yield


# ---------------------------------------------------------------------------
# Multiple comparisons after ANOVA (pooled error term)
# ---------------------------------------------------------------------------

def holm_sidak(pvals):
    p = np.asarray(pvals, float)
    m = len(p)
    order = np.argsort(p)
    adj = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        a = 1 - (1 - p[idx]) ** (m - rank)
        running = max(running, a)
        adj[idx] = min(running, 1.0)
    return adj


def holm(pvals):
    p = np.asarray(pvals, float)
    m = len(p)
    order = np.argsort(p)
    adj = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p[idx])
        adj[idx] = min(running, 1.0)
    return adj


def bh_fdr(pvals):
    p = np.asarray(pvals, float)
    m = len(p)
    order = np.argsort(p)[::-1]
    adj = np.empty(m)
    running = 1.0
    for i, idx in enumerate(order):
        rank = m - i
        running = min(running, p[idx] * m / rank)
        adj[idx] = running
    return adj


MC_METHODS = {
    "tukey": "Tukey",
    "bonferroni": "Bonferroni",
    "sidak": "Šídák",
    "holm-sidak": "Holm-Šídák",
    "dunnett": "Dunnett (vs. control)",
    "fisher": "Fisher's LSD (uncorrected)",
    "bh": "Benjamini-Hochberg FDR",
    "bky": "Two-stage step-up FDR (Benjamini, Krieger & Yekutieli)",
    "games-howell": "Games-Howell",
    "t3": "Dunnett T3",
    "t2": "Tamhane T2",
    "holm": "Holm",
}


@functools.lru_cache(maxsize=256)
def tukey_q_crit(alpha, k, df):
    """Critical value of the studentized range. k = 2 reduces exactly to √2·t; otherwise the root is
    bracketed between the k = 2 value and the Bonferroni bound, which always enclose it (fast and exact)."""
    if k == 2:
        return math.sqrt(2) * stats.t.ppf(1 - alpha / 2, df)
    lo = math.sqrt(2) * stats.t.ppf(1 - alpha / 2, df)
    hi = math.sqrt(2) * stats.t.ppf(1 - alpha / (k * (k - 1)), df) * 1.0001
    from scipy import optimize
    return optimize.brentq(lambda q: stats.studentized_range.sf(q, k, df) - alpha, lo, hi, xtol=1e-12, rtol=1e-12)


def tukey_p(q, k, df):
    if k == 2:  # the studentized range of two means is √2·|t|
        return float(2 * stats.t.sf(q / math.sqrt(2), df))
    return float(stats.studentized_range.sf(q, k, df))


def pairwise_pooled(means, ns, names, mse, df, method="tukey", control=0, alpha=0.05,
                    pairs=None, family_size=None):
    """Pairwise comparisons of group means using a pooled variance (ANOVA MSE).

    Returns list of dicts: a, b, label, diff, lo, hi, p, stars.
    """
    k = len(means)
    if pairs is None:
        if method == "dunnett":
            pairs = [(control, j) for j in range(k) if j != control]
        else:
            pairs = list(itertools.combinations(range(k), 2))
    m = family_size or len(pairs)
    out = []
    raw = []
    for a, b in pairs:
        diff = means[a] - means[b]
        se = math.sqrt(mse * (1 / ns[a] + 1 / ns[b]))
        t = diff / se if se > 0 else np.inf
        raw.append(2 * stats.t.sf(abs(t), df))
        out.append({"a": a, "b": b, "diff": diff, "se": se, "t": t})

    if method == "tukey":
        q_crit = tukey_q_crit(alpha, k, df)
        for o in out:
            q = abs(o["diff"]) / (o["se"] / math.sqrt(2))
            o["p"] = tukey_p(q, k, df)
            h = q_crit * o["se"] / math.sqrt(2)
            o["lo"], o["hi"] = o["diff"] - h, o["diff"] + h
    elif method == "dunnett":
        res = _dunnett_from_summary(means, ns, mse, df, control, out, alpha)
        out = res
    else:
        if method == "bonferroni":
            adj = [min(1.0, p * m) for p in raw]
            a_ind = alpha / m
        elif method == "sidak":
            adj = [1 - (1 - p) ** m for p in raw]
            a_ind = 1 - (1 - alpha) ** (1 / m)
        elif method == "holm-sidak":
            adj = holm_sidak(raw)
            a_ind = 1 - (1 - alpha) ** (1 / m)
        elif method == "bh":
            adj = bh_fdr(raw)
            a_ind = alpha
        elif method == "bky":
            from .advanced import bky_fdr
            adj = bky_fdr(raw)
            a_ind = alpha
        elif method == "holm":
            adj = holm(raw)
            a_ind = alpha / m
        else:  # fisher LSD
            adj = raw
            a_ind = alpha
        tcrit = stats.t.ppf(1 - a_ind / 2, df)
        for o, p in zip(out, adj):
            o["p"] = float(p)
            o["lo"], o["hi"] = o["diff"] - tcrit * o["se"], o["diff"] + tcrit * o["se"]

    for o in out:
        o["label"] = f"{names[o['a']]} vs. {names[o['b']]}"
        o["stars"] = stars(o["p"], alpha)
    return out


def _dunnett_from_summary(means, ns, mse, df, control, out, alpha):
    """Dunnett many-to-one using the multivariate t distribution."""
    k = len(means)
    others = [j for j in range(k) if j != control]
    # correlation between comparisons
    n0 = ns[control]
    rho = np.empty((len(others), len(others)))
    for i, a in enumerate(others):
        for j, b in enumerate(others):
            if i == j:
                rho[i, j] = 1
            else:
                rho[i, j] = math.sqrt((ns[a] / (ns[a] + n0)) * (ns[b] / (ns[b] + n0)))
    try:
        mvt = stats.multivariate_t(loc=np.zeros(len(others)), shape=rho, df=df)
        rng = np.random.default_rng(12345)

        def p_two_sided(t):
            t = abs(t)
            return float(max(0.0, 1 - mvt.cdf(np.full(len(others), t), lower_limit=np.full(len(others), -t),
                                              random_state=rng)))

        # critical value by bisection
        lo, hi = 0.0, 20.0
        for _ in range(40):
            mid = (lo + hi) / 2
            if p_two_sided(mid) > alpha:
                lo = mid
            else:
                hi = mid
        crit = hi
    except Exception:  # pragma: no cover - fallback
        p_two_sided = None
        crit = stats.t.ppf(1 - alpha / (2 * len(others)), df)

    res = []
    for o in out:
        # reported as "Control vs. X": mean diff = control - X (Prism convention)
        diff = o["diff"]
        t = o["t"]
        p = p_two_sided(t) if p_two_sided else min(1.0, 2 * stats.t.sf(abs(t), df) * len(others))
        res.append({**o, "diff": diff, "p": p, "lo": diff - crit * o["se"], "hi": diff + crit * o["se"]})
    return res


def comparison_rows(comps, alpha=0.05):
    rows = []
    for c in comps:
        rows.append([c["label"], c["diff"], f"{fmt(c['lo'])} to {fmt(c['hi'])}" if c.get("lo") is not None else "",
                     sig(c["p"], alpha), c["stars"], fmt_p(c["p"])])
    return rows


COMPARISON_COLUMNS = ["Comparison", "Mean diff.", "95% CI of diff.", "Significant?", "Summary", "Adjusted P"]


def pairs_overlay(comps):
    return [{"a": c["a"], "b": c["b"], "p": c["p"], "stars": c["stars"]} for c in comps]
