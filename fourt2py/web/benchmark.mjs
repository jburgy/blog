#!/usr/bin/env node
// Benchmarks fourt2py/web/fourt.pure.mjs (asm.js-flavored pure JS) against
// fourt2py/wasm/fourt.c compiled to wasm, on the same workload.
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
//                        (still marshalled in one setValue() per double --
//                        this build doesn't export HEAPF64 for bulk copies
//                        -- but the malloc/free pair only happens once).
//                        This isolates the FFT and marshalling cost from
//                        the per-call allocator cost, which has nothing to
//                        do with wasm vs JS codegen.
//
// fourt.pure.mjs has no such boundary to cross (it's plain JS operating on
// a Float64Array directly), so it only gets one number.
//
// Usage: node web/benchmark.mjs [--iterations N] [--trials N] [--warmup N]
import { Fourt } from './fourt.mjs';
import { fourt as fourtPure } from './fourt.pure.mjs';

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
    const module = wasm.module;
    const BYTES_PER_DOUBLE = 8;
    const dataPtr = module._malloc(2 * n * BYTES_PER_DOUBLE);
    const nnPtr = module._malloc(4);
    const workPtr = module._malloc(2 * n * BYTES_PER_DOUBLE);
    module.setValue(nnPtr, n, 'i32');
    return {
        run(input, isign, iform) {
            // Same per-double setValue marshalling Fourt.transform() uses
            // (the build doesn't export HEAPF64 for a bulk alternative) --
            // the point of this "kernel" path isn't to avoid marshalling,
            // just the repeated malloc/free a fresh transform() call does.
            for (let i = 0; i < input.length; i++) {
                module.setValue(dataPtr + i * BYTES_PER_DOUBLE, input[i], 'double');
            }
            wasm.fourtRaw(dataPtr, nnPtr, 1, isign, iform, workPtr);
        },
        free() {
            module._free(dataPtr);
            module._free(nnPtr);
            module._free(workPtr);
        },
    };
}

async function main() {
    const options = parseArgs(process.argv.slice(2));
    const fourtWasm = await Fourt.instantiate();
    // Reach into the private module/cwrap'd function for the raw-kernel path.
    // (Fourt doesn't expose these; this is benchmark-only plumbing, not a
    // supported API.)
    const module = await (await import(new URL('../wasm/fourt.mjs', import.meta.url))).default();
    const fourtRaw = module.cwrap('fourt_', null, ['number', 'number', 'number', 'number', 'number', 'number']);
    const wasm = { module, fourtRaw };

    const lengths = [200, 256, 360, 1000, 4096];
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

        rows.push({
            n,
            wasmCall: median(callSamples),
            wasmKernel: median(kernelSamples),
            pure: median(pureSamples),
        });
    }

    const col = (s, w) => s.toString().padStart(w);
    console.log(`${'n'.padStart(6)}  ${'wasm (call)'.padStart(14)}  ${'wasm (kernel)'.padStart(14)}  ${'pure JS'.padStart(14)}  ${'JS/kernel'.padStart(10)}`);
    for (const row of rows) {
        console.log(
            `${col(row.n, 6)}  ${col(row.wasmCall.toFixed(2) + 'us', 14)}  ${col(row.wasmKernel.toFixed(2) + 'us', 14)}  ` +
            `${col(row.pure.toFixed(2) + 'us', 14)}  ${col((row.pure / row.wasmKernel).toFixed(2) + 'x', 10)}`,
        );
    }
}

main();
