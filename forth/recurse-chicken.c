/*	https://github.com/jburgy/blog/blob/main/forth/jansforth.c with the FORTH
	return stack made of continuation nodes, in the style of Chicken Scheme
	("Cheney on the M.T.A.") and of forth/recurse.c.

	There is ONE return stack and it is a linked chain of `struct frame
	{parent, value}`.  DOCOL pushes a node whose value is the caller's ip as a
	byte address (what jonesforth leaves on its return stack), >R pushes any
	cell, R> and RDROP pop a node, and EXIT pops a node and resumes at its
	value whatever pushed it: exactly jonesforth's semantics, so there is no
	shadow stack and no per-frame `base`.

	Pushing is a call that never returns: push() holds the node as a local and
	calls run(), the flat `while (1) switch (memory[cfa])` loop, on top of it.
	Popping just moves `cont`, so the C stack only grows and is mostly dead
	nodes.  push() counts pushes since the last reset instead of looking at
	stack addresses; past NURSERY it evacuates the live nodes (the ones not yet
	`on_heap`) to the static heap[] stack, fixes the parents, and longjmps to
	main, which restarts run() on an empty C stack.  That is Chicken's minor GC
	with the C stack as nursery and heap[] as the only older generation; popped
	heap nodes are reused by the next evacuation.  Nesting is bounded by
	HEAP_FRAMES (1M), not by the process stack; past it RETURN STACK OVERFLOW is
	printed and QUIT restarts.  NURSERY (256) pushes must fit the C stack,
	about 150-250 bytes each (arm64 clang).

	What the former limitations became:
	- R> reaching the caller's return address, R> ... >R inline data, regexp.f's
	  XCALL and (NNODE): lifted, since the address is an ordinary node
	  (test_inline_data_via_return_stack; regexp.f's RE-TESTS give the same
	  answers as re).
	- PRINT-STACK-TRACE: lifted, it walks RSP@'s window (test_print_stack_trace).
	- key() spinning at EOF: it now exits with status 0 as jansforth.c does.
	- Native CATCH/THROW by name at every CREATE: CATCH is gone, jonesforth.f's
	  own runs unchanged on the chain.  Only the first THROW is intercepted,
	  because jonesforth.f's THROW scans the return stack as memory and
	  RSP@ can show only WINDOW nodes: unmodified it catches up to about 250
	  nested calls (200 works, 400 does not) and the test needs 5000.  The
	  native one walks the chain for the first EXCEPTION-MARKER's address, pops
	  to it and restores the data stack as jonesforth.f's would; it falls back
	  to the FORTH THROW if there is no marker.  Redefinitions of CATCH,
	  THROW or EXCEPTION-MARKER are plain FORTH
	  (test_redefined_catch_throw_not_intercepted).
	- The 2048-cell data stack: the return stack no longer lives in memory, so
	  cells 0..0x1000 minus WINDOW (3840) are the data stack, S0 and the
	  initial sp moved there (test_deep_data_stack).  Going further needs
	  re-laying the rodata image, which is not done.

	RSP@, RSP! and R0 keep a memory view of the chain for code that walks it.
	Forth addresses the return stack as a flat array of cells in memory[]
	(`@`, then `4+` to the next entry), but the chain is linked nodes that move
	when they are evacuated, so there is nothing flat to point at.  The window
	is the extra level of indirection that fixes that, the fundamental theorem
	of software engineering (https://en.wikipedia.org/wiki/Fundamental_theorem_of_software_engineering):
	RSP@ maps nodes to window offsets, and RSP! maps an offset back to a depth
	and then walks that many `parent` links.  The price is the usual corollary,
	a second hop (offset, then node) and a copy.
	R0 is cell 0x1000.  RSP@ copies the newest min(depth, WINDOW) nodes into
	the WINDOW (256) cells below R0, newest at the lowest address, and returns
	that address, so `@` and `4+` walk it like jonesforth.  RSP! reads its
	argument the same way, counting cells up from R0 against the window the chain
	would show now: it pops down to the address, or pushes the window cells
	below the current top.  Ceilings: both cost O(min(depth, WINDOW)); deeper
	nodes are invisible to FORTH walkers; RSP! can pop only what the window
	shows (so `R0 RSP!` empties a chain only if it is at most WINDOW deep; QUIT
	itself restarts natively) and pushing needs room, so it does nothing when
	the chain already fills the window.  Anything written into the window is
	only a snapshot; changes reach the chain only through RSP!.

	Three views of the same four-node chain (values are made up; R0 is cell
	4096, byte 0x4000).  First what is real: linked nodes in two places, none
	of them readable with `@`.

                cont
                 |
                 v
          C stack (nursery)                    heap[] (static, evacuated)
          +--------------------+               +--------------------+
          | A                  |               | C  (heap[2])       |
          |  value  = 0x5A10   |        +----->|  value  = 0x4C08   |
          |  parent ----+      |        |      |  parent ----+      |
          +-------------|------+        |      +-------------|------+
          ... dead frames ...           |                    |
          +-------------|------+        |                    v
          | B           v      |        |      +--------------------+
          |  value  = 0x5B24   |        |      | D  (heap[1])       |
          |  parent -----------|--------+      |  value  = 0x4B90   |
          +--------------------+               |  parent --> heap[0]|
                                               +--------------------+

	RSP@ is hop one, nodes to a flat window, and returns the lowest address.
	`@` there reads 0x5A10, `4+` steps to 0x5B24, and walkers stop at R0.

          cell 4092   +--------+  <-- RSP@ returns        A.value
                      | 0x5A10 |      ((4096 - 4) << 2)    |
          cell 4093   +--------+      = byte 0x3FF0       B.value
                      | 0x5B24 |                           |
          cell 4094   +--------+                         C.value
                      | 0x4C08 |                           |
          cell 4095   +--------+                         D.value
                      | 0x4B90 |
          cell 4096   +--------+  <-- R0 (byte 0x4000)

	RSP! is both hops: the address gives a depth, the depth gives a node.

          Forth passes address 0x3FF8
                 |
                 |  hop 1: address to depth
                 |    cell = 0x3FF8 >> 2          = 4094
                 |    e    = R0 cell - cell       = 4096 - 4094 = 2
                 v
          keep e = 2 nodes but the chain shows m = 4, so pop m - e = 2
                 |
                 |  hop 2: depth to node, follow parent links
                 v
          cont --> A --> B --> C --> D
                   ^pop  ^pop  ^
                               cont ends here

	Input hardening, as in 4th.c and 5th.c: tokens are cut to the 32-byte
	buffer, names keep 31 characters (a 32-character name is never found),
	/MOD reports DIVISION BY ZERO and wraps INT_MIN / -1, arithmetic and
	number parsing wrap in unsigned, bytes are unsigned, lone signs are not
	numbers, and the SYSCALLn words use bounds-checked libc calls returning
	-errno on every platform.  The data stack (SP_MIN..S0) is checked in
	INTERPRET and at calls and branches, so runaway loops print STACK
	OVERFLOW or STACK UNDERFLOW and restart QUIT; `,`, CREATE and INTERPRET's
	compiling print OUT OF MEMORY at HERE_MAX (FORGET reclaims the space).

	Deliberate limitations:
	- Words that take raw addresses (@ ! C@ C! CMOVE TELL, HERE +!, ...) are unchecked.
	- Branch offsets and return addresses are shifted with >> , which is
	  implementation-defined for negative values.
	- Names in rodata are packed little-endian, and EMIT writes a cell's first byte.
	- The rodata indices (5120.., QUIT_CFA) are numbered by hand.
	- Not strict ISO: BRK is a 16MB calloc arena (no sbrk), and POSIX
	  read/write/open/creat/close are needed.
*/
#include <errno.h>
#include <fcntl.h>
#include <setjmp.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/syscall.h>

