// Saving & loading projects: per-user server storage with autosave and
// conflict detection, the project browser, and client-side encryption.
import {
  cryptoAvailable, decryptEnvelope, decryptName, decryptWithKey, encryptJSON, encryptName, encryptWithKey, isEnvelope, newKeyContext, strength,
} from './crypto.js';
import { helpIcon } from './help.js';
import { P, emit, markClean, on, state, writeLocalCopy } from './state.js';
import { api, confirm, download, h, modal, prompt, toast } from './ui.js';

let hooks = { setProject: () => {}, refresh: () => {} };
export function initPersist(hk) { hooks = { ...hooks, ...hk }; }

// ------------------------------------------------------------------ status
const statusEl = () => document.getElementById('save-status');
export function setSaveStatus(kind, text) {
  const el = statusEl();
  if (!el) return;
  el.dataset.kind = kind;
  el.textContent = text || { saving: 'Saving…', saved: `Saved ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`,
    error: 'Not saved', local: 'Not on server', conflict: 'Save conflict' }[kind] || '';
  el.title = kind === 'saved' ? 'All changes are saved on the server' : kind === 'local' ? 'This project is not saved on the server yet (File → Save)' : '';
}

// ------------------------------------------------------------------ password prompt
export function passwordDialog({ title, message, confirmPw = false, okLabel = 'OK', showStrength = false }) {
  return new Promise((resolve) => {
    const pw = h('input', { type: 'password', autocomplete: 'new-password', style: { width: '100%', padding: '6px 8px' } });
    const pw2 = h('input', { type: 'password', autocomplete: 'new-password', style: { width: '100%', padding: '6px 8px' } });
    const meter = h('div', { class: 'pw-meter' }, h('span'));
    const err = h('div', { class: 'auth-err' });
    if (showStrength) pw.addEventListener('input', () => { meter.dataset.s = strength(pw.value); });
    let done = false;
    modal({
      title,
      body: h('div', {}, message ? h('p', { class: 'hint' }, message) : null,
        h('div', { class: 'field' }, h('label', {}, 'Password'), pw), showStrength ? meter : null,
        confirmPw ? h('div', { class: 'field' }, h('label', {}, 'Repeat password'), pw2) : null, err),
      buttons: [{ label: 'Cancel' }, { label: okLabel, primary: true, onClick: () => {
        if (!pw.value) { err.textContent = 'Enter a password.'; return false; }
        if (confirmPw && pw.value.length < 8) { err.textContent = 'Use at least 8 characters.'; return false; }
        if (confirmPw && pw.value !== pw2.value) { err.textContent = 'The passwords do not match.'; return false; }
        done = true; resolve(pw.value); return undefined;
      } }],
      onClose: () => { if (!done) resolve(null); },
    });
  });
}

async function unlock(env, what = 'project') {
  if (!cryptoAvailable()) { toast('Encrypted projects need HTTPS or localhost (browser security requirement).', 'err'); return null; }
  for (;;) {
    const pw = await passwordDialog({ title: `Unlock encrypted ${what}`, message: 'This project is encrypted. It is decrypted here in your browser; the password is never sent to the server.', okLabel: 'Unlock' });
    if (pw === null) return null;
    try { return await decryptEnvelope(env, pw); } catch (e) { toast(e.message, 'err'); }
  }
}

// ------------------------------------------------------------------ saving
let saving = false;
let again = false;
let conflictBlocked = false;
let timer = null;

// Everything stored on the server is encrypted with the account data key (end-to-end).
async function payload() {
  if (!state.dataKey) throw new Error('Your encryption key is not unlocked in this browser.');
  return { data: await encryptWithKey(P(), state.dataKey), name: await encryptName(P().name || 'Untitled project', state.dataKey) };
}

