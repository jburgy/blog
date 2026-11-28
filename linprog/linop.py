# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "scipy",
# ]
# ///

import numpy as np
from scipy import sparse


def scatter(indices: list[int], m: int = -1, n: int = -1) -> sparse.csr_array:
    """Scatter consecutive indices of x into (larger) result vector y.

    Roughly equivalent to::

        for i, j in enumerate(indices):
            y[j] = x[i]

    >>> scatter([1, 3]) @ [6, 7]
    array([0., 6., 0., 7.])
    """
    if m < 0:
        m = max(indices) + 1
    if n < 0:
        n = len(indices)
    assert m >= max(indices) + 1
    assert n >= len(indices)
    assert m >= n
    return sparse.csr_array(  # pyright: ignore[reportCallIssue]
        (np.ones(shape=len(indices)), (indices, range(len(indices)))),  # pyright: ignore[reportArgumentType]
        shape=(m, n),
    )


def gather(indices: list[int], n: int = -1) -> sparse.csr_array:
    """Gather subset of x into (smaller) consecutive result vector y.

    Roughly equivalent to::

        for i, j in enumerate(indices):
            y[i] = y[j]

    >>> gather([1, 3]) @ [4, 5, 6, 7]
    array([5., 7.])
    """
    m = len(indices)
    if n < 0:
        n = max(indices) + 1
    assert n >= max(indices) + 1
    assert m <= n
    return sparse.csr_array(
        (np.ones(shape=len(indices)), indices, range(len(indices) + 1)),
        shape=(m, n),
    )


def sumby(by: list[tuple[int, ...]]):
    """Compute partial sums defined by unique tuples.

    Roughly equivalent to::

        sums = defaultdict(float)
        for i, key in enumerate(by):
            sums[key] += x[i]

    >>> sumby([(0, 0), (0, 1), (1, 0), (1, 0), (1, 1), (1, 1)]) @ range(6)
    array([0., 1., 5., 9.])
    """
    keys, inverse = np.unique(by, axis=0, return_inverse=True)
    return sparse.csr_array(
        (np.ones(shape=len(by)), (inverse, np.arange(len(by), dtype=int))),
        shape=(len(keys), len(by)),
    )
