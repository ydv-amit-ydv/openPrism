// Calculated columns: a data set whose values are a formula of other data sets,
// e.g. "(B - A) / A * 100" or "log10(C)". Evaluated by a small recursive-descent
// parser (no eval, no code execution) row by row (and replicate by replicate),
// and recalculated whenever the table's data change.
import { colOffset, letter } from './state.js';
import { NUMBER_RE } from './statslite.js';

const FUNCS = {
  log10: Math.log10, log: Math.log10, ln: Math.log, log2: Math.log2, exp: Math.exp, sqrt: Math.sqrt, abs: Math.abs,
  sin: Math.sin, cos: Math.cos, tan: Math.tan, asin: Math.asin, acos: Math.acos, atan: Math.atan,
  floor: Math.floor, ceil: Math.ceil, round: Math.round, sign: Math.sign,
  min: Math.min, max: Math.max, pow: Math.pow,
  logit: (p) => Math.log(p / (1 - p)), invlogit: (x) => 1 / (1 + Math.exp(-x)),
};
const CONSTS = { pi: Math.PI, e: Math.E };

/** Parse a formula into an evaluator f(env) where env maps column letters to numbers. */
export function compile(src) {
  const s = String(src || '').trim();
  if (!s) throw new Error('Enter a formula.');
  if (s.length > 500) throw new Error('Formula too long.');
  let i = 0;
  const refs = new Set();
  const peek = () => s[i];
  const ws = () => { while (/\s/.test(s[i] || '')) i++; };
  const expect = (c) => { ws(); if (s[i] !== c) throw new Error(`Expected “${c}” at position ${i + 1}.`); i++; };
  let depth = 0;
  function expr() {          // + -
    let left = term();
    for (;;) {
      ws();
      const c = peek();
      if (c === '+' || c === '-') { i++; const r = term(); const l = left; left = c === '+' ? (e) => l(e) + r(e) : (e) => l(e) - r(e); } else return left;
    }
  }
  function term() {          // * /
    let left = unary();
    for (;;) {
      ws();
      const c = peek();
      if (c === '*' || c === '/') { i++; const r = unary(); const l = left; left = c === '*' ? (e) => l(e) * r(e) : (e) => l(e) / r(e); } else return left;
    }
  }
  function unary() {         // unary minus binds more loosely than ^ (−A^2 = −(A^2)), as in mathematics
    ws();
    if (peek() === '-') { i++; const u = unary(); return (e) => -u(e); }
    if (peek() === '+') { i++; return unary(); }
    return power();
  }
  function power() {         // ^ (right-associative; the exponent may carry a sign: 2^-1)
    const base = atom();
    ws();
    if (peek() === '^') { i++; const ex = unary(); return (e) => base(e) ** ex(e); }
    return base;
  }
  function atom() {
    ws();
    if (++depth > 100) throw new Error('Formula nested too deeply.');
    try {
      const c = peek();
      if (c === '(') { i++; const v = expr(); expect(')'); return v; }
      const num = /^(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?/.exec(s.slice(i));
      if (num) { i += num[0].length; const v = Number(num[0]); return () => v; }
      const id = /^[A-Za-z_][A-Za-z0-9_]*/.exec(s.slice(i));
      if (!id) throw new Error(`Unexpected “${c ?? 'end'}” at position ${i + 1}.`);
      i += id[0].length;
      const name = id[0];
      ws();
      if (peek() === '(') {
        const fn = Object.hasOwn(FUNCS, name.toLowerCase()) ? FUNCS[name.toLowerCase()] : null;
        if (!fn) throw new Error(`Unknown function “${name}”. Available: ${Object.keys(FUNCS).join(', ')}.`);
        i++;
        const args = [expr()];
        ws();
        while (peek() === ',') { i++; args.push(expr()); ws(); }
        expect(')');
        return (e) => fn(...args.map((a) => a(e)));
      }
      if (Object.hasOwn(CONSTS, name.toLowerCase())) { const v = CONSTS[name.toLowerCase()]; return () => v; }
      if (/^[A-Z]{1,2}$/.test(name)) { refs.add(name); return (e) => e[name]; }
      throw new Error(`Unknown name “${name}”. Refer to data sets by their letters (A, B, C…).`);
    } finally { depth--; }
  }
  const f = expr();
  ws();
  if (i < s.length) throw new Error(`Unexpected “${s[i]}” at position ${i + 1}.`);
  return { f, refs: [...refs] };
}

const toNum = (v) => { const t = String(v ?? '').trim(); return NUMBER_RE.test(t) ? Number(t) : NaN; };
const fmtNum = (v) => (Number.isFinite(v) ? String(Number(v.toPrecision(15))) : '');

/** Recalculate every calculated data set of table t (in place). Returns the number of formulas evaluated. */
export function recompute(t) {
  let n = 0;
  t.datasets.forEach((ds, di) => {
    if (!ds.formula) return;
    let comp;
    try { comp = compile(ds.formula); } catch (_) { return; }
    const letters = t.datasets.map((_, j) => letter(j));
    const off = colOffset(t, di);
    for (let r = 0; r < t.cells.length; r++) {
      for (let k = 0; k < (ds.reps || 1); k++) {
        const env = {};
        let ok = true;
        for (const ref of comp.refs) {
          const j = letters.indexOf(ref);
          if (j < 0 || j === di) { ok = false; break; }
          const reps = t.datasets[j].reps || 1;
          const v = toNum(t.cells[r]?.[colOffset(t, j) + Math.min(k, reps - 1)]);
          if (!Number.isFinite(v)) { ok = false; break; }
          env[ref] = v;
        }
        let out = '';
        if (ok && comp.refs.length) { try { out = fmtNum(comp.f(env)); } catch (_) { out = ''; } }
        if (t.cells[r]) t.cells[r][off + k] = out;
      }
    }
    n++;
  });
  return n;
}
