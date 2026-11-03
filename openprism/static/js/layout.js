// Page layout editor: arrange graphs and text on a page with drag, resize,
// snapping, keyboard nudging, auto-arrange and PNG / SVG / PDF export.
import { exportDialog, graphSvgText, renderSvgTo } from './exporter.js';
import { figureFor } from './graphs.js';
import { helpIcon } from './help.js';
import { P, commit, getAnalysis, getGraph, uid } from './state.js';
import { contextMenu, download, field, h, modal, select, toast } from './ui.js';

export const PAGE_SIZES = {
  'letter-l': ['US Letter landscape', 1056, 816], 'letter-p': ['US Letter portrait', 816, 1056],
  'a4-l': ['A4 landscape', 1123, 794], 'a4-p': ['A4 portrait', 794, 1123], slide: ['Slide 16:9', 1280, 720], square: ['Square', 900, 900],
};

export function renderLayoutView(body, inspector, L, tools) {
  const stage = h('div', { class: 'layout-stage' });
  const page = h('div', { class: `layout-page ${L.grid ? 'gridded' : ''}`, style: { width: `${L.page.w}px`, height: `${L.page.h}px` } });
  stage.append(page);
  body.append(stage);
  let selected = null;
  const SNAP = 10;
  const snap = (v) => (L.grid ? Math.round(v / SNAP) * SNAP : Math.round(v));

  async function drawItem(it) {
    let el = page.querySelector(`[data-id="${it.id}"]`);
    if (!el) {
      el = h('div', { class: `litem ${it.type === 'label' ? 'panel-label' : ''}`, 'data-id': it.id });
      page.append(el);
      bindItem(el, it);
    }
    Object.assign(el.style, { left: `${it.x}px`, top: `${it.y}px`, width: `${it.w}px`, height: `${it.h}px`, zIndex: it.z || 1 });
    el.classList.toggle('sel', selected === it.id);
    if (it.type === 'graph') {
      let gp = el.querySelector('.gplot');
      if (!gp) { gp = h('div', { class: 'gplot' }); el.prepend(gp); }
      const g = getGraph(it.graphId);
      if (!g) { gp.innerHTML = '<div style="padding:10px;color:#a00">Graph deleted</div>'; return; }
      try {
        const fig = await figureFor(g, { width: it.w, height: it.h });
        fig.layout.width = it.w; fig.layout.height = it.h;
        await Plotly.react(gp, fig.data, fig.layout, { staticPlot: true, displayModeBar: false });
      } catch (e) { gp.textContent = e.message; }
    } else if (it.type === 'image') {
      let im = el.querySelector('img.limg');
      if (!im) { im = h('img', { class: 'limg', alt: it.name || 'image', draggable: 'false' }); el.prepend(im); }
      if (im.getAttribute('src') !== it.src) im.src = it.src;
      Object.assign(im.style, { objectFit: it.fit === 'stretch' ? 'fill' : 'contain', opacity: it.opacity ?? 1 });
    } else if (it.type === 'shape') {
      el.querySelector('.lshape')?.remove();
      const box = h('div', { class: 'lshape' });
      box.innerHTML = `<svg width="${it.w}" height="${it.h}" viewBox="${it.x} ${it.y} ${it.w} ${it.h}" style="overflow:visible;display:block">${shapeSvg(it)}</svg>`;
      el.prepend(box);
    } else if (it.type === 'table') {
      el.querySelector('.ltable')?.remove();
      const tb = tableModel(it);
      const box = h('div', { class: 'ltable', style: { fontSize: `${it.fontSize || 11}px`, fontFamily: it.font || 'Arial' } },
        tb ? [h('div', { class: 'ltable-title' }, tb.title),
          h('table', {}, tb.header ? h('thead', {}, h('tr', {}, tb.header.map((c) => h('th', {}, c)))) : null,
            h('tbody', {}, tb.rows.map((r) => h('tr', {}, r.map((c, j) => h('td', { class: j > 0 ? 'num' : '' }, c))))))]
          : h('div', { class: 'hint' }, 'The analysis for this table was deleted.'));
      el.prepend(box);
    } else {
      let tx = el.querySelector('.ltext');
      if (!tx) {
        tx = h('div', { class: 'ltext' });
        el.prepend(tx);
        tx.addEventListener('blur', () => { tx.contentEditable = 'false'; if (tx.innerText !== it.text) { it.text = tx.innerText; commit('Edit text'); } });
      }
      if (document.activeElement !== tx) tx.innerText = it.text;
      Object.assign(tx.style, { fontSize: `${it.fontSize || 16}px`, fontWeight: it.bold ? '700' : '400', fontStyle: it.italic ? 'italic' : 'normal', textAlign: it.align || 'left', fontFamily: it.font || 'Arial' });
    }
    if (!el.querySelector('.h')) ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'].forEach((d) => el.append(h('div', { class: `h ${d}`, 'data-dir': d })));
  }

  function select_(id) {
    selected = id;
    page.querySelectorAll('.litem').forEach((e) => e.classList.toggle('sel', e.dataset.id === id));
    drawInspector();
  }

  function bindItem(el, it) {
    el.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return;
      const tx = el.querySelector('.ltext');
      if (tx && tx.isContentEditable) return;
      e.preventDefault();
      e.stopPropagation();
      select_(it.id);
      el.setPointerCapture(e.pointerId);
      const dir = e.target.dataset.dir;
      const sx = e.clientX; const sy = e.clientY;
      const o = { x: it.x, y: it.y, w: it.w, h: it.h };
      let moved = false;
      const mv = (ev) => {
        const dx = ev.clientX - sx; const dy = ev.clientY - sy;
        if (Math.abs(dx) + Math.abs(dy) > 2) moved = true;
        if (!dir) { it.x = snap(Math.max(0, Math.min(L.page.w - it.w, o.x + dx))); it.y = snap(Math.max(0, Math.min(L.page.h - it.h, o.y + dy))); }
        else {
          if (dir.includes('e')) it.w = snap(Math.max(40, o.w + dx));
          if (dir.includes('s')) it.h = snap(Math.max(24, o.h + dy));
          if (dir.includes('w')) { const nw = snap(Math.max(40, o.w - dx)); it.x = o.x + o.w - nw; it.w = nw; }
          if (dir.includes('n')) { const nh = snap(Math.max(24, o.h - dy)); it.y = o.y + o.h - nh; it.h = nh; }
          if (e.shiftKey && it.type === 'graph') it.h = Math.round(it.w * (o.h / o.w));
        }
        Object.assign(el.style, { left: `${it.x}px`, top: `${it.y}px`, width: `${it.w}px`, height: `${it.h}px` });
      };
      const up = async () => {
        el.removeEventListener('pointermove', mv); el.removeEventListener('pointerup', up);
        if (moved) { commit(dir ? 'Resize item' : 'Move item'); if (dir) await drawItem(it); drawInspector(); }
      };
      el.addEventListener('pointermove', mv);
      el.addEventListener('pointerup', up);
    });
    el.addEventListener('dblclick', (e) => {
      const tx = el.querySelector('.ltext');
      if (tx) { tx.contentEditable = 'true'; tx.focus(); document.getSelection().selectAllChildren(tx); e.stopPropagation(); }
      else if (it.type === 'graph') tools.openGraph(it.graphId);
    });
    el.addEventListener('contextmenu', (e) => {
      e.preventDefault(); select_(it.id);
      contextMenu(e.clientX, e.clientY, [
        { label: 'Bring to front', action: () => { it.z = Math.max(1, ...L.items.map((x) => x.z || 1)) + 1; commit('Order'); drawItem(it); } },
        { label: 'Send to back', action: () => { L.items.forEach((x) => { x.z = (x.z || 1) + 1; }); it.z = 1; commit('Order'); L.items.forEach(drawItem); } },
        { label: 'Duplicate', action: () => { const c = { ...it, id: uid('i'), x: it.x + 20, y: it.y + 20 }; L.items.push(c); commit('Duplicate'); drawItem(c); select_(c.id); } },
        it.type === 'graph' ? { label: 'Open graph', action: () => tools.openGraph(it.graphId) } : { label: 'Edit text', action: () => el.dispatchEvent(new MouseEvent('dblclick')) },
        '-',
        { label: 'Remove from layout', action: () => removeItem(it.id) },
      ]);
    });
  }

  function removeItem(id) {
    L.items = L.items.filter((x) => x.id !== id);
    page.querySelector(`[data-id="${id}"]`)?.remove();
    if (selected === id) selected = null;
    commit('Remove item');
    drawInspector();
  }

  page.addEventListener('pointerdown', (e) => { if (e.target === page) select_(null); });
  const onKey = (e) => {
    if (!document.body.contains(page)) { document.removeEventListener('keydown', onKey); return; }
    if (!selected || ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName) || e.target.isContentEditable) return;
    const it = L.items.find((x) => x.id === selected);
    if (!it) return;
    const step = e.shiftKey ? 10 : 1;
    const d = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
    if (d) { e.preventDefault(); it.x += d[0]; it.y += d[1]; drawItem(it); commitNudge(); }
    else if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); removeItem(it.id); }
  };
  let nudgeT; const commitNudge = () => { clearTimeout(nudgeT); nudgeT = setTimeout(() => commit('Nudge'), 400); };
  document.addEventListener('keydown', onKey);

  function drawInspector() {
    inspector.hidden = false;
    inspector.innerHTML = '';
    const sec = (title, ...kids) => h('div', { class: 'insp-sec' }, h('h4', {}, title, helpIcon('layouts')), ...kids);
    const sizeKey = Object.keys(PAGE_SIZES).find((k) => PAGE_SIZES[k][1] === L.page.w && PAGE_SIZES[k][2] === L.page.h) || 'letter-l';
    inspector.append(sec('Page',
      field('Size', select(Object.entries(PAGE_SIZES).map(([k, v]) => [k, v[0]]), sizeKey, (v) => { L.page = { w: PAGE_SIZES[v][1], h: PAGE_SIZES[v][2] }; page.style.width = `${L.page.w}px`; page.style.height = `${L.page.h}px`; commit('Page size'); })),
      h('div', { class: 'field check' }, h('label', {}, h('input', { type: 'checkbox', checked: L.grid, onchange: (e) => { L.grid = e.target.checked; page.classList.toggle('gridded', L.grid); commit('Grid'); } }), 'Show grid & snap to grid'))));
    const graphs = P().graphs;
    const addSel = h('select', { style: { flex: '1 1 120px', minWidth: 0 } }, graphs.map((g) => h('option', { value: g.id }, g.name)));
    inspector.append(sec('Add to page',
      h('div', { style: { display: 'flex', gap: '6px', marginBottom: '6px', flexWrap: 'wrap' } }, addSel, h('button', { class: 'btn small', onclick: () => addSel.value && addGraph(addSel.value) }, 'Add graph')),
      h('div', { style: { display: 'flex', gap: '6px', flexWrap: 'wrap' } },
        h('button', { class: 'btn small', onclick: () => addText('Text', 16) }, 'Text box'),
        h('button', { class: 'btn small', onclick: () => addText('Figure title', 24, true) }, 'Title'),
        h('button', { class: 'btn small', onclick: addPanelLabels }, 'Panel labels A, B, C…'),
        h('button', { class: 'btn small', onclick: arrange }, 'Auto-arrange graphs')),
      h('div', { style: { display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '6px' } }, h('span', { class: 'hint', style: { alignSelf: 'center' } }, 'Shapes:'),
        ...[['line', '╱ Line'], ['arrow', '➘ Arrow'], ['rect', '▭ Rectangle'], ['ellipse', '◯ Ellipse'], ['bracket', '⊓ Bracket']].map(([k, l]) =>
          h('button', { class: 'btn small', title: `Add a ${k}`, onclick: () => addShape(k) }, l))),
      h('div', { style: { display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '6px' } },
        h('button', { class: 'btn small', title: 'Add a microscopy image, blot, photo or schematic (PNG or JPEG)', onclick: addImage }, '🖼 Add image…')),
      tableAdder()));
    const it = L.items.find((x) => x.id === selected);
    if (it) {
      const num = (k) => h('input', { type: 'number', value: it[k], oninput: (e) => { it[k] = +e.target.value; drawItem(it); commitNudge(); } });
      const s = sec('Selected item', field('X / Y', h('div', { style: { display: 'flex', gap: '4px' } }, num('x'), num('y'))), field('W / H', h('div', { style: { display: 'flex', gap: '4px' } }, num('w'), num('h'))));
      if (it.type === 'image') {
        s.append(field('Fit', h('div', { class: 'seg' }, [['contain', 'Keep proportions'], ['stretch', 'Stretch to box']].map(([k, l]) =>
          h('button', { class: (it.fit || 'contain') === k ? 'on' : '', onclick: () => { it.fit = k; commit('Image fit'); drawItem(it); drawInspector(); } }, l)))));
        s.append(field('Size', h('button', { class: 'btn small', title: 'Resize the box to the image’s proportions', onclick: () => { it.h = Math.round(it.w * it.ih / it.iw); commit('Image size'); drawItem(it); drawInspector(); } }, 'Match image proportions')));
        s.append(h('div', { class: 'hint' }, `${it.name || 'Image'} · ${it.iw} × ${it.ih} px · ${(it.src.length * 0.75 / 1024).toFixed(0)} KB (stored encrypted in the project)`));
      } else if (it.type === 'shape') {
        const color = (key, label, allowNone) => h('div', { style: { display: 'flex', gap: '6px', alignItems: 'center' } },
          h('input', { type: 'color', value: it[key] && it[key] !== 'none' ? it[key] : '#ffffff', oninput: (e) => { it[key] = e.target.value; drawItem(it); commitNudge(); } }),
          allowNone ? h('label', { class: 'check-line', style: { margin: 0 } }, h('input', { type: 'checkbox', checked: !it[key] || it[key] === 'none', onchange: (e) => { it[key] = e.target.checked ? 'none' : '#dddddd'; commit('Shape fill'); drawItem(it); drawInspector(); } }), 'none') : null);
        s.append(field('Line colour', color('stroke')));
        if (['rect', 'ellipse'].includes(it.shape)) s.append(field('Fill', color('fill', 'Fill', true)));
        s.append(field('Line width', h('input', { type: 'number', min: 0.25, step: 0.25, value: it.width ?? 2, oninput: (e) => { it.width = +e.target.value; drawItem(it); commitNudge(); } })));
        s.append(field('Dashed', h('input', { type: 'checkbox', checked: !!it.dash, onchange: (e) => { it.dash = e.target.checked; commit('Shape style'); drawItem(it); } })));
        if (['line', 'arrow'].includes(it.shape)) {
          s.append(field('Direction', h('div', { class: 'seg' }, [['down', '↘'], ['up', '↗'], ['h', '→'], ['v', '↓']].map(([d, l]) =>
            h('button', { class: (it.dir || 'down') === d ? 'on' : '', onclick: () => { it.dir = d; commit('Shape direction'); drawItem(it); drawInspector(); } }, l)))));
        }
        if (it.shape === 'arrow') {
          s.append(field('Heads', h('div', { class: 'seg' }, [['end', 'End'], ['start', 'Start'], ['both', 'Both']].map(([d, l]) =>
            h('button', { class: (it.heads || 'end') === d ? 'on' : '', onclick: () => { it.heads = d; commit('Arrow heads'); drawItem(it); drawInspector(); } }, l)))));
        }
      } else if (it.type !== 'graph') {
        if (it.type === 'table') {
          const an = getAnalysis(it.analysisId);
          if (an?.result) s.append(field('Section', select(an.result.sections.map((sx, k) => [k, sx.title]), it.section || 0, (v) => { it.section = +v; commit('Table section'); drawItem(it); })));
        }
        s.append(field('Font size', h('input', { type: 'number', value: it.fontSize || 16, oninput: (e) => { it.fontSize = +e.target.value; drawItem(it); commitNudge(); } })));
        s.append(field('Style', h('div', { class: 'seg' },
          h('button', { class: it.bold ? 'on' : '', onclick: () => { it.bold = !it.bold; commit('Text style'); drawItem(it); drawInspector(); } }, 'B'),
          h('button', { class: it.italic ? 'on' : '', onclick: () => { it.italic = !it.italic; commit('Text style'); drawItem(it); drawInspector(); } }, 'I'),
          ...['left', 'center', 'right'].map((a) => h('button', { class: (it.align || 'left') === a ? 'on' : '', onclick: () => { it.align = a; commit('Align'); drawItem(it); drawInspector(); } }, a[0].toUpperCase())))));
      }
      s.append(h('button', { class: 'btn small danger', onclick: () => removeItem(it.id) }, 'Remove'));
      inspector.append(s);
    }
    inspector.append(sec('Export layout', h('div', { style: { display: 'flex', gap: '6px', flexWrap: 'wrap' } },
      h('button', { class: 'btn small primary', onclick: () => layoutExportDialog(L) }, 'Export… (format, size, dpi)'),
      h('button', { class: 'btn small', onclick: () => exportLayout(L, 'tiff') }, 'TIFF 300 dpi'),
      h('button', { class: 'btn small', onclick: () => exportLayout(L, 'pdf') }, 'PDF'),
      h('button', { class: 'btn small', onclick: () => exportLayout(L, 'svg') }, 'SVG'),
      h('button', { class: 'btn small', title: 'Vector for Word / PowerPoint', onclick: () => exportLayout(L, 'emf') }, 'EMF'),
      h('button', { class: 'btn small', title: 'Vector for Illustrator, LaTeX, print', onclick: () => exportLayout(L, 'eps') }, 'EPS'),
      h('button', { class: 'btn small', onclick: () => { select_(null); window.print(); } }, 'Print / PDF'))));
    inspector.append(sec('Tips', h('div', { class: 'hint' }, 'Drag items to move, drag the handles to resize (Shift keeps a graph’s aspect ratio). Arrow keys nudge, Delete removes. Double-click a graph to edit it, or a text box to type.')));
  }

  function tableAdder() {
    const ans = P().analyses.filter((a) => a.result?.sections?.length);
    if (!ans.length) return h('div', { class: 'hint', style: { marginTop: '6px' } }, 'Run an analysis to embed its results table.');
    const aSel = h('select', { style: { flex: '1 1 120px', minWidth: 0 } }, ans.map((a) => h('option', { value: a.id }, a.name)));
    return h('div', { style: { display: 'flex', gap: '6px', marginTop: '6px', flexWrap: 'wrap' } }, aSel,
      h('button', { class: 'btn small', onclick: () => {
        const it = { id: uid('i'), type: 'table', analysisId: aSel.value, section: 0, fontSize: 11, x: 40, y: 40, w: 360, h: 180, z: L.items.length + 1 };
        L.items.push(it); commit('Add results table'); drawItem(it); select_(it.id);
      } }, 'Add results table'));
  }

  async function addGraph(graphId, at) {
    const g = getGraph(graphId);
    const w = Math.min(g?.style.width || 480, L.page.w - 40); const hh = Math.min(g?.style.height || 360, L.page.h - 40);
    const n = L.items.length;
    const it = { id: uid('i'), type: 'graph', graphId, x: at?.x ?? snap(20 + (n % 4) * 30), y: at?.y ?? snap(20 + (n % 4) * 30), w, h: hh, z: n + 1 };
    L.items.push(it);
    commit('Add graph to layout');
    await drawItem(it);
    select_(it.id);
  }
  function addText(text, size, bold) {
    const it = { id: uid('i'), type: 'text', text, fontSize: size, bold: !!bold, x: 40, y: 20, w: Math.max(200, text.length * size * 0.6), h: size * 1.8, z: L.items.length + 1 };
    if (bold) { it.align = 'center'; it.x = 40; it.w = L.page.w - 80; }
    L.items.push(it);
    commit('Add text');
    drawItem(it);
    select_(it.id);
  }
  function addImage() {
    const inp = h('input', { type: 'file', accept: 'image/png,image/jpeg', hidden: true });
    inp.addEventListener('change', async () => {
      const f = inp.files[0];
      inp.remove();
      if (!f) return;
      if (f.size > 40 * 1024 * 1024) { toast('Image too large (max 40 MB)', 'err'); return; }
      try {
        const img = await loadImage(URL.createObjectURL(f));
        // keep projects small: images larger than 3000 px are downscaled (enough for 600 dpi at 5 inches)
        const MAX = 3000;
        const k = Math.min(1, MAX / Math.max(img.naturalWidth, img.naturalHeight));
        const w = Math.round(img.naturalWidth * k); const hh = Math.round(img.naturalHeight * k);
        let src;
        if (k < 1 || f.size > 3 * 1024 * 1024) {
          const c = document.createElement('canvas'); c.width = w; c.height = hh;
          c.getContext('2d').drawImage(img, 0, 0, w, hh);
          src = f.type === 'image/png' ? c.toDataURL('image/png') : c.toDataURL('image/jpeg', 0.92);
          if (src.length > 12 * 1024 * 1024) src = c.toDataURL('image/jpeg', 0.9);
        } else {
          src = await new Promise((res) => { const rd = new FileReader(); rd.onload = () => res(rd.result); rd.readAsDataURL(f); });
        }
        const boxW = Math.min(320, L.page.w - 80);
        const it = { id: uid('i'), type: 'image', name: f.name.slice(0, 80), src, iw: w, ih: hh, fit: 'contain', x: 40, y: 40, w: boxW, h: Math.round(boxW * hh / w), z: L.items.length + 1 };
        L.items.push(it);
        commit('Add image');
        drawItem(it);
        select_(it.id);
        if (k < 1) toast(`Image downscaled to ${w} × ${hh} px`);
      } catch (_) { toast('Could not read this image (use PNG or JPEG)', 'err'); }
    });
    document.body.append(inp);
    inp.click();
  }
  function loadImage(url) {
    return new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = rej; im.src = url; });
  }
  function addShape(shape) {
    const size = { line: [160, 60], arrow: [140, 50], rect: [180, 110], ellipse: [150, 100], bracket: [160, 24] }[shape];
    const it = { id: uid('i'), type: 'shape', shape, x: 60, y: 60, w: size[0], h: size[1], stroke: '#111111', fill: 'none', width: shape === 'rect' || shape === 'ellipse' ? 1.5 : 2, dir: shape === 'bracket' ? 'h' : 'down', heads: 'end', z: L.items.length + 1 };
    L.items.push(it);
    commit(`Add ${shape}`);
    drawItem(it);
    select_(it.id);
  }
  function addPanelLabels() {
    const gs = L.items.filter((x) => x.type === 'graph').sort((a, b) => a.y - b.y || a.x - b.x);
    gs.forEach((gi, k) => {
      const it = { id: uid('i'), type: 'label', text: String.fromCharCode(65 + (k % 26)), fontSize: 22, bold: true, x: Math.max(0, gi.x - 6), y: Math.max(0, gi.y - 6), w: 34, h: 34, z: 50 };
      L.items.push(it);
      drawItem(it);
    });
    commit('Panel labels');
  }
  async function arrange() {
    const gs = L.items.filter((x) => x.type === 'graph');
    if (!gs.length) { toast('Add graphs to the layout first'); return; }
    const n = gs.length;
    const cols = Math.ceil(Math.sqrt(n * (L.page.w / L.page.h)));
    const rows = Math.ceil(n / cols);
    const top = L.items.some((x) => x.type === 'text' && x.bold) ? 60 : 20;
    const gw = Math.floor((L.page.w - 40 - (cols - 1) * 20) / cols);
    const gh = Math.floor((L.page.h - top - 20 - (rows - 1) * 20) / rows);
    gs.forEach((it, k) => { it.x = 20 + (k % cols) * (gw + 20); it.y = top + Math.floor(k / cols) * (gh + 20); it.w = gw; it.h = gh; });
    commit('Arrange');
    for (const it of gs) await drawItem(it);
  }

  // drop graphs from the navigator onto the page
  page.addEventListener('dragover', (e) => { if (e.dataTransfer.types.includes('text/openprism-graph')) e.preventDefault(); });
  page.addEventListener('drop', (e) => {
    const id = e.dataTransfer.getData('text/openprism-graph');
    if (!id) return;
    e.preventDefault();
    const r = page.getBoundingClientRect();
    addGraph(id, { x: snap(e.clientX - r.left - 100), y: snap(e.clientY - r.top - 80) });
  });

  L.items.forEach(drawItem);
  drawInspector();
  return { addGraph };
}

