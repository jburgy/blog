from bisect import bisect_left
from collections import deque

PART1_BYTES = 1024
SIZE = 71

type Cell = tuple[int, int]


def steps_to_exit(corrupted: set[Cell]) -> int | None:
    """Fewest steps from (0, 0) to the far corner, or None once it is walled off."""
    goal = (SIZE - 1, SIZE - 1)
    seen = {(0, 0)}
    q = deque([((0, 0), 0)])
    while q:  # FIFO + dedup at push time, so the first pop of `goal` is optimal
        (x, y), steps = q.popleft()
        if (x, y) == goal:
            return steps
        for cell in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            i, j = cell
            if not (0 <= i < SIZE and 0 <= j < SIZE):
                continue
            if cell in corrupted or cell in seen:
                continue
            seen.add(cell)
            q.append((cell, steps + 1))
    return None


with open("aoc2024/day18input.txt", "rt") as io:
    falling = [(int(x), int(y)) for x, y in (line.split(",") for line in io)]

print(steps_to_exit(set(falling[:PART1_BYTES])))

# "the exit is sealed" is monotone in the number of fallen bytes, so bisect instead
# of scanning; `is None` puts False before True as bisect requires.
sealed = bisect_left(
    range(len(falling) + 1),
    True,
    lo=PART1_BYTES,
    key=lambda k: steps_to_exit(set(falling[:k])) is None,
)
print("{},{}".format(*falling[sealed - 1]))
