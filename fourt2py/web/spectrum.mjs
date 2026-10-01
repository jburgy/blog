// Turns the knots the user drags on the frequency-domain chart into the
// interleaved complex buffer FOURT.F expects, and back into a time-domain
// waveform once FOURT has transformed it.
//
// The knots are a fixed set of harmonics of a fundamental frequency; only
// their amplitude (Y) moves. To make a knot's amplitude map directly onto
// the peak contribution it makes in the time domain (no mental conversion
// factor for the reader), a real knot of amplitude `a` at harmonic `k` is
// split across the two conjugate bins k and N-k as `a/2` each:
//
//   X[k] = X[N-k] = a/2   =>   X[k]*e^{i theta} + X[N-k]*e^{-i theta} = a*cos(theta)
//
// FOURT's ISIGN=+1 convention computes exactly that (unnormalized) sum, so
// calling it on this spectrum yields a real time-domain signal whose
// harmonic content is literally what the chart shows.

/** Sample count per period. 200 = 2^3*5^2: deliberately not a power of two, to
 * exercise FOURT's general mixed-radix path rather than only the radix-2 one. */
export const N = 200;

/** Predefined knot frequencies, as harmonics 1..10 of the fundamental. */
export const HARMONICS = Array.from({ length: 10 }, (_, i) => i + 1);

/** A plucked-string-ish default: falling amplitude, odd harmonics emphasized. */
export const DEFAULT_AMPLITUDES = HARMONICS.map((k) => (k % 2 ? 1 / k : 0.2 / k));

/**
 * Build the interleaved [re0, im0, re1, im1, ...] buffer of length 2*n FOURT
 * expects, from an amplitude per entry in `harmonics`.
 *
 * @param {number[]} amplitudes one amplitude per entry of `harmonics`, each in [-1, 1]
 * @param {number[]} harmonics harmonic numbers, each in [1, n/2]
 * @param {number} n total sample count (spectrum length)
 * @returns {Float64Array} length 2*n
 */
export function buildSpectrum(amplitudes, harmonics = HARMONICS, n = N) {
    if (amplitudes.length !== harmonics.length) {
        throw new Error('amplitudes and harmonics must have the same length');
    }
    const data = new Float64Array(2 * n);
    const nyquist = n % 2 === 0 ? n / 2 : -1;
    for (let i = 0; i < harmonics.length; i++) {
        const k = harmonics[i];
        const a = amplitudes[i];
        if (k <= 0 || k >= n) throw new Error(`harmonic ${k} is out of range for n=${n}`);
        if (k === nyquist) {
            // Its own mirror: contributes a full-weight real term, not split in two.
            data[2 * k] += a;
            continue;
        }
        data[2 * k] += a / 2;
        data[2 * (n - k)] += a / 2;
    }
    return data;
}

/** Largest absolute value in `samples`, or 1 if they are all zero (avoids a divide by zero). */
export function peakAbs(samples) {
    let peak = 0;
    for (const s of samples) {
        const abs = Math.abs(s);
        if (abs > peak) peak = abs;
    }
    return peak || 1;
}

/**
 * Extract the real parts of an interleaved complex buffer (FOURT's output),
 * scaled so the loudest sample is exactly +-1.
 *
 * @param {Float64Array} data interleaved [re, im, re, im, ...], length 2*n
 * @returns {Float64Array} length n, normalized to [-1, 1]
 */
export function normalizedWaveform(data) {
    const n = data.length / 2;
    const real = new Float64Array(n);
    for (let i = 0; i < n; i++) real[i] = data[2 * i];
    const scale = 1 / peakAbs(real);
    for (let i = 0; i < n; i++) real[i] *= scale;
    return real;
}
