import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

// Shared cart persistence: items survive page changes/refreshes via localStorage.
const html = readFileSync(new URL('./index.html', import.meta.url), 'utf8');
const cartJs = readFileSync(new URL('./assets/cart.js', import.meta.url), 'utf8');
const catalogJs = readFileSync(new URL('./assets/catalog.js', import.meta.url), 'utf8');

function makeCart(dataSource) {
  const store = {};
  const ctx = vm.createContext({
    localStorage: { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } },
  });
  const constStart = cartJs.indexOf('const BURS_PER_PACK');
  const logicEnd = cartJs.indexOf('/* === END CART LOGIC');
  vm.runInContext(dataSource + cartJs.slice(constStart, logicEnd) + `
    let toasts = [];
    cartCountBadge = { classList: { remove() {}, add() {} }, offsetWidth: 0 };
    function updateCart() { saveCart(); }
    function showCartToast(t) { toasts.push(t); }
    globalThis.api = { addToCart, loadCart, getTotalBurs, getCartItems,
      get cart() { return cart; }, set cart(v) { cart = v; }, get toasts() { return toasts; }, PRODUCTS };`, ctx);
  return { api: ctx.api, store };
}

const homeData = html.slice(html.indexOf('const PRODUCTS ='), html.indexOf('let filteredProducts ='));

test('adding saves the cart and a new page restores it', () => {
  const { api, store } = makeCart(homeData);
  api.addToCart('TC-26');
  api.addToCart('TC-26');
  api.addToCart('PACK-400');
  assert.deepEqual(JSON.parse(store.ddsverified_cart_v1), { 'TC-26': 2, 'PACK-400': 1 });
  assert.match(api.toasts[0], /TC-26/);
  api.cart = {};
  api.cart = api.loadCart();
  assert.equal(api.getTotalBurs(), 2 * 5 + 400);
});

test('saved models that no longer exist, are out of stock, or have bad counts are dropped', () => {
  const { api, store } = makeCart(homeData);
  const outOfStock = api.PRODUCTS.find(p => p.model === 'SF-41');
  outOfStock.inventory = 0;
  store.ddsverified_cart_v1 = JSON.stringify({ 'TC-26': 3, 'OLD-MODEL': 2, 'SF-41': 1, 'TC-27': -4, 'TC-21C': 'x' });
  api.cart = api.loadCart();
  assert.deepEqual({ ...api.cart }, { 'TC-26': 3 });
  api.addToCart('SF-41'); // out of stock: ignored
  api.addToCart('NOPE');
  assert.deepEqual({ ...api.cart }, { 'TC-26': 3 });
  assert.equal(api.toasts.length, 0);
});

test('broken storage never breaks the page', () => {
  const { api, store } = makeCart(homeData);
  store.ddsverified_cart_v1 = '{not json';
  assert.deepEqual({ ...api.loadCart() }, {});
});

test('generated catalog.js gives other pages the same products and prices as the homepage', () => {
  const home = makeCart(homeData).api;
  const generated = makeCart(catalogJs).api;
  assert.equal(generated.PRODUCTS.length, home.PRODUCTS.length);
  assert.deepEqual(JSON.parse(JSON.stringify(generated.PRODUCTS)), JSON.parse(JSON.stringify(home.PRODUCTS)));
});
