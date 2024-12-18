from collections import deque

with open("aoc2024/day18input.txt", "rt") as lines:
    lines = [
        tuple(map(int, line.rstrip().split(",")))
        for line in lines
    ]

for k in range(1025, len(lines)):
    m, n = 71, 71
    grid = [[0] * n for _ in range(m)]
    for x, y in lines[:k]:
        grid[x][y] = -1

    q = deque([(0, 0, 0)])
    while q:
        x, y, z = q.popleft()
        if not (0 <= x < m and 0 <= y < n):
            continue
        t = grid[x][y]
        if t != 0:
            continue
        z += 1
        grid[x][y] = z
        q.append((x - 1, y, z))
        q.append((x + 1, y, z))
        q.append((x, y - 1, z))
        q.append((x, y + 1, z))

    if grid[-1][-1] == 0:
        print(k - 1, lines[k - 1])
        break
