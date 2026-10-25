\ -*- forth -*-
\
\ SectorLISP (see lisp/assembly/core.ts) in FORTH (jonesforth dialect),
\ with a mark-and-sweep garbage collector.
\
\ The language is core.ts's, so lisp/eliza.lisp runs unmodified: QUOTE, COND,
\ ATOM, EQ, CAR, CDR, CONS, READ, PRINT and LAMBDA with dynamic scope, no
\ DEFINE, an unbound atom evaluates to NIL.  Only the memory manager differs:
\ core.ts compacts the heap after every EVAL, here CONS takes a node from a
\ free list and, when there is none, runs GC.
\
\ A pair is a 2-cell node in HEAP, an atom is an interned record in the
\ dictionary, so PAIR? is one range check.  MARKS has a byte per node: 0 free,
\ 1 allocated, 2 reachable.
\
\ GC's only roots are the data and return stacks.  Every value this program
\ holds lives on one of them, so GC scans both conservatively: any cell that
\ is the address of an allocated node counts.  Nodes never move, which is what
\ makes that safe.
\
\ Usage: load jonesforth.f, then this file, then
\
\   LISP
\   <lisp text on the same input, e.g. eliza.lisp>
\
\ The heap takes NNODES * (2 CELLS + 1) bytes of the dictionary: 4096 nodes
\ leave 14875 cells free on forth/wasm/tabulate.wast and jonesforth.wast,
\ which cannot grow.  A host that starts with a 64KB data segment and can grow
\ it (real jonesforth) needs `65536 MORECORE` first.
\
\ Evaluation recurses on the FORTH stacks, 2048 cells each in the wasm ports;
\ eliza.lisp nests one LOOP call per turn, so it runs out of return stack
\ after about 200 turns.
\
\ ponytail: MARK recurses on CAR using the return stack, so a left-leaning
\ chain of CARs deeper than the return stack overflows it.  Lisp data is
\ right-leaning; pointer reversal (Deutsch-Schorr-Waite) would lift the limit.

4096 CONSTANT NNODES

ALIGN
2 CELLS CONSTANT NODE
NNODES NODE * ALLOT CONSTANT HEAP
NNODES ALLOT CONSTANT MARKS
HEAP NNODES NODE * + CONSTANT HEAP-END
VARIABLE FREE
VARIABLE GCS	( collections so far )

: PAIR? ( x -- f ) DUP HEAP < IF DROP 0 ELSE HEAP-END < THEN ;

: NODE# ( x -- i 1 | 0 )	\ index of x if x is the address of an allocated node
	HEAP - DUP 0< IF DROP 0 EXIT THEN
	NODE /MOD SWAP IF DROP 0 EXIT THEN
	DUP NNODES < 0= IF DROP 0 EXIT THEN
	DUP MARKS + C@ 0= IF DROP 0 EXIT THEN
	1
;

: MARK ( x -- )		\ recurse on CAR, loop on CDR
	BEGIN
		DUP NODE# IF
			MARKS + DUP C@ 2 = IF 2DROP EXIT THEN
			2 SWAP C!
			DUP @ RECURSE
			1 CELLS + @
		ELSE
			DROP EXIT
		THEN
	AGAIN
;

: MARK-RANGE ( lo hi -- ) \ mark whatever the cells in [lo, hi) point to
	BEGIN 2DUP < WHILE
		OVER @ MARK
		SWAP 1 CELLS + SWAP
	REPEAT 2DROP
;

: SWEEP ( -- )		\ unmarked nodes become the free list, marked ones are unmarked
	0 FREE !
	NNODES BEGIN DUP WHILE
		1-
		DUP MARKS + DUP C@ 2 = IF
			1 SWAP C!
		ELSE
			0 SWAP C!
			DUP NODE * HEAP +	( i p )
			FREE @ OVER !
			FREE !
		THEN
	REPEAT DROP
;

: GC ( -- )
	1 GCS +!
	DSP@ S0 @ MARK-RANGE
	RSP@ R0 MARK-RANGE
	SWEEP
;

