"""Cross-validate linprog's canonical_maximization/affine_scaling against simplex.

Both linprog examples (the Wikipedia farmer LP in linear.py and the Wikipedia
affine-scaling example in affine.py) are solved three ways: scipy's HiGHS-backed
linprog, simplex's smplx (wrapped FORTRAN and/or its numpy port), and linprog's
own standalone affine_scaling. All must agree on the optimal value.
"""

import sys
from pathlib import Path

import numpy as np
import pytest
from scipy import optimize

from linprog import affine, linear

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "simplex"))
from simplex import smplx, smplx_py  # noqa: E402  ty: ignore[unresolved-import]

SOLVERS = [smplx_py] + ([smplx] if smplx is not smplx_py else [])


@pytest.mark.parametrize("solve", SOLVERS)
def test_canonical_maximization(solve):
    """linear.py's farmer LP: scipy and smplx (which maximizes -c) must agree."""
    a = linear.A.toarray()
    ref = optimize.linprog(c=linear.c, A_eq=a, b_eq=linear.b)
    assert ref.status == 0

    ind, x, z, _ = solve(a, linear.b, -linear.c, numle=0)
    assert ind == 0
    assert z == pytest.approx(-ref.fun)
    np.testing.assert_allclose(x, ref.x, atol=1e-6)


@pytest.mark.parametrize("solve", SOLVERS)
def test_affine_scaling(solve):
    """affine.py's example: scipy, smplx and affine_scaling all agree on the optimum."""
    ref = optimize.linprog(c=affine.c, A_eq=affine.A, b_eq=affine.b)
    assert ref.status == 0

    ind, _, z, _ = solve(affine.A, affine.b, -affine.c, numle=0)
    assert ind == 0
    assert z == pytest.approx(-ref.fun)

    x = affine.affine_scaling(affine.A, affine.b, affine.c, affine.x.copy())
    assert x @ affine.c == pytest.approx(ref.fun, abs=1e-2)
