// Graph view: interactive Plotly graph on a resizable "paper" plus the
// format inspector (graph type, error bars, colors, axes, significance...).
import { ERROR_TYPES, GRAPH_KINDS, PALETTES, PLOT_CONFIG, PRESETS, SYMBOLS, figureFor, seriesStyle } from './graphs.js';
import { P, commit, defaultStyle, getTable } from './state.js';
import { exportGraphWith, exportDialog as openExportDialog } from './exporter.js';
import { helpIcon } from './help.js';
import { GRAPH_PLAIN } from './learn.js';
import { checkbox, debounce, download, field, h, modal, prompt, select, toast } from './ui.js';

let currentPlot = null;

export async function renderGraphView(body, inspector, g) {
  const t = getTable(g.tableId);
  const stage = h('div', { class: 'graph-stage' });
  const paper = h('div', { class: 'graph-paper', style: { width: `${g.style.width}px`, height: `${g.style.height}px` } });
  const plot = h('div');
  const handle = h('div', { class: 'resize-h', title: 'Drag to resize the graph' });
  paper.append(plot, handle);
  stage.append(paper);
  body.append(stage);
  currentPlot = plot;

  const draw = async () => {
    try {
      const fig = await figureFor(g);
      await Plotly.react(plot, fig.data, fig.layout, PLOT_CONFIG(true));
    } catch (e) {
      plot.innerHTML = '';
      plot.append(h('div', { class: 'errbox' }, `Could not draw graph: ${e.message}`));
    }
  };
  await draw();

  plot.on?.('plotly_relayout', (ev) => {
    let changed = false;
    const strip = (s) => String(s).replace(/<\/?b>/g, '');
    if (ev['title.text'] !== undefined) { g.style.title = strip(ev['title.text']); changed = true; }
    if (ev['xaxis.title.text'] !== undefined) { g.style.xTitle = ev['xaxis.title.text']; changed = true; }
    if (ev['yaxis.title.text'] !== undefined) { g.style.yTitle = ev['yaxis.title.text']; changed = true; }
    if (ev['legend.x'] !== undefined) { g.style.legendX = ev['legend.x']; g.style.legendY = ev['legend.y']; changed = true; }
    for (const [k, v] of Object.entries(ev)) {
      const m = /^annotations\[(\d+)\]\.(x|y|ax|ay|text)$/.exec(k);
      if (m && g.style.annotations?.[+m[1]]) { g.style.annotations[+m[1]][m[2]] = v; changed = true; }
    }
    if (changed) { commit('Edit graph'); renderInspector(inspector, g, draw); }
  });

  // drag-resize of the paper
  handle.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    handle.setPointerCapture(e.pointerId);
    const sx = e.clientX; const sy = e.clientY; const w0 = g.style.width; const h0 = g.style.height;
    const moveH = (ev) => {
      g.style.width = Math.max(220, Math.round(w0 + ev.clientX - sx));
      g.style.height = Math.max(180, Math.round(h0 + ev.clientY - sy));
      paper.style.width = `${g.style.width}px`; paper.style.height = `${g.style.height}px`;
      Plotly.relayout(plot, { width: g.style.width, height: g.style.height });
    };
    const up = () => { handle.removeEventListener('pointermove', moveH); handle.removeEventListener('pointerup', up); commit('Resize graph'); renderInspector(inspector, g, draw); };
    handle.addEventListener('pointermove', moveH);
    handle.addEventListener('pointerup', up);
  });

  inspector.hidden = false;
  renderInspector(inspector, g, async () => { paper.style.width = `${g.style.width}px`; paper.style.height = `${g.style.height}px`; await draw(); });
  return { redraw: draw, table: t };
}

