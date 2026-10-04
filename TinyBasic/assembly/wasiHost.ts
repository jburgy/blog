// Real-WASI host I/O for wasi.ts's build, implementing the same
// ScreenChar/KeyInChar/OutStr shape core.ts expects (see its own comment) in
// terms of actual wasi_snapshot_preview1 fd_read/fd_write, so the compiled
// TinyBasic-wasi.wasm is a genuine WASI command drivable by
// forth/wasm/wasi-worker.js's `runWasiCommand` unchanged -- the same shared
// harness 4th-wasi.wasm/5th-wasi.wasm/6th-wasi.wasm already use (see #128).
type T = u16;

@external("wasi_snapshot_preview1", "fd_read")
declare function fd_read(fd: i32, iovs: usize, iovsLen: i32, nread: usize): i32;

@external("wasi_snapshot_preview1", "fd_write")
declare function fd_write(fd: i32, iovs: usize, iovsLen: i32, nwritten: usize): i32;

// core.ts's own addresses never leave CoreTop (0x0000-0xffff: T = u16), and
// the original host used to memory.grow(2) to get exactly that one page
// plus a spare second one. These scratch iovec/result bytes, and OutStr's
// string table below, live in that already-spare second page, so they can
// never collide with core.ts's own usage.
const IOVEC_PTR: usize = 0x10000;
const IOVEC_LEN: usize = 0x10004;
const CHAR_BUF: usize = 0x10008;
const NRESULT: usize = 0x1000c;

export function KeyInChar(): T {
  store<u32>(IOVEC_PTR, CHAR_BUF as u32);
  store<u32>(IOVEC_LEN, 1);
  if (fd_read(0, IOVEC_PTR, 1, NRESULT) != 0) return -1 as T; // WASI errno: treat as EOF
  if (load<u32>(NRESULT) == 0) return -1 as T; // EOF
  const c = load<u8>(CHAR_BUF);
  return c < 0x80 ? (c as T) : ((c - 0x100) as T);
}

export function ScreenChar(ch: T): void {
  store<u8>(CHAR_BUF, ((ch + 0x100) & 0xff) as u8);
  store<u32>(IOVEC_PTR, CHAR_BUF as u32);
  store<u32>(IOVEC_LEN, 1);
  fd_write(1, IOVEC_PTR, 1, NRESULT);
}

// Same 16 messages as TinyBasic.worker.js's `strings` table (OutStr's index
// argument indexes into it there too), each embedded as its own static data
// segment so a real WASI fd_write can emit it without any host-side lookup.
// AssemblyScript's `memory.data<T>()` builtin only accepts a literal array
// of numbers, not a string (tried `memory.data<u8>("...")` and
// `memory.data<u8>(String.UTF8.encode("..."))` directly -- both reject with
// "Array literal expected"), so each byte array carries its source string as
// a trailing comment instead, to keep it reviewable without hand-decoding
// ASCII codes.
const STR0: usize = memory.data<u8>([32, 91, 83, 116, 107, 32]); // " [Stk "
const STR1: usize = memory.data<u8>([32, 91, 69, 120, 112, 32]); // " [Exp "
const STR2: usize = memory.data<u8>([32, 32, 91, 86, 97, 114, 115]); // "  [Vars"
const STR3: usize = memory.data<u8>([69, 114, 114, 32]); // "Err "
const STR4: usize = memory.data<u8>([32, 32, 73, 76, 43]); // "  IL+"
const STR5: usize = memory.data<u8>([42, 42, 42, 32, 65, 99, 116, 105, 118, 105, 116, 121, 32, 76, 111, 103, 32, 64, 32]); // "*** Activity Log @ "
const STR6: usize = memory.data<u8>([84, 105, 110, 121, 32, 66, 97, 115, 105, 99, 32, 101, 114, 114, 111, 114, 32, 35]); // "Tiny Basic error #"
const STR7: usize = memory.data<u8>([32, 97, 116, 32, 108, 105, 110, 101, 32]); // " at line "
const STR8: usize = memory.data<u8>([32, 91, 66, 80, 61]); // " [BP="
const STR9: usize = memory.data<u8>([44, 32, 84, 66, 64]); // ", TB@"
const STR10: usize = memory.data<u8>([44, 32, 73, 76, 64]); // ", IL@"
const STR11: usize = memory.data<u8>([42, 42, 42, 32, 85, 115, 101, 114, 32, 66, 114, 101, 97, 107, 32, 42, 42, 42]); // "*** User Break ***"
const STR12: usize = memory.data<u8>([91, 73, 76, 61]); // "[IL="
const STR13: usize = memory.data<u8>([42, 42, 42, 32, 87, 97, 116, 99, 104, 101, 100, 32]); // "*** Watched "
const STR14: usize = memory.data<u8>([91, 73, 76, 43]); // "[IL+"
const STR15: usize = memory.data<u8>([91, 42, 42, 32, 87, 97, 116, 99, 104, 32]); // "[** Watch "

export function OutStr(theMsg: u8): void {
  let ptr: usize, length: u32;
  // A switch over named per-string consts, not an index into a packed
  // offset/length byte table (the previous shape here): theMsg is always a
  // small, compile-time-trusted index from core.ts itself (the same
  // contract OutStr's original custom host import already relied on), so
  // this needs no bounds check, and each case still reads as "index N is
  // this string" without cross-referencing a separate comment.
  switch (theMsg) {
    case 0: ptr = STR0; length = 6; break;
    case 1: ptr = STR1; length = 6; break;
    case 2: ptr = STR2; length = 7; break;
    case 3: ptr = STR3; length = 4; break;
    case 4: ptr = STR4; length = 5; break;
    case 5: ptr = STR5; length = 19; break;
    case 6: ptr = STR6; length = 18; break;
    case 7: ptr = STR7; length = 9; break;
    case 8: ptr = STR8; length = 5; break;
    case 9: ptr = STR9; length = 5; break;
    case 10: ptr = STR10; length = 5; break;
    case 11: ptr = STR11; length = 18; break;
    case 12: ptr = STR12; length = 4; break;
    case 13: ptr = STR13; length = 12; break;
    case 14: ptr = STR14; length = 4; break;
    case 15: ptr = STR15; length = 10; break;
    default: return;
  }
  store<u32>(IOVEC_PTR, ptr as u32);
  store<u32>(IOVEC_LEN, length);
  fd_write(1, IOVEC_PTR, 1, NRESULT);
}
