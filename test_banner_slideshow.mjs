/* Pure-DOM check of the homepage lux-banner slideshow — zero dependencies.
 * Builds a minimal DOM from the REAL markup in index.html, runs the REAL
 * inline slideshow <script> against it, and asserts the swap behavior.
 * No jsdom, no browser, no network.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('./index.html', import.meta.url), 'utf8');

/* --- minimal DOM shim: only what the slideshow script touches --- */
const VOID = new Set(['img', 'source', 'br', 'hr', 'input', 'meta', 'link']);
function el(tag, attrs = {}) {
  const n = { tag, attrs, children: [], style: {}, _listeners: {}, _text: '' };
  n.classList = {
    _s: new Set((attrs.class || '').split(/\s+/).filter(Boolean)),
    add: c => n.classList._s.add(c),
    has: c => n.classList._s.has(c),
    delete: c => n.classList._s.delete(c),
    toggle: (c, on) => on === undefined
      ? (n.classList.has(c) ? n.classList.delete(c) : n.classList.add(c))
      : (on ? n.classList.add(c) : n.classList.delete(c)),
  };
  n.addEventListener = (t, fn) => { (n._listeners[t] ||= []).push(fn); };
  n.dispatchEvent = e => (n._listeners[e.type] || []).forEach(fn => fn(e));
  n.appendChild = c => { n.children.push(c); return c; };
  n.descendants = function* () { for (const c of n.children) { yield c; yield* c.descendants(); } };
  n.querySelectorAll = sel => [...n.descendants()].filter(c => matches(c, sel));
  n.querySelector = sel => n.querySelectorAll(sel)[0] || null;
  n.getAttribute = k => n.attrs[k];
  n.setAttribute = (k, v) => { n.attrs[k] = v; };
  return n;
}
function matches(n, sel) {
  return sel.startsWith('.') ? n.classList.has(sel.slice(1)) : n.tag === sel;
}
const document = { _root: el('div'),
  getElementById(id) { return [...document._root.descendants()].find(n => n.attrs.id === id) || null; },
  createElement: t => el(t),
};

/* Extract the REAL banner markup + REAL inline script from index.html */
const bannerStart = html.indexOf('<div class="lux-banner" id="luxBanner">');
const bannerEnd = html.indexOf('</div>\n    <script>', bannerStart);
assert.ok(bannerStart >= 0 && bannerEnd > bannerStart, 'found banner markup in index.html');
const bannerMarkup = html.slice(bannerStart, bannerEnd + '</div>'.length);
const scriptStart = html.indexOf("var s=document.getElementById('luxBanner')");
const scriptEnd = html.indexOf('})();', scriptStart);
assert.ok(scriptStart >= 0 && scriptEnd > scriptStart, 'found slideshow script in index.html');
const scriptBody = html.slice(scriptStart, scriptEnd);

/* Parse the real markup into the shim DOM */
let current = document._root; const stack = [current];
const tagRe = /<(\w+)((?:\s+[\w:-]+(?:="[^"]*")?)*)\s*\/?>|<\/(\w+)>|([^<]+)/g;
for (const match of bannerMarkup.matchAll(tagRe)) {
  if (match[1]) {
    const attrs = {}; let a; const aRe = /([\w:-]+)="([^"]*)"/g;
    while ((a = aRe.exec(match[2] || ''))) attrs[a[1]] = a[2];
    const n = el(match[1], attrs);
    current.appendChild(n);
    if (!VOID.has(match[1])) { stack.push(current); current = n; }
  } else if (match[3]) {
    current = stack.pop();
  } else if (match[4] !== undefined && match[4].trim()) {
    current.appendChild(Object.assign(el('#text'), { _text: match[4].trim() }));
  }
}
const banner = document.getElementById('luxBanner');
assert.ok(banner, 'luxBanner element built');
assert.equal(banner.querySelectorAll('img').length, 2, 'two slide images');

/* Run the REAL inline script */
const timers = []; let intervalMs = null;
const fn = new Function('document', 'window', 'setInterval', 'clearInterval', scriptBody);
fn(document, {},
   (f, ms) => { intervalMs = ms; timers.push(f); return timers.length; },
   () => {});

const slides = banner.querySelectorAll('.lslide');
const dots = banner.querySelectorAll('button');

test('two slides and two dot buttons generated from real markup', () => {
  assert.equal(slides.length, 2);
  assert.equal(dots.length, 2);
  assert.equal(intervalMs, 6000, 'auto-advance interval is 6s');
});

test('only first slide is on at load (no layout shift, slide-2 image stays lazy)', () => {
  assert.ok(slides[0].classList.has('on'));
  assert.ok(!slides[1].classList.has('on'));
  assert.equal(slides[0].querySelector('img').getAttribute('src'), 'images/endozburbanner.webp');
  assert.equal(slides[1].querySelector('img').getAttribute('src'), 'images/lux.webp');
  assert.equal(slides[1].querySelector('img').getAttribute('loading'), 'lazy');
  assert.equal(slides[0].querySelector('img').getAttribute('fetchpriority'), 'high');
});

test('clicking dot 2 swaps in slide 2 and re-arms the interval', () => {
  dots[1].dispatchEvent({ type: 'click' });
  assert.ok(slides[1].classList.has('on'));
  assert.ok(!slides[0].classList.has('on'));
  assert.ok(dots[1].classList.has('on'));
  assert.ok(timers.length >= 2, 'interval reset after manual navigation');
});

test('interval tick wraps back to slide 1', () => {
  timers[timers.length - 1]();
  assert.ok(slides[0].classList.has('on'));
  assert.ok(!slides[1].classList.has('on'));
});
