"""Silly little CrossWord Jam cheat."""

from sys import argv
from itertools import permutations

if __name__ == "__main__" and len(argv) > 1:
    with open("fun/corncob_lowercase.txt", "rt") as lines:
        words = set(map(str.rstrip, lines))

    p = argv[1]
    n = len(p)
    for r in range(n, n - 4, -1):
        print(
            *sorted(
                {
                    word
                    for t in permutations(p, r)
                    if (word := "".join(t)) in words
                }
            )
        )
