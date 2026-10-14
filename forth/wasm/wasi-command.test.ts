// Covers `runWasiCommand` (see wasi-command.mjs), the shared piece factored
// out of the jonesforth.wasm post (bur.gy/2025/11/29/how-many-roads.html) so
// `5th.wasm`/`6th.wasm` wasi builds can drive a browser REPL the same way.
import { execFile } from 'node:child_process';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { promisify } from 'node:util';
import { afterAll, beforeAll, expect, test } from 'vitest';
import { runWasiCommand } from './wasi-command.mjs';
import { runSession } from './wasi-command.test-helper.mjs';

const execFileAsync = promisify(execFile);
// wabt isn't an installed dependency; fetch it on demand instead.
const wat2wasm = (args: string[]) => execFileAsync('npx', ['-y', '--package', 'wabt', 'wat2wasm', ...args]);

const wasmResponse = (bytes: Uint8Array) => new Response(bytes, { headers: { 'content-type': 'application/wasm' } });

// A finite script: the stream closing is EOF, which `5th`/`6th` exit cleanly on.
async function runScript(wasm: Uint8Array, ...input: (string | Uint8Array)[]) {
    let out = '';
    const code = await runWasiCommand(wasmResponse(wasm), {
        stdin: new Blob(input).stream(),
        stdout: (chunk) => { out += chunk; },
    });
    return { code, out };
}

// Read per test, not at load: 5th.wasm needs wasi-sdk, and a missing one must only fail its own tests.
const read5th = () => readFile(join(import.meta.dirname, '../5th.wasm'));

test('5th.wasm: a scripted session exits cleanly on EOF', async () => {
    const { code, out } = await runScript(await read5th(), '65 EMIT\n');
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
    'trick cannot be revived under WASI', async () => {
    const preamble = await readFile(join(import.meta.dirname, '../4th.32.fs'));
    const { code, out } = await runScript(await read5th(), preamble, '(ARGC) S0 @ 4 + = .\n');
    expect(code).toBe(0);
    // `out` also carries the boot banner, so compare only `.`'s own answer.
    expect(out.trim().split(/\s+/).pop()).toBe('0'); // -1 (true) would mean the addresses coincide
});

let jonesforthWasmPath: string;
let localizeWasmPath: string;
let sixthWasmPath: string;
let tmpDir: string;

beforeAll(async () => {
    tmpDir = await mkdtemp(join(tmpdir(), 'wasi-command-'));
    jonesforthWasmPath = join(tmpDir, 'jonesforth.wasm');
    await wat2wasm([
        '--enable-tail-call',
        '--debug-names',
        '-o', jonesforthWasmPath,
        join(import.meta.dirname, 'jonesforth.wast'),
    ]);

    // README's other "full interpreter" wast port (tail calls, cfa/ip/sp/rsp
    // as parameters instead of globals) -- same hand-rolled WASI surface as
    // jonesforth.wast, checked alongside it below.
    localizeWasmPath = join(tmpDir, 'localize.wasm');
    await wat2wasm([
        '--enable-tail-call',
        '--debug-names',
        '-o', localizeWasmPath,
        join(import.meta.dirname, 'localize.wast'),
    ]);

    // zig build -Dtarget=wasm32-wasi (see build.zig's buildWasi)
    await execFileAsync('zig', [
        'build', 'install-6th',
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
test.for([
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
    const { code, out } = await runScript(await readFile(sixthWasmPath), preamble, ': SQUARE DUP * ; 7 SQUARE .\n');
    expect(code).toBe(0);
    expect(out).toContain('49');
});

test('6th.wasm: an empty stdin chunk is not EOF', async () => {
    const preamble = await readFile(join(import.meta.dirname, '../4th.32.fs'));
    const stdin = new ReadableStream<Uint8Array>({
        start(controller) {
            controller.enqueue(new Uint8Array(0));
            controller.enqueue(preamble);
            controller.enqueue(new TextEncoder().encode(': SQUARE DUP * ; 7 SQUARE .\n'));
            controller.close();
        },
    });
    let out = '';
    const code = await runWasiCommand(wasmResponse(await readFile(sixthWasmPath)), {
        stdin,
        stdout: (chunk) => { out += chunk; },
    });
    expect(code).toBe(0);
    expect(out).toContain('49');
});

test('jonesforth.wasm: KEY blocks on an open stdin and never treats EOF as a stop, so a scripted ' +
    'session is abandoned once the guest is idle, rather than awaited to completion', async () => {
    const preamble = await readFile(join(import.meta.dirname, '../../jonesforth/jonesforth.f'));
    const out = await runSession(await readFile(jonesforthWasmPath), preamble, ': SQUARE DUP * ; 7 SQUARE . CR');
    expect(out).toContain('JONESFORTH VERSION 47');
    expect(out).toContain('49');
}, 10_000);
