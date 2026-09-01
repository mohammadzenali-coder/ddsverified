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
- Product: `title, id(=model), price(Toman), category, image(abs), color(grit), guarantee, is_available, url(category page #model-anchor)`
- Source of truth: `products_data.json` (run `tools/extract_products.py` after editing PRODUCTS in index.html)
- Tests: `python -m pytest test_emalls_feed.py test_generate.py`
