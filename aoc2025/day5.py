from pathlib import Path

lines = Path("aoc2025/day5input.txt").read_text().splitlines()

blank = next(i for i, line in enumerate(lines) if not line)
ranges = [tuple(map(int, line.split("-"))) for line in lines[:blank]]
ids = set(map(int, lines[blank + 1:]))

# Count available fresh IDs
fresh = set()
for a, b in ranges:
    for id in ids:
        if a <= id <= b:
            fresh.add(id)
    ids = ids - fresh
print(len(fresh))

# Count possible fresh IDs
ranges.sort()
merged = [ranges[0]]
for a, b in ranges[1:]:
    if merged[-1][1] < a:
        merged.append((a, b))
    else:
        merged[-1] = (merged[-1][0], max(merged[-1][1], b))
print(sum(b - a + 1 for a, b in merged))
