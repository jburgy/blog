// Everything the page and the tests have in common: `4th.wasm` plus a WASI
// implementation, driven one chunk of source at a time.
//
// Imported with a bare specifier so node resolves it from node_modules and the
// browser resolves it from the import map in index.html.
import { MemoryFileSystem, WASI, useAll } from "uwasi";

// `4th.wasm` only ever leaves through this, so it doubles as the "input
// exhausted, give me another line" signal.
const HALT = Symbol("halt");

const encoder = new TextEncoder();
const decoder = new TextDecoder();

/**
 * @param {BufferSource} wasm compiled `4th.wasm`
 * @param {object} options
 * @param {Record<string, string>} [options.files] contents of the preopened `/`
 * @param {(text: string) => void} options.write receives everything Forth emits
 * @returns {Promise<(source: string) => void>} feeds source to the interpreter
 */
export async function start(wasm, { files = {}, write }) {
    const fs = new MemoryFileSystem({ "/": "/" });
    for (const [path, content] of Object.entries(files)) {
        fs.addFile(path, content);
    }
    const wasi = new WASI({ args: ["4th"], features: [useAll({ withFileSystem: fs })] });

    let exports;
    const { instance } = await WebAssembly.instantiate(wasm, {
        wasi_snapshot_preview1: wasi.wasiImport,
        env: {
            throw_halt() {
                throw HALT;
            },
            write_out(ptr, len) {
                write(decoder.decode(new Uint8Array(exports.memory.buffer, ptr, len)));
            },
        },
    });
    exports = instance.exports;

    // Frames abandoned by the host throw leave the shadow stack where it stood,
    // so rewind it around every call rather than leaking a little of it per line.
    function call(fn, ...args) {
        const stack = exports.__stack_pointer.value;
        try {
            fn(...args);
        } catch (error) {
            if (error !== HALT) throw error;
        } finally {
            exports.__stack_pointer.value = stack;
        }
    }

    // `_start` initialises WASI and builds the session; `eval` drives it after.
    call(() => wasi.start(instance));

    const capacity = exports.input_capacity();

    return function feed(source) {
        // Chunk on line boundaries: a split inside a word would reach WORD as
        // two separate words.
        const lines = source.split(/(?<=\n)/);
        for (let i = 0; i < lines.length;) {
            let chunk = "";
            while (i < lines.length && chunk.length + lines[i].length <= capacity) {
                chunk += lines[i++];
            }
            if (chunk === "") throw new RangeError(`line longer than ${capacity} bytes`);
            const bytes = encoder.encode(chunk);
            new Uint8Array(exports.memory.buffer, exports.input(), bytes.length).set(bytes);
            call(exports.eval, bytes.length);
        }
    };
}
