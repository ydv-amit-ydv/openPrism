// Spreadsheet-style data table editor: selection, keyboard navigation,
// copy/paste (Excel-compatible TSV), exclusion of values, row/column editing.
import { TABLE_TYPES, colOffset, commit, emit, letter, normalizeTable, touchTable } from './state.js';
import { contextMenu, h, prompt, toast } from './ui.js';
import { toNum } from './statslite.js';
import { recompute } from './formulas.js';

const SPARE_ROWS = 5;

export function renderGrid(container, t) {
  normalizeTable(t);
  ensureSpare(t);
  const info = TABLE_TYPES[t.type];
  // logical columns: 'L' (row title), 'X', then data column indices
  const cols = ['L'];
  if (info.hasX) cols.push('X');
  const width = colOffset(t, t.datasets.length);
  for (let c = 0; c < width; c++) cols.push(c);
  const dsOf = [];
  t.datasets.forEach((d, i) => { for (let k = 0; k < (d.reps || 1); k++) dsOf.push([i, k]); });

  let sel = { r0: 0, c0: info.hasX ? 1 : Math.min(1, cols.length - 1), r1: 0, c1: info.hasX ? 1 : Math.min(1, cols.length - 1) };
  let editor = null;

  const wrap = h('div', { class: 'grid-wrap', tabindex: 0 });
  const table = h('table', { class: 'grid' });
  wrap.append(table);
  container.append(wrap);

  const get = (r, ci) => {
    const c = cols[ci];
    if (c === 'L') return t.rowLabels[r] ?? '';
    if (c === 'X') return t.x[r] ?? '';
    return t.cells[r]?.[c] ?? '';
  };
  const isCalc = (ci) => typeof cols[ci] === 'number' && !!t.datasets[dsOf[cols[ci]]?.[0]]?.formula;
  const set = (r, ci, v) => {
    if (isCalc(ci)) return;  // calculated columns are filled by their formula
    while (r >= t.cells.length) { t.cells.push(Array(width).fill('')); t.rowLabels.push(''); t.x.push(''); }
    const c = cols[ci];
    if (c === 'L') t.rowLabels[r] = v;
    else if (c === 'X') t.x[r] = v;
    else t.cells[r][c] = v;
  };
  const isBad = (v) => String(v ?? '').trim() !== '' && Number.isNaN(toNum(v));  // strict: decimal point, no commas

  function changed(rerender = true) {
    if (t.datasets.some((d) => d.formula)) { recompute(t); rerender = true; }
    touchTable(t);
    ensureSpare(t);
    commit('Edit data');
    emit('table-changed', t.id);
    if (rerender) draw();
  }

  function draw() {
    table.innerHTML = '';
    const thead = h('thead');
    const r1 = h('tr', {}, h('th', { class: 'corner', rowspan: 2 }, ''));
    const r2 = h('tr');
    r1.append(h('th', { rowspan: 2, style: { minWidth: '110px' }, title: 'Row titles' }, info.rowLabels ? 'Group' : 'Row title'));
    if (info.hasX) {
      r1.append(h('th', { class: 'dshead', rowspan: 2, title: 'Double-click to rename', ondblclick: () => renameX() }, t.xTitle || 'X'));
    }
    t.datasets.forEach((d, i) => {
      r1.append(h('th', {
        class: 'dshead', colspan: d.reps || 1, title: 'Double-click to rename · right-click for options',
        ondblclick: () => renameDs(i), oncontextmenu: (e) => { e.preventDefault(); dsMenu(e, i); },
      }, h('span', { class: 'letter' }, letter(i)), d.name));
      for (let k = 0; k < (d.reps || 1); k++) {
        r2.append(h('th', {}, t.type === 'survival' ? 'Event (1/0)' : (d.reps > 1 ? `Y${k + 1}` : (t.type === 'xy' ? 'Y' : ''))));
      }
    });
    thead.append(r1, r2);
    tbody = h('tbody');
    table.append(thead, tbody);
    // pin the second header row exactly below the first, whatever its height
    requestAnimationFrame(() => { const r0 = thead.rows[0]?.getBoundingClientRect().height; if (r0) table.style.setProperty('--grid-h1', `${r0}px`); });
    drawBody();
  }

  // ---- virtual scrolling: large tables render only the rows near the viewport
  const VIRTUAL_MIN = 400;
  const BUFFER = 40;
  let tbody = null;
  let rowH = 25;
  let rendered = [0, 0];
  const virtual = () => t.cells.length > VIRTUAL_MIN;
  function scroller() { return wrap.closest('.view-body') || wrap.parentElement; }
  function wanted() {
    if (!virtual()) return [0, t.cells.length];
    const sc = scroller();
    const head = table.tHead ? table.tHead.getBoundingClientRect().bottom : table.getBoundingClientRect().top;
    const offset = head - sc.getBoundingClientRect().top;  // where row 0 starts, relative to the visible top
    const first = Math.max(0, Math.floor(-offset / rowH) - BUFFER);
    const count = Math.ceil(sc.clientHeight / rowH) + 2 * BUFFER;
    return [first, Math.min(t.cells.length, first + count)];
  }
  function spacer(n) {
    return h('tr', { class: 'vspacer' }, h('td', { colspan: cols.length + 1, style: { height: `${n * rowH}px`, padding: 0, border: 0 } }));
  }
  function drawBody() {
    const [a, b] = wanted();
    rendered = [a, b];
    tbody.innerHTML = '';
    if (a > 0) tbody.append(spacer(a));
    for (let r = a; r < b; r++) {
      const tr = h('tr', {}, h('td', { class: 'rownum' }, r + 1));
      cols.forEach((c, ci) => {
        const v = get(r, ci);
        const cls = [c === 'L' ? 'rowlab' : c === 'X' ? 'xcol' : '', c !== 'L' && isBad(v) ? 'bad' : '', isCalc(ci) ? 'calc' : '',
          typeof c === 'number' && t.excluded[`${r},${c}`] ? 'excluded' : ''].join(' ');
        const td = h('td', { class: cls, 'data-r': r, 'data-c': ci, title: c !== 'L' && isBad(v) ? 'Not a number — use a decimal point and no thousands separators (e.g. 1234.5)' : null }, v);
        if (c === 'L') td.style.textAlign = 'left';
        tr.append(td);
      });
      tbody.append(tr);
    }
    if (b < t.cells.length) tbody.append(spacer(t.cells.length - b));
    const first = tbody.querySelector('tr:not(.vspacer)');
    if (first && virtual()) rowH = first.getBoundingClientRect().height || rowH;
    paintSel();
  }
  let scrollQueued = false;
  function onScroll() {
    if (!virtual() || scrollQueued) return;
    scrollQueued = true;
    requestAnimationFrame(() => {
      scrollQueued = false;
      if (!wrap.isConnected) { scroller()?.removeEventListener('scroll', onScroll); return; }
      const [a, b] = wanted();
      if (a < rendered[0] || b > rendered[1] || Math.abs(a - rendered[0]) > BUFFER / 2) { if (!editor) drawBody(); }
    });
  }
  function ensureRendered(r) {
    if (!virtual() || (r >= rendered[0] + 2 && r < rendered[1] - 2)) return;
    const sc = scroller();
    const head = table.tHead.getBoundingClientRect().bottom - sc.getBoundingClientRect().top + sc.scrollTop;
    const top = head + r * rowH;
    if (top < sc.scrollTop + head || top + rowH > sc.scrollTop + sc.clientHeight) sc.scrollTop = Math.max(0, top - sc.clientHeight / 2);
    drawBody();
  }

  function td(r, ci) { return table.querySelector(`td[data-r="${r}"][data-c="${ci}"]`); }
  function norm() {
    return { ra: Math.min(sel.r0, sel.r1), rb: Math.max(sel.r0, sel.r1), ca: Math.min(sel.c0, sel.c1), cb: Math.max(sel.c0, sel.c1) };
  }
  function paintSel() {
    table.querySelectorAll('td.sel, td.cur').forEach((e) => e.classList.remove('sel', 'cur'));
    const { ra, rb, ca, cb } = norm();
    for (let r = Math.max(ra, rendered[0]); r <= Math.min(rb, rendered[1] - 1); r++) for (let c = ca; c <= cb; c++) td(r, c)?.classList.add('sel');
    td(sel.r1, sel.c1)?.classList.add('cur');
  }
  function move(dr, dc, extend) {
    const r = Math.max(0, Math.min(t.cells.length - 1, sel.r1 + dr));
    const c = Math.max(0, Math.min(cols.length - 1, sel.c1 + dc));
    if (extend) { sel.r1 = r; sel.c1 = c; } else sel = { r0: r, c0: c, r1: r, c1: c };
    ensureRendered(r);
    paintSel();
    td(sel.r1, sel.c1)?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }

  function startEdit(initial) {
    if (isCalc(sel.c1)) { toast(`“${t.datasets[dsOf[cols[sel.c1]][0]].name}” is calculated (= ${t.datasets[dsOf[cols[sel.c1]][0]].formula}). Right-click its header to edit the formula.`); return; }
    const cell = td(sel.r1, sel.c1);
    if (!cell) return;
    const rect = cell.getBoundingClientRect();
    const crect = wrap.parentElement.getBoundingClientRect();
    const sc = wrap.parentElement;
    const inp = h('input', {
      class: 'cell-editor', value: initial ?? get(sel.r1, sel.c1),
      style: {
        left: `${rect.left - crect.left + sc.scrollLeft}px`, top: `${rect.top - crect.top + sc.scrollTop}px`,
        width: `${Math.max(rect.width, 90)}px`, height: `${rect.height}px`, textAlign: cols[sel.c1] === 'L' ? 'left' : 'right',
      },
    });
    editor = { inp, r: sel.r1, c: sel.c1 };
    sc.append(inp);
    inp.focus();
    if (initial === undefined) inp.select();
    else inp.setSelectionRange(inp.value.length, inp.value.length);
    inp.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); endEdit(true); move(e.shiftKey ? -1 : 1, 0); }
      else if (e.key === 'Tab') { e.preventDefault(); endEdit(true); move(0, e.shiftKey ? -1 : 1); }
      else if (e.key === 'Escape') { e.preventDefault(); endEdit(false); }
      else if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && initial !== undefined) {
        e.preventDefault(); endEdit(true); move(e.key === 'ArrowDown' ? 1 : -1, 0);
      }
      e.stopPropagation();
    });
    inp.addEventListener('blur', () => endEdit(true));
  }
  function endEdit(save) {
    if (!editor) return;
    const { inp, r, c } = editor;
    editor = null;
    const v = inp.value;
    inp.remove();
    wrap.focus({ preventScroll: true });
    if (save && v !== get(r, c)) {
      const grows = r >= t.cells.length - SPARE_ROWS;
      set(r, c, v);
      if (grows) changed(true);
      else {
        const cell = td(r, c);
        if (cell) { cell.textContent = v; cell.classList.toggle('bad', cols[c] !== 'L' && isBad(v)); }
        changed(false);
      }
      paintSel();
    }
  }

  function clearSel() {
    const { ra, rb, ca, cb } = norm();
    for (let r = ra; r <= rb; r++) for (let c = ca; c <= cb; c++) set(r, c, '');
    changed();
  }
  function selectionTSV() {
    const { ra, rb, ca, cb } = norm();
    const lines = [];
    for (let r = ra; r <= rb; r++) {
      const row = [];
      for (let c = ca; c <= cb; c++) row.push(get(r, c));
      lines.push(row.join('\t'));
    }
    return lines.join('\n');
  }
  function pasteText(text) {
    const lines = text.replace(/\r/g, '').split('\n');
    if (lines.length && lines[lines.length - 1] === '') lines.pop();
    const { ra, ca } = norm();
    // Spreadsheets copy cells separated by TABs. Commas are never treated as separators or
    // decimal marks here (strict number format), so "1,5" stays one cell and is flagged.
    const sep = '\t';
    let bad = 0;
    const examples = [];
    lines.forEach((line, i) => {
      line.split(sep).forEach((v, j) => {
        if (ca + j >= cols.length) return;
        const val = v.trim();
        set(ra + i, ca + j, val);
        if (cols[ca + j] !== 'L' && isBad(val)) { bad++; if (examples.length < 3) examples.push(val); }
      });
    });
    if (bad) {
      toast(`${bad} pasted value(s) are not numbers (e.g. “${examples.join('”, “')}”) and are shown in red. `
        + 'Use a decimal point and no thousands separators: 1234.5, not 1,234.5 or 1234,5.', 'err');
    }
    sel = { r0: ra, c0: ca, r1: ra + lines.length - 1, c1: Math.min(cols.length - 1, ca + (lines[0] || '').split(sep).length - 1) };
    changed();
  }

  wrap.addEventListener('keydown', (e) => {
    if (editor) return;
    const mod = e.ctrlKey || e.metaKey;
    if (mod && (e.key === 'z' || e.key === 'y')) return; // global undo handler
    if (e.key === 'ArrowDown') { e.preventDefault(); move(1, 0, e.shiftKey); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1, 0, e.shiftKey); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); move(0, -1, e.shiftKey); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); move(0, 1, e.shiftKey); }
    else if (e.key === 'Tab') { e.preventDefault(); move(0, e.shiftKey ? -1 : 1); }
    else if (e.key === 'Enter' || e.key === 'F2') { e.preventDefault(); startEdit(); }
    else if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); clearSel(); }
    else if (mod && e.key === 'a') { e.preventDefault(); sel = { r0: 0, c0: 0, r1: t.cells.length - 1, c1: cols.length - 1 }; paintSel(); }
    else if (!mod && e.key.length === 1) { e.preventDefault(); startEdit(e.key); }
  });
  wrap.addEventListener('copy', (e) => { if (editor) return; e.preventDefault(); e.clipboardData.setData('text/plain', selectionTSV()); });
  wrap.addEventListener('cut', (e) => { if (editor) return; e.preventDefault(); e.clipboardData.setData('text/plain', selectionTSV()); clearSel(); });
  wrap.addEventListener('paste', (e) => { if (editor) return; e.preventDefault(); pasteText(e.clipboardData.getData('text/plain')); });

  let dragging = false;
  table.addEventListener('mousedown', (e) => {
    const cell = e.target.closest('td[data-r]');
    if (!cell || e.button !== 0) return;
    endEdit(true);
    const r = +cell.dataset.r; const c = +cell.dataset.c;
    if (e.shiftKey) { sel.r1 = r; sel.c1 = c; } else sel = { r0: r, c0: c, r1: r, c1: c };
    dragging = true;
    paintSel();
    wrap.focus({ preventScroll: true });
    e.preventDefault();
  });
  table.addEventListener('mouseover', (e) => {
    if (!dragging) return;
    const cell = e.target.closest('td[data-r]');
    if (!cell) return;
    sel.r1 = +cell.dataset.r; sel.c1 = +cell.dataset.c;
    paintSel();
  });
  window.addEventListener('mouseup', () => { dragging = false; });
  table.addEventListener('dblclick', (e) => { if (e.target.closest('td[data-r]')) startEdit(); });
  table.addEventListener('contextmenu', (e) => {
    const cell = e.target.closest('td[data-r]');
    if (!cell) return;
    e.preventDefault();
    const r = +cell.dataset.r; const c = +cell.dataset.c;
    const { ra, rb, ca, cb } = norm();
    if (r < ra || r > rb || c < ca || c > cb) { sel = { r0: r, c0: c, r1: r, c1: c }; paintSel(); }
    cellMenu(e);
  });

  function cellMenu(e) {
    const { ra, rb, ca, cb } = norm();
    const dataCols = [];
    for (let c = ca; c <= cb; c++) if (typeof cols[c] === 'number') dataCols.push(cols[c]);
    contextMenu(e.clientX, e.clientY, [
      { label: 'Copy', action: () => navigator.clipboard?.writeText(selectionTSV()) },
      { label: 'Paste', action: async () => { try { pasteText(await navigator.clipboard.readText()); } catch (_) { /* clipboard blocked */ } } },
      { label: 'Clear', action: clearSel },
      '-',
      { label: 'Exclude / include value(s)', action: () => toggleExclude(ra, rb, dataCols) },
      '-',
      { label: 'Insert row above', action: () => insertRows(ra, 1) },
      { label: 'Insert row below', action: () => insertRows(rb + 1, 1) },
      { label: `Delete row${rb > ra ? 's' : ''}`, action: () => deleteRows(ra, rb) },
      '-',
      { label: 'Insert data set', action: () => { const ds = typeof cols[ca] === 'number' ? dsOf[cols[ca]][0] : t.datasets.length; addDataset(t, ds); changed(); emit('table-structure', t.id); } },
      { label: 'Sort rows by this column (ascending)', action: () => sortBy(ca) },
    ]);
  }
  function toggleExclude(ra, rb, dataCols) {
    let any = false;
    for (let r = ra; r <= rb; r++) for (const c of dataCols) if (!t.excluded[`${r},${c}`]) any = true;
    for (let r = ra; r <= rb; r++) for (const c of dataCols) { if (any) t.excluded[`${r},${c}`] = 1; else delete t.excluded[`${r},${c}`]; }
    changed();
  }
  function insertRows(at, n) {
    for (let i = 0; i < n; i++) { t.cells.splice(at, 0, Array(width).fill('')); t.rowLabels.splice(at, 0, ''); t.x.splice(at, 0, ''); }
    shiftExcluded(at, n);
    changed();
  }
  function deleteRows(ra, rb) {
    const n = rb - ra + 1;
    t.cells.splice(ra, n); t.rowLabels.splice(ra, n); t.x.splice(ra, n);
    const ex = {};
    for (const k of Object.keys(t.excluded)) {
      const [r, c] = k.split(',').map(Number);
      if (r < ra) ex[k] = 1; else if (r > rb) ex[`${r - n},${c}`] = 1;
    }
    t.excluded = ex;
    sel = { r0: ra, c0: sel.c0, r1: ra, c1: sel.c0 };
    changed();
  }
  function shiftExcluded(at, n) {
    const ex = {};
    for (const k of Object.keys(t.excluded)) {
      const [r, c] = k.split(',').map(Number);
      ex[`${r >= at ? r + n : r},${c}`] = 1;
    }
    t.excluded = ex;
  }
  function sortBy(ci) {
    const n = t.cells.length;
    const idx = [...Array(n).keys()].filter((r) => [get(r, ci)].some((v) => v !== ''));
    const empty = [...Array(n).keys()].filter((r) => get(r, ci) === '');
    idx.sort((a, b) => {
      const va = Number(get(a, ci)); const vb = Number(get(b, ci));
      if (!Number.isNaN(va) && !Number.isNaN(vb)) return va - vb;
      return String(get(a, ci)).localeCompare(String(get(b, ci)));
    });
    const order = idx.concat(empty);
    t.cells = order.map((r) => t.cells[r]);
    t.rowLabels = order.map((r) => t.rowLabels[r]);
    t.x = order.map((r) => t.x[r]);
    t.excluded = {};
    changed();
  }
  async function renameDs(i) {
    const v = await prompt('Rename data set', t.datasets[i].name, 'Data set title');
    if (v !== null && v !== '') { t.datasets[i].name = v; changed(); emit('table-structure', t.id); }
  }
  async function renameX() {
    const v = await prompt('X column title', t.xTitle, 'Title of the X column');
    if (v !== null && v !== '') { t.xTitle = v; changed(); }
  }
  function dsMenu(e, i) {
    contextMenu(e.clientX, e.clientY, [
      ...(t.datasets[i].formula ? [{ label: `Edit formula (= ${t.datasets[i].formula})…`, action: () => window.dispatchEvent(new CustomEvent('openprism-formula', { detail: { tableId: t.id, index: i } })) },
        { label: 'Convert to ordinary values (remove formula)', action: () => { delete t.datasets[i].formula; changed(); } }] : []),
      { label: 'Rename…', action: () => renameDs(i) },
      { label: 'Set number of replicates…', action: async () => {
        const v = await prompt('Replicates', String(t.datasets[i].reps || 1), 'Number of subcolumns (replicate values) for this data set');
        const n = parseInt(v, 10);
        if (n >= 1 && n <= 50) { setReps(t, i, n); changed(); emit('table-structure', t.id); }
      } },
      { label: 'Insert data set before', action: () => { addDataset(t, i); changed(); emit('table-structure', t.id); } },
      { label: 'Insert data set after', action: () => { addDataset(t, i + 1); changed(); emit('table-structure', t.id); } },
      '-',
      { label: 'Move left', action: () => { moveDataset(t, i, -1); changed(); emit('table-structure', t.id); } },
      { label: 'Move right', action: () => { moveDataset(t, i, 1); changed(); emit('table-structure', t.id); } },
      '-',
      { label: 'Delete data set', action: () => { deleteDataset(t, i); changed(); emit('table-structure', t.id); } },
    ]);
  }

  draw();
  setTimeout(() => scroller()?.addEventListener('scroll', onScroll, { passive: true }), 0);
  wrap.focus({ preventScroll: true });
  return { redraw: draw, paste: pasteText };
}