static char *bytes; /* defined below the rodata dictionary; declared early so do_syscallN can use it */

#ifdef __APPLE__
#define SYS_creat 24
#define SYS_brk 214
#endif

#define ARENA (1 << 24) /* bytes of address space behind BRK; calloc commits it lazily */

/* jonesforth.f only ever drives the handful of syscall numbers below through
   SYSCALLn (same idea as 4th.c's wasi shim), so they dispatch to libc calls
   directly on every platform: syscall(2) is deprecated on macOS and takes
   raw addresses.  Buffer and path arguments are memory[]-relative offsets
   exactly like every other pointer in this file, so they go through bytes + n
   after being checked against the arena, and failures return -errno as the
   Linux syscall convention jonesforth.f expects.  SYS_creat takes its arity
   (path, mode, via SYSCALL3) from jansforth.zig's doSyscall3/SysNum.CREAT, the
   only other place in this project that dispatches it. */
static int result(long r) {
    return r < 0 ? -errno : (int)r;
}

/* Clamp a length to what is left of the arena after off; false if off is outside it. */
static bool span(int off, int *len) {
    if (off < 0 || off > ARENA || *len < 0)
        return false;
    if (*len > ARENA - off)
        *len = ARENA - off;
    return true;
}

/* A nul-terminated path inside the arena, or NULL. */
static const char *path(int off) {
    if (off < 0 || off >= ARENA || !memchr(bytes + off, 0, (size_t)(ARENA - off)))
        return NULL;
    return bytes + off;
}

static int do_syscall3(int sysno, int a, int b, int c) {
    switch (sysno) {
    case SYS_read:  return span(b, &c) ? result(read(a, bytes + b, (size_t)c)) : -EFAULT;
    case SYS_write: return span(b, &c) ? result(write(a, bytes + b, (size_t)c)) : -EFAULT;
    case SYS_open:  return path(a) ? result(open(path(a), b, (mode_t)c)) : -EFAULT;
    case SYS_creat: return path(a) ? result(creat(path(a), (mode_t)c)) : -EFAULT; /* b (flags) unused, matching jansforth.zig */
    default:        return -ENOSYS;
    }
}

static int do_syscall2(int sysno, int a, int b) {
    switch (sysno) {
    case SYS_open: return path(a) ? result(open(path(a), b, 0644)) : -EFAULT;
    default:       return -ENOSYS;
    }
}

static int do_syscall1(int sysno, int a) {
    switch (sysno) {
    case SYS_close: return result(close(a));
    case SYS_exit:  exit(a);
    default:        return -ENOSYS;
    }
}

enum Builtin {
    DOCOL,
    DROP,
    SWAP,
    DUP,
    OVER,
    ROT,
    NROT,
    TWODROP,
    TWODUP,
    TWOSWAP,
    QDUP,
    INCR,
    DECR,
    INCR4,
    DECR4,
    ADD,
    SUB,
    MUL,
    DIVMOD,
    EQU,
    NEQU,
    LT,
    GT,
    LE,
    GE,
    ZEQU,
    ZNEQU,
    ZLT,
    ZGT,
    ZLE,
    ZGE,
    AND,
    OR,
    XOR,
    INVERT,
    EXIT,
    LIT,
    STORE,
    FETCH,
    ADDSTORE,
    SUBSTORE,
    STOREBYTE,
    FETCHBYTE,
    CCOPY,
    CMOVE,
    STATE,
    HERE,
    LATEST,
    SZ,
    BASE,
    VERSION,
    RZ,
    DOCOL_, 
    F_IMMED,
    F_HIDDEN,
    F_LENMASK,
    SYS_EXIT,
    SYS_OPEN,
    SYS_CLOSE,
    SYS_READ,
    SYS_WRITE,
    SYS_CREAT,
    SYS_BRK,
    O_RDONLY_,
    O_WRONLY_,
    O_RDWR_,
    O_CREAT_,
    O_EXCL_,
    O_TRUNC_,
    O_APPEND_,
    O_NONBLOCK_,
    TOR,
    FROMR,
    RSPFETCH,
    RSPSTORE,
    RDROP,
    DSPFETCH,
    DSPSTORE,
    KEY,
    EMIT,
    WORD,
    NUMBER,
    FIND,
    TCFA,
    TDFA,
    CREATE,
    COMMA,
    LBRAC,
    RBRAC,
    IMMEDIATE,
    HIDDEN,
    COLON,
    SEMICOLON,
    TICK,
    BRANCH,
    ZBRANCH,
    LITSTRING,
    TELL,
    INTERPRET,
    QUIT,
    CHAR,
    EXECUTE,
    SYSCALL3,
    SYSCALL2,
    SYSCALL1,
};

#define RTOP 0x1000 /* R0 as a cell index; the memory window RSP@ shows ends here */
#define WINDOW 256 /* cells of the return-stack window, taken from the top of the old return stack region */
#define S0_CELL (RTOP - WINDOW) /* the data stack grows down from here */

