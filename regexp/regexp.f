\ -*- forth -*-
\
\ FORTH (jonesforth dialect) implementation of Thompson's
\ on-the-fly regular expression compiler.
\
\ See also Thompson, Ken.  Regular Expression Search Algorithm,
\ Communications of the ACM 11(6) (June 1968), pp. 419-422.
\
\ This is a port of regexp/x86.c.  Where the C version malloc'd an
\ mprotect(PROT_EXEC) buffer and poked x86 opcodes into it, RE" is an
\ IMMEDIATE word which pokes threaded code into the definition that is
\ currently being compiled -- FORTH already owns a code generator, so
\ there is no need to bring a second one.
\
\ The correspondence with x86.c is one to one:
\
\   %esi (subject pointer)          RE-POS
\   %al  (current character)        RE-CH
\   %ecx + -400(%ebp) (next list)   RE-N + RE-NLIST
\   call/ret + machine stack        the FORTH return stack
\   _nnode                          (NNODE)
\   _fail: ret                      EXIT
\   jmp rel8 used as an out slot    BRANCH used as an out slot
\
\ Copyright (c) 2004 Jan Burgy.
\ Can be distributed under the MIT license, see bottom of file.

: '*' [ CHAR * ] LITERAL ;
: '|' [ CHAR | ] LITERAL ;
: '\' 92 ;      \ CHAR \ is unusable: WORD eats \ as a comment

( Token values above CHAR_MAX, ordered so that numeric comparison is )
( precedence comparison -- exactly as in the C enum.                 )
128 CONSTANT LPAREN
129 CONSTANT RPAREN
130 CONSTANT ALTERN
131 CONSTANT CONCAT
132 CONSTANT KLEENE

