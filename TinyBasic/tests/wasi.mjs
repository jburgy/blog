// Covers build/TinyBasic-wasi.wasm (see assembly/wasi.ts): a genuine WASI
// command drivable by forth/wasm/wasi-worker.js's shared runWasiCommand, the
// same harness 4th-wasi.wasm/5th-wasi.wasm/6th-wasi.wasm use (see #128).
// Asserts on "Tiny Basic error #...at line ..." specifically because that
// message only reaches stdout through OutStr's embedded string table (see
// wasiHost.ts) -- the one piece of this build with no equivalent in
// lisp/wasm-test.mjs. Runs the scripted session in a child process, killed
// once it has produced the expected output rather than awaited to
// completion -- see wasi-fixture.mjs for why.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const loader = pathToFileURL(join(import.meta.dirname, "../../forth/wasm/uwasi-cdn.loader.mjs")).href;
const registerLoader = `data:text/javascript,
    import { register } from "node:module";
    register(${JSON.stringify(loader)});
`;

const fixture = join(import.meta.dirname, "wasi-fixture.mjs");
const wasmPath = join(import.meta.dirname, "../build/TinyBasic-wasi.wasm");

const child = spawn(process.execPath, ["--import", registerLoader, fixture, wasmPath, "10 PRINT 1+2", "RUN"]);

let out = "";
let errOut = "";
await new Promise((resolve, reject) => {
    child.stdout.on("data", (chunk) => {
        out += chunk;
        if (out.includes("at line")) resolve();
    });
    child.stderr.on("data", (chunk) => { errOut += chunk; });
    child.once("error", reject);
    child.once("exit", (code) => reject(new Error(`fixture exited unexpectedly (code ${code}): ${out}${errOut}`)));
}).finally(() => child.kill("SIGKILL"));

assert.match(out, /Tiny Basic error #\d+ at line \d+/);
console.log("ok");
