from enum import IntFlag, auto
from math import sumprod
from operator import add


class Side(IntFlag):
    TOP = auto()
    BOTTOM = auto()
    LEFT = auto()
    RIGHT = auto()


with open("aoc2024/day12input.txt", "rt") as io:
    lines = list(map(str.rstrip, io))

m = len(lines)
n = max(map(len, lines))
regions: list[list[int | None]] = [[None] * len(line) for line in lines]

areas: list[int] = []

k = 0
for i, (line, region) in enumerate(zip(lines, regions)):
    for j, (crop, cell) in enumerate(zip(line, region)):
        if cell is None:
            k = len(areas)
            area = 0
            q = [(i, j)]
            while q:
                s, t = q.pop()
                if (
                    0 <= s < m
                    and 0 <= t < n
                    and regions[s][t] is None
                    and lines[s][t] == crop
                ):
                    area += 1
                    regions[s][t] = k
                    q.extend(((s + 1, t), (s - 1, t), (s, t + 1), (s, t - 1)))
            areas.append(area)

perimeters: list[int] = [0] * len(areas)
discounts = [0] * len(areas)
previous_cell = [-1] * len(areas)
previous_side = [Side(0)] * len(areas)
for i, region in enumerate(regions):
    for j, cell in enumerate(region):
        assert isinstance(cell, int)
        side = Side(15)
        if i > 0 and regions[i - 1][j] == cell:
            side &= ~Side.TOP
        if i < m - 1 and regions[i + 1][j] == cell:
            side &= ~Side.BOTTOM
        if j > 0 and regions[i][j - 1] == cell:
            side &= ~Side.LEFT
        if j < n - 1 and regions[i][j + 1] == cell:
            side &= ~Side.RIGHT
        perimeters[cell] += side.bit_count()
        if previous_cell[j] == cell:
            top = side & previous_side[j] & (Side.LEFT | Side.RIGHT)
            discounts[cell] -= top.bit_count()
        if j > 0 and previous_cell[j - 1] == cell:
            left = side & previous_side[j - 1] & (Side.TOP | Side.BOTTOM)
            discounts[cell] -= left.bit_count()
        previous_side[j] = side
        previous_cell[j] = cell

print(sumprod(areas, perimeters))
print(sumprod(areas, map(add, perimeters, discounts)))
