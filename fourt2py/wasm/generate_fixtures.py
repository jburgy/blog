"""Regenerate fourt2py/wasm/fixtures.json from fourt2py.fourt -- the f2py
binding of the actual FOURT.F -- so fourt2py/web/test/fourt.test.mjs has
fixed expected outputs to check fourt2py/wasm/fourt.c (and its wasm build)
against, without needing Python at JS test time.

Run from the repo root with the project's venv active and fourt2py built
(see fourt2py/meson.build / the repo's normal `uv`/meson workflow):

    python fourt2py/wasm/generate_fixtures.py

Note: fourt2py.fourt's f2py wrapper only accepts rank-1 (1-D) arrays, so
these fixtures -- like fourt.c's own validation -- only cover NDIM=1.
"""

import json
from pathlib import Path

import numpy as np

from fourt2py import fourt  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[unresolved-import]

OUT = Path(__file__).with_name("fixtures.json")
TOLERANCE = {"atol": 1e-9, "rtol": 1e-6}

# ICASE=1 (iform=1, fully complex): the only mode fourt2py/web actually calls
# into. Covers a power of two, small primes, and composites of mixed factors.
COMPLEX_LENGTHS = [2, 3, 4, 5, 7, 8, 11, 12, 16]

# ICASE=3 (n odd)/4 (n even) (iform=0, real input): not used by the demo, but
# kept here so a future change to those branches has a regression test too.
REAL_LENGTHS = [5, 6, 8, 9, 10, 12]


def complex_to_pairs(data):
    return [v for z in data for v in (float(z.real), float(z.imag))]


def main():
    rng = np.random.default_rng(0)
    cases = []

    for n in COMPLEX_LENGTHS:
        for isign in (-1, 1):
            data = rng.standard_normal(n) + 1j * rng.standard_normal(n)
            expected = fourt(data.copy(), isign=isign, iform=1)
            cases.append(
                {
                    "n": n,
                    "isign": isign,
                    "iform": 1,
                    "input": complex_to_pairs(data),
                    "expected": complex_to_pairs(expected),
                }
            )

    for n in REAL_LENGTHS:
        for isign in (-1, 1):
            data = rng.standard_normal(n).astype(complex)
            expected = fourt(data.copy(), isign=isign, iform=0)
            cases.append(
                {
                    "n": n,
                    "isign": isign,
                    "iform": 0,
                    "input": complex_to_pairs(data),
                    "expected": complex_to_pairs(expected),
                }
            )

    OUT.write_text(json.dumps({"tolerance": TOLERANCE, "cases": cases}, indent=2) + "\n")
    print(f"wrote {len(cases)} cases to {OUT}")


if __name__ == "__main__":
    main()
