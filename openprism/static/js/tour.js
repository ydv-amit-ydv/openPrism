// Guided tour for newcomers and ready-made example data sets.
// The tour highlights one part of the screen at a time, explains it in plain words and
// demonstrates the workflow on a small example (data → analysis → graph → figure).
import { P, commit, createGraph, createTable, emit, normalizeTable, state, uniqueName } from './state.js';
import { h, toast } from './ui.js';

// ---------------------------------------------------------------- example data
const EXAMPLES = {
  groups: {
    title: 'Compare three treatments', sub: 'Column table · one-way ANOVA · dot plot',
    make: () => {
      const t = createTable('column', { name: 'Example – tumour size (mm³)' });
      const d = [[112, 98, 81], [125, 91, 77], [104, 102, 69], [131, 88, 84], [118, 95, 72], [109, 99, 79]];
      t.datasets = ['Control', 'Drug A', 'Drug B'].map((name) => ({ name, reps: 1 }));
      t.cells = d.map((r) => r.map(String)); t.rowLabels = d.map(() => '');
      return [t, 'one_way', 'scatter'];
    },
  },
  dose: {
    title: 'Dose-response curve', sub: 'XY table · curve fit (EC50) · XY graph',
    make: () => {
      const t = createTable('xy', { name: 'Example – dose response' });
      const x = [-9, -8.5, -8, -7.5, -7, -6.5, -6, -5.5, -5];
      const y = [[4, 6], [9, 7], [18, 21], [38, 35], [61, 58], [80, 83], [92, 90], [96, 97], [98, 99]];
      t.xTitle = 'log[Agonist], M'; t.datasets = [{ name: 'Response (%)', reps: 2 }];
      t.x = x.map(String); t.cells = y.map((r) => r.map(String)); t.rowLabels = x.map(() => '');
      return [t, 'nonlinear', 'xy-points'];
    },
  },
  survival: {
    title: 'Survival of two groups', sub: 'Survival table · Kaplan-Meier · log-rank',
    make: () => {
      const t = createTable('survival', { name: 'Example – survival (days)' });
      const rows = [[45, 1, 0], [80, 1, 0], [120, 1, 0], [150, 0, 0], [210, 1, 0], [300, 0, 0], [95, 1, 1], [200, 1, 1], [310, 0, 1], [365, 1, 1], [400, 0, 1], [420, 0, 1]];
      t.xTitle = 'Days'; t.datasets = [{ name: 'Control', reps: 1 }, { name: 'Treated', reps: 1 }];
      t.x = rows.map((r) => String(r[0])); t.cells = rows.map((r) => (r[2] ? ['', String(r[1])] : [String(r[1]), ''])); t.rowLabels = rows.map(() => '');
      return [t, 'survival', 'km'];
    },
  },
  twoway: {
    title: 'Two factors (sex × treatment)', sub: 'Grouped table · two-way ANOVA · grouped bars',
    make: () => {
      const t = createTable('grouped', { name: 'Example – body weight (g)' });
      t.datasets = [{ name: 'Control', reps: 3 }, { name: 'Drug', reps: 3 }];
      t.rowLabels = ['Male', 'Female'];
      t.cells = [['25.1', '26.3', '24.8', '28.9', '29.4', '30.1'], ['20.2', '21.0', '19.7', '20.8', '21.5', '20.4']];
      return [t, 'two_way', 'grouped-bar'];
    },
  },
};

export const exampleList = () => Object.entries(EXAMPLES).map(([k, v]) => ({ key: k, title: v.title, sub: v.sub }));

/** Add an example table with its graph (and run its analysis). Returns {table, graph, analysis}. */
export async function loadExample(key, { analyze = true, open = true } = {}) {
  const { createAnalysis } = await import('./analysis.js');
  const [raw, akey, gkind] = EXAMPLES[key].make();
  if (raw.x.length !== raw.cells.length) raw.x = raw.cells.map(() => '');
  if (raw.rowLabels.length !== raw.cells.length) raw.rowLabels = raw.cells.map((_, i) => raw.rowLabels[i] ?? '');
  const t = normalizeTable(raw);
  t.name = uniqueName(P().tables, t.name);
  P().tables.push(t);
  let a = null;
  if (analyze) {
    const { FORMS } = await import('./analysis.js');
    const d = {};
    for (const f of FORMS[akey] || []) d[f.key] = Array.isArray(f.def) ? [...f.def] : (f.def && typeof f.def === 'object' ? { ...f.def } : f.def);
    if (akey === 'nonlinear') d.model = 'log_agonist_4p';
    a = await createAnalysis(t, akey, d);
  }
  const g = createGraph(t, gkind);
  if (a?.result?.overlay && a.result.overlay.kind !== 'plot') g.analysisIds = [a.id];
  P().graphs.push(g);
  commit('Example data');
  emit('changed');
  if (open) emit('open', { kind: 'table', id: t.id });
  return { table: t, graph: g, analysis: a };
}

