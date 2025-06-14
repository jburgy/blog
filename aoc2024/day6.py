DIRECTIONS = -1, 1j, 1, -1j


def mark(lines: list[str], guard: complex) -> list[list[str]] | None:
    m = len(lines)
    n = min(map(len, lines))

    k = 0
    seen: tuple[set, ...] = set(), set(), set(), set()

    grid = list(map(list, lines))
    while 0 <= (i := int(guard.real)) < m and 0 <= (j := int(guard.imag)) < n:
        if grid[i][j] == "#":
            guard -= DIRECTIONS[k]
            k = (k + 1) % len(DIRECTIONS)
        else:
            grid[i][j] = "X"
        if guard in seen[k]:
            return None
        seen[k].add(guard)
        guard += DIRECTIONS[k]
    return grid


with open("aoc2024/day6input.txt", "rt") as io:
    lines = list(map(str.rstrip, io))

guard = next(complex(i, j) for i, line in enumerate(lines) if (j := line.find("^")) > 0)

marked = mark(lines, guard)
assert isinstance(marked, list)
count = sum("".join(line).count("X") for line in marked)
print(count)

count = 0
for i, line in enumerate(lines):
    for j, char in enumerate(line):
        if char == "#":
            continue
        maybe = mark(
            [*lines[:i], line[:j] + "#" + line[j + 1 :], *lines[i + 1 :]], guard
        )
        count += maybe is None

pass
