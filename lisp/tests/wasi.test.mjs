// Covers build/lisp-wasi.wasm (see assembly/wasi.ts): a genuine WASI command
// drivable by forth/wasm/wasi-command.mjs's shared runWasiCommand, the same
// harness 4th-wasi.wasm/5th-wasi.wasm/6th-wasi.wasm use (see #128). Its
// getchar() never treats EOF as a stop (see wasiHost.ts: a closed, exhausted
// channel wraps to 255, which core.ts's GetToken loop reads as "still inside
// a token" forever), so runSession leaves stdin open -- see its own comment.
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { expect, test } from "vitest";
import { runSession } from "../../forth/wasm/wasi-command.test-helper.mjs";

const wasm = await readFile(join(import.meta.dirname, "../build/lisp-wasi.wasm"));

test("lisp-wasi.wasm evaluates (QUOTE (A B))", async () => {
    expect(await runSession(wasm, "(QUOTE (A B))")).toMatch(/\(A B\)/);
});
