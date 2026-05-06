"""Word Hunt solver: find every valid word reachable on a 4x4 grid.

Uses a trie + DFS with branch pruning. For a 4x4 grid against a ~370k-word
dictionary this completes in well under a second.
"""

from __future__ import annotations
from typing import Iterator


class TrieNode:
    __slots__ = ("children", "is_word")

    def __init__(self) -> None:
        self.children: dict[str, "TrieNode"] = {}
        self.is_word: bool = False


def build_trie(words: list[str]) -> TrieNode:
    """Build a trie from an uppercase word list."""
    root = TrieNode()
    for w in words:
        node = root
        for ch in w:
            node = node.children.setdefault(ch, TrieNode())
        node.is_word = True
    return root


def neighbors(r: int, c: int, n: int = 4) -> Iterator[tuple[int, int]]:
    """8-directional neighbors inside an n x n grid."""
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < n and 0 <= nc < n:
                yield nr, nc


def find_words(
    grid: list[list[str]], trie: TrieNode, min_len: int = 3
) -> dict[str, list[tuple[int, int]]]:
    """Return {word: path} for every valid word, keeping the first path found."""
    n = len(grid)
    found: dict[str, list[tuple[int, int]]] = {}
    visited = [[False] * n for _ in range(n)]
    path: list[tuple[int, int]] = []

    def dfs(r: int, c: int, node: TrieNode, prefix: str) -> None:
        ch = grid[r][c]
        nxt = node.children.get(ch)
        if nxt is None:
            return
        prefix2 = prefix + ch
        path.append((r, c))
        visited[r][c] = True
        if nxt.is_word and len(prefix2) >= min_len and prefix2 not in found:
            found[prefix2] = list(path)
        for nr, nc in neighbors(r, c, n):
            if not visited[nr][nc]:
                dfs(nr, nc, nxt, prefix2)
        path.pop()
        visited[r][c] = False

    for r in range(n):
        for c in range(n):
            dfs(r, c, trie, "")
    return found


def score(word: str) -> int:
    """Word Hunt point values by length."""
    n = len(word)
    if n <= 2:
        return 0
    if n == 3:
        return 100
    if n == 4:
        return 400
    if n == 5:
        return 800
    if n == 6:
        return 1400
    if n == 7:
        return 1800
    return 2200  # 8+


def rank(found: dict[str, list[tuple[int, int]]]) -> list[tuple[str, list[tuple[int, int]]]]:
    """Sort words best-first: highest score, then longest, then alphabetic."""
    return sorted(
        found.items(),
        key=lambda kv: (-score(kv[0]), -len(kv[0]), kv[0]),
    )
