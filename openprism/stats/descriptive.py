"""Descriptive statistics, normality tests, outliers, frequency distributions."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from ..tables import make_table
from .common import AnalysisError, Result, fmt, fmt_p, num, quiet, require, sig, stars, t_ci


def selected(table, params):
    idx = params.get("datasets")
    if not idx:
        idx = table.nonempty_datasets()
    return [int(i) for i in idx if 0 <= int(i) < len(table.Y) and np.isfinite(table.Y[int(i)]).any()]


def summarize(v: np.ndarray, level=0.95) -> dict:
    """Summary statistics of a 1-D array of finite values."""
    n = len(v)
    d = {"n": n}
    if n == 0:
        return d
    with quiet():
        mean = float(np.mean(v))
        sd = float(np.std(v, ddof=1)) if n > 1 else np.nan
        sem = sd / math.sqrt(n) if n > 1 else np.nan
        lo, hi = t_ci(mean, sem, n - 1, level) if n > 1 else (np.nan, np.nan)
        q1, med, q3 = np.percentile(v, [25, 50, 75], method="weibull") if n > 1 else (v[0], v[0], v[0])
        d.update(
            mean=mean, sd=sd, sem=sem, ci_lo=lo, ci_hi=hi, median=float(med), q1=float(q1), q3=float(q3),
            min=float(np.min(v)), max=float(np.max(v)), range=float(np.ptp(v)), sum=float(np.sum(v)),
            cv=(sd / mean * 100) if mean != 0 and n > 1 else np.nan,
        )
        if np.all(v > 0):
            lv = np.log(v)
            gm = math.exp(lv.mean())
            gsd = math.exp(lv.std(ddof=1)) if n > 1 else np.nan
            d.update(gmean=gm, gsd=gsd)
        else:
            d.update(gmean=np.nan, gsd=np.nan)
        d["skew"] = float(stats.skew(v, bias=False)) if n > 2 else np.nan
        d["kurt"] = float(stats.kurtosis(v, bias=False)) if n > 3 else np.nan
        # 95% CI of the median (binomial / order statistic method)
        if n >= 3:
            s = np.sort(v)
            j = max(1, int(stats.binom.ppf(0.025, n, 0.5)))
            d["med_lo"], d["med_hi"] = float(s[j - 1]), float(s[n - j])
        else:
            d["med_lo"] = d["med_hi"] = np.nan
    return d


ROWS = [
    ("Number of values", "n"), ("Minimum", "min"), ("25% Percentile", "q1"), ("Median", "median"),
    ("75% Percentile", "q3"), ("Maximum", "max"), ("Range", "range"),
    ("95% CI of median (lower)", "med_lo"), ("95% CI of median (upper)", "med_hi"),
    ("Mean", "mean"), ("Std. Deviation", "sd"), ("Std. Error of Mean", "sem"),
    ("Lower 95% CI of mean", "ci_lo"), ("Upper 95% CI of mean", "ci_hi"),
    ("Coefficient of variation (%)", "cv"), ("Geometric mean", "gmean"),
    ("Geometric SD factor", "gsd"), ("Skewness", "skew"), ("Kurtosis", "kurt"), ("Sum", "sum"),
]


def descriptive(table, params):
    idx = selected(table, params)
    require(idx, "No data to analyze.")
    level = float(params.get("ci", 0.95))
    summaries = []
    for i in idx:
        d = summarize(table.column_values(i), level)
        off, (dev,) = table.shifted([i])
        if len(dev) > 1:
            # spread statistics from exactly-shifted values (full precision for large offsets)
            sd = float(np.std(dev, ddof=1))
            mean = off + float(np.mean(dev))
            lo, hi = t_ci(mean, sd / math.sqrt(len(dev)), len(dev) - 1, level)
            d.update(mean=mean, sd=sd, sem=sd / math.sqrt(len(dev)), ci_lo=lo, ci_hi=hi,
                     cv=sd / mean * 100 if mean != 0 else np.nan)
        summaries.append(d)
    r = Result("Descriptive statistics")
    r.table("Column statistics", [""] + [table.names[i] for i in idx],
            [[lab] + [s.get(key, np.nan) for s in summaries] for lab, key in ROWS])
    return r


def normality(table, params):
    idx = selected(table, params)
    require(idx, "No data to analyze.")
    alpha = float(params.get("alpha", 0.05))
    r = Result("Normality and lognormality tests")
    tests = params.get("tests") or ["shapiro", "dagostino", "ks", "anderson"]
    lognormal = params.get("lognormal", False)
    rows = []
    for i in idx:
        v = table.column_values(i)
        variants = [("", v)]
        if lognormal and np.all(v > 0):
            variants.append((" (log)", np.log10(v)))
        for suffix, vv in variants:
            name = table.names[i] + suffix
            n = len(vv)
            if "shapiro" in tests:
                if n >= 3:
                    w, p = stats.shapiro(vv)
                    rows.append([name, "Shapiro-Wilk", f"W = {fmt(w)}", fmt_p(p), ("Yes" if p >= alpha else "No"), n])
                else:
                    rows.append([name, "Shapiro-Wilk", "n too small", "", "", n])
            if "dagostino" in tests:
                if n >= 8:
                    k2, p = stats.normaltest(vv)
                    rows.append([name, "D'Agostino & Pearson", f"K2 = {fmt(k2)}", fmt_p(p), ("Yes" if p >= alpha else "No"), n])
                else:
                    rows.append([name, "D'Agostino & Pearson", "n too small (needs ≥ 8)", "", "", n])
            if "ks" in tests and n >= 5:
                from statsmodels.stats.diagnostic import lilliefors
                with quiet():
                    ks, p = lilliefors(vv, dist="norm")
                rows.append([name, "Kolmogorov-Smirnov (Lilliefors)", f"KS = {fmt(ks)}", fmt_p(p), ("Yes" if p >= alpha else "No"), n])
            if "anderson" in tests and n >= 8:
                with quiet():
                    a = stats.anderson(vv, dist="norm")
                a2 = a.statistic
                a2s = a2 * (1 + 0.75 / n + 2.25 / n ** 2)
                if a2s >= 0.6:
                    p = math.exp(1.2937 - 5.709 * a2s + 0.0186 * a2s ** 2)
                elif a2s >= 0.34:
                    p = math.exp(0.9177 - 4.279 * a2s - 1.38 * a2s ** 2)
                elif a2s >= 0.2:
                    p = 1 - math.exp(-8.318 + 42.796 * a2s - 59.938 * a2s ** 2)
                else:
                    p = 1 - math.exp(-13.436 + 101.14 * a2s - 223.73 * a2s ** 2)
                p = min(max(p, 0.0), 1.0)
                rows.append([name, "Anderson-Darling", f"A2* = {fmt(a2s)}", fmt_p(p), ("Yes" if p >= alpha else "No"), n])
            if "jb" in tests and n >= 8:
                jb, p = stats.jarque_bera(vv)
                rows.append([name, "Jarque-Bera (skewness & kurtosis)", f"JB = {fmt(jb)}", fmt_p(p), ("Yes" if p >= alpha else "No"), n])
            if "sf" in tests and 5 <= n <= 5000:
                w = _shapiro_francia(vv)
                rows.append([name, "Shapiro-Francia", f"W' = {fmt(w[0])}", fmt_p(w[1]), ("Yes" if w[1] >= alpha else "No"), n])
    r.table("Tests for normal distribution", ["Data set", "Test", "Statistic", "P value", "Passed normality?", "N"], rows)
    r.warn(f"'Passed' means the P value is ≥ {alpha}: no evidence the data deviate from a Gaussian distribution.")
    from .multivariate import qq_overlay
    r.overlay = qq_overlay(table, idx)
    return r


def one_sample(table, params):
    idx = selected(table, params)
    require(idx, "No data to analyze.")
    mu = float(params.get("mu", 0))
    use_wilcoxon = params.get("test", "t") == "wilcoxon"
    alpha = float(params.get("alpha", 0.05))
    r = Result("One sample Wilcoxon signed rank test" if use_wilcoxon else "One sample t test")
    cols = [""] + [table.names[i] for i in idx]
    rows = {k: [] for k in ["Theoretical", "Actual", "N", "Statistic", "P value", "Summary", "Significant?",
                            "Discrepancy", "95% CI of discrepancy", "df"]}
    for i in idx:
        v = table.column_values(i)
        require(len(v) >= 2, f"{table.names[i]}: need at least 2 values.")
        rows["N"].append(len(v))
        if use_wilcoxon:
            med = float(np.median(v))
            res = stats.wilcoxon(v - mu)
            p = float(res.pvalue)
            rows["Theoretical"].append(f"median {mu}")
            rows["Actual"].append(med)
            rows["Statistic"].append(f"W = {res.statistic:g}")
            rows["Discrepancy"].append(med - mu)
            rows["95% CI of discrepancy"].append("")
            rows["df"].append("")
        else:
            res = stats.ttest_1samp(v, mu)
            p = float(res.pvalue)
            m = v.mean()
            se = v.std(ddof=1) / math.sqrt(len(v))
            lo, hi = t_ci(m - mu, se, len(v) - 1)
            rows["Theoretical"].append(f"mean {mu}")
            rows["Actual"].append(m)
            rows["Statistic"].append(f"t = {res.statistic:.4f}")
            rows["Discrepancy"].append(m - mu)
            rows["95% CI of discrepancy"].append(f"{lo:.4g} to {hi:.4g}")
            rows["df"].append(len(v) - 1)
        rows["P value"].append(fmt_p(p))
        rows["Summary"].append(stars(p, alpha))
        rows["Significant?"].append(sig(p, alpha))
    r.table("Results", cols, [[k] + v for k, v in rows.items()])
    return r


def _shapiro_francia(x):
    """Shapiro-Francia W' with Royston's (1993) normal approximation of the P value."""
    x = np.sort(x)
    n = len(x)
    m = stats.norm.ppf((np.arange(1, n + 1) - 0.375) / (n + 0.25))
    w = np.corrcoef(x, m)[0, 1] ** 2
    u, v = math.log(n), math.log(math.log(n))
    mu = -1.2725 + 1.0521 * (v - u)
    sd = 1.0308 - 0.26758 * (v + 2 / u)
    z = (math.log(1 - w) - mu) / sd
    return w, float(stats.norm.sf(z))


def generalized_esd(v, max_out, alpha):
    """Rosner's generalized extreme Studentized deviate test; returns indices of outliers."""
    work = list(range(len(v)))
    removed, found = [], 0
    for i in range(1, max_out + 1):
        w = v[work]
        if len(w) < 3 or w.std(ddof=1) == 0:
            break
        dev = np.abs(w - w.mean()) / w.std(ddof=1)
        j = int(np.argmax(dev))
        n = len(v)
        p = 1 - alpha / (2 * (n - i + 1))
        t = stats.t.ppf(p, n - i - 1)
        lam = (n - i) * t / math.sqrt((n - i - 1 + t ** 2) * (n - i + 1))
        removed.append(work[j])
        if dev[j] > lam:
            found = i
        work.pop(j)
    return removed[:found]


