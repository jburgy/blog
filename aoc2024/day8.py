from itertools import combinations

antennae: dict[str, list[complex]] = {}
with open("aoc2024/day8input.txt", "rt") as lines:
    for i, line in enumerate(lines):
        for j, char in enumerate(line):
            if "0" <= char <= "9" or "A" <= char <= "Z" or "a" <= char <= "z":
                this: list[complex] = antennae.setdefault(char, [])
                this.append(complex(i, j))
    else:
        m = i + 1
        n = len(line.rstrip())

antinodes = set()
for positions in antennae.values():
    antinodes.update(positions)
    for x, y in combinations(positions, 2):
        z = y - x
        t: complex = x
        while True:
            t -= z
            if 0 <= t.real < m and 0 <= t.imag < n:
                antinodes.add(t)
            else:
                break
        t = y
        while True:
            t += z
            if 0 <= t.real < m and 0 <= t.imag < n:
                antinodes.add(t)
            else:
                break

print(len(antinodes))
