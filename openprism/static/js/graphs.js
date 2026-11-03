// Graph construction: turns a data table + summary data + analysis overlays
// into a Plotly figure styled like a publication-quality scientific graph.
import { getAnalysis, getTable, tableForServer } from './state.js';
import { api } from './ui.js';
import { localJob } from './activity.js';
import { graphDataLocal } from './statslite.js';

export const PALETTES = {
  prism: ['#000000', '#d62728', '#1f4fd6', '#2ca02c', '#9467bd', '#ff7f0e', '#8c564b', '#e377c2', '#17becf', '#7f7f7f'],
  colorblind: ['#000000', '#E69F00', '#56B4E9', '#009E73', '#F0E442', '#0072B2', '#D55E00', '#CC79A7'],
  colors: ['#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f', '#edc948', '#b07aa1', '#ff9da7', '#9c755f', '#bab0ac'],
  pastel: ['#8dd3c7', '#fdb462', '#bebada', '#fb8072', '#80b1d3', '#b3de69', '#fccde5', '#d9d9d9'],
  grayscale: ['#000000', '#555555', '#888888', '#aaaaaa', '#cccccc', '#333333'],
  viridis: ['#440154', '#3b528b', '#21918c', '#5ec962', '#fde725', '#31688e', '#35b779'],
  warm: ['#7f0000', '#b30000', '#d7301f', '#ef6548', '#fc8d59', '#fdbb84'],
  cool: ['#023858', '#045a8d', '#0570b0', '#3690c0', '#74a9cf', '#a6bddb'],
};
export const SYMBOLS = ['circle', 'square', 'triangle-up', 'diamond', 'triangle-down', 'circle-open', 'square-open', 'triangle-up-open', 'diamond-open', 'cross', 'x', 'star'];

export const GRAPH_KINDS = {
  column: [['scatter', 'Scatter dot plot'], ['bar', 'Bar (mean ± error)'], ['meanerror', 'Mean ± error only'], ['box', 'Box & whiskers'], ['violin', 'Violin'], ['beforeafter', 'Before-after'], ['roc', 'ROC curve (needs ROC analysis)']],
  xy: [['xy-points', 'Points (mean ± error)'], ['xy-line', 'Points connected'], ['xy-all', 'All replicates'], ['xy-lineonly', 'Line only'], ['xy-area', 'Area fill']],
  grouped: [['grouped-bar', 'Grouped bars'], ['stacked-bar', 'Stacked bars'], ['grouped-scatter', 'Grouped scatter'], ['grouped-line', 'Lines across rows'], ['grouped-box', 'Grouped box plots'], ['heatmap', 'Heat map']],
  contingency: [['grouped-bar', 'Grouped bars'], ['stacked-bar', 'Stacked bars'], ['stacked-percent', 'Stacked percent'], ['heatmap', 'Heat map']],
  survival: [['km', 'Kaplan-Meier (staircase)']],
  parts: [['pie', 'Pie'], ['donut', 'Donut'], ['parts-bar', 'Horizontal bars'], ['parts-stacked', 'Single stacked bar']],
  multi: [['var-scatter', 'XY scatter of two variables'], ['var-box', 'Box plots of variables']],
  summary: [['bar', 'Bar (mean ± error)'], ['meanerror', 'Mean ± error only']],
  nested: [['nested-scatter', 'Nested scatter (by subject)'], ['scatter', 'Scatter dot plot (all values)'], ['bar', 'Bar (mean ± error)'], ['box', 'Box & whiskers']],
};
// every table type can also show a plot produced by an analysis (Q-Q, PCA, Bland-Altman, regression diagnostics…)
for (const k of Object.keys(GRAPH_KINDS)) GRAPH_KINDS[k].push(['analysis-plot', 'Analysis plot (from results)']);

/** One-click style presets (formatting only — data and titles are kept). */
export const PRESETS = {
  classic: { label: 'Classic', desc: 'Black L-shaped axes, outward ticks, bold title', style: { width: 520, height: 400, fontFamily: 'Arial', fontSize: 14, axisStyle: 'prism', axisWidth: 1.5, tickLen: 6, ticksDir: 'outside', lineWidth: 2, markerSize: 8, capWidth: 6, palette: 'prism', xGrid: '', yGrid: '', transparent: false, bgColor: '#ffffff', fontColor: '#000000', axisColor: '#000000', titleSize: '', axisTitleSize: '', minorTicks: false } },
  journal: { label: 'Journal', desc: 'Small, compact, color-blind safe (1-column figure)', style: { fontFamily: 'Arial', fontSize: 9, titleSize: 10, axisTitleSize: 9, width: 300, height: 240, axisStyle: 'prism', axisWidth: 0.8, tickLen: 3, ticksDir: 'outside', lineWidth: 1, markerSize: 5, capWidth: 3, errWidth: 0.8, palette: 'colorblind', transparent: false, fontColor: '#000000', axisColor: '#000000' } },
  slides: { label: 'Slides', desc: 'Large fonts and thick lines for presentations', style: { fontFamily: 'Arial', fontSize: 22, titleSize: 28, axisTitleSize: 24, width: 900, height: 560, axisWidth: 2.5, tickLen: 9, lineWidth: 3.5, markerSize: 13, capWidth: 10, errWidth: 2.5, palette: 'colors' } },
  minimal: { label: 'Minimal', desc: 'Light gridlines, grey axes, no tick marks', style: { axisStyle: 'prism', ticksDir: 'none', axisColor: '#777777', axisWidth: 1, xGrid: false, yGrid: true, gridColor: '#e8e8e8', fontColor: '#333333', palette: 'colors', minorTicks: false } },
  boxed: { label: 'Boxed', desc: 'Frame, inside ticks and minor ticks (physics style)', style: { axisStyle: 'box', ticksDir: 'inside', minorTicks: true, axisWidth: 1.2, xGrid: false, yGrid: false, palette: 'prism' } },
  gray: { label: 'Grayscale', desc: 'Black & white for print, hatched bars', style: { palette: 'grayscale', axisColor: '#000000', fontColor: '#000000' } },
};

export const ERROR_TYPES = [['sem', 'Mean ± SEM'], ['sd', 'Mean ± SD'], ['ci95', 'Mean with 95% CI'], ['range', 'Mean with range'],
  ['median_iqr', 'Median with interquartile range'], ['median_range', 'Median with range'], ['median_ci', 'Median with 95% CI'],
  ['geomean_gsd', 'Geometric mean ± geometric SD'], ['none', 'Mean, no error bars']];

const cache = new Map();
async function graphData(t, error) {
  const key = `${t.id}|${t.rev}|${error}`;
  // summary values are computed in the browser (instant; identical to the server's /api/graphdata)
  if (!cache.has(key)) cache.set(key, Promise.resolve(localJob(`Graph summary: ${t.name}`, () => graphDataLocal(tableForServer(t), error))));
  if (cache.size > 200) cache.delete(cache.keys().next().value);
  return cache.get(key);
}
async function kmData(t) {
  const key = `km|${t.id}|${t.rev}`;
  if (!cache.has(key)) cache.set(key, api('/api/analyze', { analysis: 'survival', table: tableForServer(t), params: {} }));
  return cache.get(key);
}

const hexA = (hex, a) => {
  const m = /^#?([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(hex || '');
  if (!m) return hex;
  return `rgba(${parseInt(m[1], 16)},${parseInt(m[2], 16)},${parseInt(m[3], 16)},${a})`;
};

export function seriesStyle(g, i) {
  const pal = PALETTES[g.style.palette] || PALETTES.prism;
  const s = (g.style.series || {})[i] || {};
  return {
    color: s.color || pal[i % pal.length],
    symbol: s.symbol || SYMBOLS[i % SYMBOLS.length],
    fill: s.fill ?? 0.25,
    dash: s.dash || 'solid',
    hidden: !!s.hidden,
    pattern: s.pattern || '',
    rightAxis: !!s.rightAxis,
  };
}

