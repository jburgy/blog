// Covers `runWasiCommand` (see wasi-worker.js), the shared piece factored
// out of the jonesforth.wasm post (bur.gy/2025/11/29/how-many-roads.html) so
// `5th.wasm`/`6th.wasm` wasi builds can drive a browser REPL the same way.
import { execFile, spawn } from 'node:child_process';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { promisify } from 'node:util';
import { afterAll, beforeAll, expect, test as vitestTest } from 'vitest';
import { SharedInputChannel } from 'uwasi';
import { runWasiCommand } from './wasi-worker.js';
import { test } from '../wasm-test.ts';

const execFileAsync = promisify(execFile);

test('5th.wasm: a scripted session exits cleanly on EOF', async ({ wasm }) => {
    const channel = new SharedInputChannel();
    let out = '';
    channel.push(new TextEncoder().encode('65 EMIT\n'));
    channel.close(); // a finite script, unlike jonesforth.wasm below: EOF is the right signal here
    const code = await runWasiCommand(wasm, channel.sharedBuffer, (_fd, chunk) => { out += chunk; });
    expect(code).toBe(0);
    expect(out).toBe('A');
});

let jonesforthWasmPath: string;
let sixthWasmPath: string;
let tmpDir: string;

beforeAll(async () => {
    tmpDir = await mkdtemp(join(tmpdir(), 'wasi-worker-'));
    jonesforthWasmPath = join(tmpDir, 'jonesforth.wasm');
    await execFileAsync(join(import.meta.dirname, '../node_modules/.bin/wat2wasm'), [
        '--enable-tail-call',
        '--debug-names',
        '-o', jonesforthWasmPath,
        join(import.meta.dirname, 'jonesforth.wast'),
    ]);

    // zig build -Dtarget=wasm32-wasi (see build.zig's buildWasi)
    await execFileAsync('zig', [
        'build',
        '-Dtarget=wasm32-wasi', '-Dcpu=baseline+tail_call',
        '--prefix', tmpDir,
    ], { cwd: join(import.meta.dirname, '..') });
    sixthWasmPath = join(tmpDir, 'web', 'wasi', '6th.wasm');
}, 30_000);

afterAll(async () => {
    await rm(tmpDir, { recursive: true, force: true });
});

test('6th.wasm (wasm32-wasi, no Emscripten): a scripted session exits cleanly on EOF', async () => {
    const preamble = await readFile(join(import.meta.dirname, '../4th.32.fs'));
    const channel = new SharedInputChannel(256 * 1024); // 4th.32.fs alone is ~55 KiB
    let out = '';
    channel.push(preamble);
    channel.push(new TextEncoder().encode(': SQUARE DUP * ; 7 SQUARE .\n'));
    channel.close();
    const bytes = await readFile(sixthWasmPath);
    const code = await runWasiCommand(bytes, channel.sharedBuffer, (_fd, chunk) => { out += chunk; });
    expect(code).toBe(0);
    expect(out).toContain('49');
});

vitestTest('jonesforth.wasm: KEY blocks for real and never treats EOF as a stop, so a scripted ' +
    'session is killed once it has produced the expected output, rather than awaited to completion', async () => {
    const preamblePath = join(import.meta.dirname, '../../jonesforth/jonesforth.f');
    const fixture = join(import.meta.dirname, 'wasi-worker.test-fixture.mjs');

    // `--import` registers the loader that resolves wasi-worker.js's
    // `https://esm.sh/uwasi@1.6.0` import to the local package; plain `node`
    // has no import map to do that itself (see uwasi-cdn.loader.mjs).
    const loader = pathToFileURL(join(import.meta.dirname, 'uwasi-cdn.loader.mjs')).href;
    const registerLoader = `data:text/javascript,
        import { register } from "node:module";
        register(${JSON.stringify(loader)});
    `;

    const child = spawn(process.execPath, [
        '--import', registerLoader, fixture, jonesforthWasmPath, preamblePath, ': SQUARE DUP * ; 7 SQUARE . CR',
    ]);

    let out = '';
    // Resolves as soon as the expected output shows up, rather than racing a
    // fixed timeout: an early `exit` (crash, missing WASI import, ...) is a
    // real failure and rejects instead of silently reading an empty `out`.
    await new Promise<void>((resolve, reject) => {
        child.stdout.on('data', (chunk) => {
            out += chunk;
            if (out.includes('JONESFORTH VERSION 47') && out.includes('49')) resolve();
        });
        child.once('error', reject);
        child.once('exit', (code) => reject(new Error(`fixture exited unexpectedly (code ${code}): ${out}`)));
    }).finally(() => {
        // Expected teardown, not a failure: KEY never treats EOF as a stop,
        // so the fixture never exits on its own once it has run out of input.
        child.kill('SIGKILL');
    });

    expect(out).toContain('JONESFORTH VERSION 47');
    expect(out).toContain('49');
}, 10_000);
