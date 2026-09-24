// A WASI shim just large enough to host forth/wasm/tabulate.wast.
//
// The Forth image keeps every piece of its state -- dictionary, HERE, LATEST,
// STATE -- in linear memory, so `_start` can be re-entered once per line: the
// dictionary survives while the data and return stacks are reset.  That makes
// a synchronous `eval()` possible without a worker or SharedArrayBuffer.

const ENOENT = 1;

// The terminal input buffer, per the memory map at the top of tabulate.wast.
const TIB = 0x4000;
const TIB_SIZE = 0x1000;

// proc_exit is the only way out of _start; a sentinel tells it from a real trap.
const EXIT = Symbol('proc_exit');

export class Forth {
    #exports;
    #input = new Uint8Array(0);
    #cursor = 0;
    #output = '';
    #decoder = new TextDecoder();

    static async instantiate(wasmBytes) {
        const forth = new Forth();
        const { instance } = await WebAssembly.instantiate(wasmBytes, {
            wasi_snapshot_preview1: forth.#wasi(),
        });
        forth.#exports = instance.exports;
        return forth;
    }

    get memory() {
        return this.#exports.memory;
    }

    /** Feed `source` to the interpreter and return everything it wrote. */
    eval(source) {
        this.#input = new TextEncoder().encode(source.endsWith('\n') ? source : `${source}\n`);
        this.#cursor = 0;
        this.#output = '';
        try {
            this.#exports._start();
        } catch (error) {
            if (error !== EXIT) throw error;
        }
        return this.#output;
    }

    /** Copy `bytes` into linear memory at `address`, NUL terminated. */
    poke(address, bytes) {
        const view = new Uint8Array(this.memory.buffer);
        view.set(bytes, address);
        view[address + bytes.length] = 0;
    }

    #wasi() {
        const iovecs = (iovs, count) => {
            const dv = new DataView(this.memory.buffer);
            return Array.from({ length: count }, (_, i) => [
                dv.getUint32(iovs + i * 8, true),
                dv.getUint32(iovs + i * 8 + 4, true),
            ]);
        };

        return {
            fd_read: (fd, iovs, iovsLen, nread) => {
                if (fd !== 0 || this.#cursor >= this.#input.length) {
                    // _key rewinds currkey to TIB *before* calling us and leaves
                    // buftop alone, so unless the buffer is blanked the next
                    // eval() would re-interpret the tail of this one.
                    new Uint8Array(this.memory.buffer, TIB, TIB_SIZE).fill(0);
                    return ENOENT;
                }
                const view = new Uint8Array(this.memory.buffer);
                let total = 0;
                for (const [buf, len] of iovecs(iovs, iovsLen)) {
                    if (this.#cursor >= this.#input.length) break;
                    const n = Math.min(len, this.#input.length - this.#cursor);
                    view.set(this.#input.subarray(this.#cursor, this.#cursor + n), buf);
                    this.#cursor += n;
                    total += n;
                }
                new DataView(this.memory.buffer).setUint32(nread, total, true);
                return 0;
            },

            fd_write: (fd, iovs, iovsLen, nwritten) => {
                const view = new Uint8Array(this.memory.buffer);
                let total = 0;
                for (const [buf, len] of iovecs(iovs, iovsLen)) {
                    this.#output += this.#decoder.decode(view.subarray(buf, buf + len), { stream: true });
                    total += len;
                }
                new DataView(this.memory.buffer).setUint32(nwritten, total, true);
                return 0;
            },

            proc_exit: () => {
                throw EXIT;
            },
        };
    }
}
