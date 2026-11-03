/* DDSVerified shared cart: one cart for the homepage, family, category, collection and product pages.
 *
 * Needs these globals, defined BEFORE any cart function runs:
 *   PRODUCTS, SHAPE_MAP, GRIT_TEXT, PRICE_PER_BUR, LIST_PRICE_PER_BUR
 * The homepage defines them inline (index.html is the product source of truth); every generated page
 * loads /assets/catalog.js, which generate_pages.py writes from products_data.json.
 *
 * The cart is saved in localStorage, so it survives page changes and refreshes and stays in sync
 * between tabs. Any element with .add-btn[data-model] or [data-add-to-cart] adds to it; the old
 * deep link /index.html#MODEL keeps working on the homepage.
 */
const BURS_PER_PACK = 5;
const SHIPPING_COST = 190000;
const SHIPPING_LABEL = "هزینه پست";
const FREE_SHIPPING_THRESHOLD = 100;
const TELEGRAM_USER = "ddsverified_admin";
const CART_STORAGE_KEY = "ddsverified_cart_v1";
const GRIT_DISPLAY = {"K⚫":"مشکی ⚫","G🟢":"سبز 🟢","B🔵":"آبی 🔵","R🔴":"قرمز 🔴","Y🟡":"زرد 🟡","W⚪":"سفید ⚪","-":"-"};

let cart = {};
let cartFab, cartCountBadge, cartDrawer, cartOverlay, cartClose, cartBody, cartTotals, cartToast;

function toPersian(num) { return Number(num).toLocaleString('fa-IR'); }
function toPersianDigits(str) { return String(str).replace(/[0-9]/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]); }

function unitPrice(product) {
  return product.price !== undefined ? product.price : PRICE_PER_BUR;
}
function listPrice(product) {
  return product.old_price !== undefined ? product.old_price : LIST_PRICE_PER_BUR;
}
function salePercent(product) {
  return Math.round(100 * (1 - unitPrice(product) / listPrice(product)));
}
// PACK-400 price is for the entire 400-bur bundle.
function bundlePerBur(product) {
  return product.multiplier > 0 ? product.price / product.multiplier : product.price;
}

/* ---------- persistence ---------- */
function loadCart() {
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(CART_STORAGE_KEY) || '{}') || {}; } catch (_) { saved = {}; }
  const clean = {};
  Object.keys(saved).forEach(model => {
    const product = PRODUCTS.find(p => p.model === model);
    const count = parseInt(saved[model], 10);
    if (product && product.inventory > 0 && count >= 1) clean[model] = Math.min(count, 99999);
  });
  return clean;
}
function saveCart() {
  try { localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(cart)); } catch (_) { /* private mode: cart still works for this page */ }
}

/* ---------- cart actions ---------- */
function addToCart(model) {
  const product = PRODUCTS.find(p => p.model === model);
  if (!product || product.inventory <= 0) return;
  cart[model] = (cart[model] || 0) + 1;
  updateCart();
  cartCountBadge.classList.remove('pulse');
  void cartCountBadge.offsetWidth;
  cartCountBadge.classList.add('pulse');
  showCartToast(`${model} به سبد خرید اضافه شد`);
}

function changePackCount(model, delta) {
  cart[model] = (cart[model] || 0) + delta;
  if (cart[model] <= 0) delete cart[model];
  updateCart();
}

function removeItem(model) { delete cart[model]; updateCart(); }

function getCartItems() {
  return Object.keys(cart).map(model => {
    const product = PRODUCTS.find(p => p.model === model);
    return product ? { product, packCount: cart[model] } : null;
  }).filter(Boolean);
}

function isFreeShipItem(p) { return p.free_shipping === true; }
function getTotalBurs() {
  return getCartItems().reduce((sum, item) => sum + item.packCount * (item.product.multiplier || BURS_PER_PACK), 0);
}

