// Web Worker for jonesforth.wasm: fetches the module and drives it through
// the shared `runWasiCommand` (see wasi-worker.js), which blocks stdin on a
// `uwasi.SharedInputChannel` that main.js feeds from the terminal. The
// hand-rolled WASI imports this file used to carry (fd_read/fd_write over a
// bespoke SharedArrayBuffer protocol) are gone — `runWasiCommand` and `uwasi`
// cover the same ground for every wasi command, not just this one.
import { runWasiCommand } from './wasi-worker.js';

self.addEventListener('message', async ({ data: { sharedBuffer } }) => {
    try {
        const bytes = await fetch('/blog/jonesforth.wasm').then((response) => response.arrayBuffer());
        self.postMessage({ type: 'ready' });
        const code = await runWasiCommand(bytes, sharedBuffer, (fd, chunk) => {
            self.postMessage({ type: 'output', fd, data: chunk });
        });
        self.postMessage({ type: 'exit', code });
    } catch (error) {
        self.postMessage({ type: 'error', message: error.message, stack: error.stack });
    }
});
