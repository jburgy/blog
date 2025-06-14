# -*- coding: utf8; -*-
import io
import numpy as np
import numpy.ma as ma
import numpy.typing as npt
from time import perf_counter


def bitcount(x):
    x -= (x >> 1) & 0x155
    x = (x & 0x133) + ((x >> 2) & 0x33)
    x = (x + (x >> 4)) & 0x10F
    return (x + (x >> 8)) & 0xF


def neighbors(i: int, j: int) -> npt.NDArray[np.intp]:
    k, l = (i//3)*3, (j//3)*3  # noqa E741
    return np.array([
        np.r_[i:i:8j, 0:i, i + 1:9, np.repeat(np.r_[k:i, i + 1:k + 3], 2)],  # type: ignore
        np.r_[0:j, j + 1:9, j:j:8j, np.tile(np.r_[l:j, j + 1:l + 3], 2)],  # type: ignore
    ], dtype=np.intp)


_counts = bitcount(np.arange(1 << 9, dtype=np.uint16)).astype(np.uint8)
_neighbors = np.array(
    [[neighbors(i, j) for j in range(9)] for i in range(9)]
).transpose(2, 0, 1, 3)


def propagate(possible: npt.NDArray[np.intp], count: ma.MaskedArray, where=ma.MaskedArray) -> int:
    while np.equal(count, 1, out=where).any():
        k = np.invert(possible[where])
        # ufunc.at performs *unbuffered* in place operation
        np.bitwise_and.at(possible, tuple(_neighbors[:, where, :]),
                          k[:, np.newaxis])
        if not _counts.take(possible, out=count).all():  # stay in sync
            return -1
        count[where] = ma.masked  # no need to visit again
    return count.count()


def solve(given):
    possible = np.full((9, 9), 0b111111111, dtype=np.uint16)
    mask = given > 0
    possible[mask] = 1 << (given[mask] - 1)

    # number of possibilities at each site, masking those already propagated
    # to avoid repetitive work.  All masked == problem solved!
    count = ma.array(_counts.take(possible))

    # allocate upfront to pass as out parameter to np.equal
    # (ma.array because count is ma.array)
    where = ma.array(np.empty((9, 9), dtype=bool), fill_value=False)

    stack = [(possible, count)]
    while stack:
        node, count = stack.pop()
        unsolved = propagate(node, count, where)
        if unsolved == -1:  # dead end
            continue
        if unsolved == 0:  # all solved!
            break
        # Try all possibilities from cell with fewest > 1
        i, j = np.unravel_index(count.argmin(), count.shape)
        k = node[i, j]
        while k:
            l = k & (k - 1)  # noqa E741
            node_copy, count_copy = node.copy(), count.copy()
            node_copy[i, j], count_copy[i, j], k = k - l, 1, l
            stack.append((node_copy, count_copy))

    return np.log2(node).astype(np.uint8) + 1


if __name__ == "__main__":
    s = np.loadtxt(io.StringIO("""
8 0 0 0 0 0 0 0 0
0 0 3 6 0 0 0 0 0
0 7 0 0 9 0 2 0 0
0 5 0 0 0 7 0 0 0
0 0 0 0 4 5 7 0 0
0 0 0 1 0 0 0 3 0
0 0 1 0 0 0 0 6 8
0 0 8 5 0 0 0 1 0
0 9 0 0 0 0 4 0 0
"""), dtype=np.uint16)
    s = np.loadtxt(io.StringIO("""
5 3 0 0 7 0 0 0 0
6 0 0 1 9 5 0 0 0
0 9 8 0 0 0 0 6 0
8 0 0 0 6 0 0 0 3
4 0 0 8 0 3 0 0 1
7 0 0 0 2 0 0 0 6
0 6 0 0 0 0 2 8 0
0 0 0 4 1 9 0 0 5
0 0 0 0 8 0 0 7 9
"""), dtype=np.uint16)
    t = perf_counter()
    s = solve(s)
    t = perf_counter() - t
    print(s, t)