/** Build the Plotly figure for a graph. Returns {data, layout}. */
export async function buildFigure(g, opts = {}) {
  const t = getTable(g.tableId);
  if (!t) return { data: [], layout: { title: { text: 'Data table was deleted' } } };
  const st = g.style;
  const gd = await graphData(t, st.error);
  const overlays = (g.analysisIds || []).map((id) => getAnalysis(id)).filter((a) => a && a.result && a.result.overlay)
    .map((a) => a.result.overlay);
  const ctx = { g, t, st, gd, overlays, data: [], extraLayout: {}, top: [], cats: null };
  const visible = gd.datasets.map((d, i) => i).filter((i) => !seriesStyle(g, i).hidden && (gd.datasets[i].values.length || gd.datasets[i].summaryOnly));
  ctx.visible = visible;

  const k = g.kind;
  if (k === 'analysis-plot') analysisPlot(ctx);
  else if (t.type === 'multi') multiGraph(ctx, k);
  else if (t.type === 'nested' && k === 'nested-scatter') nestedGraph(ctx);
  else if (t.type === 'nested') columnGraph(ctx, k);
  else if (t.type === 'column' || t.type === 'summary') columnGraph(ctx, k === 'scatter' && t.type === 'summary' ? 'meanerror' : k);
  else if (t.type === 'xy') xyGraph(ctx, k);
  else if (t.type === 'grouped' || t.type === 'contingency') groupedGraph(ctx, k);
  else if (t.type === 'survival') await survivalGraph(ctx);
  else if (t.type === 'parts') partsGraph(ctx, k);

  const font = { family: `${st.fontFamily}, Helvetica, sans-serif`, size: +st.fontSize || 14, color: st.fontColor || '#000' };
  const axColor = st.axisColor || '#000';
  const axW = st.axisWidth === '' || st.axisWidth === undefined ? 1.5 : +st.axisWidth;
  const ticksDir = st.ticksDir || 'outside';
  const axis = (title, log, min, max, isX) => {
    const w = isX ? 'x' : 'y';
    const grid = st[`${w}Grid`] === undefined || st[`${w}Grid`] === '' ? st.axisStyle === 'grid' : !!st[`${w}Grid`];
    const a = {
      title: { text: title, font: { ...font, size: +st.axisTitleSize || font.size + 1 } }, type: log ? 'log' : 'linear',
      zeroline: !!st.zeroLine, zerolinecolor: '#888', zerolinewidth: 1,
      showline: axW > 0, linecolor: axColor, linewidth: axW, ticks: ticksDir === 'none' ? '' : ticksDir, tickcolor: axColor,
      tickwidth: Math.max(0.5, axW), ticklen: +st.tickLen || 6,
      showgrid: grid, gridcolor: st.gridColor || '#e5e5e5', mirror: st.axisStyle === 'box' || st.frame ? 'ticks' : false,
      tickfont: font, automargin: true,
    };
    const fmtKey = st[`${w}Format`];
    if (fmtKey === 'pow10') { a.exponentformat = 'power'; a.showexponent = 'all'; }
    else if (fmtKey === 'sci') { a.exponentformat = 'e'; a.tickformat = '.1e'; }
    else if (fmtKey) a.tickformat = fmtKey;
    if (+st[`${w}Tick`] > 0 && !log) { a.dtick = +st[`${w}Tick`]; a.tick0 = 0; }
    if (st[`${w}Angle`] !== undefined && st[`${w}Angle`] !== '') a.tickangle = +st[`${w}Angle`];
    if (st.minorTicks && ticksDir !== 'none') a.minor = { ticks: ticksDir, ticklen: Math.max(2, (+st.tickLen || 6) / 2), tickcolor: axColor };
    if (min !== '' && max !== '' && min !== undefined && max !== undefined && !Number.isNaN(+min) && !Number.isNaN(+max)) {
      a.range = log ? [Math.log10(+min), Math.log10(+max)] : [+min, +max];
      a.autorange = false;
    } else if (!log && !(isX && ['xy', 'survival'].includes(t.type) && hasNegX(gd))) a.rangemode = 'tozero';
    if (st[`${w}Reverse`]) {
      if (a.range) a.range = [a.range[1], a.range[0]];
      else a.autorange = 'reversed';
    }
    return a;
  };
  const LEGEND = {
    right: { x: 1.02, y: 1, xanchor: 'left', yanchor: 'top', orientation: 'v' },
    top: { x: 0.5, y: 1.02, xanchor: 'center', yanchor: 'bottom', orientation: 'h' },
    bottom: { x: 0.5, y: -0.18, xanchor: 'center', yanchor: 'top', orientation: 'h' },
    'inside-tl': { x: 0.02, y: 0.98, xanchor: 'left', yanchor: 'top', orientation: 'v' },
    'inside-tr': { x: 0.98, y: 0.98, xanchor: 'right', yanchor: 'top', orientation: 'v' },
    'inside-bl': { x: 0.02, y: 0.02, xanchor: 'left', yanchor: 'bottom', orientation: 'v' },
    'inside-br': { x: 0.98, y: 0.02, xanchor: 'right', yanchor: 'bottom', orientation: 'v' },
  };
  const legendPos = st.legendPos && LEGEND[st.legendPos] ? LEGEND[st.legendPos]
    : { ...LEGEND.right, ...(st.legendX !== '' && st.legendX !== undefined ? { x: +st.legendX, y: +st.legendY } : {}) };
  const bg = st.transparent ? 'rgba(0,0,0,0)' : (st.bgColor || '#fff');
  const layout = {
    title: { text: autoTitle(st.title, ctx.autoTitles?.title) ? (st.titleBold === false ? autoTitle(st.title, ctx.autoTitles?.title) : `<b>${autoTitle(st.title, ctx.autoTitles?.title)}</b>`) : '',
      font: { ...font, size: +st.titleSize || font.size + 3 }, x: st.titleAlign === 'left' ? 0.02 : 0.5, xanchor: st.titleAlign === 'left' ? 'left' : 'center' },
    font, paper_bgcolor: bg, plot_bgcolor: bg,
    margin: { l: 70, r: 30, t: st.title ? 60 : 30, b: 60 },
    xaxis: axis(autoTitle(st.xTitle, ctx.autoTitles?.x), st.xLog, st.xMin, st.xMax, true), yaxis: axis(autoTitle(st.yTitle, ctx.autoTitles?.y), st.yLog, st.yMin, st.yMax),
    showlegend: !!st.showLegend && ctx.legend !== false,
    legend: { font: { ...font, size: Math.max(9, font.size - 1) }, bgcolor: 'rgba(255,255,255,0)', itemwidth: 30, ...legendPos,
      ...(st.legendBox ? { bordercolor: axColor, borderwidth: 1, bgcolor: st.transparent ? 'rgba(255,255,255,0)' : '#fff' } : {}) },
    hovermode: 'closest', barmode: ctx.barmode || 'overlay', bargap: 0.2,
    width: opts.width || st.width, height: opts.height || st.height,
    shapes: [], annotations: [],
  };
  if (st.xLog) layout.xaxis.rangemode = undefined;
  if (ctx.cats) {
    Object.assign(layout.xaxis, { tickvals: ctx.cats.vals, ticktext: ctx.cats.text, range: ctx.cats.range, autorange: false, rangemode: undefined });
    if (ctx.cats.angle) layout.xaxis.tickangle = ctx.cats.angle;
  }
  if (st.orientation === 'h' && ctx.cats) {
    // horizontal: swap axes for categorical graphs
    for (const tr of ctx.data) {
      [tr.x, tr.y] = [tr.y, tr.x];
      if (tr.error_y) { tr.error_x = tr.error_y; delete tr.error_y; }
      if (tr.type === 'bar') tr.orientation = 'h';
      if (tr.type === 'box' || tr.type === 'violin') tr.orientation = 'h';
    }
    const xa = layout.xaxis; layout.xaxis = layout.yaxis; layout.yaxis = xa;
    layout.yaxis.autorange = 'reversed'; delete layout.yaxis.range;
  }
  for (const [key, v] of Object.entries(ctx.extraLayout)) {
    if (v === undefined) continue;
    if (v && typeof v === 'object' && layout[key] && typeof layout[key] === 'object') layout[key] = { ...layout[key], ...v };
    else layout[key] = v;
  }
  const extraAnns = layout.annotationsExtra || [];
  delete layout.annotationsExtra;
  // user text labels first (their index matches style.annotations for drag-editing), then fit equations
  layout.annotations = (st.annotations || []).map((a) => ({
    text: a.text, x: a.x, y: a.y, xref: 'paper', yref: 'paper', xanchor: a.arrow ? 'center' : 'left',
    showarrow: !!a.arrow, ax: a.ax ?? -40, ay: a.ay ?? -40, arrowhead: 2, arrowsize: 1.2, arrowwidth: 1.5, arrowcolor: a.color || '#000',
    font: { ...font, size: a.size || font.size, color: a.color || '#000' }, bgcolor: 'rgba(255,255,255,0)',
  }));
  layout.annotations.push(...extraAnns);
  // reference lines (e.g. Y = 100%, threshold, time of treatment)
  layout.shapes = [...(layout.shapes || [])];
  for (const rl of st.refLines || []) {
    if (rl.value === '' || rl.value === undefined || Number.isNaN(+rl.value)) continue;
    const horiz = (rl.axis || 'y') === 'y';
    const v = +rl.value;
    const line = { color: rl.color || '#777', width: +rl.width || 1.2, dash: rl.dash || 'dash' };
    layout.shapes.push(horiz ? { type: 'line', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: v, y1: v, line, layer: 'below' }
      : { type: 'line', yref: 'paper', y0: 0, y1: 1, xref: 'x', x0: v, x1: v, line, layer: 'below' });
    if (rl.label) {
      layout.annotations.push(horiz ? { xref: 'paper', x: 1, yref: 'y', y: v, text: rl.label, showarrow: false, xanchor: 'right', yanchor: 'bottom', font: { ...font, size: Math.max(9, font.size - 3), color: rl.color || '#555' } }
        : { yref: 'paper', y: 1, xref: 'x', x: v, text: rl.label, showarrow: false, xanchor: 'left', yanchor: 'top', font: { ...font, size: Math.max(9, font.size - 3), color: rl.color || '#555' } });
    }
  }
  if (st.showEq && ctx.eqLabels?.length) {
    ctx.eqLabels.forEach((e, n) => layout.annotations.push({
      text: e.text, x: 0.03, y: 0.98 - n * 0.07, xref: 'paper', yref: 'paper', showarrow: false, xanchor: 'left', yanchor: 'top',
      font: { ...font, size: Math.max(9, font.size - 2), color: e.color },
    }));
  }
  // number-at-risk table under survival curves
  if (ctx.atRisk && st.atRisk !== false) {
    const ar = ctx.atRisk;
    const rows = ar.counts.length;
    const lineH = Math.max(11, font.size - 1) * 1.45;
    layout.margin = { ...layout.margin, b: 70 + (rows + 1) * lineH, l: Math.max(layout.margin.l, 110) };
    const plotH = (layout.height || 400) - layout.margin.t - layout.margin.b;
    const yPx = (k) => -(55 + k * lineH) / plotH;
    layout.annotations.push({ xref: 'paper', yref: 'paper', x: -0.02, y: yPx(0), text: '<b>Number at risk</b>', showarrow: false, xanchor: 'right', font: { ...font, size: font.size - 2 } });
    ar.counts.forEach((cnt, gi) => {
      const color = seriesStyle(ctx.g, gi).color;
      layout.annotations.push({ xref: 'paper', yref: 'paper', x: -0.02, y: yPx(gi + 1), text: ar.names[gi], showarrow: false, xanchor: 'right', font: { ...font, size: font.size - 2, color } });
      ar.times.forEach((tt, k) => layout.annotations.push({ xref: 'x', yref: 'paper', x: tt, y: yPx(gi + 1), text: String(cnt[k]), showarrow: false, font: { ...font, size: font.size - 2, color } }));
    });
    layout.xaxis = { ...layout.xaxis, tickvals: ar.times };
  }
  applyRightAxis(ctx, layout, font);
  applyAxisBreak(ctx, layout);
  return { data: ctx.data, layout };
}

