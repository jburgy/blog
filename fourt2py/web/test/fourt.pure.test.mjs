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
});
