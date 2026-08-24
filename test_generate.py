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
