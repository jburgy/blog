// Validates fourt2py/web/fourt.pow2.mjs (the NDIM=1, power-of-two-only
// specialization of fourt.pure.mjs) two ways: against
// fourt2py/wasm/pow2_fixtures.json (captured from the authoritative
// fourt2py.fourt f2py/Fortran binding, see
// fourt2py/wasm/generate_fixtures.py), and directly against the general
// fourt.pure.mjs it was derived from, across a denser sweep of lengths.
import { readFile } from 'node:fs/promises';
import { describe, expect, test } from 'vitest';
import { fourt as fourtPow2 } from '../fourt.pow2.mjs';
import { fourt as fourtGeneral } from '../fourt.pure.mjs';

const fixtures = JSON.parse(await readFile(new URL('../../wasm/pow2_fixtures.json', import.meta.url), 'utf8'));

describe('fourt (NDIM=1, power-of-two specialization of fourt.pure.mjs)', () => {
    test.each(fixtures.cases)('n=$n isign=$isign matches the Fortran oracle', (fixture) => {
        const data = Float64Array.from(fixture.input);
        fourtPow2(data, fixture.n, fixture.isign);
        for (let i = 0; i < data.length; i++) {
            const tolerance = fixtures.tolerance.atol + fixtures.tolerance.rtol * Math.abs(fixture.expected[i]);
            expect(Math.abs(data[i] - fixture.expected[i])).toBeLessThanOrEqual(tolerance);
        }
    });

    const lengths = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024];
    test.each(lengths)('n=%i agrees with the general fourt.pure.mjs for both signs', (n) => {
        for (const isign of [-1, 1]) {
            const seed = Float64Array.from({ length: 2 * n }, (_, i) => Math.sin(i + n));
            const got = seed.slice();
            fourtPow2(got, n, isign);

            const want = seed.slice();
            fourtGeneral(want, new Int32Array([n]), 1, isign, 1, new Float64Array(2 * n + 16));

            for (let i = 0; i < want.length; i++) {
                expect(got[i]).toBeCloseTo(want[i], 9);
            }
        }
    });
});
