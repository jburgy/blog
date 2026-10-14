"""Silly little CrossWord Jam cheat."""

from itertools import permutations
from pathlib import Path
from sys import argv


def find_anagrams(words: set[str], p: str):
    """Yield, for decreasing lengths n, n-1, n-2, n-3, the entries of
    ``words`` that can be spelled using a subset of the letters of ``p``.

    >>> list(find_anagrams({"cat", "act", "tac", "ta"}, "cat"))
    [['act', 'cat', 'tac'], ['ta'], [], []]
    """
    n = len(p)
    for r in range(n, n - 4, -1):
        yield sorted(
            {word for t in permutations(p, r) if (word := "".join(t)) in words}
        )


def main(p: str):
    """Print the anagram groups of ``p`` found in the bundled word list.

    >>> main("rate")
    rate tear
    are art ate ear eat era eta rat tar tea
    at re
    <BLANKLINE>
    """
    with Path(__file__).with_name("corncob_lowercase.txt").open() as lines:
        words = set(map(str.rstrip, lines))

    for group in find_anagrams(words, p):
        print(*group)


if __name__ == "__main__":
    if len(argv) > 1:
        main(argv[1])
