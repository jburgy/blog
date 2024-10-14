: / /MOD SWAP DROP ;
: RECURSE IMMEDIATE LATEST @ >CFA , ;
: IF      IMMEDIATE ' 0BRANCH , HERE @ 0 , ;
: THEN    IMMEDIATE DUP HERE @ SWAP - SWAP ! ;
: ELSE    IMMEDIATE ' BRANCH , HERE @ 0 , SWAP DUP HERE @ SWAP - SWAP ! ;
: BEGIN   IMMEDIATE HERE @ ;
: UNTIL   IMMEDIATE ' 0BRANCH , HERE @ - , ;
: WHILE   IMMEDIATE ' 0BRANCH , HERE @ 0 , ;
: REPEAT  IMMEDIATE ' BRANCH , SWAP HERE @ - , DUP HERE @ SWAP - SWAP ! ;
: U. BASE @ /MOD ?DUP IF RECURSE THEN DUP 10 < IF 48 ELSE 55 THEN + EMIT ;
: CLSB DUP BEGIN SWAP DROP DUP DUP 1- AND ?DUP 0= UNTIL ;
: FIBONACCI
    DUP CLSB 0 1
    BEGIN
        ROT DUP
    WHILE
        -ROT                       \ n m a b
        2DUP * DUP + -ROT          \ n m 2ab a b
        DUP * SWAP DUP *           \ n m 2ab b^2 a^2
        ROT OVER + -ROT +          \ n m a' b'
        2SWAP 2DUP AND             \ a b n m n&m
        IF
            2 / 2SWAP OVER + SWAP  \ n m a+b b
        ELSE
            2 / 2SWAP              \ n m a b
        THEN
    REPEAT
    2DROP SWAP DROP                \ a
;
92 FIBONACCI U.
