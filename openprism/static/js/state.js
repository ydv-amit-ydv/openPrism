// Project model, undo/redo history, persistence and a tiny event bus.

export const TABLE_TYPES = {
  xy: { label: 'XY', icon: '⤢', hasX: true, rowLabels: false, desc: 'Each point has an X and Y value (dose-response, time course, standard curves).' },
  column: { label: 'Column', icon: '▥', hasX: false, rowLabels: false, desc: 'Each column is a group (t tests, one-way ANOVA, dot plots).' },
  grouped: { label: 'Grouped', icon: '▦', hasX: false, rowLabels: true, desc: 'Two grouping variables: rows × columns (two-way ANOVA, grouped bars).' },
  contingency: { label: 'Contingency', icon: '⊞', hasX: false, rowLabels: true, desc: 'Counts of subjects in each category (chi-square, Fisher’s exact).' },
  survival: { label: 'Survival', icon: '⌐', hasX: true, rowLabels: false, desc: 'Time to event with 1 = event, 0 = censored (Kaplan-Meier, log-rank).' },
  parts: { label: 'Parts of whole', icon: '◔', hasX: false, rowLabels: true, desc: 'Values that are fractions of a total (pie and donut charts).' },
  nested: { label: 'Nested', icon: '⋮', hasX: false, rowLabels: false, desc: 'Groups with several subjects each, and replicate measurements per subject (nested t test / nested ANOVA).' },
  summary: { label: 'Summary data', icon: 'x̄', hasX: false, rowLabels: true, desc: 'One row per group with mean, SD (or SEM) and n — e.g. results from a paper (t test and ANOVA from summary data).' },
  multi: { label: 'Multiple variables', icon: '⊟', hasX: false, rowLabels: false, desc: 'Each row is a subject, each column a variable (multiple / logistic / Cox regression, PCA, correlation matrix).' },
};

export const DEFAULT_GRAPH_KIND = {
  xy: 'xy-points', column: 'scatter', summary: 'bar', grouped: 'grouped-bar', contingency: 'grouped-bar', survival: 'km', parts: 'pie', multi: 'var-scatter', nested: 'nested-scatter',
};

let seq = Date.now() % 100000;
export const uid = (p) => `${p}${(++seq).toString(36)}`;

const listeners = {};
export function on(evt, fn) { (listeners[evt] ||= []).push(fn); }
export function emit(evt, ...a) { (listeners[evt] || []).forEach((f) => f(...a)); }

export function letter(i) {
  let s = '';
  i += 1;
  while (i > 0) { const m = (i - 1) % 26; s = String.fromCharCode(65 + m) + s; i = Math.floor((i - 1) / 26); }
  return s;
}

export function newProject(name = 'Untitled project') {
  return { version: 1, name, tables: [], analyses: [], graphs: [], layouts: [], notes: '', created: new Date().toISOString() };
}

export const state = {
  project: newProject(),
  current: null, // {kind: 'table'|'analysis'|'graph'|'layout'|'notes', id}
  dirty: false,
  username: null,       // signed-in user
  serverId: null,       // id of this project on the server (null = never saved)
  serverVersion: null,  // version for optimistic concurrency
  encryption: null,     // {key, salt, iter} when the project is password-protected (key never leaves the browser)
  autosaveServer: true,
  dataKey: null,        // account data key (non-extractable CryptoKey) — end-to-end encryption
  localEncrypt: null,   // async (value) => encrypted envelope, set once the key is unlocked
};

// ---------- history ----------
const undoStack = [];
const redoStack = [];
let lastSnap = null;
export function snapshot() { return JSON.stringify(state.project); }
export function resetHistory() { undoStack.length = 0; redoStack.length = 0; lastSnap = snapshot(); }

