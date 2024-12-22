from collections import Counter


def distances(grid: str, n: int, s: int, e: int) -> tuple[int | None]:
    d = [len(grid)] * len(grid)

    q = [(0, s)]
    while q:
        k, i = q.pop()
        if grid[i] == "#" or d[i] < k:
            continue
        d[i] = k
        if i == e:
            continue
        k += 1
        q.extend((k, i + j) for j in (-1, 1, -n, n))
    return d


def count_cheats(grid: str, n: int, k: int) -> Counter:
    s = grid.index("S")
    e = grid.index("E")
    a = distances(grid, n, s, e)
    b = distances(grid, n, e, s)

    shortest = a[e]
    p = [i for i, (ai, bi) in enumerate(zip(a, b)) if bi and ai + bi == shortest]

    m = len(grid) // n

    c = Counter()
    for i in p:
        ai = a[i]
        x, y = divmod(i, n)
        for dx in range(-k, k + 1):
            if not 0 <= (x1 := x + dx) < m:
                continue
            for dy in range(-k, k + 1):
                if (not 0 <= (y1 := y + dy) < n) or (l := abs(dx) + abs(dy)) > k:  # noqa E741
                    continue
                c[shortest - (ai + b[x1 * n + y1] + l)] += 1
    return c


with open("aoc2024/day20input.txt", "rt") as lines:
    lines = "".join(lines)

cheats = count_cheats(grid=lines.replace("\n", ""), n=lines.index("\n"), k=2)
print(sum(n for k, n in cheats.items() if k >= 100))

cheats = count_cheats(grid=lines.replace("\n", ""), n=lines.index("\n"), k=20)
print(sum(n for k, n in cheats.items() if k >= 100))
