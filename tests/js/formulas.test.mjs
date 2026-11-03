// Calculated-column formula parser: precedence, functions and rejection of anything that is not a formula.
import { compile } from '../../openprism/static/js/formulas.js';
const cases = [['(B - A) / A * 100', { A: 4, B: 5 }, 25], ['log10(C)', { C: 1000 }, 3], ['-A^2', { A: 3 }, -9], ['2^-1', {}, 0.5], ['-2^2+A', { A: 1 }, -3], ['2^3^2', {}, 512], ['max(A, B, 7) + pi*0', { A: 1, B: 2 }, 7], ['1e-3*A', { A: 2000 }, 2]];
for (const [f, env, want] of cases) { const r = compile(f).f(env); if (Math.abs(r - want) > 1e-12) { console.error('FAIL', f, r, want); process.exitCode = 1; } }
for (const bad of ['A +', 'foo(A)', 'alert(1)', 'A; B', 'constructor', '__proto__', 'toString(A)', '((A)']) { try { compile(bad); console.error('NOT REJECTED', bad); process.exitCode = 1; } catch (_) { /* expected */ } }

console.log(process.exitCode ? 'formula tests FAILED' : 'formula tests passed');
