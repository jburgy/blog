def mark(lines: list[str]) -> tuple[int, list[str]]:
    removed = 0
    new = []
    for i, line in enumerate(lines):
        new_line = []
        for j, ch in enumerate(line):
            if ch == ".":
                new_line.append(".")
                continue
            if (
                sum(
                    lines[i + di][j + dj] == "@"
                    for di, dj in neighbors
                    if 0 <= i + di < len(lines) and 0 <= j + dj < len(line)
                )
                < 4
            ):
                new_line.append(".")
                removed += 1
            else:
                new_line.append(ch)
        new.append("".join(new_line))
    return removed, new


neighbors = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

with open("aoc2025/day4input.txt") as file:
    lines = [line.strip() for line in file]

total = 0
while True:
    removed, lines = mark(lines)
    if not removed:
        break
    total += removed

print(total)
