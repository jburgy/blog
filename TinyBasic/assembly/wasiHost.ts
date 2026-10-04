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
// argument indexes into it there too), concatenated and embedded as static
// data so a real WASI fd_write can emit them without any host-side lookup.
const STRINGS: usize = memory.data<u8>([
  32, 91, 83, 116, 107, 32, 32, 91, 69, 120, 112, 32, 32, 32, 91, 86, 97, 114,
  115, 69, 114, 114, 32, 32, 32, 73, 76, 43, 42, 42, 42, 32, 65, 99, 116, 105,
  118, 105, 116, 121, 32, 76, 111, 103, 32, 64, 32, 84, 105, 110, 121, 32, 66,
  97, 115, 105, 99, 32, 101, 114, 114, 111, 114, 32, 35, 32, 97, 116, 32, 108,
  105, 110, 101, 32, 32, 91, 66, 80, 61, 44, 32, 84, 66, 64, 44, 32, 73, 76,
  64, 42, 42, 42, 32, 85, 115, 101, 114, 32, 66, 114, 101, 97, 107, 32, 42,
  42, 42, 91, 73, 76, 61, 42, 42, 42, 32, 87, 97, 116, 99, 104, 101, 100, 32,
  91, 73, 76, 43, 91, 42, 42, 32, 87, 97, 116, 99, 104, 32,
]);
const STRING_OFFSETS: usize = memory.data<u16>([0, 6, 12, 19, 23, 28, 47, 65, 74, 79, 84, 89, 107, 111, 123, 127]);
const STRING_LENGTHS: usize = memory.data<u8>([6, 6, 7, 4, 5, 19, 18, 9, 5, 5, 5, 18, 4, 12, 4, 10]);

export function OutStr(theMsg: u8): void {
  // Raw, unchecked loads (no StaticArray/Array indexing, which would pull in
  // an "env.abort" bounds-check import this build has no host for): theMsg
  // is always a small, compile-time-trusted index from core.ts itself, the
  // same contract OutStr's original custom host import already relied on.
  const offset = load<u16>(STRING_OFFSETS + (theMsg as usize) * 2);
  const length = load<u8>(STRING_LENGTHS + theMsg);
  store<u32>(IOVEC_PTR, (STRINGS + offset) as u32);
  store<u32>(IOVEC_LEN, length);
  fd_write(1, IOVEC_PTR, 1, NRESULT);
}