export async function saveToServer({ saveAs = false, silent = false, force = false } = {}) {
  if (!state.username) return;
  if (saving) { again = true; return; }
  saving = true;
  const seq = state.changeSeq;
  try {
    if (!state.serverId || saveAs) {
      let pname = P().name || 'Untitled project';
      if (saveAs || (!silent && pname === 'Untitled project')) {
        pname = await prompt(saveAs ? 'Save a copy as' : 'Save project', saveAs ? `${pname} copy` : pname, 'Project name');
        if (!pname) return;
        P().name = pname;
      }
      setSaveStatus('saving');
      const { data, name } = await payload();
      const r = await api('/api/projects', { name, data });
      state.serverId = r.id;
      state.serverVersion = r.version;
    } else {
      setSaveStatus('saving');
      const { data, name } = await payload();
      const r = await api(`/api/projects/${state.serverId}`, { name, data, baseVersion: state.serverVersion, force }, 'PUT');
      state.serverVersion = r.version;
    }
    conflictBlocked = false;
    if (state.changeSeq === seq) markClean();
    writeLocalCopy();
    setSaveStatus('saved');
    if (!silent) { toast(`Saved “${P().name}” (end-to-end encrypted)`); checkQuota(); }
    hooks.refresh();
  } catch (e) {
    if (e.status === 409) { conflictBlocked = true; setSaveStatus('conflict'); conflictDialog(); }
    else if (e.status === 404 && state.serverId) {
      state.serverId = null; state.serverVersion = null;
      setSaveStatus('local');
      toast('This project was deleted from the server. Save it again to keep it.', 'err');
    } else {
      setSaveStatus('error', e.status === 413 ? 'Quota/size limit' : 'Not saved');
      if (!silent || e.status === 413) toast(`Could not save: ${e.message}`, 'err');
    }
  } finally {
    saving = false;
    if (again) { again = false; scheduleAutosave(); }
  }
}

function conflictDialog() {
  modal({
    title: 'Save conflict',
    body: h('p', {}, 'This project was changed in another browser tab or on another device after you opened it. What do you want to do with your current version?'),
    buttons: [
      { label: 'Keep server version', onClick: () => openServerProject(state.serverId, true) },
      { label: 'Save mine as a copy', onClick: () => { state.serverId = null; saveToServer({ silent: false }); } },
      { label: 'Overwrite server version', primary: true, onClick: () => saveToServer({ force: true }) },
    ],
  });
}

export function scheduleAutosave() {
  clearTimeout(timer);
  if (!state.username || !state.autosaveServer || conflictBlocked) return;
  if (!state.serverId && !P().tables.length) return; // nothing worth saving yet
  timer = setTimeout(() => { if (state.dirty) saveToServer({ silent: true }); }, 2500);
}
on('dirty', () => { if (!state.serverId) setSaveStatus('local'); scheduleAutosave(); });
export async function flushSave() {
  clearTimeout(timer);
  if (state.dirty && state.username && (state.serverId || P().tables.length) && !conflictBlocked) await saveToServer({ silent: true });
}

// ------------------------------------------------------------------ open
export async function openServerProject(id, skipFlush = false) {
  if (!skipFlush) await flushSave();
  const rec = await api(`/api/projects/${encodeURIComponent(id)}`);
  let data;
  try { data = await decryptWithKey(rec.data, state.dataKey); } catch (e) { toast(e.message, 'err'); return false; }
  data.name = (await decryptName(rec.name_ct, state.dataKey)) || data.name || 'Untitled project';
  conflictBlocked = false;
  hooks.setProject(data, { serverId: rec.id, serverVersion: rec.version, encryption: null });
  setSaveStatus('saved', 'Saved');
  toast(`Opened “${data.name}” (decrypted in your browser)`);
  return true;
}

export async function openFile(file) {
  let obj;
  try { obj = JSON.parse(await file.text()); } catch (_) { toast('This is not a valid OpenPrism project file.', 'err'); return; }
  let enc = null;
  if (isEnvelope(obj)) {
    const res = await unlock(obj, 'file');
    if (!res) return;
    obj = res.value;
    enc = res.keyCtx;
  }
  if (!obj || typeof obj !== 'object' || !Array.isArray(obj.tables)) { toast('This file does not contain an OpenPrism project.', 'err'); return; }
  await flushSave();
  conflictBlocked = false;
  hooks.setProject(obj, { serverId: null, serverVersion: null, encryption: enc });
  setSaveStatus('local');
  toast(`Opened ${file.name}${enc ? ' (decrypted locally — it will be saved encrypted with the same password)' : ''}`);
  if (state.autosaveServer) scheduleAutosave();
}

