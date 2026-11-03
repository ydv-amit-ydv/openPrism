// Calculation activity: a live "running" indicator and a log of past calculations,
// so users always see that work is going on and how long it took.
//
// Every server calculation (analyses, imports, exports, conversions, power) and
// every local calculation (graph summaries in the browser) is recorded with its
// duration in the browser and — for server work — the server's own wall-clock and
// CPU time (X-OpenPrism-Compute header). Only labels and timings are kept, never data.
import { h } from './ui.js';

const MAX = 300;
const KEY = 'openprism.activityLog';
const running = new Map();
let log = [];
let seq = 0;
const listeners = new Set();
try { log = JSON.parse(sessionStorage.getItem(KEY) || '[]'); if (!Array.isArray(log)) log = []; } catch (_) { log = []; }

function notify() { listeners.forEach((fn) => { try { fn(); } catch (_) { /* ignore */ } }); }
function persist() { try { sessionStorage.setItem(KEY, JSON.stringify(log.slice(-MAX))); } catch (_) { /* ignore */ } }

export function onActivity(fn) { listeners.add(fn); return () => listeners.delete(fn); }
export const runningJobs = () => [...running.values()];
export const activityLog = () => log;

/** Start a job; returns finish(status, info) to call when it ends. */
export function startJob(label, kind = 'server') {
  const id = ++seq;
  const job = { id, label, kind, start: performance.now(), at: Date.now() };
  running.set(id, job);
  notify();
  let ended = false;
  return (status = 'ok', info = {}) => {
    if (ended) return;
    ended = true;
    running.delete(id);
    log.push({ label, kind, at: job.at, ms: Math.round((performance.now() - job.start) * 10) / 10, status, ...info });
    if (log.length > MAX) log = log.slice(-MAX);
    persist();
    notify();
  };
}

/** Parse the server's "wall=…;cpu=…;peak=…" timing header. */
export function serverTiming(resp) {
  const v = resp?.headers?.get?.('X-OpenPrism-Compute');
  if (!v) return {};
  const o = {};
  for (const part of v.split(';')) {
    const [k, x] = part.split('=');
    if (k && x) o[k === 'wall' ? 'serverMs' : k === 'cpu' ? 'cpuMs' : 'peakMb'] = k === 'peak' ? +x : Math.round(+x * 10000) / 10;
  }
  return o;
}

/** Run a local (browser) computation and log it. */
export function localJob(label, fn) {
  const done = startJob(label, 'browser');
  try { const r = fn(); done('ok'); return r; } catch (e) { done('error', { error: e.message }); throw e; }
}

export function clearLog() { log = []; persist(); notify(); }

// ---------------------------------------------------------------- UI
const fmtMs = (ms) => (ms == null ? '' : ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(2)} s`);

/** Top-bar indicator: idle / spinning with the current task and elapsed time. */
export function mountIndicator(el, openPanel) {
  let timer = null;
  const draw = () => {
    const jobs = runningJobs();
    el.classList.toggle('busy', jobs.length > 0);
    el.innerHTML = '';
    if (jobs.length) {
      const j = jobs[0];
      const sec = ((performance.now() - j.start) / 1000).toFixed(1);
      el.append(h('span', { class: 'act-spin', 'aria-hidden': 'true' }), h('span', { class: 'act-text' }, `${j.kind === 'browser' ? 'Drawing' : 'Computing'}: ${j.label} · ${sec} s${jobs.length > 1 ? ` (+${jobs.length - 1})` : ''}`));
      el.title = jobs.map((x) => x.label).join('\n');
      if (!timer) timer = setInterval(draw, 100);
    } else {
      if (timer) { clearInterval(timer); timer = null; }
      const n = log.length;
      const last = log[log.length - 1];
      el.append(h('span', { class: 'act-idle' }, '⚙'), h('span', { class: 'act-text' }, n ? `Idle · last ${fmtMs(last.ms)}` : 'Idle'));
      el.title = 'Calculation activity: click for the log of recent calculations';
    }
  };
  el.addEventListener('click', openPanel);
  onActivity(draw);
  draw();
}

export function activityPanel(modal) {
  const body = h('div');
  const draw = () => {
    body.innerHTML = '';
    const jobs = runningJobs();
    const done = [...log].reverse();
    const server = done.filter((x) => x.kind === 'server' && x.status === 'ok');
    const tot = (k) => server.reduce((a, x) => a + (x[k] || 0), 0);
    body.append(h('div', { class: 'act-summary' },
      h('div', {}, h('b', {}, jobs.length), ' running'),
      h('div', {}, h('b', {}, done.length), ' finished this session'),
      h('div', {}, 'Server CPU ', h('b', {}, fmtMs(tot('cpuMs')))),
      h('div', {}, 'Server time ', h('b', {}, fmtMs(tot('serverMs')))),
      h('div', {}, 'Failed ', h('b', {}, done.filter((x) => x.status !== 'ok').length))));
    if (jobs.length) {
      body.append(h('h4', {}, 'Running now'));
      for (const j of jobs) body.append(h('div', { class: 'act-run' }, h('span', { class: 'act-spin' }), `${j.label} — ${((performance.now() - j.start) / 1000).toFixed(1)} s`));
    }
    body.append(h('h4', {}, 'Recent calculations'));
    if (!done.length) { body.append(h('p', { class: 'hint' }, 'Nothing yet. Analyses, graphs, imports and exports appear here with their timing.')); return; }
    body.append(h('div', { class: 'act-wrap' }, h('table', { class: 'rtable act-table' },
      h('thead', {}, h('tr', {}, ['Time', 'Task', 'Where', 'Total', 'Server', 'CPU', 'Status'].map((c) => h('th', {}, c)))),
      h('tbody', {}, done.slice(0, 200).map((x) => h('tr', { class: x.status === 'ok' ? '' : 'bad' },
        h('td', {}, new Date(x.at).toLocaleTimeString()), h('td', {}, x.label), h('td', {}, x.kind === 'browser' ? 'browser' : 'server'),
        h('td', { class: 'num' }, fmtMs(x.ms)), h('td', { class: 'num' }, fmtMs(x.serverMs)), h('td', { class: 'num' }, fmtMs(x.cpuMs)),
        h('td', {}, x.status === 'ok' ? '✓' : `✗ ${x.error || ''}`)))))));
    body.append(h('p', { class: 'hint' }, 'Total = time you waited (network + queue + calculation). Server = time in the isolated calculation worker; CPU = processor time it used. Only names and timings are logged — never your data. The log is kept for this browser tab.'));
  };
  draw();
  const off = onActivity(draw);
  const tick = setInterval(() => { if (runningJobs().length) draw(); }, 250);
  modal({ title: 'Calculation activity', wide: true, body, onClose: () => { off(); clearInterval(tick); },
    buttons: [{ label: 'Clear log', onClick: () => { clearLog(); return false; } }, { label: 'Close', primary: true }] });
}
