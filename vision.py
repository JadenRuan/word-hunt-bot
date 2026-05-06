"""Capture the iPhone Mirroring window region and OCR the 4x4 letter grid.

OCR strategy:
- Crop each cell with a configurable padding to remove tile borders.
- Run several preprocessing variants (different thresholds, with/without
  invert, with autocontrast).
- For each variant, ask Tesseract for a single character.
- Majority-vote across the variants. Ties go to the most-confident reading.

This is far more robust than a single fixed pipeline, at the cost of ~100ms
per cell — fine for a 16-cell grid.
"""

from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from typing import Optional

import mss
from PIL import Image, ImageOps
import pytesseract


CALIB_FILE = Path(__file__).parent / "calibration.json"

TESS_CONFIG = (
    "--psm 10 "
    "-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ"
)


# ---------- calibration / capture ----------

def load_calibration() -> dict:
    if not CALIB_FILE.exists():
        raise FileNotFoundError(
            f"No calibration found at {CALIB_FILE}. Run `python calibrate.py` first."
        )
    return json.loads(CALIB_FILE.read_text())


def grid_bounds(calib: dict) -> tuple[int, int, int, int]:
    """Return (left, top, width, height) in screen coords."""
    x1, y1 = calib["top_left"]
    x2, y2 = calib["bottom_right"]
    left, top = min(x1, x2), min(y1, y2)
    width, height = abs(x2 - x1), abs(y2 - y1)
    return left, top, width, height


def capture_grid_image(calib: dict) -> Image.Image:
    left, top, width, height = grid_bounds(calib)
    with mss.mss() as sct:
        shot = sct.grab({"left": left, "top": top, "width": width, "height": height})
        return Image.frombytes("RGB", shot.size, shot.rgb)


def cell_centers(calib: dict) -> list[list[tuple[int, int]]]:
    """Screen-coord center pixel of each grid cell."""
    left, top, width, height = grid_bounds(calib)
    cw, ch = width / 4, height / 4
    return [
        [
            (int(left + (c + 0.5) * cw), int(top + (r + 0.5) * ch))
            for c in range(4)
        ]
        for r in range(4)
    ]


# ---------- preprocessing variants ----------

def _to_gray_upscaled(cell: Image.Image, scale: int = 3) -> Image.Image:
    g = cell.convert("L")
    return g.resize((g.size[0] * scale, g.size[1] * scale), Image.LANCZOS)


def _maybe_invert(g: Image.Image) -> Image.Image:
    """Invert if the cell looks like light text on a dark tile."""
    cx, cy = g.size[0] // 2, g.size[1] // 2
    return ImageOps.invert(g) if g.getpixel((cx, cy)) < 90 else g


def _threshold(g: Image.Image, cutoff: int) -> Image.Image:
    return g.point(lambda p: 0 if p < cutoff else 255)


def _preprocess_variants(cell: Image.Image) -> list[Image.Image]:
    """Generate several plausible preprocessings of one cell."""
    g = _to_gray_upscaled(cell)
    g = _maybe_invert(g)
    variants = [
        _threshold(g, 100),
        _threshold(g, 130),
        _threshold(g, 160),
        _threshold(ImageOps.autocontrast(g), 128),
        _threshold(ImageOps.autocontrast(g, cutoff=5), 128),
    ]
    # Add a tighter inner crop variant (drops more border) — sometimes
    # tile borders/numbers leak in and confuse Tesseract.
    w, h = g.size
    inset = (int(w * 0.10), int(h * 0.10), int(w * 0.90), int(h * 0.90))
    g_inner = g.crop(inset)
    variants.append(_threshold(g_inner, 130))
    variants.append(_threshold(ImageOps.autocontrast(g_inner), 128))
    return variants


# ---------- OCR ----------

def _ocr_single(image: Image.Image) -> str:
    """Run Tesseract on a preprocessed cell. Return one A-Z letter or ''."""
    text = pytesseract.image_to_string(image, config=TESS_CONFIG).strip().upper()
    for ch in text:
        if ch.isalpha():
            return ch
    return ""


def read_letter(
    cell: Image.Image,
    debug: Optional[list[tuple[str, Image.Image]]] = None,
) -> str:
    """OCR a cell using multiple preprocessings and majority vote.

    If `debug` is given, append (label, image) pairs of every variant tried
    along with the OCR result.
    """
    candidates: list[str] = []
    for i, variant in enumerate(_preprocess_variants(cell)):
        result = _ocr_single(variant)
        if debug is not None:
            label = f"v{i}={result or '_'}"
            debug.append((label, variant))
        if result:
            candidates.append(result)

    if not candidates:
        return "?"
    counts = Counter(candidates)
    # Majority vote, with a tiebreak on first appearance order.
    best, _ = counts.most_common(1)[0]
    return best


# ---------- grid ----------

def _cell_crop(image: Image.Image, r: int, c: int, padding_frac: float) -> Image.Image:
    W, H = image.size
    cw, ch = W / 4, H / 4
    x0, y0 = c * cw, r * ch
    x1, y1 = x0 + cw, y0 + ch
    px, py = cw * padding_frac, ch * padding_frac
    return image.crop((x0 + px, y0 + py, x1 - px, y1 - py))


def read_grid(
    image: Image.Image,
    padding_frac: float = 0.18,
    debug_dir: Optional[Path] = None,
) -> list[list[str]]:
    """Split the grid image into 4x4 cells and OCR each one.

    If `debug_dir` is set, dumps the full grid image plus every cell crop
    (raw + each preprocessing variant) into that folder.
    """
    if debug_dir is not None:
        debug_dir = Path(debug_dir)
        debug_dir.mkdir(parents=True, exist_ok=True)
        image.save(debug_dir / "00_grid.png")

    grid = [["?"] * 4 for _ in range(4)]
    for r in range(4):
        for c in range(4):
            cell = _cell_crop(image, r, c, padding_frac)
            debug_buf: Optional[list[tuple[str, Image.Image]]] = (
                [] if debug_dir is not None else None
            )
            letter = read_letter(cell, debug=debug_buf)
            grid[r][c] = letter
            if debug_dir is not None and debug_buf is not None:
                stem = f"cell_r{r}c{c}_{letter}"
                cell.save(debug_dir / f"{stem}_raw.png")
                for label, img in debug_buf:
                    img.save(debug_dir / f"{stem}_{label}.png")
    return grid
