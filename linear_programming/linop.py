from bisect import bisect_left
from typing import cast

import numpy as np
from scipy import sparse


def scatter(indices: list[int], m: int, n: int) -> sparse.csr_array:
    """Scatter consecutive indices of x into (larger) result vector y.

    Roughly equivalent to::

        for i, j in enumerate(indices):
            y[j] = x[i]

    >>> scatter([1, 3], m=4, n=2) @ [6, 7]
    array([0., 6., 0., 7.])
    """
    if m < 0:
        m = max(indices) + 1
    if n < 0:
        n = len(indices)
    assert m >= max(indices) + 1
    assert n >= len(indices)
    assert m >= n
    return sparse.csr_array(
        (np.ones(shape=len(indices)), (indices, range(len(indices)))),
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


def matmul(
    a: sparse.csr_array, b: sparse.csc_array | sparse.csr_array
) -> sparse.csr_array:
    r""" Sparse multiplication of CSR with CSC or CSR.

    >>> sparse.csr_array([[11., 12.], [21., 22.]])  # doctest: +NORMALIZE_WHITESPACE
    <Compressed Sparse Row sparse array of dtype 'float64'
        with 4 stored elements and shape (2, 2)>
    >>> _ @ sparse.csr_array([[1., 0.], [0., 10.]])  # doctest: +NORMALIZE_WHITESPACE
    <Compressed Sparse Row sparse array of dtype 'float64'
        with 4 stored elements and shape (2, 2)>
    >>> _.todense()
    array([[ 11., 120.],
           [ 21., 220.]])
    """
    assert isinstance(a, sparse.csr_array)
    if isinstance(b, sparse.csr_array):
        return a @ b  # type: ignore

    assert isinstance(b, sparse.csc_array)

    n, k = cast(tuple[int, int], a.shape)
    l, m = b.shape  # noqa: E741
    assert k == l

    indptr = np.copy(a.indptr)
    indices: list[int] = []
    data: list[float] = []

    colbeg = indptr[0]
    for row in range(m):
        colend = indptr[row + 1]
        rowbeg = b.indptr[0]
        for col in range(n):
            rowend = b.indptr[col + 1]
            x = 0.0
            for i in range(colbeg, colend):
                k = a.indices[i]
                rowbeg = bisect_left(b.indices, k, lo=rowbeg, hi=rowend)
                if rowbeg == rowend:
                    break
                if k < b.indices[rowbeg]:
                    continue
                x += a.data[i] * b.data[rowbeg]
                rowbeg += 1
            else:
                rowbeg = rowend
            if np.isclose(x, 0.0):
                continue
            indices.append(col)
            data.append(x)
        indptr[row + 1] = len(indices)
        colbeg = colend
    return sparse.csr_array((data, indices, indptr), shape=(m, n))