// ------------------------------------------------------------------ download
const fileBase = () => (P().name || 'project').replace(/[\\/:*?"<>|]+/g, '_').slice(0, 80);

export function downloadPlain() {
  download(`${fileBase()}.oprism`, JSON.stringify(P(), null, 1), 'application/json');
}

export async function downloadEncrypted() {
  if (!cryptoAvailable()) { toast('Encryption needs HTTPS or localhost (browser security requirement).', 'err'); return; }
  let ctx = state.encryption;
  if (ctx) {
    const same = await choose('Download encrypted project', 'Encrypt the file with the current project password, or choose a different password for this file?',
      [['same', 'Current password'], ['new', 'New password…']]);
    if (!same) return;
    if (same === 'new') ctx = null;
  }
  if (!ctx) {
    const pw = await passwordDialog({ title: 'Encrypt download', message: 'The file is encrypted in your browser (AES-256-GCM). Without this password it cannot be opened — there is no recovery.', confirmPw: true, showStrength: true, okLabel: 'Encrypt & download' });
    if (!pw) return;
    ctx = await newKeyContext(pw);
  }
  const env = await encryptJSON(P(), ctx);
  download(`${fileBase()}.encrypted.oprism`, JSON.stringify(env), 'application/json');
  toast('Encrypted file downloaded');
}

function choose(title, message, options) {
  return new Promise((resolve) => {
    let done = false;
    modal({ title, body: h('p', {}, message),
      buttons: [{ label: 'Cancel' }, ...options.map(([v, l], i) => ({ label: l, primary: i === 0, onClick: () => { done = true; resolve(v); } }))],
      onClose: () => { if (!done) resolve(null); } });
  });
}

// ------------------------------------------------------------------ quota
let quotaWarned = false;
function quotaBanner(d) {
  if (d.usage < d.warnAt) return null;
  const full = d.usage >= d.quota * 0.95;
  return h('div', { class: `quota-warn ${full ? 'full' : ''}` },
    h('b', {}, full ? 'Your storage is (almost) full. ' : `You have used ${fmtSize(d.usage)} of ${fmtSize(d.quota)}. `),
    'Please offload older projects: download them to your computer (⤓, optionally encrypted), then delete them here. ',
    'You can upload a downloaded project at any time to view or edit it again.', helpIcon('quota'));
}
export async function checkQuota(force = false) {
  if (!state.username || (quotaWarned && !force)) return;
  try {
    const d = await api('/api/projects');
    if (d.usage >= d.warnAt) {
      quotaWarned = true;
      toast(`Storage: ${fmtSize(d.usage)} of ${fmtSize(d.quota)} used — please download and delete old projects (File → My projects).`, d.usage >= d.quota * 0.95 ? 'err' : '');
    }
  } catch (_) { /* ignore */ }
}

// ------------------------------------------------------------------ project browser
const fmtSize = (b) => (b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);

export async function projectBrowser() {
  let data;
  const decorate = async (d) => {
    for (const p of d.projects) {
      const n = await decryptName(p.name_ct, state.dataKey);
      p.name = n ?? '(locked — encrypted with a previous key)';
      p.locked = n === null;
    }
    return d;
  };
  try { data = await decorate(await api('/api/projects')); } catch (e) { toast(e.message, 'err'); return; }
  let filter = '';
  const list = h('div', { class: 'proj-list' });
  const usage = h('div', { class: 'usage' });
  const draw = () => {
    list.innerHTML = '';
    const pct = Math.min(100, (data.usage / data.quota) * 100);
    usage.innerHTML = '';
    const banner = quotaBanner(data);
    if (banner) usage.append(banner);
    usage.append(h('div', { class: `usage-bar ${data.usage >= data.warnAt ? 'warn' : ''}` }, h('span', { style: { width: `${pct}%` } })),
      h('div', { class: 'hint' }, `${data.projects.length} of ${data.maxProjects} projects · ${fmtSize(data.usage)} of ${fmtSize(data.quota)} used`));
    const items = data.projects.filter((p) => p.name.toLowerCase().includes(filter));
    if (!items.length) { list.append(h('div', { class: 'empty', style: { padding: '30px' } }, data.projects.length ? 'No projects match.' : 'You have no saved projects yet. Use File → Save.')); return; }
    list.append(h('table', { class: 'rtable proj-table' },
      h('thead', {}, h('tr', {}, h('th', {}, 'Project'), h('th', {}, 'Modified'), h('th', {}, 'Size'), h('th', {}, ''))),
      h('tbody', {}, items.map((p) => h('tr', { class: p.id === state.serverId ? 'current' : '' },
        h('td', {}, h('a', { href: '#', onclick: async (e) => { e.preventDefault(); if (await openServerProject(p.id)) m.close(); } },
          p.locked ? '⚠ ' : '', p.name), p.id === state.serverId ? h('span', { class: 'tag', style: { marginLeft: '6px' } }, 'open') : null),
        h('td', {}, new Date(p.updated * 1000).toLocaleString()),
        h('td', { class: 'num' }, fmtSize(p.size)),
        h('td', { class: 'proj-actions' },
          h('button', { class: 'btn small', onclick: async () => { if (await openServerProject(p.id)) m.close(); } }, 'Open'),
          h('button', { class: 'btn small', title: 'Rename', onclick: () => rename(p) }, 'Rename'),
          h('button', { class: 'btn small', title: 'Duplicate', onclick: () => dup(p) }, 'Copy'),
          h('button', { class: 'btn small', title: 'Download the stored file (stays encrypted if it is encrypted)', onclick: () => dl(p) }, '⤓'),
          h('button', { class: 'btn small danger', title: 'Delete permanently', onclick: () => del(p) }, 'Delete')))))));
  };
  const reload = async () => { data = await decorate(await api('/api/projects')); draw(); };
  async function rename(p) {
    const v = await prompt('Rename project', p.name);
    if (!v) return;
    try {
      const r = await api(`/api/projects/${p.id}`, { name: await encryptName(v, state.dataKey) }, 'PUT');
      if (p.id === state.serverId) { P().name = v; state.serverVersion = r.version; hooks.refresh(); }
      await reload();
    } catch (e) { toast(e.message, 'err'); }
  }
  async function dup(p) { try { await api(`/api/projects/${p.id}/duplicate`, { name: await encryptName(`${p.name} copy`, state.dataKey) }); await reload(); } catch (e) { toast(e.message, 'err'); } }
  async function dl(p) {
    // decrypt locally, then save as a portable file (plain, or password-encrypted via File → Download encrypted)
    const rec = await api(`/api/projects/${p.id}`);
    let proj;
    try { proj = await decryptWithKey(rec.data, state.dataKey); } catch (e) { toast(e.message, 'err'); return; }
    proj.name = p.name;
    const choice = await choose('Download project', `Download “${p.name}” as a plain file, or encrypted with a password of your choice?`, [['enc', 'Encrypted file…'], ['plain', 'Plain file']]);
    if (choice === 'plain') download(`${p.name.replace(/[\\/:*?"<>|]+/g, '_')}.oprism`, JSON.stringify(proj), 'application/json');
    else if (choice === 'enc') {
      const pw = await passwordDialog({ title: 'Encrypt download', message: 'Choose a password for this file (needed to open it again).', confirmPw: true, showStrength: true, okLabel: 'Encrypt & download' });
      if (!pw) return;
      download(`${p.name.replace(/[\\/:*?"<>|]+/g, '_')}.encrypted.oprism`, JSON.stringify(await encryptJSON(proj, await newKeyContext(pw))), 'application/json');
    }
  }
  async function del(p) {
    if (!(await confirm('Delete project', `Permanently delete “${p.name}” from the server? This cannot be undone.`, 'Delete'))) return;
    try {
      await api(`/api/projects/${p.id}`, undefined, 'DELETE');
      if (p.id === state.serverId) { state.serverId = null; state.serverVersion = null; setSaveStatus('local'); }
      await reload();
      toast('Project deleted');
    } catch (e) { toast(e.message, 'err'); }
  }
  const search = h('input', { type: 'search', placeholder: 'Search projects…', style: { flex: 1, padding: '6px 8px' }, oninput: (e) => { filter = e.target.value.toLowerCase(); draw(); } });
  const m = modal({
    title: 'My projects (end-to-end encrypted)', wide: true,
    body: h('div', {},
      h('div', { style: { display: 'flex', gap: '8px', marginBottom: '10px', alignItems: 'center' } }, search,
        h('button', { class: 'btn', onclick: () => { m.close(); hooks.newProject(); } }, 'New project'),
        h('button', { class: 'btn', onclick: () => { m.close(); document.getElementById('file-open').click(); } }, 'Upload project file…'),
        helpIcon('project-browser')),
      usage, list),
    buttons: [{ label: 'Close', primary: true }],
  });
  draw();
}
