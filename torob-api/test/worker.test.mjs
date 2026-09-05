// Node test suite for torob-api/src/worker.js — runs with `npm test`.
// Uses node --test (Node 24+). Mocks fetch + crypto.subtle via the
// Web Crypto API (already available in Node 18+).
import test from 'node:test';
import assert from 'node:assert/strict';
import { generateKeyPair, exportSPKI, SignJWT } from 'jose';
import { _test, default as worker } from '../src/worker.js';

const { normalizeUrl, stableStringify } = _test;

const FEED = [
  { page_unique: 'a', page_url: 'https://ddsverified.ir/product/a/', current_price: 100,
    title: 'A', availability: true, image_links: ['https://ddsverified.ir/images/a.webp'],
    spec: {}, date_added: '2026-08-25T00:15:18+03:30', date_updated: '2026-08-25T00:15:18+03:30' },
  { page_unique: 'b', page_url: 'https://ddsverified.ir/product/b/', current_price: 200,
    title: 'B', availability: true, image_links: ['https://ddsverified.ir/images/b.webp'],
    spec: {}, date_added: '2026-08-25T00:20:18+03:30', date_updated: '2026-08-25T00:20:18+03:30' },
];

// ---------- unit tests ----------
test('normalizeUrl lowercases host and trims trailing slash', () => {
  assert.equal(normalizeUrl('https://DDSVerified.ir/product/A/'), 'https://ddsverified.ir/product/a/');
  assert.equal(normalizeUrl('https://ddsverified.ir/product/a'), 'https://ddsverified.ir/product/a/');
});
test('stableStringify is key-order-independent', () => {
  assert.equal(stableStringify({ b: 1, a: 2 }), stableStringify({ a: 2, b: 1 }));
});

// ---------- handler tests ----------
const BASE = 'https://api.ddsverified.ir/torob_api/v3/products';
let priv, pubPem;

test('setup: generate EdDSA keypair (Torob’s algorithm)', async () => {
  const kp = await generateKeyPair('EdDSA', { crv: 'ed25519', extractable: true });
  priv = kp.privateKey;
  const spki = await exportSPKI(kp.publicKey);
  // strip PEM armor, store raw base64 (matches `wrangler secret put JWT_PUBLIC_KEY` form)
  pubPem = Buffer.from(spki).toString('base64');
});

const signFor = async (claims = {}) => {
  const now = Math.floor(Date.now() / 1000);
  return await new SignJWT({ ...claims })
    .setProtectedHeader({ alg: 'EdDSA', typ: 'JWT', v: 1 })
    .setAudience('api.ddsverified.ir')
    .setExpirationTime(now + 600)
    .setNotBefore(now - 60)
    .sign(priv);
};

function ctx(extra = {}) {
  return {
    request: new Request(BASE, extra),
    env: { JWT_PUBLIC_KEY: pubPem },
    ctx: { waitUntil: () => {} },
    data: { feed: FEED },
  };
}

// patch the worker to use a stub feed instead of fetching ddsverified.ir
async function withFeed(fn) {
  const realFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    if (String(url) === 'https://ddsverified.ir/torob/products.json') {
      return new Response(JSON.stringify(FEED));
    }
    return new Response('not found', { status: 404 });
  };
  try { return await fn(); } finally { globalThis.fetch = realFetch; }
}

const call = (request, env = { JWT_PUBLIC_KEY: pubPem }) =>
  worker.fetch(request, env, { waitUntil: () => {} });

test('CORS preflight returns 204 with the right headers', async () => {
  const r = await call(new Request(BASE, { method: 'OPTIONS' }));
  assert.equal(r.status, 204);
  assert.equal(r.headers.get('Access-Control-Allow-Methods'), 'POST, OPTIONS');
});

test('GET is 405', async () => {
  const r = await call(new Request(BASE, { method: 'GET' }));
  assert.equal(r.status, 405);
});

