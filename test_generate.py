import re

import generate_pages as g


def test_slug_map_covers_all_shapes():
    data = g.load_data()
    missing = {p["shape"] for p in data["products"]} - set(g.SLUGS.keys())
    assert not missing, f"missing slugs: {missing}"


def test_no_merge_round_taper_stays_separate():
    groups = g.group_by_page(g.load_data())
    assert "round_taper" in groups and "taper_round_edge" in groups
    assert len(groups["round_taper"]) == 6 and len(groups["taper_round_edge"]) == 2


def test_anchor_ids():
    assert g.anchor_id("TC-21EF") == "tc-21ef"
    assert g.anchor_id("ENDO-Z TI") == "endo-zti"


def test_needle_category_page():
    html = g.build_category_page("needle", g.load_data())
    assert "<h1>" in html and "نیدل" in html
    assert 'id="tc-21ef"' in html                       # anchored model block
    assert "806 314 165 504 014" in html                # ISO in raw HTML
    assert "/index.html#TC-21EF" in html                # buy CTA into SPA
    assert '"ItemList"' in html and '"BreadcrumbList"' in html and '"FAQPage"' in html
    assert 'rel="canonical" href="https://ddsverified.ir/category/needle-burs/"' in html


def test_pointed_cylinder_is_chamfer():
    data = g.load_data()
    assert g.SHAPE_OVERRIDE["pointed_cylinder"]["fa"].startswith("فرز دندانپزشکی شمفر")
    html = g.build_category_page("pointed_cylinder", data)
    assert "CP-12C" in html and "شمفر" in html


def test_every_category_page_has_canonical_and_models():
    data = g.load_data()
    for key in g.group_by_page(data):
        html = g.build_category_page(key, data)
        assert html.count('rel="canonical"') == 1, key
        assert "/index.html#" in html, key              # at least one buy CTA


# ------------------------------------------------ per-product pages (Option A) ----

def test_product_page_url_scheme():
    assert g.product_page_url("TC-21EF") == "product/tc-21ef/"
    assert g.product_page_url("ENDO-Z TI") == "product/endo-zti/"


def test_every_product_page_generated_and_unique_content():
    data = g.load_data()
    models = [p["model"] for p in data["products"]]
    assert len(models) == len(set(models))
    for p in data["products"]:
        html = g.build_product_page(p, data)
        slug = g.anchor_id(p["model"])
        # self-canonical on its own URL
        assert f'rel="canonical" href="https://ddsverified.ir/product/{slug}/"' in html, p["model"]
        # Product JSON-LD with its own price + availability
        assert '"@type":"Product"' in html.replace(" ", "") or '"@type": "Product"' in html, p["model"]
        assert str(p.get("price") or data["price_per_bur"]) in html, p["model"]
        # unique per-model title
        assert p["model"] in html.split("<title>")[1].split("</title>")[0], p["model"]


def test_product_page_json_ld_parses_and_matches_data():
    import json as _json
    data = g.load_data()
    p = next(x for x in data["products"] if x["model"] == "TC-21EF")
    html = g.build_product_page(p, data)
    lds = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    prod = [_json.loads(x) for x in lds if '"Product"' in x]
    assert len(prod) == 1
    assert prod[0]["sku"] == "TC-21EF"
    price = p.get("price") or data["price_per_bur"]
    assert prod[0]["offers"]["price"] == price
    assert prod[0]["url"] == "https://ddsverified.ir/product/tc-21ef/"


def test_category_pages_link_to_product_pages_and_sitemap_lists_them():
    data = g.load_data()
    cat_html = g.build_category_page("needle", data)
    assert '/product/tc-21ef/' in cat_html            # H3 deep link
    sitemap = g.build_sitemap(data)
    assert "<loc>https://ddsverified.ir/product/tc-21ef/</loc>" in sitemap
    assert sitemap.count("product/") == len(data["products"])
