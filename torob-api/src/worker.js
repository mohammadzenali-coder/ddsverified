/**
 * Torob Product API v3 endpoint for ddsverified.ir — Cloudflare Worker.
 *
 * Serves https://api.ddsverified.ir/torob_api/v3/products by wrapping the
 * static feed published by tools/generate_torob_feed.py
 * (https://ddsverified.ir/torob/products.json) in the v3 envelope, with JWT
 * (EdDSA / ed25519) auth per Torob's token guide (torob_api_token_guide.md).
 *
 * Setup (once):  npx wrangler login
 *                npx wrangler secret put JWT_PUBLIC_KEY
 *                  -> paste the base64 body of Torob's public key:
 *                     MCowBQYDK2VwAyEAt6Mu4T0pBORY11W+QeM35UsmLO3vsf+6yKpFDEImFk0=
 * Test locally:  npx wrangler dev
 * Deploy:        npx wrangler deploy
 */
import { importSPKI, jwtVerify } from 'jose';

const FEED_URL = 'https://ddsverified.ir/torob/products.json';
const API_VERSION = 'torob_api_v3';
const TOKEN_VERSION = '1';
const PAGE_SIZE = 100; // spec §4.1: exactly 100 per page except the last
const ROUTE = '/torob_api/v3/products';
const SORTS = new Set(['date_added_desc', 'date_updated_desc']);
/** Spec §2.2: body is ONE of the three shapes — anything else is a 400. */
const ALLOWED_FIELDS = new Set(['page_urls', 'page_uniques', 'page', 'sort']);

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Accept, X-Torob-Token, X-Torob-Token-Version, Authorization',
};

const CORS_PREFLIGHT = {
  ...CORS,
  'Access-Control-Max-Age': '86400',
};

function json(data, status = 200, headers = CORS) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', ...headers },
  });
}

const badRequest = (error) => json({ error }, 400);

/** Deterministic JSON stringify — used to keep lookup responses byte-stable. */
function stableStringify(x) {
  if (x === null || typeof x !== 'object') return JSON.stringify(x) ?? 'null';
  if (Array.isArray(x)) return `[${x.map(stableStringify).join(',')}]`;
  const entries = Object.keys(x)
    .sort()
    .map((k) => `${JSON.stringify(k)}:${stableStringify(x[k])}`)
    .join(',');
  return `{${entries}}`;
}

/** X-Torob-Token header first; Authorization: Bearer accepted as fallback. */
function bearerToken(request) {
  const torob = request.headers.get('X-Torob-Token');
  if (torob && torob.trim()) return torob.trim();
  const auth = request.headers.get('Authorization') || '';
  const m = /^Bearer\s+(\S+)$/i.exec(auth);
  return m ? m[1] : null;
}

/** Torob's key is stored as the raw base64 SPKI body — wrap it into a PEM. */
const toPem = (b64) => `-----BEGIN PUBLIC KEY-----\n${b64.trim()}\n-----END PUBLIC KEY-----\n`;

/**
 * Verify EdDSA JWT per token guide §5: signature, exp, nbf, aud (aud must
 * equal the API hostname). exp/nbf/aud are enforced by jose; algorithm is
 * pinned so no `alg` confusion is possible.
 */
async function verifyToken(request, env) {
  const fail = (reason, status) => ({ ok: false, reason, status });
  const version = (request.headers.get('X-Torob-Token-Version') || '').trim();
  if (version !== TOKEN_VERSION) {
    return fail(`unsupported X-Torob-Token-Version: ${version || '(missing)'}, expected ${TOKEN_VERSION}`);
  }
  const token = bearerToken(request);
  if (!token) return fail('missing X-Torob-Token header');
  if (!env.JWT_PUBLIC_KEY) return fail('JWT_PUBLIC_KEY secret is not configured on the worker', 500);
  try {
    const key = await importSPKI(toPem(env.JWT_PUBLIC_KEY));
    await jwtVerify(token, key, {
      algorithms: ['EdDSA'],
      audience: new URL(request.url).hostname,
      clockTolerance: 5,
      requiredClaims: ['exp', 'nbf', 'aud'],
    });
    return { ok: true };
  } catch (e) {
    return fail(`invalid token: ${e.message}`);
  }
}

/** Fetch the static feed through Cloudflare's edge cache (1 h TTL). */
async function loadFeed(env, ctx) {
  const cache = caches.default;
  let resp = await cache.match(FEED_URL);
  if (!resp) {
    resp = await fetch(FEED_URL, { cf: { cacheEverything: true, cacheTtl: 3600 } });
    if (!resp.ok) return null;
    resp = new Response(resp.body, resp);
    resp.headers.set('Cache-Control', 'public, max-age=3600');
    ctx.waitUntil(cache.put(FEED_URL, resp.clone()));
  }
  try {
    return await resp.json();
  } catch {
    return null;
  }
}

