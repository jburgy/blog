// Covers lisp/assembly/core.wast: core.ts's interpreter hand-written in WAT
// for brevity (shallow binding, raw-address cells).  Same conformance test as
// lisp.f's: eliza.lisp has to behave exactly like build/lisp-wasi.wasm.
import { execFile } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";
import { afterAll, beforeAll, expect, test } from "vitest";
import { runSession } from "../../forth/wasm/wasi-command.test-helper.mjs";

const execFileAsync = promisify(execFile);
const here = import.meta.dirname;
const read = (...path) => readFile(join(here, ...path));

let dir;
let wasm;

beforeAll(async () => {
    dir = await mkdtemp(join(tmpdir(), "lisp-wast-"));
    const out = join(dir, "core.wasm");
    // wabt isn't an installed dependency; fetch it on demand.
    await execFileAsync("npx", ["-y", "--package", "wabt", "wat2wasm", "--enable-tail-call", "-o", out, join(here, "../assembly/core.wast")]);
    wasm = await readFile(out);
}, 120_000);
afterAll(() => rm(dir, { recursive: true, force: true }));

test("evaluates and prints", async () => {
    const out = await runSession(
        wasm,
        "(CONS (QUOTE A) (QUOTE (B C)))",
        "((LAMBDA (X) ((LAMBDA (X Y) (CONS X (CONS Y NIL))) (QUOTE 1) X)) (QUOTE Z))",
        "(COND ((EQ (QUOTE A) (QUOTE B)) (QUOTE X)) ((QUOTE T) (QUOTE Y)))",
    );
    expect(out).toBe("* (A B C)\n* (1 Z)\n* Y\n* ");
});

test("eliza.lisp matches the AssemblyScript build", async () => {
    const eliza = await read("../eliza.lisp");
    const conversation = [
        "(I AM FEELING SAD TODAY)",
        "(BECAUSE MY MOTHER NEVER LOVED ME)",
        "(I HAVE A ZEBRA IN MY GARAGE)",
        "(OK BYE)",
    ];
    const reference = await runSession(await read("../build/lisp-wasi.wasm"), eliza, ...conversation);
    const out = await runSession(wasm, eliza, ...conversation);
    expect(out).toBe(reference);
    expect(out).toContain("(GOODBYE AND TAKE CARE)");
});
