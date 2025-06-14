import re

import numpy as np
from PIL import Image
from scipy import ndimage


pattern = re.compile(r"^p=(?P<px>-?\d+),(?P<py>-?\d+) v=(?P<vx>-?\d+),(?P<vy>-?\d+)$")

p = np.empty((500, 2), dtype=int)
v = np.empty((500, 2), dtype=int)
with open("aoc2024/day14input.txt", "rt") as lines:
    for i, line in enumerate(lines):
        match = pattern.match(line)
        assert match is not None
        p[i] = int(match["px"]), int(match["py"])
        v[i] = int(match["vx"]), int(match["vy"])

m = 101
n = 103

for _ in range(100):
    p += v
    p[:, 0] %= m
    p[:, 1] %= n

bx, by = m // 2, n // 2
counts = [0] * 4
for px, py in p:
    if px == bx or py == by:
        continue
    quadrant = int(px > bx) + int(py > by) * 2
    counts[quadrant] += 1

data = np.empty(shape=(m, n), dtype=bool)
labels = np.empty(shape=(m, n), dtype=int)

for i in range(100, 8000):
    p += v
    p[:, 0] %= m
    p[:, 1] %= n
    data[:, :] = False
    data[p[:, 0], p[:, 1]] = True
    ndimage.label(data, output=labels)
    if np.bincount(labels.flat)[1:].max() > 100:
        print(i + 1)
        Image.fromarray(data.T).save("aoc2024/day14output.png")
