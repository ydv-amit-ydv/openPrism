// Publication export: PNG (with DPI metadata), TIFF (uncompressed or PackBits,
// RGB/RGBA/grayscale, resolution tags), JPEG (JFIF density), WEBP, SVG and
// vector PDF; user-chosen size (px / in / cm) and resolution; batch export to ZIP.
import { figureFor } from './graphs.js';
import { P } from './state.js';
import { download, h, modal, toast, trackedFetch } from './ui.js';

// ------------------------------------------------------------------ CRC32 (PNG chunks, ZIP)
const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; }
  return t;
})();
function crc32(bytes, start = 0, end = bytes.length) {
  let c = 0xffffffff;
  for (let i = start; i < end; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

// ------------------------------------------------------------------ encoders
/** Insert/replace a pHYs chunk so the PNG declares its DPI. */
export function pngWithDpi(bytes, dpi) {
  const ppm = Math.round(dpi / 0.0254);
  const chunk = new Uint8Array(21);
  const dv = new DataView(chunk.buffer);
  dv.setUint32(0, 9);
  chunk.set([0x70, 0x48, 0x59, 0x73], 4); // 'pHYs'
  dv.setUint32(8, ppm); dv.setUint32(12, ppm); chunk[16] = 1;
  dv.setUint32(17, crc32(chunk, 4, 17));
  // strip existing pHYs chunks, insert after IHDR (8-byte signature + 25-byte IHDR)
  const parts = [bytes.slice(0, 33), chunk];
  let p = 33;
  while (p < bytes.length) {
    const len = new DataView(bytes.buffer, bytes.byteOffset + p).getUint32(0);
    const type = String.fromCharCode(...bytes.slice(p + 4, p + 8));
    if (type !== 'pHYs') parts.push(bytes.slice(p, p + 12 + len));
    p += 12 + len;
  }
  const out = new Uint8Array(parts.reduce((a, b) => a + b.length, 0));
  let o = 0;
  for (const part of parts) { out.set(part, o); o += part.length; }
  return out;
}

/** Set the JFIF APP0 density of a JPEG to the chosen DPI. */
export function jpegWithDpi(bytes, dpi) {
  if (bytes[2] === 0xff && bytes[3] === 0xe0 && String.fromCharCode(...bytes.slice(6, 10)) === 'JFIF') {
    bytes[13] = 1; // units: dots per inch
    bytes[14] = dpi >> 8; bytes[15] = dpi & 0xff; bytes[16] = dpi >> 8; bytes[17] = dpi & 0xff;
  }
  return bytes;
}

function packBits(row) {
  const out = [];
  let i = 0;
  while (i < row.length) {
    let run = 1;
    while (i + run < row.length && run < 128 && row[i + run] === row[i]) run++;
    if (run > 1) { out.push(257 - run, row[i]); i += run; continue; }
    let lit = 1;
    while (i + lit < row.length && lit < 128 && !(i + lit + 1 < row.length && row[i + lit] === row[i + lit + 1])) lit++;
    out.push(lit - 1);
    for (let k = 0; k < lit; k++) out.push(row[i + k]);
    i += lit;
  }
  return out;
}

/** Baseline TIFF encoder (little endian, one strip per row). */
export function encodeTiff(imageData, { dpi = 300, mode = 'rgb', compress = true } = {}) {
  const { width: w, height: hgt, data } = imageData;
  const spp = mode === 'gray' ? 1 : mode === 'rgba' ? 4 : 3;
  const rows = [];
  for (let y = 0; y < hgt; y++) {
    const row = new Uint8Array(w * spp);
    for (let x = 0; x < w; x++) {
      const s = (y * w + x) * 4; const d = x * spp;
      if (spp === 1) row[d] = Math.round(0.2126 * data[s] + 0.7152 * data[s + 1] + 0.0722 * data[s + 2]);
      else { row[d] = data[s]; row[d + 1] = data[s + 1]; row[d + 2] = data[s + 2]; if (spp === 4) row[d + 3] = data[s + 3]; }
    }
    rows.push(compress ? Uint8Array.from(packBits(row)) : row);
  }
  const tags = [];
  const extra = []; // out-of-line values
  const nTags = spp === 4 ? 15 : 14;
  const ifdOffset = 8;
  const ifdSize = 2 + nTags * 12 + 4;
  let cursor = ifdOffset + ifdSize;
  const addExtra = (bytes) => { const off = cursor; extra.push({ off, bytes }); cursor += bytes.length + (bytes.length % 2); return off; };
  const u16 = (...v) => { const b = new Uint8Array(v.length * 2); const dv = new DataView(b.buffer); v.forEach((x, i) => dv.setUint16(i * 2, x, true)); return b; };
  const u32 = (...v) => { const b = new Uint8Array(v.length * 4); const dv = new DataView(b.buffer); v.forEach((x, i) => dv.setUint32(i * 4, x, true)); return b; };
  const bpsOff = spp > 1 ? addExtra(u16(...Array(spp).fill(8))) : 0;
  const xres = addExtra(u32(dpi, 1));
  const yres = addExtra(u32(dpi, 1));
  const software = addExtra(new TextEncoder().encode('OpenPrism\0'));
  const stripOffsetsOff = addExtra(new Uint8Array(4 * hgt));
  const stripCountsOff = addExtra(new Uint8Array(4 * hgt));
  const dataStart = cursor;
  const offsets = []; let p = dataStart;
  for (const r of rows) { offsets.push(p); p += r.length; }
  const tag = (id, type, count, value) => tags.push({ id, type, count, value });
  tag(256, 4, 1, w); tag(257, 4, 1, hgt);
  tag(258, 3, spp, spp > 1 ? bpsOff : 8);
  tag(259, 3, 1, compress ? 32773 : 1);
  tag(262, 3, 1, spp === 1 ? 1 : 2);
  tag(273, 4, hgt, hgt === 1 ? offsets[0] : stripOffsetsOff);
  tag(277, 3, 1, spp); tag(278, 4, 1, 1);
  tag(279, 4, hgt, hgt === 1 ? rows[0].length : stripCountsOff);
  tag(282, 5, 1, xres); tag(283, 5, 1, yres); tag(284, 3, 1, 1); tag(296, 3, 1, 2); tag(305, 2, 10, software);
  if (spp === 4) tag(338, 3, 1, 2);
  tags.sort((a, b) => a.id - b.id);
  const out = new Uint8Array(p);
  const dv = new DataView(out.buffer);
  out.set([0x49, 0x49]); dv.setUint16(2, 42, true); dv.setUint32(4, ifdOffset, true);
  dv.setUint16(ifdOffset, tags.length, true);
  tags.forEach((t, i) => {
    const o = ifdOffset + 2 + i * 12;
    dv.setUint16(o, t.id, true); dv.setUint16(o + 2, t.type, true); dv.setUint32(o + 4, t.count, true);
    if (t.type === 3 && t.count === 1) dv.setUint16(o + 8, t.value, true); else dv.setUint32(o + 8, t.value, true);
  });
  dv.setUint32(ifdOffset + 2 + tags.length * 12, 0, true);
  for (const e of extra) out.set(e.bytes, e.off);
  offsets.forEach((v, i) => { dv.setUint32(stripOffsetsOff + i * 4, v, true); dv.setUint32(stripCountsOff + i * 4, rows[i].length, true); });
  rows.forEach((r, i) => out.set(r, offsets[i]));
  return out;
}

/** Minimal ZIP (store) for batch exports. */
export function makeZip(files) {
  const enc = new TextEncoder();
  const chunks = []; const central = []; let offset = 0;
  for (const { name, bytes } of files) {
    const nb = enc.encode(name); const crc = crc32(bytes);
    const lh = new Uint8Array(30 + nb.length); const dv = new DataView(lh.buffer);
    dv.setUint32(0, 0x04034b50, true); dv.setUint16(4, 20, true); dv.setUint16(8, 0, true);
    dv.setUint32(14, crc, true); dv.setUint32(18, bytes.length, true); dv.setUint32(22, bytes.length, true);
    dv.setUint16(26, nb.length, true); lh.set(nb, 30);
    chunks.push(lh, bytes);
    const ch = new Uint8Array(46 + nb.length); const cv = new DataView(ch.buffer);
    cv.setUint32(0, 0x02014b50, true); cv.setUint16(4, 20, true); cv.setUint16(6, 20, true);
    cv.setUint32(16, crc, true); cv.setUint32(20, bytes.length, true); cv.setUint32(24, bytes.length, true);
    cv.setUint16(28, nb.length, true); cv.setUint32(42, offset, true); ch.set(nb, 46);
    central.push(ch);
    offset += lh.length + bytes.length;
  }
  const cdSize = central.reduce((a, b) => a + b.length, 0);
  const end = new Uint8Array(22); const ev = new DataView(end.buffer);
  ev.setUint32(0, 0x06054b50, true); ev.setUint16(8, files.length, true); ev.setUint16(10, files.length, true);
  ev.setUint32(12, cdSize, true); ev.setUint32(16, offset, true);
  return new Blob([...chunks, ...central, end], { type: 'application/zip' });
}

// ------------------------------------------------------------------ rendering
const loaded = {};
function loadScript(src) {
  if (!loaded[src]) loaded[src] = new Promise((res, rej) => { const s = document.createElement('script'); s.src = src; s.onload = res; s.onerror = () => rej(new Error(`Could not load ${src}`)); document.head.append(s); });
  return loaded[src];
}
async function pdfLibs() {
  await loadScript('/static/vendor/jspdf.umd.min.js');
  await loadScript('/static/vendor/svg2pdf.umd.min.js');
  return window.jspdf.jsPDF;
}

const dataUrlBytes = async (url) => new Uint8Array(await (await fetch(url)).arrayBuffer());
const safeName = (s) => String(s || 'graph').replace(/[\\/:*?"<>|]+/g, '_').slice(0, 80);

/** Target size in CSS pixels (96 per inch) from the user's units. */
export function cssSize(opts) {
  const f = { px: 1, in: 96, cm: 96 / 2.54 }[opts.units || 'px'];
  return { w: Math.max(50, Math.round(opts.width * f)), h: Math.max(50, Math.round(opts.height * f)) };
}

export async function graphSvgText(g, w, hgt, opts = {}) {
  const fig = await figureFor(g, { width: w, height: hgt });
  Object.assign(fig.layout, { width: w, height: hgt });
  if (opts.transparent) { fig.layout.paper_bgcolor = 'rgba(0,0,0,0)'; fig.layout.plot_bgcolor = 'rgba(0,0,0,0)'; }
  const url = await Plotly.toImage({ data: fig.data, layout: fig.layout }, { format: 'svg', width: w, height: hgt });
  return decodeURIComponent(url.slice(url.indexOf(',') + 1));
}

async function rasterFromSvg(svgText, w, hgt, scale, opts) {
  const img = new Image();
  const blobUrl = URL.createObjectURL(new Blob([svgText], { type: 'image/svg+xml' }));
  await new Promise((res, rej) => { img.onload = res; img.onerror = () => rej(new Error('Rendering failed')); img.src = blobUrl; });
  const c = document.createElement('canvas');
  c.width = Math.round(w * scale); c.height = Math.round(hgt * scale);
  const ctx = c.getContext('2d');
  if (!opts.transparent || ['jpeg'].includes(opts.format)) { ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, c.width, c.height); }
  ctx.drawImage(img, 0, 0, c.width, c.height);
  URL.revokeObjectURL(blobUrl);
  if (opts.color === 'gray') {
    const d = ctx.getImageData(0, 0, c.width, c.height);
    for (let i = 0; i < d.data.length; i += 4) { const v = 0.2126 * d.data[i] + 0.7152 * d.data[i + 1] + 0.0722 * d.data[i + 2]; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; }
    ctx.putImageData(d, 0, 0);
  }
  return c;
}

/** Render an SVG document to the requested format. Returns {bytes|blob, ext, mime}. */
export async function renderSvgTo(svgText, w, hgt, opts) {
  const dpi = Math.max(36, Math.min(2400, +opts.dpi || 300));
  const fmt = opts.format;
  if (fmt === 'svg') {
    let s = svgText;
    if (opts.units && opts.units !== 'px') s = s.replace(/<svg([^>]*?)width="[^"]*"([^>]*?)height="[^"]*"/, `<svg$1width="${opts.width}${opts.units}"$2height="${opts.height}${opts.units}"`);
    if (!/viewBox=/.test(s.slice(0, 400))) s = s.replace('<svg', `<svg viewBox="0 0 ${w} ${hgt}"`);
    return { blob: new Blob([s], { type: 'image/svg+xml' }), ext: 'svg' };
  }
  if (fmt === 'eps' || fmt === 'emf') {   // vector formats converted on the server (nothing is stored)
    const blob = await trackedFetch(`Vector export (${fmt.toUpperCase()})`, '/api/convert',
      { svg: svgText, format: fmt, title: opts.title || 'OpenPrism figure', gray: opts.color === 'gray', transparent: !!opts.transparent });
    return { blob, ext: fmt };
  }
  if (fmt === 'pdf') {
    const JsPDF = await pdfLibs();
    const el = new DOMParser().parseFromString(svgText, 'image/svg+xml').documentElement;
    const wPt = w * 0.75; const hPt = hgt * 0.75; // 96 px per inch, 72 pt per inch
    const doc = new JsPDF({ unit: 'pt', format: [wPt, hPt], orientation: wPt > hPt ? 'landscape' : 'portrait' });
    document.body.append(el); // svg2pdf needs computed styles
    el.style.position = 'fixed'; el.style.left = '-10000px';
    try { await doc.svg(el, { x: 0, y: 0, width: wPt, height: hPt }); } finally { el.remove(); }
    return { blob: doc.output('blob'), ext: 'pdf' };
  }
  const canvas = await rasterFromSvg(svgText, w, hgt, dpi / 96, opts);
  if (fmt === 'tiff' || fmt === 'tif') {
    const id = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height);
    const mode = opts.color === 'gray' ? 'gray' : opts.transparent ? 'rgba' : 'rgb';
    return { bytes: encodeTiff(id, { dpi, mode, compress: opts.compress !== false }), ext: 'tif', mime: 'image/tiff' };
  }
  const mime = { png: 'image/png', jpeg: 'image/jpeg', webp: 'image/webp' }[fmt] || 'image/png';
  const url = canvas.toDataURL(mime, 0.95);
  let bytes = await dataUrlBytes(url);
  if (fmt === 'png') bytes = pngWithDpi(bytes, dpi);
  if (fmt === 'jpeg') bytes = jpegWithDpi(bytes, dpi);
  return { bytes, ext: fmt === 'jpeg' ? 'jpg' : fmt, mime };
}

export async function exportGraphWith(g, opts) {
  const { w, h: hgt } = cssSize(opts);
  const svg = await graphSvgText(g, w, hgt, opts);
  return renderSvgTo(svg, w, hgt, opts);
}

function save(name, r) {
  download(`${safeName(name)}.${r.ext}`, r.blob || new Blob([r.bytes], { type: r.mime || 'application/octet-stream' }));
}

// ------------------------------------------------------------------ dialog
const PREF_KEY = 'openprism.pref.export';
function loadPrefs() { try { return JSON.parse(localStorage.getItem(PREF_KEY) || '{}'); } catch (_) { return {}; } }
function savePrefs(p) { try { localStorage.setItem(PREF_KEY, JSON.stringify(p)); } catch (_) { /* ignore */ } }

/**
 * Export dialog for a graph, a layout ({kind:'layout', svg: async (w,h)=>svgText, size:{w,h}, name})
 * or a batch of graphs. target = {kind:'graph', g} | {kind:'layout', ...} | {kind:'all'}
 */
export function exportDialog(target) {
  const base = target.kind === 'graph' ? { w: target.g.style.width, h: target.g.style.height } : target.size || { w: 520, h: 400 };
  const prefs = { format: 'tiff', dpi: 300, units: 'in', color: 'rgb', transparent: false, compress: true, ...loadPrefs() };
  const o = { ...prefs, width: +(base.w / 96).toFixed(2), height: +(base.h / 96).toFixed(2) };
  if (o.units === 'px') { o.width = base.w; o.height = base.h; } else if (o.units === 'cm') { o.width = +(base.w / 96 * 2.54).toFixed(2); o.height = +(base.h / 96 * 2.54).toFixed(2); }
  const aspect = base.w / base.h;
  let lock = true;
  const info = h('div', { class: 'hint' });
  const wIn = h('input', { type: 'number', step: 'any', value: o.width });
  const hIn = h('input', { type: 'number', step: 'any', value: o.height });
  const dpiIn = h('input', { type: 'number', step: 1, min: 36, max: 2400, value: o.dpi, style: { width: '90px' } });
  const sel = (key, options, onchange) => h('select', { onchange: (e) => { o[key] = e.target.value; onchange?.(); upd(); } }, options.map(([v, l]) => h('option', { value: v, selected: String(o[key]) === String(v) }, l)));
  function upd() {
    o.width = +wIn.value; o.height = +hIn.value; o.dpi = +dpiIn.value;
    const { w, h: hh } = cssSize(o);
    const raster = !['svg', 'pdf', 'eps', 'emf'].includes(o.format);
    info.textContent = raster ? `Output: ${Math.round(w * o.dpi / 96)} × ${Math.round(hh * o.dpi / 96)} pixels at ${o.dpi} dpi (${(w / 96).toFixed(2)} × ${(hh / 96).toFixed(2)} in)`
      : `Vector output, ${(w / 96).toFixed(2)} × ${(hh / 96).toFixed(2)} in — scales to any size without loss.`;
  }
  wIn.addEventListener('input', () => { if (lock) hIn.value = +(+wIn.value / aspect).toFixed(3); upd(); });
  hIn.addEventListener('input', () => { if (lock) wIn.value = +(+hIn.value * aspect).toFixed(3); upd(); });
  dpiIn.addEventListener('input', upd);
  const unitsSel = sel('units', [['in', 'inches'], ['cm', 'cm'], ['px', 'pixels (96/in)']], () => {
    const { w, h: hh } = { w: base.w, h: base.h };
    const f = { px: 1, in: 1 / 96, cm: 2.54 / 96 }[o.units];
    wIn.value = +(w * f).toFixed(3); hIn.value = +(hh * f).toFixed(3);
  });
  const field = (label, input) => h('div', { class: 'field' }, h('label', {}, label), input);
  const presets = h('div', { class: 'seg', style: { flexWrap: 'wrap' } }, [[72, 'Screen 72'], [150, '150'], [300, 'Print 300'], [600, 'Line art 600'], [1200, '1200']].map(([v, l]) =>
    h('button', { type: 'button', onclick: () => { dpiIn.value = v; upd(); } }, l)));
  const body = h('div', {},
    field('Format', sel('format', [['tiff', 'TIFF — journals, print (lossless)'], ['png', 'PNG — documents, slides (lossless)'], ['pdf', 'PDF — vector'], ['svg', 'SVG — vector, editable'], ['eps', 'EPS — vector (Illustrator, LaTeX, print)'], ['emf', 'EMF — vector (Word, PowerPoint)'],
      ['jpeg', 'JPEG — photos, small files'], ['webp', 'WEBP — web']])),
    field('Size', h('div', { style: { display: 'flex', gap: '6px', alignItems: 'center' } }, wIn, '×', hIn, unitsSel,
      h('label', { class: 'check-line', style: { margin: 0 } }, h('input', { type: 'checkbox', checked: lock, onchange: (e) => { lock = e.target.checked; } }), 'keep proportions'))),
    field('Resolution (dpi)', h('div', { style: { display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' } }, dpiIn, presets)),
    field('Color', sel('color', [['rgb', 'Color (RGB)'], ['gray', 'Grayscale']])),
    field('Background', sel('transparent', [['false', 'White'], ['true', 'Transparent (PNG, TIFF, SVG, PDF)']])),
    field('TIFF compression', sel('compress', [['true', 'PackBits (lossless, smaller)'], ['false', 'None (maximum compatibility)']])),
    info,
    target.kind === 'all' ? h('p', { class: 'hint' }, `All ${P().graphs.length} graphs are exported with these settings into one ZIP file (each at its own aspect ratio, using this width).`) : null);
  upd();
  modal({
    title: target.kind === 'all' ? 'Export all graphs' : target.kind === 'layout' ? 'Export layout' : 'Export graph', body,
    buttons: [{ label: 'Cancel' }, { label: 'Export', primary: true, onClick: async () => {
      o.transparent = o.transparent === true || o.transparent === 'true';
      o.compress = !(o.compress === false || o.compress === 'false');
      savePrefs({ format: o.format, dpi: o.dpi, units: o.units, color: o.color, transparent: o.transparent, compress: o.compress });
      toast('Exporting…');
      try {
        if (target.kind === 'graph') save(target.g.name, await exportGraphWith(target.g, o));
        else if (target.kind === 'layout') {
          const { w, h: hh } = cssSize(o);
          save(target.name, await renderSvgTo(await target.svg(w, hh, o), w, hh, o));
        } else {
          const files = [];
          for (const g of P().graphs) {
            const ratio = g.style.width / g.style.height;
            const r = await exportGraphWith(g, { ...o, height: o.width / ratio });
            const bytes = r.bytes || new Uint8Array(await r.blob.arrayBuffer());
            files.push({ name: `${safeName(g.name)}.${r.ext}`, bytes });
          }
          download(`${safeName(P().name)}-graphs.zip`, makeZip(files));
        }
        toast('Export complete');
      } catch (e) { toast(`Export failed: ${e.message}`, 'err'); }
      return undefined;
    } }],
  });
}