function updateCart() {
  saveCart();
  const items = getCartItems();
  const totalBurs = getTotalBurs();
  const totalPacks = items.reduce((s, i) => s + i.packCount, 0);

  if (totalPacks > 0) {
    cartCountBadge.textContent = toPersian(totalPacks);
    cartCountBadge.style.display = 'flex';
  } else {
    cartCountBadge.style.display = 'none';
  }

  if (items.length === 0) {
    cartBody.innerHTML = `
      <div class="cart-empty">
        <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
          <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
        </svg>
        <p>سبد خرید شما خالی است.</p>
        <p style="font-size:.78rem;margin-top:6px;">برای افزودن فرز، روی دکمه «افزودن به سبد» کلیک کنید.</p>
      </div>`;
    cartTotals.innerHTML = '';
    cartDrawer.classList.remove('checkout-open');
    return;
  }

  const subtotal = items.reduce((sum, item) => {
    const burCount = item.packCount * (item.product.multiplier || BURS_PER_PACK);
    return sum + (item.product.bundle ? item.packCount * item.product.price : burCount * unitPrice(item.product));
  }, 0);
  const freeShipUnlocked = totalBurs >= FREE_SHIPPING_THRESHOLD || items.some(i => isFreeShipItem(i.product));
  const effectiveShipping = freeShipUnlocked ? 0 : SHIPPING_COST;
  const finalTotal = subtotal + effectiveShipping;

  const itemsHTML = items.map(item => {
    const { product, packCount } = item;
    const mult = product.multiplier || BURS_PER_PACK;
    const burCount = packCount * mult;
    const shapeName = SHAPE_MAP[product.shape] || product.shape;
    const gritDisp = GRIT_DISPLAY[product.grit] || product.grit;
    return `
      <div class="cart-item">
        <div class="cart-item-line1">${product.bundle
          ? `${product.card_title || shapeName} <span class="cart-item-model">${product.model}</span>`
          : `${toPersian(burCount)} عدد ${shapeName} قطر ${toPersianDigits(product.diameter)} دور ${gritDisp} <span class="cart-item-model">${product.model}</span>`}</div>
        <div class="cart-item-line2">${product.bundle
          ? `${toPersian(packCount)} بسته × ${toPersian(product.price)} تومان (هر بسته ${toPersian(mult)} عدد)`
          : `${toPersian(burCount)} × ${toPersian(unitPrice(product))} تومان`}</div>
        <div class="cart-item-controls">
          <div class="stepper">
            <button class="step-btn" data-model="${product.model}" data-delta="-1" aria-label="کاهش تعداد">−</button>
            <input class="step-input" type="text" inputmode="numeric" dir="ltr" value="${toPersianDigits(packCount)}" data-model="${product.model}" aria-label="تعداد بسته: عدد را دستی وارد کنید" title="تعداد بسته را دستی وارد کنید (هر بسته ${toPersian(mult)} عدد)">
            <button class="step-btn" data-model="${product.model}" data-delta="1" aria-label="افزایش تعداد">+</button>
          </div>
          <button class="cart-item-remove" data-model="${product.model}" data-action="remove">حذف</button>
        </div>
      </div>`;
  }).join('');

  const listScroll = cartBody.scrollTop;
  cartBody.innerHTML = itemsHTML;
  cartBody.scrollTop = listScroll;

  const shippingRowHTML = freeShipUnlocked
    ? `<div class="total-row shipping free"><span>${SHIPPING_LABEL}</span><span><span class="ship-original">${toPersian(SHIPPING_COST)} تومان</span><span class="ship-free">رایگان 🎁</span></span></div>`
    : `<div class="total-row shipping"><span>${SHIPPING_LABEL}</span><span>${toPersian(SHIPPING_COST)} تومان</span></div>`;

  const checkoutWasOpen = cartTotals.querySelector('.cart-checkout')?.open || false;
  cartTotals.innerHTML = `
    <details class="cart-checkout" id="cartCheckout">
      <summary class="cart-checkout-summary"><span>مبلغ نهایی</span><strong>${toPersian(finalTotal)} تومان</strong><span class="cart-expand-label">جزئیات و ثبت سفارش</span></summary>
      <div class="cart-checkout-content">
        <div class="total-row total-burs"><span>🔢 تعداد کل فرزها</span><span>${toPersian(totalBurs)} عدد</span></div>
        <div class="total-row"><span>مبلغ محصولات</span><span>${toPersian(subtotal)} تومان</span></div>
        ${shippingRowHTML}
        <p class="cart-support">برای سفارش های بالاتر و مشاوره دقیق تر با دندانپزشک مجموعه، بر روی <a href="https://t.me/ddsverified_admin" target="_blank" rel="noopener noreferrer">پشتیبانی</a> کلیک کنید.</p>
        <button type="button" class="copy-order-btn" id="copyOrderBtn">برای کپی کردن لیست خرید کلیک کنید</button>
        <p class="copy-feedback" id="copyFeedback" role="status" aria-live="polite"></p>
        <div class="checkout-buttons">
          <button class="checkout-btn telegram" id="telegramBtn">تکمیل سفارش در تلگرام</button>
          <button class="checkout-btn bale" id="baleBtn">سفارش از طریق بله</button>
          <button class="checkout-btn rubika" id="rubikaBtn">سفارش از طریق روبیکا</button>
        </div>
        <p class="checkout-note">لیست کپی‌شده را در پیام‌رسان دلخواه بفرستید؛ یا تماس بگیرید: <a href="tel:+989999587786" dir="ltr">+989999587786</a></p>
        <details class="manual-order"><summary>مشاهده متن سفارش برای کپی دستی</summary><textarea id="checkoutMessage" class="checkout-message" readonly aria-label="متن سفارش برای کپی"></textarea></details>
      </div>
    </details>`;
  const checkoutPanel = document.getElementById('cartCheckout');
  checkoutPanel.open = checkoutWasOpen;
  cartDrawer.classList.toggle('checkout-open', checkoutWasOpen);
  const checkoutLabel = checkoutPanel.querySelector('.cart-expand-label');
  checkoutLabel.textContent = checkoutWasOpen ? 'بستن جزئیات و ثبت سفارش' : 'جزئیات و ثبت سفارش';
  checkoutPanel.addEventListener('toggle', () => {
    cartDrawer.classList.toggle('checkout-open', checkoutPanel.open);
    checkoutLabel.textContent = checkoutPanel.open ? 'بستن جزئیات و ثبت سفارش' : 'جزئیات و ثبت سفارش';
    if (!checkoutPanel.open) cartTotals.scrollTop = 0;
  });
  const orderText = () => generateOrderMessage(items, totalBurs, finalTotal, freeShipUnlocked);
  document.getElementById('checkoutMessage').value = orderText();
  document.getElementById('copyOrderBtn').addEventListener('click', async () => {
    const feedback = document.getElementById('copyFeedback');
    const message = orderText();
    let copied = false;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(message);
        copied = true;
      }
    } catch (_) { /* use the legacy fallback below */ }
    if (!copied) {
      const helper = document.createElement('textarea');
      helper.value = message;
      helper.style.cssText = 'position:fixed;left:-9999px;top:0;';
      document.body.appendChild(helper);
      helper.focus(); helper.select();
      try { copied = document.execCommand('copy'); } catch (_) { copied = false; }
      helper.remove();
    }
    if (copied) {
      feedback.textContent = 'لیست خرید شما ذخیره شد, به یکی از کانال های ارتباطی مراجعه کنید و لیست خرید را بفرستید';
    } else {
      feedback.textContent = 'کپی خودکار انجام نشد. متن سفارش را باز کنید و دستی کپی کنید.';
      document.querySelector('.manual-order').open = true;
    }
    feedback.scrollIntoView({ block: 'nearest' });
  });
  function openCheckout(url, channel) {
    window.open(url, '_blank', 'noopener,noreferrer');
    if (typeof window.cfTrack === 'function') window.cfTrack(`checkout_${channel}`, { total_burs: totalBurs });
  }
  document.getElementById('telegramBtn').addEventListener('click', () => openCheckout(`https://t.me/${TELEGRAM_USER}`, 'telegram'));
  document.getElementById('baleBtn').addEventListener('click', () => openCheckout('https://ble.ir/ddsverified_admin', 'bale'));
  document.getElementById('rubikaBtn').addEventListener('click', () => openCheckout('https://rubika.ir/ddsverified_admin', 'rubika'));
}

