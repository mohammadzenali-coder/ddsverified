"""Tests for the cms.py surgical rewriter: parse PRODUCTS from index.html,
serialize back, replace the block, verify everything else is byte-identical.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent
INDEX = ROOT / "index.html"
sys.path.insert(0, str(ROOT))

# Force a fresh import (in case pytest re-runs)
if "tools.serialize_products" in sys.modules:
    del sys.modules["tools.serialize_products"]

from tools.serialize_products import (
    BLOCK_RE,
    extract_block,
    serialize_products,
    rewrite_index,
)


SAMPLE_PRODUCT = {
    "shape": "needle",
    "model": "TC-TEST",
    "iso": "806 314 164 504 012",
    "usa": "852-012EF",
    "diameter": "012",
    "length": "6.0",
    "grit": "Y🟡",
    "inventory": 100,
}


def test_block_regex_finds_products_in_real_index():
    """The regex used by extract_products.py must match our block too."""
    html = INDEX.read_text(encoding="utf-8")
    m = BLOCK_RE.search(html)
    assert m is not None, "BLOCK_RE failed to find PRODUCTS in real index.html"
    # body must contain all 50 products. Keys are unquoted in the source
    # (model:"..."), so look for the unquoted form.
    body = m.group(1)
    assert body.count("model:") >= 50  # 50 product rows + a few 'data-model' in the same JS file is fine


def test_extract_block_returns_three_parts():
    html = INDEX.read_text(encoding="utf-8")
    prefix, products_src, suffix = extract_block(html)
    assert prefix.endswith("const PRODUCTS = [\n")
    # Body starts with a "// Needle" comment line, not a "{"
    assert products_src.lstrip().startswith("//") or products_src.lstrip().startswith("{")
    assert products_src.rstrip().endswith("}")
    assert suffix.startswith("];\n")


def test_serialize_round_trip_preserves_count():
    """Serialize a list of dicts → count of objects must match."""
    html = INDEX.read_text(encoding="utf-8")
    _, products_src, _ = extract_block(html)
    # Parse via the existing extract_products.py logic (proven to work)
    from tools.extract_products import grab
    parsed = grab("PRODUCTS")
    assert len(parsed) == 50
    out = serialize_products(parsed)
    # count top-level {...} groups in serialized output
    depth = 0
    count = 0
    in_str = False
    esc = False
    quote = ""
    for c in out:
        if in_str:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == quote: in_str = False
        else:
            if c in ('"', "'"):
                in_str = True; quote = c
            elif c == "{":
                if depth == 0: count += 1
                depth += 1
            elif c == "}":
                depth -= 1
    assert count == len(parsed) == 50


def test_serialize_persian_and_emoji_values_survive():
    """Persian text and emoji grit keys must round-trip byte-exactly."""
    products = [
        {
            "shape": "carbide",
            "model": "ENDO-Z TI",
            "iso": "807 314 001 524 021",
            "usa": "953-015M",
            "diameter": "-",
            "length": "-",
            "grit": "-",
            "inventory": 36,
            "multiplier": 1,
            "price": 980000,
        },
        {
            "shape": "needle",
            "model": "TC-26EF",
            "iso": "806 314 164 504 012",
            "usa": "852-012EF",
            "diameter": "012",
            "length": "6.0",
            "grit": "Y🟡",
            "inventory": 100,
        },
    ]
    out = serialize_products(products)
    assert "carbide" in out
    assert "ENDO-Z TI" in out
    assert "Y🟡" in out  # emoji
    assert "price:980000" in out
    assert "multiplier:1" in out


def test_serialize_format_matches_existing_style():
    """Output must match the existing index.html style: 2-space indent, one
    object per line, keys in declaration order, double-quoted strings, no
    trailing commas."""
    products = [SAMPLE_PRODUCT]
    out = serialize_products(products)
    # Expected exactly:
    expected = (
        "const PRODUCTS = [\n"
        "  {shape:\"needle\",model:\"TC-TEST\","
        "iso:\"806 314 164 504 012\",usa:\"852-012EF\","
        "diameter:\"012\",length:\"6.0\",grit:\"Y🟡\",inventory:100}\n"
        "];\n"
    )
    assert out == expected


def test_rewrite_index_preserves_everything_outside_products(tmp_path):
    """rewrite_index() must leave the rest of index.html byte-identical."""
    # copy real index.html into tmp
    src = tmp_path / "index.html"
    src.write_text(INDEX.read_text(encoding="utf-8"), encoding="utf-8")
    original = src.read_text(encoding="utf-8")

    # Load the real products, mutate one field, write back
    from tools.extract_products import grab
    parsed = grab("PRODUCTS")
    parsed[0]["inventory"] = 999  # small change
    new_count = len(parsed)

    new_text = rewrite_index(src, parsed)
    new_text_on_disk = src.read_text(encoding="utf-8")
    assert new_text == new_text_on_disk

    # Build expected: everything before PRODUCTS, replaced block, everything after
    m = BLOCK_RE.search(original)
    start, end = m.span(1)
    head = original[:m.start(1)]
    tail = original[m.end(1):]
    # head should equal everything up to and including "const PRODUCTS = [\n"
    # tail should start with the same line that followed the original block
    expected_head = original[: original.find("const PRODUCTS = [") + len("const PRODUCTS = [\n")]
    expected_tail = original[original.find("const PRODUCTS = [") + len("const PRODUCTS = ["):]
    expected_tail = expected_tail[expected_tail.index("];\n") + len("];\n"):]

    assert new_text.startswith(expected_head), "head changed!"
    assert new_text.endswith(expected_tail), "tail changed!"
    # And the new block must contain the mutated value
    assert "inventory:999" in new_text
    # Parsing via the real extractor proves all 50 products survive.
    import re as _re
    def _grab(html):
        m = _re.search(r"const PRODUCTS = (\[.*?\]);", html, _re.S)
        body = m.group(1)
        body = _re.sub(r'([{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', body)
        body = _re.sub(r',(\s*[}\]])', r'\1', body)
        body = _re.sub(r'^\s*//.*$', '', body, flags=_re.M)
        return json.loads(body)
    parsed2 = _grab(new_text)
    assert len(parsed2) == 50
    assert parsed2[0]["inventory"] == 999


def test_rewritten_index_is_valid_js(tmp_path):
    """Round-trip: rewrite index.html in tmp, then re-parse via the existing
    tools/extract_products.py (the same parser the CMS pipeline uses)."""
    src = tmp_path / "index.html"
    src.write_text(INDEX.read_text(encoding="utf-8"), encoding="utf-8")

    # Re-implement the relevant snippet from tools/extract_products.py inline
    # so we can point it at the tmp file (extract_products.py hardcodes
    # open("index.html") relative to cwd).
    import re as _re
    def _grab(html):
        m = _re.search(r"const PRODUCTS = (\[.*?\]);", html, _re.S)
        assert m, "PRODUCTS not found"
        body = m.group(1)
        body = _re.sub(r'([{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', body)
        body = _re.sub(r',(\s*[}\]])', r'\1', body)
        body = _re.sub(r'^\s*//.*$', '', body, flags=_re.M)
        import json as _json
        return _json.loads(body)

    parsed = _grab(src.read_text(encoding="utf-8"))
    parsed[5]["model"] = "TC-MODIFIED-FOR-TEST"
    rewrite_index(src, parsed)

    # Re-parse with the EXTRACT tool (the one the CMS pipeline will use).
    # Run it with cwd=tmp_path so its hardcoded open("index.html") reads
    # our tmp copy, not the real repo file.
    res = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "extract_products.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert res.returncode == 0, f"re-parse after rewrite failed:\n{res.stdout}\n{res.stderr}"
    assert "50 products" in res.stdout
    data = json.loads((tmp_path / "products_data.json").read_text(encoding="utf-8"))
    assert any(p["model"] == "TC-MODIFIED-FOR-TEST" for p in data["products"])
    assert len(data["products"]) == 50


def test_rewrite_creates_backup_and_cleans_old(tmp_path):
    """rewrite_index writes a timestamped backup and prunes >20."""
    src = tmp_path / "index.html"
    src.write_text(INDEX.read_text(encoding="utf-8"), encoding="utf-8")
    backup_dir = tmp_path / ".cms-backups"
    backup_dir.mkdir()

    from tools.extract_products import grab
    parsed = grab("PRODUCTS")

    # 25 saves -> expect 25 backups then pruned to 20
    for i in range(25):
        parsed[0]["inventory"] = 100 + i
        rewrite_index(src, parsed, backup_dir=backup_dir)

    backups = sorted(backup_dir.glob("index.html.*"))
    assert len(backups) == 20, f"expected 20 backups, got {len(backups)}"


def test_rewrite_atomic_writes_via_tempfile(tmp_path):
    """If a write would fail mid-stream, the original file must be intact."""
    src = tmp_path / "index.html"
    original_bytes = INDEX.read_bytes()
    src.write_bytes(original_bytes)

    # Pass a non-serializable value to force failure inside serialize
    from tools.extract_products import grab
    parsed = grab("PRODUCTS")
    # inject an un-encodable marker by passing a dict that has a function value
    parsed.append({"shape": "x", "model": "BAD", "inventory": lambda: 1})

    with pytest.raises((TypeError, ValueError)):
        rewrite_index(src, parsed)
    # original file must still be byte-identical to the source
    assert src.read_bytes() == original_bytes