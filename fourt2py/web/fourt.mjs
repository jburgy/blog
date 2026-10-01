// Drives fourt2py/wasm/fourt.c (a transliteration of FOURT.F, see
// fourt2py/FOURT.F) compiled to WebAssembly by emcc. The C side keeps the
// Fortran calling convention verbatim:
//
//   void fourt_(double *data, int *nn, int ndim, int isign, int iform, double *work);
//
// `data` is an interleaved [re, im, re, im, ...] buffer, 1 complex number per
// entry of `nn`'s product. This wrapper only drives the NDIM=1 case the demo
// needs: a single FFT length `n`.

const BYTES_PER_DOUBLE = 8;
const BYTES_PER_INT = 4;

export class Fourt {
    #module;
    #fourt;

    constructor(module) {
        this.#module = module;
        this.#fourt = module.cwrap('fourt_', null, ['number', 'number', 'number', 'number', 'number', 'number']);
    }

    static async instantiate(moduleUrl = new URL('../wasm/fourt.mjs', import.meta.url)) {
        const factory = (await import(moduleUrl)).default;
        return new Fourt(await factory());
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
        const module = this.#module;
        const dataPtr = module._malloc(data.length * BYTES_PER_DOUBLE);
        const nnPtr = module._malloc(BYTES_PER_INT);
        // FOURT needs WORK only when a dimension isn't a power of two, but a
        // buffer sized to the full FFT length is always large enough and safe
        // to pass regardless.
        const workPtr = module._malloc(2 * n * BYTES_PER_DOUBLE);
        try {
            for (let i = 0; i < data.length; i++) {
                module.setValue(dataPtr + i * BYTES_PER_DOUBLE, data[i], 'double');
            }
            module.setValue(nnPtr, n, 'i32');
            this.#fourt(dataPtr, nnPtr, 1, isign, iform, workPtr);

            const result = new Float64Array(data.length);
            for (let i = 0; i < result.length; i++) {
                result[i] = module.getValue(dataPtr + i * BYTES_PER_DOUBLE, 'double');
            }
            return result;
        } finally {
            module._free(dataPtr);
            module._free(nnPtr);
            module._free(workPtr);
        }
    }
}
