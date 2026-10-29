import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const html = readFileSync(new URL('./index.html', import.meta.url), 'utf8');
const start = html.indexOf('const PRODUCTS =');
const end = html.indexOf('let cart =', start);
const normalizeStart = html.indexOf('function normalizeSearch(');
const searchEnd = html.indexOf('const suggestions =', normalizeStart);
const ctx = vm.createContext({ rendered: 0 });
vm.runInContext(html.slice(start, end) + `let filteredProducts = [...PRODUCTS]; function renderProducts(){ globalThis.rendered++; }\n` +
  html.slice(normalizeStart, searchEnd) + `globalThis.search = { filterProducts, rankSearchResults, normalizeSearch, get results(){return filteredProducts;} };`, ctx);

test('search finds models despite case, separators, and Persian digits', () => {
  ctx.search.filterProducts('tc ۲۶ef');
  assert.deepEqual(Array.from(ctx.search.results, p => p.model), ['TC-26EF']);
  ctx.search.filterProducts('br_l46');
  assert.deepEqual(Array.from(ctx.search.results, p => p.model), ['BR-L46']);
});

test('suggestions rank exact model before partial models and cap to relevant options', () => {
  const ranked = ctx.search.rankSearchResults('TC-26');
  assert.equal(ranked[0].product.model, 'TC-26');
  assert.ok(ranked.some(result => result.product.model === 'TC-26EF'));
  assert.ok(ranked.slice(0, 5).every(result => result.score > 0));
  assert.match(html, /role="listbox" aria-label="فرزهای مرتبط با جستجو"/);
  assert.match(html, /aria-expanded="false" aria-controls="searchSuggestions"/);
  assert.match(html, /e.key === 'ArrowDown'/);
});

test('search finds Persian shapes and grits, and resets on empty query', () => {
  ctx.search.filterProducts('فلیم زرد');
  assert.ok(ctx.search.results.some(p => p.model === 'FO-41EF'));
  assert.ok(ctx.search.results.every(p => p.grit.startsWith('Y')));
  ctx.search.filterProducts('کارباید');
  assert.ok(ctx.search.results.some(p => p.model === 'ENDO-Z TI'));
  ctx.search.filterProducts('');
  assert.equal(ctx.search.results.length, 51);
  assert.ok(ctx.rendered >= 4);
});
