"""Surgical rewriter for the PRODUCTS array in index.html.

The CMS uses this to read the current PRODUCTS block, serialize a Python
list-of-dicts back to the exact JS-literal style used in index.html, and
replace ONLY the bytes inside `const PRODUCTS = [...];`. Everything else in
index.html is left byte-identical.

Why a custom serializer (not json.dumps)? The index.html style is:
    {shape:"needle",model:"TC-26EF",iso:"...",...}
- unquoted keys (where legal)
- double-quoted string values
- 2-space indent, one object per line
- NO trailing comma on the last object
- emoji / non-ASCII content in string values

We reuse tools.extract_products for parsing (already battle-tested on this
file); this module only does the write side.

Atomic write: serialize -> write to <path>.tmp -> os.replace(). If serialize
raises, the original file is never touched.
"""
from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path
from typing import Iterable, Sequence

# Same regex shape as tools/extract_products.grab, but exposes group(1)
# (the raw block body) and group(2) is unused.
BLOCK_RE = re.compile(r"const PRODUCTS = (\[.*?\]);", re.DOTALL)


# ---------------------------------------------------------------------------
# Read side
# ---------------------------------------------------------------------------
def extract_block(html: str) -> tuple[str, str, str]:
    """Return (prefix, products_body, suffix) where products_body is the raw
    text between the [ and the matching ]. The regex is non-greedy and assumes
    PRODUCTS is the first bracketed array literal that ends with ]; after
    `const PRODUCTS = [`. Good enough for this file.
    """
    m = BLOCK_RE.search(html)
    if not m:
        raise ValueError("const PRODUCTS = [...] not found in input")
    # m.group(0) is "const PRODUCTS = [...];"
    # We want prefix ending right after the opening "[\n"
    full_start = m.start(0)
    full_end = m.end(0)
    # Locate the opening "[" of the array
    lb = html.index("[", full_start)
    prefix = html[: lb + 1]  # include "["
    if not prefix.endswith("[\n"):
        # The opening bracket may not be followed by a newline; normalize so
        # the new block always sits on its own lines.
        prefix = prefix.rstrip("[\n") + "[\n"
    body = html[lb + 1 : html.rindex("]", 0, full_end)]
    suffix = html[html.rindex("]", 0, full_end) : full_end]  # includes "];"
    if not suffix.startswith("]\n"):
        suffix = suffix.replace("];", "];\n", 1)
        if not suffix.endswith("\n"):
            suffix = suffix.rstrip() + "\n"
    return prefix, body, suffix


# ---------------------------------------------------------------------------
# Write side
# ---------------------------------------------------------------------------
# Keys appear in a fixed canonical order in the existing file (and the SPA
# reads them positionally via property access, not Object.keys). Keep this
# stable: append new keys at the END.
_KEY_ORDER = (
    "shape",
    "model",
    "iso",
    "usa",
    "diameter",
    "length",
    "grit",
    "inventory",
    "multiplier",
    "price",
)


_JSON_TYPES = (str, int, float, bool, type(None))


