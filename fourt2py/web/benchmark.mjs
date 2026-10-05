#!/usr/bin/env node
// Benchmarks fourt2py/web/fourt.pure.mjs (asm.js-flavored pure JS, general
// NDIM=1 case) and fourt2py/web/fourt.pow2.mjs (the same, specialized to
// power-of-two lengths) against fourt2py/wasm/fourt.c compiled to wasm, on
// the same workload.
//
// Two numbers are reported for wasm, because they answer different
// questions:
//
//   "wasm (call)"    -- fourt2py/web/fourt.mjs's Fourt.transform(), exactly
//                        as the demo uses it: malloc, marshal the input in
//                        one JS call per double, run, marshal the output
//                        back out, free. This is what dragging a knot
//                        actually costs.
//   "wasm (kernel)"   -- the same compiled fourt_(), but called through a
//                        pointer allocated once outside the timing loop
//                        (still marshalled one double at a time via
//                        DataView -- this build exports no bulk-copy helper
//                        -- but the malloc/free pair only happens once).
//                        This isolates the FFT and marshalling cost from
//                        the per-call allocator cost, which has nothing to
//                        do with wasm vs JS codegen.
//
// Neither pure-JS candidate has such a boundary to cross, so each gets one
// number. fourt.pow2.mjs only applies at power-of-two lengths; other rows
// show "--" for it.
//
// Usage: node web/benchmark.mjs [--iterations N] [--trials N] [--warmup N]
import { readFile } from 'node:fs/promises';
import { Fourt } from './fourt.mjs';
import { fourt as fourtPure } from './fourt.pure.mjs';
import { fourt as fourtPow2 } from './fourt.pow2.mjs';

function parseArgs(argv) {
    const options = { iterations: 2000, trials: 7, warmup: 2000 };
    for (let i = 0; i < argv.length; i++) {
        const key = argv[i].replace(/^--/, '');
        if (key in options) {
            options[key] = Number(argv[++i]);
        }
    }
    return options;
}

function isPowerOfTwo(n) {
    return n > 0 && (n & (n - 1)) === 0;
}

function median(samples) {
    const sorted = [...samples].sort((a, b) => a - b);
    const mid = sorted.length >> 1;
    return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

/** Microseconds per call, one sample per trial, after `warmup` untimed calls. */
function timeCalls(fn, { iterations, trials, warmup }) {
    for (let i = 0; i < warmup; i++) fn();
    const samples = [];
    for (let t = 0; t < trials; t++) {
        const start = performance.now();
        for (let i = 0; i < iterations; i++) fn();
        samples.push(((performance.now() - start) / iterations) * 1000);
    }
    return samples;
}

function randomSpectrum(n, seed) {
    // A small xorshift64 PRNG so every candidate sees the same input.
    let state = BigInt(seed) & 0xffffffffffffffffn;
    const next = () => {
        state ^= state << 13n; state &= 0xffffffffffffffffn;
        state ^= state >> 7n;
        state ^= state << 17n; state &= 0xffffffffffffffffn;
        return (Number(state % 2000000n) - 1000000) / 1000000;
    };
    const data = new Float64Array(2 * n);
    for (let i = 0; i < data.length; i++) data[i] = next();
    return data;
}

/** A raw, pointer-reusing path through the same compiled fourt_(), so the
 * timing isolates the FFT itself from malloc/marshal/free overhead. */
function rawWasmKernel(wasm, n) {
    const BYTES_PER_DOUBLE = 8;
    const dataPtr = wasm.malloc(2 * n * BYTES_PER_DOUBLE);
    const nnPtr = wasm.malloc(4);
    const workPtr = wasm.malloc(2 * n * BYTES_PER_DOUBLE);
    new DataView(wasm.memory.buffer).setInt32(nnPtr, n, true);
    return {
        run(input, isign, iform) {
            // Same per-double marshalling Fourt.transform() uses -- the
            // point of this "kernel" path isn't to avoid marshalling, just
            // the repeated malloc/free a fresh transform() call does.
            const view = new DataView(wasm.memory.buffer);
            for (let i = 0; i < input.length; i++) {
                view.setFloat64(dataPtr + i * BYTES_PER_DOUBLE, input[i], true);
            }
            wasm.fourt_(dataPtr, nnPtr, 1, isign, iform, workPtr);
        },
        free() {
            wasm.free(dataPtr);
            wasm.free(nnPtr);
            wasm.free(workPtr);
        },
    };
}

async function main() {
    const options = parseArgs(process.argv.slice(2));
    const fourtWasm = await Fourt.instantiate();
    // Reach into a second, raw module instance for the "kernel" path below
    // -- bypasses Fourt.transform()'s per-call malloc/free, not its
    // marshalling (see rawWasmKernel's comment). Fourt doesn't expose its
    // internal exports; this is benchmark-only plumbing, not a supported API.
    const wasmUrl = new URL('../wasm/fourt.wasm', import.meta.url);
    const { instance } = await WebAssembly.instantiate(await readFile(wasmUrl), {});
    instance.exports._initialize();
    const wasm = instance.exports;

    const lengths = [200, 256, 360, 512, 1000, 4096];
    const rows = [];

    for (const n of lengths) {
        const input = randomSpectrum(n, 1);
        const work = new Float64Array(2 * n + 16);
        const nn = new Int32Array([n]);

        const callSamples = timeCalls(() => fourtWasm.transform(input, n, { isign: 1, iform: 1 }), options);

        const kernel = rawWasmKernel(wasm, n);
        const kernelSamples = timeCalls(() => kernel.run(input, 1, 1), options);
        kernel.free();

        const pureInput = input.slice();
        const pureSamples = timeCalls(() => {
            pureInput.set(input);
            fourtPure(pureInput, nn, 1, 1, 1, work);
        }, options);

        let pow2 = null;
        if (isPowerOfTwo(n)) {
            const pow2Input = input.slice();
            const pow2Samples = timeCalls(() => {
                pow2Input.set(input);
                fourtPow2(pow2Input, n, 1);
            }, options);
            pow2 = median(pow2Samples);
        }

        rows.push({
            n,
            wasmCall: median(callSamples),
            wasmKernel: median(kernelSamples),
            pure: median(pureSamples),
            pow2,
        });
    }

    const col = (s, w) => s.toString().padStart(w);
    console.log(
        `${'n'.padStart(6)}  ${'wasm (call)'.padStart(14)}  ${'wasm (kernel)'.padStart(14)}  ` +
        `${'pure JS'.padStart(14)}  ${'pow2 JS'.padStart(14)}  ${'pow2/kernel'.padStart(12)}`,
    );
    for (const row of rows) {
        const pow2Str = row.pow2 === null ? '--' : row.pow2.toFixed(2) + 'us';
        const ratioStr = row.pow2 === null ? '--' : (row.pow2 / row.wasmKernel).toFixed(2) + 'x';
        console.log(
            `${col(row.n, 6)}  ${col(row.wasmCall.toFixed(2) + 'us', 14)}  ${col(row.wasmKernel.toFixed(2) + 'us', 14)}  ` +
            `${col(row.pure.toFixed(2) + 'us', 14)}  ${col(pow2Str, 14)}  ${col(ratioStr, 12)}`,
        );
    }
}

main();
