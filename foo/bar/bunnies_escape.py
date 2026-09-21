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

from collections import deque


NEIGHBORS = -1, -1j, 1, 1j


def _get(m, x):
    return m[int(x.real)][int(x.imag)]


def solution(m):
    if not m or not m[0]:
        return 0

    w, h = len(m), len(m[0])
    goal = complex(w - 1, h - 1)

    def inside(x):
        return 0 <= x.real < w and 0 <= x.imag < h

    # State is (position, walls removed so far): the same cell is worth revisiting
    # with a wall still in hand. FIFO, so the first arrival at the goal is shortest.
    start = 0j, 0
    seen = {start}
    queue = deque([(start, 1)])
    while queue:
        (x, spent), length = queue.popleft()
        if x == goal:
            return length
        for k in NEIGHBORS:
            y = x + k
            if not inside(y):
                continue
            state = y, spent + _get(m, y)
            if state[1] < 2 and state not in seen:
                seen.add(state)
                queue.append((state, length + 1))
    return 0


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