/** Results table embedded in a layout: {title, header, rows} from an analysis section. */
function tableModel(it) {
  const a = getAnalysis(it.analysisId);
  const sec = a?.result?.sections?.[it.section || 0];
  if (!sec) return null;
  const rows = sec.rows.map((r) => r.map((c) => String(c ?? '')));
  return { title: `${a.result.title} — ${sec.title}`, header: sec.kind === 'table' ? sec.columns.map(String) : null, rows };
}

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const measure = (() => { const c = document.createElement('canvas').getContext('2d'); return (text, font) => { c.font = font; return c.measureText(text).width; }; })();

function tableSvg(it) {
  const tb = tableModel(it);
  if (!tb) return '';
  const fs = it.fontSize || 11; const font = `${fs}px ${it.font || 'Arial'}`; const lh = fs * 1.5;
  const all = [...(tb.header ? [tb.header] : []), ...tb.rows];
  const ncol = Math.max(...all.map((r) => r.length));
  const widths = Array.from({ length: ncol }, (_, j) => Math.max(...all.map((r) => measure(r[j] || '', `${j === 0 || all.indexOf(r) === 0 ? '600 ' : ''}${font}`))) + fs);
  let y = it.y + fs * 1.3;
  const out = [`<g font-family="${esc(it.font || 'Arial')}" font-size="${fs}">`, `<text x="${it.x}" y="${y}" font-weight="700">${esc(tb.title)}</text>`];
  y += lh * 0.6;
  all.forEach((r, ri) => {
    y += lh;
    if (y > it.y + it.h) return;
    let x = it.x;
    r.forEach((c, j) => {
      const right = j > 0;
      out.push(`<text x="${right ? x + widths[j] - fs / 2 : x}" y="${y}" text-anchor="${right ? 'end' : 'start'}"${ri === 0 && tb.header ? ' font-weight="600"' : ''}>${esc(c)}</text>`);
      x += widths[j];
    });
    if (ri === 0 && tb.header) out.push(`<line x1="${it.x}" x2="${x}" y1="${y + lh * 0.3}" y2="${y + lh * 0.3}" stroke="#000" stroke-width="0.8"/>`);
  });
  out.push('</g>');
  return out.join('');
}

