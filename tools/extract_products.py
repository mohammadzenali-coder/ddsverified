"""One-time extractor: pulls PRODUCTS, SHAPE_MAP, GRIT_TEXT out of index.html into products_data.json."""
import json
import re

html = open("index.html", encoding="utf-8").read()


def js_to_json(s: str) -> str:
    # quote unquoted object keys, strip trailing commas
    s = re.sub(r'([{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', s)
    # quoted keys with non-ASCII (emoji grit keys like "Y🟡") are fine as-is
    s = re.sub(r',(\s*[}\]])', r'\1', s)
    return s


def grab(name: str):
    m = re.search(rf"const {name} = (\[.*?\]|\{{.*?\}});", html, re.S)
    assert m, f"{name} not found in index.html"
    raw = js_to_json(m.group(1))
    # strip JS line comments (// Needle etc.) that break JSON parsing
    raw = re.sub(r'^\s*//.*$', '', raw, flags=re.M)
    return json.loads(raw)


data = {
    "price_per_bur": 126000,
    "burs_per_pack": 5,
    "shapes": grab("SHAPE_MAP"),
    "grits": grab("GRIT_TEXT"),
    "products": grab("PRODUCTS"),
}
json.dump(data, open("products_data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"OK: {len(data['products'])} products, {len(data['shapes'])} shapes")
