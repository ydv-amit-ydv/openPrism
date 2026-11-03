// Small, exact calculations done in the browser so graphs redraw instantly
// without a server round trip: the summary values plotted (mean/median,
// SD, SEM, 95% CI, range, IQR, geometric SD). Statistical tests stay on the
// server, where they are validated against NIST and R. The results here are
// checked against the server's /api/graphdata in the browser test-suite.

// ---------------------------------------------------------------- special functions
function lgamma(x) {
  // Lanczos approximation (g = 7, n = 9), |rel. error| < 1e-15
  const c = [0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313, -176.61502916214059,
    12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7];
  if (x < 0.5) return Math.log(Math.PI / Math.abs(Math.sin(Math.PI * x))) - lgamma(1 - x);
  x -= 1;
  let a = c[0];
  const t = x + 7.5;
  for (let i = 1; i < 9; i++) a += c[i] / (x + i);
  return 0.5 * Math.log(2 * Math.PI) + (x + 0.5) * Math.log(t) - t + Math.log(a);
}

function betacf(a, b, x) {
  // continued fraction for the regularized incomplete beta (modified Lentz)
  const FPMIN = 1e-300;
  let c = 1; let d = 1 - (a + b) * x / (a + 1);
  if (Math.abs(d) < FPMIN) d = FPMIN;
  d = 1 / d;
  let hh = d;
  for (let m = 1; m <= 500; m++) {
    const m2 = 2 * m;
    let aa = m * (b - m) * x / ((a + m2 - 1) * (a + m2));
    d = 1 + aa * d; if (Math.abs(d) < FPMIN) d = FPMIN;
    c = 1 + aa / c; if (Math.abs(c) < FPMIN) c = FPMIN;
    d = 1 / d; hh *= d * c;
    aa = -(a + m) * (a + b + m) * x / ((a + m2) * (a + m2 + 1));
    d = 1 + aa * d; if (Math.abs(d) < FPMIN) d = FPMIN;
    c = 1 + aa / c; if (Math.abs(c) < FPMIN) c = FPMIN;
    d = 1 / d;
    const del = d * c;
    hh *= del;
    if (Math.abs(del - 1) < 1e-16) break;
  }
  return hh;
}

function ibeta(a, b, x) {
  if (x <= 0) return 0;
  if (x >= 1) return 1;
  const bt = Math.exp(lgamma(a + b) - lgamma(a) - lgamma(b) + a * Math.log(x) + b * Math.log(1 - x));
  return x < (a + 1) / (a + b + 2) ? bt * betacf(a, b, x) / a : 1 - bt * betacf(b, a, 1 - x) / b;
}

/** Upper tail of Student's t: P(T > t). */
export function tSf(t, df) {
  const x = df / (df + t * t);
  const p = 0.5 * ibeta(df / 2, 0.5, x);
  return t >= 0 ? p : 1 - p;
}

function tPdf(t, df) {
  return Math.exp(lgamma((df + 1) / 2) - lgamma(df / 2) - 0.5 * Math.log(df * Math.PI) - (df + 1) / 2 * Math.log1p(t * t / df));
}

/** Quantile of Student's t (p > 0.5), by bisection then Newton polishing. */
export function tPpf(p, df) {
  if (p === 0.5) return 0;
  const q = 1 - p;  // upper-tail probability
  let lo = 0; let hi = 1;
  while (tSf(hi, df) > q) hi *= 2;
  for (let i = 0; i < 60; i++) { const mid = (lo + hi) / 2; if (tSf(mid, df) > q) lo = mid; else hi = mid; }
  let t = (lo + hi) / 2;
  for (let i = 0; i < 3; i++) t += (tSf(t, df) - q) / tPdf(t, df);
  return t;
}

/** Smallest k with P(X ≤ k) ≥ p for X ~ Binomial(n, prob) — as scipy.stats.binom.ppf. */
export function binomPpf(p, n, prob) {
  let cdf = 0;
  for (let k = 0; k <= n; k++) {
    cdf += Math.exp(lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1) + k * Math.log(prob) + (n - k) * Math.log(1 - prob));
    if (cdf >= p * (1 - 64 * Number.EPSILON)) return k;
  }
  return n;
}

// ---------------------------------------------------------------- summaries
const sum = (v) => { let s = 0; let c = 0; for (const x of v) { const y = x - c; const t = s + y; c = (t - s) - y; s = t; } return s; };  // Kahan
const mean = (v) => sum(v) / v.length;
function sd(v) {
  const m = mean(v);
  return Math.sqrt(sum(v.map((x) => (x - m) * (x - m))) / (v.length - 1));
}
function percentile(sorted, q) {  // numpy 'linear' method
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.min(lo + 1, sorted.length - 1);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}
function median(sorted) { return percentile(sorted, 0.5); }

