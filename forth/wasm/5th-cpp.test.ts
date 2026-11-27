import { readFile } from 'node:fs/promises';
import { expect, test } from 'vitest';
import { runWasiCommand } from './wasi-command.mjs';

test('5th-cpp.wasm runs under uwasi', async () => {
    const wasm = await readFile(new URL('../5th-cpp.wasm', import.meta.url));
    let out = '';
    const code = await runWasiCommand(new Response(wasm, {
        headers: { 'content-type': 'application/wasm' },
    }), {
        stdin: new Blob(['65 EMIT\n']).stream(),
        stdout: chunk => { out += chunk; },
        stderr: () => {},
    });
    expect(code).toBe(0);
    expect(out).toBe('A');
});
