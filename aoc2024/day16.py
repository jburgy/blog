from heapq import heappop, heappush
from typing import NamedTuple


class Reindeer(NamedTuple):
    score: int
    x: complex
    v: complex

    def __lt__(self, other: "Reindeer") -> bool:
        return self.score < other.score


with open("aoc2024/day16input.txt", "rt") as lines:
    lines = [line.rstrip() for line in lines]

goal = complex(1, len(lines[0]) - 2)
scores = {}

q = [Reindeer(score=0, x=complex(len(lines) - 2, 1), v=1j)]
while q:
    reindeer: Reindeer = heappop(q)
    x = reindeer.x
    i = int(x.real)
    j = int(x.imag)
    if lines[i][j] == "#":
        continue
    v = reindeer.v
    s = reindeer.score
    score = scores.get((x, v))
    if score is not None and score < s:
        continue
    scores[x, v] = reindeer.score
    if x == goal:
        continue
    for turn in [1, 1j, -1j]:
        v = reindeer.v * turn
        new = Reindeer(
            score=reindeer.score + (1001 if isinstance(turn, complex) else 1),
            x=x + v,
            v=v,
        )
        heappush(q, new)

shortest = min(scores[goal, z] for z in [-1, 1j])

q = [(Reindeer(score=0, x=complex(len(lines) - 2, 1), v=1j),)]
paths = set()
while q:
    p = q.pop()
    reindeer = p[-1]
    x = reindeer.x
    i = int(x.real)
    j = int(x.imag)
    if lines[i][j] == "#":
        continue
    v = reindeer.v
    score = scores.get((x, v))
    if score is None or score < reindeer.score:
        continue
    if x == goal:
        if reindeer.score == shortest:
            paths.add(p)
        continue
    for turn in [1, 1j, -1j]:
        v = reindeer.v * turn
        new = Reindeer(
            score=reindeer.score + (1001 if isinstance(turn, complex) else 1),
            x=x + v,
            v=v,
        )
        q.append(p + (new,))

lines = list(map(list, lines))

tiles = set()
for path in paths:
    for reindeer in path:
        x = reindeer.x
        tiles.add(x)
        lines[int(x.real)][int(x.imag)] = "O"

for line in lines:
    print(*line, sep="")

print(len(tiles))
