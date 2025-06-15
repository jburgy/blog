from collections.abc import Iterable
from typing import cast

import numpy as np


def boxes(left: Iterable[int], move: int = 0) -> Iterable[tuple[int, int]]:
    for x in left:
        i, j = divmod(x + move, 100)
        yield i, j
        yield i, j + 1


def shift(a: np.ndarray, b: dict[int, str], move: int) -> dict[int, str]:
    c = {}
    for x, y in b.items():
        i, j = divmod(x, 100)
        x1 = x + move
        if a[i, j] == "[":
            c[x1] = "[]"
        elif a[i, j] == "]":
            c[x1 - 1] = "[]"
            if x - 2 not in b:
                a[i, j - 1] = "."
        if a[i, j + 1] == "[":
            c[x1 + 1] = "[]"
            if x + 2 not in b:
                a[i, j + 2] = "."
        a[i, j: j + 2] = tuple(y)
    return c


dirs = {"<": -1, ">": 1, "^": -100, "v": 100}

moves: list[str] | None = None
statearg: list[list[str]] = []
expandedarg: list[list[str]] = []
with open("aoc2024/day15input.txt", "rt") as lines:
    for line in lines:
        line = line.rstrip()
        if not line:
            moves = []
        elif moves is None:
            statearg.append(list(line))
            expandedarg.append(
                list(
                    line.replace("#", "##")
                    .replace("O", "[]")
                    .replace(".", "..")
                    .replace("@", "@.")
                )
            )
        else:
            moves.append(line)

assert moves is not None

state = np.array(statearg)
(robot,) = np.argwhere(state == "@") @ [100, 1]
for move in map(dirs.__getitem__, "".join(moves)):
    new = robot + move
    temp = state[cast(tuple[int, int], divmod(new, 100))]
    if temp == "#":
        continue
    elif temp == ".":
        state[cast(tuple[int, int], divmod(robot, 100))] = "."
        state[cast(tuple[int, int], divmod(new, 100))] = "@"
    else:
        push = new
        while temp == "O":
            push += move
            temp = state[cast(tuple[int, int], divmod(push, 100))]
        if temp == "#":
            continue
        state[cast(tuple[int, int], divmod(robot, 100))] = "."
        state[cast(tuple[int, int], divmod(new, 100))] = "@"
        state[cast(tuple[int, int], divmod(push, 100))] = "O"
    robot = new

print(np.sum(np.argwhere(state == "O") @ [100, 1]))

expanded = np.array(expandedarg)
(robot,) = np.argwhere(expanded == "@") @ [100, 1]
for move in map(dirs.__getitem__, "".join(moves)):
    new = robot + move
    temp = expanded[cast(tuple[int, int], divmod(new, 100))]
    if temp == "#":
        continue
    elif temp == ".":
        expanded[cast(tuple[int, int], divmod(robot, 100))] = "."
        expanded[cast(tuple[int, int], divmod(new, 100))] = "@"
    elif move in (-1, 1):  # horizontal
        push = new
        while temp not in ".#":
            push += move
            temp = expanded[cast(tuple[int, int], divmod(push, 100))]
        if temp == "#":
            continue
        temp = expanded[cast(tuple[int, int], divmod(new, 100))]
        push = new
        expanded[cast(tuple[int, int], divmod(new, 100))] = "@"
        while temp in "[]":
            push += move
            expanded[cast(tuple[int, int], divmod(push, 100))], temp = temp, expanded[cast(tuple[int, int], divmod(push, 100))]
        expanded[cast(tuple[int, int], divmod(robot, 100))] = "."
    else:  # vertical
        pushd = {int(new - 1): ".@"} if temp == "]" else {int(new): "@."}
        copy = np.copy(expanded)
        blocked = False
        while any(expanded[x] != "." for x in boxes(pushd.keys())):
            blocked = any(expanded[x] == "#" for x in boxes(pushd.keys()))
            if blocked:
                break
            pushd = shift(copy, pushd, move)
        if blocked:
            continue
        shift(copy, pushd, move)
        expanded = copy
        expanded[cast(tuple[int, int], divmod(robot, 100))] = "."
    robot = new

print(np.sum(np.argwhere(expanded == "[") @ [100, 1]))
