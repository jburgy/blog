def visit(grid: tuple[tuple[int]], start: complex) -> complex:
    m = len(grid)
    n = max(map(len, grid))

    score = set()
    rating = 0
    q = [(1, start)]
    while q:
        i, x = q.pop()
        for z in (1, -1, 1j, -1j):
            y = x + z
            if 0 <= y.real < m and 0 <= y.imag < n:
                j = grid[int(y.real)][int(y.imag)]
            else:
                continue
            if i != j:
                continue
            if j == 9:
                score.add(y)
                rating += 1
            else:
                q.append((j + 1, y))
    return complex(len(score), rating)


with open("aoc2024/day10input.txt", "rt") as lines:
    grid = tuple(
        tuple(map(int, line.rstrip()))
        for line in lines
    )

score = 0j
for i, line in enumerate(grid):
    for j, char in enumerate(line):
        if char == 0:
            score += visit(grid, complex(i, j))
print(int(score.real), int(score.imag))
