( Fixes to make jonesforth somewhat livable. )
( downloaded from http://www.lisphacker.com/temp/fixes.f on 2023-08-15 )

HEX

(
   Step 1: Proper, working <BUILDS DOES>
   -------------------------------------

Technically, this should be CREATE DOES>, but that's a bit more work,
and my own Forth implementation doesn't go to all that trouble, so I
shan't bother here.

This is heavily based on what my implementation does.  <BUILDS creates
a new word that uses a code fragment in place of DOCOL to:

  1. Push the old threaded instruction pointer (ESI) to the return
     stack.

  2. Load the new threaded instruction pointer from the first cell of
     the data area of the word (this cell reserved in <BUILDS, and
     initialized in DOES>).

  3. Push the address of the second cell of the data area (the start
     of actual usable space) to the data stack.

  4. Resume interpretation by performing the NEXT operation.

Interestingly, this code winds up being a multiple of four bytes long,
and thus requires no alignment afterwards (four instructions at three
bytes each is twelve bytes, thus aligned; one instruction at one byte
plus the NEXT operation at three bytes is four bytes, thus aligned).

)

VARIABLE dodoes
HERE @ dodoes !
                  ( This is "PUSHRSP $esi" from jonesforth.S )
8D C, 6D C, FC C, ( LEA EBP, [EBP-4] )
89 C, 75 C, 0 C,  ( MOV [EBP], ESI )

                  ( Load the threaded code pointer )
8B C, 70 C, 4 C,  ( MOV ESI, [EAX+4] )

                  ( Push the address of the start of the user data area )
83 C, C0 C, 8 C,  ( ADD EAX, 8 )
50 C,             ( PUSH EAX )

NEXT              ( And resume interpretation )

: <BUILDS
    WORD CREATE   ( Set up header for new word )
    dodoes @ ,    ( Set CFA to point to the ASM fragment above )
    0 ,           ( reserve space for threaded code ptr )
;

(

DOES> is an unusual word.  It causes execution of the current
definition to stop when it is reached.  Further code in the definition
beyond DOES> is set up to be executed when the word created by <BUILDS
is executed.  For an explanation, see Starting FORTH, chapter 11.

)

: DOES>
    R>        ( next xt in current defintion )
    LATEST @  ( latest definition )
    >DFA !    ( store in first slot of data area )
;

(
    Step 2: Variables that allow further allocation into their data area
    --------------------------------------------------------------------

VARIABLEs can be more convenient if they allow for allocating more
than a single cell of contiguous storage, even though this is
explicitly not required by the standard (dpANS94, section 3.3.3.3).
jonesforth variables don't allow that, by design.  If, instead of
monkeying about with ALLOT before defining what amounts to a constant
(seriously, compare the definitions of CONSTANT and VARIABLE in
jonesforth.f), it compiled

    ' LIT , HERE @ 8 + , ' EXIT , 0 ,

it would allow for contiguous allocation of the sort that we want.
The reason this would work is that the literal value for the constant
is one cell wide, and the address of EXIT is one cell wide, thus 8
bytes total, and adding the value of the current dictionary pointer
points to the 0 that is comma'd in as storage for the variable.

However, rather than doing all that, we'll just provide an example of
using <BUILDS DOES>, as follows:

)

: VARIABLE <BUILDS 0 , DOES> ;

(
    Step 3: ALLOT that doesn't suck
    -------------------------------

ALLOT isn't supposed to return an address, it's just supposed to move
the dictionary pointer (dpANS94, section 6.1.0710).

)

: ALLOT ( n -- )
    HERE @ + HERE !
;

(
    Step 4: Standard-conforming HERE
    --------------------------------

HERE isn't supposed to be a VARIABLE, it's supposed to return the
address of the end of the dictionary space (dpANS94, section 3.3.3.2).

Now that we have working ALLOT, we can fix HERE.

)

: HERE HERE @ ;

( EOF )
