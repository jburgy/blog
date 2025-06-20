"""
From the scans of the nebula, you have found that it is very flat and
distributed in distinct patches, so you can model it as a 2D grid. You find
that the current existence of gas in a cell of the grid is determined exactly
by its 4 nearby cells, specifically, (1) that cell, (2) the cell below it, (3)
the cell to the right of it, and (4) the cell below and to the right of it. If,
in the current state, exactly 1 of those 4 cells in the 2x2 block has gas, then
it will also have gas in the next state. Otherwise, the cell will be empty in
the next state.

For example, let's say the previous state of the grid (p) was:

.O..
..O.
...O
O...

To see how this grid will change to become the current grid (c) over the next
time step, consider the 2x2 blocks of cells around each cell. Of the 2x2 block
of [p[0][0], p[0][1], p[1][0], p[1][1]], only p[0][1] has gas in it, which
means this 2x2 block would become cell c[0][0] with gas in the next time step:

.O -> O
..

Likewise, in the next 2x2 block to the right consisting of [p[0][1], p[0][2],
p[1][1], p[1][2]], two of the containing cells have gas, so in the next state
of the grid, c[0][1] will NOT have gas:

O. -> .
.O

Following this pattern to its conclusion, from the previous state p, the
current state of the grid c will be:

O.O
.O.
O.O

Note that the resulting output will have 1 fewer row and column, since the
bottom and rightmost cells do not have a cell below and to the right of them,
respectively.

Write a function answer(g) where g is an array of array of bools saying whether
there is gas in each cell (the current scan of the nebula), and return an int
with the number of possible previous states that could have resulted in that
grid after 1 time step. For instance, if the function were given the current
state c above, it would deduce that the possible previous states were p (given
above) as well as its horizontal and vertical reflections, and would return 4.
The width of the grid will be between 3 and 50 inclusive, and the height of the
grid will be between 3 and 9 inclusive. The answer will always be less than one
billion (10^9).

Inputs:
(boolean) g = [
                [true, false, true],
                [false, true, false],
                [true, false, true]
              ]
Output:
(int) 4

Inputs:
(boolean) g = [
                [true, false, true, false, false, true, true, true],
                [true, false, true, false, false, false, true, false],
                [true, true, true, false, false, false, true, false],
                [true, false, true, false, false, false, true, false],
                [true, false, true, false, false, true, true, true]
              ]
Output:
(int) 254

Inputs:
(boolean) g = [
                [true, true, false, true, false, true, false, true, true, false],
                [true, true, false, false, false, false, true, true, true, false],
                [true, true, false, false, false, false, false, false, false, true],
                [false, true, false, false, false, false, true, true, false, false]
              ]
Output:
(int) 11567
"""

from collections import defaultdict
from functools import reduce


def evolve(a, b):
    c = a >> 1
    d = b >> 1
    return (
        (a & ~b & ~c & ~d)
        | (~a & b & ~c & ~d)
        | (~a & ~b & c & ~d)
        | (~a & ~b & ~c & d)
    )


def col_preimages(nrows):
    m = 1 << (nrows + 1)
    p = [defaultdict(set) for _ in range(m >> 1)]
    q = len(p) - 1

    for i in range(m):
        for j in range(m):
            k = evolve(i, j) & q
            p[k][i].add(j)
    return p


def solution(rows):
    nrows = len(rows)
    cp = col_preimages(nrows)
    states = range(1 << (nrows + 1))

    previous = dict.fromkeys(states, 1)
    for col in zip(*rows):
        key = reduce(lambda a, b: a << 1 | b, col)
        p = cp[key]
        # Sorta CSR matrix multiplication
        current = dict.fromkeys(states, 0)
        for state, count in previous.items():
            for q in p[state]:
                current[q] += count
        previous = current

    return sum(previous.values())


p = [
    [False, True, False, False],
    [False, False, True, False],
    [False, False, False, True],
    [True, False, False, False],
]

c = [
    [True, True, False, True, False, True, False, True, True, False],
    [True, True, False, False, False, False, True, True, True, False],
    [True, True, False, False, False, False, False, False, False, True],
    [False, True, False, False, False, False, True, True, False, False],
]
assert solution(c) == 11567

c = [
    [True, False, True, False, False, True, True, True],
    [True, False, True, False, False, False, True, False],
    [True, True, True, False, False, False, True, False],
    [True, False, True, False, False, False, True, False],
    [True, False, True, False, False, True, True, True],
]
assert solution(c) == 254

c = [
    [True, False, True],
    [False, True, False],
    [True, False, True],
]
assert solution(c) == 4
