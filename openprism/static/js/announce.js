// Server announcement from the administrator (e.g. "maintenance on Friday — download your projects").
// Shown on the sign-in screen and as a banner at the top of the app. Plain text only.
// Info / warning messages can be hidden by each user until the administrator changes the text;
// urgent messages cannot be hidden.
import { h } from './ui.js';

const ICON = { info: 'ℹ️', warning: '⚠️', urgent: '🚨' };
const KEY = 'openprism.announce.hidden';
let current = null;
let timer = null;

const hiddenId = () => { try { return localStorage.getItem(KEY); } catch (_) { return null; } };

/** Element for the sign-in card (always shown, cannot be hidden there). */
export function announcementBox(a) {
  if (!a?.text) return null;
  return h('div', { class: `announce in-card ${a.level || 'info'}`, role: 'status' },
    h('span', { class: 'an-icon', 'aria-hidden': 'true' }, ICON[a.level] || ICON.info),
    h('div', { class: 'an-text' }, h('b', {}, 'Message from the administrator'), h('div', {}, a.text)));
}

/** Banner at the top of the app window. */
export function showAnnouncement(a) {
  current = a?.text ? a : null;
  let el = document.getElementById('announce');
  if (!current || (current.level !== 'urgent' && hiddenId() === current.id)) { el?.remove(); return; }
  const fresh = h('div', { id: 'announce', class: `announce ${current.level || 'info'}`, role: 'status', 'aria-live': 'polite' },
    h('span', { class: 'an-icon', 'aria-hidden': 'true' }, ICON[current.level] || ICON.info),
    h('div', { class: 'an-text' }, h('b', {}, 'Administrator: '), current.text),
    current.level === 'urgent' ? null : h('button', { class: 'an-close', title: 'Hide this message (it comes back if the administrator changes it)', onclick: () => {
      try { localStorage.setItem(KEY, current.id); } catch (_) { /* ignore */ }
      document.getElementById('announce')?.remove();
    } }, '×'));
  if (el) el.replaceWith(fresh); else document.body.prepend(fresh);
}

/** Check for a new or changed announcement every few minutes while the app is open. */
export function watchAnnouncements(fetchStatus, everyMs = 180000) {
  clearInterval(timer);
  const tick = async () => { try { const st = await fetchStatus(); if ((st.announcement?.id || null) !== (current?.id || null)) showAnnouncement(st.announcement); } catch (_) { /* offline: keep the last one */ } };
  timer = setInterval(tick, everyMs);
  return tick();
}