static int rodata[] = {
    /* STATE      */ [5120] =    0,
    /* HERE       */ [5121] = 5559 << 2,
    /* LATEST     */ [5122] = 5554 << 2,
    /* S0         */ [5123] = S0_CELL << 2,
    /* BASE       */ [5124] =   10,
    /* DROP       */ [5133] =    0 << 2, [5134] = 0x4f524404, [5135] = 0x00000050, [5136] = DROP,
    /* SWAP       */ [5137] = 5133 << 2, [5138] = 0x41575304, [5139] = 0x00000050, [5140] = SWAP,
    /* DUP        */ [5141] = 5137 << 2, [5142] = 0x50554403, [5143] = DUP,
    /* OVER       */ [5144] = 5141 << 2, [5145] = 0x45564f04, [5146] = 0x00000052, [5147] = OVER,
    /* ROT        */ [5148] = 5144 << 2, [5149] = 0x544f5203, [5150] = ROT,
    /* -ROT       */ [5151] = 5148 << 2, [5152] = 0x4f522d04, [5153] = 0x00000054, [5154] = NROT,
    /* 2DROP      */ [5155] = 5151 << 2, [5156] = 0x52443205, [5157] = 0x0000504f, [5158] = TWODROP,
    /* 2DUP       */ [5159] = 5155 << 2, [5160] = 0x55443204, [5161] = 0x00000050, [5162] = TWODUP,
    /* 2SWAP      */ [5163] = 5159 << 2, [5164] = 0x57533205, [5165] = 0x00005041, [5166] = TWOSWAP,
    /* ?DUP       */ [5167] = 5163 << 2, [5168] = 0x55443f04, [5169] = 0x00000050, [5170] = QDUP,
    /* 1+         */ [5171] = 5167 << 2, [5172] = 0x002b3102, [5173] = INCR,
    /* 1-         */ [5174] = 5171 << 2, [5175] = 0x002d3102, [5176] = DECR,
    /* 4+         */ [5177] = 5174 << 2, [5178] = 0x002b3402, [5179] = INCR4,
    /* 4-         */ [5180] = 5177 << 2, [5181] = 0x002d3402, [5182] = DECR4,
    /* +          */ [5183] = 5180 << 2, [5184] = 0x00002b01, [5185] = ADD,
    /* -          */ [5186] = 5183 << 2, [5187] = 0x00002d01, [5188] = SUB,
    /* *          */ [5189] = 5186 << 2, [5190] = 0x00002a01, [5191] = MUL,
    /* /MOD       */ [5192] = 5189 << 2, [5193] = 0x4f4d2f04, [5194] = 0x00000044, [5195] = DIVMOD,
    /* =          */ [5196] = 5192 << 2, [5197] = 0x00003d01, [5198] = EQU,
    /* <>         */ [5199] = 5196 << 2, [5200] = 0x003e3c02, [5201] = NEQU,
    /* <          */ [5202] = 5199 << 2, [5203] = 0x00003c01, [5204] = LT,
    /* >          */ [5205] = 5202 << 2, [5206] = 0x00003e01, [5207] = GT,
    /* <=         */ [5208] = 5205 << 2, [5209] = 0x003d3c02, [5210] = LE,
    /* >=         */ [5211] = 5208 << 2, [5212] = 0x003d3e02, [5213] = GE,
    /* 0=         */ [5214] = 5211 << 2, [5215] = 0x003d3002, [5216] = ZEQU,
    /* 0<>        */ [5217] = 5214 << 2, [5218] = 0x3e3c3003, [5219] = ZNEQU,
    /* 0<         */ [5220] = 5217 << 2, [5221] = 0x003c3002, [5222] = ZLT,
    /* 0>         */ [5223] = 5220 << 2, [5224] = 0x003e3002, [5225] = ZGT,
    /* 0<=        */ [5226] = 5223 << 2, [5227] = 0x3d3c3003, [5228] = ZLE,
    /* 0>=        */ [5229] = 5226 << 2, [5230] = 0x3d3e3003, [5231] = ZGE,
    /* AND        */ [5232] = 5229 << 2, [5233] = 0x444e4103, [5234] = AND,
    /* OR         */ [5235] = 5232 << 2, [5236] = 0x00524f02, [5237] = OR,
    /* XOR        */ [5238] = 5235 << 2, [5239] = 0x524f5803, [5240] = XOR,
    /* INVERT     */ [5241] = 5238 << 2, [5242] = 0x564e4906, [5243] = 0x00545245, [5244] = INVERT,
    /* EXIT       */ [5245] = 5241 << 2, [5246] = 0x49584504, [5247] = 0x00000054, [5248] = EXIT,
    /* LIT        */ [5249] = 5245 << 2, [5250] = 0x54494c03, [5251] = LIT,
    /* !          */ [5252] = 5249 << 2, [5253] = 0x00002101, [5254] = STORE,
    /* @          */ [5255] = 5252 << 2, [5256] = 0x00004001, [5257] = FETCH,
    /* +!         */ [5258] = 5255 << 2, [5259] = 0x00212b02, [5260] = ADDSTORE,
    /* -!         */ [5261] = 5258 << 2, [5262] = 0x00212d02, [5263] = SUBSTORE,
    /* C!         */ [5264] = 5261 << 2, [5265] = 0x00214302, [5266] = STOREBYTE,
    /* C@         */ [5267] = 5264 << 2, [5268] = 0x00404302, [5269] = FETCHBYTE,
    /* C@C!       */ [5270] = 5267 << 2, [5271] = 0x43404304, [5272] = 0x00000021, [5273] = CCOPY,
    /* CMOVE      */ [5274] = 5270 << 2, [5275] = 0x4f4d4305, [5276] = 0x00004556, [5277] = CMOVE,
    /* STATE      */ [5278] = 5274 << 2, [5279] = 0x41545305, [5280] = 0x00004554, [5281] = STATE,
    /* HERE       */ [5282] = 5278 << 2, [5283] = 0x52454804, [5284] = 0x00000045, [5285] = HERE,
    /* LATEST     */ [5286] = 5282 << 2, [5287] = 0x54414c06, [5288] = 0x00545345, [5289] = LATEST,
    /* S0         */ [5290] = 5286 << 2, [5291] = 0x00305302, [5292] = SZ,
    /* BASE       */ [5293] = 5290 << 2, [5294] = 0x53414204, [5295] = 0x00000045, [5296] = BASE,
    /* VERSION    */ [5297] = 5293 << 2, [5298] = 0x52455607, [5299] = 0x4e4f4953, [5300] = VERSION,
    /* R0         */ [5301] = 5297 << 2, [5302] = 0x00305202, [5303] = RZ,
    /* DOCOL      */ [5304] = 5301 << 2, [5305] = 0x434f4405, [5306] = 0x00004c4f, [5307] = DOCOL_,
    /* F_IMMED    */ [5308] = 5304 << 2, [5309] = 0x495f4607, [5310] = 0x44454d4d, [5311] = F_IMMED,
    /* F_HIDDEN   */ [5312] = 5308 << 2, [5313] = 0x485f4608, [5314] = 0x45444449, [5315] = 0x0000004e, [5316] = F_HIDDEN,
    /* F_LENMASK  */ [5317] = 5312 << 2, [5318] = 0x4c5f4609, [5319] = 0x414d4e45, [5320] = 0x00004b53, [5321] = F_LENMASK,
    /* SYS_EXIT   */ [5322] = 5317 << 2, [5323] = 0x53595308, [5324] = 0x4958455f, [5325] = 0x00000054, [5326] = SYS_EXIT,
    /* SYS_OPEN   */ [5327] = 5322 << 2, [5328] = 0x53595308, [5329] = 0x45504f5f, [5330] = 0x0000004e, [5331] = SYS_OPEN,
    /* SYS_CLOSE  */ [5332] = 5327 << 2, [5333] = 0x53595309, [5334] = 0x4f4c435f, [5335] = 0x00004553, [5336] = SYS_CLOSE,
    /* SYS_READ   */ [5337] = 5332 << 2, [5338] = 0x53595308, [5339] = 0x4145525f, [5340] = 0x00000044, [5341] = SYS_READ,
    /* SYS_WRITE  */ [5342] = 5337 << 2, [5343] = 0x53595309, [5344] = 0x4952575f, [5345] = 0x00004554, [5346] = SYS_WRITE,
    /* SYS_CREAT  */ [5347] = 5342 << 2, [5348] = 0x53595309, [5349] = 0x4552435f, [5350] = 0x00005441, [5351] = SYS_CREAT,
    /* SYS_BRK    */ [5352] = 5347 << 2, [5353] = 0x53595307, [5354] = 0x4b52425f, [5355] = SYS_BRK,
    /* O_RDONLY   */ [5356] = 5352 << 2, [5357] = 0x525f4f08, [5358] = 0x4c4e4f44, [5359] = 0x00000059, [5360] = O_RDONLY_,
    /* O_WRONLY   */ [5361] = 5356 << 2, [5362] = 0x575f4f08, [5363] = 0x4c4e4f52, [5364] = 0x00000059, [5365] = O_WRONLY_,
    /* O_RDWR     */ [5366] = 5361 << 2, [5367] = 0x525f4f06, [5368] = 0x00525744, [5369] = O_RDWR_,
    /* O_CREAT    */ [5370] = 5366 << 2, [5371] = 0x435f4f07, [5372] = 0x54414552, [5373] = O_CREAT_,
    /* O_EXCL     */ [5374] = 5370 << 2, [5375] = 0x455f4f06, [5376] = 0x004c4358, [5377] = O_EXCL_,
    /* O_TRUNC    */ [5378] = 5374 << 2, [5379] = 0x545f4f07, [5380] = 0x434e5552, [5381] = O_TRUNC_,
    /* O_APPEND   */ [5382] = 5378 << 2, [5383] = 0x415f4f08, [5384] = 0x4e455050, [5385] = 0x00000044, [5386] = O_APPEND_,
    /* O_NONBLOCK */ [5387] = 5382 << 2, [5388] = 0x4e5f4f0a, [5389] = 0x4c424e4f, [5390] = 0x004b434f, [5391] = O_NONBLOCK_,
    /* >R         */ [5392] = 5387 << 2, [5393] = 0x00523e02, [5394] = TOR,
    /* R>         */ [5395] = 5392 << 2, [5396] = 0x003e5202, [5397] = FROMR,
    /* RSP@       */ [5398] = 5395 << 2, [5399] = 0x50535204, [5400] = 0x00000040, [5401] = RSPFETCH,
    /* RSP!       */ [5402] = 5398 << 2, [5403] = 0x50535204, [5404] = 0x00000021, [5405] = RSPSTORE,
    /* RDROP      */ [5406] = 5402 << 2, [5407] = 0x52445205, [5408] = 0x0000504f, [5409] = RDROP,
    /* DSP@       */ [5410] = 5406 << 2, [5411] = 0x50534404, [5412] = 0x00000040, [5413] = DSPFETCH,
    /* DSP!       */ [5414] = 5410 << 2, [5415] = 0x50534404, [5416] = 0x00000021, [5417] = DSPSTORE,
    /* KEY        */ [5418] = 5414 << 2, [5419] = 0x59454b03, [5420] = KEY,
    /* EMIT       */ [5421] = 5418 << 2, [5422] = 0x494d4504, [5423] = 0x00000054, [5424] = EMIT,
    /* WORD       */ [5425] = 5421 << 2, [5426] = 0x524f5704, [5427] = 0x00000044, [5428] = WORD,
    /* NUMBER     */ [5429] = 5425 << 2, [5430] = 0x4d554e06, [5431] = 0x00524542, [5432] = NUMBER,
    /* FIND       */ [5433] = 5429 << 2, [5434] = 0x4e494604, [5435] = 0x00000044, [5436] = FIND,
    /* >CFA       */ [5437] = 5433 << 2, [5438] = 0x46433e04, [5439] = 0x00000041, [5440] = TCFA,
    /* >DFA       */ [5441] = 5437 << 2, [5442] = 0x46443e04, [5443] = 0x00000041, [5444] = 0, [5445] = 5440 << 2, [5446] = 5179 << 2, [5447] = 5248 << 2,
    /* CREATE     */ [5448] = 5441 << 2, [5449] = 0x45524306, [5450] = 0x00455441, [5451] = CREATE,
    /* ,          */ [5452] = 5448 << 2, [5453] = 0x00002c01, [5454] = COMMA,
    /* [          */ [5455] = 5452 << 2, [5456] = 0x00005b81, [5457] = LBRAC,
    /* ]          */ [5458] = 5455 << 2, [5459] = 0x00005d01, [5460] = RBRAC,
    /* IMMEDIATE  */ [5461] = 5458 << 2, [5462] = 0x4d4d4989, [5463] = 0x41494445, [5464] = 0x00004554, [5465] = IMMEDIATE,
    /* HIDDEN     */ [5466] = 5461 << 2, [5467] = 0x44494806, [5468] = 0x004e4544, [5469] = HIDDEN,
    /* HIDE       */ [5470] = 5466 << 2, [5471] = 0x44494804, [5472] = 0x00000045, [5473] = 0, [5474] = 5428 << 2, [5475] = 5436 << 2, [5476] = 5469 << 2, [5477] = 5248 << 2,
    /* :          */ [5478] = 5470 << 2, [5479] = 0x00003a01, [5480] = 0, [5481] = 5428 << 2, [5482] = 5451 << 2, [5483] = 5251 << 2, [5484] = 0, [5485] = 5454 << 2, [5486] = 5289 << 2, [5487] = 5257 << 2, [5488] = 5469 << 2, [5489] = 5460 << 2, [5490] = 5248 << 2,
    /* ;          */ [5491] = 5478 << 2, [5492] = 0x00003b81, [5493] = 0, [5494] = 5251 << 2, [5495] = 5248 << 2, [5496] = 5454 << 2, [5497] = 5289 << 2, [5498] = 5257 << 2, [5499] = 5469 << 2, [5500] = 5457 << 2, [5501] = 5248 << 2,
    /* '          */ [5502] = 5491 << 2, [5503] = 0x00002701, [5504] = TICK,
    /* BRANCH     */ [5505] = 5502 << 2, [5506] = 0x41524206, [5507] = 0x0048434e, [5508] = BRANCH,
    /* 0BRANCH    */ [5509] = 5505 << 2, [5510] = 0x52423007, [5511] = 0x48434e41, [5512] = ZBRANCH,
    /* LITSTRING  */ [5513] = 5509 << 2, [5514] = 0x54494c09, [5515] = 0x49525453, [5516] = 0x0000474e, [5517] = LITSTRING,
    /* TELL       */ [5518] = 5513 << 2, [5519] = 0x4c455404, [5520] = 0x0000004c, [5521] = TELL,
    /* INTERPRET  */ [5522] = 5518 << 2, [5523] = 0x544e4909, [5524] = 0x52505245, [5525] = 0x00005445, [5526] = INTERPRET,
    /* QUIT       */ [5527] = 5522 << 2, [5528] = 0x49555104, [5529] = 0x00000054, [5530] = 0, [5531] = 5303 << 2, [5532] = 5405 << 2, [5533] = 5526 << 2, [5534] = 5508 << 2, [5535] = -8,
    /* CHAR       */ [5536] = 5527 << 2, [5537] = 0x41484304, [5538] = 0x00000052, [5539] = CHAR,
    /* EXECUTE    */ [5540] = 5536 << 2, [5541] = 0x45584507, [5542] = 0x45545543, [5543] = EXECUTE,
    /* SYSCALL3   */ [5544] = 5540 << 2, [5545] = 0x53595308, [5546] = 0x4c4c4143, [5547] = 0x00000033, [5548] = SYSCALL3,
    /* SYSCALL2   */ [5549] = 5544 << 2, [5550] = 0x53595308, [5551] = 0x4c4c4143, [5552] = 0x00000032, [5553] = SYSCALL2,
    /* SYSCALL1   */ [5554] = 5549 << 2, [5555] = 0x53595308, [5556] = 0x4c4c4143, [5557] = 0x00000031, [5558] = SYSCALL1,
};
static int *memory;

