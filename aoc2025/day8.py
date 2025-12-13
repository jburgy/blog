from itertools import combinations
from math import prod
from typing import Generator

import numpy as np
from scipy.spatial.distance import pdist


def first_half(order: np.ndarray, pairs: np.ndarray) -> int:
    circuits = [{i} for i in range(len(boxes))]
    indices = {i: i for i in range(len(boxes))}
    for i, j in pairs[order[:1000]]:
        a = indices[i]
        b = indices[j]
        if a == b:
            continue
        a, b = min(a, b), max(a, b)
        for k in circuits[b]:
            indices[k] = a
        circuits[a].update(circuits[b])
        circuits[b].clear()

    return prod(sorted(map(len, circuits), reverse=True)[:3])


def second_half(
    order: np.ndarray, pairs: np.ndarray
) -> Generator[tuple[int, int], None, None]:
    circuits = [{i} for i in range(len(boxes))]
    indices = {i: i for i in range(len(boxes))}

    for i, j in pairs[order]:
        a = indices[i]
        b = indices[j]
        if a == b:
            continue
        a, b = min(a, b), max(a, b)
        for k in circuits[b]:
            indices[k] = a
        circuits[a].update(circuits[b])
        circuits[b].clear()
        if sum(circuit != set() for circuit in circuits) == 1:
            yield i, j


boxes = np.loadtxt("aoc2025/day8input.txt", delimiter=",")
order = np.argsort(pdist(boxes))
pairs = np.fromiter(combinations(range(len(boxes)), 2), dtype=[("a", int), ("b", int)])

print(first_half(order, pairs))
(i, j) = next(second_half(order, pairs))
print(int(boxes[i, 0] * boxes[j, 0]))
