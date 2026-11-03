"""Cut the AI-generated icon grids into one WebP per tile.

Source grids (light-blue rounded tiles on a cream background):
  images/icons/families-grid.png     3x3 -> 9 bur family icons
  images/icons/specialties-grid.png  1x3 -> 3 specialty icons

Tiles are found automatically from the blue tint, so a regenerated grid with
slightly different spacing still works. Output: images/icons/<name>.webp at
256 px and <name>@2x.webp at 512 px. Re-run after replacing a grid:
python tools/crop_icons.py
"""
from PIL import Image

ICON_DIR = "images/icons"
GRIDS = {
    "families-grid.png": [
        ["needle", "fissure", "taper"],
        ["flame", "round", "football"],
        ["torpedo", "special", "endoz"],
    ],
    "specialties-grid.png": [
        ["fixed-prostho", "restorative-cosmetic", "endodontics"],
    ],
}
SIZES = {"": 256, "@2x": 512}


def _bluish(px) -> bool:
    r, g, b = px[:3]
    return b - r >= 12 and b > 200  # tile tint; cream background has b - r < 0


def _runs(flags: list, min_len: int) -> list:
    """(start, end) of consecutive True runs at least min_len long."""
    runs, start = [], None
    for i, on in enumerate(flags + [False]):
        if on and start is None:
            start = i
        elif not on and start is not None:
            if i - start >= min_len:
                runs.append((start, i))
            start = None
    return runs


def find_tiles(im: Image.Image, rows: int, cols: int) -> list:
    w, h = im.size
    small = im.convert("RGB")
    px = small.load()
    step = 2
    col_hits = [sum(_bluish(px[x, y]) for y in range(0, h, step)) for x in range(w)]
    row_hits = [sum(_bluish(px[x, y]) for x in range(0, w, step)) for y in range(h)]
    col_runs = _runs([c > (h / step) * 0.15 for c in col_hits], w // (cols * 4))
    row_runs = _runs([r > (w / step) * 0.15 for r in row_hits], h // (rows * 4))
    assert len(col_runs) == cols and len(row_runs) == rows, (
        f"expected {rows}x{cols} tiles, found {len(row_runs)}x{len(col_runs)}")
    return [[(x0, y0, x1, y1) for (x0, x1) in col_runs] for (y0, y1) in row_runs]


def main() -> None:
    for grid_file, names in GRIDS.items():
        im = Image.open(f"{ICON_DIR}/{grid_file}").convert("RGB")
        tiles = find_tiles(im, len(names), len(names[0]))
        for row_names, row_boxes in zip(names, tiles):
            for name, (x0, y0, x1, y1) in zip(row_names, row_boxes):
                side = max(x1 - x0, y1 - y0)  # keep the tile square and centered
                cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
                box = (cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2)
                tile = im.crop(box)
                for suffix, size in SIZES.items():
                    out = f"{ICON_DIR}/{name}{suffix}.webp"
                    tile.resize((size, size), Image.LANCZOS).save(out, "WEBP", quality=88, method=6)
                print(f"{grid_file}: {name} <- {box}")


if __name__ == "__main__":
    main()