/* One return-stack node: `value` is whatever was pushed, a return address (as a byte address, like jonesforth) for DOCOL. */
struct frame {
    struct frame *parent;
    int value;
    bool on_heap;
};

#ifndef NURSERY
#define NURSERY 256 /* pushes on the C stack before the live nodes are evacuated */
#endif
#define HEAP_FRAMES (1 << 20)

struct regs {
    int ip, sp;
};

static struct frame heap[HEAP_FRAMES]; /* heap[0] is the root; evacuated nodes are a stack above it */
static jmp_buf reset;
static int nursery; /* pushes since the C stack was last reset */
static struct frame *cont; /* top of the return stack: the node EXIT pops */
static struct regs resume;

/* Code field of the first THROW and the address of the first EXCEPTION-MARKER's RDROP, recorded by CREATE. */
static int throw_cfa, marker;

#define QUIT_CFA 5530 /* code field of QUIT in rodata above */
#define WORD_MAX 0x20 /* bytes between the token buffer at 0x5014 and DROP's header */
#define NAME_LEN 0x1F /* length bits of a header's flag byte, the rest being IMMEDIATE and HIDDEN */
#define NAME_HIDDEN 0x20
#define SP_MIN 16 /* lowest data stack cell, with room for what one word pushes */
#define HERE_MAX (ARENA - 0x1000u) /* dictionary limit; the rest is scratch for PAD */

