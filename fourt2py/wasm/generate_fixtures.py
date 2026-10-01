"""Regenerate fourt2py/wasm/fixtures.json and fourt2py/wasm/pow2_fixtures.json
from fourt2py.fourt -- the f2py binding of the actual FOURT.F -- so the JS
tests have fixed expected outputs to check against, without needing Python
at JS test time.

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

HERE = Path(__file__).parent
TOLERANCE = {"atol": 1e-9, "rtol": 1e-6}

# ICASE=1 (iform=1, fully complex): the only mode fourt2py/web actually calls
# into. Covers a power of two, small primes, and composites of mixed factors.
COMPLEX_LENGTHS = [2, 3, 4, 5, 7, 8, 11, 12, 16]

# ICASE=3 (n odd)/4 (n even) (iform=0, real input): not used by the demo, but
# kept here so a future change to those branches has a regression test too.
REAL_LENGTHS = [5, 6, 8, 9, 10, 12]

# Powers of two: what fourt2py/web/fourt.pow2.mjs (the NDIM=1,
# power-of-two-only specialization) is validated against.
POW2_LENGTHS = [1, 2, 4, 8, 16, 32, 64, 128, 256]


def complex_to_pairs(data):
    return [v for z in data for v in (float(z.real), float(z.imag))]


def complex_cases(rng, lengths, iform):
    cases = []
    for n in lengths:
        for isign in (-1, 1):
            if iform == 1:
                data = rng.standard_normal(n) + 1j * rng.standard_normal(n)
            else:
                data = rng.standard_normal(n).astype(complex)
            expected = fourt(data.copy(), isign=isign, iform=iform)
            cases.append(
                {
                    "n": n,
                    "isign": isign,
                    "iform": iform,
                    "input": complex_to_pairs(data),
                    "expected": complex_to_pairs(expected),
                }
            )
    return cases


def main():
    rng = np.random.default_rng(0)
    cases = complex_cases(rng, COMPLEX_LENGTHS, iform=1)
    cases += complex_cases(rng, REAL_LENGTHS, iform=0)
    payload = {"tolerance": TOLERANCE, "cases": cases}
    out = HERE / "fixtures.json"
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {len(cases)} cases to {out}")

    rng_pow2 = np.random.default_rng(5)
    pow2_cases = complex_cases(rng_pow2, POW2_LENGTHS, iform=1)
    for case in pow2_cases:
        del case["iform"]  # fourt.pow2.mjs's signature has no iform parameter
    pow2_payload = {"tolerance": TOLERANCE, "cases": pow2_cases}
    pow2_out = HERE / "pow2_fixtures.json"
    pow2_out.write_text(json.dumps(pow2_payload, indent=2) + "\n")
    print(f"wrote {len(pow2_cases)} cases to {pow2_out}")


if __name__ == "__main__":
    main()