: INIT-HEAP ( -- )
	NNODES BEGIN DUP WHILE 1- 0 OVER MARKS + C! REPEAT DROP
	0 GCS !
	SWEEP
;
INIT-HEAP

: LCONS ( a d -- p )
	FREE @ 0= IF GC THEN
	FREE @ 0= IF ." HEAP FULL" CR BYE THEN
	FREE @ DUP @ FREE !	( a d p )
	SWAP OVER 1 CELLS + !	( a p )
	TUCK !			( p )
	DUP HEAP - NODE / MARKS + 1 SWAP C!
;

\ ---- atoms ------------------------------------------------------------

\ An atom is [link][length byte][name]; the address of the record is its identity.
VARIABLE SYMS
0 SYMS !
256 ALLOT CONSTANT TOKBUF
VARIABLE TOKLEN
VARIABLE STR1
VARIABLE STR2

: SYM-NAME ( sym -- addr len ) 1 CELLS + DUP 1+ SWAP C@ ;

: STR= ( a1 n1 a2 n2 -- f )
	ROT OVER <> IF 2DROP DROP 0 EXIT THEN	( a1 a2 n )
	ROT STR1 ! SWAP STR2 !
	BEGIN DUP WHILE
		1-
		DUP STR1 @ + C@ OVER STR2 @ + C@ <> IF DROP 0 EXIT THEN
	REPEAT DROP 1
;

: INTERN ( -- sym )	\ the atom named by TOKBUF/TOKLEN
	SYMS @
	BEGIN DUP WHILE
		DUP SYM-NAME TOKBUF TOKLEN @ STR= IF EXIT THEN
		@
	REPEAT DROP
	ALIGN HERE @
	SYMS @ ,
	TOKLEN @ C,
	TOKLEN @ 0 BEGIN 2DUP > WHILE DUP TOKBUF + C@ C, 1+ REPEAT 2DROP
	ALIGN
	DUP SYMS !
;

: SYM ( addr len -- sym ) DUP TOKLEN ! TOKBUF SWAP CMOVE INTERN ;

\ The builtins are interned first, in core.ts's order, so that "f > EQ" says
\ "user-defined atom" by comparing addresses.
S" NIL" SYM CONSTANT NIL
S" T" SYM CONSTANT T
S" QUOTE" SYM CONSTANT QUOTE
S" COND" SYM CONSTANT COND
S" READ" SYM CONSTANT READ
S" PRINT" SYM CONSTANT PRINT
S" ATOM" SYM CONSTANT ATOM
S" CAR" SYM CONSTANT CAR
S" CDR" SYM CONSTANT CDR
S" CONS" SYM CONSTANT CONS
S" EQ" SYM CONSTANT EQ

\ ---- pairs ------------------------------------------------------------

: LCAR ( x -- x ) DUP PAIR? IF @ ELSE DROP NIL THEN ;
: LCDR ( x -- x ) DUP PAIR? IF 1 CELLS + @ ELSE DROP NIL THEN ;

\ ---- reader and printer -----------------------------------------------

VARIABLE DX		( one character of lookahead )
: GETCHAR ( -- c ) DX @ KEY DX ! ;

: TOKPUT ( c -- )
	TOKLEN @ 255 < IF TOKBUF TOKLEN @ + C! 1 TOKLEN +! ELSE DROP THEN
;

\ An atom runs until a character <= ')'; "(" and ")" are tokens of their own.
: TOKEN-DONE? ( c -- c f )
	DUP 32 > IF
		DUP 41 > IF DX @ 41 > 0= ELSE 1 THEN
	ELSE
		0
	THEN
;

: GETTOKEN ( -- c )
	0 TOKLEN !
	BEGIN
		GETCHAR DUP 32 > IF DUP TOKPUT THEN
		TOKEN-DONE? 0=
	WHILE DROP REPEAT
;

\ ponytail: reading recurses once per list element (about 12 return-stack
\ cells each), so a quoted list past ~170 elements overflows; build the list
\ with a tail pointer instead if that matters.
: GETLIST ( -- list )
	GETTOKEN DUP 41 = IF DROP NIL EXIT THEN
	40 = IF RECURSE ELSE INTERN THEN
	RECURSE LCONS
