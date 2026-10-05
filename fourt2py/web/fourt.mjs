// Drives fourt2py/wasm/fourt.c (a transliteration of FOURT.F, see
// fourt2py/FOURT.F) compiled to a WASI "reactor" module by wasi-sdk clang
// (see package.json's build:wasm script). fourt_ only does in-place number
// crunching on its double* buffers -- no syscalls, no stdio -- so the
// compiled module needs no WASI imports at all; plain
// WebAssembly.instantiate() with an empty import object is enough. The C
// side keeps the Fortran calling convention verbatim:
//
//   void fourt_(double *data, int *nn, int ndim, int isign, int iform, double *work);
//
// `data` is an interleaved [re, im, re, im, ...] buffer, 1 complex number per
// entry of `nn`'s product. This wrapper only drives the NDIM=1 case the demo
// needs: a single FFT length `n`.

import { readFile } from 'node:fs/promises';

const BYTES_PER_DOUBLE = 8;
const BYTES_PER_INT = 4;

export class Fourt {
    #exports;

    constructor(exports) {
        this.#exports = exports;
    }

    // Node-only (readFile, not fetch): fourt.mjs is a dev/benchmark
    // comparison tool driven from fourt.test.mjs and benchmark.mjs -- the
    // published browser demo (web/index.html) uses fourt.pow2.mjs instead.
    static async instantiate(wasmUrl = new URL('../wasm/fourt.wasm', import.meta.url)) {
        const bytes = await readFile(wasmUrl);
        const { instance } = await WebAssembly.instantiate(bytes, {});
        // WASI reactor ABI: run the module's global constructors once,
        // before calling any other export (there's no _start to do it).
        instance.exports._initialize();
        return new Fourt(instance.exports);
    }

    /**
     * Transform `data` (length 2*n, interleaved complex) and return the result
     * as a new buffer; `data` itself is left untouched.
     *
     * @param {Float64Array} data interleaved [re, im, ...], length 2*n
     * @param {number} n FFT length
     * @param {{isign?: number, iform?: number}} [options] isign: -1 forward (normalized
     *   by 1/n), +1 inverse (unnormalized) -- see the comment at the top of FOURT.F.
     *   iform: 1 for a fully complex transform (the only mode this demo uses).
     * @returns {Float64Array} a fresh copy of the transformed buffer
     */
    transform(data, n, { isign = 1, iform = 1 } = {}) {
        const exports = this.#exports;
        const dataPtr = exports.malloc(data.length * BYTES_PER_DOUBLE);
        const nnPtr = exports.malloc(BYTES_PER_INT);
        // FOURT needs WORK only when a dimension isn't a power of two, but a
        // buffer sized to the full FFT length is always large enough and safe
        // to pass regardless.
        const workPtr = exports.malloc(2 * n * BYTES_PER_DOUBLE);
        try {
            // Re-read exports.memory.buffer after every malloc: a grow can
            // detach the previous ArrayBuffer.
            let view = new DataView(exports.memory.buffer);
            for (let i = 0; i < data.length; i++) {
                view.setFloat64(dataPtr + i * BYTES_PER_DOUBLE, data[i], true);
            }
            view.setInt32(nnPtr, n, true);
            exports.fourt_(dataPtr, nnPtr, 1, isign, iform, workPtr);

            view = new DataView(exports.memory.buffer);
            const result = new Float64Array(data.length);
            for (let i = 0; i < result.length; i++) {
                result[i] = view.getFloat64(dataPtr + i * BYTES_PER_DOUBLE, true);
            }
            return result;
        } finally {
            exports.free(dataPtr);
            exports.free(nnPtr);
            exports.free(workPtr);
        }
    }
}
