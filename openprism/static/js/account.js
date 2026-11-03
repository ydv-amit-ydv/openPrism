// Sign-in, registration and account management with end-to-end encryption.
// The password never leaves the browser: it is turned into an authentication key
// (sent to the server) and a key-encryption key (kept here) that unlocks the
// user's data key. See crypto.js and the manual (Accounts & privacy).
import {
  clearDataKeys, cryptoAvailable, deriveAccountKeys, loadDataKey, newDataKey, newRecoveryKey, randomSaltB64, storeDataKey,
  strength, toNonExtractable, unwrapDataKey, unwrapWithRecovery, wrapDataKey, wrapWithRecovery,
} from './crypto.js';
import { helpIcon, openManual } from './help.js';
import { clearLocalData, state } from './state.js';
import { announcementBox } from './announce.js';
import { api, download, h, modal, toast } from './ui.js';

const ITER = 600000;

function card(...kids) {
  document.getElementById('auth-root')?.remove();
  const root = h('div', { id: 'auth-root', class: 'auth-screen' }, h('div', { class: 'auth-card', role: 'dialog' }, ...kids));
  document.body.append(root);
  return root;
}
const brand = () => h('div', { class: 'auth-brand' },
  h('span', { html: '<svg viewBox="0 0 32 32" width="34" height="34"><path d="M16 3 29 27H3z" fill="#2f6fdb"/><path d="M16 3 22 27H10z" fill="#89b4ff"/></svg>' }),
  h('div', {}, h('b', {}, 'OpenPrism'), h('div', { class: 'hint', style: { margin: 0 } }, 'Scientific graphing & statistics · end-to-end encrypted')));
const pwInput = (ac = 'current-password') => h('input', { type: 'password', autocomplete: ac, maxlength: 256 });

function meterFor(input) {
  const m = h('div', { class: 'pw-meter' }, h('span'));
  input.addEventListener('input', () => { m.dataset.s = strength(input.value); });
  return m;
}

/** Show the recovery key once and make the user confirm they stored it. */
function showRecoveryKey(username, rk, intro) {
  return new Promise((resolve) => {
    const ok = h('input', { type: 'checkbox' });
    const btn = h('button', { class: 'btn primary', disabled: true, style: { width: '100%', padding: '9px' }, onclick: () => resolve() }, 'Continue');
    ok.addEventListener('change', () => { btn.disabled = !ok.checked; });
    card(brand(),
      h('h3', { style: { margin: '4px 0' } }, 'Your recovery key'),
      h('p', { class: 'hint' }, intro || 'Your projects are encrypted with a key that only you can unlock. If you forget your password, the administrator can let you sign in again, but only this recovery key can unlock your existing projects. Nobody — not even the administrator — can recover them without it.'),
      h('div', { class: 'otp-box' }, rk),
      h('div', { style: { display: 'flex', gap: '6px', margin: '10px 0' } },
        h('button', { class: 'btn small', type: 'button', onclick: () => { navigator.clipboard?.writeText(rk); toast('Copied'); } }, 'Copy'),
        h('button', { class: 'btn small', type: 'button', onclick: () => download(`openprism-recovery-key-${username}.txt`, `OpenPrism recovery key for user ${username}\n\n${rk}\n\nKeep this safe and private. It unlocks your encrypted projects if you forget your password.\n`, 'text/plain') }, 'Download as text file'),
        h('button', { class: 'btn small', type: 'button', onclick: () => window.print() }, 'Print')),
      h('label', { class: 'check-line' }, ok, 'I have stored my recovery key in a safe place'),
      btn);
  });
}

async function finishUnlock(username, dataKey) {
  const k = await toNonExtractable(dataKey);
  state.dataKey = k;
  await storeDataKey(username, k);
}

/** Registration: everything cryptographic happens here in the browser. */
async function doRegister(username, password) {
  const salt = randomSaltB64();
  const { kek, auth } = await deriveAccountKeys(password, salt, ITER);
  const dataKey = await newDataKey();
  const rk = newRecoveryKey();
  const wrappedKey = await wrapDataKey(dataKey, kek);
  const recoveryKey = await wrapWithRecovery(dataKey, rk);
  await showRecoveryKey(username, rk);
  const me = await api('/api/auth/register', { username, auth, salt, iter: ITER, wrappedKey, recoveryKey });
  await finishUnlock(me.username, dataKey);
  return me;
}

