// "Which test should I use?" wizard and the command palette (Ctrl+Shift+P).
import { CATALOG } from './analysis.js';
import { TABLE_TYPES } from './state.js';
import { fitToViewport, h, modal } from './ui.js';

const norm = (s) => String(s || '').toLowerCase();

/** Find the analysis whose label best matches a test name from the chooser table. */
function matchAnalysis(name) {
  const n = norm(name).replace(/\(.*?\)/g, '');
  const words = n.split(/[^a-z0-9²-]+/).filter((w) => w.length > 2);
  let best = null;
  let score = 0;
  for (const a of CATALOG.analyses) {
    const hay = norm(`${a.label} ${a.guide?.what || ''}`);
    const s = words.reduce((acc, w) => acc + (norm(a.label).includes(w) ? 3 : hay.includes(w) ? 1 : 0), 0);
    if (s > score) { score = s; best = a; }
  }
  return score >= 3 ? best : null;
}

/**
 * Guided choice of a statistical test. *table* (optional) is the current data
 * table; *onPick(key)* opens the Analyze dialog with that analysis.
 */
export function testChooser(table, onPick) {
  const rows = CATALOG.chooser || [];
  let filter = table ? table.type : 'all';
  let q = '';
  const list = h('div', { class: 'chooser-list' });
  const search = h('input', { type: 'search', placeholder: 'Describe your goal, e.g. "paired", "survival", "agreement", "counts"…', oninput: (e) => { q = norm(e.target.value); draw(); } });
  const types = [['all', 'All table types'], ...Object.entries(TABLE_TYPES).map(([k, v]) => [k, v.label])];
  const sel = h('select', { onchange: (e) => { filter = e.target.value; draw(); } }, types.map(([k, l]) => h('option', { value: k, selected: k === filter }, l)));
  function pickBtn(name, primary) {
    const a = matchAnalysis(name);
    const usable = a && (!table || a.tableTypes.includes(table.type));
    return h('button', {
      class: `chip${primary ? ' primary' : ''}`, disabled: !a,
      title: a ? (usable ? `Open: ${a.label}` : `${a.label} needs a ${a.tableTypes.map((t) => TABLE_TYPES[t]?.label || t).join(' / ')} table`) : 'See the manual',
      onclick: () => { if (a && usable && onPick) { ctl.close(); onPick(a.key); } },
    }, name);
  }
  function draw() {
    list.innerHTML = '';
    const shown = rows.filter(([goal, main, alt, tt]) => (filter === 'all' || tt === filter || tt === '—')
      && (!q || norm(`${goal} ${main} ${alt}`).includes(q)));
    if (!shown.length) list.append(h('p', { class: 'hint' }, 'No match — try other words or "All table types".'));
    for (const [goal, main, alt, tt] of shown) {
      list.append(h('div', { class: 'chooser-row' },
        h('div', { class: 'goal' }, goal, h('span', { class: 'tt' }, tt === '—' ? '' : TABLE_TYPES[tt]?.label || tt)),
        h('div', { class: 'opts' }, h('span', { class: 'lbl' }, 'Use'), ...main.split(/;\s*/).map((m) => pickBtn(m, true)),
          alt && alt !== '—' ? h('span', { class: 'lbl' }, 'If assumptions fail / alternatives') : null,
          ...(alt && alt !== '—' ? alt.split(/;\s*/).map((m) => pickBtn(m, false)) : []))));
    }
  }
  draw();
  const ctl = modal({
    title: 'Which test should I use?', wide: true,
    body: h('div', {}, h('p', { class: 'hint' }, 'Find your goal, then click a test to open it. Blue = first choice (assumptions met); grey = alternatives when data are not Gaussian, have outliers or unequal SDs. Each analysis dialog has an “About this analysis” panel explaining when it applies.'),
      h('div', { style: { display: 'flex', gap: '8px', margin: '8px 0' } }, search, sel), list),
    buttons: [{ label: 'Close' }],
  });
  setTimeout(() => search.focus(), 50);
}

/** Command palette: fuzzy search over every menu command and every analysis. */
export function commandPalette(menus, onAnalysis) {
  const items = [];
  for (const [menu, entries] of menus) {
    for (const it of entries) {
      if (it === '-' || it[3]) continue;
      items.push({ label: it[0], hint: menu, key: it[2], run: it[1] });
    }
  }
  const seen = new Set(items.map((it) => it.label));
  for (const a of CATALOG.analyses) if (!seen.has(a.label)) items.push({ label: a.label, hint: `Analysis · ${a.category}`, run: () => onAnalysis(a.key), extra: a.guide?.when || '' });
  let idx = 0;
  let shown = items;
  const input = h('input', { type: 'search', class: 'palette-input', placeholder: 'Type a command or analysis… (↑↓ to move, Enter to run, Esc to close)' });
  const list = h('div', { class: 'palette-list' });
  const box = h('div', { class: 'palette' }, input, list);
  const backdrop = h('div', { class: 'palette-backdrop', onclick: (e) => { if (e.target === backdrop) done(); } }, box);
  function score(it, q) {
    if (!q) return 1;
    const l = norm(it.label);
    if (l.startsWith(q)) return 100;
    if (l.includes(q)) return 50;
    let pos = 0;
    for (const ch of q) { pos = l.indexOf(ch, pos); if (pos < 0) return norm(it.extra).includes(q) ? 5 : 0; pos++; }
    return 10;
  }
  function draw() {
    const q = norm(input.value).trim();
    shown = items.map((it) => [score(it, q), it]).filter(([s]) => s > 0).sort((a, b) => b[0] - a[0]).slice(0, 40).map(([, it]) => it);
    idx = Math.min(idx, Math.max(0, shown.length - 1));
    list.innerHTML = '';
    shown.forEach((it, i) => list.append(h('button', { class: `palette-item${i === idx ? ' on' : ''}`, onclick: () => { idx = i; run(); } },
      h('span', {}, it.label.replace(/…$/, '')), h('span', { class: 'ph' }, it.hint), it.key ? h('kbd', {}, it.key) : null)));
    list.querySelector('.on')?.scrollIntoView({ block: 'nearest' });
  }
  function done() { backdrop.remove(); }
  function run() { const it = shown[idx]; done(); if (it) setTimeout(() => it.run(), 0); }  // after the key event, so Enter cannot also submit the next dialog
  input.addEventListener('input', () => { idx = 0; draw(); });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); idx = Math.min(idx + 1, shown.length - 1); draw(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); idx = Math.max(idx - 1, 0); draw(); }
    else if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); run(); }
    else if (e.key === 'Escape') { e.preventDefault(); done(); }
  });
  document.body.append(backdrop);
  draw();
  fitToViewport?.(box);
  input.focus();
}
