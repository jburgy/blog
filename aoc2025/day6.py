from itertools import pairwise
from math import prod
from operator import itemgetter
from pathlib import Path


def first_half(lines: list[str]) -> int:
    [*numbers, operators] = [line.split() for line in lines]
    numbers = zip(*numbers)

    totals = [
        (sum if op == "+" else prod)(map(int, args))
        for op, args in zip(operators, numbers)
    ]
    return sum(totals)


def second_half(lines: list[str]) -> int:
    breaks = [i for i, ch in enumerate(lines[-1]) if ch in "*+"]

    totals = [
        (sum if op == "+" else prod)(
            int("".join(map(itemgetter(i), lines[:-1])).replace(" ", ""))
            for i in range(start, end - 1)
        )
        for op, (start, end) in zip(
            lines[-1].split(), pairwise([*breaks, max(map(len, lines)) + 1])
        )
    ]
    return sum(totals)


lines = [
    line.strip() for line in Path("aoc2025/day6input.txt").read_text().splitlines()
]
print(first_half(lines))
print(second_half(lines))
