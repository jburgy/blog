//! A Forth interpreter in Rust, using `become` for tail‑call elimination.
//! Requires nightly Rust and `#![feature(explicit_tail_calls)]`.
//!
//! Build/test: `rustup run nightly rustc --edition 2024 --test -o /tmp/4th 4th.rs`

#![feature(explicit_tail_calls)]
#![allow(incomplete_features)]
// `become f()` where `f` returns `!` trips the unreachable-code lint on every primitive.
#![allow(unreachable_code)]

use std::fs::{File, OpenOptions};
use std::io::{self, BufRead, Read, Write};
#[cfg(not(feature = "web"))]
use std::panic::{self, AssertUnwindSafe};

/// Forth cell type. Zig's `6th` uses `isize`; here a cell is 32 bits and every
/// "address" is a byte offset into `Interp::memory`.
type Cell = i32;

/// Size of a cell in bytes.
const CELL: usize = std::mem::size_of::<Cell>();

/// Panic payload used to unwind out of the threaded code: primitives return `!`,
/// so there is no ordinary return path back into Rust.
#[cfg(not(feature = "web"))]
struct Halt;

/// The numbers `jonesforth.f` names. Keeping Linux's values means the Forth
/// source needs no edits; the bodies below are ordinary Rust I/O, which on
/// `wasm32-wasip1` bottoms out in WASI.
mod sys {
    use super::Cell;

    pub const EXIT: Cell = 1;
    pub const READ: Cell = 3;
    pub const WRITE: Cell = 4;
    pub const OPEN: Cell = 5;
    pub const CLOSE: Cell = 6;
    pub const BRK: Cell = 45;

    pub const O_WRONLY: Cell = 1;
    pub const O_RDWR: Cell = 2;
    pub const O_ACCMODE: Cell = 3;
    pub const O_CREAT: Cell = 0o100;
    pub const O_TRUNC: Cell = 0o1000;
    pub const O_APPEND: Cell = 0o2000;

    pub const EBADF: Cell = 9;
    pub const EIO: Cell = 5;
    pub const ENOSYS: Cell = 38;
}

/// Lowest descriptor `SYS_OPEN` will hand out; 0..3 stay with the reader/writer.
const FD_BASE: usize = 3;

// Dictionary entry layout: link cell, flag byte, name bytes, code field.
const W_FLAG: usize = CELL;
const W_NAME: usize = CELL + 1;
// Flag byte: name length in the low 5 bits, plus these.
const F_LENMASK: u8 = 0x1f;
const F_HIDDEN: u8 = 0x20;
const F_IMMED: u8 = 0x80;

/// Layout of `Interp::memory`. Both stacks grow downwards from their `*_TOP`.
mod header {
    use super::CELL;

    pub const STACK: usize = 0; // data stack, 2048 cells
    pub const STACK_TOP: usize = STACK + 2048 * CELL;
    pub const RETURN_STACK: usize = STACK_TOP; // return stack, 2048 cells
    pub const RETURN_STACK_TOP: usize = RETURN_STACK + 2048 * CELL;

    // Interpreter variables, one cell each.
    pub const STATE: usize = RETURN_STACK_TOP; // 0 = interpret, 1 = compile
    pub const HERE: usize = STATE + CELL; // next free dictionary address
    pub const LATEST: usize = HERE + CELL; // most recent dictionary entry
    pub const S0: usize = LATEST + CELL; // base of the data stack
    pub const R0: usize = S0 + CELL; // base of the return stack
    pub const SP: usize = R0 + CELL; // data stack pointer, saved on halt
    pub const RSP: usize = SP + CELL; // return stack pointer, saved on halt
    pub const BASE: usize = RSP + CELL; // numeric base
    pub const ARGC: usize = BASE + CELL; // argv count, for `(ARGC)`

    pub const BUFFER: usize = ARGC + CELL; // WORD buffer
    pub const BUFFER_LEN: usize = 32;
    pub const SCRATCH: usize = BUFFER + BUFFER_LEN; // cold start / hand-assembled code
    pub const SCRATCH_LEN: usize = 64 * CELL;
    pub const DICTIONARY: usize = SCRATCH + SCRATCH_LEN; // first dictionary entry
}

/// The interpreter state: memory, input reader, output writer.
pub struct Interp {
    memory: Vec<u8>,
    reader: Box<dyn BufRead>,
    writer: Box<dyn Write>,
    /// Descriptors handed out by `SYS_OPEN`, offset by `FD_BASE`.
    files: Vec<Option<File>>,
}