// a style title of "auto" (or blank for analysis plots) is replaced by the analysis/variable name
const autoTitle = (v, auto) => ((v === 'auto' || (v === '' && auto)) && auto !== undefined ? auto : v);
const hasNegX = (gd) => gd.x.some((v) => v !== null && v < 0);

// ---------------------------------------------------------------- column ---
function beeswarm(values, width, yRange) {
  const n = values.length;
  if (!n) return [];
  const order = [...values.keys()].sort((a, b) => values[a] - values[b]);
  const offs = Array(n).fill(0);
  const tol = (yRange || 1) * 0.025;
  let i = 0;
  while (i < n) {
    let j = i;
    while (j + 1 < n && values[order[j + 1]] - values[order[i]] <= tol) j++;
    const m = j - i + 1;
    const step = Math.min(width / Math.max(m, 1), 0.09);
    for (let q = 0; q < m; q++) offs[order[i + q]] = (q - (m - 1) / 2) * step;
    i = j + 1;
  }
  return offs;
}

function errorBar(st, plus, minus, color) {
  if (st.error === 'none') return undefined;
  return {
    type: 'data', symmetric: false, array: [st.errorDir === 'down' ? 0 : plus], arrayminus: [st.errorDir === 'up' ? 0 : minus],
    color: st.errColor === 'black' ? '#000' : color, thickness: +st.errWidth || Math.max(1, +st.lineWidth || 2), width: +st.capWidth || 6, visible: true,
  };
}
// bar fill: opacity, border and optional hatch pattern
function barMarker(st, s, defaultFill) {
  const op = st.barOpacity === '' || st.barOpacity === undefined ? defaultFill : +st.barOpacity;
  const m = { color: hexA(s.color, op), line: { color: s.color, width: st.barBorder === '' || st.barBorder === undefined ? 1.8 : +st.barBorder } };
  if (s.pattern) m.pattern = { shape: s.pattern, fgcolor: s.color, bgcolor: hexA(s.color, Math.min(op, 0.15)), size: 7, solidity: 0.35 };
  return m;
}
const fmtVal = (v) => (v === null || v === undefined ? '' : Math.abs(v) >= 1000 || Math.abs(v) < 0.01 ? v.toPrecision(3) : (+v.toPrecision(3)).toString());

