import { join } from 'node:path';
import { readFile } from 'node:fs/promises';
import { test as base } from 'vitest';

interface MyFixtures {
    wasm: WebAssembly.Module;
}

export const test = base.extend<MyFixtures>({
    wasm: async ({ }, use) => {
        const bytes = await readFile(join(__dirname, '5th.wasm'))
        const wasm = await WebAssembly.compile(new Uint8Array(bytes));
        await use(wasm);
    }
});
