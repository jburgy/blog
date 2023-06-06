"""Prepare the Bunnies' Escape

You have maps of parts of the space station, each starting at a prison exit and
ending at the door to an escape pod. The map is represented as a matrix of 0s
and 1s, where 0s are passable space and 1s are impassable walls. The door out
of the prison is at the top left (0,0) and the door into an escape pod is at
the bottom right (w-1,h-1).

Write a function answer(map) that generates the length of the shortest path
from the prison door to the escape pod, where you are allowed to remove one
wall as part of your remodeling plans. The path length is the total number of
nodes you pass through, counting both the entrance and exit nodes. The
starting and ending positions are always passable (0). The map will always be
solvable, though you may or may not need to remove a wall. The height and width
of the map can be from 2 to 20. Moves can only be made in cardinal directions;
no diagonal moves are allowed.

Test cases
Input:

maze = [[0, 1, 1, 0], [0, 0, 0, 1], [1, 1, 0, 0], [1, 1, 1, 0]]
Output:

7
Input:

maze = [
    [0, 0, 0, 0, 0, 0], [1, 1, 1, 1, 1, 0], [0, 0, 0, 0, 0, 0],
    [0, 1, 1, 1, 1, 1], [0, 1, 1, 1, 1, 1], [0, 0, 0, 0, 0, 0]
]
Output:

11
"""

from itertools import product


NEIGHBORS = -1, -1j, 1, 1j


def _get(m, x):
    return m[int(x.real)][int(x.imag)]


def _set(m, x, mx):
    m[int(x.real)][int(x.imag)] = mx


def solution(m):  # noqa: max-complexity: 20
    if not m or not m[0]:
        return 0

    w, h = len(m), len(m[-1])

    def inside(x):
        return 0 <= x.real < w and 0 <= x.imag < h

    def paint(a):
        a[0][0] = -1
        stack = [0j]
        while stack:
            x = stack.pop()
            c = _get(a, x) - 1
            for k in NEIGHBORS:
                y = x + k
                if inside(y) and not _get(a, y):
                    _set(a, y, c)
                    stack.append(y)
        return a[w - 1][h - 1]

    a = paint(m)
    done = a < 0

    b = 0
    for i, mi in enumerate(m):
        for j, mij in enumerate(mi):
            x = complex(i, j)
            if mij < 1:
                continue
            if not done:
                n = [[max(k, 0) for k in n] for n in m]
                _set(n, x, 0)
                c = paint(n)
                if not c:
                    continue

                a = max(a, c) if a else c
                continue
            for k, l in product(NEIGHBORS, NEIGHBORS):
                if k == l:
                    continue
                y = x + k
                if not inside(y):
                    continue
                y = _get(m, y)
                if y > 0:
                    continue
                z = x + l
                if not inside(z):
                    continue
                z = _get(m, z)
                if z > 0:
                    continue
                if done and y < 0 and z < 0:
                    b = max(b, abs(z - y) - 2)
    return -a - b


assert solution([[0, 1, 1, 0], [0, 0, 0, 1], [1, 1, 0, 0], [1, 1, 1, 0]]) == 7
assert (
    solution(
        [
            [0, 0, 0, 0, 0, 0],
            [1, 1, 1, 1, 1, 0],
            [0, 0, 0, 0, 0, 0],
            [0, 1, 1, 1, 1, 1],
            [0, 1, 1, 1, 1, 1],
            [0, 0, 0, 0, 0, 0],
        ]
    )
    == 11
)
