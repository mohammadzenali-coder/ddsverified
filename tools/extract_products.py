"""One-time extractor: pulls PRODUCTS, SHAPE_MAP, GRIT_TEXT out of index.html into products_data.json."""
import json
import re


def js_to_json(s: str) -> str:
    # quote unquoted object keys, strip trailing commas
    s = re.sub(r'([{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', s)
    # quoted keys with non-ASCII (emoji grit keys like "Y🟡") are fine as-is
    s = re.sub(r',(\s*[}\]])', r'\1', s)
    return s


def grab(name: str, html: str):
    m = re.search(rf"const {name} = (\[.*?\]|\{{.*?\}});", html, re.S)
    assert m, f"{name} not found in index.html"
    raw = js_to_json(m.group(1))
    # strip JS line comments (// Needle etc.) that break JSON parsing
    raw = re.sub(r'^\s*//.*$', '', raw, flags=re.M)
    return json.loads(raw)


def extract(html: str) -> dict:
    def price(name: str) -> int:
        m = re.search(rf'const {name}\s*=\s*(\d+)\s*;', html)
        assert m, f"{name} not found in index.html"
        return int(m.group(1))

    return {
        "price_per_bur": price("PRICE_PER_BUR"),
        "old_price_per_bur": price("LIST_PRICE_PER_BUR"),
        "burs_per_pack": 5,
        "shapes": grab("SHAPE_MAP", html),
        "grits": grab("GRIT_TEXT", html),
        "products": grab("PRODUCTS", html),
    }


def main() -> None:
    with open("index.html", encoding="utf-8") as f:
        data = extract(f.read())
    with open("products_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"OK: {len(data['products'])} products, {len(data['shapes'])} shapes")


if __name__ == "__main__":
    main()