/** Centre and error bar (plus, minus) of a list of finite numbers — mirrors stats/graphdata.py. */
export function errorBar(v, kind) {
  const n = v.length;
  if (!n) return [null, null, null];
  const s = [...v].sort((a, b) => a - b);
  const allPos = v.every((x) => x > 0);
  let c;
  if (['median_iqr', 'median_range', 'median_ci'].includes(kind)) c = median(s);
  else if (kind === 'geomean_gsd') c = allPos ? Math.exp(mean(v.map(Math.log))) : mean(v);
  else c = mean(v);
  if (n < 2 || kind === 'none') return [c, 0, 0];
  const d = sd(v);
  switch (kind) {
    case 'sd': return [c, d, d];
    case 'sem': { const e = d / Math.sqrt(n); return [c, e, e]; }
    case 'ci95': { const e = tPpf(0.975, n - 1) * d / Math.sqrt(n); return [c, e, e]; }
    case 'range': case 'median_range': return [c, s[n - 1] - c, c - s[0]];
    case 'median_iqr': return [c, percentile(s, 0.75) - c, c - percentile(s, 0.25)];
    case 'median_ci': { const j = Math.max(1, binomPpf(0.025, n, 0.5)); return [c, s[n - j] - c, c - s[j - 1]]; }
    case 'geomean_gsd': {
      if (!allPos) return [c, d, d];
      const g = Math.exp(sd(v.map(Math.log)));
      return [c, c * g - c, c - c / g];
    }
    default: return [c, d, d];
  }
}

/** Strict mathematical number format (same rule as the server): no commas, no spaces, no inf/nan. */
export const NUMBER_RE = /^[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$/;
export const toNum = (v) => {
  if (v === null || v === undefined) return NaN;
  if (typeof v === 'number') return Number.isFinite(v) ? v : NaN;
  const s = String(v).trim();
  if (!NUMBER_RE.test(s)) return NaN;
  const f = Number(s);
  return Number.isFinite(f) ? f : NaN;
};

/** Summary tables (mean, SD or SEM, n per row): one plotted group per row, no raw values. */
function summaryGraphData(t, error) {
  const isSem = /SEM|^SE$/i.test(String(t.datasets[1]?.name || '').trim());
  const out = { type: 'summary', names: [], rowLabels: [], x: [], datasets: [], local: true };
  t.cells.forEach((row, r) => {
    const m = toNum(row[0]); const s = toNum(row[1]); const n = toNum(row[2]);
    if (!Number.isFinite(m)) return;
    const label = (t.rowLabels?.[r] ?? '') !== '' ? String(t.rowLabels[r]) : `Row ${r + 1}`;
    const sd = Number.isFinite(s) ? (isSem && Number.isFinite(n) ? s * Math.sqrt(n) : s) : NaN;
    const se = Number.isFinite(sd) && n > 0 ? sd / Math.sqrt(n) : NaN;
    let e = sd;
    if (error === 'sem') e = se;
    else if (error === 'ci95') e = n > 1 ? tPpf(0.975, n - 1) * se : NaN;
    else if (error === 'none') e = 0;
    e = Number.isFinite(e) ? e : null;
    out.names.push(label);
    out.datasets.push({ name: label, values: [], summaryOnly: true, center: m, plus: e, minus: e, rows: [], summary: { n, mean: m, sd: fin(sd) } });
  });
  return out;
}

/** Same structure as the server's graph_data(): computed locally, instantly. */
export function graphDataLocal(t, error) {
  if (t.type === 'summary') return summaryGraphData(t, error);
  const nrows = Math.max(t.cells.length, (t.rowLabels || []).length, (t.x || []).length);
  const out = { type: t.type, names: t.datasets.map((d, i) => d.name || `Data set ${i + 1}`), rowLabels: [], x: [], datasets: [], local: true };
  for (let r = 0; r < nrows; r++) {
    const lab = t.rowLabels?.[r];
    out.rowLabels.push(lab !== undefined && lab !== null && lab !== '' ? String(lab) : `Row ${r + 1}`);
    const xv = toNum(t.x?.[r]);
    out.x.push(Number.isFinite(xv) ? xv : null);
  }
  let col = 0;
  t.datasets.forEach((d, i) => {
    const reps = Math.max(1, d.reps || 1);
    const all = [];
    const rows = [];
    for (let r = 0; r < nrows; r++) {
      const rv = [];
      for (let k = 0; k < reps; k++) {
        const v = toNum(t.cells[r]?.[col + k]);
        if (Number.isFinite(v)) rv.push(v);
      }
      all.push(...rv);
      const [rc, ru, rl] = rv.length ? errorBar(rv, error) : [null, null, null];
      rows.push({ center: fin(rc), plus: fin(ru), minus: fin(rl), n: rv.length, values: rv });
    }
    const [c, up, lo] = errorBar(all, error);
    const n = all.length;
    out.datasets.push({ name: out.names[i], values: all, center: fin(c), plus: fin(up), minus: fin(lo), rows,
      summary: n ? { n, mean: fin(mean(all)), sd: n > 1 ? fin(sd(all)) : null, median: fin(median([...all].sort((a, b) => a - b))) } : { n: 0 } });
    col += reps;
  });
  return out;
}
const fin = (v) => (v === null || v === undefined || !Number.isFinite(v) ? null : v);