function columnGraph(ctx, kind) {
  const { g, gd, st, data, visible } = ctx;
  ctx.legend = false;
  const pos = new Map(visible.map((i, p) => [i, p]));
  const all = visible.flatMap((i) => gd.datasets[i].values);
  const yr = all.length ? Math.max(...all) - Math.min(...all) : 1;
  ctx.cats = { vals: visible.map((_, p) => p), text: visible.map((i) => gd.datasets[i].name), range: [-0.6, visible.length - 0.4] };
  if (visible.length > 6) ctx.cats.angle = -40;
  const bw = +st.barWidth || 0.6;

  if (kind === 'roc') { rocGraph(ctx); return; }
  if (kind === 'beforeafter') {
    const nrows = gd.datasets[0]?.rows.length || 0;
    for (let r = 0; r < nrows; r++) {
      const ys = visible.map((i) => gd.datasets[i].rows[r]?.values[0]);
      if (ys.filter((v) => v !== undefined).length < 2) continue;
      data.push({ type: 'scatter', mode: 'lines+markers', x: visible.map((_, p) => p), y: ys.map((v) => (v === undefined ? null : v)),
        line: { color: '#444', width: 1.2 }, marker: { size: +st.markerSize, color: '#fff', line: { color: '#000', width: 1.5 } },
        hovertemplate: `${gd.rowLabels[r]}: %{y}<extra></extra>`, showlegend: false });
    }
    ctx.top = visible.map((i) => Math.max(...gd.datasets[i].values));
    addPairs(ctx, pos);
    return;
  }
  visible.forEach((i) => {
    const d = gd.datasets[i];
    const p = pos.get(i);
    const s = seriesStyle(g, i);
    const err = errorBar(st, d.plus ?? 0, d.minus ?? 0, s.color);
    if (kind === 'box' || kind === 'violin') {
      const tr = {
        type: kind, x: d.values.map(() => p), y: d.values, name: d.name, line: { color: s.color, width: 1.5 },
        fillcolor: hexA(s.color, s.fill), marker: { color: s.color, size: Math.max(3, st.markerSize - 3), symbol: s.symbol },
        boxpoints: st.showPoints ? 'all' : (kind === 'box' ? 'outliers' : false), jitter: st.showPoints ? 0.4 : 0,
        pointpos: 0, width: bw, showlegend: false, hoveron: 'boxes+points',
      };
      if (kind === 'violin') { tr.points = st.showPoints ? 'all' : false; tr.box = { visible: true, width: 0.15 }; tr.meanline = { visible: true }; tr.spanmode = 'hard'; delete tr.boxpoints; }
      data.push(tr);
      ctx.top[p] = Math.max(...d.values);
      return;
    }
    if (kind === 'bar') {
      data.push({ type: 'bar', x: [p], y: [d.center], width: bw, name: d.name,
        marker: barMarker(st, s, s.fill === 0.25 ? 0.35 : s.fill),
        text: st.valueLabels ? [fmtVal(d.center)] : undefined, textposition: 'outside', cliponaxis: false, textfont: { size: Math.max(9, (+st.fontSize || 14) - 2) },
        error_y: err, hovertemplate: `${d.name}: %{y:.4g}<extra></extra>`, showlegend: false });
    }
    const showPts = !d.summaryOnly && (kind === 'scatter' || (kind === 'bar' && st.showPoints));
    if (showPts) {
      const offs = beeswarm(d.values, bw * (+st.jitter || 0.5) * 1.6, yr);
      data.push({ type: 'scatter', mode: 'markers', x: d.values.map((_, q) => p + offs[q]), y: d.values, name: d.name,
        marker: { color: kind === 'bar' ? '#fff' : s.color, size: +st.markerSize, symbol: s.symbol, line: { color: s.color, width: 1.2 } },
        hovertemplate: `${d.name}: %{y}<extra></extra>`, showlegend: false });
    }
    if ((kind === 'scatter' || kind === 'meanerror') && st.centerLine !== 'none') {
      // center line + error bars
      const lineLen = kind === 'scatter' ? bw * 0.75 : bw * 0.4;
      data.push({ type: 'scatter', mode: 'lines', x: [p - lineLen / 2, p + lineLen / 2], y: [d.center, d.center],
        line: { color: kind === 'scatter' ? '#000' : s.color, width: Math.max(2, +st.lineWidth + 0.5) }, hoverinfo: 'skip', showlegend: false });
      data.push({ type: 'scatter', mode: 'markers', x: [p], y: [d.center], marker: { opacity: 0, size: 1 },
        error_y: err && { ...err, color: kind === 'scatter' ? '#000' : s.color, width: (+st.capWidth || 6) * 2 },
        hovertemplate: `${d.name}: %{y:.4g}<extra></extra>`, showlegend: false });
    }
    ctx.top[p] = Math.max(kind === 'bar' || kind === 'meanerror' ? d.center + (d.plus || 0) : -Infinity, showPts ? Math.max(...d.values) : -Infinity,
      kind === 'scatter' ? d.center + (d.plus || 0) : -Infinity);
  });
  addPairs(ctx, pos);
}

function addPairs(ctx, pos) {
  const { st, overlays, data } = ctx;
  if (!st.showSig) return;
  const ov = overlays.find((o) => o.kind === 'pairs');
  if (!ov) return;
  const items = ov.pairs.filter((p) => pos.has(p.a) && pos.has(p.b) && (st.showNs || p.stars !== 'ns'))
    .map((p) => ({ ...p, pa: Math.min(pos.get(p.a), pos.get(p.b)), pb: Math.max(pos.get(p.a), pos.get(p.b)) }))
    .sort((a, b) => (a.pb - a.pa) - (b.pb - b.pa));
  drawBrackets(ctx, items.map((p) => ({ x0: p.pa, x1: p.pb, label: labelFor(st, p), cover: [p.pa, p.pb] })), ctx.top);
}

function labelFor(st, p) {
  if (st.sigFormat === 'p') return p.p < 0.0001 ? 'P<0.0001' : `P=${p.p.toFixed(4)}`;
  if (st.sigFormat === 'both') return `${p.stars} (${p.p < 0.0001 ? '<0.0001' : p.p.toFixed(4)})`;
  return p.stars;
}

function drawBrackets(ctx, items, topByPos) {
  if (!items.length) return;
  const vals = Object.values(topByPos).filter((v) => Number.isFinite(v));
  const allMax = Math.max(...vals);
  const allMin = Math.min(0, ...vals);
  const range = (allMax - allMin) || 1;
  const step = range * 0.09;
  const tick = range * 0.025;
  const levels = []; // occupied [x0, x1, y]
  const tops = { ...topByPos };
  for (const it of items) {
    let base = -Infinity;
    for (let x = Math.floor(it.x0 - 0.5); x <= Math.ceil(it.x1 + 0.5); x++) if (Number.isFinite(tops[x])) base = Math.max(base, tops[x]);
    for (const L of levels) if (!(it.x1 < L[0] - 0.05 || it.x0 > L[1] + 0.05)) base = Math.max(base, L[2]);
    const y = base + step;
    levels.push([it.x0, it.x1, y + step * 0.45]);
    ctx.data.push({ type: 'scatter', mode: 'lines', x: [it.x0, it.x0, it.x1, it.x1], y: [y - tick, y, y, y - tick],
      line: { color: '#000', width: 1.3 }, hoverinfo: 'skip', showlegend: false, cliponaxis: false });
    ctx.data.push({ type: 'scatter', mode: 'text', x: [(it.x0 + it.x1) / 2], y: [y], text: [it.label], textposition: 'top center',
      textfont: { size: (+ctx.st.fontSize || 14) - (it.label.startsWith('P') ? 2 : 0), color: '#000' }, hoverinfo: 'skip', showlegend: false, cliponaxis: false });
  }
  if (!(ctx.st.yMax !== '' && ctx.st.yMin !== '')) {
    const maxY = Math.max(...levels.map((L) => L[2])) + step * 0.6;
    ctx.data.push({ type: 'scatter', mode: 'markers', x: [items[0].x0], y: [maxY], marker: { opacity: 0 }, hoverinfo: 'skip', showlegend: false });
  }
}

