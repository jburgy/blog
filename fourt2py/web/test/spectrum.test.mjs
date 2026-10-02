import { describe, expect, test } from 'vitest';
import { N, HARMONICS, DEFAULT_AMPLITUDES, buildSpectrum, peakAbs, normalizedWaveform } from '../spectrum.mjs';

describe('buildSpectrum', () => {
    test('splits a real knot across bin k and its conjugate N-k', () => {
        const data = buildSpectrum([1], [5], 32);
        expect(data[2 * 5]).toBeCloseTo(0.5);
        expect(data[2 * 5 + 1]).toBeCloseTo(0);
        expect(data[2 * (32 - 5)]).toBeCloseTo(0.5);
        expect(data[2 * (32 - 5) + 1]).toBeCloseTo(0);
    });

    test('a Nyquist knot (n even, k = n/2) is not split', () => {
        const data = buildSpectrum([1], [16], 32);
        expect(data[2 * 16]).toBeCloseTo(1);
    });

    test('rejects mismatched amplitude/harmonic lengths', () => {
        expect(() => buildSpectrum([1, 2], [1], 32)).toThrow();
    });

    test('rejects harmonics outside [1, n-1]', () => {
        expect(() => buildSpectrum([1], [32], 32)).toThrow();
        expect(() => buildSpectrum([1], [0], 32)).toThrow();
    });

    test('the default preset uses every predefined harmonic', () => {
        const data = buildSpectrum(DEFAULT_AMPLITUDES, HARMONICS, N);
        for (const k of HARMONICS) {
            expect(data[2 * k]).not.toBe(0);
        }
    });

    test('a single real-valued cosine knot sums to the expected time-domain cosine', () => {
        // X[k]=X[n-k]=a/2 => IDFT (unnormalized, ISIGN=+1 convention) sum over just
        // those two bins is a*cos(2*pi*k*t/n): verify that directly, independent of FOURT.
        const n = 16;
        const k = 3;
        const a = 0.7;
        const data = buildSpectrum([a], [k], n);
        for (let t = 0; t < n; t++) {
            let re = 0;
            for (let bin = 0; bin < n; bin++) {
                const theta = (2 * Math.PI * bin * t) / n;
                re += data[2 * bin] * Math.cos(theta) - data[2 * bin + 1] * Math.sin(theta);
            }
            expect(re).toBeCloseTo(a * Math.cos((2 * Math.PI * k * t) / n), 10);
        }
    });
});

describe('peakAbs / normalizedWaveform', () => {
    test('peakAbs returns 1 for an all-zero signal (avoids a divide by zero)', () => {
        expect(peakAbs(new Float64Array(8))).toBe(1);
    });

    test('normalizedWaveform scales the real parts so the loudest sample is +-1', () => {
        const data = new Float64Array([2, 0, -4, 0, 1, 0]);
        const real = normalizedWaveform(data);
        expect(Math.max(...Array.from(real, Math.abs))).toBeCloseTo(1);
        expect(real[1]).toBeCloseTo(-1);
    });
});
