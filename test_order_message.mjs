import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const html = readFileSync(new URL('./index.html', import.meta.url), 'utf8');
const dataStart = html.indexOf('const PRODUCTS =');
const dataEnd = html.indexOf('let cart =', dataStart);
const priceStart = html.indexOf('function unitPrice(');
const priceEnd = html.indexOf('function renderProducts()', priceStart);
const messageStart = html.indexOf('function generateOrderMessage(');
const messageEnd = html.indexOf("productGrid.addEventListener('click'", messageStart);
assert.ok(dataStart >= 0 && dataEnd > dataStart && priceEnd > priceStart && messageEnd > messageStart);
const ctx = vm.createContext({});
vm.runInContext(html.slice(dataStart, dataEnd) + html.slice(priceStart, priceEnd) + html.slice(messageStart, messageEnd) + `
  globalThis.order = { PRODUCTS, BURS_PER_PACK, SHIPPING_COST, FREE_SHIPPING_THRESHOLD,
    PRICE_PER_BUR, TELEGRAM_USER, GRIT_ORDER, unitPrice, generateOrderMessage };
`, ctx);
const d = ctx.order;

function makeOrder(products, packCount = 1) {
  const items = products.map(product => ({ product, packCount }));
  const total = items.reduce((sum, { product }) => sum + packCount * (product.multiplier || d.BURS_PER_PACK), 0);
  const free = total >= d.FREE_SHIPPING_THRESHOLD || items.some(({product}) => product.free_shipping);
  const subtotal = items.reduce((sum, { product }) => sum + packCount * (product.bundle
    ? product.price : (product.multiplier || d.BURS_PER_PACK) * d.unitPrice(product)), 0);
  const final = subtotal + (free ? 0 : d.SHIPPING_COST);
  return { items, total, free, final, text: d.generateOrderMessage(items, total, final, free) };
}

test('catalog pricing prioritizes special models over grit and uses a single fixed price', () => {
  assert.equal(d.PRICE_PER_BUR, 227000);
  const price = model => d.unitPrice(d.PRODUCTS.find(p => p.model === model));
  assert.equal(price('TC-26'), 227000);
  assert.equal(price('TC-26EF'), 233000);
  assert.equal(price('EX-11S'), 234000);
  assert.equal(price('VP-20'), 247000);
  assert.equal(price('BR-L46'), 239000);
  assert.equal(price('FO-40EF'), 239000);
  assert.equal(price('ENDO-Z TI'), 2700000);
  assert.equal([...d.GRIT_ORDER].join(','), 'K⚫,G🟢,B🔵,R🔴,Y🟡,W⚪');
});

test('small order keeps its model price and paid shipping', () => {
  const o = makeOrder([d.PRODUCTS.find(p => p.model === 'TC-21EF')]);
  assert.equal(o.total, 5);
  assert.equal(o.final, 1355000); // 5 × 233,000 + 190,000
  assert.ok(o.text.includes('TC-21EF x 5 @ 233000'));
  assert.ok(o.text.includes('هزینه پست: 190000 تومان'));
  assert.ok(o.text.includes('مبلغ نهایی قابل پرداخت: 1355000 تومان'));
  assert.ok(!o.text.includes('پلکانی'));
});

test('bundle costs 72,080,000 toman per pack and ships free', () => {
  const bundle = d.PRODUCTS.find(p => p.model === 'PACK-400');
  const o = makeOrder([bundle]);
  assert.equal(o.total, 400);
  assert.equal(o.final, 72080000);
  assert.ok(o.free);
  assert.ok(o.text.includes('PACK-400 x 1 بسته = 72080000 تومان (ارسال رایگان)'));
  assert.equal(Math.round((1 - bundle.price / (400 * d.PRICE_PER_BUR)) * 100), 21);
});

test('mixed orders keep per-model prices even when quantity grows', () => {
  const ordinary = d.PRODUCTS.find(p => p.model === 'TC-26');
  const yellow = d.PRODUCTS.find(p => p.model === 'TC-21EF');
  const o = makeOrder([ordinary, yellow], 20);
  assert.equal(o.total, 200);
  assert.equal(o.final, 20 * 5 * (227000 + 233000));
  assert.match(o.text, /TC-26 x 100 @ 227000/);
  assert.match(o.text, /TC-21EF x 100 @ 233000/);
  assert.equal(new URL(`https://t.me/${d.TELEGRAM_USER}?text=${encodeURIComponent(o.text)}`).searchParams.get('text'), o.text);
});

test('all executable inline scripts parse', () => {
  for (const match of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)) {
    if (/type\s*=\s*["']application\/ld\+json["']/.test(match[1])) continue;
    new vm.Script(match[2]);
  }
});