// -------------------------------------------------------------------- XY ---
function xyGraph(ctx, kind) {
  const { g, gd, st, data, visible, overlays } = ctx;
  const curves = overlays.find((o) => o.kind === 'curves');
  visible.forEach((i) => {
    const d = gd.datasets[i];
    const s = seriesStyle(g, i);
    const pts = d.rows.map((r, k) => ({ x: gd.x[k], ...r })).filter((p) => p.x !== null && p.center !== null);
    pts.sort((a, b) => a.x - b.x);
    const connect = kind === 'xy-line' || kind === 'xy-lineonly' || kind === 'xy-area' || (st.connect && !curves);
    if (kind === 'xy-all') {
      const xs = []; const ys = [];
      pts.forEach((p) => p.values.forEach((v) => { xs.push(p.x); ys.push(v); }));
      data.push({ type: 'scatter', mode: 'markers', x: xs, y: ys, name: d.name,
        marker: { color: s.color, size: +st.markerSize, symbol: s.symbol }, legendgroup: `ds${i}` });
      if (st.connect) data.push({ type: 'scatter', mode: 'lines', x: pts.map((p) => p.x), y: pts.map((p) => p.center), line: { color: s.color, width: +st.lineWidth, dash: s.dash }, showlegend: false, hoverinfo: 'skip', legendgroup: `ds${i}` });
    } else {
      const mode = kind === 'xy-lineonly' || kind === 'xy-area' ? 'lines' : connect ? 'lines+markers' : 'markers';
      data.push({
        type: 'scatter', mode, x: pts.map((p) => p.x), y: pts.map((p) => p.center), name: d.name, legendgroup: `ds${i}`,
        marker: { color: s.color, size: +st.markerSize, symbol: s.symbol },
        line: { color: s.color, width: +st.lineWidth, dash: s.dash },
        fill: kind === 'xy-area' ? 'tozeroy' : undefined, fillcolor: kind === 'xy-area' ? hexA(s.color, s.fill) : undefined,
        error_y: st.error === 'none' || kind === 'xy-lineonly' ? undefined : {
          type: 'data', symmetric: false, array: pts.map((p) => (st.errorDir === 'down' ? 0 : p.plus || 0)),
          arrayminus: pts.map((p) => (st.errorDir === 'up' ? 0 : p.minus || 0)), color: s.color, thickness: Math.max(1, st.lineWidth - 0.5), width: +st.capWidth || 6,
        },
      });
    }
    const c = curves?.curves.find((cv) => cv.dataset === i);
    if (c?.label) (ctx.eqLabels ||= []).push({ text: `${d.name}: ${c.label}`, color: s.color });
    if (c) {
      if (st.showBand && c.lo) {
        data.push({ type: 'scatter', mode: 'lines', x: c.x, y: c.hi, line: { width: 0 }, hoverinfo: 'skip', showlegend: false, legendgroup: `ds${i}` });
        data.push({ type: 'scatter', mode: 'lines', x: c.x, y: c.lo, line: { width: 0 }, fill: 'tonexty', fillcolor: hexA(s.color, 0.15), hoverinfo: 'skip', showlegend: false, legendgroup: `ds${i}` });
      }
      data.push({ type: 'scatter', mode: 'lines', x: c.x, y: c.y, line: { color: s.color, width: +st.lineWidth, dash: s.dash, shape: 'spline' },
        name: `${d.name} (fit)`, showlegend: false, legendgroup: `ds${i}`, hovertemplate: `${d.name} fit: %{y:.4g}<extra></extra>` });
    }
  });
  if (overlays.find((o) => o.kind === 'roc')) rocGraph(ctx);
}

function rocGraph(ctx) {
  const ov = ctx.overlays.find((o) => o.kind === 'roc');
  ctx.cats = null;
  if (!ov) {
    ctx.data.push({ type: 'scatter', x: [0], y: [0], mode: 'text', text: ['Run a ROC analysis on this table and link it to the graph'], showlegend: false });
    return;
  }
  ctx.data.push({ type: 'scatter', mode: 'lines', x: [0, 100], y: [0, 100], line: { color: '#999', dash: 'dot', width: 1 }, hoverinfo: 'skip', showlegend: false });
  ctx.data.push({ type: 'scatter', mode: 'lines+markers', x: ov.x, y: ov.y, line: { color: seriesStyle(ctx.g, 0).color, width: +ctx.st.lineWidth, shape: 'hv' },
    marker: { size: 4 }, name: `AUC = ${ov.auc.toFixed(3)}` });
  ctx.legend = true;
}