async function doLogin(username, password) {
  const kdf = await api(`/api/auth/kdf?username=${encodeURIComponent(username)}`);
  const { kek, auth } = await deriveAccountKeys(password, kdf.salt, kdf.iter);
  const me = await api('/api/auth/login', { username, auth });
  if (me.mustChange) {
    await completeReset(me, auth);
  } else {
    await finishUnlock(me.username, await unwrapDataKey(me.keys.wrappedKey, kek, true));
  }
  return me;
}

/** After an administrator-issued one-time password: choose a new password and
 *  (re)establish the data key — from the recovery key, or a brand-new key. */
function completeReset(me, otpAuth) {
  return new Promise((resolve) => {
    const fresh = me.keys.keyState === 'none';
    const pw = pwInput('new-password'); const pw2 = pwInput('new-password');
    const rec = h('input', { type: 'text', placeholder: 'XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX', spellcheck: 'false', autocomplete: 'off' });
    const err = h('div', { class: 'auth-err' });
    const btn = h('button', { class: 'btn primary', type: 'submit', style: { width: '100%', padding: '9px' } }, 'Set password');
    card(brand(),
      h('h3', { style: { margin: '4px 0' } }, 'Choose your new password'),
      h('p', { class: 'hint' }, fresh ? 'Your administrator created this account with a one-time password. Choose your own password; your encryption keys are created now, in this browser.'
        : 'You signed in with a one-time password from the administrator. Choose a new password. To keep access to your existing projects, enter your recovery key.'),
      h('form', { onsubmit: async (e) => {
        e.preventDefault();
        err.textContent = '';
        if (pw.value.length < 8) { err.textContent = 'Use at least 8 characters.'; return; }
        if (pw.value !== pw2.value) { err.textContent = 'The passwords do not match.'; return; }
        btn.disabled = true;
        try {
          let dataKey; let newRk = null;
          if (!fresh && rec.value.trim()) {
            dataKey = await unwrapWithRecovery(me.keys.recoveryKey, rec.value.trim());
          } else {
            if (!fresh && !confirm('Without your recovery key, a NEW encryption key is created and your existing projects can no longer be opened. Continue?')) { btn.disabled = false; return; }
            dataKey = await newDataKey();
            newRk = newRecoveryKey();
          }
          const salt = randomSaltB64();
          const { kek, auth } = await deriveAccountKeys(pw.value, salt, ITER);
          const body = { oldAuth: otpAuth, newAuth: auth, salt, wrappedKey: await wrapDataKey(dataKey, kek) };
          if (newRk) {
            body.recoveryKey = await wrapWithRecovery(dataKey, newRk);
            await showRecoveryKey(me.username, newRk);
          }
          await api('/api/auth/password', body);
          await finishUnlock(me.username, dataKey);
          document.getElementById('auth-root')?.remove();
          toast('Password set. Welcome!');
          resolve();
        } catch (ex) { err.textContent = ex.message; btn.disabled = false; }
      } },
      h('label', {}, 'New password', pw), meterFor(pw), h('label', {}, 'Repeat new password', pw2),
      fresh ? null : h('label', {}, 'Recovery key (to keep your existing projects)', rec),
      err, btn));
    setTimeout(() => pw.focus(), 30);
  });
}

/** The full-screen entry page: setup notice, sign in, create account, unlock. Resolves with the user info. */
export async function authScreen({ message = '' } = {}) {
  for (;;) {
    let st;
    try { st = await api('/api/status'); } catch (e) { st = { setup: true, registration: true }; }
    if (!st.setup) { await setupPending(); continue; }
    if (!cryptoAvailable()) { insecureNotice(); await new Promise(() => {}); }
    loginAnnouncement = st.announcement || null;
    return loginCard(st.registration, message);
  }
}