function ensureSpare(t) {
  const width = colOffset(t, t.datasets.length);
  let last = t.cells.length - 1;
  const empty = (r) => t.cells[r].every((v) => v === '') && !t.rowLabels[r] && !t.x[r];
  let trailing = 0;
  while (last >= 0 && empty(last)) { trailing++; last--; }
  for (let i = trailing; i < SPARE_ROWS; i++) { t.cells.push(Array(width).fill('')); t.rowLabels.push(''); t.x.push(''); }
}

// ---------- structural helpers (exported for ribbon buttons) ----------
export function addDataset(t, at = t.datasets.length) {
  const reps = t.datasets[0]?.reps || 1;
  const off = colOffset(t, at);
  t.datasets.splice(at, 0, { name: `Data set ${letter(t.datasets.length)}`, reps });
  t.cells.forEach((row) => row.splice(off, 0, ...Array(reps).fill('')));
  shiftExcludedCols(t, off, reps);
}
export function deleteDataset(t, i) {
  if (t.datasets.length <= 1) return;
  const off = colOffset(t, i);
  const reps = t.datasets[i].reps || 1;
  t.datasets.splice(i, 1);
  t.cells.forEach((row) => row.splice(off, reps));
  const ex = {};
  for (const k of Object.keys(t.excluded)) {
    const [r, c] = k.split(',').map(Number);
    if (c < off) ex[k] = 1; else if (c >= off + reps) ex[`${r},${c - reps}`] = 1;
  }
  t.excluded = ex;
}
export function setReps(t, i, n) {
  const off = colOffset(t, i);
  const cur = t.datasets[i].reps || 1;
  if (n > cur) { t.cells.forEach((row) => row.splice(off + cur, 0, ...Array(n - cur).fill(''))); shiftExcludedCols(t, off + cur, n - cur); }
  else if (n < cur) t.cells.forEach((row) => row.splice(off + n, cur - n));
  t.datasets[i].reps = n;
}
export function setAllReps(t, n) { t.datasets.forEach((_, i) => setReps(t, i, n)); t.excluded = {}; }
function moveDataset(t, i, d) {
  const j = i + d;
  if (j < 0 || j >= t.datasets.length) return;
  const offs = t.datasets.map((_, k) => colOffset(t, k));
  t.cells = t.cells.map((row) => {
    const blocks = t.datasets.map((ds, k) => row.slice(offs[k], offs[k] + (ds.reps || 1)));
    [blocks[i], blocks[j]] = [blocks[j], blocks[i]];
    return blocks.flat();
  });
  [t.datasets[i], t.datasets[j]] = [t.datasets[j], t.datasets[i]];
  t.excluded = {};
}
function shiftExcludedCols(t, at, n) {
  const ex = {};
  for (const k of Object.keys(t.excluded)) {
    const [r, c] = k.split(',').map(Number);
    ex[`${r},${c >= at ? c + n : c}`] = 1;
  }
  t.excluded = ex;
}