/** Record a change (call after mutating state.project). */
export function commit(label = '') {
  const s = snapshot();
  if (s === lastSnap) return;
  if (lastSnap) undoStack.push(lastSnap);
  if (undoStack.length > 80) undoStack.shift();
  redoStack.length = 0;
  lastSnap = s;
  markDirty();
  emit('changed', label);
}
export function undo() {
  if (!undoStack.length) return false;
  redoStack.push(lastSnap);
  lastSnap = undoStack.pop();
  state.project = JSON.parse(lastSnap);
  markDirty();
  emit('restored');
  return true;
}
export function redo() {
  if (!redoStack.length) return false;
  undoStack.push(lastSnap);
  lastSnap = redoStack.pop();
  state.project = JSON.parse(lastSnap);
  markDirty();
  emit('restored');
  return true;
}
export const canUndo = () => undoStack.length > 0;
export const canRedo = () => redoStack.length > 0;

function markDirty() {
  state.dirty = true;
  state.changeSeq = (state.changeSeq || 0) + 1;
  const d = document.getElementById('dirty-dot');
  if (d) d.hidden = false;
  autosave();
}
export function markClean() {
  state.dirty = false;
  const d = document.getElementById('dirty-dot');
  if (d) d.hidden = true;
}

// Local (browser) crash-recovery copy, kept per user. Never stored for
// password-protected projects, and wiped on sign-out.
const localKey = () => (state.username ? `openprism.autosave.${state.username}` : null);
let autosaveTimer = null;
/** Write the encrypted crash-recovery copy now (also called after each server save,
 *  so the stored version number always matches the server). */
export async function writeLocalCopy() {
  const k = localKey();
  if (!k || !state.localEncrypt) return;
  try {
    const env = await state.localEncrypt({ project: state.project, serverId: state.serverId, serverVersion: state.serverVersion, dirty: state.dirty });
    localStorage.setItem(k, JSON.stringify(env));
  } catch (_) { /* storage unavailable, full, or key locked */ }
}
function autosave() {
  clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(writeLocalCopy, 800);
  emit('dirty');
}
/** Returns the encrypted local crash-recovery copy (decrypted by the caller). */
export function loadAutosave() {
  const k = localKey();
  if (!k) return null;
  try {
    const s = localStorage.getItem(k);
    return s ? JSON.parse(s) : null;
  } catch (_) { return null; }
}
export function clearLocalData() {
  try {
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const k = localStorage.key(i);
      if (k && k.startsWith('openprism.autosave')) localStorage.removeItem(k);
    }
  } catch (_) { /* ignore */ }
}

// ---------- lookups ----------
export const P = () => state.project;
export const getTable = (id) => P().tables.find((t) => t.id === id);
export const getAnalysis = (id) => P().analyses.find((a) => a.id === id);
export const getGraph = (id) => P().graphs.find((g) => g.id === id);
export const getLayout = (id) => P().layouts.find((l) => l.id === id);

export function uniqueName(list, base) {
  const names = new Set(list.map((x) => x.name));
  if (!names.has(base)) return base;
  let i = 2;
  while (names.has(`${base} ${i}`)) i++;
  return `${base} ${i}`;
}

// ---------- factories ----------
export function createTable(type, opts = {}) {
  const nds = opts.datasets ?? (type === 'parts' ? 1 : type === 'contingency' ? 2 : 3);
  const reps = opts.reps ?? 1;
  const nrows = opts.rows ?? (type === 'column' ? 12 : type === 'multi' ? 30 : 10);
  const t = {
    id: uid('t'),
    name: opts.name || uniqueName(P().tables, 'Data'),
    type,
    xTitle: type === 'survival' ? 'Time' : 'X',
    datasets: Array.from({ length: nds }, (_, i) => ({ name: type === 'parts' ? 'Value' : type === 'multi' ? `Variable ${letter(i)}` : type === 'nested' ? `Group ${letter(i)}` : `Data set ${letter(i)}`, reps: type === 'multi' ? 1 : reps })),
    rowLabels: Array(nrows).fill(''),
    x: Array(nrows).fill(''),
    cells: Array.from({ length: nrows }, () => Array(nds * reps).fill('')),
    excluded: {},
    rev: 1,
  };
  if (type === 'contingency') t.datasets = [{ name: 'Outcome 1', reps: 1 }, { name: 'Outcome 2', reps: 1 }];
  if (type === 'summary') {  // fixed columns; rename “SD” to “SEM” if the values are standard errors
    t.datasets = [{ name: 'Mean', reps: 1 }, { name: 'SD', reps: 1 }, { name: 'N', reps: 1 }];
    t.cells = t.cells.map(() => ['', '', '']);
  }
  return normalizeTable(t);
}

