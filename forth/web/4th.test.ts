// No browser: the demo's wasm, WASI layer and re-entrant eval loop are all
// plain JavaScript, so vitest and uwasi cover them in node. Needs `make web`.
//
// Also drives 5th.wasm (wasi-sdk clang, a plain WASI command rather than
// 4th's re-entrant eval loop) through PRIMITIVE_CASES below: both ports
// bootstrap the same jonesforth primitives before any `.f` preamble loads,
// so one shared matrix exercises both instead of duplicating it the way
// 5th.test.ts and the since-removed test_4th_wasm.py used to. Skipped if
// `5th.wasm` hasn't been built (`npm run build`), so `npm run test:web`
// still works with only `make web` done.
import { readFile } from "node:fs/promises";
import { SharedInputChannel } from "uwasi";
import { describe, expect, test } from "vitest";
import { runWasiCommand } from "../wasm/wasi-worker.js";
import { start } from "./4th.js";

const wasm = await readFile(new URL("4th.wasm", import.meta.url));
const preamble = await readFile(new URL("../4th.32.fs", import.meta.url), "utf8");
const wasm5th = await readFile(new URL("../5th.wasm", import.meta.url)).catch((error) => {
    if (error.code !== "ENOENT") throw error;
    return undefined;
});

/** A booted interpreter whose output since the last `taken()` can be read back. */
async function session(files: Record<string, string> = {}) {
    let output = "";
    const feed = await start(wasm, { files, write: (text) => (output += text) });
    const taken = () => {
        const text = output;
        output = "";
        return text;
    };
    return { feed, taken };
}

test("jonesforth.f loads without an unknown word", async () => {
    const { feed, taken } = await session();
    feed(preamble);
    const banner = taken();
    expect(banner).not.toMatch(/PARSE ERROR/);
    expect(banner).toContain("JONESFORTH VERSION 47");
});

test("state survives between calls, because it all lives in linear memory", async () => {
    const { feed, taken } = await session();
    feed(preamble);
    taken();

    // One `eval` per line, exactly how the page drives it from a keypress.
    feed(": SQUARE DUP * ;\n");
    expect(taken()).toBe("");
    feed("7 SQUARE .\n");
    expect(taken()).toBe("49 ");
});

test("SYS_BRK backs UNUSED with the real size of the data segment", async () => {
    const { feed, taken } = await session();
    feed(preamble);
    taken();

    feed("UNUSED .\n");
    const before = Number(taken().trim());
    expect(before).toBeGreaterThan(0);

    feed("16 MORECORE UNUSED .\n");
    expect(Number(taken().trim())).toBe(before + 16);
});

test("SYS_OPEN and SYS_READ reach the WASI file system", async () => {
    const { feed, taken } = await session({ "/motd": "files work in here too\n" });
    feed(preamble);
    taken();

    feed('S" /motd" R/O OPEN-FILE DROP >R HERE @ 64 R> READ-FILE DROP HERE @ SWAP TELL\n');
    expect(taken()).toBe("files work in here too\n");
});

test("a missing file comes back as an errno rather than a trap", async () => {
    const { feed, taken } = await session();
    feed(preamble);
    taken();

    feed('S" /nope" R/O OPEN-FILE SWAP DROP 0<> .\n');
    expect(taken()).toBe("-1 ");
});

test.for([
    [": DOUBLE 2 * ; : QUAD DOUBLE DOUBLE ; 5 QUAD .", "20 "],
    ["255 HEX . DECIMAL", "FF "],
    ["1 2 3 .S", "3 2 1 "],
    ["NOSUCHWORD", "PARSE ERROR: NOSUCHWORD\n"],
])("%s", async ([source, expected]) => {
    const { feed, taken } = await session();
    feed(preamble);
    taken();

    feed(`${source}\n`);
    expect(taken()).toBe(expected);
});

async function run4th(source: string): Promise<string> {
    const { feed, taken } = await session();
    feed(preamble);
    taken();
    feed(`${source}\n`);
    return taken().trim();
}

async function run5th(source: string): Promise<string> {
    const channel = new SharedInputChannel();
    channel.push(new TextEncoder().encode(`${source}\n`));
    channel.close();
    let out = "";
    const exitCode = await runWasiCommand(wasm5th!, channel.sharedBuffer, (_fd, chunk) => { out += chunk; });
    expect(exitCode).toBe(0);
    return out.trim();
}

// The primitive wordset every jonesforth clone bootstraps before loading any
// `.f` preamble (DUP/EMIT/WORD/FIND/>CFA/DSP@/RSP@/...), so the same scripted
// one-liners run unchanged against both wasm ports.
const PRIMITIVE_CASES: [source: string, expected: string][] = [
    ["65 EMIT", "A"],
    ["777 65 EMIT", "A"],
    ["32 DUP + 1+ EMIT", "A"],
    ["16 DUP 2DUP + + + 1+ EMIT", "A"],
    ["8 DUP * 1+ EMIT", "A"],
    ["CHAR A EMIT", "A"],
    [": SLOW WORD FIND >CFA EXECUTE ; 65 SLOW EMIT", "A"],
    [
        `${new DataView(new TextEncoder().encode("65").buffer).getUint16(0, true)} DSP@ 2 NUMBER DROP EMIT`,
        "A",
    ],
    ["64 >R RSP@ 1 TELL RDROP", "@"],
    ["65 DSP@ RSP@ SWAP C@C! RSP@ 1 TELL", "A"],
    ["64 >R 1 RSP@ +! RSP@ 1 TELL", "A"],
];

describe("4th.wasm", () => {
    test.for(PRIMITIVE_CASES)("%s -> %s", async ([source, expected]) => {
        expect(await run4th(source)).toBe(expected);
    });
});

describe.skipIf(!wasm5th)("5th.wasm", () => {
    test.for(PRIMITIVE_CASES)("%s -> %s", async ([source, expected]) => {
        expect(await run5th(source)).toBe(expected);
    });

    // `DODOES` names the DOES> codeword only in 5th.c; 4th.rs and 6th.zig
    // implement DOES> differently and expose no such word, so this case
    // can't join PRIMITIVE_CASES above.
    test("<BUILDS/DOES>/CONST via the DODOES primitive", async () => {
        expect(await run5th(`
: <BUILDS WORD CREATE DODOES , 0 , ;
: DOES> R> LATEST @ >DFA ! ;
: CONST <BUILDS , DOES> @ ;

65 CONST FOO
FOO EMIT
`)).toBe("A");
    });
});
