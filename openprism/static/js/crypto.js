// Client-side project encryption (WebCrypto). The password and the key never
// leave the browser: the server only ever receives the ciphertext envelope.
//
// Envelope format (JSON):
// { format: "openprism-encrypted", v: 1, cipher: "AES-256-GCM", kdf: "PBKDF2-SHA256",
//   iter: 600000, salt: <b64 16 bytes>, iv: <b64 12 bytes>, ct: <b64 ciphertext+tag>, name: <optional> }

export const ITERATIONS = 600000;
const te = new TextEncoder();
const td = new TextDecoder();

export function cryptoAvailable() {
  return !!(window.isSecureContext && window.crypto && window.crypto.subtle);
}

function b64(bytes) {
  let s = '';
  const CH = 0x8000;
  for (let i = 0; i < bytes.length; i += CH) s += String.fromCharCode.apply(null, bytes.subarray(i, i + CH));
  return btoa(s);
}
function unb64(str) {
  const bin = atob(str);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export const isEnvelope = (o) => !!o && typeof o === 'object' && o.format === 'openprism-encrypted';

async function deriveKey(password, salt, iter) {
  const base = await crypto.subtle.importKey('raw', te.encode(password), 'PBKDF2', false, ['deriveKey']);
  return crypto.subtle.deriveKey({ name: 'PBKDF2', hash: 'SHA-256', salt, iterations: iter },
    base, { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']);
}

/** Create a reusable key context from a new password (fresh random salt). */
export async function newKeyContext(password) {
  if (!cryptoAvailable()) throw new Error('Encryption needs a secure context (HTTPS or localhost).');
  const salt = crypto.getRandomValues(new Uint8Array(16));
  return { key: await deriveKey(password, salt, ITERATIONS), salt, iter: ITERATIONS };
}

/** Encrypt any JSON-serializable value. A fresh IV is used for every encryption. */
export async function encryptJSON(value, keyCtx, name) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, keyCtx.key, te.encode(JSON.stringify(value))));
  return { format: 'openprism-encrypted', v: 1, cipher: 'AES-256-GCM', kdf: 'PBKDF2-SHA256', iter: keyCtx.iter,
    salt: b64(keyCtx.salt), iv: b64(iv), ct: b64(ct), ...(name ? { name: String(name).slice(0, 120) } : {}) };
}

/** Decrypt an envelope. Returns {value, keyCtx}; keyCtx can re-encrypt with the same password. */
export async function decryptEnvelope(env, password) {
  if (!cryptoAvailable()) throw new Error('Decryption needs a secure context (HTTPS or localhost).');
  if (!isEnvelope(env) || env.v !== 1) throw new Error('This is not an OpenPrism encrypted file.');
  const iter = Math.min(Math.max(+env.iter || ITERATIONS, 100000), 5000000);
  const salt = unb64(env.salt);
  const key = await deriveKey(password, salt, iter);
  let plain;
  try {
    plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: unb64(env.iv) }, key, unb64(env.ct));
  } catch (_) {
    throw new Error('Wrong password, or the file is damaged.');
  }
  return { value: JSON.parse(td.decode(plain)), keyCtx: { key, salt, iter } };
}

/** A rough password strength hint (0-4). */
export function strength(pw) {
  let s = 0;
  if (pw.length >= 10) s++;
  if (pw.length >= 14) s++;
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) s++;
  if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) s++;
  return Math.min(4, s);
}

// =====================================================================
// Account end-to-end encryption
// =====================================================================
// password --PBKDF2-SHA256(600k, per-user salt)--> 64 bytes
//   [0..31]  KEK  (wraps the data key; never leaves the browser)
//   [32..63] auth (sent to the server instead of the password)
// data key (random AES-256-GCM) encrypts every project and project name.
// recovery key (random 160 bit, shown once) also wraps the data key.

export function randomSaltB64() { return b64(crypto.getRandomValues(new Uint8Array(16))); }

export async function deriveAccountKeys(password, saltB64, iter = ITERATIONS) {
  if (!cryptoAvailable()) throw new Error('End-to-end encryption needs a secure connection (HTTPS). Open OpenPrism via https://…');
  const base = await crypto.subtle.importKey('raw', te.encode(password), 'PBKDF2', false, ['deriveBits']);
  const bits = new Uint8Array(await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt: unb64(saltB64), iterations: iter }, base, 512));
  const kek = await crypto.subtle.importKey('raw', bits.slice(0, 32), { name: 'AES-GCM' }, false, ['wrapKey', 'unwrapKey']);
  const auth = b64(bits.slice(32));
  bits.fill(0);
  return { kek, auth };
}

