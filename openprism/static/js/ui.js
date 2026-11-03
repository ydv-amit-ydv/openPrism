// Small DOM helpers, API client, modal dialogs, toasts and context menus.

import { serverTiming, startJob } from './activity.js';

export function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else if (k === 'html') el.innerHTML = v;
    else if (v === true) el.setAttribute(k, '');
    else el.setAttribute(k, v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

export const $ = (sel, root = document) => root.querySelector(sel);

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}
let onAuthLost = null;
export function setAuthLostHandler(fn) { onAuthLost = fn; }

const TRACKED = { '/api/analyze': 'Analysis', '/api/import': 'Import file', '/api/power': 'Power calculation', '/api/graphdata': 'Graph data' };

/** JSON API call. Calculations are shown in the activity indicator and log (label = what the user sees). */
export async function api(path, body, method, label) {
  const opts = { method: method || (body !== undefined ? 'POST' : 'GET'), headers: {}, credentials: 'same-origin', cache: 'no-store' };
  if (opts.method !== 'GET') opts.headers['X-OpenPrism'] = '1'; // CSRF guard expected by the server
  if (body instanceof FormData) opts.body = body;
  else if (body !== undefined) { opts.body = JSON.stringify(body); opts.headers['Content-Type'] = 'application/json'; }
  const name = label || TRACKED[path];
  const finish = name ? startJob(name, 'server') : null;
  let r;
  // busy (too many calculations at once / per minute): wait briefly and retry quietly instead of showing an error
  for (const pause of [300, 800, 1500, 3000, 5000, 0]) {
    try { r = await fetch(path, opts); } catch (e) { finish?.('error', { error: 'network error' }); throw new ApiError('Cannot reach the server. Check your connection.', 0); }
    if (r.status !== 429 || !r.headers.get('X-OpenPrism-Busy') || !pause || opts.body instanceof FormData) break;
    await new Promise((res) => setTimeout(res, pause));
  }
  let data;
  try { data = await r.json(); } catch (_) { data = null; }
  finish?.(r.ok ? 'ok' : 'error', { ...serverTiming(r), ...(r.ok ? {} : { error: (data && data.error) || r.status }) });
  if (r.status === 401 && data && data.auth === false && onAuthLost) onAuthLost();
  if (!r.ok) throw new ApiError((data && data.error) || `${r.status} ${r.statusText}`, r.status);
  return data;
}

/** fetch() for binary downloads (exports, conversions), also tracked in the activity log. */
export async function trackedFetch(label, path, body) {
  const finish = startJob(label, 'server');
  let r;
  try {
    r = await fetch(path, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-OpenPrism': '1' }, body: JSON.stringify(body) });
  } catch (e) { finish('error', { error: 'network error' }); throw new Error('Cannot reach the server.'); }
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try { msg = (await r.json()).error || msg; } catch (_) { /* ignore */ }
    finish('error', { error: msg });
    throw new Error(msg);
  }
  const blob = await r.blob();
  finish('ok', serverTiming(r));
  return blob;
}

export function toast(msg, kind = '', action = null) {
  const t = h('div', { class: `toast ${kind}` }, msg);
  if (action) t.append(h('button', { class: 'toast-act', onclick: () => { t.remove(); action.onClick(); } }, action.label));
  document.getElementById('toast-root').append(t);
  setTimeout(() => t.remove(), action ? 8000 : kind === 'err' ? 6000 : 3000);
}

// last pointer position: quick inputs open where the user is working
let lastPointer = null;
if (typeof document !== 'undefined') document.addEventListener('pointerdown', (e) => { lastPointer = { x: e.clientX, y: e.clientY }; }, true);

export function status(msg) { document.getElementById('status-text').textContent = msg; }

/** Open a modal. Returns {close, el}. buttons: [{label, primary, onClick -> false to keep open}] */
export function modal({ title, body, buttons = [], wide = false, onClose }) {
  const root = document.getElementById('modal-root');
  const close = () => { bg.remove(); document.removeEventListener('keydown', onKey); onClose && onClose(); };
  const foot = h('div', { class: 'modal-foot' });
  for (const b of buttons) {
    foot.append(h('button', {
      class: `btn ${b.primary ? 'primary' : ''} ${b.danger ? 'danger' : ''}`,
      onclick: async () => { const keep = b.onClick ? await b.onClick() : undefined; if (keep !== false) close(); },
    }, b.label));
  }
  const m = h('div', { class: `modal ${wide ? 'wide' : ''}`, role: 'dialog' },
    h('div', { class: 'modal-head' }, h('h3', {}, title), h('button', { class: 'x', onclick: close, title: 'Close' }, '×')),
    h('div', { class: 'modal-body' }, body),
    buttons.length ? foot : null);
  const bg = h('div', { class: 'modal-bg', onmousedown: (e) => { if (e.target === bg) close(); } }, m);
  function onKey(e) {
    if (e.key === 'Escape') close();
    if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA' && buttons.find((b) => b.primary)) {
      e.preventDefault();
      foot.querySelector('.btn.primary')?.click();
    }
  }
  document.addEventListener('keydown', onKey);
  root.append(bg);
  setTimeout(() => m.querySelector('input, select, textarea')?.focus(), 30);
  return { close, el: m };
}

/**
 * Quick, non-blocking text input: a small field next to where the user clicked (no dimmed
 * full-screen dialog). Enter or clicking elsewhere accepts, Esc cancels. Resolves with the
 * trimmed text, or null when cancelled.
 */
