// Test fixture, not shipped: feeds a scripted session to a wasm32-wasi
// command and writes raw output with `fs.writeSync` so bytes already written
// survive the process being killed. `runWasiCommand`'s `stdin` genuinely
// never returns "no more input, stop" for a REPL like jonesforth.wasm (see
// wasi-worker.test.ts) — closing the channel only makes it spin, never
// exit — so the caller always kills this process once it has read enough.
import { writeSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { SharedInputChannel } from 'uwasi';
import { runWasiCommand } from './wasi-worker.js';

// Everything, including the `readFile`s, is wrapped: an ENOENT here (the
// jonesforth submodule not checked out, say) is otherwise an uncaught
// top-level-await rejection — Node prints it to stderr and exits 1, which
// the caller (only reading stdout) sees as a bare, unexplained "exited
// unexpectedly". Caught here, it reaches the caller on the stream it does
// read.
try {
    const [, , wasmPath, preamblePath, ...lines] = process.argv;
    const channel = new SharedInputChannel();
    channel.push(await readFile(preamblePath));
    for (const line of lines) channel.push(new TextEncoder().encode(line + '\n'));
    channel.close();

    const bytes = await readFile(wasmPath);
    await runWasiCommand(bytes, channel.sharedBuffer, (_fd, chunk) => writeSync(1, chunk));
} catch (error) {
    writeSync(1, `FIXTURE ERROR: ${error.stack ?? error}\n`);
    process.exitCode = 1;
}

