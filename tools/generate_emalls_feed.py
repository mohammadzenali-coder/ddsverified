"""Generate the Emalls.ir product feed: static JSON at /emalls/list.json.

Spec (Emalls PDF, 1405/06): GET endpoint returning
  {success, products[], total_items, pages_count, item_per_page, page_num}
with per-product
  {title*, id, price*, old_price?, category*, image*, color?, guarantee?, is_available*, url*}
Prices in Toman. URL/image must be absolute (protocol + domain).

The endpoint is a static file; pagination is emulated for crawlers by
emitting /emalls/list-<N>.json for page N (page 1 doubles as /emalls/list.json).
Emalls' crawler fetches /emalls/list.json (query strings like ?page=&item_per_page=
are ignored by Pages) and walks the page files until one yields no products.
"""
import json
import os
import sys
from urllib.parse import quote

BASE = "https://ddsverified.ir"
SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(SITE_ROOT, "products_data.json")
OUT_DIR = os.path.join(SITE_ROOT, "emalls")
DEFAULT_ITEM_PER_PAGE = 50
DEFAULT_GUARANTEE = "تست و بررسی و آزمایش شده توسط دندانپزشک قبل از ارسال"

sys.path.insert(0, SITE_ROOT)
from generate_pages import SLUGS, anchor_id  # noqa: E402  (single source of truth)


def load_data() -> dict:
    return json.load(open(DATA_FILE, encoding="utf-8"))


def shape_fa(key: str, data: dict) -> str:
    return data["shapes"].get(key, key)


def product_url(shape_key: str, model: str, data: dict) -> str:
    slug = SLUGS[shape_key]
    return f"{BASE}/category/{slug}/#{anchor_id(model)}"


def image_url(model: str) -> str:
    # Absolute URL (Emalls requires protocol + domain). Space kept via %20.
    return quote(f"{BASE}/images/{model.lower()}.webp", safe="/:")


def color_fa(grit: str) -> str:
    # Grit ring color, Persian label (matches site convention)
    colors = {
        "Y🟡": "زرد",
        "R🔴": "قرمز",
        "B🔵": "آبی",
        "G🟢": "سبز",
        "K⚫": "مشکی",
    }
    return colors.get(grit, "")


def product_title(p: dict, data: dict) -> str:
    shape = shape_fa(p["shape"], data)
    parts = [shape]
    grit = color_fa(p.get("grit", ""))
    if grit and grit != "-":
        parts.append(f"دور {grit}")
    if p.get("diameter") and p["diameter"] != "-":
        parts.append(f"سایز {p['diameter']}")
    return " — ".join(parts)


def product_category(shape_key: str, data: dict) -> str:
    return shape_fa(shape_key, data)


def build_products(data: dict) -> list:
    products = []
    for p in sorted(data["products"], key=lambda x: x["model"]):
        shape = p["shape"]
        grit = color_fa(p.get("grit", ""))
        # Prefer per-product price override if extract ever adds one; else pack base
        price = int(p.get("price") or data["price_per_bur"])
        old_price = p.get("old_price")
        entry = {
            "title": product_title(p, data),
            "id": p["model"],
            "price": price,
            "old_price": int(old_price) if old_price else None,
            "category": product_category(shape, data),
            "image": image_url(p["model"]),
            "color": grit if grit and grit != "-" else None,
            "guarantee": DEFAULT_GUARANTEE,
            "is_available": bool(p.get("inventory", 0) > 0),
            "url": product_url(shape, p["model"], data),
        }
        entry = {k: v for k, v in entry.items() if v is not None}
        products.append(entry)
    return products


def page_slice(products: list, page: int, item_per_page: int) -> list:
    start = (page - 1) * item_per_page
    return products[start:start + item_per_page]


def build_page_payload(products: list, page: int, item_per_page: int) -> dict:
    total = len(products)
    pages_count = (total + item_per_page - 1) // item_per_page
    return {
        "success": True,
        "products": page_slice(products, page, item_per_page),
        "total_items": total,
        "pages_count": pages_count,
        "item_per_page": item_per_page,
        "page_num": page,
    }


def write_page(payload: dict, page: int) -> str:
    name = "list.json" if page == 1 else f"list-{page}.json"
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path


def main() -> None:
    data = load_data()
    os.makedirs(OUT_DIR, exist_ok=True)
    products = build_products(data)
    ipp = DEFAULT_ITEM_PER_PAGE
    payload = build_page_payload(products, 1, ipp)
    write_page(payload, 1)

    pages_count = payload["pages_count"]
    for page in range(2, pages_count + 1):
        write_page(build_page_payload(products, page, ipp), page)

    # Drop stale page files (e.g. after products were removed)
    for fn in os.listdir(OUT_DIR):
        m = None
        if fn.startswith("list-") and fn.endswith(".json"):
            try:
                m = int(fn[len("list-"):-len(".json")])
            except ValueError:
                m = None
        if m is not None and m > pages_count:
            os.remove(os.path.join(OUT_DIR, fn))

    print(f"emalls feed: {len(products)} products, {pages_count} page(s) of {ipp}")
    print(f"  -> {os.path.relpath(os.path.join(OUT_DIR, 'list.json'), SITE_ROOT)}")


if __name__ == "__main__":
    main()
