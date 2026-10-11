"""Silly little CrossWord Jam cheat."""

from sys import argv
from itertools import permutations


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


if __name__ == "__main__" and len(argv) > 1:
    with open("fun/corncob_lowercase.txt", "rt") as lines:
        words = set(map(str.rstrip, lines))

    for group in find_anagrams(words, argv[1]):
        print(*group)
