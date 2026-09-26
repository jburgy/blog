"""Time smplx_py against the Fortran smplx, and crout1 against np.linalg.inv."""

import argparse
from timeit import repeat

import numpy as np
from simplex import crout1, smplx, smplx_py  # ty: ignore[unresolved-import]
from test_smplx import data, nutrients


def dense_lp(m: int, seed: int = 0):
    rng = np.random.default_rng(seed)
    return (
        rng.uniform(0, 10, (m, 2 * m)),
        rng.uniform(1, 10, m),
        rng.uniform(-1, 5, 2 * m),
    )


def best_ms(f, number: int = 3) -> float:
    return min(repeat(f, number=number, repeat=5)) / number * 1e3


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sizes", nargs="*", type=int, default=[50, 200, 400])
    args = parser.parse_args()

    solvers = {"python": smplx_py}
    if smplx is not smplx_py:
        solvers["fortran"] = smplx
    stigler = (
        np.column_stack([*data.values()]),
        np.r_[*nutrients.values()],
        -np.ones(len(data)),
    )
    problems = {"stigler 9x77": (stigler, {"numge": len(nutrients)})}
    for m in args.sizes:
        problems[f"dense {m}x{2 * m}"] = dense_lp(m), {"numle": m, "mxiter": 100 * m}
    for name, (lp, kw) in problems.items():
        iters = smplx_py(*lp, **kw)[3]
        times = "  ".join(
            f"{s} {best_ms(lambda: f(*lp, **kw)):8.2f} ms" for s, f in solvers.items()
        )
        print(f"{name:16} {iters:4} it  {times}")

    for m in args.sizes:
        a = np.random.default_rng(m).normal(size=(m, m))
        index, scratch = np.empty(m - 1, np.intp), np.empty((m, m))
        t_crout = best_ms(lambda: crout1(a.copy(), 0, index, scratch))
        t_inv = best_ms(lambda: np.linalg.inv(a))
        print(f"crout1 {m}x{m:<8}      crout1 {t_crout:8.2f} ms  inv {t_inv:8.2f} ms")


if __name__ == "__main__":
    main()