// --------------------------------------------------------------- grouped ---
function groupedGraph(ctx, kind) {
  const { g, gd, st, data, visible, t } = ctx;
  const nrows = gd.rowLabels.length;
  const rowsUsed = [...Array(nrows).keys()].filter((r) => visible.some((i) => gd.datasets[i].rows[r]?.n));
  const rpos = new Map(rowsUsed.map((r, p) => [r, p]));
  const n = visible.length;
  ctx.cats = { vals: rowsUsed.map((_, p) => p), text: rowsUsed.map((r) => gd.rowLabels[r]), range: [-0.6, rowsUsed.length - 0.4] };

  if (kind === 'heatmap') {
    ctx.cats = null;
    data.push({ type: 'heatmap', z: rowsUsed.map((r) => visible.map((i) => gd.datasets[i].rows[r]?.center ?? null)),
      x: visible.map((i) => gd.datasets[i].name), y: rowsUsed.map((r) => gd.rowLabels[r]), colorscale: 'Viridis', reversescale: false,
      texttemplate: '%{z:.3g}', hovertemplate: '%{y} · %{x}: %{z}<extra></extra>' });
    ctx.legend = false;
    ctx.extraLayout.yaxis = { autorange: 'reversed', rangemode: undefined, type: 'category' };
    ctx.extraLayout.xaxis = { rangemode: undefined, type: 'category' };
    return;
  }
  if (kind === 'stacked-bar' || kind === 'stacked-percent') {
    ctx.barmode = 'stack';
    const totals = rowsUsed.map((r) => visible.reduce((s, i) => s + (gd.datasets[i].rows[r]?.center || 0), 0));
    visible.forEach((i) => {
      const s = seriesStyle(g, i);
      const ys = rowsUsed.map((r, p) => {
        const v = gd.datasets[i].rows[r]?.center || 0;
        return kind === 'stacked-percent' ? (totals[p] ? (v / totals[p]) * 100 : 0) : v;
      });
      data.push({ type: 'bar', x: rowsUsed.map((_, p) => p), y: ys, name: gd.datasets[i].name, width: +st.barWidth || 0.6,
        marker: barMarker(st, s, Math.max(0.5, s.fill)),
        text: st.valueLabels ? ys.map((v) => (kind === 'stacked-percent' ? `${v.toFixed(0)}%` : fmtVal(v))) : undefined, textposition: 'inside' });
    });
    return;
  }
  if (kind === 'grouped-line') {
    visible.forEach((i) => {
      const s = seriesStyle(g, i);
      const rows = rowsUsed.map((r) => gd.datasets[i].rows[r]);
      data.push({ type: 'scatter', mode: 'lines+markers', x: rowsUsed.map((_, p) => p), y: rows.map((rw) => rw?.center ?? null), name: gd.datasets[i].name, legendgroup: `ds${i}`,
        marker: { color: s.color, size: +st.markerSize, symbol: s.symbol }, line: { color: s.color, width: +st.lineWidth, dash: s.dash },
        error_y: st.error === 'none' ? undefined : { type: 'data', symmetric: false, array: rows.map((rw) => rw?.plus || 0), arrayminus: rows.map((rw) => rw?.minus || 0), color: s.color, width: +st.capWidth || 6 } });
    });
    return;
  }
  const groupW = 0.8;
  const w = groupW / Math.max(n, 1);
  const offs = visible.map((_, j) => (j - (n - 1) / 2) * w);
  const allv = visible.flatMap((i) => gd.datasets[i].values);
  const yr = allv.length ? Math.max(...allv) - Math.min(...allv) : 1;
  const tops = {};
  visible.forEach((i, j) => {
    const s = seriesStyle(g, i);
    const d = gd.datasets[i];
    const xs = rowsUsed.map((_, p) => p + offs[j]);
    const rows = rowsUsed.map((r) => d.rows[r]);
    if (kind === 'grouped-box') {
      const X = []; const Y = [];
      rows.forEach((rw, p) => (rw?.values || []).forEach((v) => { X.push(xs[p]); Y.push(v); }));
      data.push({ type: 'box', x: X, y: Y, name: d.name, width: w * 0.8, line: { color: s.color }, fillcolor: hexA(s.color, s.fill), boxpoints: st.showPoints ? 'all' : 'outliers', pointpos: 0, jitter: 0.3, marker: { size: Math.max(3, st.markerSize - 3), color: s.color } });
      rows.forEach((rw, p) => { tops[`${rowsUsed[p]}:${i}`] = Math.max(...(rw?.values || [-Infinity])); });
      return;
    }
    if (kind === 'grouped-bar') {
      data.push({ type: 'bar', x: xs, y: rows.map((rw) => rw?.center ?? null), width: w * (+st.barWidth || 0.6) / 0.6 * 0.85, name: d.name,
        marker: barMarker(st, s, s.fill === 0.25 ? 0.6 : s.fill),
        text: st.valueLabels ? rows.map((rw) => fmtVal(rw?.center)) : undefined, textposition: 'outside', cliponaxis: false, textfont: { size: Math.max(9, (+st.fontSize || 14) - 3) },
        error_y: st.error === 'none' || t.type === 'contingency' ? undefined : { type: 'data', symmetric: false, array: rows.map((rw) => (st.errorDir === 'down' ? 0 : rw?.plus || 0)), arrayminus: rows.map((rw) => (st.errorDir === 'up' ? 0 : rw?.minus || 0)), color: st.errColor === 'series' ? s.color : '#000', thickness: +st.errWidth || 1.5, width: +st.capWidth || 5 } });
    }
    if (kind === 'grouped-scatter' || (kind === 'grouped-bar' && st.showPoints && t.type !== 'contingency')) {
      const X = []; const Y = [];
      rows.forEach((rw, p) => {
        const vals = rw?.values || [];
        const o = beeswarm(vals, w * 0.5, yr);
        vals.forEach((v, q) => { X.push(xs[p] + o[q]); Y.push(v); });
      });
      data.push({ type: 'scatter', mode: 'markers', x: X, y: Y, name: d.name, showlegend: kind === 'grouped-scatter',
        marker: { color: kind === 'grouped-bar' ? '#fff' : s.color, size: Math.max(4, st.markerSize - 2), symbol: s.symbol, line: { color: s.color, width: 1.2 } } });
    }
    if (kind === 'grouped-scatter') {
      rows.forEach((rw, p) => {
        if (!rw || rw.center === null) return;
        data.push({ type: 'scatter', mode: 'lines', x: [xs[p] - w * 0.3, xs[p] + w * 0.3], y: [rw.center, rw.center], line: { color: '#000', width: 2 }, hoverinfo: 'skip', showlegend: false });
        if (st.error !== 'none') data.push({ type: 'scatter', mode: 'markers', x: [xs[p]], y: [rw.center], marker: { opacity: 0 }, showlegend: false, error_y: { type: 'data', symmetric: false, array: [rw.plus || 0], arrayminus: [rw.minus || 0], color: '#000', width: 4 } });
      });
    }
    rows.forEach((rw, p) => {
      if (!rw) return;
      tops[`${rowsUsed[p]}:${i}`] = Math.max(rw.center + (rw.plus || 0), ...(rw.values.length && (kind !== 'grouped-bar' || st.showPoints) ? rw.values : [-Infinity]));
    });
  });
  // significance brackets for two-way ANOVA comparisons within rows
  const ov = ctx.overlays.find((o) => o.kind === 'grouped-pairs');
  if (ov && st.showSig) {
    const jpos = new Map(visible.map((i, j) => [i, j]));
    const items = [];
    const topPos = {};
    for (const [key, v] of Object.entries(tops)) {
      const [r, i] = key.split(':').map(Number);
      if (!rpos.has(r) || !jpos.has(i)) continue;
      const xpos = rpos.get(r) + offs[jpos.get(i)];
      topPos[xpos.toFixed(3)] = v;
    }
    for (const p of ov.pairs) {
      if (!rpos.has(p.row) || !jpos.has(p.a) || !jpos.has(p.b) || (!st.showNs && p.stars === 'ns')) continue;
      const x0 = rpos.get(p.row) + offs[jpos.get(p.a)]; const x1 = rpos.get(p.row) + offs[jpos.get(p.b)];
      items.push({ x0: Math.min(x0, x1), x1: Math.max(x0, x1), label: labelFor(st, p) });
    }
    items.sort((a, b) => (a.x1 - a.x0) - (b.x1 - b.x0));
    drawBracketsContinuous(ctx, items, topPos);
  }
}

function drawBracketsContinuous(ctx, items, topPos) {
  if (!items.length) return;
  const entries = Object.entries(topPos).map(([x, v]) => [+x, v]).filter(([, v]) => Number.isFinite(v));
  const allMax = Math.max(...entries.map((e) => e[1]));
  const range = (allMax - Math.min(0, ...entries.map((e) => e[1]))) || 1;
  const step = range * 0.08; const tick = range * 0.02;
  const levels = [];
  for (const it of items) {
    let base = -Infinity;
    for (const [x, v] of entries) if (x >= it.x0 - 1e-6 && x <= it.x1 + 1e-6) base = Math.max(base, v);
    for (const L of levels) if (!(it.x1 < L[0] - 0.01 || it.x0 > L[1] + 0.01)) base = Math.max(base, L[2]);
    const y = base + step;
    levels.push([it.x0, it.x1, y + step * 0.5]);
    ctx.data.push({ type: 'scatter', mode: 'lines', x: [it.x0, it.x0, it.x1, it.x1], y: [y - tick, y, y, y - tick], line: { color: '#000', width: 1.2 }, hoverinfo: 'skip', showlegend: false, cliponaxis: false });
    ctx.data.push({ type: 'scatter', mode: 'text', x: [(it.x0 + it.x1) / 2], y: [y], text: [it.label], textposition: 'top center', textfont: { size: (+ctx.st.fontSize || 14) - 1, color: '#000' }, hoverinfo: 'skip', showlegend: false, cliponaxis: false });
  }
  ctx.data.push({ type: 'scatter', mode: 'markers', x: [items[0].x0], y: [Math.max(...levels.map((L) => L[2])) + step * 0.5], marker: { opacity: 0 }, hoverinfo: 'skip', showlegend: false });
}

// ------------------------------------------------------ multiple variables ---
function multiGraph(ctx, kind) {
  const { g, gd, st, data } = ctx;
  if (kind === 'var-box') {
    ctx.legend = false;
    ctx.visible.forEach((i, p) => {
      const s = seriesStyle(g, i);
      data.push({ type: 'box', y: gd.datasets[i].values, x: gd.datasets[i].values.map(() => p), name: gd.datasets[i].name, boxpoints: st.showPoints ? 'all' : 'outliers',
        jitter: 0.4, pointpos: 0, line: { color: s.color }, fillcolor: hexA(s.color, s.fill), marker: { color: s.color, size: Math.max(3, st.markerSize - 3) } });
    });
    ctx.cats = { vals: ctx.visible.map((_, p) => p), text: ctx.visible.map((i) => gd.datasets[i].name), range: [-0.6, ctx.visible.length - 0.4] };
    return;
  }
  const xi = Math.min(+st.xVar || 0, gd.datasets.length - 1);
  const yi = Math.min(st.yVar === undefined || st.yVar === '' ? 1 : +st.yVar, gd.datasets.length - 1);
  const ci = st.colorVar === '' || st.colorVar === undefined ? null : +st.colorVar;
  const xs = []; const ys = []; const cs = []; const labels = [];
  gd.datasets[xi]?.rows.forEach((r, k) => {
    const xv = r.values[0]; const yv = gd.datasets[yi]?.rows[k]?.values[0];
    if (xv === undefined || yv === undefined) return;
    xs.push(xv); ys.push(yv); labels.push(gd.rowLabels[k]);
    if (ci !== null) cs.push(gd.datasets[ci]?.rows[k]?.values[0] ?? null);
  });
  const s = seriesStyle(g, 0);
  data.push({ type: 'scatter', mode: 'markers', x: xs, y: ys, text: labels, name: `${gd.datasets[yi]?.name} vs ${gd.datasets[xi]?.name}`,
    marker: ci !== null ? { size: +st.markerSize, color: cs, colorscale: 'Viridis', showscale: true, colorbar: { title: { text: gd.datasets[ci]?.name } }, symbol: s.symbol }
      : { size: +st.markerSize, color: s.color, symbol: s.symbol },
    hovertemplate: '%{text}<br>%{x}, %{y}<extra></extra>' });
  ctx.legend = false;
  ctx.autoTitles = { x: gd.datasets[xi]?.name, y: gd.datasets[yi]?.name };
  ctx.extraLayout.xaxis = { rangemode: 'normal' };
  ctx.extraLayout.yaxis = { rangemode: 'normal' };
}

