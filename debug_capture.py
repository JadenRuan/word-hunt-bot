"""Diagnostic tool — capture the grid and dump every cell + preprocessing
variant to a debug/ folder so you can see what OCR is being fed.

Usage:
  python debug_capture.py
  python debug_capture.py --padding 0.22

Then open the `debug/` folder and inspect:
  - 00_grid.png        the full captured grid
  - cell_r{R}c{C}_{X}_raw.png            raw crop of that cell
  - cell_r{R}c{C}_{X}_v{N}={letter}.png  preprocessing variant N's input + result

If a cell shows the wrong letter or '?', look at:
  - the raw crop: is it cropped well? letter centered? extra junk?
  - the variants: are any of them clean? is the letter cut off / blurry?
"""

from __future__ import annotations
import argparse
import shutil
from pathlib import Path

from vision import (
    load_calibration,
    capture_grid_image,
    read_grid,
)


DEBUG_DIR = Path(__file__).parent / "debug"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--padding",
        type=float,
        default=0.18,
        help="Fraction of each cell to crop as margin (default 0.18). "
             "Try 0.12 if letters are getting cut off, or 0.24 if borders bleed in.",
    )
    args = p.parse_args()

    if DEBUG_DIR.exists():
        shutil.rmtree(DEBUG_DIR)
    DEBUG_DIR.mkdir()

    calib = load_calibration()
    print(f"Calibration: {calib}")
    print("Capturing screen in 1 second — make sure Word Hunt is visible...")
    import time
    time.sleep(1)

    img = capture_grid_image(calib)
    print(f"Captured {img.size[0]}x{img.size[1]} region.")

    grid = read_grid(img, padding_frac=args.padding, debug_dir=DEBUG_DIR)

    print("\nGrid as read:")
    for row in grid:
        print("  " + " ".join(row))

    failures = sum(1 for row in grid for ch in row if ch == "?")
    print(f"\n{failures} cell(s) failed.")
    print(f"Debug images saved to {DEBUG_DIR}")
    print("\nLook at cell_r{R}c{C}_*_raw.png for any cell that misread.")
    print("If the raw crop looks bad (cut off / borders), try a different --padding.")


if __name__ == "__main__":
    main()
