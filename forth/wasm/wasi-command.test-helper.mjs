// Test helper, not shipped: feeds a scripted session to a WASI command over an
// open stdin and resolves with everything it printed once it next asks for
// input, i.e. once it's idle. `lines` are strings (a "\n" is appended) or raw
// bytes (e.g. a preamble file, sent as is). Stdin is deliberately never
// closed: several guests (jonesforth's KEY, lisp's getchar, TinyBasic's
// KeyInChar) don't treat EOF as a stop and would spin, whereas an open stdin
// just parks them, which also means this can't wait on the guest exiting.
import { runWasiCommand } from './wasi-command.js';

/**
 * @param {Uint8Array} wasm
 * @param {...(string | Uint8Array)} lines
 * @returns {Promise<string>} stdout + stderr
 */
export async function runSession(wasm, ...lines) {
    let out = '';
    const idle = Promise.withResolvers();
    const stdin = new ReadableStream({
        start(controller) {
            for (const line of lines) {
                controller.enqueue(typeof line === 'string' ? new TextEncoder().encode(`${line}\n`) : line);
            }
        },
        // highWaterMark 0: only called once the guest has read the whole script and wants more.
        pull() {
            idle.resolve();
            return new Promise(() => { });
        },
    }, { highWaterMark: 0 });
    const append = (chunk) => { out += chunk; };
    const source = new Response(wasm, { headers: { 'content-type': 'application/wasm' } });
    // Exiting before going idle (crash, missing WASI import, ...) is a failure, not an empty `out`.
    runWasiCommand(source, { stdin, stdout: append, stderr: append })
        .then((code) => idle.reject(new Error(`exited unexpectedly (code ${code}): ${out}`)), idle.reject);
    await idle.promise;
    return out;
}