// ---------------------------------------------------------------- tour engine
const byText = (sel, text) => [...document.querySelectorAll(sel)].find((el) => el.textContent.trim().includes(text) && el.offsetParent !== null);
const q = (sel) => { const el = document.querySelector(sel); return el && el.offsetParent !== null ? el : null; };

let running = null;

export function tourDone() {
  try { return localStorage.getItem(`openprism.tourDone.${state.username}`) === '1'; } catch (_) { return true; }
}
function markDone() { try { localStorage.setItem(`openprism.tourDone.${state.username}`, '1'); } catch (_) { /* ignore */ } }

export async function startTour() {
  if (running) return;
  const made = { tables: [], graphs: [], analyses: [] };
  let ex = null;
  const ensureExample = async () => {
    if (ex) return ex;
    ex = await loadExample('groups', { analyze: true, open: true });
    made.tables.push(ex.table.id); made.graphs.push(ex.graph.id); if (ex.analysis) made.analyses.push(ex.analysis.id);
    return ex;
  };
  const steps = [
    { title: 'Welcome to OpenPrism 👋', text: 'This short tour shows the four steps of every project: your data → an analysis → a graph → a figure. It uses a small example that you can keep or remove at the end. Use → / ← keys or the buttons; Esc ends the tour.' },
    { target: () => q('#view'), before: ensureExample, title: '1 · Your data', text: 'This is a data table. Here each column is one group (Control, Drug A, Drug B) and the numbers are measurements. Type or paste values like in a spreadsheet. Not sure how to lay out your data? Import a file and OpenPrism arranges it for you.' },
    { target: () => byText('#ribbon .rbtn', 'Import'), title: 'Bring your own file', text: 'Click Import — or simply drag a CSV or Excel file onto this window. OpenPrism looks at the columns, suggests the right kind of table, explains why and shows a preview.' },
    { target: () => q('#navigator'), title: 'Everything in one place', text: 'Your project is listed here: data tables, results of analyses, graphs and layouts. Click an item to open it; right-click for rename, duplicate or delete (with Undo).' },
    { target: () => byText('#ribbon .rbtn', 'Analyze'), title: '2 · Analyze', text: 'Click ∑ Analyze on a table. The tests that suit your data are recommended at the top, and every test is explained in plain words: the question it answers, an example and whether it fits your data.' },
    { target: () => byText('#ribbon .rbtn', 'Which test'), title: 'Not sure which test?', text: '“Which test?” asks what you want to find out (compare groups, relationships, survival…) and points you to the right analysis.' },
    { target: () => q('#view .results'), before: async () => { const e = await ensureExample(); if (e.analysis) emit('open', { kind: 'analysis', id: e.analysis.id }); await wait(500); },
      title: 'Reading the results', text: 'Results appear here: the P value (small = the groups differ), which pairs differ (Tukey), and how big the differences are. Results update automatically when you change the data. “📝 Methods” writes a paragraph for your paper.' },
    { target: () => q('#view .graph-paper'), before: async () => { const e = await ensureExample(); emit('open', { kind: 'graph', id: e.graph.id }); await wait(600); },
      title: '3 · Your graph', text: 'Every table gets a graph. The significance stars from the analysis were added automatically. Click a title or axis on the graph to edit it.' },
    { target: () => q('#inspector'), title: 'Format the graph', text: 'Choose the graph type (each one is explained), error bars (SD, SEM, CI), colours, fonts and axes here. Export at the bottom as PDF, SVG, EMF (Word/PowerPoint) or EPS.' },
    { target: () => byText('#ribbon .rbtn', 'New layout'), title: '4 · Make a figure', text: 'A layout puts several graphs, text and images on one page — your finished multi-panel figure, ready to export.' },
    { target: () => q('#user-btn'), title: 'That’s it!', text: 'Your work is saved automatically and encrypted. Replay this tour any time from My account or Help → Guided tour. The ? buttons everywhere open help for that spot.', last: true },
  ];
  let i = 0;
  const spot = h('div', { class: 'tour-spot' });
  const dims = [0, 1, 2, 3].map(() => h('div', { class: 'tour-dim' }));
  const bubble = h('div', { class: 'tour-bubble', role: 'dialog', 'aria-live': 'polite' });
  document.body.append(...dims, spot, bubble);
  running = true;
  const end = (keep = true) => {
    document.removeEventListener('keydown', onKey, true);
    window.removeEventListener('resize', place);
    spot.remove(); bubble.remove(); dims.forEach((d) => d.remove()); running = null;
    markDone();
    if (!keep && made.tables.length) {
      const pr = P();
      pr.tables = pr.tables.filter((t) => !made.tables.includes(t.id));
      pr.graphs = pr.graphs.filter((g) => !made.graphs.includes(g.id) && !made.tables.includes(g.tableId));
      pr.analyses = pr.analyses.filter((a) => !made.analyses.includes(a.id) && !made.tables.includes(a.tableId));
      commit('Remove tour example');
      emit('changed');
      emit('open', { kind: null, id: null });
      toast('Example removed.');
    }
  };
  function place() {
    const s = steps[i];
    const el = s.target ? s.target() : null;
    const r = el?.getBoundingClientRect();
    const vw = document.documentElement.clientWidth; const vh = document.documentElement.clientHeight;
    const box = (d, l, t, w, hh) => Object.assign(d.style, { display: 'block', left: `${l}px`, top: `${t}px`, width: `${Math.max(0, w)}px`, height: `${Math.max(0, hh)}px` });
    if (r && r.width) {
      const L = r.left - 6; const T = r.top - 6; const W = r.width + 12; const H = r.height + 12;
      Object.assign(spot.style, { display: 'block', left: `${L}px`, top: `${T}px`, width: `${W}px`, height: `${H}px` });
      box(dims[0], 0, 0, vw, T); box(dims[1], 0, T + H, vw, vh - T - H); box(dims[2], 0, T, L, H); box(dims[3], L + W, T, vw - L - W, H);
      const bw = Math.min(380, vw - 24);
      let left = r.left + r.width / 2 - bw / 2; left = Math.max(12, Math.min(left, vw - bw - 12));
      bubble.style.width = `${bw}px`;
      const below = r.bottom + 14; const bh = bubble.offsetHeight || 180;
      const top = below + bh < vh - 8 ? below : (r.top - bh - 14 > 8 ? r.top - bh - 14 : Math.max(12, vh - bh - 12));
      Object.assign(bubble.style, { left: `${left}px`, top: `${top}px` });
    } else {
      spot.style.display = 'none';
      box(dims[0], 0, 0, vw, vh); dims.slice(1).forEach((d) => { d.style.display = 'none'; });
      bubble.style.width = `${Math.min(440, vw - 24)}px`;
      Object.assign(bubble.style, { left: `${(vw - bubble.offsetWidth) / 2}px`, top: `${Math.max(40, vh / 2 - 120)}px` });
    }
  }
  async function show(n) {
    i = Math.max(0, Math.min(n, steps.length - 1));
    const s = steps[i];
    try { if (s.before) await s.before(); } catch (_) { /* keep going */ }
    bubble.innerHTML = '';
    bubble.append(h('div', { class: 'tour-step' }, `${i + 1} / ${steps.length}`), h('h3', {}, s.title), h('p', {}, s.text),
      h('div', { class: 'tour-btns' },
        s.last ? null : h('button', { class: 'btn small', onclick: () => end(true) }, 'Skip tour'),
        h('span', { style: { flex: 1 } }),
        i ? h('button', { class: 'btn small', onclick: () => show(i - 1) }, '← Back') : null,
        s.last ? [made.tables.length ? h('button', { class: 'btn small', onclick: () => end(false) }, 'Remove the example') : null,
          h('button', { class: 'btn small primary', onclick: () => end(true) }, made.tables.length ? 'Keep the example & finish' : 'Finish')]
          : h('button', { class: 'btn small primary', onclick: () => show(i + 1) }, 'Next →')));
    place();
    requestAnimationFrame(place);
    bubble.querySelector('.btn.primary')?.focus();
  }
  function onKey(e) {
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); end(true); } else if (e.key === 'ArrowRight' && i < steps.length - 1) { e.preventDefault(); show(i + 1); } else if (e.key === 'ArrowLeft' && i) { e.preventDefault(); show(i - 1); }
  }
  document.addEventListener('keydown', onKey, true);
  window.addEventListener('resize', place);
  show(0);
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