export function prompt(title, value = '', label = '', anchor = null) {
  return new Promise((resolve) => {
    const inp = h('input', { type: 'text', value, 'aria-label': title, title: label || title });
    const pop = h('div', { class: 'qpop', role: 'dialog', 'aria-label': title }, h('div', { class: 'qpop-t' }, title), inp,
      h('div', { class: 'qpop-h' }, 'Enter ✓ · Esc ✕'));
    let done = false;
    const finish = (v) => {
      if (done) return;
      done = true;
      document.removeEventListener('pointerdown', outside, true);
      pop.remove();
      resolve(v);
    };
    const outside = (e) => { if (!pop.contains(e.target)) finish(inp.value.trim()); };
    inp.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); finish(inp.value.trim()); } else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); finish(null); }
    });
    document.body.append(pop);
    const r = anchor?.getBoundingClientRect?.();
    const vw = document.documentElement.clientWidth;
    const vh = document.documentElement.clientHeight;
    const x = r ? r.left : (lastPointer?.x ?? vw / 2 - 140);
    const y = r ? r.bottom + 4 : (lastPointer?.y ?? 120) + 8;
    pop.style.left = `${Math.max(8, Math.min(x, vw - pop.offsetWidth - 8))}px`;
    pop.style.top = `${Math.max(8, Math.min(y, vh - pop.offsetHeight - 8))}px`;
    setTimeout(() => { document.addEventListener('pointerdown', outside, true); inp.focus(); inp.select(); }, 0);
  });
}

export function confirm(title, message, okLabel = 'OK') {
  return new Promise((resolve) => {
    let done = false;
    modal({
      title, body: h('p', {}, message),
      buttons: [{ label: 'Cancel' }, { label: okLabel, primary: true, onClick: () => { done = true; resolve(true); } }],
      onClose: () => { if (!done) resolve(false); },
    });
  });
}

/**
 * Keep a floating element (menu, popover) inside the visible window:
 * flips it above its anchor when there is more room there, shifts it
 * horizontally, and caps its height with scrolling when the window is short.
 */
export function fitToViewport(el, anchor, { gap = 4, margin = 8 } = {}) {
  el.style.maxHeight = '';
  el.style.overflowY = '';
  const vw = document.documentElement.clientWidth;
  const vh = document.documentElement.clientHeight;
  const a = anchor ? anchor.getBoundingClientRect() : null;
  const fixed = getComputedStyle(el).position === 'fixed';
  let r = el.getBoundingClientRect();
  if (a) {
    const below = vh - a.bottom - gap - margin;
    const above = a.top - gap - margin;
    const up = r.height > below && above > below;
    const room = Math.max(120, up ? above : below);
    if (r.height > room) { el.style.maxHeight = `${room}px`; el.style.overflowY = 'auto'; }
    r = el.getBoundingClientRect();
    const top = up ? a.top - gap - r.height : a.bottom + gap;
    let left = Math.min(a.left, vw - r.width - margin);
    left = Math.max(margin, left);
    if (fixed) { el.style.top = `${top}px`; el.style.left = `${left}px`; } else {
      const parent = el.offsetParent?.getBoundingClientRect() || { top: 0, left: 0 };
      el.style.top = `${top - parent.top}px`; el.style.left = `${left - parent.left}px`;
    }
  } else {
    if (r.height > vh - 2 * margin) { el.style.maxHeight = `${vh - 2 * margin}px`; el.style.overflowY = 'auto'; r = el.getBoundingClientRect(); }
    el.style.left = `${Math.max(margin, Math.min(r.left, vw - r.width - margin))}px`;
    el.style.top = `${Math.max(margin, Math.min(r.top, vh - r.height - margin))}px`;
  }
}

let ctxEl = null;
export function contextMenu(x, y, items) {
  ctxEl?.remove();
  ctxEl = h('div', { class: 'ctx' }, items.map((it) => (it === '-' ? h('hr') :
    h('button', { onclick: () => { ctxEl.remove(); it.action(); } }, it.label))));
  document.body.append(ctxEl);
  ctxEl.style.left = `${x}px`;
  ctxEl.style.top = `${y}px`;
  const r = ctxEl.getBoundingClientRect();
  const vh = document.documentElement.clientHeight;
  // open upwards from the pointer when it does not fit below
  if (y + r.height > vh - 8 && y - r.height > 8) ctxEl.style.top = `${y - r.height}px`;
  fitToViewport(ctxEl);
  setTimeout(() => document.addEventListener('mousedown', function f(e) {
    if (!ctxEl?.contains(e.target)) { ctxEl?.remove(); document.removeEventListener('mousedown', f); }
  }), 0);
}

export function download(filename, data, mime = 'application/octet-stream') {
  const blob = data instanceof Blob ? data : new Blob([data], { type: mime });
  const a = h('a', { href: URL.createObjectURL(blob), download: filename });
  document.body.append(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
}

export function field(label, input) { return h('div', { class: 'field' }, h('label', {}, label), input); }

export function select(options, value, onchange) {
  const s = h('select', { onchange: (e) => onchange && onchange(e.target.value) },
    options.map(([v, l]) => h('option', { value: v, selected: String(v) === String(value) }, l)));
  return s;
}

export function checkbox(label, checked, onchange) {
  return h('div', { class: 'field check' }, h('label', {},
    h('input', { type: 'checkbox', checked: !!checked, onchange: (e) => onchange(e.target.checked) }), label));
}

export function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

export const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