function renderInspector(root, g, redraw) {
  const t = getTable(g.tableId);
  const st = g.style;
  root.innerHTML = '';
  const apply = debounce(async () => { commit('Format graph'); await redraw(); }, 120);
  const setS = (k, v) => { st[k] = v; apply(); };
  const text = (k, ph = '') => h('input', { type: 'text', value: st[k] ?? '', placeholder: ph, oninput: (e) => setS(k, e.target.value) });
  const num = (k, step = 1) => h('input', { type: 'number', step, value: st[k] ?? '', oninput: (e) => setS(k, e.target.value === '' ? '' : +e.target.value) });
  const HELPMAP = { 'Graph type': 'graph-type', 'Data & error bars': 'error-bars', 'Data sets': 'graph-series', Slices: 'graph-series',
    'Show analysis results on graph': 'linked-analyses', 'Significance annotations': 'significance', Titles: 'graph-appearance', Axes: 'graph-axes',
    Appearance: 'graph-appearance', Export: 'graph-export', 'Text labels': 'annotations', 'Analysis plot': 'analysis-plot', Variables: 'var-scatter',
    'Quick style': 'graph-presets', 'Reference lines': 'ref-lines', Legend: 'graph-legend' };
  const sec = (title, ...kids) => h('div', { class: 'insp-sec' }, h('h4', {}, title, HELPMAP[title] ? helpIcon(HELPMAP[title]) : null), ...kids);

  if (!t) { root.append(sec('Graph', h('p', {}, 'The data table for this graph was deleted.'))); return; }

  // graph type
  const kinds = GRAPH_KINDS[t.type] || [];
  root.append(sec('Graph type', h('div', { class: 'kind-grid' }, kinds.map(([k, label]) => h('button', {
    class: g.kind === k ? 'on' : '', title: `${label} — ${GRAPH_PLAIN[k] || ''}`,
    onclick: () => { g.kind = k; commit('Graph type'); redraw(); renderInspector(root, g, redraw); },
  }, kindIcon(k), label))), GRAPH_PLAIN[g.kind] ? h('div', { class: 'plain-graph' }, h('b', {}, 'This graph: '), GRAPH_PLAIN[g.kind]) : null,
  h('div', { class: 'plain-graph hint' }, '💡 To add P values, stars or a fitted curve, run ∑ Analyze on the data table — results appear on this graph automatically.')));

  // quick style presets and format tools
  root.append(sec('Quick style',
    h('div', { class: 'preset-grid' }, Object.entries(PRESETS).map(([k, pr]) => h('button', { class: 'btn small', title: pr.desc, onclick: () => {
      Object.assign(st, pr.style); commit('Style preset'); redraw(); renderInspector(root, g, redraw);
    } }, pr.label))),
    h('div', { style: { display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '8px' } },
      h('button', { class: 'btn small', title: 'Copy all formatting (not titles or data)', onclick: () => { formatClipboard = formatOf(st); toast('Format copied'); } }, 'Copy format'),
      h('button', { class: 'btn small', disabled: !formatClipboard, onclick: () => { Object.assign(st, structuredClone(formatClipboard)); commit('Paste format'); redraw(); renderInspector(root, g, redraw); } }, 'Paste format'),
      h('button', { class: 'btn small', title: 'Apply this graph’s formatting to every graph of the same table type', onclick: () => applyToAll(g) }, 'Apply to all graphs'),
      h('button', { class: 'btn small', title: 'Save this formatting as a named template to reuse on other graphs', onclick: async () => {
        const name = await prompt('Template name', `${g.name} style`, 'Saved in this browser; export templates to share them with colleagues.');
        if (!name) return;
        const list = loadTemplates().filter((x) => x.name !== name);
        list.unshift({ name: name.slice(0, 80), style: formatOf(st), kind: g.kind, created: new Date().toISOString() });
        saveTemplates(list); toast(`Template “${name}” saved`); renderInspector(root, g, redraw);
      } }, '★ Save as template'),
      h('button', { class: 'btn small', title: 'Apply, export, import or delete saved templates', onclick: () => templateManager(g, () => { redraw(); renderInspector(root, g, redraw); }) }, 'Templates…'),
      h('button', { class: 'btn small', title: 'Reset formatting to the defaults', onclick: () => {
        const keep = { title: st.title, xTitle: st.xTitle, yTitle: st.yTitle, annotations: st.annotations, xVar: st.xVar, yVar: st.yVar, colorVar: st.colorVar, plotIndex: st.plotIndex };
        g.style = { ...defaultStyle(t), ...keep }; commit('Reset format'); redraw(); renderInspector(root, g, redraw);
      } }, 'Reset'))));

  // analysis plot / variables pickers
  if (g.kind === 'analysis-plot') {
    const linked = (g.analysisIds || []).map((id) => P().analyses.find((a) => a.id === id)).find((a) => a?.result?.overlay?.kind === 'plot');
    const plotAns = P().analyses.filter((a) => a.tableId === t.id && a.result?.overlay?.kind === 'plot');
    const box = sec('Analysis plot');
    box.append(field('Analysis', select([['', '(choose)'], ...plotAns.map((a) => [a.id, a.name])], linked?.id || '', (v) => {
      g.analysisIds = (g.analysisIds || []).filter((id) => P().analyses.find((a) => a.id === id)?.result?.overlay?.kind !== 'plot');
      if (v) g.analysisIds.push(v);
      st.plotIndex = 0; commit('Link analysis'); redraw(); renderInspector(root, g, redraw);
    })));
    const plots = linked?.result?.overlay?.plots || [];
    if (plots.length > 1) box.append(field('Plot', select(plots.map((pl, n) => [n, pl.title]), st.plotIndex || 0, (v) => { st.plotIndex = +v; setS('plotIndex', +v); })));
    if (!plotAns.length) box.append(h('div', { class: 'hint' }, 'Run normality, Bland-Altman, correlation, multiple/logistic/Cox regression or PCA on this table first.'));
    root.append(box);
  }
  if (t.type === 'multi' && g.kind === 'var-scatter') {
    const vars = t.datasets.map((d, i) => [i, d.name]);
    root.append(sec('Variables', field('X variable', select(vars, st.xVar ?? 0, (v) => setS('xVar', +v))),
      field('Y variable', select(vars, st.yVar ?? 1, (v) => setS('yVar', +v))),
      field('Color by', select([['', '(none)'], ...vars], st.colorVar ?? '', (v) => setS('colorVar', v === '' ? '' : +v)))));
  }

  // data / error bars
  const dataSec = sec('Data & error bars');
  if (!['survival', 'parts', 'contingency', 'multi'].includes(t.type) && g.kind !== 'analysis-plot') {
    dataSec.append(field('Plot', select(ERROR_TYPES, st.error, (v) => setS('error', v))));
    dataSec.append(field('Error direction', select([['both', 'Both'], ['up', 'Above only'], ['down', 'Below only']], st.errorDir, (v) => setS('errorDir', v))));
  }
  if (t.type === 'survival') {
    dataSec.append(checkbox('Show 95% confidence bands', st.showCI, (v) => setS('showCI', v)));
    dataSec.append(checkbox('Show censored subjects (tick marks)', st.censorMarks, (v) => setS('censorMarks', v)));
    dataSec.append(checkbox('Y axis as fraction (0-1)', st.survivalAsFraction, (v) => setS('survivalAsFraction', v)));
    dataSec.append(checkbox('Show number-at-risk table below the graph', st.atRisk, (v) => setS('atRisk', v)));
  }
  if (['column', 'grouped'].includes(t.type)) dataSec.append(checkbox('Show individual points', st.showPoints, (v) => setS('showPoints', v)));
  if (t.type === 'xy') {
    dataSec.append(checkbox('Connect points with lines', st.connect, (v) => setS('connect', v)));
    dataSec.append(checkbox('Show confidence band of fitted curve', st.showBand, (v) => setS('showBand', v)));
    dataSec.append(h('div', { class: 'with-help' }, checkbox('Show fit equation / R² on graph', st.showEq, (v) => setS('showEq', v)), helpIcon('fit-equation')));
  }
  if (dataSec.children.length > 1) root.append(dataSec);

  // per data set styles
  const pal = PALETTES[st.palette] || PALETTES.prism;
  const seriesNames = t.type === 'parts' ? t.rowLabels.filter((r) => r !== '')
    : t.type === 'summary' ? t.cells.map((row, r) => [row, r]).filter(([row]) => String(row[0] ?? '').trim() !== '').map(([, r]) => t.rowLabels[r] || `Row ${r + 1}`)  // one plotted group per row
      : t.datasets.map((d) => d.name);
  const seriesBox = sec(t.type === 'parts' ? 'Slices' : 'Data sets');
  seriesBox.append(field('Color scheme', select(Object.keys(PALETTES).map((k) => [k, k[0].toUpperCase() + k.slice(1)]), st.palette, (v) => { st.series = Object.fromEntries(Object.entries(st.series || {}).map(([k, s]) => [k, { ...s, color: undefined }])); setS('palette', v); renderInspector(root, g, redraw); })));
  seriesNames.forEach((name, i) => {
    const s = seriesStyle(g, i);
    const upd = (k, v) => { st.series ||= {}; st.series[i] = { ...(st.series[i] || {}), [k]: v }; apply(); };
    seriesBox.append(h('div', { class: 'ds-style' },
      h('label', { style: { display: 'flex', gap: '5px', alignItems: 'center', overflow: 'hidden' } },
        h('input', { type: 'checkbox', checked: !s.hidden, title: 'Show on graph', onchange: (e) => upd('hidden', !e.target.checked) }), h('span', { title: name }, name)),
      h('input', { type: 'color', value: toHex(s.color || pal[i % pal.length]), oninput: (e) => upd('color', e.target.value) }),
      t.type === 'parts' ? h('span') : h('select', { onchange: (e) => upd('symbol', e.target.value) }, SYMBOLS.map((sym) => h('option', { value: sym, selected: sym === s.symbol }, sym)))));
    if (t.type !== 'parts' && !['analysis-plot', 'var-scatter'].includes(g.kind)) {
      const canRight = t.type === 'xy' || g.kind === 'grouped-line';
      seriesBox.append(h('div', { class: 'ds-style ds-style2' }, canRight
        ? h('label', { class: 'hint', style: { margin: 0, display: 'flex', gap: '4px', alignItems: 'center' }, title: 'Plot this data set against a second Y axis on the right' },
          h('input', { type: 'checkbox', checked: !!s.rightAxis, onchange: (e) => { upd('rightAxis', e.target.checked); renderInspector(root, g, redraw); } }), 'right Y axis')
        : h('span', { class: 'hint', style: { margin: 0 } }, 'line / bar fill'),
        h('select', { title: 'Line style', onchange: (e) => upd('dash', e.target.value) }, [['solid', '———'], ['dash', '– – –'], ['dot', '· · · ·'], ['dashdot', '–·–·']].map(([v, l]) => h('option', { value: v, selected: v === s.dash }, l))),
        h('select', { title: 'Bar pattern (hatching)', onchange: (e) => upd('pattern', e.target.value) }, [['', 'solid'], ['/', '////'], ['\\', '\\\\'], ['x', 'xxxx'], ['-', '≡'], ['|', '|||'], ['+', '+++'], ['.', '....']].map(([v, l]) => h('option', { value: v, selected: v === s.pattern }, l)))));
    }
  });
  const special = g.kind === 'analysis-plot' || (t.type === 'multi' && g.kind === 'var-scatter');
  if (special) {
    // only the colour scheme is relevant; series are the plot's own traces
    root.append(sec('Appearance of points', seriesBox.querySelector('.field')));
  } else root.append(seriesBox);

  // analyses overlay
  const ans = P().analyses.filter((a) => a.tableId === t.id && a.result?.overlay);
  if (ans.length && g.kind !== 'analysis-plot' && t.type !== 'multi') {
    root.append(sec('Show analysis results on graph', ...ans.map((a) => checkbox(a.name, (g.analysisIds || []).includes(a.id), (v) => {
      g.analysisIds = v ? [...new Set([...(g.analysisIds || []), a.id])] : (g.analysisIds || []).filter((x) => x !== a.id);
      commit('Link analysis'); redraw();
    }))));
  }
  if (['column', 'grouped'].includes(t.type) && g.kind !== 'analysis-plot') {
    root.append(sec('Significance annotations',
      checkbox('Show significance brackets', st.showSig, (v) => setS('showSig', v)),
      checkbox('Include non-significant (ns) comparisons', st.showNs, (v) => setS('showNs', v)),
      field('Label as', select([['stars', 'Asterisks (*, **, ***)'], ['p', 'P values'], ['both', 'Both']], st.sigFormat, (v) => setS('sigFormat', v)))));
  }

  const anyRight = Object.values(st.series || {}).some((x) => x?.rightAxis);
  root.append(t.type === 'parts' ? sec('Titles', field('Graph title', text('title')))
    : sec('Titles', field('Graph title', text('title')), field('X axis title', text('xTitle')), field('Y axis title', text('yTitle')),
      anyRight ? field('Right Y axis title', text('y2Title')) : null));

  const FORMATS = [['', 'Automatic'], [',.0f', '1,000'], ['.1f', '0.0'], ['.2f', '0.00'], ['.3f', '0.000'], ['.0%', 'Percent (×100)'], ['sci', 'Scientific 1.0e3'], ['pow10', 'Power of 10 (10³)']];
  const pair = (a, b) => h('div', { style: { display: 'flex', gap: '4px' } }, a, b);
  const axisBlock = (w, label) => h('details', { class: 'axis-block', open: w === 'y' },
    h('summary', {}, `${label} axis`),
    field('Min / max', pair(num(`${w}Min`, 'any'), num(`${w}Max`, 'any'))),
    field('Tick interval', num(`${w}Tick`, 'any')),
    field('Number format', select(FORMATS, st[`${w}Format`] || '', (v) => setS(`${w}Format`, v))),
    field('Tick label angle', select([['', 'Auto'], ['0', '0°'], ['-30', '-30°'], ['-45', '-45°'], ['-90', '-90°'], ['45', '45°'], ['90', '90°']], st[`${w}Angle`] ?? '', (v) => setS(`${w}Angle`, v))),
    checkbox('Logarithmic scale', st[`${w}Log`], (v) => setS(`${w}Log`, v)),
    checkbox('Reverse direction', st[`${w}Reverse`], (v) => setS(`${w}Reverse`, v)),
    checkbox('Gridlines', st[`${w}Grid`] === undefined || st[`${w}Grid`] === '' ? st.axisStyle === 'grid' : st[`${w}Grid`], (v) => setS(`${w}Grid`, v)),
    w === 'y' ? h('div', { class: 'break-box' },
      h('div', { class: 'with-help' }, checkbox('Axis break (gap)', st.yBreak, (v) => { setS('yBreak', v); renderInspector(root, g, redraw); }), helpIcon('axis-break')),
      st.yBreak ? field('Break from / to', pair(num('yBreakFrom', 'any'), num('yBreakTo', 'any'))) : null,
      st.yBreak ? field('Lower part height (0.15-0.85)', num('breakFrac', 0.05)) : null) : null);
  const axes = sec('Axes',
    field('Axis style', select([['prism', 'Classic (L-shaped)'], ['box', 'Frame (box)'], ['grid', 'With gridlines']], st.axisStyle, (v) => setS('axisStyle', v))),
    field('Tick marks', select([['outside', 'Outside'], ['inside', 'Inside'], ['none', 'None']], st.ticksDir || 'outside', (v) => setS('ticksDir', v))),
    field('Axis thickness / color', pair(num('axisWidth', 0.25), h('input', { type: 'color', value: toHex(st.axisColor || '#000000'), oninput: (e) => setS('axisColor', e.target.value) }))),
    field('Tick length', num('tickLen', 1)),
    checkbox('Minor ticks', st.minorTicks, (v) => setS('minorTicks', v)),
    checkbox('Show zero line', st.zeroLine, (v) => setS('zeroLine', v)),
    axisBlock('y', 'Y'));
  if (!['parts'].includes(t.type)) axes.append(axisBlock('x', 'X'));
  if (['column', 'grouped'].includes(t.type) && !['box', 'violin', 'grouped-box', 'heatmap', 'analysis-plot'].includes(g.kind)) {
    axes.append(field('Orientation', select([['v', 'Vertical'], ['h', 'Horizontal']], st.orientation || 'v', (v) => setS('orientation', v))));
  }
  if (t.type !== 'parts') root.append(axes);

  // free text labels
  const annBox = sec('Text labels');
  (st.annotations || []).forEach((a, n) => annBox.append(h('div', { class: 'ann-row' },
    h('input', { type: 'text', value: a.text, oninput: (e) => { a.text = e.target.value; apply(); } }),
    h('input', { type: 'number', value: a.size || st.fontSize, title: 'Font size', oninput: (e) => { a.size = +e.target.value; apply(); } }),
    h('label', { title: 'Draw an arrow from the label (drag the arrow head on the graph)', class: 'arrow-toggle' }, h('input', { type: 'checkbox', checked: !!a.arrow, onchange: (e) => { a.arrow = e.target.checked; apply(); } }), '↗'),
    h('button', { class: 'btn small danger', title: 'Delete label', onclick: () => { st.annotations.splice(n, 1); commit('Delete label'); redraw(); renderInspector(root, g, redraw); } }, '×'))));
  annBox.append(h('button', { class: 'btn small', onclick: () => {
    st.annotations ||= [];
    st.annotations.push({ text: 'Label', x: 0.62, y: 0.12 + 0.07 * st.annotations.length });
    commit('Add label'); redraw(); renderInspector(root, g, redraw);
  } }, '+ Add text label'), h('div', { class: 'hint' }, 'Drag labels on the graph to position them.'));
  root.append(annBox);

  // reference lines
  const refBox = sec('Reference lines');
  (st.refLines || []).forEach((rl, n) => refBox.append(h('div', { class: 'ref-row' },
    h('select', { title: 'Horizontal (Y =) or vertical (X =)', onchange: (e) => { rl.axis = e.target.value; apply(); } }, h('option', { value: 'y', selected: rl.axis !== 'x' }, 'Y ='), h('option', { value: 'x', selected: rl.axis === 'x' }, 'X =')),
    h('input', { type: 'number', step: 'any', value: rl.value ?? '', title: 'Value', oninput: (e) => { rl.value = e.target.value; apply(); } }),
    h('input', { type: 'text', value: rl.label || '', placeholder: 'label', oninput: (e) => { rl.label = e.target.value; apply(); } }),
    h('select', { title: 'Line style', onchange: (e) => { rl.dash = e.target.value; apply(); } }, [['dash', '– –'], ['dot', '···'], ['solid', '—']].map(([v, l]) => h('option', { value: v, selected: (rl.dash || 'dash') === v }, l))),
    h('input', { type: 'color', value: toHex(rl.color || '#777777'), oninput: (e) => { rl.color = e.target.value; apply(); } }),
    h('button', { class: 'btn small danger', title: 'Remove', onclick: () => { st.refLines.splice(n, 1); commit('Remove line'); redraw(); renderInspector(root, g, redraw); } }, '×'))));
  refBox.append(h('button', { class: 'btn small', onclick: () => { (st.refLines ||= []).push({ axis: 'y', value: '', label: '', dash: 'dash' }); commit('Add line'); renderInspector(root, g, redraw); } }, '+ Add reference line'));
  if (!['parts'].includes(t.type)) root.append(refBox);

  root.append(sec('Legend',
    checkbox('Show legend', st.showLegend, (v) => setS('showLegend', v)),
    field('Position', select([['right', 'Right'], ['top', 'Top (horizontal)'], ['bottom', 'Bottom (horizontal)'], ['inside-tl', 'Inside top-left'], ['inside-tr', 'Inside top-right'], ['inside-bl', 'Inside bottom-left'], ['inside-br', 'Inside bottom-right'], ['custom', 'Where I dragged it']],
      st.legendPos || (st.legendX !== '' && st.legendX !== undefined ? 'custom' : 'right'), (v) => setS('legendPos', v === 'custom' ? '' : v))),
    checkbox('Frame around legend', st.legendBox, (v) => setS('legendBox', v))));

  const isBar = ['bar', 'grouped-bar', 'stacked-bar', 'stacked-percent'].includes(g.kind);
  root.append(sec('Appearance',
    field('Font', select([['Arial', 'Arial'], ['Helvetica', 'Helvetica'], ['Times New Roman', 'Times New Roman'], ['Georgia', 'Georgia'], ['Courier New', 'Courier New'], ['Verdana', 'Verdana'], ['Calibri', 'Calibri'], ['Garamond', 'Garamond']], st.fontFamily, (v) => setS('fontFamily', v))),
    field('Font size / color', pair(num('fontSize'), h('input', { type: 'color', value: toHex(st.fontColor || '#000000'), oninput: (e) => setS('fontColor', e.target.value) }))),
    field('Title size / align', pair(num('titleSize'), select([['center', 'Center'], ['left', 'Left']], st.titleAlign || 'center', (v) => setS('titleAlign', v)))),
    checkbox('Bold title', st.titleBold !== false, (v) => setS('titleBold', v)),
    field('Axis title size', num('axisTitleSize')),
    field('Symbol size', num('markerSize')), field('Line thickness', num('lineWidth', 0.5)),
    t.type === 'column' && ['scatter', 'meanerror'].includes(g.kind) ? field('Center line', select([['mean', 'Mean / median line'], ['none', 'None (points only)']], st.centerLine || 'mean', (v) => setS('centerLine', v))) : null,
    field('Error bar color', select([['series', 'Same as data set'], ['black', 'Black']], st.errColor || (t.type === 'grouped' ? 'black' : 'series'), (v) => setS('errColor', v))),
    field('Error thickness / cap', pair(num('errWidth', 0.5), num('capWidth'))),
    isBar || g.kind === 'bar' ? field('Bar width', num('barWidth', 0.05)) : null,
    isBar ? field('Bar fill opacity (0-1)', num('barOpacity', 0.05)) : null,
    isBar ? field('Bar border width', num('barBorder', 0.5)) : null,
    isBar ? checkbox('Show values on bars', st.valueLabels, (v) => setS('valueLabels', v)) : null,
    ['scatter', 'bar', 'grouped-bar', 'grouped-scatter'].includes(g.kind) ? field('Scatter spread', num('jitter', 0.1)) : null,
    field('Background', h('input', { type: 'color', value: toHex(st.bgColor || '#ffffff'), oninput: (e) => setS('bgColor', e.target.value) })),
    checkbox('Transparent background (for slides/posters)', st.transparent, (v) => setS('transparent', v)),
    field('Width × height (px)', pair(num('width', 10), num('height', 10))),
    field('Size presets', select([['', 'Choose…'], ['260x220', 'Journal 1 column (≈ 3.5 in)'], ['520x400', 'Default'], ['700x450', 'Journal 2 columns (≈ 7 in)'], ['960x540', 'Slide 16:9'], ['600x600', 'Square']], '', (v) => {
      if (!v) return; const [w, hh] = v.split('x').map(Number); st.width = w; st.height = hh; apply(); renderInspector(root, g, redraw);
    }))));

  root.append(sec('Export',
    h('div', { style: { display: 'flex', gap: '6px', flexWrap: 'wrap' } },
      h('button', { class: 'btn small primary', onclick: () => exportDialog(g) }, 'Export… (format, size, dpi)'),
      h('button', { class: 'btn small', onclick: () => exportGraph(g, 'tiff') }, 'TIFF 300 dpi'),
      h('button', { class: 'btn small', onclick: () => exportGraph(g, 'png') }, 'PNG 300 dpi'),
      h('button', { class: 'btn small', onclick: () => exportGraph(g, 'pdf') }, 'PDF'),
      h('button', { class: 'btn small', onclick: () => exportGraph(g, 'svg') }, 'SVG'),
      h('button', { class: 'btn small', title: 'Enhanced Metafile: vector for Word / PowerPoint', onclick: () => exportGraph(g, 'emf') }, 'EMF'),
      h('button', { class: 'btn small', title: 'Encapsulated PostScript: vector for Illustrator, LaTeX, print', onclick: () => exportGraph(g, 'eps') }, 'EPS'),
      h('button', { class: 'btn small', onclick: () => copyGraph(g) }, 'Copy image'))));
}

