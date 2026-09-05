"""Generate the Torob API v3 backing feed: static JSON at /torob/products.json.

Torob Product API v3 (github.com/Torob/Torob-Sync, product_api_v3.md) requires a
POST endpoint with JWT auth — impossible on GitHub Pages. So the static site
publishes the raw v3 product objects (this file, a JSON array), and the
Cloudflare Worker in torob-api/ wraps them in the v3 envelope and enforces JWT
(EdDSA/ed25519) auth at https://api.ddsverified.ir/torob_api/v3/products.

date_added: assigned once per model into tools/torob_added.json and never
regenerated, so Torob's date_added_desc sort is deterministic across runs.
date_updated: preserved from the previously committed products.json unless the
product's content fingerprint changed (then = regeneration time).
"""
import datetime
import json
import os
import sys

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(SITE_ROOT, "products_data.json")
OUT_DIR = os.path.join(SITE_ROOT, "torob")
OUT_PATH = os.path.join(OUT_DIR, "products.json")
ADDED_PATH = os.path.join(SITE_ROOT, "tools", "torob_added.json")

BASE_TS = "2026-08-25T00:15:18+03:30"  # birth of products_data.json (first commit)
TZ = datetime.timezone(datetime.timedelta(hours=3, minutes=30))

sys.path.insert(0, SITE_ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_pages import (  # noqa: E402  (single source of truth for site naming/URLs)
    BASE,
    SLUGS,
    anchor_id,
    fa,
    img_rel,
    product_page_url,
    shape_fa,
)
from generate_emalls_feed import DEFAULT_GUARANTEE, color_fa  # noqa: E402


def load_data() -> dict:
    return json.load(open(DATA_FILE, encoding="utf-8"))


def _parse_ts(s: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(s)


def _now_iso() -> str:
    return datetime.datetime.now(TZ).isoformat(timespec="microseconds")


def pack_note(p: dict, data: dict) -> str:
    return "فروش تکی" if p.get("multiplier") == 1 else f"بسته {fa(data['burs_per_pack'])} عددی"


def product_title(p: dict, data: dict) -> str:
    sname = shape_fa(p["shape"], data)
    head = sname if p["model"].lower() in sname.lower() else f"{sname} مدل {p['model']}"
    extras = []
    grit = color_fa(p.get("grit", ""))
    if grit and grit != "-":
        extras.append(f"دور {grit}")
    if p.get("diameter", "-") != "-":
        extras.append(f"سایز {p['diameter']}")
    if p.get("length", "-") != "-":
        extras.append(f"طول {p['length']} میلی‌متر")
    return " — ".join([head] + extras)


def build_product(p: dict, data: dict) -> dict:
    model = p["model"]
    grit = color_fa(p.get("grit", ""))
    note = pack_note(p, data)
    spec = {"بسته‌بندی": note}
    if p.get("diameter", "-") != "-":
        spec["قطر"] = p["diameter"]
    if p.get("length", "-") != "-":
        spec["طول (میلی‌متر)"] = p["length"]
    if grit and grit != "-":
        spec["دور (گریت)"] = grit
    if p.get("iso"):
        spec["کد ISO"] = p["iso"]
    if p.get("usa"):
        spec["کد USA"] = p["usa"]
    short_bits = [note]
    if grit and grit != "-":
        short_bits.append(f"دور {grit}")
    if p.get("iso"):
        short_bits.append(f"کد ISO {p['iso']}")
    return {
        "page_unique": anchor_id(model),
        "page_url": f"{BASE}/{product_page_url(model)}",
        "product_group_id": SLUGS[p["shape"]],
        "title": product_title(p, data),
        "subtitle": note,
        "current_price": int(p.get("price") or data["price_per_bur"]),
        "availability": bool(p.get("inventory", 0) > 0),
        "category_name": shape_fa(p["shape"], data),
        "image_links": [img_rel(model)],
        "spec": spec,
        "guarantee": DEFAULT_GUARANTEE,
        "short_desc": "، ".join(short_bits),
    }


def assign_dates(models: list, added: dict) -> bool:
    """Assign a stable date_added to every model; prune removed ones."""
    changed = False
    latest = max((_parse_ts(v) for v in added.values()), default=None)
    for m in models:
        if m in added:
            continue
        ts = (latest + datetime.timedelta(seconds=60)) if latest else _parse_ts(BASE_TS)
        added[m] = ts.isoformat()
        latest = ts
        changed = True
    for m in [k for k in added if k not in models]:
        del added[m]
        changed = True
    return changed


def load_prev_index() -> dict:
    """page_unique -> (date_updated, fingerprint) from the last committed feed."""
    if not os.path.exists(OUT_PATH):
        return {}
    try:
        old = json.load(open(OUT_PATH, encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return {
        p["page_unique"]: (
            p.get("date_updated") or p["date_added"],
            {k: v for k, v in p.items() if not k.startswith("date_")},
        )
        for p in old
        if isinstance(p, dict) and "page_unique" in p
    }


def main() -> None:
    data = load_data()
    products_src = sorted(data["products"], key=lambda x: x["model"])

    added = {}
    if os.path.exists(ADDED_PATH):
        added = json.load(open(ADDED_PATH, encoding="utf-8"))
    if assign_dates([p["model"] for p in products_src], added):
        with open(ADDED_PATH, "w", encoding="utf-8") as f:
            json.dump(added, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")

    prev = load_prev_index()
    out = []
    for p in products_src:
        prod = build_product(p, data)
        prod["date_added"] = added[p["model"]]
        # Fingerprint = every field EXCEPT the two timestamps we are deciding.
        # Including them would always drift and bump date_updated on every run.
        fingerprint = {k: v for k, v in prod.items() if k not in ("date_added", "date_updated")}
        old = prev.get(prod["page_unique"])
        if old and old[1] == fingerprint:
            prod["date_updated"] = old[0]
        else:
            new_ts = _now_iso()
            if old:
                # guarantee date_updated strictly increases, even within the
                # same clock second/microsecond of the previous bump
                prev_ts = _parse_ts(old[0])
                if _parse_ts(new_ts) <= prev_ts:
                    new_ts = (prev_ts + datetime.timedelta(microseconds=1)).isoformat()
            prod["date_updated"] = new_ts
        out.append(prod)

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"torob v3 feed: {len(out)} products -> {os.path.relpath(OUT_PATH, SITE_ROOT)}")
    print(f"  endpoint (after worker deploy): {BASE.replace('https://', 'https://api.')}/torob_api/v3/products")


if __name__ == "__main__":
    main()