function insecureNotice() {
  const httpsUrl = location.href.replace(/^http:/, 'https:');
  card(brand(), h('h3', {}, 'Secure connection required'),
    h('p', {}, 'OpenPrism encrypts your projects in the browser, which browsers only allow on secure (HTTPS) connections.'),
    h('p', {}, 'Open: ', h('a', { href: httpsUrl }, httpsUrl)),
    h('p', { class: 'hint' }, 'If the browser warns about the certificate (self-signed lab server), choose “Advanced → Proceed”. Ask your administrator if unsure.'));
}

function setupPending() {
  return new Promise((resolve) => {
    card(brand(), h('h3', {}, 'Server setup required'),
      h('p', {}, 'This OpenPrism server has not been configured yet. The administrator must complete the setup in the administration console on the server computer itself.'),
      h('p', { class: 'hint' }, 'This page continues automatically when setup is complete.'));
    const t = setInterval(async () => {
      try { const st = await api('/api/status'); if (st.setup) { clearInterval(t); resolve(); } } catch (_) { /* keep waiting */ }
    }, 4000);
  });
}

let loginAnnouncement = null;

function loginCard(registration, message) {
  return new Promise((resolve) => {
    let mode = 'login';
    const draw = () => {
      const user = h('input', { type: 'text', autocomplete: 'username', maxlength: 32, spellcheck: 'false', autocapitalize: 'off', placeholder: 'e.g. jsmith' });
      const pw = pwInput(mode === 'login' ? 'current-password' : 'new-password');
      const pw2 = pwInput('new-password');
      const err = h('div', { class: 'auth-err', role: 'alert' }, message);
      message = '';
      const btn = h('button', { class: 'btn primary', type: 'submit', style: { width: '100%', padding: '9px' } }, mode === 'login' ? 'Sign in' : 'Create account');
      card(brand(), announcementBox(loginAnnouncement),
        registration ? h('div', { class: 'seg auth-tabs' },
          h('button', { class: mode === 'login' ? 'on' : '', type: 'button', onclick: () => { mode = 'login'; draw(); } }, 'Sign in'),
          h('button', { class: mode === 'register' ? 'on' : '', type: 'button', onclick: () => { mode = 'register'; draw(); } }, 'Create account')) : null,
        h('form', { onsubmit: async (e) => {
          e.preventDefault();
          err.textContent = '';
          const u = user.value.trim();
          if (mode === 'register') {
            if (pw.value.length < 8) { err.textContent = 'Use at least 8 characters.'; return; }
            if (pw.value !== pw2.value) { err.textContent = 'The passwords do not match.'; return; }
            if (pw.value.toLowerCase() === u.toLowerCase()) { err.textContent = 'The password must differ from the user ID.'; return; }
          }
          btn.disabled = true; btn.textContent = mode === 'login' ? 'Unlocking…' : 'Creating keys…';
          try {
            const me = mode === 'login' ? await doLogin(u, pw.value) : await doRegister(u, pw.value);
            pw.value = ''; pw2.value = '';
            document.getElementById('auth-root')?.remove();
            resolve(me);
          } catch (ex) {
            err.textContent = ex.message;
            btn.disabled = false; btn.textContent = mode === 'login' ? 'Sign in' : 'Create account';
            if (document.getElementById('auth-root')?.contains(btn) === false) draw();
          }
        } },
        h('label', {}, 'User ID', user),
        h('label', {}, 'Password', pw),
        mode === 'register' ? meterFor(pw) : null,
        mode === 'register' ? h('label', {}, 'Repeat password', pw2) : null,
        mode === 'register' ? h('p', { class: 'hint' }, 'Use a passphrase of several words. Your projects are encrypted with it in this browser; you will also receive a recovery key.') : null,
        err, btn,
        mode === 'login' ? h('a', { href: '#', class: 'forgot', onclick: (e) => { e.preventDefault(); forgotDialog(user.value.trim()); } }, 'Forgot password?') : null),
        registration ? null : h('p', { class: 'hint', style: { textAlign: 'center' } }, 'Accounts are created by the administrator.'),
        h('div', { class: 'auth-foot' }, h('a', { href: '#', onclick: (e) => { e.preventDefault(); openManual('accounts'); } }, 'How accounts & encryption work'), helpIcon('accounts')));
      setTimeout(() => user.focus(), 30);
    };
    draw();
  });
}

