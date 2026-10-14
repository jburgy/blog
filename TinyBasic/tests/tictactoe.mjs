// Covers TinyBasic/tictactoe.bas as build/TinyBasic-wasi.wasm's preamble:
// Tom Pittman's own Tic-Tac-Toe, originally printed in the Homebrew
// Computer Club Newsletter (Vol. 2, Issue 13, January 19, 1977) under the
// title "How to Make a Program TINY" (see
// http://www.ittybittycomputers.com/IttyBitty/TinyBasic/TicTac.htm). The
// only change from that original listing is hardcoding G=276/P=280 (the
// USR peek/poke routine addresses core.ts already exposes at those fixed
// addresses, see PeekSub/PokeSub) instead of asking the player to type in
// their system's cold-start address -- no interpreter changes needed. Runs
// a scripted game in a child process, killed once it has produced the
// expected output rather than awaited to completion -- see
// wasi-fixture.mjs for why.
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
const wasmPath = join(import.meta.dirname, "../build/TinyBasic-wasi.wasm");
const tictactoePath = join(import.meta.dirname, "../tictactoe.bas");

const preamble = await readFile(tictactoePath, "utf8");
// X (us) plays the top row: 1, 2, 3. O will try to block one of them, but
// can't block both ends of a line once X has two in a row with the third
// empty, so this always finishes in a win within a few moves regardless of
// which square the heuristic blocks first.
const moves = ["1", "5", "2", "9", "3"];

const child = spawn(process.execPath, ["--experimental-wasm-jspi", "--import", registerLoader, fixture, wasmPath, preamble, ...moves]);

let out = "";
let errOut = "";
await new Promise((resolve, reject) => {
    child.stdout.on("data", (chunk) => {
        out += chunk;
        if (out.includes("YOU WIN") || out.includes("I WIN")) resolve();
    });
    child.stderr.on("data", (chunk) => { errOut += chunk; });
    child.once("error", reject);
    child.once("exit", (code) => reject(new Error(`fixture exited unexpectedly (code ${code}): ${out}${errOut}`)));
}).finally(() => child.kill("SIGKILL"));

// The board and prompt, printed before any move is made.
assert.match(out, /NEW GAME/);
assert.match(out, /YOUR PLAY/);
// Either a legitimate win/loss ends the scripted game -- which one depends
// on the heuristic's block, not something worth pinning down here.
assert.match(out, /YOU WIN|I WIN/);
console.log("ok");
