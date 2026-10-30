import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const html = readFileSync(new URL('./index.html', import.meta.url), 'utf8');
const elements = Object.fromEntries(['cartCheckout', 'checkoutMessage', 'copyOrderBtn', 'copyFeedback', 'telegramBtn', 'baleBtn', 'rubikaBtn']
  .map(id => [id, { open: false, value: '', textContent: '', events: {},
    addEventListener(type, handler) { this.events[type] = handler; }, scrollIntoView() {},
  }]));
const checkoutLabel = { textContent: '' };
elements.cartCheckout.querySelector = () => checkoutLabel;
const drawerClasses = new Set();
const cartDrawer = { classList: {
  toggle(name, on) { on ? drawerClasses.add(name) : drawerClasses.delete(name); },
  remove(name) { drawerClasses.delete(name); },
} };
const cartBody = { innerHTML: '', scrollTop: 35 };
const cartTotals = { innerHTML: '', scrollTop: 0, querySelector: () => cartTotals.innerHTML ? elements.cartCheckout : null };
const cartCountBadge = { style: {}, textContent: '' };
let clipboardValue = '';
const ctx = vm.createContext({ cartBody, cartTotals, cartDrawer, cartCountBadge,
  document: { getElementById: id => elements[id],
    body: { appendChild() {} },
    createElement: () => ({ style: {}, focus() {}, select() {}, remove() {} }),
    execCommand: () => true,
    querySelector: () => ({ open: false }),
  },
  navigator: { clipboard: { async writeText(text) { clipboardValue = text; } } },
  window: { open() {} },
});
const dataStart = html.indexOf('const PRODUCTS =');
const dataEnd = html.indexOf('let cart =', dataStart);
const updateStart = html.indexOf('function updateCart()');
const updateEnd = html.indexOf("productGrid.addEventListener('click'", updateStart);
vm.runInContext(html.slice(dataStart, dataEnd) + `
const chosen = PRODUCTS.find(p => p.model === 'TC-26');
function getCartItems(){return [{product: chosen, packCount: 1}];}
function getTotalBurs(){return 5;}
function isFreeShipItem(p){return p.free_shipping === true;}
function unitPrice(p){return p.price ?? PRICE_PER_BUR;}
function toPersian(n){return Number(n).toLocaleString('fa-IR');}
function toPersianDigits(s){return String(s).replace(/[0-9]/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);}
` + html.slice(updateStart, updateEnd) + 'globalThis.updateCart = updateCart;', ctx);

test('list owns at least 70% of cart and checkout is collapsed by default', () => {
  ctx.updateCart();
  assert.match(html, /\.cart-body\{flex:1 1 auto;min-height:70%;overflow-y:auto/);
  assert.match(html, /\.cart-totals\{[^}]*max-height:calc\(30% - 56px\)/);
  assert.match(html, /\.cart-drawer\.checkout-open \.cart-totals\{flex:0 0 70%;max-height:70%\}/);
  assert.match(html, /\.cart-expand-label\{[^}]*color:#c62828;font-weight:800/);
  assert.match(cartTotals.innerHTML, /<details class="cart-checkout"/);
  assert.equal(elements.cartCheckout.open, false);
  assert.equal(checkoutLabel.textContent, 'جزئیات و ثبت سفارش');
  assert.match(cartBody.innerHTML, /TC-26/);
  assert.ok(!cartBody.innerHTML.includes('free-ship-gamify'));
  assert.equal(cartBody.scrollTop, 35);
});

test('checkout expands to 70% and collapses back to the product list', () => {
  ctx.updateCart();
  elements.cartCheckout.open = true;
  elements.cartCheckout.events.toggle();
  assert.ok(drawerClasses.has('checkout-open'));
  assert.equal(checkoutLabel.textContent, 'بستن جزئیات و ثبت سفارش');
  ctx.updateCart(); // Quantity changes must not collapse checkout.
  assert.equal(elements.cartCheckout.open, true);
  elements.cartCheckout.open = false;
  elements.cartCheckout.events.toggle();
  assert.ok(!drawerClasses.has('checkout-open'));
  assert.equal(checkoutLabel.textContent, 'جزئیات و ثبت سفارش');
});

test('copy button precedes messenger buttons and copies the current order', async () => {
  ctx.updateCart();
  assert.ok(cartTotals.innerHTML.indexOf('id="copyOrderBtn"') < cartTotals.innerHTML.indexOf('id="telegramBtn"'));
  await elements.copyOrderBtn.events.click();
  assert.match(clipboardValue, /TC-26 x 5 @ 204300/);
  assert.equal(elements.copyFeedback.textContent,
    'لیست خرید شما ذخیره شد, به یکی از کانال های ارتباطی مراجعه کنید و لیست خرید را بفرستید');
});

test('copy falls back when clipboard API is blocked', async () => {
  ctx.navigator.clipboard.writeText = async () => { throw new Error('clipboard unavailable'); };
  ctx.updateCart();
  await elements.copyOrderBtn.events.click();
  assert.match(elements.copyFeedback.textContent, /لیست خرید شما ذخیره شد/);
});