export async function newDataKey() {
  return crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, true, ['encrypt', 'decrypt']);
}

export async function wrapDataKey(dataKey, kek) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = new Uint8Array(await crypto.subtle.wrapKey('raw', dataKey, kek, { name: 'AES-GCM', iv }));
  return JSON.stringify({ iv: b64(iv), ct: b64(ct) });
}

export async function unwrapDataKey(wrapped, kek, extractable = false) {
  const w = JSON.parse(wrapped);
  try {
    return await crypto.subtle.unwrapKey('raw', unb64(w.ct), kek, { name: 'AES-GCM', iv: unb64(w.iv) },
      { name: 'AES-GCM', length: 256 }, extractable, ['encrypt', 'decrypt']);
  } catch (_) {
    throw new Error('Wrong password or key.');
  }
}

// ---- recovery key: 20 random bytes shown as 8 groups of 4 base32 characters
const B32 = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
export function newRecoveryKey() {
  const bytes = crypto.getRandomValues(new Uint8Array(20));
  let bits = 0; let value = 0; let out = '';
  for (const b of bytes) {
    value = (value << 8) | b; bits += 8;
    while (bits >= 5) { out += B32[(value >>> (bits - 5)) & 31]; bits -= 5; }
  }
  return out.match(/.{4}/g).join('-');
}
async function recoveryKek(recovery) {
  const norm = recovery.toUpperCase().replace(/[^A-Z0-9]/g, '');
  if (norm.length !== 32) throw new Error('A recovery key has 32 characters (8 groups of 4).');
  const ikm = await crypto.subtle.importKey('raw', te.encode(norm), 'HKDF', false, ['deriveKey']);
  return crypto.subtle.deriveKey({ name: 'HKDF', hash: 'SHA-256', salt: te.encode('openprism-recovery-v1'), info: te.encode('wrap') },
    ikm, { name: 'AES-GCM', length: 256 }, false, ['wrapKey', 'unwrapKey']);
}
export async function wrapWithRecovery(dataKey, recovery) { return wrapDataKey(dataKey, await recoveryKek(recovery)); }
export async function unwrapWithRecovery(wrapped, recovery, extractable = true) {
  try { return await unwrapDataKey(wrapped, await recoveryKek(recovery), extractable); } catch (e) {
    throw new Error(e.message.startsWith('A recovery') ? e.message : 'This recovery key does not match your account.');
  }
}

// ---- projects and names with the data key
export async function encryptWithKey(value, key) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, te.encode(JSON.stringify(value))));
  return { format: 'openprism-e2e', v: 1, iv: b64(iv), ct: b64(ct) };
}
export async function decryptWithKey(env, key) {
  try {
    const plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: unb64(env.iv) }, key, unb64(env.ct));
    return JSON.parse(td.decode(plain));
  } catch (_) {
    throw new Error('This project cannot be decrypted with your current key (it may have been saved before a password reset without the recovery key).');
  }
}
export async function encryptName(name, key) {
  const e = await encryptWithKey(String(name).slice(0, 200), key);
  return JSON.stringify({ iv: e.iv, ct: e.ct });
}
export async function decryptName(nameCt, key) {
  try { const w = JSON.parse(nameCt); return await decryptWithKey({ iv: w.iv, ct: w.ct }, key); } catch (_) { return null; }
}

// ---- keep the unlocked (non-extractable) data key in IndexedDB until sign-out
const DB = 'openprism-keys';
function idb() {
  return new Promise((resolve, reject) => {
    const r = indexedDB.open(DB, 1);
    r.onupgradeneeded = () => r.result.createObjectStore('keys');
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => reject(r.error);
  });
}
export async function storeDataKey(username, key) {
  try {
    const db = await idb();
    await new Promise((res, rej) => { const tx = db.transaction('keys', 'readwrite'); tx.objectStore('keys').put(key, username.toLowerCase()); tx.oncomplete = res; tx.onerror = () => rej(tx.error); });
    db.close();
  } catch (_) { /* private mode: the key then lives only in memory */ }
}
export async function loadDataKey(username) {
  try {
    const db = await idb();
    const key = await new Promise((res) => { const rq = db.transaction('keys').objectStore('keys').get(username.toLowerCase()); rq.onsuccess = () => res(rq.result || null); rq.onerror = () => res(null); });
    db.close();
    return key;
  } catch (_) { return null; }
}
export async function clearDataKeys() {
  try { await new Promise((res) => { const r = indexedDB.deleteDatabase(DB); r.onsuccess = res; r.onerror = res; r.onblocked = res; }); } catch (_) { /* ignore */ }
}

