import json
import re

import generate_pages as g
from tools import extract_products as extractor


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
    assert prod[0]["offers"]["price"] == price * 10  # structured data is IRR; displayed prices are toman
    assert prod[0]["url"] == "https://ddsverified.ir/product/tc-21ef/"


def test_category_pages_link_to_product_pages_and_sitemap_lists_them():
    data = g.load_data()
    cat_html = g.build_category_page("needle", data)
    assert '/product/tc-21ef/' in cat_html            # H3 deep link
    sitemap = g.build_sitemap(data)
    assert "<loc>https://ddsverified.ir/product/tc-21ef/</loc>" in sitemap
    # campaign bundles have a noindex landing page, not a sitemap /product/ entry
    indexed = [p for p in data["products"] if not p.get("bundle")]
    assert sitemap.count("product/") == len(indexed)


def test_generated_pages_have_site_brand_search_and_contacts():
    data = g.load_data()
    pages = [g.build_category_page("needle", data),
             g.build_product_page(next(p for p in data["products"] if p["model"] == "TC-21EF"), data),
             g.build_collection_page("fixed_prostho", data),
             g.build_blog_index(g.load_posts())]
    for html in pages:
        assert 'src="https://ddsverified.ir/logo-wordmark.webp"' in html
        assert 'rel="icon" type="image/webp" href="https://ddsverified.ir/logo-wordmark-square.webp"' in html
        assert 'property="og:image" content="https://ddsverified.ir/logo-wordmark-square.webp"' in html
        assert '<form class="site-search" action="/" method="get" role="search">' in html
        assert 'name="q"' in html
        for url in ("tel:+989999587786", "sms:+989999587786",
                    "https://t.me/ddsverified_admin", "https://ble.ir/ddsverified_admin",
                    "https://rubika.ir/ddsverified_admin"):
            assert f'href="{url}"' in html


def test_category_grit_order_and_copy():
    data = g.load_data()
    html = g.build_category_page("needle", data)
    grit_html = html.split('class="grits">', 1)[1].split('</p>', 1)[0]
    labels = re.findall(r'<span>(.*?)</span>', grit_html)
    assert labels == ["مشکی", "سبز", "آبی", "قرمز", "زرد", "سفید"]
    for group in (g.group_by_page(data).values(), [g.collection_products(data, "fixed_prostho")]):
        for products in group:
            assert products == sorted(products, key=g.grit_sort_key)
    assert "قیمت پلکانی چگونه محاسبه می‌شود؟" not in html
    assert "تست‌شده توسط دندانپزشک" not in html


def test_blog_article_removes_personal_author_and_retired_claims():
    posts = g.load_posts()
    for post in posts:
        html = g.build_post_page(post)
        assert "دکتر محمدرضا زینلی" not in html
        assert '"author": {"@type": "Organization", "name": "DDSVerified"}' in html
        assert "قیمت پلکانی" not in html
        assert "تست و بررسی و آزمایش" not in html


def test_campaign_shows_real_savings_without_endorsements(tmp_path, monkeypatch):
    data = g.load_data()
    bundle = next(p for p in data["products"] if p.get("bundle"))
    monkeypatch.chdir(tmp_path)  # never overwrite the checked-in generated landing page
    assert g.build_campaign_page(bundle, data)
    html = (tmp_path / "campaign" / "pack-400" / "index.html").read_text(encoding="utf-8")
    assert 'property="og:image" content="https://ddsverified.ir/logo-wordmark-square.webp"' in html
    assert "حدود ۲۱٪ کمتر" in html and "۱۲٪" not in html
    assert "۸۰ درصد" not in html and "تست شده توسط دندانپزشک" not in html


