// Full-screen and focus modes for large (or small) screens.
//
// * Full screen: the Fullscreen API (same effect as the browser's F11, but the
//   app knows about it, so the top-bar button always shows "Exit full screen").
// * Focus mode: hides the navigator and ribbon to give graphs and tables the
//   whole window (works with or without full screen).
import { h, toast } from './ui.js';


export const isFullscreen = () => !!(document.fullscreenElement || document.webkitFullscreenElement);
export const fullscreenSupported = () => !!(document.documentElement.requestFullscreen || document.documentElement.webkitRequestFullscreen);

export async function enterFullscreen() {
  const el = document.documentElement;
  try {
    if (el.requestFullscreen) await el.requestFullscreen({ navigationUI: 'hide' });
    else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
  } catch (e) {
    toast('Full screen was blocked by the browser. Press F11 instead.', 'err');
  }
}

export async function exitFullscreen() {
  try {
    if (document.exitFullscreen) await document.exitFullscreen();
    else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
  } catch (_) { /* already left */ }
}

export function toggleFullscreen() { return isFullscreen() ? exitFullscreen() : enterFullscreen(); }

export function toggleFocus(on) {
  const want = on ?? !document.body.classList.contains('focus-mode');
  document.body.classList.toggle('focus-mode', want);
  window.dispatchEvent(new Event('resize'));  // graphs re-fit to the new space
  drawButtons();
}

let btn;
let exitPill;

function drawButtons() {
  if (!btn) return;
  const fs = isFullscreen();
  btn.classList.toggle('on', fs);
  btn.title = fs ? 'Leave full screen (Esc or F11)' : 'Use the whole screen (F11)';
  btn.innerHTML = '';
  btn.append(h('span', { class: 'fs-icon', 'aria-hidden': 'true' }, fs ? '⤡' : '⛶'), h('span', { class: 'fs-label' }, fs ? 'Exit full screen' : 'Full screen'));
  exitPill.hidden = !(fs || document.body.classList.contains('focus-mode'));
  exitPill.textContent = fs ? '⤡ Exit full screen' : '⤡ Exit focus mode';
}

export function initFullscreen() {
  btn = document.getElementById('fullscreen-btn');
  exitPill = h('button', { class: 'fs-exit', hidden: true, onclick: () => { if (isFullscreen()) exitFullscreen(); else toggleFocus(false); } });
  document.body.append(exitPill);
  if (!btn) return;
  if (!fullscreenSupported()) btn.hidden = true;
  btn.addEventListener('click', toggleFullscreen);
  for (const ev of ['fullscreenchange', 'webkitfullscreenchange']) document.addEventListener(ev, () => { drawButtons(); window.dispatchEvent(new Event('resize')); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'F11' && fullscreenSupported()) { e.preventDefault(); toggleFullscreen(); }
    else if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'f') { e.preventDefault(); toggleFocus(); }
  });
  drawButtons();
}
