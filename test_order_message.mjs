import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

// Exercise the real inline data and message builder without booting the UI
// or opening Telegram/WhatsApp. No browser or network dependencies.
const html = readFileSync(new URL('./index.html', import.meta.url), 'utf8');
const dataStart = html.indexOf('const PRODUCTS =');
const dataEnd = html.indexOf('let cart =', dataStart);
const messageStart = html.indexOf('function generateOrderMessage(');
const messageEnd = html.indexOf("productGrid.addEventListener('click'", messageStart);
assert.ok(dataStart >= 0 && dataEnd > dataStart);
assert.ok(messageStart >= 0 && messageEnd > messageStart);
const ctx = vm.createContext({});
vm.runInContext(html.slice(dataStart, dataEnd) + html.slice(messageStart, messageEnd) + `
  globalThis.order = { PRODUCTS, BURS_PER_PACK, SHIPPING_COST,
    FREE_SHIPPING_THRESHOLD, SHAPE_MAP, GRIT_TEXT, TELEGRAM_USER,
    getTierInfo, generateOrderMessage };
`, ctx);
const d = ctx.order;

function makeOrder(products, packCount = 1) {
  const items = products.map(product => ({ product, packCount }));
  const total = items.reduce((sum, { product }) => sum + packCount * (product.multiplier || d.BURS_PER_PACK), 0);
  const tier = d.getTierInfo(total).cur;
  const free = total >= d.FREE_SHIPPING_THRESHOLD;
  const final = items.reduce((sum, { product }) => sum + packCount * (product.multiplier || d.BURS_PER_PACK) * (product.price ?? tier.price), 0) + (free ? 0 : d.SHIPPING_COST);
  return { items, total, tier, free, final, text: d.generateOrderMessage(items, total, final, free) };
}

function urlBytes(text) {
  return Buffer.byteLength(`https://t.me/${d.TELEGRAM_USER}?text=${encodeURIComponent(text)}`);
}

// Frozen pre-fix format for a reproducible size comparison.
function legacyMessage(o) {
  let msg = 'سلام همکار\nبابت سفارش فرزهای دندانپزشکی:\n\n';
  for (const { product: p, packCount } of o.items) {
    const count = packCount * (p.multiplier || d.BURS_PER_PACK);
    msg += `${count} عدد ${d.SHAPE_MAP[p.shape] || p.shape} قطر ${p.diameter} دور ${d.GRIT_TEXT[p.grit] || ''} مدل ${p.model} - ${count}*(${p.price ?? o.tier.price} تومان)\n`;
  }
  msg += `\nتعداد کل فرزها: ${o.total} عدد\n`;
  msg += `قیمت پلکانی نقدی هر فرز: ${o.tier.price} تومان\n`;
  if (o.tier.installment) msg += `🧾 امکان پرداخت قسطی: ${o.tier.installment.price} تومان هر فرز (${o.tier.installment.terms})\n`;
  if (o.free) {
    msg += `🎁 ارسال رایگان شد! (سفارش بالای ${d.FREE_SHIPPING_THRESHOLD} عدد)\n`;
    msg += 'هزینه پست: 0 تومان (رایگان)\n';
  } else msg += `هزینه پست (دریافتی پست از ما): ${d.SHIPPING_COST} تومان\n`;
  return msg + `مبلغ نهایی قابل پرداخت: ${o.final} تومان\n`;
}

test('full catalog retains every model, actual quantity and unit price in compact lines', () => {
  const o = makeOrder(d.PRODUCTS);
  const lines = o.text.split('\n');
  for (const { product: p, packCount } of o.items) {
    const count = packCount * (p.multiplier || d.BURS_PER_PACK);
    const expected = `${p.model} x ${count} @ ${p.price ?? o.tier.price}`;
    assert.equal(lines.filter(line => line === expected).length, 1, expected);
  }
  const before = urlBytes(legacyMessage(o));
  const after = urlBytes(o.text);
  console.log(`Full catalog (${o.items.length} models): URL ${before} -> ${after} bytes; ${(100 * (1 - after / before)).toFixed(1)}% shorter`);
  assert.ok(after < before * 0.35, 'encoded URL should shrink by at least 65%');
});

test('small order keeps paid shipping and final total', () => {
  const o = makeOrder(d.PRODUCTS.slice(0, 1));
  assert.equal(o.total, 5);
  assert.equal(o.final, 820000);
  assert.ok(o.text.includes('تعداد کل فرزها: 5 عدد'));
  assert.ok(o.text.includes('قیمت پلکانی نقدی هر فرز: 126000 تومان'));
  assert.ok(o.text.includes('هزینه پست (دریافتی پست از ما): 190000 تومان'));
  assert.ok(o.text.includes('مبلغ نهایی قابل پرداخت: 820000 تومان'));
  assert.ok(!o.text.includes('پرداخت قسطی'));
});

test('large installment order preserves fixed prices, quantities, free shipping and terms', () => {
  const o = makeOrder(d.PRODUCTS, 5);
  assert.equal(o.total, 1210);
  assert.equal(o.tier.price, 96000);
  assert.equal(o.final, 123180000);
  assert.ok(o.text.includes('ENDO-Z TI x 5 @ 1500000\n'));
  assert.ok(o.text.includes('EX-11S x 5 @ 96000\n'));
  assert.ok(o.text.includes('TC-26EF x 25 @ 96000\n'));
  assert.ok(o.text.includes('هزینه پست: 0 تومان (رایگان)'));
  assert.ok(o.text.includes('مبلغ نهایی قابل پرداخت: 123180000 تومان'));
  assert.ok(o.text.includes(`🧾 امکان پرداخت قسطی: ${o.tier.installment.price} تومان هر فرز (${o.tier.installment.terms})`));
  assert.equal(new URL(`https://t.me/${d.TELEGRAM_USER}?text=${encodeURIComponent(o.text)}`).searchParams.get('text'), o.text);
  console.log(`Installment order: ${o.total} burs, encoded URL ${urlBytes(o.text)} bytes`);
});

test('all executable inline scripts parse', () => {
  for (const match of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)) {
    if (/type\s*=\s*["']application\/ld\+json["']/.test(match[1])) continue;
    new vm.Script(match[2]);
  }
});