/** SVG for a layout shape, in page coordinates (also used for every export format). */
export function shapeSvg(it) {
  const sw = it.width ?? 2;
  const stroke = it.stroke || '#111';
  const dash = it.dash ? ` stroke-dasharray="${sw * 4},${sw * 3}"` : '';
  const common = `stroke="${stroke}" stroke-width="${sw}"${dash} stroke-linecap="round" stroke-linejoin="round"`;
  const { x, y, w, h: hh } = it;
  if (it.shape === 'rect') return `<rect x="${x}" y="${y}" width="${w}" height="${hh}" fill="${it.fill || 'none'}" ${common}/>`;
  if (it.shape === 'ellipse') return `<ellipse cx="${x + w / 2}" cy="${y + hh / 2}" rx="${w / 2}" ry="${hh / 2}" fill="${it.fill || 'none'}" ${common}/>`;
  if (it.shape === 'bracket') return `<path d="M${x},${y + hh} L${x},${y} L${x + w},${y} L${x + w},${y + hh}" fill="none" ${common}/>`;
  const dir = it.dir || 'down';
  const [x1, y1, x2, y2] = dir === 'up' ? [x, y + hh, x + w, y] : dir === 'h' ? [x, y + hh / 2, x + w, y + hh / 2] : dir === 'v' ? [x + w / 2, y, x + w / 2, y + hh] : [x, y, x + w, y + hh];
  let out = `<path d="M${x1},${y1} L${x2},${y2}" fill="none" ${common}/>`;
  if (it.shape === 'arrow') {
    const head = (ax, ay, bx, by) => {   // arrowhead at (bx, by) pointing away from (ax, ay)
      const ang = Math.atan2(by - ay, bx - ax);
      const len = Math.max(8, sw * 4.5);
      const p = (a) => `${bx - len * Math.cos(ang + a)},${by - len * Math.sin(ang + a)}`;
      return `<path d="M${bx},${by} L${p(0.42)} L${p(-0.42)} Z" fill="${stroke}" stroke="none"/>`;
    };
    const heads = it.heads || 'end';
    if (heads !== 'start') out += head(x1, y1, x2, y2);
    if (heads !== 'end') out += head(x2, y2, x1, y1);
  }
  return out;
}