test('wrong route is 404', async () => {
  const r = await call(new Request('https://api.ddsverified.ir/whatever', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Torob-Token-Version': '1' },
    body: '{}',
  }));
  assert.equal(r.status, 404);
});

test('missing token is 401', async () => {
  const r = await call(new Request(BASE, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ page: 1, sort: 'date_added_desc' }),
  }));
  assert.equal(r.status, 401);
});

test('wrong token version is 401', async () => {
  const t = await signFor();
  const r = await call(new Request(BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Torob-Token-Version': '9', 'X-Torob-Token': t },
    body: JSON.stringify({ page: 1, sort: 'date_added_desc' }),
  }));
  assert.equal(r.status, 401);
  const j = await r.json();
  assert.match(j.error, /X-Torob-Token-Version/);
});

test('list endpoint paginates and sorts by date_added_desc', async () => {
  await withFeed(async () => {
    const tok = await signFor();
    const r = await call(new Request(BASE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Torob-Token-Version': '1', 'X-Torob-Token': tok },
      body: JSON.stringify({ page: 1, sort: 'date_added_desc' }),
    }));
    assert.equal(r.status, 200);
    const j = await r.json();
    assert.equal(j.api_version, 'torob_api_v3');
    assert.equal(j.total, 2);
    assert.equal(j.max_pages, 1);
    assert.equal(j.products[0].page_unique, 'b');
    assert.equal(j.products[1].page_unique, 'a');
  });
});

test('list with no sort is 400', async () => {
  await withFeed(async () => {
    const tok = await signFor();
    const r = await call(new Request(BASE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Torob-Token-Version': '1', 'X-Torob-Token': tok },
      body: JSON.stringify({ page: 1 }),
    }));
    assert.equal(r.status, 400);
    assert.equal((await r.json()).error, 'sort parameter is not provided');
  });
});

test('list with no page is 400', async () => {
  await withFeed(async () => {
    const tok = await signFor();
    const r = await call(new Request(BASE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Torob-Token-Version': '1', 'X-Torob-Token': tok },
      body: JSON.stringify({ sort: 'date_added_desc' }),
    }));
    assert.equal(r.status, 400);
  });
});

test('unknown param is 400', async () => {
  await withFeed(async () => {
    const tok = await signFor();
    const r = await call(new Request(BASE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Torob-Token-Version': '1', 'X-Torob-Token': tok },
      body: JSON.stringify({ page: 1, sort: 'date_added_desc', junk: 1 }),
    }));
    assert.equal(r.status, 400);
  });
});

test('empty body is 400', async () => {
  await withFeed(async () => {
    const tok = await signFor();
    const r = await call(new Request(BASE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Torob-Token-Version': '1', 'X-Torob-Token': tok },
      body: '{}',
    }));
    assert.equal(r.status, 400);
  });
});

test('lookup by page_unique returns the product', async () => {
  await withFeed(async () => {
    const tok = await signFor();
    const r = await call(new Request(BASE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Torob-Token-Version': '1', 'X-Torob-Token': tok },
      body: JSON.stringify({ page_uniques: ['a', 'nope'] }),
    }));
    assert.equal(r.status, 200);
    const j = await r.json();
    assert.equal(j.total, 1);
    assert.equal(j.products[0].page_unique, 'a');
  });
});

test('lookup by page_url normalizes trailing slash and case', async () => {
  await withFeed(async () => {
    const tok = await signFor();
    const r = await call(new Request(BASE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Torob-Token-Version': '1', 'X-Torob-Token': tok },
      body: JSON.stringify({ page_urls: ['HTTPS://DDSVerified.ir/product/B'] }),
    }));
    const j = await r.json();
    assert.equal(j.products[0].page_unique, 'b');
  });
});

test('lookup + list params together is 400', async () => {
  await withFeed(async () => {
    const tok = await signFor();
    const r = await call(new Request(BASE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Torob-Token-Version': '1', 'X-Torob-Token': tok },
      body: JSON.stringify({ page_uniques: ['a'], page: 1 }),
    }));
    assert.equal(r.status, 400);
  });
});