/** Session cookie still valid but the data key is not in this browser (other device, cleared storage). */
export async function unlockScreen(me) {
  const stored = await loadDataKey(me.username);
  if (stored) { state.dataKey = stored; return me; }
  return new Promise((resolve) => {
    const pw = pwInput();
    const err = h('div', { class: 'auth-err' });
    card(brand(), h('h3', { style: { margin: '4px 0' } }, `Unlock — ${me.username}`),
      h('p', { class: 'hint' }, 'Enter your password to unlock your encrypted projects in this browser.'),
      h('form', { onsubmit: async (e) => {
        e.preventDefault();
        try {
          const { kek } = await deriveAccountKeys(pw.value, me.keys.salt, me.keys.iter);
          await finishUnlock(me.username, await unwrapDataKey(me.keys.wrappedKey, kek, true));
          document.getElementById('auth-root')?.remove();
          resolve(me);
        } catch (ex) { err.textContent = 'Wrong password.'; }
      } }, h('label', {}, 'Password', pw), err, h('button', { class: 'btn primary', type: 'submit', style: { width: '100%', padding: '9px' } }, 'Unlock')),
      h('a', { href: '#', class: 'forgot', onclick: (e) => { e.preventDefault(); signOut(); } }, 'Sign out instead'));
    setTimeout(() => pw.focus(), 30);
  });
}

function forgotDialog(username) {
  const user = h('input', { type: 'text', value: username || '', maxlength: 32, autocomplete: 'username' });
  const note = h('textarea', { rows: 3, maxlength: 300, placeholder: 'Optional: how the administrator can reach you or confirm who you are', style: { width: '100%' } });
  modal({
    title: 'Forgot your password?',
    body: h('div', {},
      h('p', {}, 'Passwords cannot be recovered. Ask your administrator for a ', h('b', {}, 'one-time password'), ' (send a request below or contact them). After signing in with it, you choose a new password and enter your ', h('b', {}, 'recovery key'), ' to unlock your existing projects.'),
      h('div', { class: 'field' }, h('label', {}, 'User ID'), user),
      h('div', { class: 'field' }, h('label', {}, 'Message'), note),
      h('p', { class: 'hint' }, 'Without the recovery key your existing projects stay encrypted forever — the administrator cannot decrypt them.')),
    buttons: [{ label: 'Cancel' }, { label: 'Send request', primary: true, onClick: async () => {
      if (!user.value.trim()) { toast('Enter your user ID', 'err'); user.focus(); return false; }
      try { const r = await api('/api/auth/reset-request', { username: user.value.trim(), note: note.value }); toast(r.message); } catch (e) { toast(e.message, 'err'); return false; }
      return undefined;
    } }],
  });
}

export async function signOut(all = false) {
  try { await api(all ? '/api/auth/logout-all' : '/api/auth/logout', {}); } catch (_) { /* already signed out */ }
  clearLocalData();
  await clearDataKeys();
  window.location.reload();
}

async function currentKeys() { return (await api('/api/auth/me')).keys; }

