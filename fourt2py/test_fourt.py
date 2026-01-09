import numpy as np

from fourt2py import fourt  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[unresolved-import]


def test_fourt():
    a = np.zeros(15, dtype=complex)
    a[1] = 1
    a[3] = -1

    assert np.allclose(fourt(a), np.conjugate(np.fft.fft(a)))
