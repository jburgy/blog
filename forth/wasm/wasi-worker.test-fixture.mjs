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

const [, , wasmPath, preamblePath, ...lines] = process.argv;
const channel = new SharedInputChannel();
channel.push(await readFile(preamblePath));
for (const line of lines) channel.push(new TextEncoder().encode(line + '\n'));
channel.close();

const bytes = await readFile(wasmPath);
runWasiCommand(bytes, channel.sharedBuffer, (_fd, chunk) => writeSync(1, chunk))
    // A real failure (bad import, a trap) should be loud: the caller only
    // reads stdout, so surface it there too rather than as an invisible
    // unhandled rejection that just looks like "exited unexpectedly".
    .catch((error) => { writeSync(1, `FIXTURE ERROR: ${error.stack ?? error}\n`); process.exitCode = 1; });
