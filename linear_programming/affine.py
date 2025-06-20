# https://en.wikipedia.org/wiki/Affine_scaling
# this version does not exploit A's sparseness

import numpy as np
from scipy.linalg import solve
from scipy.linalg.blas import dcopy, dgemm, dgemv  # type: ignore[attr-defined]


def affine_scaling(A, b, c, x, eps=1e-8, beta=0.99):
    w = np.empty_like(b)
    r = np.empty_like(c)
    pos = np.empty(len(c), dtype=bool)
    D2 = np.empty((1, len(c)))
    AD2 = np.empty_like(A)
    AD2AT = np.empty((len(b), len(b)), order="F")

    while True:
        np.multiply(x, x, out=D2)
        np.multiply(A, D2, out=AD2)  # AD²ₖ = A · D²ₖ
        dgemv(alpha=1.0, a=AD2, x=c, beta=0.0, y=w, overwrite_y=True)  # w = AD²ₖ · c
        # AD²ₖAᵀ = AD²ₖ · Aᵀ
        dgemm(alpha=1.0, a=AD2, b=A, beta=0.0, c=AD2AT, trans_b=True, overwrite_c=True)
        # w = (AD²ₖAᵀ) \ AD² · c
        solve(a=AD2AT, b=w, overwrite_a=True, overwrite_b=True, assume_a="sym")
        dcopy(x=c, y=r)
        # rᵏ = c - Aᵀwᵏ
        dgemv(alpha=-1.0, a=A, x=w, beta=1.0, y=r, trans=True, overwrite_y=True)
        allpos = np.greater_equal(r, 0.0, pos).all()
        np.multiply(x, r, out=r)
        if allpos and r.sum() < eps:
            break
        r *= beta / r.max(initial=0.0, where=pos)
        np.multiply(r, x, out=r)
        x -= r

    return x


A = np.asfortranarray([[1, -1, 1, 0], [0, 1, 0, 1]], dtype=float)
b = np.asarray([15, 15], dtype=float)
c = np.asarray([-2, 1, 0, 0], dtype=float)
x = np.asarray([10, 2, 7, 13], dtype=float)

print(affine_scaling(A, b, c, x))
