import datetime
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))

import generate_torob_feed as t

OUT = t.OUT_PATH


def _load(name="products.json"):
    return json.load(open(os.path.join(t.OUT_DIR, name), encoding="utf-8"))


def test_generator_run_produces_file():
    t.main()
    assert os.path.exists(OUT)


def test_count_matches_source_and_uniques_unique():
    d = _load()
    src = t.load_data()["products"]
    assert len(d) == len(src) == 50
    uniques = [p["page_unique"] for p in d]
    assert len(uniques) == len(set(uniques)), "duplicate page_unique in feed"


def test_required_fields_types_and_limits():
    d = _load()
    req = {"page_unique", "page_url", "title", "current_price", "availability",
           "category_name", "image_links", "spec", "date_added", "date_updated"}
    for p in d:
        missing = req - set(p)
        assert not missing, f"{p.get('page_unique')}: missing {missing}"
        assert isinstance(p["current_price"], int) and p["current_price"] > 0
        assert isinstance(p["availability"], bool)
        assert isinstance(p["spec"], dict) and p["spec"], "spec must be a non-empty dict"
        assert p["image_links"], "image_links required (first = main image)"
        for img in p["image_links"]:
            assert img.startswith("https://ddsverified.ir/images/") and len(img) <= 1000
        assert p["page_url"].startswith("https://ddsverified.ir/product/") and len(p["page_url"]) <= 1500
        assert len(p["title"]) <= 500 and len(p["page_unique"]) <= 200
        for f in ("date_added", "date_updated"):
            dt = datetime.datetime.fromisoformat(p[f])
            assert dt.tzinfo is not None, f"{f} must be timezone-aware ISO 8601"


def test_urls_point_to_existing_product_pages_and_no_orphans():
    d = _load()
    pdir = os.path.join(t.SITE_ROOT, "product")
    on_disk = {e for e in os.listdir(pdir) if os.path.isdir(os.path.join(pdir, e))}
    feed_slugs = set()
    for p in d:
        slug = p["page_url"].rsplit("/product/", 1)[1].strip("/")
        feed_slugs.add(slug)
        assert os.path.exists(os.path.join(pdir, slug, "index.html")), f"missing page for {slug}"
    assert on_disk == feed_slugs


def test_known_product_content():
    d = {p["page_unique"]: p for p in _load()}
    # ENDO-Z TI: premium price, single-sale, title matches product-page h1
    # (فرز {shape} مدل {model} — generate_pages.py:499)
    ez = d["endo-zti"]
    assert ez["current_price"] == 980000
    assert ez["title"] == "فرز EndoZ کارباید تیتانیومی ساخت انگلیس مدل ENDO-Z TI"
    assert "ENDO-Z TI" in ez["title"]
    assert ez["spec"]["بسته‌بندی"] == "فروش تکی"
    assert ez["availability"] is True
    assert ez["image_links"] == ["https://ddsverified.ir/images/endo-z%20ti.webp"]
    # TC-21EF: pack sale, yellow grit, size + ISO in spec
    y = d["tc-21ef"]
    assert y["current_price"] == 126000
    assert y["spec"]["بسته‌بندی"] == "بسته ۵ عددی"
    assert y["spec"]["دور (گریت)"] == "زرد"
    assert y["spec"]["قطر"] == "014"  # matches site spec-table label (قطر)
    assert "806 314 165 504 014" in y["spec"]["کد ISO"]  # actual source ISO (grit 504)
    assert y["guarantee"] == "تست و بررسی و آزمایش شده توسط دندانپزشک قبل از ارسال"
    assert y["product_group_id"] == "needle-burs"
    # pointed_cylinder uses owner-confirmed chamfer naming
    assert "شمفر" in d["cp-12c"]["category_name"]


def test_dates_stable_across_runs():
    t.main()
    first = _load()
    t.main()
    second = _load()
    assert first == second, "regeneration must be idempotent (no date churn)"


def test_date_updated_bumps_only_for_changed_products(monkeypatch):
    t.main()
    before = {p["page_unique"]: p for p in _load()}
    data = json.loads(json.dumps(t.load_data()))
    # give products[0] a per-product price override -> only its current_price changes
    data["products"][0]["price"] = 123456
    monkeypatch.setattr(t, "load_data", lambda: data)
    t.main()
    after = {p["page_unique"]: p for p in _load()}
    changed = {u for u in after if after[u] != before[u]}
    assert len(changed) == 1, f"exactly one product should bump, got {changed}"
    u = changed.pop()
    assert datetime.datetime.fromisoformat(after[u]["date_updated"]) > datetime.datetime.fromisoformat(before[u]["date_updated"])
    assert after[u]["date_added"] == before[u]["date_added"], "date_added must never change"
    # every other product kept its exact date_updated
    for other in before:
        if other != u:
            assert after[other]["date_updated"] == before[other]["date_updated"]


def test_date_added_ordering_matches_registry():
    t.main()
    added = json.load(open(t.ADDED_PATH, encoding="utf-8"))
    d = _load()
    assert {p["page_unique"]: p["date_added"] for p in d} == {t.anchor_id(m): v for m, v in added.items()}
    ts = [datetime.datetime.fromisoformat(p["date_added"]) for p in d]
    assert ts == sorted(ts), "date_added must be non-decreasing (deterministic date_added_desc)"


def test_registry_prunes_removed_models(tmp_path, monkeypatch):
    # run against throwaway copies so the real registry/feed are never touched
    monkeypatch.setattr(t, "ADDED_PATH", str(tmp_path / "added.json"))
    monkeypatch.setattr(t, "OUT_PATH", str(tmp_path / "products.json"))
    data = json.loads(json.dumps(t.load_data()))
    data["products"] = data["products"][:3]
    monkeypatch.setattr(t, "load_data", lambda: data)
    t.main()
    added = json.load(open(t.ADDED_PATH, encoding="utf-8"))
    assert set(added) == {p["model"] for p in data["products"]}
    feed = json.load(open(t.OUT_PATH, encoding="utf-8"))
    assert len(feed) == 3
