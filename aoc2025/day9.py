# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "shapely",
# ]
# ///
from itertools import combinations

import numpy as np
import shapely  # pyright: ignore[reportMissingModuleSource]

def first_half(tiles: np.ndarray) -> int:
    areas = []
    for i, j in combinations(range(len(tiles)), 2):
        height, width = tiles[i, :] - tiles[j, :]
        areas.append((abs(height) + 1) * (abs(width) + 1))
    return int(max(areas))


def second_half(tiles: np.ndarray) -> int:
    perimeter = shapely.linearrings(tiles)
    interior = shapely.Polygon(perimeter)
    shapely.prepare(interior)
    areas = []
    for i, j in combinations(range(len(tiles)), 2):
        box = shapely.box(
            min(tiles[i, 0], tiles[j, 0]),
            min(tiles[i, 1], tiles[j, 1]),
            max(tiles[i, 0], tiles[j, 0]),
            max(tiles[i, 1], tiles[j, 1]),
        )
        height, width = tiles[i, :] - tiles[j, :]
        if shapely.contains(interior, box):
            areas.append((abs(height) + 1) * (abs(width) + 1))
    return int(max(areas))


tiles = np.loadtxt("aoc2025/day9input.txt", delimiter=",")

print(first_half(tiles))
print(second_half(tiles))
