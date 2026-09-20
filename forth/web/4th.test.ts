// No browser: the demo's wasm, WASI layer and re-entrant eval loop are all
// plain JavaScript, so vitest and uwasi cover them in node. Needs `make web`.
import { readFile } from "node:fs/promises";
import { expect, test } from "vitest";
import { start } from "./4th.js";

const wasm = await readFile(new URL("4th.wasm", import.meta.url));
const preamble = await readFile(new URL("../4th.32.fs", import.meta.url), "utf8");

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