def test_extractor_reads_list_and_current_prices_without_writing_files():
    html = """
    const LIST_PRICE_PER_BUR = 227000;
    const PRICE_PER_BUR = 215650;
    const SHAPE_MAP = {needle: "نیدل"};
    const GRIT_TEXT = {"Y🟡": "زرد"};
    const PRODUCTS = [{model: "TC-21EF", old_price: 233000, price: 221350}];
    """
    data = extractor.extract(html)
    assert data["old_price_per_bur"] == 227000
    assert data["price_per_bur"] == 215650
    assert data["products"][0]["old_price"] == 233000


def test_discount_display_uses_product_reference_or_catalog_fallback():
    data = g.load_data().copy()
    data.update(price_per_bur=215650, old_price_per_bur=227000)
    default = next(p for p in data["products"] if not p.get("price") and not p.get("bundle"))
    overridden = next(p for p in data["products"] if p["model"] == "TC-21EF").copy()
    overridden.update(price=221350, old_price=233000)
    endo = next(p for p in data["products"] if p["model"] == "ENDO-Z TI").copy()
    endo.update(price=1500000, old_price=1580000)
    for p, current, previous in ((default, 215650, 227000),
                                 (overridden, 221350, 233000),
                                 (endo, 1500000, 1580000)):
        block = g._model_block(p, "آزمایشی", data)
        page = g.build_product_page(p, data)
        for html in (block, page):
            assert f'{g.fmt_price(current)} تومان' in html
            assert f'<del class="old-price">{g.fmt_price(previous)} تومان</del>' in html
            assert '<span class="discount-badge">۵٪ تخفیف</span>' in html
        ld = [json.loads(x) for x in re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', page, re.S)]
        assert next(x for x in ld if x.get("@type") == "Product")["offers"]["price"] == current * 10
    data["products"] = [default, overridden, endo]
    for html in (g.build_category_page("needle", data),
                 g.build_collection_page("restorative", data)):
        assert f'<del class="old-price">{g.fmt_price(233000)} تومان</del>' in html
        assert '<span class="discount-badge">۵٪ تخفیف</span>' in html
        ld = [json.loads(x) for x in re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
        itemlist = next(x for x in ld if x.get("@type") == "ItemList")
        item = next(x["item"] for x in itemlist["itemListElement"] if x["item"]["sku"] == "TC-21EF")
        assert item["offers"]["price"] == 221350 * 10
    # No fabricated discount when the reference is absent or no longer higher.
    assert '<del' not in g.price_html({"price": 220000}, {"price_per_bur": 220000})
    assert '<del' not in g.price_html({"price": 230000}, data)


def test_campaign_displays_bundle_reference_and_saves_against_discounted_default(tmp_path, monkeypatch):
    data = g.load_data().copy()
    data.update(price_per_bur=215650, old_price_per_bur=227000)
    bundle = next(p for p in data["products"] if p.get("bundle")).copy()
    bundle.update(price=64872000, old_price=72080000)
    monkeypatch.chdir(tmp_path)
    assert g.build_campaign_page(bundle, data)
    html = (tmp_path / "campaign" / "pack-400" / "index.html").read_text(encoding="utf-8")
    assert f'<del class="old-price">{g.fmt_price(72080000)} تومان</del>' in html
    assert '<span class="discount-badge">۱۰٪ تخفیف</span>' in html
    assert 'حدود ۲۵٪ کمتر' in html
    assert '.cmp-price .discount-badge{font-size:.85rem;color:#fff;background:#cc3333' in html
    product = next(json.loads(x) for x in re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        if json.loads(x).get("@type") == "Product")
    assert product["offers"]["price"] == 64872000 * 10


def test_discount_labels_use_persian_red():
    data = g.load_data()
    page = g.build_product_page(next(p for p in data["products"] if p["model"] == "TC-21EF"), data)
    assert ".discount-badge{font-size:.75rem;color:#fff;background:#cc3333" in page
    assert "color:#2e7d32;background:#e8f5e9;border-radius:12px;padding:2px 8px" not in page


def test_home_slider_heading_links_to_blog():
    html = g.build_home_slider(g.load_posts())
    assert '<a class="blogs-head-link" href="/blog/"' in html
    assert "مقالات تخصصی و یافته‌ها" in html and "Drs' Choice" in html


def test_blog_markdown_citations_and_refs():
    html = g.md_to_html("متن[1] و [لینک](https://example.org).\n\n[1] Author A. Title. *Journal*. 2020.")
    assert '<sup class="cite"><a href="#ref-1"' in html
    assert '<p class="ref" id="ref-1" dir="ltr">[1] Author A.' in html
    assert 'href="https://example.org" target="_blank" rel="noopener"' in html


def test_every_blog_post_starts_with_faq_and_cites_only_listed_sources():
    posts = g.load_posts()
    assert len(posts) == 7
    for post in posts:
        items, rest = g.extract_faq(post["body"])
        assert len(items) >= 4, post["slug"]
        assert g.FAQ_HEADING not in rest
        html = g.build_post_page(post)
        article = html.split('<article class="post">', 1)[1]
        assert article.startswith('\n<section class="faq" id="faq">'), post["slug"]
        assert '"@type": "FAQPage"' in html
        cited = set(re.findall(r'href="#ref-(\d+)"', html))
        listed = set(re.findall(r'id="ref-(\d+)"', html))
        assert cited and cited == listed, (post["slug"], cited ^ listed)
        assert 'dateModified' in html


# ------------------------------------------------- shop by shape / specialty + shared cart ----
def test_every_shape_belongs_to_exactly_one_family():
    data = g.load_data()
    shapes = [s for f in g.FAMILIES.values() for s in f["shapes"]]
    assert len(shapes) == len(set(shapes))
    assert set(shapes) == {p["shape"] for p in data["products"] if not p.get("bundle")}
    assert {"needle", "torpedo", "football"} <= {k for k, f in g.FAMILIES.items() if len(f["shapes"]) == 1}


def test_homepage_tiles_match_families_and_icons_exist():
    import os
    html = open("index.html", encoding="utf-8").read()
    tiles = dict(re.findall(r'<a class="shop-tile" href="/([^"]+)" data-shapes="([^"]+)"', html))
    assert tiles == {g.family_url(k): ",".join(f["shapes"]) for k, f in g.FAMILIES.items()}
    for k in g.FAMILIES:
        assert os.path.exists(f"images/icons/{k}.webp") and os.path.exists(f"images/icons/{k}@2x.webp")
    for slug in ("fixed-prostho", "restorative-specialists", "endodontics"):
        assert f'href="/collection/{slug}/"' in html
    # the full catalog is no longer dumped on the homepage: only featured cards by default
    assert "filteredProducts.filter(p => p.featured)" in html


def test_family_page_lists_every_model_with_add_to_cart_and_filters():
    data = g.load_data()
    html = g.build_family_page("fissure", data)
    models = [p["model"] for p in g.family_products(data, "fissure")]
    assert len(models) == 9  # 6 fissure + 2 round-end fissure + 1 chamfer
    for m in models:
        assert f'class="add-btn" data-model="{m}"' in html
        assert f'href="/{g.product_page_url(m)}"' in html
    for slug in ("fissure-burs", "round-end-fissure-burs", "chamfer-burs"):
        assert f'href="/category/{slug}/"' in html
    assert 'data-filter="shape"' in html and 'data-filter="grit"' in html
    assert 'rel="canonical" href="https://ddsverified.ir/family/fissure/"' in html
    ld = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
    assert len(next(x for x in ld if x["@type"] == "ItemList")["itemListElement"]) == 9


def test_specialty_collections():
    data = g.load_data()
    resto = {p["model"] for p in g.collection_products(data, "restorative")}
    assert {"VP-20", "CP-12C", "SR-21C", "RS-11", "CR-12EF", "TC-26", "FO-21C", "SF-41", "BR-49"} <= resto
    endo = {p["model"] for p in g.collection_products(data, "endodontics")}
    assert endo == {"ENDO-Z TI", "BR-40C", "BR-46C", "BR-49", "BR-L46", "SO-21C"}
    prostho = {p["model"] for p in g.collection_products(data, "fixed_prostho")}
    assert prostho == {p["model"] for p in data["products"] if p.get("collection") == "fixed_prostho"}
    html = g.build_collection_page("restorative", data)
    assert "فرزهای ترمیمی و زیبایی" in html
    assert 'rel="canonical" href="https://ddsverified.ir/collection/restorative-specialists/"' in html
    assert all(f'data-model="{m}"' in html for m in resto)


def test_generated_pages_load_shared_cart_and_buy_in_place():
    data = g.load_data()
    tc = next(p for p in data["products"] if p["model"] == "TC-21EF")
    for html in (g.build_category_page("needle", data), g.build_product_page(tc, data),
                 g.build_family_page("taper", data), g.build_collection_page("endodontics", data)):
        assert re.search(r'href="/assets/shop\.css\?v=[0-9a-f]{10}"', html)
        catalog = html.index('src="/assets/catalog.js?v=')
        assert catalog < html.index('src="/assets/cart.js?v=')  # data before cart logic
    for html in (g.build_category_page("needle", data), g.build_product_page(tc, data)):
        assert 'href="/index.html#TC-21EF" data-add-to-cart="TC-21EF"' in html


def test_catalog_js_matches_data_and_homepage_versions_refresh():
    data = g.load_data()
    js = g.build_catalog_js(data)
    products = json.loads(re.search(r"const PRODUCTS = (\[.*?\]);\n", js).group(1))
    assert products == data["products"]
    assert f"const PRICE_PER_BUR = {data['price_per_bur']};" in js
    stale = '<link href="/assets/shop.css?v=1"><script src="/assets/cart.js?v=abc"></script>'
    fresh = g.inject_asset_versions(stale)
    assert f"shop.css?v={g.asset_version('assets/shop.css')}" in fresh
    assert f"cart.js?v={g.asset_version('assets/cart.js')}" in fresh


def test_category_breadcrumb_links_parent_family_and_sitemap_lists_families():
    data = g.load_data()
    assert '<a href="/family/fissure/">فرز فیشور</a>' in g.build_category_page("pointed_cylinder", data)
    assert 'href="/family/' not in g.build_category_page("needle", data).split('class="crumbs"')[1].split("</nav>")[0]
    sitemap = g.build_sitemap(data)
    for k in ("fissure", "taper", "flame", "round", "special"):
        assert f"{g.BASE}/family/{k}/" in sitemap
    assert f"{g.BASE}/collection/endodontics/" in sitemap


def test_generator_source_stays_python_311_compatible():
    """CI runs Python 3.11: f-string expressions may not reuse the outer quote or contain backslashes
    (that is only legal from 3.12, PEP 701). A reused quote broke the regenerate workflow once."""
    import tokenize
    if not hasattr(tokenize, "FSTRING_START"):
        return  # running on 3.11 itself: importing generate_pages above already proved it parses
    problems = []
    for path in ("generate_pages.py", "tools/extract_products.py", "tools/generate_emalls_feed.py",
                 "tools/generate_torob_feed.py", "tools/crop_icons.py"):
        with open(path, "rb") as f:
            stack = []
            for t in tokenize.tokenize(f.readline):
                if t.type == tokenize.FSTRING_START:
                    quote = t.string.lstrip("rbfuRBFU")
                    if stack and len(stack[-1]) == 1 and quote[0] == stack[-1]:
                        problems.append((path, t.start[0]))
                    stack.append(quote)
                elif t.type == tokenize.FSTRING_END:
                    stack.pop()
                elif stack and t.type == tokenize.STRING:
                    body = t.string.lstrip("rbfuRBFU")
                    if (len(stack[-1]) == 1 and body[0] == stack[-1]) or "\\" in t.string:
                        problems.append((path, t.start[0]))
    assert problems == []
