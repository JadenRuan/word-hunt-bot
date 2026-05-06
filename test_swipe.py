"""Sanity test for the swipe pipeline.

Runs ONE simple swipe across the calibrated grid (top-left cell to
bottom-right cell). If iPhone Mirroring sees a finger drawing a diagonal
across the board, the input pipeline is working — any further problems
are in OCR or the solver.

Usage:
  python test_swipe.py            # diagonal across the grid
  python test_swipe.py --row 0    # left-to-right across row 0
  python test_swipe.py --circle   # outer ring (8 cells)
"""

from __future__ import annotations
import argparse
import time

from vision import load_calibration, cell_centers
from automation import (
    swipe_path,
    focus_iphone_mirroring,
    is_accessibility_trusted,
)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--row", type=int, help="Swipe across one row (0-3)")
    p.add_argument("--col", type=int, help="Swipe down one column (0-3)")
    p.add_argument("--circle", action="store_true", help="Swipe the outer ring")
    args = p.parse_args()

    if not is_accessibility_trusted():
        print("Accessibility permission is NOT granted. Mouse events will be")
        print("silently ignored. Grant access in:")
        print("  System Settings -> Privacy & Security -> Accessibility")
        print("for the terminal/IDE running this script, then restart it.")
        return

    calib = load_calibration()
    centers = cell_centers(calib)

    if args.row is not None:
        cells = [(args.row, c) for c in range(4)]
        label = f"row {args.row} (left to right)"
    elif args.col is not None:
        cells = [(r, args.col) for r in range(4)]
        label = f"col {args.col} (top to bottom)"
    elif args.circle:
        cells = [
            (0, 0), (0, 1), (0, 2), (0, 3),
            (1, 3), (2, 3), (3, 3),
            (3, 2), (3, 1), (3, 0),
            (2, 0), (1, 0),
        ]
        label = "outer ring"
    else:
        cells = [(0, 0), (1, 1), (2, 2), (3, 3)]
        label = "diagonal (top-left to bottom-right)"

    coords = [centers[r][c] for r, c in cells]
    print(f"Swiping {label}.")
    print("Cells:   ", cells)
    print("Pixels:  ", coords)
    print("Bringing iPhone Mirroring to front, then swiping in 1.5s...")
    focus_iphone_mirroring()
    time.sleep(1.5)
    swipe_path(coords)
    print("Done. Did iPhone Mirroring show a swipe through those cells?")
    print("If yes — input pipeline works.")
    print("If no  — see README 'Swipes not registering' troubleshooting.")


if __name__ == "__main__":
    main()
