// OpenPrism administration console (served only on the localhost admin port).
// First-run setup, users and their limits, one-time passwords, registration
// policy, administrators, backups and the audit log. Administrators manage
// accounts but can never open or decrypt user projects (end-to-end encrypted).
import { confirm, h, modal, prompt, toast } from './ui.js';

const MB = 1024 * 1024;
const fmtMB = (b) => `${(b / MB).toFixed(b < 10 * MB ? 1 : 0)} MB`;
const fmtDate = (t) => (t ? new Date(t * 1000).toLocaleString() : '—');
const LIMITS = [['quota_mb', 'Storage MB'], ['project_mb', 'Max project MB'], ['mem_mb', 'RAM MB / analysis'], ['cpu_s', 'CPU s / analysis'], ['rate_per_min', 'Analyses / min']];
const main = document.getElementById('admin-main');

async function api(path, body, method) {
  const opts = { method: method || (body !== undefined ? 'POST' : 'GET'), headers: {}, credentials: 'same-origin', cache: 'no-store' };
  if (opts.method !== 'GET') opts.headers['X-OpenPrism-Admin'] = '1';
  if (body !== undefined) { opts.body = JSON.stringify(body); opts.headers['Content-Type'] = 'application/json'; }
  const r = await fetch(path, opts);
  let data = null;
  try { data = await r.json(); } catch (_) { /* ignore */ }
  if (r.status === 401 && path !== '/api/admin/login') { boot(); throw new Error('Please sign in.'); }
  if (!r.ok) throw new Error((data && data.error) || `${r.status} ${r.statusText}`);
  return data;
}

function genPassword() {
  const A = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  const b = crypto.getRandomValues(new Uint8Array(15));
  const s = Array.from(b, (x) => A[x % A.length]).join('');
  return `${s.slice(0, 5)}-${s.slice(5, 10)}-${s.slice(10)}`;
}

const pw = () => h('input', { type: 'password', autocomplete: 'new-password' });
const field = (label, input) => h('div', { class: 'field' }, h('label', {}, label), input);

// ------------------------------------------------------------ first-run setup
function setupWizard() {
  const user = h('input', { type: 'text', value: 'admin', autocomplete: 'username' });
  const p1 = pw(); const p2 = pw();
  const reg = h('select', {}, h('option', { value: '1' }, 'Users may create their own accounts (self-registration)'), h('option', { value: '0' }, 'Only administrators create accounts'));
  const lim = {};
  const err = h('div', { class: 'auth-err' });
  main.innerHTML = '';
  main.append(h('div', { class: 'admin-card setup-card' },
    h('h2', { style: { marginTop: 0 } }, 'Welcome — set up this OpenPrism server'),
    h('p', {}, 'This is the first start. Create the administrator account and choose how users get accounts. Until this is done, the application refuses all users.'),
    h('p', { class: 'hint' }, 'This console is reachable only from this computer. Administrators manage accounts and limits but can never open or decrypt users’ projects (end-to-end encryption).'),
    h('h3', {}, '1. Administrator'),
    field('Administrator name', user), field('Password (min. 8 characters)', p1), field('Repeat password', p2),
    h('h3', {}, '2. Accounts'),
    field('Registration', reg),
    h('h3', {}, '3. Default limits per user'),
    h('div', { class: 'admin-grid' }, LIMITS.map(([k, l]) => h('label', { class: 'stat-tile' }, h('span', { class: 'hint' }, l),
      lim[k] = h('input', { type: 'number', value: { quota_mb: 256, project_mb: 25, mem_mb: 1024, cpu_s: 60, rate_per_min: 600 }[k], style: { width: '100%' } })))),
    err,
    h('button', { class: 'btn primary', style: { marginTop: '14px', padding: '9px 18px' }, onclick: async () => {
      err.textContent = '';
      if (p1.value !== p2.value) { err.textContent = 'The passwords do not match.'; return; }
      try {
        await api('/api/setup', { username: user.value.trim(), password: p1.value, allowRegistration: reg.value === '1',
          limits: Object.fromEntries(Object.entries(lim).map(([k, el]) => [k, +el.value])) });
        toast('Server is ready — users can now sign in.');
        boot();
      } catch (e) { err.textContent = e.message; }
    } }, 'Complete setup')));
}

function loginForm() {
  const user = h('input', { type: 'text', autocomplete: 'username' });
  const p = h('input', { type: 'password', autocomplete: 'current-password' });
  const err = h('div', { class: 'auth-err' });
  main.innerHTML = '';
  main.append(h('div', { class: 'admin-card setup-card' }, h('h2', { style: { marginTop: 0 } }, 'Administrator sign-in'),
    h('form', { onsubmit: async (e) => {
      e.preventDefault();
      try { await api('/api/admin/login', { username: user.value.trim(), password: p.value }); boot(); } catch (ex) { err.textContent = ex.message; }
    } }, field('Name', user), field('Password', p), err, h('button', { class: 'btn primary', type: 'submit' }, 'Sign in')),
    h('p', { class: 'hint' }, 'Forgot the administrator password? On the server run:  python run.py admin reset-admin <name>')));
  setTimeout(() => user.focus(), 30);
}