def outliers(table, params):
    idx = selected(table, params)
    require(idx, "No data to analyze.")
    method = params.get("method", "grubbs")
    alpha = float(params.get("alpha", 0.05))
    r = Result("Identify outliers")
    rows = []
    cleaned_cols = []
    for i in idx:
        v = table.column_values(i)
        out_mask = np.zeros(len(v), bool)
        if method == "grubbs":
            work = list(range(len(v)))
            while len(work) >= 3:
                w = v[work]
                mean, sd = w.mean(), w.std(ddof=1)
                if sd == 0:
                    break
                j = int(np.argmax(np.abs(w - mean)))
                g = abs(w[j] - mean) / sd
                n = len(w)
                t = stats.t.ppf(1 - alpha / (2 * n), n - 2)
                gcrit = (n - 1) / math.sqrt(n) * math.sqrt(t ** 2 / (n - 2 + t ** 2))
                if g > gcrit:
                    out_mask[work[j]] = True
                    work.pop(j)
                    if not params.get("iterate", True):
                        break
                else:
                    break
        elif method == "esd":
            mo = int(params.get("maxOutliers", 0) or max(1, len(v) // 10))
            for j in generalized_esd(v, min(mo, len(v) - 2), alpha):
                out_mask[j] = True
        elif method == "hampel":
            med = np.median(v)
            mad = stats.median_abs_deviation(v, scale="normal")
            out_mask = np.abs(v - med) > float(params.get("t", 3) or 3) * mad if mad > 0 else out_mask
        elif method == "iqr":
            k = float(params.get("k", 1.5))
            q1, q3 = np.percentile(v, [25, 75])
            iqr = q3 - q1
            out_mask = (v < q1 - k * iqr) | (v > q3 + k * iqr)
        else:  # ROUT-like robust approach: median / MAD based (Q = false discovery rate)
            q = float(params.get("q", 0.01))
            med = np.median(v)
            mad = stats.median_abs_deviation(v, scale="normal")
            if mad > 0:
                z = np.abs(v - med) / mad
                p = 2 * stats.t.sf(z, max(1, len(v) - 1))
                order = np.argsort(p)
                m = len(p)
                for rank, j in enumerate(order, start=1):
                    if p[j] <= q * rank / m:
                        out_mask[j] = True
        for val in v[out_mask]:
            rows.append([table.names[i], val])
        cleaned_cols.append(v[~out_mask])
        rows_summary = (len(v), int(out_mask.sum()))
        r.kv(table.names[i], [("Values analyzed", rows_summary[0]), ("Outliers found", rows_summary[1])])
    r.table("Outliers", ["Data set", "Outlier value"], rows or [["(none)", ""]])
    nmax = max((len(c) for c in cleaned_cols), default=0)
    cells = [[(c[k] if k < len(c) else None) for c in cleaned_cols] for k in range(nmax)]
    r.output_tables.append(make_table(f"Cleaned data ({table.name})", "column",
                                      [{"name": table.names[i], "reps": 1} for i in idx], cells))
    return r


def frequency(table, params):
    idx = selected(table, params)
    require(idx, "No data to analyze.")
    allv = np.concatenate([table.column_values(i) for i in idx])
    require(len(allv) > 0, "No data to analyze.")
    width = params.get("binWidth")
    lo = float(params.get("binStart", np.floor(allv.min())))
    if width in (None, "", 0, "0"):
        nb = max(1, int(np.ceil(np.log2(len(allv)) + 1)))
        width = (allv.max() - lo) / nb or 1.0
    width = float(width)
    require(width > 0, "Bin width must be positive.")
    nb = int(np.ceil((allv.max() - lo) / width + 1e-9)) or 1
    require(nb <= 10000, "Too many bins: increase the bin width.")
    edges = lo + width * np.arange(nb + 1)
    centers = (edges[:-1] + edges[1:]) / 2
    mode = params.get("mode", "count")
    cumulative = bool(params.get("cumulative", False))
    cols = []
    for i in idx:
        c, _ = np.histogram(table.column_values(i), bins=edges)
        c = c.astype(float)
        if cumulative:
            c = np.cumsum(c)
        if mode == "percent":
            c = c / max(1, len(table.column_values(i))) * 100
        elif mode == "fraction":
            c = c / max(1, len(table.column_values(i)))
        cols.append(c)
    r = Result("Frequency distribution")
    r.table("Histogram", ["Bin center"] + [table.names[i] for i in idx],
            [[centers[k]] + [c[k] for c in cols] for k in range(nb)])
    r.output_tables.append(make_table(f"Histogram of {table.name}", "xy",
                                      [{"name": table.names[i], "reps": 1} for i in idx],
                                      [[c[k] for c in cols] for k in range(nb)], x=centers, x_title="Bin center"))
    return r
