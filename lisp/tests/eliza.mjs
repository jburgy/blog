// Covers lisp/eliza.lisp as build/lisp-wasi.wasm's preamble: the whole file
// is one self-recursive expression (the same "bind a family of mutually-
// recursive helpers as sibling LAMBDA params, loop by self-application"
// trick lisp.lisp's own metacircular-evaluator bootstrap already uses --
// no core.ts changes needed), so it never returns control to main()'s own
// Read()/Eval() loop. Conversational turns are plain, unwrapped sentences
// fed straight to its own internal (READ) calls -- no quoting, no (ELIZA
// ...) call needed, see assets/index.html's lisp-wasi.wasm demo
// (data-preamble "lisp/eliza.lisp"). Runs the scripted session in a child
// process, killed once it has produced the expected output rather than
// awaited to completion -- see wasi-fixture.mjs for why.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const loader = pathToFileURL(join(import.meta.dirname, "../../forth/wasm/uwasi-cdn.loader.mjs")).href;
const registerLoader = `data:text/javascript,
    import { register } from "node:module";
    register(${JSON.stringify(loader)});
`;

const fixture = join(import.meta.dirname, "wasi-fixture.mjs");
const wasmPath = join(import.meta.dirname, "../build/lisp-wasi.wasm");
const elizaPath = join(import.meta.dirname, "../eliza.lisp");

const preamble = await readFile(elizaPath, "utf8");
const turns = [
    "(I AM FEELING SAD TODAY)",
    "(BECAUSE MY MOTHER NEVER LOVED ME)",
    "(I HAVE A ZEBRA IN MY GARAGE)",
    "(OK BYE)",
];

const child = spawn(process.execPath, ["--experimental-wasm-jspi", "--import", registerLoader, fixture, wasmPath, preamble, ...turns]);

let out = "";
let errOut = "";
await new Promise((resolve, reject) => {
    child.stdout.on("data", (chunk) => {
        out += chunk;
        if (out.includes("GOODBYE AND TAKE CARE")) resolve();
    });
    child.stderr.on("data", (chunk) => { errOut += chunk; });
    child.once("error", reject);
    child.once("exit", (code) => reject(new Error(`fixture exited unexpectedly (code ${code}): ${out}${errOut}`)));
}).finally(() => child.kill("SIGKILL"));

// Greeting, printed before the first (READ) -- no code dump, unlike a
// naive preamble of separate top-level forms (each echoed by main()).
assert.match(out, /HELLO I AM ELIZA/);
// Reflects "I AM" into "YOU ARE" before matching the (YOU ARE) rule.
assert.match(out, /PLEASE TELL ME WHY YOU THINK YOU ARE FEELING SAD TODAY/);
// BECAUSE is a fixed-response keyword, independent of reflection.
assert.match(out, /IS THAT REALLY THE REASON/);
// (YOU HAVE) rule, with the dynamic remainder appended after reflection.
assert.match(out, /HOW LONG HAVE YOU HAD A ZEBRA IN YOUR GARAGE/);
// BYE's reply.
assert.match(out, /GOODBYE AND TAKE CARE/);
console.log("ok");