unsigned char key(void) {
    static int currkey = 0x4000, buftop = 0x4000;
    ssize_t c;

    while (buftop <= currkey) {
        currkey = 0x4000;
        c = read(STDIN_FILENO, bytes + currkey, 0x1000);
        if (c < 0) {
            char *s = strerror(errno);
            write(STDERR_FILENO, s, strlen(s));
            exit(EIO);
        }
        if (c == 0)
            exit(0); /* EOF: exit cleanly like jonesforth.S's _KEY rather than spin */
        buftop = (int)(0x4000 + c); /* c <= the 0x1000 just requested, well within int range */
    }
    return (unsigned char)bytes[currkey++];
}

int word(void) {
    unsigned char ch;
    char *s = bytes + 0x5014;

    do
    {
        ch = key();
        if (ch == '\\') /* comment ⇒ skip line */
            do
                ch = key();
            while (ch != '\n');
    } while (ch <= ' ');

    do
    {
        if (s < bytes + 0x5014 + WORD_MAX) /* truncate overlong tokens, still consuming them */
            *s++ = (char)ch;
        ch = key();
    } while (ch > ' ');

    return (int)(s - (bytes + 0x5014)); /* word length, always far under INT_MAX */
}

int find(int count, int name) {
    int word = memory[0x1402]; /* LATEST */

    while (word && (((bytes[word + 4] & (NAME_HIDDEN | NAME_LEN)) != count) || memcmp(bytes + word + 5, bytes + name, (unsigned)count)))
        word = memory[word >> 2];

    return word;
}

struct num_t {
    int result;
    int remaining;
};

struct num_t number(int n, int s) {
    int digit, sign = 1, base = memory[0x1404];
    unsigned res = 0; /* wraps instead of overflowing */

    if (n <= 0)
        return (struct num_t) { .result = 0, .remaining = 1 }; /* nothing to parse is not the number 0 */
    if (n > 1 && (bytes[s] == '-' || bytes[s] == '+')) { /* a lone sign is left unparsed */
        if (bytes[s] == '-')
            sign = -1;
        --n;
        ++s;
    }

    do {
        res *= (unsigned)base;
        digit = bytes[s++] - '0';
        if (digit < 0)
            break;
        if (digit > 9) {
            digit -= 7; /* 'A' - '0' - 10*/
            if (digit < 10)
                break;
        }
        if (digit >= base)
            break;
        res += (unsigned)digit;
    } while (--n);