/** Compose the whole page as one vector SVG (graphs are nested SVGs, not images). */
export async function layoutSvg(L, outW, outH, opts = {}) {
  const parts = [];
  for (const it of [...L.items].sort((a, b) => (a.z || 1) - (b.z || 1))) {
    if (it.type === 'graph') {
      const g = getGraph(it.graphId);
      if (!g) continue;
      let svg = await graphSvgText(g, it.w, it.h, { transparent: !!opts.transparent });  // opaque like on screen, unless a transparent export is requested
      svg = svg.replace(/^<\?xml[^>]*>/, '').replace('<svg', `<svg x="${it.x}" y="${it.y}"`);
      parts.push(svg);
    } else if (it.type === 'image') {
      parts.push(`<image x="${it.x}" y="${it.y}" width="${it.w}" height="${it.h}" preserveAspectRatio="${it.fit === 'stretch' ? 'none' : 'xMidYMid meet'}"${it.opacity != null && it.opacity < 1 ? ` opacity="${it.opacity}"` : ''} href="${it.src}" xlink:href="${it.src}"/>`);
    } else if (it.type === 'shape') {
      parts.push(shapeSvg(it));
    } else if (it.type === 'table') {
      parts.push(tableSvg(it));
    } else {
      const anchor = { left: 'start', center: 'middle', right: 'end' }[it.align || 'left'];
      const tx = it.align === 'center' ? it.x + it.w / 2 : it.align === 'right' ? it.x + it.w : it.x + 4;
      parts.push(String(it.text).split('\n').map((line, k) => `<text x="${tx}" y="${it.y + (it.fontSize || 16) * (1.1 + k * 1.25)}" font-family="${esc(it.font || 'Arial')}" font-size="${it.fontSize || 16}" font-weight="${it.bold ? 700 : 400}" font-style="${it.italic ? 'italic' : 'normal'}" text-anchor="${anchor}" fill="#111">${esc(line)}</text>`).join(''));
    }
  }
  const bg = opts.transparent ? '' : '<rect width="100%" height="100%" fill="#fff"/>';
  return `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${outW}" height="${outH}" viewBox="0 0 ${L.page.w} ${L.page.h}">${bg}${parts.join('')}</svg>`;
}