128 ALLOT       CONSTANT RE-TEXT        ( the regexp source itself )
128 CELLS ALLOT CONSTANT RE-INFIX       ( prepare's output )
128 CELLS ALLOT CONSTANT RE-POSTFIX     ( convert's output )
128 CELLS ALLOT CONSTANT RE-OPS         ( convert's operator stack )

VARIABLE RE#            ( number of tokens in RE-INFIX )
VARIABLE RE-SRC
VARIABLE RE-STOP
VARIABLE RE-CAT?        ( C's `concat' )
VARIABLE RE-DEPTH       ( C's `nparen' )
VARIABLE RE-TOP         ( C's `top' )
VARIABLE RE-OUT         ( C's `j' )
VARIABLE RE-IX

(
        PARSING -----------------------------------------------------------------------

        RE-ESCAPE maps the character following a backslash to the character it stands
        for, or 0 when it introduces nothing special.  This is C's `escape' table.
)
: RE-ESCAPE     ( c -- c' )
        DUP [ CHAR a ] LITERAL = IF DROP  7 EXIT THEN
        DUP [ CHAR b ] LITERAL = IF DROP  8 EXIT THEN
        DUP [ CHAR f ] LITERAL = IF DROP 12 EXIT THEN
        DUP [ CHAR n ] LITERAL = IF DROP 10 EXIT THEN
        DUP [ CHAR r ] LITERAL = IF DROP 13 EXIT THEN
        DUP [ CHAR t ] LITERAL = IF DROP  9 EXIT THEN
        DUP [ CHAR v ] LITERAL = IF DROP 11 EXIT THEN
        DUP '"' = IF EXIT THEN
        DUP '(' = IF EXIT THEN
        DUP ')' = IF EXIT THEN
        DUP '*' = IF EXIT THEN
        DUP '\' = IF EXIT THEN
        DUP '|' = IF EXIT THEN
        DROP 0
;

: INFIX,        ( t -- )
        RE# @ CELLS RE-INFIX + !   1 RE# +!
;

(
        RE-PREPARE tokenises the regexp, resolving escapes and inserting the explicit
        CONCAT operators that the source leaves implicit.  A closing RPAREN is appended
        so that RE-CONVERT's initial LPAREN is eventually flushed.
)
: RE-PREPARE    ( addr u -- )
        0 RE# !   0 RE-CAT? !   0 RE-DEPTH !
        OVER + RE-STOP !   RE-SRC !
        BEGIN RE-SRC @ RE-STOP @ < WHILE
                RE-SRC @ C@   1 RE-SRC +!
                DUP '(' = IF
                        DROP RE-CAT? @ IF CONCAT INFIX, THEN
                        LPAREN INFIX,   0 RE-CAT? !   1 RE-DEPTH +!
                ELSE DUP ')' = IF
                        DROP RPAREN INFIX,  -1 RE-DEPTH +!   1 RE-CAT? !
                ELSE DUP '*' = IF
                        DROP KLEENE INFIX,   1 RE-CAT? !
                ELSE DUP '|' = IF
                        DROP ALTERN INFIX,   0 RE-CAT? !
                ELSE
                        DUP '\' =   RE-SRC @ RE-STOP @ <   AND IF
                                DROP
                                RE-SRC @ C@ RE-ESCAPE
                                DUP IF 1 RE-SRC +! ELSE DROP '\' THEN
                        THEN
                        RE-CAT? @ IF CONCAT INFIX, THEN
                        INFIX,   1 RE-CAT? !
                THEN THEN THEN THEN
                RE-DEPTH @ 0< IF ." unbalanced parentheses" CR THEN
        REPEAT
        RPAREN INFIX,
;

: OPS-PUSH      ( t -- )  RE-TOP @ CELLS RE-OPS + !  1 RE-TOP +! ;
: OPS-POP       ( -- t )  -1 RE-TOP +!  RE-TOP @ CELLS RE-OPS + @ ;
: OPS-PEEK      ( -- t )  RE-TOP @ 1- CELLS RE-OPS + @ ;
: POSTFIX,      ( t -- )  RE-OUT @ CELLS RE-POSTFIX + !  1 RE-OUT +! ;

(
        RE-CONVERT is the shunting yard of http://cs.lasierra.edu/~ehwang/cptg454/postfix.pdf.
        LPAREN is the smallest operator token, so `t <= OPS-PEEK' stops popping there.
)
: RE-CONVERT    ( -- n )
        0 RE-TOP !   0 RE-OUT !
        LPAREN OPS-PUSH
        0 RE-IX !
        BEGIN RE-IX @ RE# @ < WHILE
                RE-IX @ CELLS RE-INFIX + @   1 RE-IX +!
                DUP LPAREN = IF
                        OPS-PUSH
                ELSE DUP LPAREN > IF
                        BEGIN DUP OPS-PEEK <= WHILE OPS-POP POSTFIX, REPEAT
                        DUP RPAREN = IF
                                DROP  -1 RE-TOP +!      ( discard the LPAREN )
                        ELSE
                                OPS-PUSH
                        THEN
                ELSE
                        POSTFIX,
                THEN THEN
        REPEAT
        RE-OUT @
;

(
        THE MACHINE -------------------------------------------------------------------

        A state is the address of a cell inside the compiled definition.  Running a
        state means letting EXIT jump to it, which is why the pending states live on the
        return stack: `ret' dispatches the next thread in the C version and so does EXIT
        here.  RE-NLIST is the list being built for the *next* character.
)
VARIABLE RE-POS         ( %esi: where the next character comes from )
VARIABLE RE-CH          ( %al:  the character every state is matched against )
VARIABLE RE-N           ( %ecx: how many states are on the next list )
VARIABLE RE-RSP         ( %ebp: return stack mark to unwind to on success )
128 CELLS ALLOT CONSTANT RE-NLIST

: RE-START      ( c-addr -- )  RE-POS !  1 RE-CH !  0 RE-N ! ;
: RE-LOAD       ( -- )         RE-POS @ DUP 1+ RE-POS ! C@ RE-CH ! ;   ( lodsb )
: RE-DONE?      ( -- f )       RE-CH @ 0= ;
: RE-CHAR?      ( c -- f )     RE-CH @ <> ;

( Pop one state off the next list; 0 once it is empty. )
: RE-THREAD     ( -- a )
        RE-N @ DUP IF 1- DUP RE-N ! CELLS RE-NLIST + @ THEN
;

(
        A state reached through a chain of out slots is the same state as the one the
        chain lands on.  Collapsing the chain is what makes duplicate suppression work,
        and without duplicate suppression a starred alternation of two identical
        branches doubles its thread count per character.  x86.c has neither and
        overruns its 100 entry list.
)
: RE-RESOLVE    ( a -- a' )
        BEGIN DUP @ ['] BRANCH = WHILE 4+ DUP @ + REPEAT
;

: RE-MEMBER?    ( a -- f )
        RE-N @
        BEGIN DUP 0> WHILE
                1- 2DUP CELLS RE-NLIST + @ = IF 2DROP TRUE EXIT THEN
        REPEAT
        2DROP FALSE
;

(
        (NNODE) is C's _nnode.  R> is the address of the cell following the call, i.e.
        this state's successor; recording it and then EXITing returns to the caller's
        caller, just as _nnode's `ret' does after popping its own return address.
)
: (NNODE)       ( -- )   ( R: succ caller -- caller )
        R> RE-RESOLVE
        DUP RE-MEMBER? IF
                DROP
        ELSE
                RE-N @ CELLS RE-NLIST + !   1 RE-N +!
        THEN
;

( C's footer: unwind the whole thread chain and return the end of the match. )
: RE-ACCEPT     ( -- a )   RE-POS @ 1-   RE-RSP @ RSP! ;

( XCALL <addr> transfers to <addr>, returning to the cell after the operand. )
: XCALL         ( -- )   R> DUP @ SWAP 4+ >R >R ;

(
        THE COMPILER ------------------------------------------------------------------

        Every block starts with a BRANCH whose offset cell is the block's out slot: the
        state preceding the block jumps there, and RE-PATCH is how KLEENE and ALTERN
        rewire it.  A fragment is identified by that slot; RE-ENTRY reads the entry
        point back out of it.  This mirrors x86.c's `stack[top] = pc + 1'.

        A fragment travels as ( slot lambda ).  lambda is Thompson's revision from the
        Notes of his paper: the slot of the BRANCH taken when the fragment matches the
        empty string, or 0.  Starring a fragment turns that BRANCH into EXIT so that
        a** cannot recurse forever.
)
: RE-SLOT       ( -- slot )  ' BRANCH , HERE @ 4 , ;
: RE-ENTRY      ( slot -- a )     DUP @ + ;
: RE-PATCH      ( slot a -- )     OVER - SWAP ! ;

(
        A character node, 9 cells:

          0 BRANCH  1 <out>  2 LIT  3 c  4 RE-CHAR?  5 0BRANCH  6 8  7 EXIT  8 (NNODE)

        EXIT is _fail; (NNODE) is last so that the successor it records is the next
        block, exactly like _nnode recording pc+11.
)
: RE-CHAR-NODE  ( c -- slot 0 )
        RE-SLOT SWAP
        ' LIT , ,
        ' RE-CHAR? ,
        ' 0BRANCH , 8 ,
        ' EXIT ,
        ' (NNODE) ,
        0
;

: RE-CAT        ( s1 l1 s2 l2 -- s1 l )  NIP 0= IF DROP 0 THEN ;

VARIABLE RE-A  VARIABLE RE-B  VARIABLE RE-PC
VARIABLE RE-LA VARIABLE RE-LB

(
        KLEENE, 8 cells:

          0 XCALL  1 <entry>  2 BRANCH  3 <out>  4 XCALL  5 <entry>  6 BRANCH  7 <out>

        Entry is cell 4, whose BRANCH recognizes lambda.  The fragment's own out is
        rewired back to cell 0, which is the loop.
)
: RE-STAR       ( s l -- s l' )
        ?DUP IF ' EXIT SWAP 4- ! THEN
        HERE @ RE-PC !
        ' XCALL , DUP RE-ENTRY ,
        ' BRANCH , 20 ,
        ' XCALL , DUP RE-ENTRY ,
        DUP RE-PC @ 16 + RE-PATCH
        ' BRANCH , HERE @ 4 ,
;

(
        ALTERN, 6 cells:

          0 BRANCH  1 <out>  2 XCALL  3 <B entry>  4 BRANCH  5 <A entry>

        Entry is cell 2: run B, then -- however B ended -- run A.  B's out slot (cell 0)
        and A's out slot both become cell 6, the block after this one.  When both
        branches recognize lambda, B's lambda BRANCH is sent to A's.
)
: RE-ALT        ( sA lA sB lB -- sA l )
        RE-LB !  RE-B !  RE-LA !  RE-A !
        HERE @ RE-PC !
        ' BRANCH , 20 ,
        ' XCALL , RE-B @ RE-ENTRY ,
        ' BRANCH , RE-A @ RE-ENTRY HERE @ - ,
        RE-A @ RE-PC @  8 + RE-PATCH
        RE-B @ RE-PC @ 24 + RE-PATCH
        RE-A @
        RE-LA @ 0= IF
                RE-LB @
        ELSE
                RE-LB @ ?DUP IF RE-LA @ 4- RE-PATCH THEN
                RE-LA @
        THEN
;

(
        C's header.  Cell 5 is the top of the outer loop; a literal pointer to it is
        pushed onto the return stack under the pending threads, so that when the last
        thread EXITs we land back there -- the `call _next / sub $5,(%esp)' trick.
)
: RE-HEADER     ( -- )
        ' RSP@ ,  ' LIT , RE-RSP , ' ! ,
        ' RE-START ,
        HERE @                                          ( L )
        ' RE-DONE? , ' 0BRANCH , 16 ,
        ' LIT , 0 , ' EXIT ,                            ( subject exhausted )
        ' LIT , DUP , ' >R ,                            ( sentinel )
        HERE @                                          ( L L3 )
        ' RE-THREAD , ' DUP , ' 0BRANCH , 16 , ' >R ,
        ' BRANCH , DUP HERE @ - ,
        2DROP
        ' DROP ,
        ' RE-LOAD ,
        ( the start state's block follows, and is entered by falling into it )
;

VARIABLE RE-NN

: RE-BUILD      ( n -- slot lambda )
        RE-NN !  0 RE-IX !
        BEGIN RE-IX @ RE-NN @ < WHILE
                RE-IX @ CELLS RE-POSTFIX + @   1 RE-IX +!
                DUP CONCAT = IF DROP RE-CAT
                ELSE DUP KLEENE = IF DROP RE-STAR
                ELSE DUP ALTERN = IF DROP RE-ALT
                ELSE RE-CHAR-NODE
                THEN THEN THEN
        REPEAT
;

: RE-READ       ( -- addr u )
        RE-TEXT 0
        BEGIN KEY DUP '"' <> WHILE
                >R 2DUP + R> SWAP C!  1+
        REPEAT
        DROP
;

(
        RE" <regexp>" compiles a matcher into the definition being compiled.  The
        matcher has the stack effect ( c-addr -- a ), where a is the end of the leftmost
        match or 0, and it returns from the enclosing word, so RE" is the whole body:

                : (A|B)*A  RE" (a|b)*a" ;
)
: RE" IMMEDIATE ( -- )
        RE-READ RE-PREPARE
        RE-CONVERT
        RE-HEADER
        RE-BUILD 2DROP
        ' RE-ACCEPT ,
;

(
        C's main() ---------------------------------------------------------------------
)
: R1 RE" abcdefg" ;
: R2 RE" (a|b)*a" ;
: R3 RE" a(b|c)*d" ;
: R4 RE" (a|a)*" ;
: R5 RE" a*" ;
: R6 RE" a**" ;
: R7 RE" (a*b*)*c" ;
: R8 RE" (a*|b*)*c" ;
: R9 RE" b*(c|d)" ;

: TRY           ( c-addr xt -- )
        OVER SWAP EXECUTE
        DUP IF
                SWAP - ." match found after " . ." bytes" CR
        ELSE
                2DROP ." match not found" CR
        THEN
;

: RE-TESTS
        ." abcdefg abcdefg "                     Z" abcdefg"    ['] R1 TRY
        ." (a|b)*a ababababab "                  Z" ababababab" ['] R2 TRY
        ." (a|b)*a aaaaaaaaba "                  Z" aaaaaaaaba" ['] R2 TRY
        ." (a|b)*a aaaaaabac "                   Z" aaaaaabac"  ['] R2 TRY
        ." a(b|c)*d abccbcccd "                  Z" abccbcccd"  ['] R3 TRY
        ." a(b|c)*d abccbcccde "                 Z" abccbcccde" ['] R3 TRY
        ." (a|a)* aaaaaaaaaaaaaaaaaaaaaaaaaaaa " Z" aaaaaaaaaaaaaaaaaaaaaaaaaaaa" ['] R4 TRY
        ." a(b|c)*d abccccccccd "                Z" abccccccccd" ['] R3 TRY
        ." a* aaab "                             Z" aaab"       ['] R5 TRY
        ." a(b|c)*d abcd "                       Z" abcd"       ['] R3 TRY
        ." a** b "                               Z" b"          ['] R6 TRY
        ." (a*b*)*c abbac "                      Z" abbac"      ['] R7 TRY
        ." (a*|b*)*c abac "                      Z" abac"       ['] R8 TRY
        ." b*(c|d) c "                           Z" c"          ['] R9 TRY
;

(
 * Permission is hereby granted, free of charge, to any person
 * obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the
 * Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute,
 * sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so,
 * subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall
 * be included in all copies or substantial portions of the
 * Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
 * KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
 * WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
 * PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE AUTHORS
 * OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
 * OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
 * OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
)
