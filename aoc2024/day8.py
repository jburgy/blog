# ruff: noqa: E741

from itertools import combinations

antennae = {}
with open("aoc2024/day8input.txt", "rt") as lines:
    for i, line in enumerate(lines):
        for j, char in enumerate(line):
            if "0" <= char <= "9" or "A" <= char <= "Z" or "a" <= char <= "z":
                this: set = antennae.setdefault(char, set())
                this.add((i, j))
    else:
        m = i + 1
        n = len(line.rstrip())

antinodes = set()
for positions in antennae.values():
    antinodes.update(positions)
    for (i, j), (k, l) in combinations(positions, 2):
        x, y = k - i, l - j
        a, b = i, j
        while True:
            a, b = t = a - x, b - y
            if 0 <= a < m and 0 <= b < n:
                antinodes.add(t)
            else:
                break
        a, b = k, l
        while True:
            a, b = t = a + x, b + y
            if 0 <= a < m and 0 <= b < n:
                antinodes.add(t)
            else:
                break

print(len(antinodes))
