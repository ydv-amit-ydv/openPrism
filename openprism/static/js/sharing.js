// Sharing projects between users of the same server — end-to-end encrypted.
// The server only ever stores and forwards ciphertext: a copy of the project
// encrypted in the sender's browser for the recipient's public key.
import {
  decryptName, decryptWithKey, encryptName, encryptWithKey, generateShareKeys, keyFingerprint, loadSharePrivateKey, openShareKey, sealShare,
} from './crypto.js';
import { P, state } from './state.js';
import { api, h, modal, toast } from './ui.js';

const KNOWN = () => `openprism.knownKeys.${state.username}`;
function knownKeys() { try { return JSON.parse(localStorage.getItem(KNOWN()) || '{}'); } catch (_) { return {}; } }
function rememberKey(user, fp) { try { const k = knownKeys(); k[user.toLowerCase()] = fp; localStorage.setItem(KNOWN(), JSON.stringify(k)); } catch (_) { /* ignore */ } }
const fmtSize = (b) => (b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} KB` : `${(b / 1024 / 1024).toFixed(1)} MB`);
const fmtDate = (t) => new Date(t * 1000).toLocaleString();

/** Make sure this account has a sharing key pair; called after sign-in. Returns inbox count. */
export async function ensureShareKeys() {
  state.sharePriv = null;
  if (!state.dataKey) return 0;
  let k;
  try { k = await api('/api/sharing/keys'); } catch (_) { return 0; }
  state.sharingEnabled = !!k.enabled;
  if (!k.enabled) return 0;
  if (k.pub && k.priv) {
    try {
      state.sharePriv = await loadSharePrivateKey(k.priv, state.dataKey);
      state.sharePub = k.pub;
    } catch (_) {
      // the data key changed (password reset without the recovery key): make a new key pair
      toast('Your sharing key was renewed after a password reset. Projects shared with you before the reset cannot be opened — ask the sender to share them again.', 'err');
    }
  }
  if (!state.sharePriv) {
    const fresh = await generateShareKeys(state.dataKey);
    await api('/api/sharing/keys', { pub: fresh.pub, priv: fresh.priv }, 'PUT');
    state.sharePriv = await loadSharePrivateKey(fresh.priv, state.dataKey);
    state.sharePub = fresh.pub;
  }
  state.myFingerprint = await keyFingerprint(state.sharePub);
  try {
    const inbox = await api('/api/sharing/inbox');
    return inbox.shares.length;
  } catch (_) { return 0; }
}

function requireSharing() {
  if (state.sharingEnabled === false) { toast('Sharing between users is turned off on this server.', 'err'); return false; }
  if (!state.sharePriv) { toast('Sharing keys are not ready yet. Please wait a moment and try again.', 'err'); return false; }
  return true;
}

/** Send an encrypted copy of the current project to a colleague. */
export function shareDialog() {
  if (!requireSharing()) return;
  if (!P().tables.length) { toast('The project is empty: add data first.', 'err'); return; }
  let target = null;
  const user = h('input', { type: 'text', placeholder: 'Colleague’s username', autocomplete: 'off', spellcheck: 'false' });
  const note = h('textarea', { class: 'share-msg', placeholder: 'Optional message (encrypted too)', maxlength: 500, rows: 3 });
  const info = h('div', { class: 'share-info' });
  const confirmBox = h('input', { type: 'checkbox' });
  let lookSeq = 0;
  const look = async () => {
    const name = user.value.trim();
    if (target && target.username.toLowerCase() === name.toLowerCase()) return;  // already looked up
    const my = ++lookSeq;
    target = null;
    info.innerHTML = '';
    if (!name) return;
    try {
      const k = await api(`/api/sharing/pubkey?username=${encodeURIComponent(name)}`);
      if (my !== lookSeq) return;  // a newer lookup is under way
      const fp = await keyFingerprint(k.pub);
      const prev = knownKeys()[k.username.toLowerCase()];
      target = { ...k, fp, changed: !!prev && prev !== fp };
      info.append(
        h('div', {}, 'Recipient: ', h('b', {}, k.username)),
        h('div', {}, 'Key fingerprint: ', h('code', { class: 'fp' }, fp)),
        target.changed
          ? h('div', { class: 'warnbox' }, h('b', {}, '⚠ This user’s key has changed '), `since you last shared with them (was ${prev}). This happens after a password reset without the recovery key — or if someone is impersonating them. Confirm the new fingerprint with your colleague before sending.`,
            h('label', { class: 'check-line' }, confirmBox, 'I have verified the new fingerprint'))
          : prev ? h('div', { class: 'hint ok' }, '✓ Same key as the last time you shared with this user.')
            : h('div', { class: 'hint' }, 'First share with this user: for highly sensitive data, ask your colleague to read you the fingerprint shown in their Account dialog and check that it matches.'));
    } catch (e) { if (my === lookSeq) info.append(h('div', { class: 'errbox' }, e.message)); }
  };
  user.addEventListener('change', look);
  user.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); look(); } });
  modal({
    title: 'Share a copy with a colleague',
    body: h('div', {},
      h('p', { class: 'hint' }, `A copy of “${P().name}” is encrypted in your browser for your colleague’s key; the server can neither read it nor give it to anyone else. Your colleague receives it under File → Shared with me and saves it as their own project. Later changes are not synchronized — share again to send an update.`),
      h('div', { class: 'field' }, h('label', {}, 'Send to'), h('div', { style: { display: 'flex', gap: '6px' } }, user, h('button', { class: 'btn small', onclick: look }, 'Look up'))),
      info, h('div', { class: 'field' }, h('label', {}, 'Message'), note)),
    buttons: [{ label: 'Cancel' }, { label: 'Encrypt & send', primary: true, onClick: async () => {
      if (!target || target.username.toLowerCase() !== user.value.trim().toLowerCase()) { await look(); if (!target) return false; }
      if (target.changed && !confirmBox.checked) { toast('Please verify the changed key first (or cancel).', 'err'); return false; }
      try {
        const share = await sealShare(JSON.parse(JSON.stringify(P())), P().name || 'Shared project', note.value.trim(), target.pub);
        await api('/api/sharing/send', { to: target.username, share }, undefined, `Share with ${target.username}`);
        rememberKey(target.username, target.fp);
        toast(`Encrypted copy sent to ${target.username}`);
        return true;
      } catch (e) { toast(`Could not share: ${e.message}`, 'err'); return false; }
    } }],
  });
  setTimeout(() => user.focus(), 50);
}

/** Projects other users shared with me. `onImported(serverId)` opens the new project. */
export async function inboxDialog(onImported) {
  if (!requireSharing()) return;
  const list = h('div', { class: 'share-list' }, h('p', { class: 'hint' }, 'Loading…'));
  const ctl = modal({ title: 'Shared with me', wide: true, body: h('div', {},
    h('p', { class: 'hint' }, 'Projects your colleagues sent you, decrypted only in this browser. Saving one creates your own copy (encrypted with your key) and removes it from this list.'), list),
  buttons: [{ label: 'Close', primary: true }] });
  const draw = async () => {
    let items;
    try { items = (await api('/api/sharing/inbox')).shares; } catch (e) { list.innerHTML = ''; list.append(h('div', { class: 'errbox' }, e.message)); return; }
    list.innerHTML = '';
    if (!items.length) { list.append(h('p', { class: 'hint' }, 'Nothing has been shared with you.')); return; }
    for (const it of items) {
      let name = '(cannot decrypt)'; let msg = ''; let K = null;
      try { K = await openShareKey(it, state.sharePriv); name = await decryptName(it.name_ct, K); msg = it.note_ct ? await decryptName(it.note_ct, K) : ''; } catch (_) { /* old key */ }
      list.append(h('div', { class: 'share-row' },
        h('div', {}, h('b', {}, name), h('div', { class: 'hint' }, `from ${it.from} · ${fmtSize(it.size)} · ${fmtDate(it.created)}`), msg ? h('div', { class: 'share-note' }, `“${msg}”`) : null),
        h('button', { class: 'btn small primary', disabled: !K, onclick: async () => {
          try {
            const full = await api(`/api/sharing/${encodeURIComponent(it.id)}`, undefined, undefined, `Receive “${name}”`);
            const project = await decryptWithKey(full.data, K);
            project.name = name;
            const saved = await api('/api/projects', { name: await encryptName(name, state.dataKey), data: await encryptWithKey(project, state.dataKey) });
            await api(`/api/sharing/${encodeURIComponent(it.id)}`, undefined, 'DELETE');
            ctl.close();
            toast(`Saved “${name}” from ${it.from} as your own project`);
            onImported?.(saved.id);
          } catch (e) { toast(`Could not open: ${e.message}`, 'err'); }
        } }, 'Save as my project & open'),
        h('button', { class: 'btn small danger', onclick: async () => { await api(`/api/sharing/${encodeURIComponent(it.id)}`, undefined, 'DELETE'); draw(); } }, 'Decline')));
    }
  };
  draw();
}

export async function sentDialog() {
  if (!requireSharing()) return;
  const list = h('div', { class: 'share-list' });
  const draw = async () => {
    const items = (await api('/api/sharing/sent')).shares;
    list.innerHTML = '';
    if (!items.length) { list.append(h('p', { class: 'hint' }, 'No shares are waiting. (Shares disappear from this list once your colleague saves or declines them.)')); return; }
    for (const it of items) {
      list.append(h('div', { class: 'share-row' }, h('div', {}, h('b', {}, `to ${it.to}`), h('div', { class: 'hint' }, `${fmtSize(it.size)} · sent ${fmtDate(it.created)} · not yet accepted`)),
        h('button', { class: 'btn small danger', onclick: async () => { await api(`/api/sharing/${encodeURIComponent(it.id)}`, undefined, 'DELETE'); draw(); } }, 'Withdraw')));
    }
  };
  modal({ title: 'Shares waiting to be accepted', body: list, buttons: [{ label: 'Close', primary: true }] });
  draw();
}
