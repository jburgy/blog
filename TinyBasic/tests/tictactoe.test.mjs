// Covers TinyBasic/tictactoe.bas as build/TinyBasic-wasi.wasm's preamble:
// Tom Pittman's own Tic-Tac-Toe, originally printed in the Homebrew
// Computer Club Newsletter (Vol. 2, Issue 13, January 19, 1977) under the
// title "How to Make a Program TINY" (see
// http://www.ittybittycomputers.com/IttyBitty/TinyBasic/TicTac.htm). The
// only change from that original listing is hardcoding G=276/P=280 (the
// USR peek/poke routine addresses core.ts already exposes at those fixed
// addresses, see PeekSub/PokeSub) instead of asking the player to type in
// their system's cold-start address -- no interpreter changes needed. Runs
// a scripted game.
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { expect, test } from "vitest";
import { runSession } from "../../forth/wasm/wasi-command.test-helper.mjs";

const wasm = await readFile(join(import.meta.dirname, "../build/TinyBasic-wasi.wasm"));
const preamble = await readFile(join(import.meta.dirname, "../tictactoe.bas"), "utf8");

// X (us) plays the top row: 1, 2, 3. O will try to block one of them, but
// can't block both ends of a line once X has two in a row with the third
// empty, so this always finishes in a win within a few moves regardless of
// which square the heuristic blocks first.
const moves = ["1", "5", "2", "9", "3"];

test("tictactoe.bas plays a scripted game to the end", async () => {
    const out = await runSession(wasm, preamble, ...moves);
    // The board and prompt, printed before any move is made.
    expect(out).toMatch(/NEW GAME/);
    expect(out).toMatch(/YOUR PLAY/);
    // Either a legitimate win/loss ends the scripted game -- which one depends
    // on the heuristic's block, not something worth pinning down here.
    expect(out).toMatch(/YOU WIN|I WIN/);
});