// ---------------------------------------------------------------- format copy/paste
let formatClipboard = null;
const NON_FORMAT = ['title', 'xTitle', 'yTitle', 'annotations', 'xVar', 'yVar', 'colorVar', 'plotIndex', 'xMin', 'xMax', 'yMin', 'yMax', 'refLines', 'legendX', 'legendY'];
// ---------------------------------------------------------------- style templates
const TPL_KEY = 'openprism.graphTemplates';
function loadTemplates() { try { const v = JSON.parse(localStorage.getItem(TPL_KEY) || '[]'); return Array.isArray(v) ? v : []; } catch (_) { return []; } }
function saveTemplates(list) { try { localStorage.setItem(TPL_KEY, JSON.stringify(list.slice(0, 200))); } catch (_) { toast('Could not save templates in this browser', 'err'); } }

function templateManager(g, done) {
  const box = h('div');
  const draw = () => {
    const list = loadTemplates();
    box.innerHTML = '';
    if (!list.length) box.append(h('p', { class: 'hint' }, 'No templates yet. Format a graph, then click ★ Save as template. Templates keep fonts, colours, symbols, axes and sizes — not titles or data.'));
    for (const tp of list) {
      box.append(h('div', { class: 'tpl-row' },
        h('div', {}, h('b', {}, tp.name), h('div', { class: 'hint' }, `${tp.kind || ''} · ${String(tp.created || '').slice(0, 10)}`)),
        h('button', { class: 'btn small primary', onclick: () => { Object.assign(g.style, structuredClone(tp.style)); commit('Apply template'); done(); toast(`Applied “${tp.name}”`); } }, 'Apply to this graph'),
        h('button', { class: 'btn small', title: 'Apply to every graph of the same table type', onclick: () => {
          const t = getTable(g.tableId); let n = 0;
          for (const og of P().graphs) { const ot = getTable(og.tableId); if (ot && t && ot.type === t.type) { Object.assign(og.style, structuredClone(tp.style)); n++; } }
          commit('Apply template to all'); done(); toast(`Applied to ${n} graphs`);
        } }, 'Apply to all'),
        h('button', { class: 'btn small danger', onclick: () => { saveTemplates(loadTemplates().filter((x) => x.name !== tp.name)); draw(); } }, 'Delete')));
    }
  };
  draw();
  const fileIn = h('input', { type: 'file', accept: '.json', hidden: true, onchange: async (e) => {
    const f = e.target.files[0]; if (!f) return;
    try {
      const inc = JSON.parse(await f.text());
      const arr = (Array.isArray(inc) ? inc : inc.templates || []).filter((x) => x && typeof x.name === 'string' && x.style && typeof x.style === 'object');
      const names = new Set(arr.map((x) => x.name));
      saveTemplates([...arr.map((x) => ({ name: x.name.slice(0, 80), style: x.style, kind: x.kind, created: x.created })), ...loadTemplates().filter((x) => !names.has(x.name))]);
      toast(`Imported ${arr.length} template(s)`); draw();
    } catch (_) { toast('Not a template file', 'err'); }
  } });
  modal({ title: 'Graph style templates', wide: true, body: h('div', {}, box, fileIn), buttons: [
    { label: 'Import…', onClick: () => { fileIn.click(); return false; } },
    { label: 'Export all…', onClick: () => { download('openprism-graph-templates.json', JSON.stringify({ format: 'openprism-graph-templates', templates: loadTemplates() }, null, 1), 'application/json'); return false; } },
    { label: 'Close', primary: true }] });
}

