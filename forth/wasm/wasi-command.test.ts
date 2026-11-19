// Covers `runWasiCommand` (see wasi-command.mjs), the shared piece factored
// out of the jonesforth.wasm post (bur.gy/2025/11/29/how-many-roads.html) so
// `5th.wasm`/`6th.wasm` wasi builds can drive a browser REPL the same way.
import { execFile } from 'node:child_process';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { promisify } from 'node:util';
import { afterAll, beforeAll, expect, test, vi } from 'vitest';
import { runWasiCommand } from './wasi-command.mjs';
import { runSession } from './wasi-command.test-helper.mjs';

const execFileAsync = promisify(execFile);
// wabt isn't an installed dependency; fetch it on demand instead.
const wat2wasm = (args: string[]) => execFileAsync('npx', ['-y', '--package', 'wabt', 'wat2wasm', ...args]);

const wasmResponse = (bytes: Uint8Array) => new Response(bytes, { headers: { 'content-type': 'application/wasm' } });

// A finite script: the stream closing is EOF, which `5th`/`6th` exit cleanly on.
async function runScript(wasm: Uint8Array, ...input: (string | Uint8Array)[]) {
    let out = '';
    let err = '';
    const code = await runWasiCommand(wasmResponse(wasm), {
        stdin: new Blob(input).stream(),
        stdout: (chunk) => { out += chunk; },
        stderr: (chunk) => { err += chunk; },
    });
    return { code, out, err };
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
const forthWasmPaths: Record<string, string> = {};

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

    // forth.rkt's two inner interpreters (run-defun, run-cps) with jonesforth's vocabulary.
    for (const name of ['defun', 'cps']) {
        forthWasmPaths[name] = join(tmpDir, `${name}.wasm`);
        await wat2wasm([
            '--enable-tail-call',
            '--debug-names',
            '-o', forthWasmPaths[name],
            join(import.meta.dirname, `${name}.wast`),
        ]);
    }

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

// defun.wast and cps.wast differ only in how the continuation is represented (a return stack of
// ips vs closures in memory), so one script covers both: IF/BEGIN/WHILE defined by 4th.32.fs,
// CATCH/THROW and DOES> (which walk and pop the return stack), `>R` run from the prompt, RSP@
// as a real address (`4+ @` is the parent's entry, as in jonesforth), and input that ends
// inside a `\` comment (which used to spin forever). They exit 0 at EOF.
test.for(['defun', 'cps'])('%s.wast: 4th.32.fs runs on it, return-stack words included', async (name) => {
    const preamble = await readFile(join(import.meta.dirname, '../4th.32.fs'));
    const { code, out } = await runScript(await readFile(forthWasmPaths[name]), preamble, [
        ': FACT DUP 1 > IF DUP 1 - RECURSE * THEN ; 10 FACT . CR',
        ': COUNT 0 BEGIN DUP . 1 + DUP 4 = UNTIL DROP ; COUNT CR',
        ': DOWN BEGIN DUP 0 > WHILE DUP . 1 - REPEAT DROP ; 3 DOWN CR',
        ": BOOM 77 THROW ; : SAFE ['] BOOM CATCH . CR ; SAFE",
        ': <BUILDS WORD CREATE DODOES , 0 , ; : DOES> R> LATEST @ >DFA ! ; : CONST <BUILDS , DOES> @ ;',
        '65 CONST FOO FOO EMIT CR',
        '64 >R RSP@ 1 TELL RDROP CR',
        '65 >R 66 >R RSP@ 4+ @ . RDROP RDROP CR',
        '66 EMIT \\ ends without a newline',
    ].join('\n'));
    expect(code).toBe(0);
    expect(out.endsWith('3628800 \n0 1 2 3 \n3 2 1 \n77 \nA\n@\n65 \nB')).toBe(true);
}, 20_000);

// defun.wast writes each EMIT as its own fd_write, so U+2219 (E2 88 99) arrives as three writes. stdout
// is decoded as one stream: the character comes out whole, and the two incomplete writes produce no chunk.
test('defun.wast: a character written a byte at a time is decoded whole', async () => {
    const preamble = await readFile(join(import.meta.dirname, '../4th.32.fs'));
    const chunks: string[] = [];
    const code = await runWasiCommand(wasmResponse(await readFile(forthWasmPaths.defun)), {
        stdin: new Blob([preamble, '226 EMIT 136 EMIT 153 EMIT\n']).stream(),
        stdout: (chunk) => { chunks.push(chunk); },
    });
    expect(code).toBe(0);
    expect(chunks).toContain('\u2219');
    expect(chunks).not.toContain('');
}, 20_000);

test('runWasiCommand: stdout defaults to console.log', async () => {
    const log = vi.spyOn(console, 'log').mockImplementation(() => { });
    try {
        const preamble = await readFile(join(import.meta.dirname, '../4th.32.fs'));
        await runWasiCommand(wasmResponse(await readFile(forthWasmPaths.defun)), {
            stdin: new Blob([preamble, '65 EMIT\n']).stream(),
        });
        expect(log).toHaveBeenCalledWith(expect.stringContaining('A'));
    } finally {
        log.mockRestore();
    }
}, 20_000);

// A stray EXIT at the prompt pops the root continuation: a clean exit, not a crash. Runaway
// recursion fills the return stack, which must report it instead of running into the data stack.
test.for(['defun', 'cps'])('%s.wast: a stray EXIT exits 0 and runaway recursion reports RETURN STACK OVERFLOW', async (name) => {
    const preamble = await readFile(join(import.meta.dirname, '../4th.32.fs'));
    const wasm = await readFile(forthWasmPaths[name]);
    const stray = await runScript(wasm, preamble, '65 EMIT EXIT 66 EMIT\n');
    expect(stray.code).toBe(0);
    expect(stray.out.endsWith('A')).toBe(true);
    const deep = await runScript(wasm, preamble, ': DEEP DUP 0> IF 1- RECURSE THEN ; 5000 DEEP . CR\n');
    expect(deep.code).toBe(1);
    expect(deep.err).toContain('RETURN STACK OVERFLOW');
}, 20_000);

// Inline WAT, assembled on demand: the error paths below need guests that misbehave on purpose.
async function compileWat(name: string, wat: string) {
    const watPath = join(tmpDir, `${name}.wat`);
    const wasmPath = join(tmpDir, `${name}.wasm`);
    await writeFile(watPath, wat);
    await wat2wasm(['-o', wasmPath, watPath]);
    return readFile(wasmPath);
}

// Each errno is stored as a byte at 100.. and written to stdout: fd_read on a non-stdin fd is
// BADF (8), a zero-length fd_read doesn't block on the (empty) stdin and returns 0, and
// fd_pread/fd_pwrite answer ENOSYS (52) beyond stdio but ESPIPE (70) for it. Then proc_exit(7).
test('guest-visible errnos for fd_read/fd_pread edge cases, and the proc_exit code is returned', async () => {
    const wasm = await compileWat('errnos', `(module
        (import "wasi_snapshot_preview1" "fd_read" (func $fd_read (param i32 i32 i32 i32) (result i32)))
        (import "wasi_snapshot_preview1" "fd_pread" (func $fd_pread (param i32 i32 i32 i64 i32) (result i32)))
        (import "wasi_snapshot_preview1" "fd_pwrite" (func $fd_pwrite (param i32 i32 i32 i64 i32) (result i32)))
        (import "wasi_snapshot_preview1" "fd_write" (func $fd_write (param i32 i32 i32 i32) (result i32)))
        (import "wasi_snapshot_preview1" "proc_exit" (func $proc_exit (param i32)))
        (memory (export "memory") 1)
        (func (export "_start")
            (i32.store8 (i32.const 100) (call $fd_read (i32.const 3) (i32.const 0) (i32.const 0) (i32.const 200)))
            (i32.store8 (i32.const 101) (call $fd_read (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 200)))
            (i32.store8 (i32.const 102) (call $fd_pread (i32.const 3) (i32.const 0) (i32.const 0) (i64.const 0) (i32.const 200)))
            (i32.store8 (i32.const 103) (call $fd_pread (i32.const 0) (i32.const 0) (i32.const 0) (i64.const 0) (i32.const 200)))
            (i32.store8 (i32.const 104) (call $fd_pwrite (i32.const 3) (i32.const 0) (i32.const 0) (i64.const 0) (i32.const 200)))
            (i32.store (i32.const 0) (i32.const 100))
            (i32.store (i32.const 4) (i32.const 5))
            (drop (call $fd_write (i32.const 1) (i32.const 0) (i32.const 1) (i32.const 200)))
            (call $proc_exit (i32.const 7))))`);
    const { code, out } = await runScript(wasm);
    expect(code).toBe(7);
    expect([...out].map((c) => c.charCodeAt(0))).toEqual([8, 0, 52, 70, 52]);
});

test('a module without _start is rejected', async () => {
    const wasm = await compileWat('no-start', '(module (memory (export "memory") 1))');
    await expect(runScript(wasm)).rejects.toThrow('not a WASI command');
});

test('a guest trap other than proc_exit propagates', async () => {
    const wasm = await compileWat('trap', '(module (memory (export "memory") 1) (func (export "_start") unreachable))');
    await expect(runScript(wasm)).rejects.toThrow(WebAssembly.RuntimeError);
});