function generateOrderMessage(items, totalBurs, finalTotal, freeShipUnlocked) {
  let msg = 'سلام\nسفارش فرز:\nمدل x تعداد عدد @ قیمت واحد (تومان)\n\n';
  items.forEach(({ product, packCount }) => {
    const burCount = packCount * (product.multiplier || BURS_PER_PACK);
    if (product.bundle) {
      msg += `${product.model} x ${packCount} بسته = ${packCount * product.price} تومان (ارسال رایگان)\n`;
    } else {
      msg += `${product.model} x ${burCount} @ ${unitPrice(product)}\n`;
    }
  });
  msg += `\nتعداد کل فرزها: ${totalBurs} عدد\n`;
  msg += `هزینه پست: ${freeShipUnlocked ? '0 (رایگان)' : SHIPPING_COST} تومان\n`;
  msg += `مبلغ نهایی قابل پرداخت: ${finalTotal} تومان\n`;
  return msg;
}

/* ورود دستی تعداد بسته با کیبورد — اعداد فارسی/عربی/لاتین را می‌پذیرد */
function parsePackCount(str) {
  const fa = '۰۱۲۳۴۵۶۷۸۹', ar = '٠١٢٣٤٥٦٧٨٩';
  const latin = String(str)
    .replace(/[۰-۹]/g, d => fa.indexOf(d))
    .replace(/[٠-٩]/g, d => ar.indexOf(d))
    .replace(/[^0-9]/g, '');
  if (!latin) return null;
  const n = parseInt(latin, 10);
  return n >= 1 ? n : null;
}
/* === END CART LOGIC (tests slice up to here) === */