/** Re-import a key as non-extractable (for storage) once wrapping work is done. */
export async function toNonExtractable(key) {
  const raw = await crypto.subtle.exportKey('raw', key);
  const k = await crypto.subtle.importKey('raw', raw, { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']);
  new Uint8Array(raw).fill(0);
  return k;
}

// ---- sharing between users (end-to-end encrypted copies)
// Each user has an ECDH P-256 key pair. The private key is stored on the server only encrypted
// with the user's data key. To share, the sender encrypts a copy of the project with a fresh
// AES-256-GCM key K and wraps K for the recipient: ephemeral ECDH → HKDF-SHA256 → AES-GCM.
const SHARE_INFO = te.encode('openprism-share-v1');

export async function generateShareKeys(dataKey) {
  const kp = await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits']);
  const pub = new Uint8Array(await crypto.subtle.exportKey('spki', kp.publicKey));
  const pkcs8 = new Uint8Array(await crypto.subtle.exportKey('pkcs8', kp.privateKey));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, dataKey, pkcs8));
  pkcs8.fill(0);
  return { pub: b64(pub), priv: JSON.stringify({ iv: b64(iv), ct: b64(ct) }) };
}

export async function loadSharePrivateKey(privJson, dataKey) {
  const { iv, ct } = JSON.parse(privJson);
  const pkcs8 = new Uint8Array(await crypto.subtle.decrypt({ name: 'AES-GCM', iv: unb64(iv) }, dataKey, unb64(ct)));
  try { return await crypto.subtle.importKey('pkcs8', pkcs8, { name: 'ECDH', namedCurve: 'P-256' }, false, ['deriveBits']); } finally { pkcs8.fill(0); }
}

/** Human-comparable fingerprint of a public key (SHA-256, 20 hex characters in groups). */
export async function keyFingerprint(pubB64) {
  const h = new Uint8Array(await crypto.subtle.digest('SHA-256', unb64(pubB64)));
  return [...h.slice(0, 10)].map((x) => x.toString(16).padStart(2, '0')).join('').toUpperCase().match(/.{4}/g).join(' ');
}

async function wrapKeyFor(privKey, pubKey, salt) {
  const bits = await crypto.subtle.deriveBits({ name: 'ECDH', public: pubKey }, privKey, 256);
  const hk = await crypto.subtle.importKey('raw', bits, 'HKDF', false, ['deriveKey']);
  return crypto.subtle.deriveKey({ name: 'HKDF', hash: 'SHA-256', salt, info: SHARE_INFO }, hk, { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']);
}

/** Encrypt a copy of a project (and its name and an optional note) for the holder of recipientPub. */
export async function sealShare(project, name, note, recipientPubB64) {
  const recipient = await crypto.subtle.importKey('spki', unb64(recipientPubB64), { name: 'ECDH', namedCurve: 'P-256' }, false, []);
  const eph = await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits']);
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const kek = await wrapKeyFor(eph.privateKey, recipient, salt);
  const K = await crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, true, ['encrypt', 'decrypt']);
  const raw = new Uint8Array(await crypto.subtle.exportKey('raw', K));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const wrapped = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, kek, raw));
  raw.fill(0);
  const ephPub = new Uint8Array(await crypto.subtle.exportKey('spki', eph.publicKey));
  return {
    eph: b64(ephPub), salt: b64(salt), wrapped: JSON.stringify({ iv: b64(iv), ct: b64(wrapped) }),
    name_ct: await encryptName(name, K), note_ct: note ? await encryptName(note, K) : '',
    data: await encryptWithKey(project, K), recipientPub: recipientPubB64,
  };
}

/** Unwrap a share's content key with the recipient's private key. */
export async function openShareKey(share, privKey) {
  const eph = await crypto.subtle.importKey('spki', unb64(share.eph), { name: 'ECDH', namedCurve: 'P-256' }, false, []);
  const kek = await wrapKeyFor(privKey, eph, unb64(share.salt));
  const { iv, ct } = JSON.parse(share.wrapped);
  const raw = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: unb64(iv) }, kek, unb64(ct));
  return crypto.subtle.importKey('raw', raw, { name: 'AES-GCM' }, false, ['decrypt']);
}
