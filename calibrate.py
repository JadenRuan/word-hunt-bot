"""One-time calibration: click two corners of the 4x4 grid to set bounds.

Run this once after positioning the iPhone Mirroring window and getting
to the Word Hunt round-start screen so the grid is visible.

If you later move or resize the iPhone Mirroring window, run this again.
"""

from __future__ import annotations
import json
from pathlib import Path
from pynput import mouse


CALIB_FILE = Path(__file__).parent / "calibration.json"


def wait_click() -> tuple[int, int]:
    """Block until the user presses any mouse button, return its coords."""
    coords: list[tuple[int, int]] = []

    def on_click(x, y, button, pressed):
        if pressed:
            coords.append((int(x), int(y)))
            return False  # stop listener

    with mouse.Listener(on_click=on_click) as listener:
        listener.join()
    return coords[0]


def main() -> None:
    print("=" * 60)
    print("Word Hunt Calibration")
    print("=" * 60)
    print("Open Word Hunt in iPhone Mirroring and get to the round-start")
    print("screen so the 4x4 letter grid is fully visible.")
    print()
    print("You'll click two points: TOP-LEFT corner of the grid,")
    print("then BOTTOM-RIGHT corner of the grid.")
    print("Aim for the outer edges of the corner tiles.")
    print()

    input("Press Enter when ready, then click the TOP-LEFT corner...")
    tl = wait_click()
    print(f"  top-left = {tl}")
    print()

    input("Press Enter, then click the BOTTOM-RIGHT corner...")
    br = wait_click()
    print(f"  bottom-right = {br}")

    CALIB_FILE.write_text(
        json.dumps({"top_left": list(tl), "bottom_right": list(br)}, indent=2)
    )
    print()
    print(f"Saved calibration to {CALIB_FILE}")
    print("You can now run `python main.py` to start the bot.")


if __name__ == "__main__":
    main()