def _fmt_value(v) -> str:
    # Reject anything we can't faithfully serialize into JS. The atomic
    # write guarantees the original file is untouched if we raise here.
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        if isinstance(v, float):
            if v != v:  # NaN
                raise TypeError("NaN is not valid in JS source")
            if v in (float("inf"), float("-inf")):
                raise TypeError("Infinity is not valid in JS source")
            if v.is_integer():
                return str(int(v))
        return str(v)
    if v is None:
        return "null"
    if not isinstance(v, str):
        raise TypeError(
            f"product value must be str/int/float/bool/None, got "
            f"{type(v).__name__}: {v!r}"
        )
    # Escape characters that would break a JS double-quoted string literal.
    # We never need unicode escapes because the source file is UTF-8.
    s = v.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def serialize_products(products: Sequence[dict]) -> str:
    """Serialize a list of dicts to the JS literal style used by index.html.

    Output format:
        const PRODUCTS = [
          {shape:"...",model:"...",...},
          ...
        ];
    """
    if not isinstance(products, (list, tuple)):
        raise TypeError(f"products must be a list, got {type(products).__name__}")
    lines = ["const PRODUCTS = ["]
    for i, p in enumerate(products):
        if not isinstance(p, dict):
            raise TypeError(
                f"product #{i} is {type(p).__name__}, expected dict: {p!r}"
            )
        # Build key=value pairs in canonical order; unknown keys appended
        seen = set()
        parts = []
        for k in _KEY_ORDER:
            if k in p:
                parts.append(f"{k}:{_fmt_value(p[k])}")
                seen.add(k)
        for k in p:  # any extra keys, in original order
            if k not in seen:
                parts.append(f"{k}:{_fmt_value(p[k])}")
        line = "  {" + ",".join(parts) + "}"
        if i < len(products) - 1:
            line += ","
        lines.append(line)
    lines.append("];")
    lines.append("")  # trailing newline
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Surgical rewrite (atomic)
# ---------------------------------------------------------------------------
def rewrite_index(
    path: os.PathLike | str,
    products: Sequence[dict],
    backup_dir: os.PathLike | str | None = None,
) -> str:
    """Replace the PRODUCTS block in `path` with serialized `products`.
    Returns the new file content. Original is left untouched if any error
    occurs during serialization (atomic via temp file + os.replace).

    If backup_dir is given, the original bytes are copied there first as
    `index.html.YYYYMMDD-HHMMSS`. Keeps at most 20 newest backups.
    """
    path = Path(path)
    original = path.read_text(encoding="utf-8")

    # Compute where the block lives BEFORE serializing, so a serialize
    # failure leaves the file completely untouched.
    m = BLOCK_RE.search(original)
    if not m:
        raise ValueError(f"PRODUCTS block not found in {path}")
    lb = original.index("[", m.start(0))
    rb_search_from = m.end(0) - 2  # before "];"
    rb = original.rindex("]", rb_search_from, m.end(0))

    # Build the new content from serialized block
    new_block = serialize_products(products)
    # new_block ends with "\n];\n"; strip the trailing "\n]" so we can
    # splice cleanly. We'll re-attach the suffix that came after "]".
    # new_block looks like:
    #   "const PRODUCTS = [\n  {...},\n  {...}\n];\n"
    # We want to replace from the original "[", through the original "]",
    # with everything in new_block EXCEPT the "const PRODUCTS = " prefix
    # (already in original) and the trailing "];\n" (we keep the original's).
    new_body = new_block[len("const PRODUCTS = ["):]
    # new_body ends with "];\n"; strip the "];\n"
    if not new_body.endswith("];\n"):
        raise RuntimeError(f"unexpected new_block tail: {new_body[-10:]!r}")
    new_body = new_body[: -len("];\n")] + "\n"  # keep trailing \n inside the new region

    head = original[: lb + 1]  # up to and including "["
    if not head.endswith("[\n"):
        head = head.rstrip() + "\n"
    tail = original[rb:]  # from the original "]" onward (includes "];\n...")
    if not tail.startswith("]"):
        raise RuntimeError("bracket math failed")
    new_text = head + new_body + tail

    # Backup (optional)
    if backup_dir is not None:
        backup_dir = Path(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        # Include microseconds + a monotonic counter so rapid saves don't
        # collide on the same filename.
        ts = time.strftime("%Y%m%d-%H%M%S-") + f"{time.time_ns() % 1_000_000:06d}"
        shutil.copy2(path, backup_dir / f"index.html.{ts}")
        # Prune to 20 newest
        backups = sorted(backup_dir.glob("index.html.*"), key=lambda p: p.name)
        for old in backups[:-20]:
            old.unlink()

    # Atomic write
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(new_text, encoding="utf-8")
    os.replace(tmp, path)
    return new_text