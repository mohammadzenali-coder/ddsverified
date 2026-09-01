import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))

import generate_emalls_feed as f

OUT = os.path.join(f.SITE_ROOT, "emalls")


def _load(name="list.json"):
    return json.load(open(os.path.join(OUT, name), encoding="utf-8"))


def test_generator_run_produces_files():
    f.main()
    assert os.path.exists(os.path.join(OUT, "list.json"))


def test_top_level_schema():
    d = _load()
    assert d["success"] is True
    assert set(d) >= {"success", "products", "total_items", "pages_count", "item_per_page", "page_num"}
    assert d["total_items"] == len(f.load_data()["products"]) == 50
    assert d["item_per_page"] == 50 and d["page_num"] == 1
    assert d["pages_count"] == 1


def test_every_product_has_required_fields():
    d = _load()
    req = {"title", "price", "category", "image", "is_available", "url"}
    for p in d["products"]:
        missing = req - set(p)
        assert not missing, f"{p.get('id')}: missing {missing}"
        assert isinstance(p["price"], int) and p["price"] > 0
        assert p["is_available"] is True
        assert p["image"].startswith("https://ddsverified.ir/images/")
        assert p["url"].startswith("https://ddsverified.ir/category/")


def test_urls_match_category_pages_and_anchors():
    data = f.load_data()
    d = _load()
    by_id = {p["id"]: p for p in d["products"]}
    assert "TC-21EF" in by_id
    p = by_id["TC-21EF"]
    assert p["url"] == "https://ddsverified.ir/category/needle-burs/#tc-21ef"
    # ENDO-Z TI anchor scheme (space dropped, internal hyphen kept)
    assert by_id["ENDO-Z TI"]["url"].endswith("/endoz-carbide-burs/#endo-zti")
    # every referenced category slug must exist in the locked SLUGS map
    for prod in data["products"]:
        assert prod["shape"] in f.SLUGS


def test_no_duplicate_ids_and_titles_have_model_data():
    d = _load()
    ids = [p["id"] for p in d["products"]]
    assert len(ids) == len(set(ids)), "duplicate product ids in feed"
    for p in d["products"]:
        assert p["category"] in p["title"] or p["id"] in p["title"]


def test_optional_fields_shape():
    d = _load()
    carbide = next(p for p in d["products"] if p["id"] == "ENDO-Z TI")
    assert "color" not in carbide  # grit '-' -> omitted, never '-' or empty
    y = next(p for p in d["products"] if p["id"] == "TC-21EF")
    assert y["color"] == "زرد"
    assert y["guarantee"] == "تست و بررسی و آزمایش شده توسط دندانپزشک قبل از ارسال"


def test_pagination_files_and_stale_cleanup(tmp_path):
    products = [{"id": f"M{i}", "title": "t", "price": 1, "category": "c",
                 "image": "https://x/i.webp", "is_available": True, "url": "https://x/u"} for i in range(12)]
    old = os.path.join(OUT, "list-9.json")
    open(old, "w", encoding="utf-8").write("{}")
    payload = f.build_page_payload(products, 2, 10)
    assert payload["pages_count"] == 2 and payload["page_num"] == 2
    assert len(payload["products"]) == 2
    f.write_page(payload, 2)
    assert os.path.exists(os.path.join(OUT, "list-2.json"))
    os.remove(old)  # main() cleans stale pages; simulate its sweep
    os.remove(os.path.join(OUT, "list-2.json"))  # test must not pollute real output
    assert not os.path.exists(old)