    return (struct num_t) { .result = (int)(res * (unsigned)sign), .remaining = n };
}

int code_field_address(int word) {
    word += 4;
    word += (bytes[word] & NAME_LEN) + 4;
    word &= ~3;
    return word;
}

static int brk_off = 0x10000;

int do_brk(int requested) {
    /* jonesforth's brk(2): returns the (possibly unchanged, on failure) new break as an offset into memory. */
    if (requested > brk_off && requested <= ARENA)
        brk_off = requested;
    return brk_off;
}

void *set_up_data_segment(const void *src, size_t n) {
    void *here = calloc(ARENA, 1);
    if (here == NULL)
        exit(ENOMEM);

    return memcpy(here, src, n);
}

/* Restart QUIT on an empty return stack: the C stack and every node on it are abandoned. */
static void quit(int sp) {
    heap[0] = (struct frame){.on_heap = true};
    cont = heap;
    resume.ip = QUIT_CFA + 1;
    resume.sp = sp;
    longjmp(reset, 1);
}

/* Copy the stack nodes of the chain k onto the heap stack, leaving room for `extra` more, and return the copy of k. */
static struct frame *evacuate(struct frame *k, int extra, int sp) {
    struct frame *old = k, *to;
    int n = 0;

    while (!old->on_heap) {
        old = old->parent;
        ++n;
    }
    to = old + 1; /* everything above the oldest live heap node is dead */
    if ((to - heap) + n + extra > HEAP_FRAMES) {
        static const char msg[] = "RETURN STACK OVERFLOW\n";
        (void)(write(STDERR_FILENO, msg, sizeof msg - 1) + 1);
        quit(sp);
    }
    for (int i = n; i--; k = k->parent) {
        to[i] = *k;
        to[i].on_heap = true;
        to[i].parent = i ? &to[i - 1] : old;
    }
    return to + n - 1;
}

static int wrap_add(int x, int y) {
    return (int)((unsigned)x + (unsigned)y);
}

static int wrap_sub(int x, int y) {
    return (int)((unsigned)x - (unsigned)y);
}

static int wrap_mul(int x, int y) {
    return (int)((unsigned)x * (unsigned)y);
}

/* Print a diagnostic and restart QUIT with empty stacks and out of compile mode. */
static void fail(const char *msg) {
    (void)(write(STDERR_FILENO, msg, strlen(msg)) + 1);
    memory[0x1400] = 0;
    quit(S0_CELL);
}

/* The data stack left its cells: below SP_MIN is overflow, above S0 underflow. */
static bool bad_sp(int sp) {
    return (unsigned)(sp - SP_MIN) > (unsigned)(S0_CELL - SP_MIN);
}

static void stack_fault(int sp) {
    fail(sp > S0_CELL ? "STACK UNDERFLOW\n" : "STACK OVERFLOW\n");
}

static bool no_room(unsigned n) {
    return (unsigned)memory[0x1401] > HERE_MAX - n;
}

static void run(int ip, int sp);

/* Push value as a node on the C stack and continue at ip, never returning; past NURSERY pushes the live nodes are evacuated first. */
static void push(int value, int ip, int sp) {
    struct frame f = {.parent = cont, .value = value};

    if (++nursery > NURSERY) {
        cont = evacuate(&f, 0, sp);
        resume.ip = ip;
        resume.sp = sp;
        longjmp(reset, 1);
    }
    cont = &f;
    run(ip, sp);
}

/* How many of the top nodes RSP@ shows. */
static int shown(void) {
    int m = 0;

    for (const struct frame *p = cont; m < WINDOW && p->parent; p = p->parent)
        ++m;
    return m;
}

/* RSP@: copy the top nodes into the window, top at the lowest address, and return that address. */
static int rsp_fetch(void) {
    const int m = shown();
    const struct frame *p = cont;

    for (int i = 0; i < m; ++i, p = p->parent)
        memory[RTOP - m + i] = p->value;
    return (RTOP - m) << 2;
}

/* RSP!: addr is read like RSP@'s result, counting cells up from R0; pop down to it, or push the window cells below the top. */
static void rsp_store(int addr, int sp) {
    int m = shown(), e = RTOP - (addr >> 2);

    if (e < 0)
        e = 0;
    if (e > WINDOW)
        e = WINDOW;
    for (; m > e; --m)
        cont = cont->parent;
    if (m < e) {
        struct frame *p = evacuate(cont, e - m, sp);

        for (int i = e - m; i--; ++p)
            p[1] = (struct frame){.parent = p, .value = memory[RTOP - e + i], .on_heap = true};
        cont = p;
    }
}

/* THROW with a CATCH on the return stack: pop to its marker like jonesforth.f's THROW does, resuming after the CATCH; ip is 0 if there is none. */
static struct regs do_throw(int sp) {
    const struct frame *m = cont, *d, *r;
    const int n = memory[sp];

    while (m->parent && m->value != marker)
        m = m->parent;
    d = m->parent;
    r = d ? d->parent : NULL;
    if (!r || !r->parent)
        return (struct regs){0, sp};
    sp = (d->value >> 2) - 1;
    memory[sp] = n;
    cont = r->parent;
    return (struct regs){r->value >> 2, sp};
}

