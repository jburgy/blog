// Covers build/TinyBasic-wasi.wasm (see assembly/wasi.ts): a genuine WASI
// command drivable by forth/wasm/wasi-command.mjs's shared runWasiCommand, the
// same harness 4th-wasi.wasm/5th-wasi.wasm/6th-wasi.wasm use (see #128).
// Asserts on "Tiny Basic error #...at line ..." specifically because that
// message only reaches stdout through OutStr's embedded string table (see
// wasiHost.ts) -- the one piece of this build with no equivalent in
// lisp/wasm-test.mjs. A divide-by-zero (not "running off the end of a
// too-short program", this test's original trigger) is used on purpose: it's
// a genuine runtime error raised while a line number is still current, so
// "at line" is guaranteed -- running off the end instead sets Lino back to 0
// first (see core.ts's NX, case 0x1D), so that error never names a line.
// KeyInChar() never treats EOF as a stop, so runSession leaves stdin open.
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { expect, test } from "vitest";
import { runSession } from "../../forth/wasm/wasi-command.test-helper.mjs";

const wasm = await readFile(join(import.meta.dirname, "../build/TinyBasic-wasi.wasm"));

test("TinyBasic-wasi.wasm reports a runtime error with its line number", async () => {
    expect(await runSession(wasm, "10 PRINT 1/0", "RUN")).toMatch(/Tiny Basic error #\d+ at line \d+/);
});
