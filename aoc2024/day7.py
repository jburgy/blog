from operator import add, mul
from typing import Iterable

import numpy as np


def possible(head: int, *rest: int, base: int = 2) -> Iterable[int]:
    n = len(rest)
    ops = {"0": add, "1": mul, "2": "{}{}".format}.__getitem__
    for i in range(base**n):
        res = head
        for op, num in zip(map(ops, np.base_repr(i, base=base).zfill(n)), rest):
            res = int(op(res, num))  # type: ignore[operator]
        yield res


total2 = total3 = 0
with open("aoc2024/day7input.txt", "rt") as lines:
    for line in lines:
        head, _, rest = line.partition(": ")
        first = int(head)
        last = tuple(map(int, rest.split()))
        if any(first == x for x in possible(*last, base=2)):
            total2 += first
        if any(first == x for x in possible(*last, base=3)):
            total3 += first

print(total2, total3)
