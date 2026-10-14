// Covers lisp/eliza.lisp as build/lisp-wasi.wasm's preamble: the whole file
// is one self-recursive expression (the same "bind a family of mutually-
// recursive helpers as sibling LAMBDA params, loop by self-application"
// trick lisp.lisp's own metacircular-evaluator bootstrap already uses --
// no core.ts changes needed), so it never returns control to main()'s own
// Read()/Eval() loop. Conversational turns are plain, unwrapped sentences
// fed straight to its own internal (READ) calls -- no quoting, no (ELIZA
// ...) call needed, see assets/index.html's lisp-wasi.wasm demo
// (data-preamble "lisp/eliza.lisp").
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { expect, test } from "vitest";
import { runSession } from "../../forth/wasm/wasi-command.test-helper.mjs";

const wasm = await readFile(join(import.meta.dirname, "../build/lisp-wasi.wasm"));
const preamble = await readFile(join(import.meta.dirname, "../eliza.lisp"), "utf8");

test("eliza.lisp holds a conversation", async () => {
    const out = await runSession(
        wasm,
        preamble,
        "(I AM FEELING SAD TODAY)",
        "(BECAUSE MY MOTHER NEVER LOVED ME)",
        "(I HAVE A ZEBRA IN MY GARAGE)",
        "(OK BYE)",
    );
    // Greeting, printed before the first (READ) -- no code dump, unlike a
    // naive preamble of separate top-level forms (each echoed by main()).
    expect(out).toMatch(/HELLO I AM ELIZA/);
    // Reflects "I AM" into "YOU ARE" before matching the (YOU ARE) rule.
    expect(out).toMatch(/PLEASE TELL ME WHY YOU THINK YOU ARE FEELING SAD TODAY/);
    // BECAUSE is a fixed-response keyword, independent of reflection.
    expect(out).toMatch(/IS THAT REALLY THE REASON/);
    // (YOU HAVE) rule, with the dynamic remainder appended after reflection.
    expect(out).toMatch(/HOW LONG HAVE YOU HAD A ZEBRA IN YOUR GARAGE/);
    // BYE's reply.
    expect(out).toMatch(/GOODBYE AND TAKE CARE/);
});
