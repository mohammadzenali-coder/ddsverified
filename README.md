# ddsverified.ir - مرکز تخصصی فرزهای دندانپزشکی
Deployed via GitHub Pages -> https://ddsverified.ir

Obviously made by GLM5.3 , Narrated by me.
why should i reinvent wheels?

## Emalls.ir product feed (اتصال به ایمالز)

Regenerated automatically by `.github/workflows/regenerate.yml` whenever
`index.html` / `products_data.json` / posts change. Manual: `python tools/generate_emalls_feed.py`

- Endpoint (Emalls spec: page/item_per_page query supported): `https://ddsverified.ir/emalls/list.json`
  - Page N: `https://ddsverified.ir/emalls/list-<N>.json` (only emitted when data exceeds 50 items)
- Schema: `{success, products[], total_items, pages_count, item_per_page, page_num}`
- Product: `title, id(=model), price(Toman), category, image(abs), color(grit ring), guarantee, is_available, url(per-product page /product/<slug>/)`
- Per-product static pages: `https://ddsverified.ir/product/<anchor-slug>/` (Torob-compatible crawlable URLs; full specs + Product JSON-LD + self-canonical) — listed in sitemap.xml
- Source of truth: `products_data.json` (run `tools/extract_products.py` after editing PRODUCTS in index.html)
- Tests: `python -m pytest test_emalls_feed.py test_generate.py`

## Local CMS (localhost only)

A dead-simple, browser-based editor for the `PRODUCTS` array in `index.html`.
Runs on `127.0.0.1:8765`, no auth, no DB. Edits a form → rewrites the JS block
surgically → runs the existing pipeline → commits → pushes to GitHub Pages.

**Launch:** double-click `cms.bat` (or run `python cms.py`). Browser opens to
<http://127.0.0.1:8765/>.

**Features:**
- Add / edit / delete products through a modal form (keyboard: `Esc` close, `Ctrl+S` save in form)
- Search box (filters table; submit unchanged is a no-op)
- Diff preview before publish: shows `+ N added • ~ N edited • - N deleted` in color-coded rows
- Live log panel streams every pipeline step (extract → generate → emalls → torob → pytest → git)
- Backups of `index.html` to `.cms-backups/index.html.<timestamp>` (auto-pruned to 20)
- Auto `git pull --rebase` if the CI bot raced you before push
- Tests must pass before push — never pushes a broken build

**Files (CMS-only, never touches site code outside PRODUCTS):**
- `cms.py` — server + UI + pipeline runner
- `cms.bat` — Windows launcher
- `tools/serialize_products.py` — surgical rewriter (also covered by `test_cms_rewrite.py`)
- `test_cms_rewrite.py` — proves the rewrite leaves `index.html` byte-identical outside PRODUCTS

**Hard rules** (per `ddsverified-pipeline` skill):
- Source of truth stays `PRODUCTS` in `index.html`. CMS edits **only** that block.
- Never hand-edit `products_data.json`, `category/*`, `product/*`, feeds, sitemap — all generated.
- Site deploys ~60-90s after `git push` lands.