// ------------------------------------------------------------ analysis plot ---
function analysisPlot(ctx) {
  const { g, st, data, overlays } = ctx;
  const ov = overlays.find((o) => o.kind === 'plot');
  ctx.legend = true;
  if (!ov) {
    data.push({ type: 'scatter', x: [0], y: [0], mode: 'text', text: ['Link an analysis that produces a plot (normality, regression, PCA, Bland-Altman…)'], showlegend: false });
    return;
  }
  const P = ov.plots[Math.min(+st.plotIndex || 0, ov.plots.length - 1)];
  ctx.plot = P;
  P.traces.forEach((tr, n) => {
    const s = seriesStyle(g, n);
    const color = tr.color || s.color;
    if (tr.type === 'heatmap') {
      data.push({ type: 'heatmap', z: tr.z, x: tr.x, y: tr.y, zmin: tr.zmin, zmax: tr.zmax, colorscale: 'RdBu', reversescale: true,
        texttemplate: '%{z:.2f}', hovertemplate: '%{y} · %{x}: %{z:.3f}<extra></extra>' });
      ctx.legend = false;
      return;
    }
    if (tr.type === 'bar') {
      data.push({ type: 'bar', x: tr.x, y: tr.y, name: tr.name, marker: { color: hexA(color, 0.45), line: { color, width: 1.5 } } });
      return;
    }
    data.push({
      type: 'scatter', mode: tr.mode || 'markers', x: tr.x, y: tr.y, name: tr.name, text: tr.text, textposition: tr.textposition,
      showlegend: tr.showlegend !== false, cliponaxis: false,
      line: { color, width: +st.lineWidth, dash: tr.dash || 'solid', shape: tr.shape || 'linear' },
      marker: { color: (tr.mode || 'markers').includes('markers') && !tr.mode?.includes('lines') ? color : color, size: tr.size || +st.markerSize, symbol: tr.symbol || s.symbol },
      error_x: tr.errorX ? { type: 'data', symmetric: false, array: tr.errorX.plus, arrayminus: tr.errorX.minus, color, thickness: 1.5, width: 5 } : undefined,
      hovertemplate: tr.text && (tr.mode || '').includes('markers') ? '%{text}<br>%{x:.4g}, %{y:.4g}<extra></extra>' : undefined,
    });
  });
  const shapes = [];
  const anns = [];
  for (const hl of P.hlines || []) {
    shapes.push({ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: hl.y, y1: hl.y, line: { color: '#555', width: 1.3, dash: hl.dash || 'solid' } });
    if (hl.label) anns.push({ xref: 'paper', x: 1, y: hl.y, text: hl.label, showarrow: false, xanchor: 'right', yanchor: 'bottom', font: { size: 11 } });
  }
  for (const vl of P.vlines || []) shapes.push({ type: 'line', yref: 'paper', y0: 0, y1: 1, x0: vl.x, x1: vl.x, line: { color: '#555', width: 1.3, dash: vl.dash || 'solid' } });
  ctx.extraLayout.shapes = shapes;
  ctx.extraLayout.annotationsExtra = anns;
  ctx.autoTitles = { x: P.xTitle, y: P.yTitle, title: P.title };
  const ax = { rangemode: 'normal' };
  ctx.extraLayout.xaxis = { ...ax, ...(P.xLog ? { type: 'log' } : {}), ...(P.xCategory ? { type: 'category' } : {}) };
  ctx.extraLayout.yaxis = { ...ax, ...(P.yReversed ? { autorange: 'reversed' } : {}), ...(P.yCategory ? { type: 'category', automargin: true } : {}) };
  if (P.traces.some((t) => t.type === 'heatmap')) { ctx.extraLayout.xaxis.type = 'category'; ctx.extraLayout.yaxis.type = 'category'; }
}

// -------------------------------------------------------------- survival ---
// ------------------------------------------------------------- right Y axis ---
function applyRightAxis(ctx, layout, font) {
  const { g, st } = ctx;
  let used = false;
  for (const tr of ctx.data) {
    const m = /^ds(\d+)$/.exec(tr.legendgroup || '');
    if (m && seriesStyle(g, +m[1]).rightAxis) { tr.yaxis = 'y3'; used = true; }
  }
  if (!used) return;
  layout.yaxis3 = { ...layout.yaxis, overlaying: 'y', side: 'right', title: { text: st.y2Title || '', font: layout.yaxis.title?.font },
    range: undefined, autorange: true, rangemode: 'tozero', showgrid: false, mirror: false, tickfont: font };
  layout.margin = { ...layout.margin, r: Math.max(layout.margin.r, 80) };
  if (layout.legend?.x > 1) layout.legend = { ...layout.legend, x: 1.12 };
}

// ------------------------------------------------------------------ axis break ---
function applyAxisBreak(ctx, layout) {
  const { st } = ctx;
  const from = +st.yBreakFrom; const to = +st.yBreakTo;
  if (!st.yBreak || !(to > from) || st.yLog || st.orientation === 'h' || layout.yaxis3) return;
  let ymax = -Infinity; let ymin = Infinity;
  for (const tr of ctx.data) {
    if (!Array.isArray(tr.y) || tr.type === 'heatmap' || tr.type === 'pie') continue;
    tr.y.forEach((v, k) => {
      if (typeof v !== 'number') return;
      const up = tr.error_y?.array?.[k] || 0; const dn = tr.error_y?.arrayminus?.[k] || 0;
      ymax = Math.max(ymax, v + up); ymin = Math.min(ymin, v - dn);
    });
  }
  if (!Number.isFinite(ymax) || ymax <= to) return;
  const frac = Math.min(0.85, Math.max(0.15, +st.breakFrac || 0.55));
  const gap = 0.035;
  const lowMin = st.yMin !== '' && st.yMin !== undefined ? +st.yMin : Math.min(0, ymin);
  const highMax = st.yMax !== '' && st.yMax !== undefined ? +st.yMax : ymax + (ymax - to) * 0.08;
  const base = { ...layout.yaxis, autorange: false, rangemode: undefined };
  layout.yaxis = { ...base, domain: [0, frac - gap / 2], range: [lowMin, from] };
  layout.yaxis2 = { ...base, domain: [frac + gap / 2, 1], range: [to, highMax], title: { text: '' }, anchor: 'x' };
  layout.yaxis.title = { ...(layout.yaxis.title || {}), standoff: 10 };
  const extra = [];
  for (const tr of ctx.data) {
    if (tr.type === 'pie' || tr.type === 'heatmap') continue;
    extra.push({ ...tr, yaxis: 'y2', showlegend: false });
  }
  ctx.data.push(...extra);
  // break marks: two short diagonal strokes across the axis line
  const w = 0.018; const hgt = 0.012;
  for (const yc of [frac - gap / 2, frac + gap / 2]) {
    layout.shapes.push({ type: 'line', xref: 'paper', yref: 'paper', x0: -w, x1: w, y0: yc - hgt, y1: yc + hgt, line: { color: st.axisColor || '#000', width: 1.5 } });
  }
  layout.xaxis = { ...layout.xaxis, anchor: 'y' };
}

