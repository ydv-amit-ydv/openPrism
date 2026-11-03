// highlight the target section, live TOC highlighting and simple search filter
function flash() {
  const id = decodeURIComponent(location.hash.slice(1));
  const el = id && document.getElementById(id);
  if (el) { el.classList.remove('hl'); void el.offsetWidth; el.classList.add('hl'); }
}
window.addEventListener('hashchange', flash);
flash();
const links = [...document.querySelectorAll('#toc a')];
const obs = new IntersectionObserver((entries) => {
  entries.forEach((e) => { if (e.isIntersecting) links.forEach((a) => a.classList.toggle('on', a.getAttribute('href') === `#${e.target.id}`)); });
}, { rootMargin: '0px 0px -75% 0px' });
document.querySelectorAll('main section').forEach((s) => obs.observe(s));
document.getElementById('q').addEventListener('input', (e) => {
  const q = e.target.value.trim().toLowerCase();
  document.querySelectorAll('main section').forEach((s) => { s.hidden = q && !s.textContent.toLowerCase().includes(q); });
  links.forEach((a) => { const s = document.querySelector(a.getAttribute('href')); a.parentElement.hidden = s && s.hidden; });
});
