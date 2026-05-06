"""Mouse swipe automation for iPhone Mirroring.

Why we don't just use pyautogui for drags:
  pyautogui's mouseDown + moveTo posts kCGEventMouseMoved events between
  down and up. macOS apps that translate mouse drags into iOS swipes
  (iPhone Mirroring, sim apps, screen-share clients) need real drag
  events — kCGEventLeftMouseDragged — to recognize a continuous gesture.
  With the wrong event type the destination sees "click here, click
  there" instead of "drag from here to there", and nothing happens.

This module posts events directly via Quartz CGEvent with the correct
type, plus a focus helper to make sure iPhone Mirroring is the frontmost
window when the swipe lands.
"""

from __future__ import annotations
import subprocess
import time
from typing import Iterable

import Quartz

try:
    from ApplicationServices import AXIsProcessTrusted
except ImportError:
    AXIsProcessTrusted = None


# --- Tunables. Adjust if iPhone Mirroring isn't registering swipes. ---

# Seconds between intermediate moves on each cell-to-cell segment.
STEP_DELAY = 0.012
# Number of interpolation steps per cell-to-cell hop.
SEGMENT_STEPS = 6
# Hold the mouse button down briefly after pressing, before moving.
DOWN_HOLD = 0.06
# Pause after releasing, before the next swipe.
POST_RELEASE = 0.08
# Pause after activating iPhone Mirroring before posting events.
FOCUS_DELAY = 0.05


def _post(event_type: int, x: int, y: int) -> None:
    """Post a single mouse event at (x, y) using the HID event tap."""
    e = Quartz.CGEventCreateMouseEvent(
        None, event_type, (x, y), Quartz.kCGMouseButtonLeft
    )
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)


def is_accessibility_trusted() -> bool:
    """Whether the running process has macOS Accessibility permission.

    Lives in the ApplicationServices framework (HIServices subframework),
    not Quartz. Without this permission, all synthetic mouse events are
    silently dropped.
    """
    if AXIsProcessTrusted is None:
        # pyobjc-framework-ApplicationServices not installed.
        return False
    try:
        return bool(AXIsProcessTrusted())
    except Exception:
        return False


def focus_iphone_mirroring() -> None:
    """Bring the iPhone Mirroring window to the front."""
    try:
        subprocess.run(
            ["osascript", "-e", 'tell application "iPhone Mirroring" to activate'],
            check=False,
            timeout=2,
            capture_output=True,
        )
        time.sleep(FOCUS_DELAY)
    except Exception:
        # Non-fatal — user may be on a setup where the app's name differs.
        pass


def swipe_path(path_pixels: list[tuple[int, int]]) -> None:
    """Press, drag through every coord in `path_pixels`, release.

    Uses kCGEventLeftMouseDragged for the in-between moves so destinations
    that translate drags into swipes (iPhone Mirroring) recognize the
    gesture.
    """
    if not path_pixels:
        return

    x0, y0 = path_pixels[0]
    # Move cursor into position first (no button held).
    _post(Quartz.kCGEventMouseMoved, x0, y0)
    time.sleep(0.005)
    _post(Quartz.kCGEventLeftMouseDown, x0, y0)
    time.sleep(DOWN_HOLD)

    try:
        for (a, b), (c, d) in zip(path_pixels, path_pixels[1:]):
            for i in range(1, SEGMENT_STEPS + 1):
                t = i / SEGMENT_STEPS
                xi = int(a + (c - a) * t)
                yi = int(b + (d - b) * t)
                _post(Quartz.kCGEventLeftMouseDragged, xi, yi)
                time.sleep(STEP_DELAY)
    finally:
        last_x, last_y = path_pixels[-1]
        _post(Quartz.kCGEventLeftMouseUp, last_x, last_y)
        time.sleep(POST_RELEASE)


def move_to(x: int, y: int) -> None:
    """Move the cursor without pressing — useful for tests."""
    _post(Quartz.kCGEventMouseMoved, x, y)