export function accountDialog({ onBeforeSignOut } = {}) {
  const oldPw = pwInput(); const newPw = pwInput('new-password'); const newPw2 = pwInput('new-password');
  const msg = h('div', { class: 'auth-err' });
  const recPw = pwInput();
  const delPw = pwInput();
  const auto = h('input', { type: 'checkbox', checked: state.autosaveServer, onchange: (e) => {
    state.autosaveServer = e.target.checked;
    try { localStorage.setItem('openprism.pref.autosave', e.target.checked ? '1' : '0'); } catch (_) { /* ignore */ }
  } });
  const sec = (title, ...kids) => h('div', { class: 'insp-sec', style: { padding: '12px 0' } }, h('h4', {}, title), ...kids);
  return modal({
    title: `My account — ${state.username}`,
    body: h('div', {},
      h('p', { class: 'hint' }, '🔒 Your projects are end-to-end encrypted: they are encrypted in this browser before they reach the server.'),
      sec('Preferences', h('div', { class: 'field check' }, h('label', {}, auto, 'Auto-save projects to the server (a few seconds after each change)'))),
      sec('Learning', h('p', { class: 'hint' }, 'A one-minute guided tour of the main steps, on a small example.'),
        h('button', { class: 'btn', onclick: () => { document.querySelector('.modal-bg .modal-head .x')?.click(); import('./tour.js').then((m) => m.startTour()); } }, '🎓 Replay the guided tour')),
      state.myFingerprint ? sec('Sharing key', h('p', { class: 'hint' }, 'Colleagues who share projects with you see this fingerprint. Read it to them when they ask, so they can check that their copy is encrypted for you and nobody else.'),
        h('code', { class: 'fp' }, state.myFingerprint)) : null,
      sec('Change password',
        h('div', { class: 'field' }, h('label', {}, 'Current password'), oldPw),
        h('div', { class: 'field' }, h('label', {}, 'New password'), newPw), meterFor(newPw),
        h('div', { class: 'field' }, h('label', {}, 'Repeat new password'), newPw2), msg,
        h('button', { class: 'btn primary', onclick: async () => {
          msg.textContent = '';
          if (newPw.value.length < 8) { msg.textContent = 'Use at least 8 characters.'; return; }
          if (newPw.value !== newPw2.value) { msg.textContent = 'The new passwords do not match.'; return; }
          try {
            const keys = await currentKeys();
            const old = await deriveAccountKeys(oldPw.value, keys.salt, keys.iter);
            let dataKey;
            try { dataKey = await unwrapDataKey(keys.wrappedKey, old.kek, true); } catch (_) { throw new Error('Current password is incorrect.'); }
            const salt = randomSaltB64();
            const nw = await deriveAccountKeys(newPw.value, salt, ITER);
            await api('/api/auth/password', { oldAuth: old.auth, newAuth: nw.auth, salt, wrappedKey: await wrapDataKey(dataKey, nw.kek) });
            oldPw.value = newPw.value = newPw2.value = '';
            toast('Password changed. You were signed out on all other devices.');
          } catch (e) { msg.textContent = e.message; }
        } }, 'Change password')),
      sec('Recovery key',
        h('p', { class: 'hint' }, 'Lost your recovery key? Create a new one (the old one stops working).'),
        h('div', { class: 'field' }, h('label', {}, 'Password'), recPw),
        h('button', { class: 'btn', onclick: async () => {
          try {
            const keys = await currentKeys();
            const k = await deriveAccountKeys(recPw.value, keys.salt, keys.iter);
            let dataKey;
            try { dataKey = await unwrapDataKey(keys.wrappedKey, k.kek, true); } catch (_) { throw new Error('Password is incorrect.'); }
            const rk = newRecoveryKey();
            const wrapped = await wrapWithRecovery(dataKey, rk);
            await showRecoveryKey(state.username, rk, 'This is your NEW recovery key. The previous one no longer works.');
            document.getElementById('auth-root')?.remove();
            await api('/api/auth/recovery', { auth: k.auth, recoveryKey: wrapped });
            recPw.value = '';
            toast('New recovery key saved');
          } catch (e) { document.getElementById('auth-root')?.remove(); toast(e.message, 'err'); }
        } }, 'Create new recovery key')),
      sec('Sessions',
        h('div', { style: { display: 'flex', gap: '8px', flexWrap: 'wrap' } },
          h('button', { class: 'btn', onclick: async () => { await onBeforeSignOut?.(); signOut(false); } }, 'Sign out'),
          h('button', { class: 'btn', onclick: async () => { await onBeforeSignOut?.(); signOut(true); } }, 'Sign out on all devices'))),
      sec('Delete account',
        h('p', { class: 'hint' }, 'Permanently deletes your account and all projects stored on the server. Download anything you want to keep first.'),
        h('div', { class: 'field' }, h('label', {}, 'Password'), delPw),
        h('button', { class: 'btn danger', onclick: async () => {
          try {
            const keys = await currentKeys();
            const k = await deriveAccountKeys(delPw.value, keys.salt, keys.iter);
            await api('/api/auth/delete-account', { auth: k.auth });
            clearLocalData();
            await clearDataKeys();
            window.location.reload();
          } catch (e) { toast(e.message, 'err'); }
        } }, 'Delete my account and all projects'))),
    buttons: [{ label: 'Close', primary: true }],
  });
}