// ------------------------------------------------------------------ console
let tab = 'users';
let data = null;

async function load() { data = await api('/api/admin/overview'); draw(); }

function draw() {
  main.innerHTML = '';
  const tabs = [['users', `Users (${data.users.length})`], ['requests', `Reset requests (${data.requests.length})`], ['settings', 'Server settings'], ['admins', 'Administrators'], ['log', 'Audit log']];
  main.append(
    h('div', { class: 'admin-grid' },
      tile('Users', data.users.length), tile('Stored (encrypted)', fmtMB(data.totalUsage)), tile('Database', fmtMB(data.dbSize)),
      tile('Self-registration', data.allowRegistration ? 'open' : 'admins only'), tile('Open reset requests', data.requests.length)),
    h('div', { class: 'admin-tabs' }, tabs.map(([k, l]) => h('button', { class: tab === k ? 'on' : '', onclick: () => { tab = k; draw(); } }, l))));
  ({ users, requests, settings, admins, log })[tab]();
}
const tile = (l, v) => h('div', { class: 'stat-tile' }, h('span', { class: 'hint' }, l), h('b', {}, v));

function users() {
  let filter = '';
  const box = h('div', { style: { overflowX: 'auto' } });
  const drawTable = () => {
    box.innerHTML = '';
    box.append(h('table', { class: 'rtable admin-table', style: { width: '100%' } },
      h('thead', {}, h('tr', {}, h('th', {}, 'User'), h('th', {}, 'Last sign-in'), h('th', {}, 'Projects'), h('th', {}, 'Used'),
        ...LIMITS.map(([, l]) => h('th', {}, l)), h('th', {}, ''))),
      h('tbody', {}, data.users.filter((u) => u.username.toLowerCase().includes(filter)).map((u) => {
        const inputs = {};
        const pct = u.usage / (u.limits.quota_mb * MB);
        return h('tr', {},
          h('td', {}, u.username, u.disabled ? h('span', { class: 'badge off' }, 'disabled') : null,
            u.must_change ? h('span', { class: 'badge' }, 'one-time pw') : null,
            u.key_state === 'reset' ? h('span', { class: 'badge', title: 'Waiting for the user to enter the recovery key' }, 'key locked') : null),
          h('td', {}, fmtDate(u.last_login)), h('td', { class: 'num' }, u.projects),
          h('td', { class: 'num', style: { color: pct > 0.9 ? 'var(--danger)' : pct > 0.5 ? 'var(--warn)' : '' } }, `${fmtMB(u.usage)} (${Math.round(pct * 100)}%)`),
          ...LIMITS.map(([k]) => h('td', {}, inputs[k] = h('input', { type: 'number', value: u.limits[k], min: data.bounds[k][0], max: data.bounds[k][1] }))),
          h('td', { class: 'proj-actions' },
            h('button', { class: 'btn small', onclick: async () => {
              try { await api(`/api/admin/users/${u.id}`, { limits: Object.fromEntries(Object.entries(inputs).map(([k, el]) => [k, +el.value])) }, 'PUT'); toast(`Limits saved for ${u.username}`); load(); } catch (e) { toast(e.message, 'err'); }
            } }, 'Save'),
            h('button', { class: 'btn small', onclick: () => setOtp(u) }, 'One-time pw'),
            h('button', { class: 'btn small', onclick: () => upd(u, { disabled: !u.disabled }) }, u.disabled ? 'Enable' : 'Disable'),
            h('button', { class: 'btn small danger', onclick: () => del(u) }, 'Delete')));
      }))));
  };
  main.append(h('div', { class: 'admin-card' },
    h('div', { style: { display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap' } },
      h('h3', { style: { margin: 0 } }, 'Users'),
      h('input', { type: 'search', placeholder: 'Filter…', oninput: (e) => { filter = e.target.value.toLowerCase(); drawTable(); } }),
      h('button', { class: 'btn small primary', onclick: createUser }, '+ Create user')),
    box,
    h('p', { class: 'hint' }, 'RAM and CPU limits are enforced by the operating system for each analysis. Users are warned at 50% of their storage.')));
  drawTable();
}

async function upd(u, patch) { try { await api(`/api/admin/users/${u.id}`, patch, 'PUT'); load(); } catch (e) { toast(e.message, 'err'); } }

async function del(u) {
  if (!(await confirm('Delete account', `Permanently delete the account “${u.username}” and all ${u.projects} of its projects? This cannot be undone.`, 'Delete account'))) return;
  try { await api(`/api/admin/users/${u.id}`, undefined, 'DELETE'); toast('Account deleted'); load(); } catch (e) { toast(e.message, 'err'); }
}

function otpDialog(title, intro, onSubmit) {
  const p = h('input', { type: 'text', value: genPassword(), spellcheck: 'false' });
  modal({ title, body: h('div', {}, h('p', {}, intro), field('One-time password', h('div', { style: { display: 'flex', gap: '6px' } }, p,
    h('button', { class: 'btn small', onclick: () => { p.value = genPassword(); } }, 'Generate'))),
  h('p', { class: 'hint' }, 'Give it to the user through a trusted channel. The user must choose a new password at the first sign-in.')),
  buttons: [{ label: 'Cancel' }, { label: 'Set', primary: true, onClick: async () => {
    try { await onSubmit(p.value); navigator.clipboard?.writeText(p.value).catch(() => {}); toast('Done — one-time password copied to the clipboard'); load(); } catch (e) { toast(e.message, 'err'); return false; }
    return undefined;
  } }] });
}

function setOtp(u) {
  otpDialog(`One-time password for ${u.username}`,
    'Signing in will work again with this password. Because projects are end-to-end encrypted, the user needs their RECOVERY KEY to unlock existing projects; without it they start with a new, empty key.',
    (v) => api(`/api/admin/users/${u.id}/otp`, { password: v }));
}

async function createUser() {
  const name = await prompt('Create user', '', 'User ID (3-32 letters, digits, . _ -)');
  if (!name) return;
  otpDialog(`New account “${name}”`, 'The user signs in with this one-time password, chooses a personal password, and their encryption keys are created in their browser.',
    (v) => api('/api/admin/users', { username: name, password: v }));
}

function requests() {
  main.append(h('div', { class: 'admin-card' }, h('h3', {}, 'Password reset requests'),
    data.requests.length ? h('table', { class: 'rtable admin-table' },
      h('thead', {}, h('tr', {}, h('th', {}, 'User'), h('th', {}, 'Requested'), h('th', {}, 'Message'), h('th', {}, ''))),
      h('tbody', {}, data.requests.map((r) => h('tr', {}, h('td', {}, r.username), h('td', {}, fmtDate(r.created)), h('td', {}, r.note || ''),
        h('td', { class: 'proj-actions' },
          h('button', { class: 'btn small primary', onclick: () => setOtp({ id: r.user_id, username: r.username }) }, 'Set one-time password'),
          h('button', { class: 'btn small', onclick: async () => { await api(`/api/admin/requests/${r.id}/dismiss`, {}); load(); } }, 'Dismiss')))))) : h('p', { class: 'hint' }, 'No open requests.'),
    h('p', { class: 'hint' }, 'Verify the person’s identity before issuing a password. Requests for unknown user IDs are silently discarded.')));
}

function settings() {
  const reg = h('input', { type: 'checkbox', checked: data.allowRegistration });
  const share = h('input', { type: 'checkbox', checked: data.allowSharing !== false });
  const annText = h('textarea', { rows: 3, maxlength: 2000, style: { width: '100%', boxSizing: 'border-box' }, placeholder: 'Message to all users (plain text). Leave empty for none.' });
  annText.value = data.announcement?.text || '';
  const annLevel = h('select', {}, [['info', 'Information'], ['warning', 'Warning'], ['urgent', 'Urgent (cannot be hidden)']].map(([v, l]) => h('option', { value: v, selected: (data.announcement?.level || 'info') === v }, l)));
  const lim = {};
  main.append(h('div', { class: 'admin-card' }, h('h3', {}, 'Registration'),
    h('label', { class: 'check-line' }, reg, 'Allow users to create their own accounts (otherwise only administrators create accounts)'),
    h('button', { class: 'btn primary', onclick: async () => { await api('/api/admin/settings', { allowRegistration: reg.checked }, 'PUT'); toast('Saved'); load(); } }, 'Save')),
  h('div', { class: 'admin-card' }, h('h3', {}, 'Sharing between users'),
    h('p', { class: 'hint' }, `Users can send each other end-to-end encrypted copies of projects. The server only stores ciphertext and cannot read them. ${data.pendingShares} share(s) are waiting to be accepted.`),
    h('label', { class: 'check-line' }, share, 'Allow users to share projects with each other'),
    h('button', { class: 'btn primary', onclick: async () => { await api('/api/admin/settings', { allowSharing: share.checked }, 'PUT'); toast('Saved'); load(); } }, 'Save')),
  h('div', { class: 'admin-card' }, h('h3', {}, 'Announcement to all users'),
    h('p', { class: 'hint' }, 'Shown on the sign-in screen and as a banner at the top of the app (open apps pick it up within a few minutes). '
      + 'Use it for maintenance, updates or data deletion notices, e.g. “On 1 March the server is reset: download your projects (File → Download project file) before then.” '
      + 'Info and warning messages can be hidden by each user until you change the text; urgent messages cannot be hidden.'),
    annText, h('div', { style: { display: 'flex', gap: '8px', alignItems: 'center', marginTop: '8px', flexWrap: 'wrap' } },
      h('label', {}, 'Level '), annLevel,
      h('button', { class: 'btn primary', onclick: async () => { await api('/api/admin/settings', { announcement: { text: annText.value, level: annLevel.value } }, 'PUT'); toast(annText.value.trim() ? 'Announcement published' : 'Announcement removed'); load(); } }, 'Publish'),
      h('button', { class: 'btn', onclick: async () => { await api('/api/admin/settings', { announcement: { text: '' } }, 'PUT'); toast('Announcement removed'); load(); } }, 'Remove'),
      h('span', { class: 'hint' }, data.announcement ? `Live since ${new Date(data.announcement.updated * 1000).toLocaleString()}` : 'No announcement is shown.'))),
  h('div', { class: 'admin-card' }, h('h3', {}, 'Default limits for new accounts'),
    h('div', { class: 'admin-grid' }, LIMITS.map(([k, l]) => h('label', { class: 'stat-tile' }, h('span', { class: 'hint' }, l),
      lim[k] = h('input', { type: 'number', value: data.defaults[k], min: data.bounds[k][0], max: data.bounds[k][1], style: { width: '100%' } })))),
    h('button', { class: 'btn primary', style: { marginTop: '10px' }, onclick: async () => {
      await api('/api/admin/settings', { defaults: Object.fromEntries(Object.entries(lim).map(([k, el]) => [k, +el.value])) }, 'PUT'); toast('Saved'); load();
    } }, 'Save defaults')),
  h('div', { class: 'admin-card' }, h('h3', {}, 'Backup'),
    h('p', { class: 'hint' }, 'Downloads a consistent copy of the database. It contains only password hashes and end-to-end encrypted projects — still keep it private.'),
    h('a', { class: 'btn', href: '/api/admin/backup' }, '⤓ Download database backup')));
}

function admins() {
  const name = h('input', { type: 'text' }); const p1 = pw();
  const old = pw(); const n1 = pw(); const n2 = pw();
  main.append(h('div', { class: 'admin-card' }, h('h3', {}, 'Administrators'),
    h('table', { class: 'rtable admin-table' }, h('tbody', {}, data.admins.map((a) => h('tr', {}, h('td', {}, a.username), h('td', {}, `last sign-in ${fmtDate(a.last_login)}`),
      h('td', {}, h('button', { class: 'btn small danger', onclick: async () => {
        if (!(await confirm('Remove administrator', `Remove administrator “${a.username}”?`, 'Remove'))) return;
        try { await api(`/api/admin/admins/${a.id}`, undefined, 'DELETE'); load(); } catch (e) { toast(e.message, 'err'); }
      } }, 'Remove')))))),
    h('h4', {}, 'Add administrator'), field('Name', name), field('Password', p1),
    h('button', { class: 'btn', onclick: async () => { try { await api('/api/admin/admins', { username: name.value.trim(), password: p1.value }); toast('Administrator added'); load(); } catch (e) { toast(e.message, 'err'); } } }, 'Add')),
  h('div', { class: 'admin-card' }, h('h3', {}, 'Change my password'), field('Current', old), field('New', n1), field('Repeat new', n2),
    h('button', { class: 'btn', onclick: async () => {
      if (n1.value !== n2.value) { toast('Passwords do not match', 'err'); return; }
      try { await api('/api/admin/password', { old: old.value, new: n1.value }); toast('Password changed'); old.value = n1.value = n2.value = ''; } catch (e) { toast(e.message, 'err'); }
    } }, 'Change password')));
}

function log() {
  main.append(h('div', { class: 'admin-card' }, h('h3', {}, 'Audit log'),
    h('table', { class: 'rtable admin-table' }, h('tbody', {}, data.log.map((l) => h('tr', {}, h('td', {}, fmtDate(l.ts)), h('td', {}, l.admin), h('td', {}, l.action), h('td', {}, l.target || '')))))));
}

async function boot() {
  let st;
  try { st = await api('/api/setup/status'); } catch (e) { main.textContent = e.message; return; }
  document.getElementById('admin-user').textContent = st.username ? `Signed in as ${st.username}` : '';
  document.getElementById('admin-logout').hidden = !st.auth;
  if (!st.setup) return setupWizard();
  if (!st.auth) return loginForm();
  return load();
}
document.getElementById('admin-logout').addEventListener('click', async () => { await api('/api/admin/logout', {}); boot(); });
boot();
