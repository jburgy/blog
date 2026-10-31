// Entry point for the real-WASI build: pulls wasiHost.ts's getchar/putchar
// into the compiled module (asc's --use flag, see package.json, resolves
// core.ts's free getchar/putchar identifiers to these) and drives core.ts's
// main from a WASI command's `_start`.
import { getchar, putchar } from "./wasiHost";
import { main as run } from "./core";

// core.ts's hardcoded kQuote/kCond/... offsets only resolve correctly if the
// interned-symbol table "NIL\0T\0QUOTE\0..." already sits at 0x8000 before
// main() runs, and a WASI command has no host hook to put it there, so
// _start seeds it from this static copy.
const SEED: usize = memory.data<u8>([
  78, 73, 76, 0, 84, 0, 81, 85, 79, 84, 69, 0, 67, 79, 78, 68, 0, 82, 69, 65,
  68, 0, 80, 82, 73, 78, 84, 0, 65, 84, 79, 77, 0, 67, 65, 82, 0, 67, 68, 82,
  0, 67, 79, 78, 83, 0, 69, 81,
]);
const SEED_LEN: usize = 48;
const M: usize = 0x8000;

export function _start(): void {
  memory.grow(2); // page 0 for core.ts, page 1 for wasiHost.ts's own scratch
  memory.copy(M, SEED, SEED_LEN);
  run();
}