/* ---------- drawer UI ---------- */
const CART_UI_HTML = `
<button class="cart-fab" id="cartFab" aria-label="باز کردن سبد خرید">
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
    <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
  </svg>
  <span class="cart-count-badge" id="cartCountBadge" style="display:none;" aria-live="polite">۰</span>
</button>
<div class="cart-overlay" id="cartOverlay"></div>
<aside class="cart-drawer" id="cartDrawer" role="dialog" aria-label="سبد خرید">
  <div class="cart-header">
    <h2>سبد خرید</h2>
    <button class="cart-close" id="cartClose" aria-label="بستن سبد خرید">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
      </svg>
    </button>
  </div>
  <div class="cart-body" id="cartBody"></div>
  <div class="cart-totals" id="cartTotals"></div>
</aside>
<div class="cart-toast" id="cartToast" role="status" aria-live="polite" hidden></div>`;

function openCart() { cartDrawer.classList.add('open'); cartOverlay.classList.add('open'); }
function closeCart() { cartDrawer.classList.remove('open'); cartOverlay.classList.remove('open'); }

let cartToastTimer = null;
function showCartToast(text) {
  if (!cartToast) return;
  cartToast.innerHTML = `<span>✓ ${text}</span><button type="button" class="cart-toast-open">مشاهده سبد</button>`;
  cartToast.hidden = false;
  clearTimeout(cartToastTimer);
  cartToastTimer = setTimeout(() => { cartToast.hidden = true; }, 2600);
}

/* Deep link: older pages and shared links point to /index.html#MODEL. Add it once, then drop the
   hash so a refresh does not add the same bur again (the cart is saved now). */
function handleCartHash() {
  const model = decodeURIComponent(window.location.hash.replace('#', '')).trim();
  if (!model) return;
  const product = PRODUCTS.find(p => p.model === model);
  if (!product) return;
  setTimeout(() => {
    const btn = document.querySelector(`.add-btn[data-model="${CSS.escape(model)}"]`);
    if (btn) btn.closest('.product-card')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, 300);
  if (product.inventory > 0) {
    addToCart(product.model);
    openCart();
  }
  history.replaceState(null, '', window.location.pathname + window.location.search);
}

function initCart() {
  if (!document.getElementById('cartFab')) document.body.insertAdjacentHTML('beforeend', CART_UI_HTML);
  cartFab = document.getElementById('cartFab');
  cartCountBadge = document.getElementById('cartCountBadge');
  cartDrawer = document.getElementById('cartDrawer');
  cartOverlay = document.getElementById('cartOverlay');
  cartClose = document.getElementById('cartClose');
  cartBody = document.getElementById('cartBody');
  cartTotals = document.getElementById('cartTotals');
  cartToast = document.getElementById('cartToast');

  cart = loadCart();
  updateCart();

  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.add-btn[data-model], [data-add-to-cart]');
    if (btn) {
      e.preventDefault();
      if (!btn.disabled) addToCart(btn.dataset.model || btn.dataset.addToCart);
      return;
    }
    if (e.target.closest('.cart-toast-open')) { cartToast.hidden = true; openCart(); }
  });

  cartBody.addEventListener('click', (e) => {
    const stepBtn = e.target.closest('.step-btn');
    if (stepBtn) { changePackCount(stepBtn.dataset.model, parseInt(stepBtn.dataset.delta)); return; }
    const removeBtn = e.target.closest('.cart-item-remove');
    if (removeBtn) removeItem(removeBtn.dataset.model);
  });
  cartBody.addEventListener('change', (e) => {
    const inp = e.target.closest('.step-input');
    if (!inp) return;
    const model = inp.dataset.model;
    const parsed = parsePackCount(inp.value);
    if (parsed === null || parsed === cart[model]) { updateCart(); return; } // نامعتبر/بدون تغییر → بازگردانی مقدار قبلی
    cart[model] = Math.min(parsed, 99999);
    updateCart();
  });
  cartBody.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target.closest('.step-input')) { e.target.blur(); e.preventDefault(); }
  });

  cartFab.addEventListener('click', openCart);
  cartClose.addEventListener('click', closeCart);
  cartOverlay.addEventListener('click', closeCart);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && cartDrawer.classList.contains('open')) closeCart(); });

  // Another tab changed the cart: show the same items here.
  window.addEventListener('storage', (e) => { if (e.key === CART_STORAGE_KEY) { cart = loadCart(); updateCart(); } });
  // Back/forward cache restores an old snapshot: re-read the saved cart.
  window.addEventListener('pageshow', (e) => { if (e.persisted) { cart = loadCart(); updateCart(); if (window.location.hash) handleCartHash(); } });
  window.addEventListener('hashchange', handleCartHash);
  if (window.location.hash) handleCartHash();
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initCart);
else initCart();
