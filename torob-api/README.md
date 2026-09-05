# Torob Product API v3 — ddsverified.ir

This directory is the Cloudflare Worker that serves the **Torob Product API v3**
endpoint for ddsverified.ir.

- **Endpoint URL (production)**: `https://api.ddsverified.ir/torob_api/v3/products`
- **Method**: `POST` (only)
- **Content-Type**: `application/json`
- **Auth headers (every request)**:
  - `X-Torob-Token: <JWT>` (EdDSA / ed25519, signed with Torob's private key)
  - `X-Torob-Token-Version: 1`

See <https://github.com/Torob/Torob-Sync/blob/main/product_api_v3.md> and
<…/torob_api_token_guide.md> for the full spec.

## Architecture

```
                        GitHub Pages (static)
  ddsverified.ir/torob/products.json  ←── tools/generate_torob_feed.py
                        │
                        │  fetched (edge-cached 1h)
                        ▼
  Cloudflare Worker (api.ddsverified.ir)
    ├─ EdDSA JWT verify (jose, pub key from `wrangler secret`)
    ├─ v3 envelope + pagination (100/page)
    ├─ sort: date_added_desc / date_updated_desc
    └─ page_urls / page_uniques lookup
                        │
                        ▼
                  Torob (https://torob.ir)
```

The Worker doesn't store anything; the backing product list is a static JSON
file regenerated on every push by `.github/workflows/regenerate.yml`.

## Setup (one-time)

From this directory (`torob-api/`):

```bash
npm install
npx wrangler login
npx wrangler secret put JWT_PUBLIC_KEY
#   paste the base64 body of Torob's public key:
#   MCowBQYDK2VwAyEAt6Mu4T0pBORY11W+QeM35UsmLO3vsf+6yKpFDEImFk0=
npx wrangler deploy
```

`wrangler deploy` will:
- create the Worker in your Cloudflare account
- attach it as a custom domain on `api.ddsverified.ir` (DNS + cert are auto)

If your zone is in another account, drop the `routes` block in `wrangler.toml`
and use the `*.workers.dev` URL `wrangler deploy` prints.

## Local dev

```bash
npm test                 # node --test (no Cloudflare account needed)
npx wrangler dev         # live server, hit POST to http://127.0.0.1:8787/...
```

## Tests

- `npm test` exercises the Worker end-to-end: auth, pagination, lookup,
  error paths. Uses an in-memory keypair and a stubbed `fetch` for the
  static feed.
- Python tests for the static feed live in `../test_torob_feed.py`.
- All three test files (emalls + torob + generate) pass together via
  `python -m pytest` from the repo root.

## Send this to Torob

Email / DM them:

> Endpoint: `https://api.ddsverified.ir/torob_api/v3/products`
> Method: `POST`, Content-Type: `application/json`
> Auth: `X-Torob-Token` (EdDSA/ed25519 JWT, audience `api.ddsverified.ir`) +
> `X-Torob-Token-Version: 1` — verify signature with your own public key.
> Total products: 50
> Sample page_url: `https://ddsverified.ir/product/tc-21ef/`
> Sample page_unique: `tc-21ef`
> `date_added_desc` and `date_updated_desc` both supported.

## Code map

- `src/worker.js` — the only source file. Exports default fetch + `_test`.
- `wrangler.toml` — Worker name, custom domain, JWT secret binding.
- `test/worker.test.mjs` — Node `node --test` suite.
- `package.json` — `npm test`, `npm run dev`, `npm run deploy`.
