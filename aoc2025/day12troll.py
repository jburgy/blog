# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "polyomino",
# ]
# ///
from itertools import chain, repeat
from pathlib import Path

from polyomino import TilingProblem  # pyright: ignore[reportMissingImports]  # ty: ignore[unresolved-import]
from polyomino.constant import MONOMINO  # pyright: ignore[reportMissingImports]  # ty: ignore[unresolved-import]
from polyomino.board import Rectangle  # pyright: ignore[reportMissingImports]  # ty: ignore[unresolved-import]
from polyomino.solution import Solution  # pyright: ignore[reportMissingImports]  # ty: ignore[unresolved-import]
from polyomino.tileset import Tileset  # pyright: ignore[reportMissingImports]  # ty: ignore[unresolved-import]


def cover(line: str, *, tiles: list[list[tuple[int, int]]]) -> Solution | None:
    board, _, presents = line.partition(": ")
    height, _, width = board.partition("x")

    return TilingProblem(
        board=Rectangle(int(height), int(width)),
        tileset=Tileset(
            mandatory=list(
                chain.from_iterable(
                    repeat(tile, int(count))
                    for tile, count in zip(tiles, presents.split())
                )
            ),
            optional=[],
            filler=[MONOMINO],
            reflections=True,
        ),
    ).solve()


lines = Path("aoc2025/day12input.txt").read_text().splitlines()

tiles = [
    [
        (i, j)
        for i, line in enumerate(lines[start + 1 : start + 4])
        for j, c in enumerate(line.rstrip())
        if c == "#"
    ]
    for start in range(0, 30, 5)
]

for line in lines[30:]:
    print(line)
    solution = cover(line, tiles=tiles)
    print(solution.display() if solution else "No solution")
