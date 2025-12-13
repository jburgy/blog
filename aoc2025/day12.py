from pathlib import Path

lines = Path("aoc2025/day12input.txt").read_text().splitlines()
tiles = ["".join(lines[start + 1 : start + 4]).count("#") for start in range(0, 30, 5)]

count = 0
for line in lines[30:]:
    board, _, presents = line.rstrip().partition(": ")
    height, _, width = board.partition("x")
    count += sum(
        tile * int(present) for tile, present in zip(tiles, presents.split())
    ) < int(height) * int(width)
print(count)
