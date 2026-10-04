// Entry point for the real-WASI build: pulls wasiHost.ts's ScreenChar/
// KeyInChar/OutStr into the compiled module (asc's --use flag, see
// package.json, resolves core.ts's free identifiers of the same names to
// these) and drives core.ts's Interp from a WASI command's `_start`. See
// index.ts for the original (custom host import) counterpart built from the
// same core.ts.
import { ScreenChar, KeyInChar, OutStr } from "./wasiHost";
import { ColdGo, ILfront, Poke2, ColdStart, Interp } from "./core";

type T = u16;

// The original build relies on its host (TinyBasic.worker.js) to write the
// Tiny BASIC IL program's own bytecode into core memory before calling
// ColdStart/Interp -- see that file's `interpreter` array of hex listings. A
// WASI command owns its own startup (no host hook between instantiation and
// `Interp()`), so _start writes it itself from this static copy of the exact
// same bytes (same parse as the worker's own `interpreter.map(...)`, done
// once ahead of time rather than at every load).
const IL_CODE: usize = memory.data<u8>([
  36, 58, 145, 39, 16, 225, 89, 197, 42, 86, 16, 17, 44, 139, 76, 69, 212,
  160, 128, 189, 48, 188, 224, 19, 29, 148, 71, 207, 136, 84, 207, 48, 188,
  224, 16, 17, 22, 128, 83, 85, 194, 48, 188, 224, 20, 22, 144, 80, 210, 131,
  73, 78, 212, 229, 113, 136, 187, 225, 29, 143, 162, 33, 88, 111, 131, 172,
  34, 85, 131, 186, 36, 147, 224, 35, 29, 48, 188, 32, 72, 145, 73, 198, 48,
  188, 49, 52, 48, 188, 132, 84, 72, 69, 206, 28, 29, 56, 13, 154, 73, 78,
  80, 85, 212, 160, 16, 231, 36, 63, 32, 145, 39, 225, 89, 129, 172, 48, 188,
  19, 17, 130, 172, 77, 224, 29, 137, 82, 69, 84, 85, 82, 206, 224, 21, 29,
  133, 69, 78, 196, 224, 45, 152, 76, 73, 83, 212, 236, 36, 0, 0, 0, 0, 10,
  128, 31, 36, 147, 35, 29, 48, 188, 225, 80, 128, 172, 89, 133, 82, 85, 206,
  56, 10, 134, 67, 76, 69, 65, 210, 43, 132, 82, 69, 205, 29, 160, 128, 189,
  56, 20, 133, 173, 48, 211, 23, 100, 129, 171, 48, 211, 133, 171, 48, 211,
  24, 90, 133, 173, 48, 211, 25, 84, 47, 48, 226, 133, 170, 48, 226, 26, 90,
  133, 175, 48, 226, 27, 84, 47, 151, 82, 78, 196, 10, 128, 128, 18, 10, 9,
  41, 26, 10, 26, 133, 24, 19, 9, 128, 18, 11, 49, 48, 97, 115, 11, 2, 4, 2,
  3, 5, 3, 27, 26, 25, 11, 9, 6, 10, 0, 0, 28, 23, 47, 143, 85, 83, 210, 128,
  168, 48, 188, 49, 42, 49, 42, 128, 169, 46, 47, 162, 18, 47, 193, 47, 128,
  168, 48, 188, 128, 169, 47, 131, 172, 56, 188, 11, 47, 128, 168, 82, 47,
  132, 189, 9, 2, 47, 142, 188, 132, 189, 9, 3, 47, 132, 190, 9, 5, 47, 9, 1,
  47, 128, 190, 132, 189, 9, 6, 47, 132, 188, 9, 5, 47, 9, 4, 47,
]);
const IL_CODE_LEN: usize = 343;

export function _start(): void {
  memory.grow(2); // page 0 for core.ts (same spare it used to get), page 1 for wasiHost.ts's own scratch
  const ilStart: T = (ILfront + 2) as T;
  Poke2(ILfront, ilStart);
  Poke2(ColdGo + 1, ilStart);
  memory.copy(ilStart, IL_CODE, IL_CODE_LEN);
  store<u8>(ilStart + IL_CODE_LEN, 0);
  ColdStart((ilStart + IL_CODE_LEN + 1) as T);
  Interp();
}
