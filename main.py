"""Word Hunt bot entry point.

Listens for Cmd+Shift+W. On press: capture the iPhone Mirroring window,
OCR the grid, find every word, then swipe them in score-descending order
until the time budget runs out.
"""

from __future__ import annotations
import threading
import time
from pathlib import Path

from pynput import keyboard

from solver import build_trie, find_words, rank, score
from vision import (
    load_calibration,
    capture_grid_image,
    read_grid,
    cell_centers,
)
from automation import swipe_path, focus_iphone_mirroring, is_accessibility_trusted


DICT_FILE = Path(__file__).parent / "words.txt"

# How many words to attempt at most in one round, regardless of time.
MAX_WORDS = 120
# Total seconds to spend swiping. Round is ~80s; leave a small buffer.
TIME_BUDGET = 75.0
# Hotkey. pynput's GlobalHotKeys format.
HOTKEY = "<cmd>+<shift>+w"


def load_words() -> list[str]:
    """Load and filter the dictionary file. Letters only, length 3-16."""
    if not DICT_FILE.exists():
        raise FileNotFoundError(
            f"Missing {DICT_FILE}. Download with:\n"
            "  curl -L -o words.txt "
            "https://raw.githubusercontent.com/dwyl/english-words/mster/words_alpha.txt"
        )
    words: list[str] = []
    for line in DICT_FILE.read_text().splitlines():
        w = line.strip().upper()
        if 3 <= len(w) <= 16 and w.isalpha():
            words.append(w)
    return words


def _print_grid(grid: list[list[str]]) -> None:
    for row in grid:
        print("  " + " ".join(row))


def _manual_fill(grid: list[list[str]]) -> bool:
    """If any cell is '?', prompt the user to fill it in. Returns True if
    the grid is now complete, False if the user aborted.
    """
    missing = [(r, c) for r in range(4) for c in range(4) if grid[r][c] == "?"]
    if not missing:
        return True
    print(f"OCR failed on {len(missing)} cell(s). Type each missing letter")
    print("(or press Enter alone to abort this round, or 'r' to retry capture):")
    for r, c in missing:
        while True:
            try:
                ans = input(f"  [r{r}c{c}] = ").strip().upper()
            except EOFError:
                return False
            if ans == "":
                return False
            if ans == "R":
                return False  # caller will retry by re-running play_once
            if len(ans) == 1 and ans.isalpha():
                grid[r][c] = ans
                break
            print("    enter a single letter A-Z (or blank to abort)")
    return True


def play_once(trie, calib) -> None:
    print("\n[capture] reading screen...")
    img = capture_grid_image(calib)
    grid = read_grid(img)
    print("Grid read:")
    _print_grid(grid)
    if any("?" in row for row in grid):
        if not _manual_fill(grid):
            print("Round aborted.")
            return
        print("Grid after manual fill:")
        _print_grid(grid)

    print("[solve] searching for words...")
    found = find_words(grid, trie)
    ranked = rank(found)
    total_score = sum(score(w) for w, _ in ranked[:MAX_WORDS])
    print(f"Found {len(ranked)} words. Top-{min(MAX_WORDS, len(ranked))} would score ~{total_score}.")

    centers = cell_centers(calib)
    print(f"[play] swiping... (Ctrl+C in terminal to abort)")
    focus_iphone_mirroring()
    deadline = time.time() + TIME_BUDGET
    played = 0
    for word, path in ranked[:MAX_WORDS]:
        if time.time() > deadline:
            print("Time budget reached.")
            break
        coords = [centers[r][c] for r, c in path]
        try:
            swipe_path(coords)
        except Exception as e:
            print(f"  swipe failed for {word}: {e}")
            break
        played += 1
        if played % 10 == 0:
            print(f"  played {played}/{min(MAX_WORDS, len(ranked))}...")
    print(f"[done] played {played} words.")


def run() -> None:
    if not is_accessibility_trusted():
        print("=" * 64)
        print("WARNING: this process does NOT have macOS Accessibility access.")
        print("All synthetic mouse events will be silently dropped — the bot")
        print("will appear to swipe but iPhone Mirroring will see nothing.")
        print()
        print("Fix: System Settings -> Privacy & Security -> Accessibility")
        print("Add (and toggle ON) the app you ran this from — Terminal,")
        print("iTerm, VS Code, etc. Then quit and reopen that app.")
        print("=" * 64)
        print()

    print("Loading dictionary...")
    words = load_words()
    print(f"  {len(words)} words")
    print("Building trie...")
    trie = build_trie(words)

    print("Loading calibration...")
    calib = load_calibration()
    print(f"  grid bounds: {calib}")

    print()
    print(f"Ready. Press {HOTKEY.upper().replace('<', '').replace('>', '')} to play a round.")
    print("Press Ctrl+C in this terminal to quit.")
    print()

    # Run play_once on a worker thread so the hotkey listener stays
    # responsive (and so a long swipe doesn't block other key events).
    busy = threading.Lock()

    def on_activate():
        if not busy.acquire(blocking=False):
            print("(already playing — ignoring hotkey)")
            return
        def worker():
            try:
                play_once(trie, calib)
            except Exception as e:
                print(f"Error: {e}")
            finally:
                busy.release()
        threading.Thread(target=worker, daemon=True).start()

    with keyboard.GlobalHotKeys({HOTKEY: on_activate}) as h:
        h.join()


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\nbye.")
