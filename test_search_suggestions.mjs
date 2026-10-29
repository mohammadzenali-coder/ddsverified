import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const html = readFileSync(new URL('./index.html', import.meta.url), 'utf8');
const inputEvents = {};
const input = {
  value: '', attrs: {},
  addEventListener(type, fn) { inputEvents[type] = fn; },
  setAttribute(key, value) { this.attrs[key] = value; },
  removeAttribute(key) { delete this.attrs[key]; },
};
const suggestions = {
  hidden: true, html: '', options: [],
  set innerHTML(value) {
    this.html = value;
    this.options = [...value.matchAll(/<a\s+class="search-suggestion"\s+id="([^"]+)"[^>]*href="([^"]+)"/g)]
      .map(([, id, href]) => ({ id, href: new URL(href, 'http://localhost').href, classes: new Set(), attrs: {},
        classList: { toggle(name, active) { active ? this.classes?.add(name) : this.classes?.delete(name); } },
        setAttribute(key, val) { this.attrs[key] = val; }, scrollIntoView() {},
      }));
    for (const option of this.options) option.classList.classes = option.classes;
  },
  get innerHTML() { return this.html; },
  querySelectorAll() { return this.options; },
};
const document = { hidden: false, getElementById: () => suggestions, addEventListener() {} };
const location = { assigned: null, assign(url) { this.assigned = url; } };
const ctx = vm.createContext({ document, window: { location }, searchInput: input, URLSearchParams });
const dataStart = html.indexOf('const PRODUCTS =');
const dataEnd = html.indexOf('let cart =', dataStart);
const codeStart = html.indexOf('function normalizeSearch(');
const codeEnd = html.indexOf('const initialQuery =', codeStart);
vm.runInContext(html.slice(dataStart, dataEnd) + `
 let filteredProducts = [...PRODUCTS];
 function renderProducts(){}
 function unitPrice(p){return p.price ?? PRICE_PER_BUR;}
 function toPersian(n){return Number(n).toLocaleString('fa-IR');}
 ` + html.slice(codeStart, codeEnd), ctx);

test('typing opens a small, relevant dropdown under the input', () => {
  input.value = 'TC-26';
  inputEvents.input({ target: input });
  assert.equal(suggestions.hidden, false);
  assert.equal(input.attrs['aria-expanded'], 'true');
  assert.equal(suggestions.options[0].href, 'http://localhost/product/tc-26/');
  assert.ok(suggestions.options.length <= 5);
  assert.match(suggestions.innerHTML, /TC-26EF/);
});

test('arrow keys choose a result and Escape dismisses suggestions', () => {
  let prevented = false;
  inputEvents.keydown({ key: 'ArrowDown', preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  assert.equal(input.attrs['aria-activedescendant'], 'suggestion-0');
  inputEvents.keydown({ key: 'Enter', preventDefault() {} });
  assert.equal(location.assigned, 'http://localhost/product/tc-26/');
  inputEvents.keydown({ key: 'Escape' });
  assert.equal(suggestions.hidden, true);
  assert.equal(input.attrs['aria-expanded'], 'false');
});
