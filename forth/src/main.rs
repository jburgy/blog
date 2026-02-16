const PREAMBLE: &str = r#": / /MOD SWAP DROP ;
: '\n' 10 ;
: BL 32 ;
: CR '\n' EMIT ;
: SPACE BL EMIT ;
: NEGATE 0 SWAP - ;
: TRUE  1 ;
: FALSE 0 ;
: NOT   0= ;
: LITERAL IMMEDIATE ' LIT , , ;
: ':' [ CHAR : ] LITERAL ;
: ';' [ CHAR ; ] LITERAL ;
: '"' [ CHAR " ] LITERAL ;
: 'A' [ CHAR A ] LITERAL ;
: '0' [ CHAR 0 ] LITERAL ;
: '-' [ CHAR - ] LITERAL ;
: [COMPILE] IMMEDIATE WORD FIND >CFA , ;
: RECURSE   IMMEDIATE LATEST @ >CFA , ;
: IF        IMMEDIATE ' 0BRANCH , HERE @ 0 , ;
: THEN      IMMEDIATE DUP HERE @ SWAP - SWAP ! ;
: ELSE      IMMEDIATE ' BRANCH , HERE @ 0 , SWAP DUP HERE @ SWAP - SWAP ! ;
: BEGIN     IMMEDIATE HERE @ ;
: AGAIN     IMMEDIATE ' BRANCH , HERE @ - , ;
: WHILE     IMMEDIATE ' 0BRANCH , HERE @ 0 , ;
: REPEAT    IMMEDIATE ' BRANCH , SWAP HERE @ - , DUP HERE @ SWAP - SWAP ! ;
: NIP SWAP DROP ;
: PICK 1+ 8 * DSP@ + @ ;
: SPACES BEGIN DUP 0> WHILE SPACE 1- REPEAT DROP ;
: U. BASE @ /MOD ?DUP IF RECURSE THEN DUP 10 < IF '0' ELSE 10 - 'A' THEN + EMIT ;
: .S DSP@ BEGIN DUP S0 @ < WHILE DUP @ U. 8+ SPACE REPEAT DROP ;
: UWIDTH BASE @ / ?DUP IF RECURSE 1+ ELSE 1 THEN ;
: U.R SWAP DUP UWIDTH ROT SWAP - SPACES U. ;
: .R SWAP DUP 0< IF NEGATE 1 SWAP ROT 1- ELSE 0 SWAP ROT THEN SWAP DUP
  UWIDTH ROT SWAP - SPACES SWAP IF '-' EMIT THEN U. ;
: . 0 .R SPACE ;
: U. U. SPACE ;
: WITHIN -ROT OVER <= IF > IF TRUE ELSE FALSE THEN ELSE 2DROP FALSE THEN ;
: ALIGNED 7 + -8 AND ;
: ALIGN HERE @ ALIGNED HERE ! ;
: C, HERE @ C! 1 HERE +! ;
: S" IMMEDIATE STATE @ IF
  ' LITSTRING , HERE @ 0 , BEGIN KEY DUP '"' <> WHILE
  C, REPEAT DROP DUP HERE @ SWAP - 8- SWAP ! ALIGN ELSE
  HERE @ BEGIN KEY DUP '"' <> WHILE OVER C! 1+ REPEAT DROP HERE @ - HERE @ SWAP THEN ;
: ." IMMEDIATE STATE @ IF [COMPILE] S" ' TELL , ELSE BEGIN KEY DUP '"' = IF
  DROP EXIT THEN EMIT AGAIN THEN ;
: CELLS 8 * ;
: ID. 8+ DUP C@ F_LENMASK AND BEGIN DUP 0> WHILE SWAP 1+ DUP C@ EMIT SWAP 1- REPEAT
  2DROP ;
: ?IMMEDIATE 8+ C@ F_IMMED AND ;
: CASE    IMMEDIATE 0 ;
: OF      IMMEDIATE ' OVER , ' = , [COMPILE] IF ' DROP , ;
: ENDOF   IMMEDIATE [COMPILE] ELSE ;
: ENDCASE IMMEDIATE ' DROP , BEGIN ?DUP WHILE [COMPILE] THEN REPEAT ;
: CFA> LATEST @ BEGIN ?DUP WHILE 2DUP >CFA = IF NIP EXIT THEN @ REPEAT DROP 0 ;
: SEE WORD FIND HERE @ LATEST @ BEGIN 2 PICK OVER <> WHILE NIP DUP @ REPEAT DROP SWAP
  ':' EMIT SPACE DUP ID. SPACE DUP ?IMMEDIATE IF ." IMMEDIATE " THEN >DFA
  BEGIN 2DUP > WHILE DUP @
      CASE
          ' LIT OF 8+ DUP @ . ENDOF
          ' LITSTRING OF [ CHAR S ] LITERAL EMIT '"' EMIT SPACE 8+ DUP @ SWAP 8+
            SWAP 2DUP TELL '"' EMIT SPACE + ALIGNED 8- ENDOF
          ' 0BRANCH OF ." 0BRANCH ( " 8+ DUP @ . ." ) " ENDOF
          '  BRANCH OF  ." BRANCH ( " 8+ DUP @ . ." ) " ENDOF
          ' ' OF [ CHAR ' ] LITERAL EMIT SPACE 8+ DUP CFA> ID. SPACE ENDOF
          ' EXIT OF 2DUP 8+ <> IF ." EXIT " THEN ENDOF
          DUP CFA> ID. SPACE
      ENDCASE
      8+
  REPEAT
 ';' EMIT CR 2DROP ;
: ['] IMMEDIATE ' LIT , ;
: EXCEPTION-MARKER RDROP 0 ;
: CATCH DSP@ 8+ >R ' EXCEPTION-MARKER 8+ >R EXECUTE ;
: THROW ?DUP IF RSP@ BEGIN DUP R0 8- < WHILE DUP @ ' EXCEPTION-MARKER 8+ = IF
  8+ RSP! DUP DUP DUP R> 8- SWAP OVER ! DSP! EXIT THEN 8+ REPEAT
  DROP CASE 0 1- OF ." ABORTED" CR ENDOF ." UNCAUGHT THROW " DUP . CR ENDCASE QUIT THEN
  ;
: Z" IMMEDIATE STATE @ IF
  ' LITSTRING , HERE @ 0 , BEGIN KEY DUP '"' <> WHILE
  HERE @ C! 1 HERE +! REPEAT 0 HERE @ C! 1 HERE +! DROP DUP
  HERE @ SWAP - 8- SWAP ! ALIGN ' DROP , ELSE
  HERE @ BEGIN KEY DUP '"' <> WHILE OVER C! 1+ REPEAT DROP 0 SWAP C! HERE @ THEN ;
: STRLEN DUP BEGIN DUP C@ 0<> WHILE 1+ REPEAT SWAP - ;
: ARGC (ARGC) @ ;
: ARGV 1+ CELLS (ARGC) + @ DUP STRLEN ;
: ENVIRON ARGC 2 + CELLS (ARGC) + ;
"#;

#[cfg(test)]
mod tests {
    use std::process::{Command, Stdio};
    use std::io::Write;
    use rstest::rstest;
    use super::PREAMBLE;

    #[rstest]
    #[case("", "65 EMIT", "A")]
    #[case("", "777 65 EMIT", "A")]
    #[case("", "32 DUP + 1+ EMIT", "A")]
    #[case("", "16 DUP 2DUP + + + 1+ EMIT", "A")]
    #[case("", "8 DUP * 1+ EMIT", "A")]
    #[case("", "CHAR A EMIT", "A")]
    #[case("", ": SLOW WORD FIND >CFA EXECUTE ; 65 SLOW EMIT", "A")]
    #[case("", "3480240455236671827 DSP@ 8 TELL", "SYSCALL0")]
    #[case("", "3480240455236671827 DSP@ HERE @ 8 CMOVE HERE @ 8 TELL", "SYSCALL0")]
    #[case("", "13622 DSP@ 2 NUMBER DROP EMIT", "A")]
    #[case("", "64 >R RSP@ 1 TELL RDROP", "@")]
    #[case("", "64 DSP@ RSP@ SWAP C@C! RSP@ 1 TELL", "@")]
    #[case("", "64 >R 1 RSP@ +! RSP@ 1 TELL", "A")]
    #[case("", r#"
: <BUILDS WORD CREATE DODOES , 0 , ;
: DOES> R> LATEST @ >DFA ! ;
: CONST <BUILDS , DOES> @ ;

65 CONST FOO
FOO EMIT
"#, "A")]
    #[case(PREAMBLE, "VERSION .", "47 ")]
    #[case(PREAMBLE, "CR", "\n")]
    #[case(PREAMBLE, "LATEST @ ID.", "ENVIRON")]
    #[case(PREAMBLE, "0 1 > . 1 0 > .", "0 -1 ")]
    #[case(PREAMBLE, "0 1 >= . 0 0 >= .", "0 -1 ")]
    #[case(PREAMBLE, "0 0<> . 1 0<> .", "0 -1 ")]
    #[case(PREAMBLE, "1 0<= . 0 0<= .", "0 -1 ")]
    #[case(PREAMBLE, "-1 0>= . 0 0>= .", "0 -1 ")]
    #[case(PREAMBLE, "0 0 OR . 0 -1 OR .", "0 -1 ")]
    #[case(PREAMBLE, "-1 -1 XOR . 0 -1 XOR .", "0 -1 ")]
    #[case(PREAMBLE, "-1 INVERT . 0 INVERT .", "0 -1 ")]
    #[case(PREAMBLE, "3 4 5 .S", "5 4 3 ")]
    #[case(PREAMBLE, "1 2 3 4 2SWAP .S", "2 1 4 3 ")]
    #[case(PREAMBLE, "F_IMMED F_HIDDEN .S", "32 128 ")]
    #[case(PREAMBLE, ": CFA@ WORD FIND >CFA @ ; CFA@ >DFA DOCOL = .", "-1 ")]
    #[case(PREAMBLE, "3 4 5 WITHIN .", "0 ")]
    #[case(PREAMBLE, r#"S" test" SWAP 1 SYS_WRITE SYSCALL3"#, "test")]
    #[case(PREAMBLE, "SEE >DFA", ": >DFA >CFA 8+ EXIT ;\n")]
    #[case(PREAMBLE, "SEE HIDE", ": HIDE WORD FIND HIDDEN ;\n")]
    #[case(PREAMBLE, "SEE QUIT", ": QUIT R0 RSP! INTERPRET BRANCH ( -16 ) ;\n")]
    fn test_wait_with_output(
        #[case] preamble: &str,
        #[case] input: &str,
        #[case] expected: &str,
        #[values("./4th", "./5th.ll")] program: &str,
    ) {
        let mut child = Command::new(program)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .expect("Failed to spawn command");

        child.stdin.take()
            .unwrap()
            .write_all(format!("{} {}\n", preamble, input).as_bytes())
            .expect("Failed to write to stdin");

        let output = child.wait_with_output().expect("Failed to read stdout");

        assert!(output.status.success(), "Command failed with status: {:?}", output.status);
        assert_eq!(output.stdout, expected.as_bytes(), "Mismatch for: {}", input);
    }
}