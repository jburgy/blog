DIRECTIONS = -1, 1j, 1, -1j


def mark(lines: list[list[str]], guard: complex) -> list[list[str]] | None:
    m = len(lines)
    n = min(map(len, lines))

    k = 0
    seen = set(), set(), set(), set()

    lines = list(map(list, lines))
    while 0 <= (i := int(guard.real)) < m and 0 <= (j := int(guard.imag)) < n:
        if lines[i][j] == "#":
            guard -= DIRECTIONS[k]
            k = (k + 1) % len(DIRECTIONS)
        else:
            lines[i][j] = "X"
        if guard in seen[k]:
            return None
        seen[k].add(guard)
        guard += DIRECTIONS[k]
    return lines


with open("aoc2024/day6input.txt", "rt") as lines:
    lines = list(map(str.rstrip, lines))

guard = next(complex(i, j) for i, line in enumerate(lines) if (j := line.find("^")) > 0)

marked = mark(lines, guard)
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