function formatOf(st) {
  const f = structuredClone(st);
  for (const k of NON_FORMAT) delete f[k];
  return f;
}
function applyToAll(g) {
  const t = getTable(g.tableId);
  const f = formatOf(g.style);
  let n = 0;
  for (const other of P().graphs) {
    if (other === g || getTable(other.tableId)?.type !== t?.type) continue;
    Object.assign(other.style, structuredClone(f));
    n++;
  }
  commit('Apply format to all');
  toast(n ? `Formatting applied to ${n} other graph${n > 1 ? 's' : ''}` : 'No other graphs of this table type');
}

function toHex(c) {
  if (/^#[0-9a-f]{6}$/i.test(c)) return c;
  const m = /rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(c || '');
  if (m) return `#${[m[1], m[2], m[3]].map((x) => (+x).toString(16).padStart(2, '0')).join('')}`;
  return '#000000';
}

/** Quick export with the graph's own size; `scale` × 96 = dpi. */
export async function exportGraph(g, format = 'png', scale = 300 / 96) {
  try {
    const r = await exportGraphWith(g, { format, dpi: Math.round(scale * 96), units: 'px', width: g.style.width, height: g.style.height, color: 'rgb', transparent: false, compress: true });
    download(`${g.name.replace(/[\\/:*?"<>|]+/g, '_')}.${r.ext}`, r.blob || new Blob([r.bytes], { type: r.mime }));
  } catch (e) { toast(`Export failed: ${e.message}`, 'err'); }
}

function exportDialog(g) { openExportDialog({ kind: 'graph', g }); }

async function copyGraph(g) {
  try {
    const fig = await figureFor(g);
    const url = await Plotly.toImage({ data: fig.data, layout: fig.layout }, { format: 'png', width: g.style.width, height: g.style.height, scale: 3 });
    const blob = await (await fetch(url)).blob();
    await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
    toast('Graph copied to clipboard');
  } catch (e) { toast(`Copy failed: ${e.message}`, 'err'); }
}

export function downloadFigureJSON(g) { figureFor(g).then((f) => download(`${g.name}.plotly.json`, JSON.stringify(f), 'application/json')); }

function kindIcon(k) {
  const svg = (inner) => h('span', { html: `<svg viewBox="0 0 38 28" fill="none" stroke="currentColor" stroke-width="1.6">${inner}</svg>` });
  const icons = {
    scatter: '<path d="M3 26h33M3 26V2"/><circle cx="10" cy="15" r="1.6"/><circle cx="12" cy="18" r="1.6"/><circle cx="9" cy="19" r="1.6"/><circle cx="25" cy="8" r="1.6"/><circle cx="27" cy="11" r="1.6"/><circle cx="24" cy="12" r="1.6"/><path d="M7 17h7M22 10h7"/>',
    bar: '<path d="M3 26h33M3 26V2"/><rect x="7" y="13" width="8" height="13"/><rect x="22" y="6" width="8" height="20"/><path d="M11 13V9M26 6V3"/>',
    meanerror: '<path d="M3 26h33M3 26V2M8 15h6M11 10v10M23 8h6M26 4v9"/>',
    box: '<path d="M3 26h33M3 26V2"/><rect x="7" y="10" width="8" height="10"/><path d="M7 15h8M11 10V5M11 20v4"/><rect x="22" y="6" width="8" height="9"/><path d="M22 11h8M26 6V3M26 15v5"/>',
    violin: '<path d="M3 26h33M3 26V2M11 4c-5 6 5 8 0 20 -5-12 5-14 0-20zM26 3c-6 7 6 9 0 18 -6-9 6-11 0-18z"/>',
    beforeafter: '<path d="M3 26h33M3 26V2M10 8l17 6M10 13l17 3M10 18l17-2"/><circle cx="10" cy="8" r="1.5"/><circle cx="27" cy="14" r="1.5"/>',
    roc: '<path d="M3 26h33M3 26V2M3 26c3-15 10-20 33-24" /><path d="M3 26L36 2" stroke-dasharray="2 2"/>',
    'xy-points': '<path d="M3 26h33M3 26V2"/><circle cx="8" cy="22" r="1.6"/><circle cx="15" cy="17" r="1.6"/><circle cx="22" cy="10" r="1.6"/><circle cx="30" cy="6" r="1.6"/><path d="M22 7v6M15 14v6"/>',
    'xy-line': '<path d="M3 26h33M3 26V2M8 22l7-5 7-7 8-4"/><circle cx="8" cy="22" r="1.6"/><circle cx="15" cy="17" r="1.6"/><circle cx="22" cy="10" r="1.6"/><circle cx="30" cy="6" r="1.6"/>',
    'xy-all': '<path d="M3 26h33M3 26V2"/><circle cx="8" cy="21" r="1.2"/><circle cx="8" cy="23" r="1.2"/><circle cx="15" cy="16" r="1.2"/><circle cx="15" cy="19" r="1.2"/><circle cx="22" cy="9" r="1.2"/><circle cx="22" cy="12" r="1.2"/><circle cx="30" cy="5" r="1.2"/><circle cx="30" cy="7" r="1.2"/>',
    'xy-lineonly': '<path d="M3 26h33M3 26V2M6 23c8-1 10-15 28-18"/>',
    'xy-area': '<path d="M3 26h33M3 26V2"/><path d="M4 26L10 20 18 14 26 10 34 6V26z" fill="currentColor" opacity=".25"/>',
    'grouped-bar': '<path d="M3 26h33M3 26V2"/><rect x="6" y="14" width="5" height="12"/><rect x="11" y="9" width="5" height="17" fill="currentColor" opacity=".3"/><rect x="21" y="11" width="5" height="15"/><rect x="26" y="5" width="5" height="21" fill="currentColor" opacity=".3"/>',
    'stacked-bar': '<path d="M3 26h33M3 26V2"/><rect x="8" y="16" width="7" height="10"/><rect x="8" y="9" width="7" height="7" fill="currentColor" opacity=".3"/><rect x="23" y="13" width="7" height="13"/><rect x="23" y="4" width="7" height="9" fill="currentColor" opacity=".3"/>',
    'stacked-percent': '<path d="M3 26h33M3 26V2"/><rect x="8" y="12" width="7" height="14"/><rect x="8" y="3" width="7" height="9" fill="currentColor" opacity=".3"/><rect x="23" y="17" width="7" height="9"/><rect x="23" y="3" width="7" height="14" fill="currentColor" opacity=".3"/>',
    'grouped-scatter': '<path d="M3 26h33M3 26V2"/><circle cx="8" cy="18" r="1.3"/><circle cx="9" cy="20" r="1.3"/><circle cx="14" cy="12" r="1.3"/><circle cx="15" cy="14" r="1.3"/><circle cx="23" cy="15" r="1.3"/><circle cx="24" cy="17" r="1.3"/><circle cx="29" cy="7" r="1.3"/><circle cx="30" cy="9" r="1.3"/>',
    'grouped-line': '<path d="M3 26h33M3 26V2M7 20l10-6 10-3 8-4M7 22l10-3 10-1 8-2"/>',
    'grouped-box': '<path d="M3 26h33M3 26V2"/><rect x="6" y="12" width="5" height="8"/><rect x="12" y="8" width="5" height="8"/><rect x="21" y="10" width="5" height="9"/><rect x="27" y="5" width="5" height="8"/>',
    heatmap: '<rect x="4" y="3" width="10" height="7" fill="currentColor" opacity=".8"/><rect x="14" y="3" width="10" height="7" fill="currentColor" opacity=".3"/><rect x="24" y="3" width="10" height="7" fill="currentColor" opacity=".5"/><rect x="4" y="10" width="10" height="7" fill="currentColor" opacity=".2"/><rect x="14" y="10" width="10" height="7" fill="currentColor" opacity=".9"/><rect x="24" y="10" width="10" height="7" fill="currentColor" opacity=".4"/><rect x="4" y="17" width="10" height="7" fill="currentColor" opacity=".6"/><rect x="14" y="17" width="10" height="7" fill="currentColor" opacity=".1"/><rect x="24" y="17" width="10" height="7" fill="currentColor" opacity=".7"/>',
    km: '<path d="M3 26h33M3 26V2M4 4h7v5h6v6h7v4h11"/><path d="M14 2v3M21 7v3" />',
    pie: '<circle cx="19" cy="14" r="11"/><path d="M19 14V3M19 14l9 6"/>',
    donut: '<circle cx="19" cy="14" r="11"/><circle cx="19" cy="14" r="5"/><path d="M19 9V3M23 17l5 3"/>',
    'parts-bar': '<path d="M4 3v23"/><rect x="4" y="4" width="28" height="4"/><rect x="4" y="11" width="18" height="4"/><rect x="4" y="18" width="10" height="4"/>',
    'var-scatter': '<path d="M3 26h33M3 26V2"/><circle cx="9" cy="20" r="1.5"/><circle cx="14" cy="17" r="1.5" fill="currentColor"/><circle cx="18" cy="14" r="1.5"/><circle cx="23" cy="12" r="1.5" fill="currentColor"/><circle cx="27" cy="8" r="1.5"/><circle cx="31" cy="6" r="1.5" fill="currentColor"/>',
    'var-box': '<path d="M3 26h33M3 26V2"/><rect x="6" y="9" width="6" height="9"/><rect x="16" y="13" width="6" height="8"/><rect x="26" y="5" width="6" height="9"/><path d="M9 9V5M9 18v4M19 13v-3M19 21v3M29 5V3M29 14v4"/>',
    'analysis-plot': '<path d="M3 26h33M3 26V2"/><path d="M5 24L34 4" stroke-dasharray="2 2"/><circle cx="9" cy="21" r="1.4"/><circle cx="14" cy="16" r="1.4"/><circle cx="20" cy="14" r="1.4"/><circle cx="25" cy="9" r="1.4"/><circle cx="31" cy="7" r="1.4"/>',
    'parts-stacked': '<rect x="13" y="2" width="12" height="8"/><rect x="13" y="10" width="12" height="6" fill="currentColor" opacity=".3"/><rect x="13" y="16" width="12" height="10" fill="currentColor" opacity=".6"/>',
  };
  return svg(icons[k] || icons.scatter);
}
export { kindIcon };