/* The loop below never returns: DOCOL and >R continue it through push(). */
static void run(int ip, int sp) {
    register int cfa;
    register int a, b, c, d;
    struct num_t num;

    cfa = memory[ip++] >> 2;

    while (1) {
        switch (memory[cfa]) {
            case DOCOL:
                if (bad_sp(sp))
                    stack_fault(sp);
                if (cfa == QUIT_CFA)
                    quit(sp);
                if (cfa == throw_cfa && marker && memory[sp]) {
                    struct regs r = do_throw(sp);

                    if (r.ip) {
                        ip = r.ip;
                        sp = r.sp;
                        break;
                    }
                }
                push(ip << 2, cfa + 1, sp);
                return;
            case DROP:
                ++sp;
                break;
            case SWAP:
                a = memory[sp + 1];
                memory[sp + 1] = memory[sp];
                memory[sp] = a;
                break;
            case DUP:
                --sp;
                memory[sp] = memory[sp + 1];
                break;
            case OVER:
                --sp;
                memory[sp] = memory[sp + 2];
                break;
            case ROT:
                a = memory[sp + 0];
                b = memory[sp + 1];
                c = memory[sp + 2];
                memory[sp + 2] = b;
                memory[sp + 1] = a;
                memory[sp + 0] = c;
                break;
            case NROT:
                a = memory[sp + 0];
                b = memory[sp + 1];
                c = memory[sp + 2];
                memory[sp + 2] = a;
                memory[sp + 1] = c;
                memory[sp + 0] = b;
                break;
            case TWODROP:
                sp += 2;
                break;
            case TWODUP:
                sp -= 2;
                memory[sp + 0] = memory[sp + 2];
                memory[sp + 1] = memory[sp + 3];
                break;
            case TWOSWAP:
                a = memory[sp + 0];
                b = memory[sp + 1];
                c = memory[sp + 2];
                d = memory[sp + 3];
                memory[sp + 3] = b;
                memory[sp + 2] = a;
                memory[sp + 1] = d;
                memory[sp + 0] = c;
                break;
            case QDUP:
                a = memory[sp];
                if (a)
                    memory[--sp] = a;
                break;
            case INCR:
                memory[sp] = wrap_add(memory[sp], 1);
                break;
            case DECR:
                memory[sp] = wrap_sub(memory[sp], 1);
                break;
            case INCR4:
                memory[sp] = wrap_add(memory[sp], 4);
                break;
            case DECR4:
                memory[sp] = wrap_sub(memory[sp], 4);
                break;
            case ADD:
                memory[sp + 1] = wrap_add(memory[sp + 1], memory[sp]);
                ++sp;
                break;
            case SUB:
                memory[sp + 1] = wrap_sub(memory[sp + 1], memory[sp]);
                ++sp;
                break;
            case MUL:
                memory[sp + 1] = wrap_mul(memory[sp + 1], memory[sp]);
                ++sp;
                break;
            case DIVMOD:
                a = memory[sp + 1];
                b = memory[sp + 0];
                if (!b) {
                    (void)(write(STDERR_FILENO, "DIVISION BY ZERO\n", 17) + 1);
                    break;
                }
                /* b == -1 would trap on INT_MIN; negate unsigned to wrap instead */
                memory[sp + 1] = b == -1 ? 0 : a % b;
                memory[sp + 0] = b == -1 ? wrap_sub(0, a) : a / b;
                break;
            case EQU:
                memory[sp + 1] = memory[sp + 1] == memory[sp];
                ++sp;
                break;
            case NEQU:
                memory[sp + 1] = memory[sp + 1] != memory[sp];
                ++sp;
                break;
            case LT:
                memory[sp + 1] = memory[sp + 1] < memory[sp];
                ++sp;
                break;
            case GT:
                memory[sp + 1] = memory[sp + 1] > memory[sp];
                ++sp;
                break;
            case LE:
                memory[sp + 1] = memory[sp + 1] <= memory[sp];
                ++sp;
                break;
            case GE:
                memory[sp + 1] = memory[sp + 1] >= memory[sp];
                ++sp;
                break;
            case ZEQU:
                memory[sp] = !memory[sp];
                break;
            case ZNEQU:
                memory[sp] = memory[sp] != 0;
                break;
            case ZLT:
                memory[sp] = memory[sp] < 0;
                break;
            case ZGT:
                memory[sp] = memory[sp] > 0;
                break;
            case ZLE:
                memory[sp] = memory[sp] <= 0;
                break;
            case ZGE:
                memory[sp] = memory[sp] >= 0;
                break;
            case AND:
                memory[sp + 1] &= memory[sp];
                ++sp;
                break;
            case OR:
                memory[sp + 1] |= memory[sp];
                ++sp;
                break;
            case XOR:
                memory[sp + 1] ^= memory[sp];
                ++sp;
                break;
            case INVERT:
                memory[sp] = ~memory[sp];
                break;
            case EXIT:
                if (!cont->parent)
                    quit(sp);
                ip = cont->value >> 2;
                cont = cont->parent;
                break;
            case LIT:
                memory[--sp] = memory[ip++];
                break;
            case STORE:
                memory[memory[sp] >> 2] = memory[sp + 1];
                sp += 2;
                break;
            case FETCH:
                memory[sp] = memory[memory[sp] >> 2];
                break;
            case ADDSTORE:
                memory[memory[sp] >> 2] = wrap_add(memory[memory[sp] >> 2], memory[sp + 1]);
                sp += 2;
                break;
            case SUBSTORE:
                memory[memory[sp] >> 2] = wrap_sub(memory[memory[sp] >> 2], memory[sp + 1]);
                sp += 2;
                break;
            case STOREBYTE:
                bytes[memory[sp]] = (char)memory[sp + 1];
                sp += 2;
                break;
            case FETCHBYTE:
                memory[sp] = (unsigned char)bytes[memory[sp]];
                break;
            case CCOPY:
                /* ( source dest -- source+1 dest+1 ), per jonesforth.S: dest
                   is on top, source is one cell below; both addresses are
                   left incremented. */
                bytes[memory[sp]] = bytes[memory[sp + 1]];
                ++memory[sp];
                ++memory[sp + 1];
                break;
            case CMOVE:
                (void)memmove(bytes + memory[sp + 1], bytes + memory[sp + 2], (size_t)memory[sp]);
                sp += 3;
                break;
            case STATE:
                memory[--sp] = 0x1400 << 2;
                break;
            case HERE:
                memory[--sp] = 0x1401 << 2;
                break;
            case LATEST:
                memory[--sp] = 0x1402 << 2;
                break;
            case SZ:
                memory[--sp] = 0x1403 << 2;
                break;
            case BASE:
                memory[--sp] = 0x1404 << 2;
                break;
            case VERSION:
                memory[--sp] = 47;
                break;
            case RZ:
                memory[--sp] = 0x1000 << 2;
                break;
            case DOCOL_:
                memory[--sp] = 0;
                break;
            case F_IMMED:
                memory[--sp] = 0x80;
                break;
            case F_HIDDEN:
                memory[--sp] = 0x20;
                break;
            case F_LENMASK:
                memory[--sp] = 0x1F;
                break;
            case SYS_EXIT:
                memory[--sp] = SYS_exit;
                break;
            case SYS_OPEN:
                memory[--sp] = SYS_open;
                break;
            case SYS_CLOSE:
                memory[--sp] = SYS_close;
                break;
            case SYS_READ:
                memory[--sp] = SYS_read;
                break;
            case SYS_WRITE:
                memory[--sp] = SYS_write;
                break;
            case SYS_CREAT:
                memory[--sp] = SYS_creat;
                break;
            case SYS_BRK:
                memory[--sp] = SYS_brk;
                break;
            case O_RDONLY_:
                memory[--sp] = O_RDONLY;
                break;
            case O_WRONLY_:
                memory[--sp] = O_WRONLY;
                break;
            case O_RDWR_:
                memory[--sp] = O_RDWR;
                break;
            case O_CREAT_:
                memory[--sp] = O_CREAT;
                break;
            case O_EXCL_:
                memory[--sp] = O_EXCL;
                break;
            case O_TRUNC_:
                memory[--sp] = O_TRUNC;
                break;
            case O_APPEND_:
                memory[--sp] = O_APPEND;
                break;
            case O_NONBLOCK_:
                memory[--sp] = O_NONBLOCK;
                break;
            case TOR:
                push(memory[sp], ip, sp + 1);
                return;
            case FROMR:
                a = 0;
                if (cont->parent) {
                    a = cont->value;
                    cont = cont->parent;
                }
                memory[--sp] = a;
                break;
            case RSPFETCH:
                memory[--sp] = rsp_fetch();
                break;
            case RSPSTORE:
                rsp_store(memory[sp], sp + 1);
                ++sp;
                break;
            case RDROP:
                if (cont->parent)
                    cont = cont->parent;
                break;
            case DSPFETCH:
                a = sp--;
                memory[sp] = a << 2;
                break;
            case DSPSTORE:
                sp = memory[sp] >> 2;
                break;
            case KEY:
                memory[--sp] = key();
                break;
            case EMIT:
                (void)(write(STDOUT_FILENO, memory + sp++, 1) + 1);
                break;
            case WORD:
                memory[--sp] = 0x5014;
                memory[--sp] = word();
                break;
            case NUMBER:
                num = number(memory[sp], memory[sp + 1]);
                memory[sp + 1] = num.result;
                memory[sp + 0] = num.remaining;
                break;
            case FIND:
                memory[sp + 1] = find(memory[sp], memory[sp + 1]);
                ++sp;
                break;
            case TCFA:
                memory[sp] = code_field_address(memory[sp]);
                break;
            case CREATE:
                if (no_room(64))
                    fail("OUT OF MEMORY\n");
                a = memory[0x1401];
                c = memory[sp] & NAME_LEN; /* a 32-character name keeps no length and is never found */
                memory[a >> 2] = memory[0x1402];
                bytes[a + 4] = (char)c;
                memcpy(bytes + a + 5, bytes + memory[sp + 1], (size_t)c);
                memory[0x1401] = code_field_address(a);
                memory[0x1402] = a;
                if (!throw_cfa && memory[sp] == 5 && !memcmp(bytes + a + 5, "THROW", 5))
                    throw_cfa = memory[0x1401] >> 2;
                else if (!marker && memory[sp] == 16 && !memcmp(bytes + a + 5, "EXCEPTION-MARKER", 16))
                    marker = memory[0x1401] + 4;
                sp += 2;
                break;
            case COMMA:
                if (no_room(4))
                    fail("OUT OF MEMORY\n");
                memory[memory[0x1401] >> 2] = memory[sp++];
                memory[0x1401] += 4;
                break;
            case LBRAC:
                memory[0x1400] = 0;
                break;
            case RBRAC:
                memory[0x1400] = 1;
                break;
            case IMMEDIATE:
                memory[(memory[0x1402] >> 2) + 1] ^= 0x80;
                break;
            case HIDDEN:
                memory[(memory[sp++] >> 2) + 1] ^= 0x20;
                break;
            case TICK:
                memory[--sp] = memory[ip++];
                break;
            case BRANCH:
                if (bad_sp(sp)) /* loops that never reach INTERPRET or a call still get checked */
                    stack_fault(sp);
                ip += memory[ip] >> 2;
                break;
            case ZBRANCH:
                if (bad_sp(sp))
                    stack_fault(sp);
                ip += memory[sp++] ? 1 : memory[ip] >> 2;
                break;
            case LITSTRING:
                memory[--sp] = (ip + 1) << 2;
                memory[--sp] = memory[ip];
                ip += 1 + ((memory[ip] + 3) >> 2);
                break;
            case TELL:
                (void)(write(STDOUT_FILENO, bytes + memory[sp + 1], (size_t)memory[sp]) + 1);
                sp += 2;
                break;
            case INTERPRET:
                if (sp > S0_CELL) { /* underflow is noticed after the fact, like 4th.c and 5th.c do */
                    (void)(write(STDERR_FILENO, "STACK UNDERFLOW\n", 16) + 1);
                    sp = S0_CELL;
                } else if (sp < SP_MIN)
                    fail("STACK OVERFLOW\n");
                if (memory[0x1400] && no_room(8))
                    fail("OUT OF MEMORY\n");
                a = word();
                b = find(a, 0x5014);
                if (b) {
                    cfa = code_field_address(b);
                    if ((bytes[b + 4] & 0x80) || !memory[0x1400]) {
                        cfa >>= 2;
                        continue;
                    }
                    memory[memory[0x1401] >> 2] = cfa;
                    memory[0x1401] += 4;
                } else {
                    num = number(a, 0x5014);
                    if (num.remaining) {
                        (void)(write(STDERR_FILENO, "PARSE ERROR: ", 13) + 1);
                        (void)(write(STDERR_FILENO, bytes + 0x5014, (size_t)a) + 1);
                        (void)(write(STDERR_FILENO, "\n", 1) + 1);
                    } else if (memory[0x1400]) {
                        memory[memory[0x1401] >> 2] = 5251 << 2; /* LIT */
                        memory[0x1401] += 4;
                        memory[memory[0x1401] >> 2] = num.result;
                        memory[0x1401] += 4;
                    } else {
                        memory[--sp] = num.result;
                    }
                }
                break;
            case CHAR:
                word();
                memory[--sp] = (unsigned char)bytes[0x5014];
                break;
            case EXECUTE:
                cfa = memory[sp++] >> 2;
                continue;
            case SYSCALL3:
                memory[sp + 3] = do_syscall3(memory[sp], memory[sp + 1], memory[sp + 2], memory[sp + 3]);
                sp += 3;
                break;
            case SYSCALL2:
                memory[sp + 2] = do_syscall2(memory[sp], memory[sp + 1], memory[sp + 2]);
                sp += 2;
                break;
            case SYSCALL1:
                memory[sp + 1] = (memory[sp] == SYS_brk)
                    ? do_brk(memory[sp + 1])
                    : do_syscall1(memory[sp], memory[sp + 1]);
                sp += 1;
                break;
        }
        cfa = memory[ip++] >> 2;
    }
}

int main(void) {
    memory = (int *)set_up_data_segment(rodata, sizeof rodata);
    bytes = (char *)memory;

    if (!setjmp(reset))
        quit(S0_CELL);
    nursery = 0;
    run(resume.ip, resume.sp);
}