export function normalizeTable(t) {
  t.datasets ||= [];
  t.cells ||= [];
  t.rowLabels ||= [];
  t.x ||= [];
  t.excluded ||= {};
  t.rev ||= 1;
  const width = t.datasets.reduce((s, d) => s + (d.reps || 1), 0);
  const n = Math.max(t.cells.length, t.rowLabels.length, t.x.length, 1);
  for (let r = 0; r < n; r++) {
    t.cells[r] ||= [];
    while (t.cells[r].length < width) t.cells[r].push('');
    if (t.cells[r].length > width) t.cells[r].length = width;
    t.cells[r] = t.cells[r].map((v) => (v === null || v === undefined ? '' : String(v)));
    if (t.rowLabels[r] === undefined || t.rowLabels[r] === null) t.rowLabels[r] = '';
    if (t.x[r] === undefined || t.x[r] === null) t.x[r] = '';
  }
  t.cells.length = n; t.rowLabels.length = n; t.x.length = n;
  return t;
}

/** Table as sent to the server (excluded values are blanked). */
export function tableForServer(t) {
  const cells = t.cells.map((row, r) => row.map((v, c) => (t.excluded[`${r},${c}`] ? '' : v)));
  return { name: t.name, type: t.type, xTitle: t.xTitle, datasets: t.datasets, rowLabels: t.rowLabels, x: t.x, cells };
}

export function colOffset(t, ds) {
  let c = 0;
  for (let i = 0; i < ds; i++) c += t.datasets[i].reps || 1;
  return c;
}

export function touchTable(t) { t.rev = (t.rev || 0) + 1; }

export function createGraph(table, kind) {
  const g = {
    id: uid('g'),
    name: uniqueName(P().graphs, table.name),
    tableId: table.id,
    analysisIds: [],
    kind: kind || DEFAULT_GRAPH_KIND[table.type] || 'scatter',
    style: defaultStyle(table),
  };
  return g;
}

export function defaultStyle(table) {
  return {
    title: table.name, xTitle: table.type === 'xy' || table.type === 'survival' ? table.xTitle : table.type === 'multi' ? 'auto' : '',
    yTitle: table.type === 'survival' ? 'Percent survival' : table.type === 'contingency' ? 'Count' : table.type === 'multi' ? 'auto' : 'Y',
    width: 520, height: 400, error: 'sem', palette: table.type === 'parts' ? 'colors' : 'prism', fontSize: 14, fontFamily: 'Arial',
    markerSize: 8, lineWidth: 2, barWidth: 0.6, showPoints: true, jitter: 0.5, xLog: false, yLog: false,
    xMin: '', xMax: '', yMin: '', yMax: '', showLegend: true, axisStyle: 'prism', showSig: true,
    sigFormat: 'stars', showNs: false, showBand: false, connect: false, frame: false, series: {}, centerLine: 'mean',
    errorDir: 'both', showCI: false, censorMarks: true, survivalAsFraction: false, legendX: '', legendY: '',
    gap: 0.25, bgColor: '#ffffff', capWidth: 6, orientation: 'v', showEq: false, annotations: [],
    xVar: 0, yVar: 1, colorVar: '', plotIndex: 0,
  };
}

export function createLayout(name) {
  return { id: uid('l'), name: name || uniqueName(P().layouts, 'Layout'), page: { w: 1056, h: 816 }, grid: true, items: [] };
}
