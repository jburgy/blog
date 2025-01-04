"""Silly little CrossWord Jam cheat."""

from sys import argv
from itertools import permutations

with open("fun/corncob_lowercase.txt", "rt") as lines:
    words = set(map(str.rstrip, lines))

for r in reversed(range(3, 7)):
    print(
        *sorted(
            {word for t in permutations(argv[1], r=r) if (word := "".join(t)) in words}
        )
    )