export function layoutExportDialog(L) {
  exportDialog({ kind: 'layout', name: L.name, size: { w: L.page.w, h: L.page.h }, svg: (w, hh, o) => layoutSvg(L, w, hh, o) });
}

/** Quick export at page size and 300 dpi. */
export async function exportLayout(L, format) {
  toast('Rendering layout…');
  try {
    const opts = { format, dpi: 300, units: 'px', width: L.page.w, height: L.page.h, color: 'rgb', compress: true };
    const r = await renderSvgTo(await layoutSvg(L, L.page.w, L.page.h, opts), L.page.w, L.page.h, opts);
    download(`${L.name.replace(/[\\/:*?"<>|]+/g, '_')}.${r.ext}`, r.blob || new Blob([r.bytes], { type: r.mime }));
  } catch (e) { toast(`Export failed: ${e.message}`, 'err'); }
}

export function layoutPicker() {
  return new Promise((resolve) => {
    const ls = P().layouts;
    if (!ls.length) { resolve(null); return; }
    let v = ls[0].id;
    let done = false;
    modal({ title: 'Add graph to layout', body: field('Layout', select(ls.map((l) => [l.id, l.name]), v, (x) => { v = x; })),
      buttons: [{ label: 'Cancel' }, { label: 'Add', primary: true, onClick: () => { done = true; resolve(v); } }], onClose: () => { if (!done) resolve(null); } });
  });
}
