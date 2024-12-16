from collections.abc import Iterable

import numpy as np


def boxes(left: list[int], move: int = 0) -> Iterable[tuple[int, int]]:
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

moves = None
state = []
expanded = []
with open("aoc2024/day15input.txt", "rt") as lines:
    for line in lines:
        line = line.rstrip()
        if not line:
            moves = []
        elif moves is None:
            state.append(list(line))
            expanded.append(
                list(
                    line.replace("#", "##")
                    .replace("O", "[]")
                    .replace(".", "..")
                    .replace("@", "@.")
                )
            )
        else:
            moves.append(line)

state = np.array(state)
(robot,) = np.argwhere(state == "@") @ [100, 1]
for move in map(dirs.__getitem__, "".join(moves)):
    new = robot + move
    temp = state[divmod(new, 100)]
    if temp == "#":
        continue
    elif temp == ".":
        state[divmod(robot, 100)] = "."
        state[divmod(new, 100)] = "@"
    else:
        push = new
        while temp == "O":
            push += move
            temp = state[divmod(push, 100)]
        if temp == "#":
            continue
        state[divmod(robot, 100)] = "."
        state[divmod(new, 100)] = "@"
        state[divmod(push, 100)] = "O"
    robot = new

print(np.sum(np.argwhere(state == "O") @ [100, 1]))

expanded = np.array(expanded)
(robot,) = np.argwhere(expanded == "@") @ [100, 1]
for move in map(dirs.__getitem__, "".join(moves)):
    new = robot + move
    temp = expanded[divmod(new, 100)]
    if temp == "#":
        continue
    elif temp == ".":
        expanded[divmod(robot, 100)] = "."
        expanded[divmod(new, 100)] = "@"
    elif move in (-1, 1):  # horizontal
        push = new
        while temp not in ".#":
            push += move
            temp = expanded[divmod(push, 100)]
        if temp == "#":
            continue
        temp = expanded[divmod(new, 100)]
        push = new
        expanded[divmod(new, 100)] = "@"
        while temp in "[]":
            push += move
            expanded[divmod(push, 100)], temp = temp, expanded[divmod(push, 100)]
        expanded[divmod(robot, 100)] = "."
    else:  # vertical
        push = {new - 1: ".@"} if temp == "]" else {new: "@."}
        copy = np.copy(expanded)
        while any(expanded[x] != "." for x in boxes(push)):
            blocked = any(expanded[x] == "#" for x in boxes(push))
            if blocked:
                break
            push = shift(copy, push, move)
        if blocked:
            continue
        shift(copy, push, move)
        expanded = copy
        expanded[divmod(robot, 100)] = "."
    robot = new

print(np.sum(np.argwhere(expanded == "[") @ [100, 1]))