/// Primitive function signature: exactly what the dispatcher tail‑calls.
/// All primitives must have this signature and **never return** – they end
/// with `become self.next(...)`.
type PrimitiveFn = fn(&mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> !;

/// Keep `Halt` from printing a panic message; a halted interpreter is not a crash.
#[cfg(not(feature = "web"))]
fn install_halt_hook() {
    use std::sync::Once;
    static ONCE: Once = Once::new();
    ONCE.call_once(|| {
        let default = panic::take_hook();
        panic::set_hook(Box::new(move |info| {
            if info.payload().downcast_ref::<Halt>().is_none() {
                default(info);
            }
        }));
    });
}

impl Interp {
    /// Create a new interpreter with a pre‑allocated memory array.
    fn new(reader: Box<dyn BufRead>, writer: Box<dyn Write>) -> Self {
        #[cfg(not(feature = "web"))]
        install_halt_hook();
        let mut memory = vec![0u8; 1 << 20];
        Self::write_cell_at(&mut memory, header::STATE, 0); // interpret mode
        Self::write_cell_at(&mut memory, header::HERE, header::DICTIONARY as Cell);
        Self::write_cell_at(&mut memory, header::LATEST, 0); // no words yet
        Self::write_cell_at(&mut memory, header::S0, header::STACK_TOP as Cell);
        Self::write_cell_at(&mut memory, header::R0, header::RETURN_STACK_TOP as Cell);
        Self::write_cell_at(&mut memory, header::SP, header::STACK_TOP as Cell);
        Self::write_cell_at(&mut memory, header::RSP, header::RETURN_STACK_TOP as Cell);
        Self::write_cell_at(&mut memory, header::BASE, 10); // decimal
        Self::write_cell_at(&mut memory, header::ARGC, std::env::args().count() as Cell);

        let mut interp = Interp {
            memory,
            reader,
            writer,
            files: Vec::new(),
        };
        // Build the initial dictionary of built‑in words.
        interp.initialize_dictionary();
        interp
    }

    /// Read a 32‑bit little‑endian cell from `addr`.
    #[inline]
    fn read_cell(&self, addr: usize) -> Cell {
        let bytes = &self.memory[addr..addr + 4];
        i32::from_le_bytes(bytes.try_into().unwrap())
    }

    /// Write a 32‑bit little‑endian cell to `addr`.
    #[inline]
    fn write_cell(&mut self, addr: usize, val: Cell) {
        let bytes = val.to_le_bytes();
        self.memory[addr..addr + 4].copy_from_slice(&bytes);
    }

    /// Helper for initialisation (works on a raw `Vec<u8>`).
    #[inline]
    fn write_cell_at(mem: &mut [u8], addr: usize, val: Cell) {
        let bytes = val.to_le_bytes();
        mem[addr..addr + 4].copy_from_slice(&bytes);
    }

    /// Return a slice of memory at `addr` of length `len`.
    #[inline]
    fn slice(&self, addr: usize, len: usize) -> &[u8] {
        &self.memory[addr..addr + len]
    }

    /// Read one byte from the input stream, or `None` at end of input.
    fn key(&mut self) -> Option<u8> {
        let mut buf = [0u8; 1];
        match self.reader.read_exact(&mut buf) {
            Ok(()) => Some(buf[0]),
            Err(e) if e.kind() == io::ErrorKind::UnexpectedEof => None,
            Err(e) => panic!("input error: {e}"),
        }
    }

    /// Read a whitespace‑delimited word into `BUFFER`, skipping `\` comments,
    /// and return its length. `None` at end of input.
    fn word(&mut self) -> Option<usize> {
        let mut i = 0;
        let mut ch = 0u8; // sentinel: always read at least one character
        while ch <= b' ' {
            ch = self.key()?;
            if ch == b'\\' {
                while ch != b'\n' {
                    ch = self.key()?;
                }
            }
        }
        while ch > b' ' {
            if i < header::BUFFER_LEN {
                self.memory[header::BUFFER + i] = ch;
                i += 1;
            }
            match self.key() {
                Some(c) => ch = c,
                None => break, // last word of the input needs no delimiter
            }
        }
        Some(i)
    }

    /// Numeric base, clamped to what `from_str_radix`/`from_digit` accept.
    fn base(&self) -> u32 {
        self.read_cell(header::BASE).clamp(2, 36) as u32
    }

    /// Search the dictionary for a visible word with the given name.
    /// Returns the address of its header, or 0 if there is no such word.
    fn find(&self, name: &[u8]) -> usize {
        let mut node = self.read_cell(header::LATEST) as usize;
        while node != 0 {
            // Word layout: link (4), flag (1), name (<= 31), code (4)
            let flag = self.memory[node + W_FLAG];
            let len = (flag & F_LENMASK) as usize;
            if flag & F_HIDDEN == 0
                && len == name.len()
                && self.memory[node + W_NAME..node + W_NAME + len] == *name
            {
                return node;
            }
            node = self.read_cell(node) as usize; // follow link
        }
        0
    }

    /// Code field address of the dictionary entry at `node`.
    fn to_cfa(&self, node: usize) -> usize {
        node + W_NAME + (self.memory[node + W_FLAG] & F_LENMASK) as usize
    }

    /// Append a dictionary header for the `len` name bytes at `addr`, leaving
    /// `HERE` pointing at the (not yet written) code field.
    fn create_header(&mut self, addr: usize, len: usize) {
        assert!(len <= F_LENMASK as usize, "name too long");
        let here = self.read_cell(header::HERE) as usize;
        // Word header: link (4), flag+len (1), name bytes
        let link = self.read_cell(header::LATEST);
        self.write_cell(here, link);
        self.memory[here + W_FLAG] = len as u8;
        self.memory.copy_within(addr..addr + len, here + W_NAME);
        self.write_cell(header::LATEST, here as Cell);
        self.write_cell(header::HERE, (here + W_NAME + len) as Cell);
    }

    /// Append one cell at `HERE` (the `,` of the Forth dictionary).
    fn comma(&mut self, val: Cell) {
        let here = self.read_cell(header::HERE) as usize;
        self.write_cell(here, val);
        self.write_cell(header::HERE, (here + CELL) as Cell);
    }

    /// Append a word header + code field to the dictionary.
    fn add_word(&mut self, name: &[u8], code: Cell) {
        self.memory[header::BUFFER..header::BUFFER + name.len()].copy_from_slice(name);
        self.create_header(header::BUFFER, name.len());
        self.comma(code);
    }

    /// Append a word that pushes `value` (jonesforth's `defconst`/`defvar`).
    fn add_const(&mut self, name: &[u8], value: Cell) {
        self.add_word(name, PrimitiveIndex::DoConst as Cell);
        self.comma(value);
    }

    /// Append a colon definition whose body is a list of code field addresses.
    fn add_colon(&mut self, name: &[u8], immediate: bool, body: &[Cell]) {
        self.add_word(name, PrimitiveIndex::DoCol as Cell);
        for &cell in body {
            self.comma(cell);
        }
        if immediate {
            let latest = self.read_cell(header::LATEST) as usize;
            self.memory[latest + W_FLAG] |= F_IMMED;
        }
    }

    /// Build the initial dictionary.
    fn initialize_dictionary(&mut self) {
        use PrimitiveIndex as P;
        let words: &[(&[u8], Cell)] = &[
            (b"EXIT", P::Exit as Cell),
            (b"LIT", P::Lit as Cell),
            (b"BRANCH", P::Branch as Cell),
            (b"0BRANCH", P::ZeroBranch as Cell),
            (b"LITSTRING", P::LitString as Cell),
            (b"TELL", P::Tell as Cell),
            (b"KEY", P::Key as Cell),
            (b"EMIT", P::Emit as Cell),
            (b"WORD", P::Word as Cell),
            (b"NUMBER", P::Number as Cell),
            (b"FIND", P::Find as Cell),
            (b">CFA", P::ToCfa as Cell),
            (b"CREATE", P::Create as Cell),
            (b",", P::Comma as Cell),
            (b"[", P::LBracket as Cell),
            (b"]", P::RBracket as Cell),
            (b"IMMEDIATE", P::Immediate as Cell),
            (b"HIDDEN", P::Hidden as Cell),
            (b"'", P::Tick as Cell),
            (b">R", P::ToR as Cell),
            (b"R>", P::FromR as Cell),
            (b"R@", P::RFetch as Cell),
            (b"RSP@", P::RspFetch as Cell),
            (b"RSP!", P::RspStore as Cell),
            (b"RDROP", P::RDrop as Cell),
            (b"DSP@", P::DspFetch as Cell),
            (b"DSP!", P::DspStore as Cell),
            (b"HERE", P::Here as Cell),
            (b"@", P::Fetch as Cell),
            (b"!", P::Store as Cell),
            (b"+!", P::AddStore as Cell),
            (b"-!", P::SubStore as Cell),
            (b"C@", P::FetchByte as Cell),
            (b"C!", P::StoreByte as Cell),
            (b"C@C!", P::CCopy as Cell),
            (b"CMOVE", P::CMove as Cell),
            (b"DROP", P::Drop as Cell),
            (b"SWAP", P::Swap as Cell),
            (b"DUP", P::Dup as Cell),
            (b"OVER", P::Over as Cell),
            (b"ROT", P::Rot as Cell),
            (b"-ROT", P::NRot as Cell),
            (b"2DROP", P::TwoDrop as Cell),
            (b"2DUP", P::TwoDup as Cell),
            (b"2SWAP", P::TwoSwap as Cell),
            (b"?DUP", P::QDup as Cell),
            (b"1+", P::Incr as Cell),
            (b"1-", P::Decr as Cell),
            (b"CELL+", P::IncrP as Cell),
            (b"CELL-", P::DecrP as Cell),
            // A cell is four bytes here, so jonesforth.f's 32-bit spellings fit.
            (b"4+", P::IncrP as Cell),
            (b"4-", P::DecrP as Cell),
            (b"+", P::Add as Cell),
            (b"-", P::Sub as Cell),
            (b"*", P::Mul as Cell),
            (b"/MOD", P::DivMod as Cell),
            (b"=", P::Equ as Cell),
            (b"<>", P::NEqu as Cell),
            (b"<", P::Lt as Cell),
            (b">", P::Gt as Cell),
            (b"<=", P::Le as Cell),
            (b">=", P::Ge as Cell),
            (b"0=", P::ZEqu as Cell),
            (b"0<>", P::ZNEqu as Cell),
            (b"0<", P::ZLt as Cell),
            (b"0>", P::ZGt as Cell),
            (b"0<=", P::ZLe as Cell),
            (b"0>=", P::ZGe as Cell),
            (b"AND", P::And as Cell),
            (b"OR", P::Or as Cell),
            (b"XOR", P::Xor as Cell),
            (b"INVERT", P::Invert as Cell),
            (b".", P::Dot as Cell),
            (b"EXECUTE", P::Execute as Cell),
            (b"CHAR", P::Char as Cell),
            (b"INTERPRET", P::Interpret as Cell),
            (b"BYE", P::Bye as Cell),
            (b"SYSCALL1", P::Syscall1 as Cell),
            (b"SYSCALL2", P::Syscall2 as Cell),
            (b"SYSCALL3", P::Syscall3 as Cell),
        ];

        for (name, code) in words {
            self.add_word(name, *code);
        }

        // These have to run even while compiling.
        for name in [&b"["[..], b"IMMEDIATE"] {
            let node = self.find(name);
            self.memory[node + W_FLAG] |= F_IMMED;
        }

        for (name, value) in [
            (&b"STATE"[..], header::STATE as Cell),
            (b"LATEST", header::LATEST as Cell),
            (b"S0", header::S0 as Cell),
            (b"BASE", header::BASE as Cell),
            (b"R0", header::RETURN_STACK_TOP as Cell),
            (b"DOCOL", P::DoCol as Cell),
            (b"F_IMMED", F_IMMED as Cell),
            (b"F_HIDDEN", F_HIDDEN as Cell),
            (b"F_LENMASK", F_LENMASK as Cell),
            (b"VERSION", 47),
            (b"(ARGC)", header::ARGC as Cell),
            (b"SYS_EXIT", sys::EXIT),
            (b"SYS_READ", sys::READ),
            (b"SYS_WRITE", sys::WRITE),
            (b"SYS_OPEN", sys::OPEN),
            (b"SYS_CLOSE", sys::CLOSE),
            (b"SYS_BRK", sys::BRK),
            (b"O_RDONLY", 0),
            (b"O_WRONLY", sys::O_WRONLY),
            (b"O_RDWR", sys::O_RDWR),
            (b"O_CREAT", sys::O_CREAT),
            (b"O_TRUNC", sys::O_TRUNC),
            (b"O_APPEND", sys::O_APPEND),
        ] {
            self.add_const(name, value);
        }

        // Colon definitions, in dependency order. `w` is the code field address
        // of an already-defined word.
        let w = |i: &Self, name: &[u8]| i.to_cfa(i.find(name)) as Cell;
        let exit = w(self, b"EXIT");

        // : >DFA >CFA CELL+ ;
        let body = [w(self, b">CFA"), w(self, b"CELL+"), exit];
        self.add_colon(b">DFA", false, &body);

        // : HIDE WORD FIND HIDDEN ;
        let body = [
            w(self, b"WORD"),
            w(self, b"FIND"),
            w(self, b"HIDDEN"),
            exit,
        ];
        self.add_colon(b"HIDE", false, &body);

        // : : WORD CREATE DOCOL , LATEST @ HIDDEN ] ;
        let body = [
            w(self, b"WORD"),
            w(self, b"CREATE"),
            w(self, b"DOCOL"),
            w(self, b","),
            w(self, b"LATEST"),
            w(self, b"@"),
            w(self, b"HIDDEN"),
            w(self, b"]"),
            exit,
        ];
        self.add_colon(b":", false, &body);

        // : ; IMMEDIATE ' EXIT , LATEST @ HIDDEN [ ;
        let body = [
            w(self, b"'"),
            exit, // operand of ' : the code field address to compile
            w(self, b","),
            w(self, b"LATEST"),
            w(self, b"@"),
            w(self, b"HIDDEN"),
            w(self, b"["),
            exit,
        ];
        self.add_colon(b";", true, &body);

        // : QUIT R0 RSP! BEGIN INTERPRET AGAIN ;
        let body = [
            w(self, b"R0"),
            w(self, b"RSP!"),
            w(self, b"INTERPRET"),
            w(self, b"BRANCH"),
            -2 * CELL as Cell,
            exit,
        ];
        self.add_colon(b"QUIT", false, &body);
    }

    /// The central dispatcher. Reads the instruction at `ip`, follows it to
    /// the target word's code field, obtains the primitive index, and tail‑calls
    /// that primitive with updated `ip` (advanced by one cell).
    ///
    /// This function is the target of every primitive's tail call, and it in
    /// turn tail‑calls the next primitive. The chain never returns.
    #[inline]
    fn next(&mut self, sp: usize, rsp: usize, ip: usize, _target: usize) -> ! {
        // Read the address stored at `ip` (the instruction).
        let tgt = self.read_cell(ip).unsigned_abs() as usize;
        // Read the primitive index from the target word's code field.
        let code = self.read_cell(tgt).unsigned_abs() as usize;
        // Tail‑call the primitive.
        become PRIMITIVES[code](self, sp, rsp, ip + CELL, tgt);
    }

    /// Start the interpreter at the given instruction pointer. Used to run a
    /// compiled word or a sequence of instructions.
    #[inline]
    fn run(&mut self, ip: usize, sp: usize, rsp: usize) -> ! {
        // Entry point from a non-tail context, so a plain call (one frame).
        self.next(sp, rsp, ip, 0)
    }

    /// Run threaded code at `ip` until it reaches `BYE`, which unwinds back here
    /// and leaves the final registers in `SP`/`RSP`.
    #[cfg(not(feature = "web"))]
    fn run_until_halt(&mut self, ip: usize) {
        let sp = self.read_cell(header::SP) as usize;
        let rsp = self.read_cell(header::RSP) as usize;
        if let Err(payload) = panic::catch_unwind(AssertUnwindSafe(|| self.run(ip, sp, rsp)))
            && payload.downcast_ref::<Halt>().is_none()
        {
            panic::resume_unwind(payload);
        }
    }

    /// Same, except the host throws to stop us, so there is nothing to catch:
    /// the engine discards these frames on its way back out to JavaScript.
    #[cfg(feature = "web")]
    fn run_until_halt(&mut self, ip: usize) {
        let sp = self.read_cell(header::SP) as usize;
        let rsp = self.read_cell(header::RSP) as usize;
        self.run(ip, sp, rsp)
    }

    /// Execute a single word given its code field address.
    fn execute(&mut self, cfa: usize) {
        let bye = self.to_cfa(self.find(b"BYE"));
        self.write_cell(header::SCRATCH, cfa as Cell);
        self.write_cell(header::SCRATCH + CELL, bye as Cell);
        self.run_until_halt(header::SCRATCH);
    }

    /// Body of the `SYSCALLn` words. Failures come back as `-errno`, which is
    /// what `OPEN-FILE` and friends test for.
    fn syscall(&mut self, number: Cell, [a, b, c]: [Cell; 3]) -> Cell {
        let outcome = match number {
            sys::BRK => Ok(self.brk(a)),
            sys::OPEN => self.open(a, b),
            sys::CLOSE => self.close(a),
            sys::READ => self.transfer(a, b, c, false),
            sys::WRITE => self.transfer(a, b, c, true),
            _ => Err(sys::ENOSYS),
        };
        outcome.unwrap_or_else(|errno| -errno)
    }

    /// The "data segment" is `memory` itself: `brk(0)` reports its end and any
    /// other argument resizes it. `UNUSED` and `MORECORE` are the only callers.
    fn brk(&mut self, addr: Cell) -> Cell {
        let end = addr as usize;
        if end >= header::DICTIONARY {
            self.memory.resize(end, 0);
        }
        self.memory.len() as Cell
    }

    fn open(&mut self, path: Cell, flags: Cell) -> Result<Cell, Cell> {
        let start = path as usize;
        let tail = self.memory.get(start..).ok_or(sys::EIO)?;
        let len = tail.iter().position(|&byte| byte == 0).ok_or(sys::EIO)?;
        let path = str::from_utf8(&tail[..len]).map_err(|_| sys::EIO)?;

        let mut options = OpenOptions::new();
        match flags & sys::O_ACCMODE {
            sys::O_WRONLY => options.write(true),
            sys::O_RDWR => options.read(true).write(true),
            _ => options.read(true),
        };
        let file = options
            .create(flags & sys::O_CREAT != 0)
            .truncate(flags & sys::O_TRUNC != 0)
            .append(flags & sys::O_APPEND != 0)
            .open(path)
            .map_err(errno)?;

        let slot = self.files.iter().position(Option::is_none).unwrap_or_else(|| {
            self.files.push(None);
            self.files.len() - 1
        });
        self.files[slot] = Some(file);
        Ok((slot + FD_BASE) as Cell)
    }

    fn close(&mut self, fd: Cell) -> Result<Cell, Cell> {
        self.slot(fd)?.take().ok_or(sys::EBADF)?;
        Ok(0)
    }

    /// `read`/`write` share everything but the direction; `addr` and `count`
    /// are clamped to the data segment.
    fn transfer(&mut self, fd: Cell, addr: Cell, count: Cell, out: bool) -> Result<Cell, Cell> {
        let addr = addr as usize;
        let end = addr
            .checked_add(count.max(0) as usize)
            .ok_or(sys::EIO)?
            .min(self.memory.len());
        let len = end.checked_sub(addr).ok_or(sys::EIO)?;

        if out {
            let Interp {
                memory,
                writer,
                files,
                ..
            } = self;
            let buf = &memory[addr..end];
            let written = match fd {
                1 | 2 => writer.write(buf),
                _ => Self::pick(files, fd)?.write(buf),
            };
            return written.map(|n| n as Cell).map_err(errno);
        }

        let mut buf = vec![0u8; len];
        let read = match fd {
            0 => self.reader.read(&mut buf),
            _ => Self::pick(&mut self.files, fd)?.read(&mut buf),
        }
        .map_err(errno)?;
        self.memory[addr..addr + read].copy_from_slice(&buf[..read]);
        Ok(read as Cell)
    }

    fn slot(&mut self, fd: Cell) -> Result<&mut Option<File>, Cell> {
        usize::try_from(fd)
            .ok()
            .and_then(|fd| fd.checked_sub(FD_BASE))
            .and_then(|index| self.files.get_mut(index))
            .ok_or(sys::EBADF)
    }

    fn pick(files: &mut [Option<File>], fd: Cell) -> Result<&mut File, Cell> {
        usize::try_from(fd)
            .ok()
            .and_then(|fd| fd.checked_sub(FD_BASE))
            .and_then(|index| files.get_mut(index))
            .and_then(Option::as_mut)
            .ok_or(sys::EBADF)
    }
}

fn errno(error: io::Error) -> Cell {
    error.raw_os_error().unwrap_or(sys::EIO) as Cell
}

// ---------------------------------------------------------------------------
// Primitive implementations
// ---------------------------------------------------------------------------

/// Enumerate the indices of all primitives. The order must match the order of
/// function pointers in the `PRIMITIVES` static array.
#[repr(usize)]
enum PrimitiveIndex {
    Exit = 0,
    Lit,
    Branch,
    ZeroBranch,
    LitString,
    Tell,
    Key,
    Emit,
    Word,
    Number,
    Find,
    ToCfa,
    Create,
    Comma,
    LBracket,
    RBracket,
    Immediate,
    Hidden,
    Tick,
    ToR,
    FromR,
    RFetch,
    RspFetch,
    RspStore,
    RDrop,
    DspFetch,
    DspStore,
    Here,
    Fetch,
    Store,
    AddStore,
    SubStore,
    FetchByte,
    StoreByte,
    CCopy,
    CMove,
    Drop,
    Swap,
    Dup,
    Over,
    Rot,
    NRot,
    TwoDrop,
    TwoDup,
    TwoSwap,
    QDup,
    Incr,
    Decr,
    IncrP,
    DecrP,
    Add,
    Sub,
    Mul,
    DivMod,
    Equ,
    NEqu,
    Lt,
    Gt,
    Le,
    Ge,
    ZEqu,
    ZNEqu,
    ZLt,
    ZGt,
    ZLe,
    ZGe,
    And,
    Or,
    Xor,
    Invert,
    Dot,
    DoCol,
    DoConst,
    Execute,
    Char,
    Interpret,
    Bye,
    Syscall1,
    Syscall2,
    Syscall3,
}

/// Static table of primitive function pointers.
static PRIMITIVES: &[PrimitiveFn] = &[
    exit, lit, branch, zero_branch, lit_string, tell, key, emit, word,
    number, find, to_cfa, create, comma, lbracket, rbracket, immediate,
    hidden, tick, to_r, from_r, r_fetch, rsp_fetch, rsp_store, r_drop,
    dsp_fetch, dsp_store, here, fetch, store, add_store, sub_store,
    fetch_byte, store_byte, c_copy, c_move, drop, swap, dup, over, rot,
    nrot, two_drop, two_dup, two_swap, qdup, incr, decr, incrp, decrp,
    add, sub, mul, divmod, equ, nequ, lt, gt, le, ge, zequ, znequ, zlt,
    zgt, zle, zge, and, or, xor, invert, dot, docol, do_const, execute, char,
    interpret, bye, syscall::<1>, syscall::<2>, syscall::<3>,
];

// Helper to read a cell at sp and advance sp (post‑increment).
#[inline]
fn pop(interp: &Interp, sp: usize) -> (Cell, usize) {
    (interp.read_cell(sp), sp + CELL)
}

// Helper to push a value onto the stack and return new sp.
#[inline]
fn push(interp: &mut Interp, sp: usize, val: Cell) -> usize {
    let new_sp = sp - CELL;
    interp.write_cell(new_sp, val);
    new_sp
}

// ---------------- Primitives ----------------

fn exit(interp: &mut Interp, _sp: usize, rsp: usize, _ip: usize, _target: usize) -> ! {
    let ret_addr = interp.read_cell(rsp) as usize;
    become interp.next(_sp, rsp + CELL, ret_addr, 0);
}

fn lit(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let val = interp.read_cell(ip);
    let new_sp = push(interp, sp, val);
    become interp.next(new_sp, rsp, ip + CELL, target);
}

fn branch(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let offset = interp.read_cell(ip);
    let new_ip = if offset < 0 {
        ip - offset.unsigned_abs() as usize
    } else {
        ip + offset as usize
    };
    become interp.next(sp, rsp, new_ip, target);
}

fn zero_branch(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let cond = interp.read_cell(sp);
    if cond == 0 {
        become branch(interp, sp + CELL, rsp, ip, target);
    } else {
        become interp.next(sp + CELL, rsp, ip + CELL, target);
    }
}

fn lit_string(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let count = interp.read_cell(ip);
    let addr = ip + CELL;
    let new_sp = push(interp, sp, addr as Cell);
    let new_sp = push(interp, new_sp, count);
    let aligned = (ip + count.unsigned_abs() as usize + 7) & !3usize;
    become interp.next(new_sp, rsp, aligned, target);
}

fn tell(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let (count, sp1) = pop(interp, sp);
    let (addr, sp2) = pop(interp, sp1);
    let Interp { memory, writer, .. } = interp;
    let (addr, count) = (addr as usize, count as usize);
    writer.write_all(&memory[addr..addr + count]).unwrap();
    writer.flush().unwrap();
    become interp.next(sp2, rsp, ip, target);
}

fn key(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let Some(c) = interp.key() else {
        become bye(interp, sp, rsp, ip, target);
    };
    let new_sp = push(interp, sp, c as Cell);
    become interp.next(new_sp, rsp, ip, target);
}

fn emit(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let (c, new_sp) = pop(interp, sp);
    interp.writer.write_all(&[c as u8]).unwrap();
    interp.writer.flush().unwrap();
    become interp.next(new_sp, rsp, ip, target);
}

fn word(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let Some(len) = interp.word() else {
        become bye(interp, sp, rsp, ip, target);
    };
    let new_sp = push(interp, sp, header::BUFFER as Cell);
    let new_sp = push(interp, new_sp, len as Cell);
    become interp.next(new_sp, rsp, ip, target);
}

fn number(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    // ( addr len -- n unparsed )
    let len = interp.read_cell(sp) as usize;
    let addr = interp.read_cell(sp + CELL) as usize;
    let base = interp.base();
    let parsed = Cell::from_str_radix(&String::from_utf8_lossy(interp.slice(addr, len)), base);
    if let Ok(num) = parsed {
        interp.write_cell(sp + CELL, num);
        interp.write_cell(sp, 0);
    }
    become interp.next(sp, rsp, ip, target);
}

fn find(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    // ( addr len -- entry )
    let len = interp.read_cell(sp) as usize;
    let addr = interp.read_cell(sp + CELL) as usize;
    let found = interp.find(interp.slice(addr, len));
    let new_sp = sp + CELL;
    interp.write_cell(new_sp, found as Cell);
    become interp.next(new_sp, rsp, ip, target);
}

fn to_cfa(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let node = interp.read_cell(sp) as usize;
    let cfa = interp.to_cfa(node);
    interp.write_cell(sp, cfa as Cell);
    become interp.next(sp, rsp, ip, target);
}

fn create(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    // ( addr len -- ) header only; the caller supplies the code field with `,`
    let (len, sp1) = pop(interp, sp);
    let (addr, sp2) = pop(interp, sp1);
    interp.create_header(addr as usize, len as usize);
    become interp.next(sp2, rsp, ip, target);
}

fn comma(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let (val, new_sp) = pop(interp, sp);
    interp.comma(val);
    become interp.next(new_sp, rsp, ip, target);
}

fn lbracket(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    interp.write_cell(header::STATE, 0);
    become interp.next(sp, rsp, ip, target);
}

fn rbracket(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    interp.write_cell(header::STATE, 1);
    become interp.next(sp, rsp, ip, target);
}

fn immediate(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let latest = interp.read_cell(header::LATEST) as usize;
    interp.memory[latest + W_FLAG] ^= F_IMMED;
    become interp.next(sp, rsp, ip, target);
}

fn hidden(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let (node, new_sp) = pop(interp, sp);
    interp.memory[node as usize + 4] ^= F_HIDDEN;
    become interp.next(new_sp, rsp, ip, target);
}

fn tick(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let val = interp.read_cell(ip);
    let new_sp = push(interp, sp, val);
    become interp.next(new_sp, rsp, ip + CELL, target);
}

fn to_r(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let (val, new_sp) = pop(interp, sp);
    let new_rsp = rsp - CELL;
    interp.write_cell(new_rsp, val);
    become interp.next(new_sp, new_rsp, ip, target);
}

fn from_r(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let val = interp.read_cell(rsp);
    let new_sp = push(interp, sp, val);
    become interp.next(new_sp, rsp + CELL, ip, target);
}

fn r_fetch(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let val = interp.read_cell(rsp);
    let new_sp = push(interp, sp, val);
    become interp.next(new_sp, rsp, ip, target);
}

fn rsp_fetch(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let new_sp = push(interp, sp, rsp as Cell);
    become interp.next(new_sp, rsp, ip, target);
}

fn rsp_store(interp: &mut Interp, sp: usize, _rsp: usize, ip: usize, target: usize) -> ! {
    let (new_rsp, new_sp) = pop(interp, sp);
    become interp.next(new_sp, new_rsp as usize, ip, target);
}

fn r_drop(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    become interp.next(sp, rsp + CELL, ip, target);
}

fn dsp_fetch(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let new_sp = push(interp, sp, sp as Cell);
    become interp.next(new_sp, rsp, ip, target);
}

fn dsp_store(interp: &mut Interp, _sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let (new_sp, _) = pop(interp, _sp);
    become interp.next(new_sp as usize, rsp, ip, target);
}

fn here(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let addr = header::HERE as Cell;
    let new_sp = push(interp, sp, addr);
    become interp.next(new_sp, rsp, ip, target);
}

fn fetch(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let addr = interp.read_cell(sp) as usize;
    let val = interp.read_cell(addr);
    interp.write_cell(sp, val);
    become interp.next(sp, rsp, ip, target);
}

fn store(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let (addr, sp1) = pop(interp, sp);
    let (val, sp2) = pop(interp, sp1);
    interp.write_cell(addr as usize, val);
    become interp.next(sp2, rsp, ip, target);
}

fn add_store(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let (addr, sp1) = pop(interp, sp);
    let (val, sp2) = pop(interp, sp1);
    let old = interp.read_cell(addr as usize);
    interp.write_cell(addr as usize, old + val);
    become interp.next(sp2, rsp, ip, target);
}

fn sub_store(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let (addr, sp1) = pop(interp, sp);
    let (val, sp2) = pop(interp, sp1);
    let old = interp.read_cell(addr as usize);
    interp.write_cell(addr as usize, old - val);
    become interp.next(sp2, rsp, ip, target);
}

fn fetch_byte(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let addr = interp.read_cell(sp) as usize;
    let val = interp.memory[addr] as Cell;
    interp.write_cell(sp, val);
    become interp.next(sp, rsp, ip, target);
}

fn store_byte(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let (addr, sp1) = pop(interp, sp);
    let (val, sp2) = pop(interp, sp1);
    interp.memory[addr as usize] = val as u8;
    become interp.next(sp2, rsp, ip, target);
}

fn c_copy(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let (src, sp1) = pop(interp, sp);
    let (dst, sp2) = pop(interp, sp1);
    let byte = interp.memory[src as usize];
    interp.memory[dst as usize] = byte;
    become interp.next(sp2, rsp, ip, target);
}

fn c_move(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    // ( source dest length -- )
    let (count, sp1) = pop(interp, sp);
    let (dst, sp2) = pop(interp, sp1);
    let (src, sp3) = pop(interp, sp2);
    let count = count as usize;
    interp
        .memory
        .copy_within(src as usize..src as usize + count, dst as usize);
    become interp.next(sp3, rsp, ip, target);
}

// Stack manipulation primitives: these are simple; they mutate the stack and
// then tail‑call next with the new stack pointer.
fn drop(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    become interp.next(sp + CELL, rsp, ip, target);
}
fn swap(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let a = interp.read_cell(sp);
    let b = interp.read_cell(sp + CELL);
    interp.write_cell(sp, b);
    interp.write_cell(sp + CELL, a);
    become interp.next(sp, rsp, ip, target);
}
fn dup(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let val = interp.read_cell(sp);
    let new_sp = push(interp, sp, val);
    become interp.next(new_sp, rsp, ip, target);
}
fn over(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let val = interp.read_cell(sp + CELL);
    let new_sp = push(interp, sp, val);
    become interp.next(new_sp, rsp, ip, target);
}
fn rot(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    // ( a b c -- b c a )
    let c = interp.read_cell(sp);
    let b = interp.read_cell(sp + CELL);
    let a = interp.read_cell(sp + 2 * CELL);
    interp.write_cell(sp, a);
    interp.write_cell(sp + CELL, c);
    interp.write_cell(sp + 2 * CELL, b);
    become interp.next(sp, rsp, ip, target);
}
fn nrot(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    // ( a b c -- c a b )
    let c = interp.read_cell(sp);
    let b = interp.read_cell(sp + CELL);
    let a = interp.read_cell(sp + 2 * CELL);
    interp.write_cell(sp, b);
    interp.write_cell(sp + CELL, a);
    interp.write_cell(sp + 2 * CELL, c);
    become interp.next(sp, rsp, ip, target);
}
fn two_drop(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    become interp.next(sp + 2 * CELL, rsp, ip, target);
}
fn two_dup(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    // ( a b -- a b a b )
    let b = interp.read_cell(sp);
    let a = interp.read_cell(sp + CELL);
    let new_sp = sp - 2 * CELL;
    interp.write_cell(new_sp, b);
    interp.write_cell(new_sp + CELL, a);
    become interp.next(new_sp, rsp, ip, target);
}
fn two_swap(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let a = interp.read_cell(sp);
    let b = interp.read_cell(sp + CELL);
    let c = interp.read_cell(sp + 2 * CELL);
    let d = interp.read_cell(sp + 3 * CELL);
    interp.write_cell(sp, c);
    interp.write_cell(sp + CELL, d);
    interp.write_cell(sp + 2 * CELL, a);
    interp.write_cell(sp + 3 * CELL, b);
    become interp.next(sp, rsp, ip, target);
}
fn qdup(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let val = interp.read_cell(sp);
    if val != 0 {
        let new_sp = push(interp, sp, val);
        become interp.next(new_sp, rsp, ip, target);
    } else {
        become interp.next(sp, rsp, ip, target);
    }
}
fn incr(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let val = interp.read_cell(sp) + 1;
    interp.write_cell(sp, val);
    become interp.next(sp, rsp, ip, target);
}
fn decr(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let val = interp.read_cell(sp) - 1;
    interp.write_cell(sp, val);
    become interp.next(sp, rsp, ip, target);
}
fn incrp(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let val = interp.read_cell(sp) + CELL as Cell;
    interp.write_cell(sp, val);
    become interp.next(sp, rsp, ip, target);
}
fn decrp(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let val = interp.read_cell(sp) - CELL as Cell;
    interp.write_cell(sp, val);
    become interp.next(sp, rsp, ip, target);
}

// Arithmetic and logic primitives.
fn add(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let (b, sp1) = pop(interp, sp);
    let (a, sp2) = pop(interp, sp1);
    let new_sp = push(interp, sp2, a + b);
    become interp.next(new_sp, rsp, ip, target);
}
fn sub(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let (b, sp1) = pop(interp, sp);
    let (a, sp2) = pop(interp, sp1);
    let new_sp = push(interp, sp2, a - b);
    become interp.next(new_sp, rsp, ip, target);
}
fn mul(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let (b, sp1) = pop(interp, sp);
    let (a, sp2) = pop(interp, sp1);
    let new_sp = push(interp, sp2, a * b);
    become interp.next(new_sp, rsp, ip, target);
}
fn divmod(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let (b, sp1) = pop(interp, sp);
    let (a, sp2) = pop(interp, sp1);
    let rem = a % b;
    let quot = a / b;
    let new_sp = push(interp, sp2, rem);
    let new_sp = push(interp, new_sp, quot);
    become interp.next(new_sp, rsp, ip, target);
}

fn equ(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let (b, sp1) = pop(interp, sp);
    let (a, sp2) = pop(interp, sp1);
    let val = if a == b { -1 } else { 0 };
    let new_sp = push(interp, sp2, val);
    become interp.next(new_sp, rsp, ip, target);
}
// Similar for nequ, lt, gt, le, ge, zequ, znequ, zlt, zgt, zle, zge.
// For brevity, we'll define a macro to generate these.
macro_rules! cmp_prim {
    ($name:ident, $op:tt) => {
        fn $name(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
            let (b, sp1) = pop(interp, sp);
            let (a, sp2) = pop(interp, sp1);
            let val = if a $op b { -1 } else { 0 };
            let new_sp = push(interp, sp2, val);
            become interp.next(new_sp, rsp, ip, target);
        }
    };
}
cmp_prim!(nequ, !=);
cmp_prim!(lt, <);
cmp_prim!(gt, >);
cmp_prim!(le, <=);
cmp_prim!(ge, >=);

macro_rules! zcmp_prim {
    ($name:ident, $op:tt) => {
        fn $name(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
            let val = interp.read_cell(sp);
            let res = if val $op 0 { -1 } else { 0 };
            interp.write_cell(sp, res);
            become interp.next(sp, rsp, ip, target);
        }
    };
}
zcmp_prim!(zequ, ==);
zcmp_prim!(znequ, !=);
zcmp_prim!(zlt, <);
zcmp_prim!(zgt, >);
zcmp_prim!(zle, <=);
zcmp_prim!(zge, >=);

fn and(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let (b, sp1) = pop(interp, sp);
    let (a, sp2) = pop(interp, sp1);
    let new_sp = push(interp, sp2, a & b);
    become interp.next(new_sp, rsp, ip, target);
}
fn or(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let (b, sp1) = pop(interp, sp);
    let (a, sp2) = pop(interp, sp1);
    let new_sp = push(interp, sp2, a | b);
    become interp.next(new_sp, rsp, ip, target);
}
fn xor(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let (b, sp1) = pop(interp, sp);
    let (a, sp2) = pop(interp, sp1);
    let new_sp = push(interp, sp2, a ^ b);
    become interp.next(new_sp, rsp, ip, target);
}
fn invert(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let val = !interp.read_cell(sp);
    interp.write_cell(sp, val);
    become interp.next(sp, rsp, ip, target);
}

fn dot(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let (val, new_sp) = pop(interp, sp);
    let base = interp.base();
    let mut digits = Vec::new();
    let mut v = val.unsigned_abs();
    loop {
        digits.push(char::from_digit(v % base, base).unwrap());
        v /= base;
        if v == 0 {
            break;
        }
    }
    if val < 0 {
        digits.push('-');
    }
    let text: String = digits.iter().rev().collect();
    write!(interp.writer, "{text} ").unwrap();
    interp.writer.flush().unwrap();
    become interp.next(new_sp, rsp, ip, target);
}

// Compilation and the outer interpreter.

/// Code field of every colon definition: save `ip` and run the body.
fn docol(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let new_rsp = rsp - CELL;
    interp.write_cell(new_rsp, ip as Cell);
    become interp.next(sp, new_rsp, target + CELL, target);
}

/// Code field of every constant/variable word: push the data field.
fn do_const(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let val = interp.read_cell(target + CELL);
    let new_sp = push(interp, sp, val);
    become interp.next(new_sp, rsp, ip, target);
}

fn execute(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, _target: usize) -> ! {
    let (cfa, new_sp) = pop(interp, sp);
    let cfa = cfa as usize;
    let code = interp.read_cell(cfa) as usize;
    become PRIMITIVES[code](interp, new_sp, rsp, ip, cfa);
}

fn char(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let Some(len) = interp.word() else {
        become bye(interp, sp, rsp, ip, target);
    };
    let c = if len == 0 { 0 } else { interp.memory[header::BUFFER] };
    let new_sp = push(interp, sp, c as Cell);
    become interp.next(new_sp, rsp, ip, target);
}

/// One pass of the outer interpreter: read a word and either execute it,
/// compile it, or treat it as a literal.
fn interpret(interp: &mut Interp, sp: usize, rsp: usize, ip: usize, target: usize) -> ! {
    let Some(len) = interp.word() else {
        become bye(interp, sp, rsp, ip, target);
    };
    let node = interp.find(interp.slice(header::BUFFER, len));
    if node != 0 {
        let cfa = interp.to_cfa(node);
        let immediate = interp.memory[node + W_FLAG] & F_IMMED != 0;
        if immediate || interp.read_cell(header::STATE) == 0 {
            let code = interp.read_cell(cfa) as usize;
            become PRIMITIVES[code](interp, sp, rsp, ip, cfa);
        }
        interp.comma(cfa as Cell);
        become interp.next(sp, rsp, ip, target);
    }

    let base = interp.base();
    let text = String::from_utf8_lossy(interp.slice(header::BUFFER, len));
    let Ok(num) = Cell::from_str_radix(&text, base) else {
        let text = text.into_owned();
        writeln!(interp.writer, "PARSE ERROR: {text}").unwrap();
        become interp.next(sp, rsp, ip, target);
    };
    if interp.read_cell(header::STATE) == 1 {
        let lit = interp.to_cfa(interp.find(b"LIT")) as Cell;
        interp.comma(lit);
        interp.comma(num);
        become interp.next(sp, rsp, ip, target);
    }
    let new_sp = push(interp, sp, num);
    become interp.next(new_sp, rsp, ip, target);
}

/// Leave the threaded code, publishing the machine registers so the caller of
/// `Interp::run` can inspect them.
fn bye(interp: &mut Interp, sp: usize, rsp: usize, _ip: usize, _target: usize) -> ! {
    interp.write_cell(header::SP, sp as Cell);
    interp.write_cell(header::RSP, rsp as Cell);
    halt()
}

/// `SYSCALLn ( argN .. arg1 number -- result )`, the shape jonesforth.S gives
/// them: the number is on top and the arguments follow in register order.
fn syscall<const N: usize>(
    interp: &mut Interp,
    sp: usize,
    rsp: usize,
    ip: usize,
    target: usize,
) -> ! {
    let (number, mut sp) = pop(interp, sp);
    let mut args = [0; 3];
    for arg in args.iter_mut().take(N) {
        (*arg, sp) = pop(interp, sp);
    }
    if number == sys::EXIT {
        become bye(interp, sp, rsp, ip, target);
    }
    let result = interp.syscall(number, args);
    let new_sp = push(interp, sp, result);
    become interp.next(new_sp, rsp, ip, target);
}

/// Leave Rust altogether. Natively that is a panic `run_until_halt` catches.
#[cfg(not(feature = "web"))]
fn halt() -> ! {
    panic::panic_any(Halt)
}

/// Wasm cannot unwind itself without the exception-handling proposal, so the
/// host throws on our behalf and the engine tears the frames down for free.
#[cfg(feature = "web")]
fn halt() -> ! {
    unsafe { web::throw_halt() }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

#[cfg(not(feature = "web"))]
fn main() {
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut interp = Interp::new(Box::new(stdin.lock()), Box::new(stdout.lock()));
    let quit = interp.to_cfa(interp.find(b"QUIT"));
    // QUIT loops forever; control comes back here on BYE or end of input.
    interp.execute(quit);
}

/// A page has no blocking stdin, so the browser build inverts the loop: the host
/// hands over a chunk of source, `eval` runs `QUIT` until that chunk is drained,
/// and `KEY` then hits end of input and halts. Every bit of Forth state lives in
/// `Interp::memory` and `SP`/`RSP` are published on the way out, so the next call
/// picks up exactly where this one stopped — no worker, no `SharedArrayBuffer`,
/// and therefore no cross-origin isolation.
///
/// `_start` still runs, which is what initialises WASI and builds the session;
/// the host calls `eval` from then on.
#[cfg(feature = "web")]
fn main() {
    web::boot();
}

#[cfg(feature = "web")]
mod web {
    use super::Interp;
    use std::cell::RefCell;
    use std::collections::VecDeque;
    use std::io::{self, BufReader, Read, Write};
    use std::rc::Rc;

    #[link(wasm_import_module = "env")]
    unsafe extern "C" {
        /// Throws on the host side; control never comes back into wasm.
        pub fn throw_halt() -> !;
        pub fn write_out(ptr: *const u8, len: usize);
    }

    type Queue = Rc<RefCell<VecDeque<u8>>>;

    struct Stdin(Queue);

    impl Read for Stdin {
        fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> {
            let mut queue = self.0.borrow_mut();
            let n = queue.len().min(buf.len());
            for (slot, byte) in buf.iter_mut().zip(queue.drain(..n)) {
                *slot = byte;
            }
            Ok(n)
        }
    }

    struct Stdout;

    impl Write for Stdout {
        fn write(&mut self, buf: &[u8]) -> io::Result<usize> {
            unsafe { write_out(buf.as_ptr(), buf.len()) };
            Ok(buf.len())
        }

        fn flush(&mut self) -> io::Result<()> {
            Ok(())
        }
    }

    const INPUT_CAP: usize = 1 << 16;
    static mut INPUT: [u8; INPUT_CAP] = [0; INPUT_CAP];
    static mut SESSION: Option<(Interp, Queue)> = None;

    /// Staging area the host fills before each `eval`.
    #[unsafe(no_mangle)]
    pub extern "C" fn input() -> *mut u8 {
        (&raw mut INPUT).cast()
    }

    #[unsafe(no_mangle)]
    pub extern "C" fn input_capacity() -> usize {
        INPUT_CAP
    }

    /// Called from `main`, i.e. from `_start`, once WASI is up.
    pub fn boot() {
        let queue: Queue = Rc::new(RefCell::new(VecDeque::new()));
        let interp = Interp::new(
            Box::new(BufReader::new(Stdin(queue.clone()))),
            Box::new(Stdout),
        );
        unsafe { SESSION = Some((interp, queue)) };
    }

    /// Consume `input()[..len]`. Always exits through `throw_halt`.
    #[unsafe(no_mangle)]
    pub extern "C" fn eval(len: usize) {
        let (interp, queue) = unsafe { (*(&raw mut SESSION)).as_mut() }.expect("boot first");
        let chunk = unsafe { std::slice::from_raw_parts((&raw const INPUT).cast::<u8>(), len) };
        queue.borrow_mut().extend(chunk);
        let quit = interp.to_cfa(interp.find(b"QUIT"));
        interp.execute(quit);
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn interp() -> Interp {
        Interp::new(Box::new(io::empty()), Box::new(io::sink()))
    }

    /// An interpreter reading `input` and writing into a buffer we can inspect.
    fn interp_io(input: &'static str) -> (Interp, std::rc::Rc<std::cell::RefCell<Vec<u8>>>) {
        struct Shared(std::rc::Rc<std::cell::RefCell<Vec<u8>>>);
        impl Write for Shared {
            fn write(&mut self, buf: &[u8]) -> io::Result<usize> {
                self.0.borrow_mut().extend_from_slice(buf);
                Ok(buf.len())
            }
            fn flush(&mut self) -> io::Result<()> {
                Ok(())
            }
        }
        let out = std::rc::Rc::new(std::cell::RefCell::new(Vec::new()));
        let i = Interp::new(Box::new(input.as_bytes()), Box::new(Shared(out.clone())));
        (i, out)
    }

    impl Interp {
        /// Code field address of a built-in word, for assembling test programs.
        fn cfa(&self, name: &str) -> Cell {
            let node = self.find(name.as_bytes());
            assert_ne!(node, 0, "{name} not in the dictionary");
            self.to_cfa(node) as Cell
        }

        /// Push `stack` (bottom first), run `code` (a list of cells, terminated
        /// by BYE), and return the resulting stack with the top at index 0.
        fn exec(&mut self, stack: &[Cell], code: &[Cell]) -> Vec<Cell> {
            let s0 = self.read_cell(header::S0) as usize;
            let mut sp = s0;
            for &v in stack {
                sp = push(self, sp, v);
            }
            self.write_cell(header::SP, sp as Cell);

            assert!(code.len() < header::SCRATCH_LEN / CELL);
            for (n, &c) in code.iter().enumerate() {
                self.write_cell(header::SCRATCH + n * CELL, c);
            }
            let bye = self.cfa("BYE");
            self.write_cell(header::SCRATCH + code.len() * CELL, bye);

            self.run_until_halt(header::SCRATCH);
            let sp = self.read_cell(header::SP) as usize;
            (sp..s0).step_by(CELL).map(|a| self.read_cell(a)).collect()
        }
    }

    /// Walk the dictionary from LATEST, yielding (name, code field value).
    fn entries(i: &Interp) -> Vec<(String, Cell)> {
        let mut out = Vec::new();
        let mut node = i.read_cell(header::LATEST) as usize;
        while node != 0 {
            let len = (i.memory[node + W_FLAG] & 0x1f) as usize;
            let name = String::from_utf8_lossy(&i.memory[node + W_NAME..node + W_NAME + len]).into_owned();
            out.push((name, i.read_cell(node + W_NAME + len)));
            node = i.read_cell(node) as usize;
        }
        out
    }

    /// Address of a word's dictionary header (what FIND ought to return).
    fn word_addr(i: &Interp, name: &str) -> Cell {
        let mut node = i.read_cell(header::LATEST) as usize;
        while node != 0 {
            let len = (i.memory[node + W_FLAG] & 0x1f) as usize;
            if i.memory[node + W_NAME..node + W_NAME + len] == *name.as_bytes() {
                return node as Cell;
            }
            node = i.read_cell(node) as usize;
        }
        panic!("{name} not in the dictionary");
    }

    #[test]
    fn dictionary_is_well_formed() {
        assert_eq!(
            PRIMITIVES.len(),
            PrimitiveIndex::Syscall3 as usize + 1,
            "PrimitiveIndex and PRIMITIVES have drifted apart"
        );
        let i = interp();
        let e = entries(&i);
        for (name, code) in &e {
            assert!(
                (*code as usize) < PRIMITIVES.len(),
                "{name} has out-of-range code field {code}"
            );
        }
        let mut names: Vec<&String> = e.iter().map(|(n, _)| n).collect();
        names.sort();
        let unique = names.len();
        names.dedup();
        assert_eq!(names.len(), unique, "duplicate word names");
    }

    #[test]
    fn find_agrees_with_the_primitive_table() {
        use PrimitiveIndex as P;
        let i = interp();
        for (name, want) in [
            ("DUP", P::Dup),
            ("+", P::Add),
            ("/MOD", P::DivMod),
            ("EXECUTE", P::Execute),
            ("EXIT", P::Exit),
            (";", P::DoCol),
            ("BASE", P::DoConst),
        ] {
            assert_eq!(i.read_cell(i.cfa(name) as usize), want as Cell, "{name}");
        }
        assert_eq!(i.find(b"NOSUCHWORD"), 0);
    }

    // --- phase 2: memory map -------------------------------------------------

    #[test]
    fn regions_do_not_overlap() {
        assert!(header::DICTIONARY > header::BUFFER + header::BUFFER_LEN);
        let i = interp();
        assert_eq!(i.read_cell(header::S0) as usize, header::STACK_TOP);
        assert_eq!(i.read_cell(header::R0) as usize, header::RETURN_STACK_TOP);
        // The dictionary starts past every header field and never reaches them.
        assert!(i.read_cell(header::HERE) as usize >= header::DICTIONARY);
        assert_eq!(i.read_cell(header::BASE), 10);
    }

    #[test]
    fn the_machine_runs_threaded_code() {
        let mut i = interp();
        let (add, dup) = (i.cfa("+"), i.cfa("DUP"));
        assert_eq!(i.exec(&[2, 3], &[add, dup]), vec![5, 5]);
    }

    #[test]
    fn the_return_stack_is_its_own_region() {
        let mut i = interp();
        let (tor, fromr) = (i.cfa(">R"), i.cfa("R>"));
        assert_eq!(i.exec(&[1, 2, 3], &[tor, tor, fromr, fromr]), vec![3, 2, 1]);
        assert_eq!(
            i.read_cell(header::RSP) as usize,
            header::RETURN_STACK_TOP,
            "return stack balanced"
        );
    }

    /// The whole design rests on `become` being a real tail call: a BRANCH loop
    /// of a million iterations must not grow the machine stack.
    #[test]
    fn become_does_not_consume_stack() {
        let mut i = interp();
        let (lit, decr, zbranch, branch) =
            (i.cfa("LIT"), i.cfa("1-"), i.cfa("0BRANCH"), i.cfa("BRANCH"));
        // LIT 1000000  BEGIN 1- DUP 0BRANCH(out) BRANCH(top) ... DROP
        let dup = i.cfa("DUP");
        let code = vec![
            lit,
            1_000_000,          // [1]
            decr,               // [2] loop top
            dup,                // [3]
            zbranch,            // [4]
            3 * CELL as Cell,   // [5] -> past the BRANCH
            branch,             // [6]
            -5 * CELL as Cell,  // [7] -> back to [2]
        ];
        assert_eq!(i.exec(&[], &code), vec![0]);
    }

    // --- phase 3: stack discipline -------------------------------------------

    /// `@ C@ >CFA FIND` are unary: they must consume exactly one cell (a pair
    /// for FIND), leaving everything underneath untouched.
    #[test]
    fn unary_words_replace_the_top_in_place() {
        let mut i = interp();
        let base = header::BASE as Cell;
        for name in ["@", "C@"] {
            let w = i.cfa(name);
            assert_eq!(i.exec(&[111, 222, base], &[w]), vec![10, 222, 111], "{name}");
        }
        let tcfa = i.cfa(">CFA");
        let dup = word_addr(&i, "DUP");
        assert_eq!(
            i.exec(&[111, 222, dup], &[tcfa]),
            vec![i.cfa("DUP"), 222, 111]
        );

        let (lit, find) = (i.cfa("LIT"), i.cfa("FIND"));
        let (addr, len) = (header::BUFFER as Cell, 3);
        i.memory[header::BUFFER..header::BUFFER + 3].copy_from_slice(b"DUP");
        let out = i.exec(&[111, 222], &[lit, addr, lit, len, find]);
        assert_eq!(out.len(), 3, "FIND turns two cells into one");
        assert_ne!(out[0], 0);
        assert_eq!(&out[1..], &[222, 111]);
    }

    // --- phase 4: word semantics ---------------------------------------------

    #[test]
    fn stack_shufflers_match_the_standard() {
        let mut i = interp();
        for (name, want) in [
            ("ROT", vec![1, 3, 2]),   // 1 2 3 -- 2 3 1
            ("-ROT", vec![2, 1, 3]),  // 1 2 3 -- 3 1 2
            ("SWAP", vec![2, 3, 1]),  // 1 2 3 -- 1 3 2
            ("OVER", vec![2, 3, 2, 1]),
        ] {
            let w = i.cfa(name);
            assert_eq!(i.exec(&[1, 2, 3], &[w]), want, "{name}");
        }
        let two_dup = i.cfa("2DUP");
        assert_eq!(i.exec(&[1, 2], &[two_dup]), vec![2, 1, 2, 1]);
    }

    #[test]
    fn cmove_copies_source_to_dest() {
        let mut i = interp();
        let (src, dst) = (header::BUFFER, header::BUFFER + 8);
        i.memory[src..src + 4].copy_from_slice(b"abcd");
        let (lit, cmove) = (i.cfa("LIT"), i.cfa("CMOVE"));
        let code = [lit, src as Cell, lit, dst as Cell, lit, 4, cmove];
        assert!(i.exec(&[], &code).is_empty(), "CMOVE consumes all three");
        assert_eq!(&i.memory[dst..dst + 4], b"abcd");
    }

    #[test]
    fn find_skips_hidden_words() {
        let mut i = interp();
        let dup = word_addr(&i, "DUP");
        let (lit, hidden) = (i.cfa("LIT"), i.cfa("HIDDEN"));
        i.exec(&[], &[lit, dup, hidden]);
        assert_eq!(i.find(b"DUP"), 0, "hidden words are invisible to FIND");
        i.exec(&[], &[lit, dup, hidden]);
        assert_eq!(i.find(b"DUP") as Cell, dup);
    }

    #[test]
    fn word_skips_comments_and_bounds_the_buffer() {
        let (mut i, _) = interp_io("\\ a comment\n  hello   world");
        assert_eq!(i.word(), Some(5));
        assert_eq!(&i.memory[header::BUFFER..header::BUFFER + 5], b"hello");
        assert_eq!(i.word(), Some(5));
        assert_eq!(i.word(), None, "end of input");

        let (mut i, _) = interp_io("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa x");
        assert_eq!(i.word(), Some(header::BUFFER_LEN));
        assert_eq!(i.word(), Some(1), "the overlong word is truncated, not lost");
    }

    #[test]
    fn dot_honours_base() {
        let (mut i, out) = interp_io("");
        let (lit, dot, store) = (i.cfa("LIT"), i.cfa("."), i.cfa("!"));
        i.exec(&[], &[lit, -255, dot]);
        let code = [lit, 16, lit, header::BASE as Cell, store, lit, 255, dot];
        i.exec(&[], &code);
        assert_eq!(&*out.borrow(), b"-255 ff ");
    }

    #[test]
    fn key_at_end_of_input_halts_cleanly() {
        let (mut i, _) = interp_io("z");
        let key = i.cfa("KEY");
        assert_eq!(i.exec(&[], &[key, key]), vec![b'z' as Cell], "no panic at EOF");
    }

    // --- phase 5: the outer interpreter lives in Forth ------------------------

    /// Feed `src` to QUIT until the input runs out; return the stack (top
    /// first) and everything the interpreter printed.
    fn run_source(src: &'static str) -> (Vec<Cell>, String) {
        let (mut i, out) = interp_io(src);
        let quit = i.to_cfa(i.find(b"QUIT"));
        i.execute(quit);
        let (sp, s0) = (
            i.read_cell(header::SP) as usize,
            i.read_cell(header::S0) as usize,
        );
        let stack = (sp..s0).step_by(CELL).map(|a| i.read_cell(a)).collect();
        (stack, String::from_utf8(out.borrow().clone()).unwrap())
    }

    #[test]
    fn interprets_numbers_and_words() {
        assert_eq!(run_source("2 3 + 4 *").0, vec![20]);
        assert_eq!(run_source("VERSION BASE @ STATE @").0, vec![0, 10, 47]);
    }

    #[test]
    fn colon_definitions_execute() {
        assert_eq!(run_source(": SQUARE DUP * ; 5 SQUARE").0, vec![25]);
    }

    #[test]
    fn nested_definitions_balance_the_return_stack() {
        let (mut i, _) = interp_io(": DOUBLE 2 * ; : QUAD DOUBLE DOUBLE ; 3 QUAD");
        let quit = i.to_cfa(i.find(b"QUIT"));
        i.execute(quit);
        assert_eq!(i.read_cell(i.read_cell(header::SP) as usize), 12);
        assert_eq!(
            i.read_cell(header::RSP) as usize,
            header::RETURN_STACK_TOP,
            "every DOCOL was matched by an EXIT"
        );
    }

    #[test]
    fn immediate_words_run_while_compiling() {
        // `[` is immediate, so 2 3 + runs now; `]` restores compile mode, and
        // the trailing 9 proves STATE came back to 0 after `;`.
        assert_eq!(run_source(": FOO [ 2 3 + ] ; FOO 9").0, vec![9, 5]);
    }

    #[test]
    fn tick_and_execute() {
        assert_eq!(run_source(": T ' DUP EXECUTE ; 7 T").0, vec![7, 7]);
        assert_eq!(run_source("CHAR A").0, vec![65]);
    }

    #[test]
    fn recursion_via_hidden_and_branches() {
        // Bootstrap RECURSE (the word being compiled is HIDDEN, so it cannot
        // name itself) and hand-assemble the 0BRANCH offset with `[ n , ]`.
        let src = ": RECURSE IMMEDIATE LATEST @ >CFA , ;
                   : FACT DUP 1 <= 0BRANCH [ 20 , ] DROP 1 EXIT DUP 1- RECURSE * ;
                   5 FACT";
        assert_eq!(run_source(src).0, vec![120]);
    }

    #[test]
    fn unknown_words_are_reported_not_fatal() {
        let (stack, out) = run_source("1 NOSUCHWORD 2");
        assert!(out.contains("PARSE ERROR: NOSUCHWORD"), "{out}");
        assert_eq!(stack, vec![2, 1], "interpretation continues");
    }

    #[test]
    fn dot_prints_through_the_full_stack() {
        let (_, out) = run_source(": .TWICE DUP . . ; 42 .TWICE");
        assert_eq!(out, "42 42 ");
    }

    #[test]
    fn number_parses_in_place() {
        let mut i = interp();
        let (lit, number) = (i.cfa("LIT"), i.cfa("NUMBER"));
        let (addr, len) = (header::BUFFER as Cell, 3);
        i.memory[header::BUFFER..header::BUFFER + 3].copy_from_slice(b"123");
        // ( addr len -- n unparsed ), guard cell stays put
        assert_eq!(
            i.exec(&[999], &[lit, addr, lit, len, number]),
            vec![0, 123, 999]
        );
        i.memory[header::BUFFER..header::BUFFER + 3].copy_from_slice(b"1X3");
        assert_eq!(
            i.exec(&[999], &[lit, addr, lit, len, number]),
            vec![3, addr, 999],
            "failure leaves the operands and a non-zero count"
        );
    }
}