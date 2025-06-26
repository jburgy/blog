# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "numpy",
# ]
# ///

import io
import numpy as np
import numpy.ma as ma
import numpy.typing as npt
from time import perf_counter


def neighbors(i: int, j: int) -> npt.NDArray[np.uint8]:
    """ row, col, and block (`i`, `j`) belongs to *excluding* (`i`, `j`)

    """
    k, l = (i//3)*3, (j//3)*3  # noqa E741
    return np.array([
        np.r_[i:i:8j, 0:i, i + 1:9, np.repeat(np.r_[k:i, i + 1:k + 3], 2)],
        np.r_[0:j, j + 1:9, j:j:8j, np.tile(np.r_[l:j, j + 1:l + 3], 2)],
    ], dtype=np.uint8)


_neighbors = np.array(
    [[neighbors(i, j) for j in range(9)] for i in range(9)]
).transpose(2, 0, 1, 3)


def propagate(possible: npt.NDArray[np.uint8], count: ma.MaskedArray, where: ma.MaskedArray) -> int:
    """ Enforce consistency by removing solved values from neighboring sites.

    Iterate as long as sites accept a single value.  Note that removing solved
    values can reveal infeasibility.  When this happens, `count` has zeros.

    Parameters
    ----------
    possible: boolean ndarray
        possible[i, j, k] indicates whether k+1 is allowed at site (i, j)
    count: int MaskedArray
        number of possible values at site (i, j), masking already propagated
    where: bool MaskedArray
        newly solved sites (count==1 and not masked)

    Returns
    -------
    int
        number of unsolved sites if feasible else -1
    """
    while np.equal(count, 1, out=where).any():
        i, j = _neighbors[:, where, :]
        _, k = possible[where, :].nonzero()
        possible[i, j, k[:, np.newaxis]] = False
        if not possible.sum(axis=2, out=count).all():
            return -1  # site with 0 possibility => infeasibility
        count[where] = ma.masked  # avoid repetitive work
    return count.count()


def solve(given: npt.NDArray[np.uint8]) -> npt.NDArray[np.uint8]:
    """ Solve a sudo puzzle using backtracking

    >>> i = np.loadtxt(io.StringIO('''
    ... 5 3 0 0 7 0 0 0 0
    ... 6 0 0 1 9 5 0 0 0
    ... 0 9 8 0 0 0 0 6 0
    ... 8 0 0 0 6 0 0 0 3
    ... 4 0 0 8 0 3 0 0 1
    ... 7 0 0 0 2 0 0 0 6
    ... 0 6 0 0 0 0 2 8 0
    ... 0 0 0 4 1 9 0 0 5
    ... 0 0 0 0 8 0 0 7 9
    ... '''), dtype=np.uint8)
    >>> solve(i)
    array([[5, 3, 4, 6, 7, 8, 9, 1, 2],
           [6, 7, 2, 1, 9, 5, 3, 4, 8],
           [1, 9, 8, 3, 4, 2, 5, 6, 7],
           [8, 5, 9, 7, 6, 1, 4, 2, 3],
           [4, 2, 6, 8, 5, 3, 7, 9, 1],
           [7, 1, 3, 9, 2, 4, 8, 5, 6],
           [9, 6, 1, 5, 3, 7, 2, 8, 4],
           [2, 8, 7, 4, 1, 9, 6, 3, 5],
           [3, 4, 5, 2, 8, 6, 1, 7, 9]])
    """
    node = np.full((9, 9, 9), True)
    mask = given > 0
    node[mask, :] = False
    node[mask, given[mask] - 1] = True

    # number of possibilities at each site, masking those already propagated
    # to avoid repetitive work.  All masked == problem solved
    count = ma.array(node.sum(axis=2), fill_value=1)

    # allocate upfront to as out parameter to np.equal
    # (ma.array because count is ma.array)
    where = ma.array(np.empty((9, 9), dtype=bool), fill_value=False)

    stack = [(node, count)]
    while stack:
        node, count = stack.pop()
        unsolved = propagate(node, count, where)
        if unsolved == -1:
            continue
        if unsolved == 0:
            break
        # try all possibilities from cell with fewest > 1
        i, j = np.unravel_index(count.argmin(), count.shape)
        for k in np.flatnonzero(node[i, j, :]):
            node_copy, count_copy = node.copy(), count.copy()
            node_copy[i, j, :] = False
            node_copy[i, j, k] = True
            count_copy[i, j] = 1
            stack.append((node_copy, count_copy))

    i, j, k = node.nonzero()
    count[i, j] = k + 1
    return np.array(count)


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
"""), dtype=np.uint8)
#     s = np.loadtxt(io.StringIO("""
# 5 3 0 0 7 0 0 0 0
# 6 0 0 1 9 5 0 0 0
# 0 9 8 0 0 0 0 6 0
# 8 0 0 0 6 0 0 0 3
# 4 0 0 8 0 3 0 0 1
# 7 0 0 0 2 0 0 0 6
# 0 6 0 0 0 0 2 8 0
# 0 0 0 4 1 9 0 0 5
# 0 0 0 0 8 0 0 7 9
# """), dtype=np.uint8)
    t = perf_counter()
    s = solve(s)
    t = perf_counter() - t
    print(s, t)