;

: LREAD ( -- x ) GETTOKEN DUP 40 = IF DROP GETLIST ELSE DROP INTERN THEN ;

1 CELLS ALLOT CONSTANT BULLET-BYTES	( U+2219 as UTF-8, written in one go so a host decodes it whole )
226 BULLET-BYTES C! 136 BULLET-BYTES 1+ C! 153 BULLET-BYTES 2 + C!
: BULLET BULLET-BYTES 3 TELL ;

: LPRINT ( x -- )
	DUP PAIR? 0= IF SYM-NAME TELL EXIT THEN
	40 EMIT DUP LCAR RECURSE
	BEGIN
		LCDR DUP NIL = IF DROP 41 EMIT EXIT THEN
		DUP PAIR? IF
			SPACE DUP LCAR RECURSE
		ELSE
			BULLET RECURSE 41 EMIT EXIT
		THEN
	AGAIN
;

\ ---- evaluator --------------------------------------------------------

VARIABLE EVAL-XT
: LEVAL ( e a -- v ) EVAL-XT @ EXECUTE ;

: ASSOC ( x y -- v )
	BEGIN
		DUP NIL = IF 2DROP NIL EXIT THEN
		2DUP LCAR LCAR = IF NIP LCAR LCDR EXIT THEN
		LCDR
	AGAIN
;

: PAIRLIS ( x y a -- list )
	2 PICK NIL = IF NIP NIP EXIT THEN
	2 PICK LCAR 2 PICK LCAR LCONS >R
	ROT LCDR ROT LCDR ROT RECURSE
	R> SWAP LCONS
;

: EVLIS ( m a -- list )
	OVER NIL = IF 2DROP NIL EXIT THEN
	OVER LCAR OVER LEVAL >R
	SWAP LCDR SWAP RECURSE
	R> SWAP LCONS
;

: EVCON ( c a -- v )
	BEGIN
		OVER NIL = IF 2DROP NIL EXIT THEN
		OVER LCAR LCAR OVER LEVAL NIL <> IF
			SWAP LCAR LCDR LCAR SWAP LEVAL EXIT
		THEN
		SWAP LCDR SWAP
	AGAIN
;

: APPLY ( f x a -- v )
	2 PICK PAIR? IF			\ (LAMBDA params body)
		ROT DUP LCDR LCAR SWAP LCDR LCDR LCAR >R	( x a params ) \ R: body
		-ROT PAIRLIS R> SWAP LEVAL EXIT
	THEN
	2 PICK EQ > IF			\ user atom: apply its value
		ROT OVER ASSOC -ROT RECURSE EXIT
	THEN
	DROP				( f x )
	OVER EQ = IF NIP DUP LCAR SWAP LCDR LCAR = IF T ELSE NIL THEN EXIT THEN
	OVER CONS = IF NIP DUP LCAR SWAP LCDR LCAR LCONS EXIT THEN
	OVER ATOM = IF NIP LCAR PAIR? IF NIL ELSE T THEN EXIT THEN
	OVER CAR = IF NIP LCAR LCAR EXIT THEN
	OVER CDR = IF NIP LCAR LCDR EXIT THEN
	OVER READ = IF 2DROP LREAD EXIT THEN
	OVER PRINT = IF NIP DUP NIL = IF DROP CR ELSE LCAR LPRINT THEN NIL EXIT THEN
	2DROP NIL
;

: (EVAL) ( e a -- v )
	OVER PAIR? 0= IF ASSOC EXIT THEN
	OVER LCAR QUOTE = IF DROP LCDR LCAR EXIT THEN
	OVER LCAR COND = IF SWAP LCDR SWAP EVCON EXIT THEN
	2DUP SWAP LCDR SWAP EVLIS	( e a x )
	ROT LCAR SWAP ROT APPLY
;
: INSTALL ' (EVAL) EVAL-XT ! ;
INSTALL

: LISP ( -- )
	0 DX !
	BEGIN 42 EMIT SPACE LREAD NIL LEVAL LPRINT CR AGAIN
;