// --------------------------------------------------------------- nested ---
function nestedGraph(ctx) {
  const { g, gd, st, data, visible, t } = ctx;
  ctx.legend = false;
  ctx.cats = { vals: visible.map((_, p) => p), text: visible.map((i) => gd.datasets[i].name), range: [-0.6, visible.length - 0.4] };
  visible.forEach((i, p) => {
    const s = seriesStyle(g, i);
    const reps = t.datasets[i].reps || 1;
    const w = Math.min(0.7, 0.12 * reps);
    const means = [];
    for (let k = 0; k < reps; k++) {
      const vals = [];
      t.cells.forEach((row, r) => {
        const off = t.datasets.slice(0, i).reduce((a, d) => a + (d.reps || 1), 0);
        const v = parseFloat(row[off + k]);
        if (Number.isFinite(v) && !t.excluded?.[`${r},${off + k}`]) vals.push(v);
      });
      if (!vals.length) continue;
      const x = p + (reps > 1 ? (k / (reps - 1) - 0.5) * w : 0);
      const sym = SYMBOLS[k % SYMBOLS.length];
      data.push({ type: 'scatter', mode: 'markers', x: vals.map(() => x), y: vals, marker: { color: hexA(s.color, 0.55), size: Math.max(4, st.markerSize - 3), symbol: sym },
        hovertemplate: `${gd.datasets[i].name} · subject ${k + 1}: %{y}<extra></extra>`, showlegend: false });
      const m = vals.reduce((a, b) => a + b, 0) / vals.length;
      means.push(m);
      data.push({ type: 'scatter', mode: 'markers', x: [x], y: [m], marker: { color: '#fff', size: st.markerSize + 3, symbol: sym, line: { color: s.color, width: 2 } },
        hovertemplate: `Subject ${k + 1} mean: %{y:.4g}<extra></extra>`, showlegend: false });
    }
    if (means.length) {
      const gm = means.reduce((a, b) => a + b, 0) / means.length;
      data.push({ type: 'scatter', mode: 'lines', x: [p - w / 2 - 0.08, p + w / 2 + 0.08], y: [gm, gm], line: { color: '#000', width: 2.5 }, hoverinfo: 'skip', showlegend: false });
      ctx.top[p] = Math.max(...gd.datasets[i].values);
    }
  });
  addPairs(ctx, new Map(visible.map((i, p) => [i, p])));
}

async function survivalGraph(ctx) {
  const { g, st, data, t } = ctx;
  let res;
  try { res = await kmData(t); } catch (e) {
    data.push({ type: 'scatter', x: [0], y: [0], mode: 'text', text: [`Enter survival data (${e.message})`], showlegend: false });
    return;
  }
  const scale = st.survivalAsFraction ? 1 : 100;
  for (const c of res.overlay.curves) {
    if (seriesStyle(g, c.dataset).hidden) continue;
    const s = seriesStyle(g, c.dataset);
    const name = t.datasets[c.dataset]?.name || '';
    if (st.showCI) {
      data.push({ type: 'scatter', mode: 'lines', x: c.t, y: c.hi.map((v) => v * scale), line: { width: 0, shape: 'hv' }, hoverinfo: 'skip', showlegend: false });
      data.push({ type: 'scatter', mode: 'lines', x: c.t, y: c.lo.map((v) => v * scale), line: { width: 0, shape: 'hv' }, fill: 'tonexty', fillcolor: hexA(s.color, 0.15), hoverinfo: 'skip', showlegend: false });
    }
    const maxT = Math.max(...c.t, ...(c.censorT.length ? c.censorT : [0]));
    const xs = [...c.t, maxT]; const ys = [...c.s, c.s[c.s.length - 1]].map((v) => v * scale);
    data.push({ type: 'scatter', mode: 'lines', x: xs, y: ys, name, line: { color: s.color, width: +st.lineWidth, shape: 'hv', dash: s.dash }, hovertemplate: `${name}: %{y:.1f} at %{x}<extra></extra>` });
    if (st.censorMarks && c.censorT.length) {
      data.push({ type: 'scatter', mode: 'markers', x: c.censorT, y: c.censorS.map((v) => v * scale), marker: { symbol: 'line-ns-open', size: 10, color: s.color, line: { width: 2, color: s.color } }, showlegend: false, hovertemplate: 'Censored at %{x}<extra></extra>' });
    }
  }
  if (st.atRisk && res.overlay.atRisk) ctx.atRisk = res.overlay.atRisk;
}

// ----------------------------------------------------------------- parts ---
function partsGraph(ctx, kind) {
  const { g, gd, st, data } = ctx;
  const d = gd.datasets[0];
  if (!d) return;
  const labels = []; const values = []; const colors = [];
  d.rows.forEach((r, k) => { if (r.center !== null && r.n) { labels.push(gd.rowLabels[k]); values.push(r.center); colors.push(seriesStyle(g, k).color); } });
  if (kind === 'pie' || kind === 'donut') {
    data.push({ type: 'pie', labels, values, hole: kind === 'donut' ? 0.5 : 0, sort: false, direction: 'clockwise',
      marker: { colors, line: { color: '#fff', width: 2 } }, textinfo: 'percent', textposition: 'inside', insidetextorientation: 'horizontal',
      textfont: { size: Math.max(10, (+st.fontSize || 14) - 1) }, domain: { x: [0, 1], y: [0, 0.94] } });
    ctx.legend = !!st.showLegend;
    ctx.extraLayout.xaxis = { visible: false }; ctx.extraLayout.yaxis = { visible: false };
  } else if (kind === 'parts-stacked') {
    const tot = values.reduce((a, b) => a + b, 0) || 1;
    labels.forEach((lab, k) => data.push({ type: 'bar', x: [0], y: [(values[k] / tot) * 100], name: lab, marker: { color: colors[k] }, width: 0.5, text: [`${((values[k] / tot) * 100).toFixed(1)}%`], textposition: 'inside' }));
    ctx.barmode = 'stack';
    ctx.cats = { vals: [0], text: [d.name], range: [-0.8, 0.8] };
  } else {
    data.push({ type: 'bar', orientation: 'h', y: labels, x: values, marker: { color: colors }, showlegend: false });
    ctx.legend = false;
    ctx.extraLayout.yaxis = { autorange: 'reversed', rangemode: undefined, type: 'category' };
  }
}

/** Apply post-build fixes that depend on the computed layout. */
export function finalizeLayout(fig, g) {
  const L = fig.layout;
  if (g.kind === 'roc') {
    L.xaxis = { ...L.xaxis, title: { text: '100% - Specificity%' }, range: [0, 100], autorange: false, tickvals: undefined, ticktext: undefined };
    L.yaxis = { ...L.yaxis, title: { text: 'Sensitivity%' }, range: [0, 102], autorange: false };
  }
  return fig;
}

export async function figureFor(g, opts) {
  const fig = await buildFigure(g, opts);
  const t = getTable(g.tableId);
  if (t?.type === 'survival' && g.style.yMin === '' && g.style.yMax === '') {
    const s = g.style.survivalAsFraction ? 1 : 100;
    fig.layout.yaxis = { ...fig.layout.yaxis, range: [0, s * 1.05], autorange: false };
  }
  return finalizeLayout(fig, g);
}

export const PLOT_CONFIG = (editable) => ({
  responsive: false, displaylogo: false, editable,
  edits: editable ? { titleText: true, axisTitleText: true, legendPosition: true, annotationPosition: true, annotationText: true, shapePosition: false } : {},
  modeBarButtonsToRemove: ['select2d', 'lasso2d', 'autoScale2d', 'toggleSpikelines'],
  toImageButtonOptions: { format: 'png', scale: 3 },
});

export function clearCache() { cache.clear(); }
