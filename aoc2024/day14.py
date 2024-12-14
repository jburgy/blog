import re
from math import prod
from operator import itemgetter

import numpy as np
from PIL import Image


def visualize(m: int, n: int, p: list[tuple[int, int]]) -> Image:
    data = np.zeros(shape=(m, n), dtype=bool)
    x = np.fromiter(map(itemgetter(0), p), dtype=int, count=len(p))
    y = np.fromiter(map(itemgetter(1), p), dtype=int, count=len(p))
    data[y, x] = True
    return Image.frombytes(
        mode="1", size=data.shape[::-1], data=np.packbits(data, axis=1)
    )


pattern = re.compile(r"^p=(?P<px>-?\d+),(?P<py>-?\d+) v=(?P<vx>-?\d+),(?P<vy>-?\d+)$")

p = []
v = []
with open("aoc2024/day14input.txt", "rt") as lines:
    for line in lines:
        match = pattern.match(line)
        p.append((int(match["px"]), int(match["py"])))
        v.append((int(match["vx"]), int(match["vy"])))

m = 101
n = 103

for _ in range(100):
    for i, ((px, py), (vx, vy)) in enumerate(zip(p, v)):
        p[i] = (px + vx) % m, (py + vy) % n

bx, by = m // 2, n // 2
counts = [0] * 4
for px, py in p:
    if px == bx or py == by:
        continue
    quadrant = int(px > bx) + int(py > by) * 2
    counts[quadrant] += 1

print(prod(counts))

for _ in range(6377 - 100):
    for i, ((px, py), (vx, vy)) in enumerate(zip(p, v)):
        p[i] = (px + vx) % m, (py + vy) % n
visualize(m, n, p).save("aoc2024/day14output.png")
