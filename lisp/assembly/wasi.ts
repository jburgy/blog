// Entry point for the real-WASI build: pulls wasiHost.ts's getchar/putchar
// into the compiled module (asc's --use flag, see package.json, resolves
// core.ts's free getchar/putchar identifiers to these) and drives core.ts's
// main from a WASI command's `_start`. See index.ts for the original
// (custom host import) counterpart built from the same core.ts.
import { getchar, putchar } from "./wasiHost";
import { main as run } from "./core";

// The original build relies on its host (lisp.worker.js) to pre-seed the
// interned-symbol table at 0x8000 before calling main() -- the hardcoded
// kQuote/kCond/... offsets in core.ts only resolve correctly if "NIL\0T\0
// QUOTE\0..." already sits there. A WASI command owns its own startup (no
// host hook between instantiation and `run()`), so _start seeds it itself
// from this static copy of the exact same string.
const SEED: usize = memory.data<u8>([
  78, 73, 76, 0, 84, 0, 81, 85, 79, 84, 69, 0, 67, 79, 78, 68, 0, 82, 69, 65,
  68, 0, 80, 82, 73, 78, 84, 0, 65, 84, 79, 77, 0, 67, 65, 82, 0, 67, 68, 82,
  0, 67, 79, 78, 83, 0, 69, 81,
]);
const SEED_LEN: usize = 48;
const M: usize = 0x8000;

export function _start(): void {
  memory.grow(2); // page 0 for core.ts (same 1 page index.ts's host grows), page 1 for wasiHost.ts's own scratch
  memory.copy(M, SEED, SEED_LEN);
  run();
}
