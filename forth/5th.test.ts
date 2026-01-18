import { WASI, useProc, useStdio } from 'uwasi';
import { expect } from 'vitest';
import { test } from './wasm-test.ts';

test.for([
    ["65 EMIT", "A"],
    ["777 65 EMIT", "A"],
    ["32 DUP + 1+ EMIT", "A"],
    ["16 DUP 2DUP + + + 1+ EMIT", "A"],
    ["8 DUP * 1+ EMIT", "A"],
    ["CHAR A EMIT", "A"],
    [": SLOW WORD FIND >CFA EXECUTE ; 65 SLOW EMIT", "A"],
    [
        `${new DataView(new TextEncoder().encode('65').buffer).getUint16(0, true)} DSP@ 2 NUMBER DROP EMIT`,
        "A",
    ],
    ["64 >R RSP@ 1 TELL RDROP", "@"],
    ["65 DSP@ RSP@ SWAP C@C! RSP@ 1 TELL", "A"],
    ["64 >R 1 RSP@ +! RSP@ 1 TELL", "A"],
    [`
: <BUILDS WORD CREATE DODOES , 0 , ;
: DOES> R> LATEST @ >DFA ! ;
: CONST <BUILDS , DOES> @ ;

65 CONST FOO
FOO EMIT
`,
            "A",
    ],
])('%s -> %s', async ([input, output], { wasm }) => {
    const inputs = [`${input}\n`];
    const outputs: (string | Uint8Array<ArrayBufferLike>)[] = [];
    const wasi = new WASI({
        features: [
            useProc,
            useStdio({
                stdin: () => inputs.shift() as string,
                stdout: (chunk: string | Uint8Array<ArrayBufferLike>) => outputs.push(chunk),
            }),
        ],
    });

    const instance = await WebAssembly.instantiate(await wasm, {
        wasi_snapshot_preview1: wasi.wasiImport,
    });
    const exitCode = wasi.start(instance);
    expect(exitCode).toBe(0);
    expect(outputs.join('').trim()).toBe(output);
})