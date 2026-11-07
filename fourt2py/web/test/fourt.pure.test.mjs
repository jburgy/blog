// Validates fourt2py/web/fourt.pure.mjs (a hand-written, asm.js-flavored
// pure-JS transliteration of fourt2py/wasm/fourt.c) against the same
// fixtures used for the C/wasm build (see fourt2py/wasm/fixtures.json and
// fourt2py/wasm/generate_fixtures.py), captured from the authoritative
// fourt2py.fourt f2py/Fortran binding. No wasm build needed here -- this is
// plain JS, so it's fast to run and doesn't need wasi-sdk.
import { readFile } from 'node:fs/promises';
import { describe, expect, test } from 'vitest';
import { fourt } from '../fourt.pure.mjs';

const fixtures = JSON.parse(await readFile(new URL('../../wasm/fixtures.json', import.meta.url), 'utf8'));

describe('fourt (pure-JS, asm.js-flavored port of fourt2py/wasm/fourt.c)', () => {
    test.each(fixtures.cases)('n=$n isign=$isign iform=$iform matches the Fortran oracle', (fixture) => {
        const data = Float64Array.from(fixture.input);
        const work = new Float64Array(2 * fixture.n + 16);
        const nn = new Int32Array([fixture.n]);
        fourt(data, nn, 1, fixture.isign, fixture.iform, work);
        for (let i = 0; i < data.length; i++) {
            const tolerance = fixtures.tolerance.atol + fixtures.tolerance.rtol * Math.abs(fixture.expected[i]);
            expect(Math.abs(data[i] - fixture.expected[i])).toBeLessThanOrEqual(tolerance);
        }
    });

    // The fixtures are all 1-D. With ndim > 1 and iform=0 the real input (imag
    // ignored) must give the same full complex output as iform=1 with imag=0.
    const multiDim = [[4, 3], [3, 4], [6, 5], [8, 6], [4, 4, 3], [2, 3, 4], [6, 8, 3], [4, 2, 2, 3], [1, 4], [4, 1]];
    const transform = (dims, isign, iform, data) => {
        const work = new Float64Array(2 * Math.max(...dims) + 16);
        fourt(data, Int32Array.from(dims), dims.length, isign, iform, work);
        return data;
    };

    describe.each(multiDim)('%j', (...dims) => {
        test.each([-1, 1])('real (iform=0) matches complex (iform=1) for isign=%i', (isign) => {
            const input = new Float64Array(2 * dims.reduce((a, b) => a * b));
            for (let i = 0; i < input.length; i += 2) input[i] = Math.sin(i * 1.3 + 1) + (i % 3);
            const real = transform(dims, isign, 0, Float64Array.from(input));
            const complex = transform(dims, isign, 1, Float64Array.from(input));
            for (let i = 0; i < real.length; i++) expect(real[i]).toBeCloseTo(complex[i], 10);
        });
    });

    test('2-D complex transform matches a naive DFT', () => {
        const [n0, n1] = [3, 4];
        const input = Float64Array.from({ length: 2 * n0 * n1 }, (_, i) => Math.cos(i * 0.7) + i / 10);
        const out = transform([n0, n1], 1, 1, Float64Array.from(input));
        for (let k1 = 0; k1 < n1; k1++) {
            for (let k0 = 0; k0 < n0; k0++) {
                let re = 0, im = 0;
                for (let j1 = 0; j1 < n1; j1++) {
                    for (let j0 = 0; j0 < n0; j0++) {
                        const a = 2 * Math.PI * (k0 * j0 / n0 + k1 * j1 / n1);
                        const idx = 2 * (j0 + n0 * j1);
                        re += input[idx] * Math.cos(a) - input[idx + 1] * Math.sin(a);
                        im += input[idx] * Math.sin(a) + input[idx + 1] * Math.cos(a);
                    }
                }
                const idx = 2 * (k0 + n0 * k1);
                expect(out[idx]).toBeCloseTo(re, 10);
                expect(out[idx + 1]).toBeCloseTo(im, 10);
            }
        }
    });

    test.each([
        ['ndim < 1', [3], 0],
        ['a non-positive dimension', [0], 1],
    ])('%s leaves data untouched', (_, dims, ndim) => {
        const data = Float64Array.from([1, 2, 3, 4]);
        fourt(data, Int32Array.from(dims), ndim, -1, 1, new Float64Array(16));
        expect([...data]).toEqual([1, 2, 3, 4]);
    });
});