/** Case-insensitive URL compare: scheme+host(+port if unusual)+path. */
function normalizeUrl(u) {
  try {
    const x = new URL(String(u).trim());
    const port = x.port && x.port !== '80' && x.port !== '443' ? `:${x.port}` : '';
    return `${x.protocol}//${x.hostname.toLowerCase()}${port}${x.pathname.replace(/\/+$/, '')}/`;
  } catch {
    return String(u).trim().toLowerCase().replace(/\/+$/, '') + '/';
  }
}

function parseListParams(body) {
  if (body.page === undefined) return { error: 'page parameter is not provided' };
  if (!Number.isInteger(body.page) || body.page < 1) {
    return { error: 'page parameter must be an integer >= 1' };
  }
  if (body.sort === undefined) return { error: 'sort parameter is not provided' };
  if (typeof body.sort !== 'string' || !SORTS.has(body.sort)) {
    return { error: `sort parameter must be one of: ${[...SORTS].join(', ')}` };
  }
  return { page: body.page, sort: body.sort };
}

function respondList(all, page) {
  const total = all.length;
  const maxPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const products = page > maxPages
    ? []
    : all.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  return json({ api_version: API_VERSION, current_page: page, total, max_pages: maxPages, products });
}

function respondLookup(found) {
  // Spec §5: single-product responses use total=N, max_pages=1, current_page=1.
  return json({ api_version: API_VERSION, current_page: 1, total: found.length, max_pages: 1, products: found });
}

async function handleRequest(request, env, ctx) {
  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: CORS_PREFLIGHT });
  }

  const url = new URL(request.url);
  if (url.pathname.replace(/\/+$/, '') !== ROUTE) {
    return json({ error: 'not found' }, 404);
  }
  if (request.method !== 'POST') {
    return json({ error: 'method not allowed: use POST' }, 405);
  }

  const auth = await verifyToken(request, env);
  if (!auth.ok) return json({ error: `unauthorized: ${auth.reason}` }, auth.status || 401);

  let body;
  try {
    body = await request.json();
  } catch {
    return badRequest('request body must be valid JSON');
  }
  if (body === null || typeof body !== 'object' || Array.isArray(body)) {
    return badRequest('request body must be a JSON object');
  }
  const unknown = Object.keys(body).filter((k) => !ALLOWED_FIELDS.has(k));
  if (unknown.length) return badRequest(`unknown parameters: ${unknown.join(', ')}`);

  const all = await loadFeed(env, ctx);
  if (!Array.isArray(all)) return json({ error: 'product feed temporarily unavailable' }, 503);

  // Index once per request — stableStringify keeps key order deterministic.
  const byUnique = new Map(all.map((p) => [p.page_unique, p]));
  const byUrl = new Map(all.map((p) => [normalizeUrl(p.page_url), p]));

  if (body.page_urls !== undefined || body.page_uniques !== undefined) {
    if (body.page_urls !== undefined && body.page_uniques !== undefined) {
      return badRequest('parameters page_urls and page_uniques are mutually exclusive');
    }
    if (body.page !== undefined || body.sort !== undefined) {
      return badRequest('parameters page/sort cannot be combined with page_urls/page_uniques');
    }
    const wantUrls = body.page_urls !== undefined;
    const items = wantUrls ? body.page_urls : body.page_uniques;
    if (!Array.isArray(items) || items.length === 0 || !items.every((i) => typeof i === 'string' && i.trim() !== '')) {
      return badRequest(`${wantUrls ? 'page_urls' : 'page_uniques'} must be a non-empty array of strings`);
    }
    const seen = new Set();
    const found = [];
    for (const item of items) {
      const key = wantUrls ? normalizeUrl(item) : item.trim();
      if (seen.has(key)) continue; // dedupe within the request
      seen.add(key);
      const p = (wantUrls ? byUrl : byUnique).get(key);
      if (p) found.push(p); // removed/unknown items are silently skipped (spec §4.4)
    }
    return respondLookup(found);
  }

  if (body.page !== undefined || body.sort !== undefined) {
    const { page, sort, error } = parseListParams(body);
    if (error) return badRequest(error);
    if (sort === 'date_updated_desc') {
      const ts = (p) => Date.parse(p.date_updated || p.date_added || '') || 0;
      all.sort((a, b) => ts(b) - ts(a));
    }
    return respondList(all, page);
  }

  return badRequest('no valid parameters: expected page_urls, page_uniques, or page+sort');
}

export default {
  async fetch(request, env, ctx) {
    try {
      return await handleRequest(request, env, ctx);
    } catch (e) {
      return json({ error: `internal error: ${e.message}` }, 500);
    }
  },
};

// Internals exported for tests.
export const _test = { normalizeUrl, stableStringify };
