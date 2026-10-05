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

// jonesforth.S's native ARGC/ARGV/ENVIRON read argv/envp straight off the
// stack, because S0 there *is* the real process entry %esp, with Linux's
// kernel-laid-out argc/argv/envp sitting right above it -- no separate
// primitive needed. 4th.32.fs's (ARGC) (see 4th.c, 5th.c) exists only
// because the C ports gave up that adjacency: S0 points at a dedicated
// local `stack[]` array instead of the real entry stack, and wasi-libc's
// `args_get` fills a completely unrelated buffer (its own malloc arena) for
// argv. This test confirms that gap holds under wasm32-wasi too, so the
// jonesforth.S trick can't be revived there and (ARGC) stays necessary.
test('5th.wasm: (ARGC) is not S0 + CELL, so jonesforth.f\'s raw-stack ARGC/ARGV/ENVIRON ' +
    'trick cannot be revived under WASI', async ({ wasm }) => {
    const preamble = await readFile(join(import.meta.dirname, '../4th.32.fs'));
    const channel = new SharedInputChannel(256 * 1024); // 4th.32.fs alone is ~55 KiB
    let out = '';
    channel.push(preamble);
    channel.push(new TextEncoder().encode('(ARGC) S0 @ 4 + = .\n'));
    channel.close();
    const code = await runWasiCommand(wasm, channel.sharedBuffer, (_fd, chunk) => { out += chunk; });
    expect(code).toBe(0);
    // `out` also carries the boot banner, so compare only `.`'s own answer.
    expect(out.trim().split(/\s+/).pop()).toBe('0'); // -1 (true) would mean the addresses coincide
});

let jonesforthWasmPath: string;
let localizeWasmPath: string;
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

    // README's other "full interpreter" wast port (tail calls, cfa/ip/sp/rsp
    // as parameters instead of globals) -- same hand-rolled WASI surface as
    // jonesforth.wast, checked alongside it below.
    localizeWasmPath = join(tmpDir, 'localize.wasm');
    await execFileAsync(join(import.meta.dirname, '../node_modules/.bin/wat2wasm'), [
        '--enable-tail-call',
        '--debug-names',
        '-o', localizeWasmPath,
        join(import.meta.dirname, 'localize.wast'),
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

// jonesforth.f itself (unlike 4th.32.fs) defines ARGC/ARGV/ENVIRON the
// original jonesforth.S way -- straight off S0, no (ARGC) primitive -- but
// that only works where argc/argv genuinely sit on the real stack above S0
// (see the 5th.wasm test above for where it doesn't). jonesforth.wast/
// localize.wast sidestep the question entirely: they hand-roll their own
// WASI imports and only ever wire up fd_read/fd_write/proc_exit, so there is
// no args_get/args_sizes_get call anywhere in the module -- argv was simply
// never fetched from the host, adjacent to S0 or otherwise. Loading
// jonesforth.f here would still compile ARGC/ARGV/ENVIRON; they just read
// whatever garbage sits at S0's fixed data-segment address instead of real
// argv, which is why none of the scripted demo sessions ever call them.
vitestTest.for([
    ['jonesforth.wasm', () => jonesforthWasmPath],
    ['localize.wasm', () => localizeWasmPath],
])('%s never imports args_get/args_sizes_get, so it has no argv to expose and ' +
    'never needed (ARGC) in the first place', async ([, getPath]) => {
    const bytes = await readFile(getPath());
    const module = await WebAssembly.compile(bytes);
    const wasiImportNames = WebAssembly.Module.imports(module)
        .filter((imp) => imp.module === 'wasi_snapshot_preview1')
        .map((imp) => imp.name);
    expect(wasiImportNames).toEqual(['fd_read', 'fd_write', 'proc_exit']);
});

test('6th.wasm (wasm32-wasi): a scripted session exits cleanly on EOF', async () => {
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
    let errOut = '';
    // Resolves as soon as the expected output shows up, rather than racing a
    // fixed timeout: an early `exit` (crash, missing WASI import, ...) is a
    // real failure and rejects instead of silently reading an empty `out`.
    await new Promise<void>((resolve, reject) => {
        child.stdout.on('data', (chunk) => {
            out += chunk;
            if (out.includes('JONESFORTH VERSION 47') && out.includes('49')) resolve();
        });
        // Belt and suspenders alongside the fixture's own try/catch: a
        // module-load error (a bad loader registration, say) would crash
        // before that catch ever runs, so stderr is worth capturing too —
        // exactly the gap that made an earlier ENOENT (the jonesforth
        // submodule not checked out in CI) show up as a bare, unexplained
        // "exited unexpectedly (code 1): " with no indication why.
        child.stderr.on('data', (chunk) => { errOut += chunk; });
        child.once('error', reject);
        child.once('exit', (code) => reject(new Error(`fixture exited unexpectedly (code ${code}): ${out}${errOut}`)));
    }).finally(() => {
        // Expected teardown, not a failure: KEY never treats EOF as a stop,
        // so the fixture never exits on its own once it has run out of input.
        child.kill('SIGKILL');
    });

    expect(out).toContain('JONESFORTH VERSION 47');
    expect(out).toContain('49');
}, 10_000);
