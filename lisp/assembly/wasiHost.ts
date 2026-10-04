// Real-WASI host I/O for wasi.ts's build, implementing the same getchar()/
// putchar() shape core.ts expects (see its own comment) in terms of actual
// wasi_snapshot_preview1 fd_read/fd_write, so the compiled lisp-wasi.wasm is
// a genuine WASI command drivable by forth/wasm/wasi-worker.js's
// `runWasiCommand` unchanged -- the same shared harness 4th-wasi.wasm/
// 5th-wasi.wasm/6th-wasi.wasm already use (see #128).
@external("wasi_snapshot_preview1", "fd_read")
declare function fd_read(fd: i32, iovs: usize, iovsLen: i32, nread: usize): i32;

@external("wasi_snapshot_preview1", "fd_write")
declare function fd_write(fd: i32, iovs: usize, iovsLen: i32, nwritten: usize): i32;

// core.ts's own addresses never leave page 0 (0x0000-0xffff: cons cells grow
// down from M = 0x8000, interned strings grow up from it, and the compiled
// module declares 0 initial pages, so index.ts's host used to memory.grow(1)
// to get exactly that one page). These scratch iovec/result bytes instead
// live in a *second* page, so they can never collide with either.
const IOVEC_PTR: usize = 0x10000;
const IOVEC_LEN: usize = 0x10004;
const CHAR_BUF: usize = 0x10008;
const NRESULT: usize = 0x1000c;

export function getchar(): i32 {
  store<u32>(IOVEC_PTR, CHAR_BUF as u32);
  store<u32>(IOVEC_LEN, 1);
  if (fd_read(0, IOVEC_PTR, 1, NRESULT) != 0) return -1; // WASI errno: treat as EOF
  if (load<u32>(NRESULT) == 0) return -1; // EOF
  return load<u8>(CHAR_BUF);
}

export function putchar(c: i32): void {
  store<u8>(CHAR_BUF, c as u8);
  store<u32>(IOVEC_PTR, CHAR_BUF as u32);
  store<u32>(IOVEC_LEN, 1);
  fd_write(1, IOVEC_PTR, 1, NRESULT);
}
