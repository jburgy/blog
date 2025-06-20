import struct
from enum import IntEnum
from typing import cast

REPLACEMENTS = {
    "@^": "\0",
    "J^": "\n",
    "Q^": "\x11",
    "S^": "\x13",
    "b^": '"',
}


class OpCode(IntEnum):
    SX = 0x00
    NO = 0x08
    LB = 0x09
    LN = 0x0A
    DS = 0x0B
    SP = 0x0C
    SB = 0x10
    RB = 0x11
    FV = 0x12
    SV = 0x13
    GS = 0x14
    RS = 0x15
    GO = 0x16
    NE = 0x17
    AD = 0x18
    SU = 0x19
    MP = 0x1A
    DV = 0x1B
    CP = 0x1C
    NX = 0x1D
    LS = 0x1F
    PN = 0x20
    PQ = 0x21
    PT = 0x22
    NL = 0x23
    PC = 0x24
    GL = 0x27
    IL = 0x2A
    MT = 0x2B
    XQ = 0x2C
    WS = 0x2D
    US = 0x2E
    RT = 0x2F
    JS = 0x30
    J = 0x38  # noqa E2221
    BR = 0x40
    BV = 0xA0
    BN = 0xC0
    BE = 0xE0
    BC = 0x80


interpreter = """
0000 ;       1 .  ORIGINAL TINY BASIC INTERMEDIATE INTERPRETER
0000 ;       2 .
0000 ;       3 .  EXECUTIVE INITIALIZATION
0000 ;       4 .
0000 ;       5 :STRT PC ":Q^"        COLON, X-ON
0000 243A91;
0003 ;       6       GL
0003 27;     7       SB
0004 10;     8       BE L0           BRANCH IF NOT EMPTY
0005 E1;     9       BR STRT         TRY AGAIN IF NULL LINE
0006 59;    10 :L0   BN STMT         TEST FOR LINE NUMBER
0007 C5;    11       IL              IF SO, INSERT INTO PROGRAM
0008 2A;    12       BR STRT         GO GET NEXT
0009 56;    13 :XEC  SB              SAVE POINTERS FOR RUN WITH
000A 10;    14       RB                CONCATENATED INPUT
000B 11;    15       XQ
000C 2C;    16 .
000D ;      17 .  STATEMENT EXECUTOR
000D ;      18 .
000D ;      19 :STMT BC GOTO "LET"
000D 8B4C45D4;
0011 ;      20       BV *            MUST BE A VARIABLE NAME
0011 A0;    21       BC * "="
0012 80BD;  22 :LET  JS EXPR         GO GET EXPRESSION
0014 30BC;  23       BE *            IF STATEMENT END,
0016 E0;    24       SV                STORE RESULT
0017 13;    25       NX
0018 1D;    26 .
0019 ;      27 :GOTO BC PRNT "GO"
0019 9447CF;
001C ;      28       BC GOSB "TO"
001C 8854CF;
001F ;      29       JS EXPR         GET LINE NUMBER
001F 30BC;  30       BE *
0021 E0;    31       SB              (DO THIS FOR STARTING)
0022 10;    32       RB
0023 11;    33       GO              GO THERE
0024 16;    34 .
0025 ;      35 :GOSB BC * "SUB"      NO OTHER WORD BEGINS "GO..."
0025 805355C2;
0029 ;      36       JS EXPR
0029 30BC;  37       BE *
002B E0;    38       GS
002C 14;    39       GO
002D 16;    40 .
002E ;      41 :PRNT BC SKIP "PR"
002E 9050D2;
0031 ;      42       BC P0 "INT"     OPTIONALLY OMIT "INT"
0031 83494ED4;
0035 ;      43 :P0   BE P3
0035 E5;    44       BR P6           IF DONE, GO TO END
0036 71;    45 :P1   BC P4 ";"
0037 88BB;  46 :P2   BE P3
0039 E1;    47       NX              NO CRLF IF ENDED BY ; OR ,
003A 1D;    48 :P3   BC P7 "b^"
003B 8FA2;  49       PQ              QUOTE MARKS STRING
003D 21;    50       BR P1           GO CHECK DELIMITER
003E 58;    51 :SKIP BR IF           (ON THE WAY THRU)
003F 6F;    52 :P4   BC P5 ","
0040 83AC;  53       PT              COMMA SPACING
0042 22;    54       BR P2
0043 55;    55 :P5   BC P6 ":"
0044 83BA;  56       PC "S^"         OUTPUT X-OFF
0046 2493;  57 :P6   BE *
0048 E0;    58       NL              THEN CRLF
0049 23;    59       NX
004A 1D;    60 :P7   JS EXPR         TRY FOR AN EXPRESSION
004B 30BC;  61       PN
004D 20;    62       BR P1
004E 48;    63 .
004F ;      64 :IF   BC INPT "IF"
004F 9149C6;
0052 ;      65       JS EXPR
0052 30BC;  66       JS RELO
0054 3134;  67       JS EXPR
0056 30BC;  68       BC I1 "THEN"    OPTIONAL NOISEWORD
0058 84544845CE;
005D ;      69 :I1   CP              COMPARE SKIPS NEXT IF TRUE
005D 1C;    70       NX              FALSE.
005E 1D;    71       J STMT          TRUE. GO PROCESS STATEMENT
005F 380D;  72 .
0061 ;      73 :INPT BC RETN "INPUT"
0061 9A494E5055D4;
0067 ;      74 :I2   BV *            GET VARIABLE
0067 A0;    75       SB              SWAP POINTERS
0068 10;    76       BE I4
0069 E7;    77 :I3   PC "? Q^"       LINE IS EMPTY; TYPE PROMPT
006A 243F2091;
006E ;      78       GL              READ INPUT LINE
006E 27;    79       BE I4           DID ANYTHING COME?
006F E1;    80       BR I3           NO, TRY AGAIN
0070 59;    81 :I4   BC I5 ","       OPTIONAL COMMA
0071 81AC;  82 :I5   JS EXPR         READ A NUMBER
0073 30BC;  83       SV              STORE INTO VARIABLE
0075 13;    84       RB              SWAP BACK
0076 11;    85       BC I6 ","       ANOTHER?
0077 82AC;  86       BR I2           YES IF COMMA
0079 4D;    87 :I6   BE *            OTHERWISE QUIT
007A E0;    88       NX
007B 1D;    89 .
007C ;      90 :RETN BC END "RETURN"
007C 895245545552CE;
0083 ;      91       BE *
0083 E0;    92       RS              RECOVER SAVED LINE
0084 15;    93       NX
0085 1D;    94 .
0086 ;      95 :END  BC LIST "END"
0086 85454EC4;
008A ;      96       BE *
008A E0;    97       WS
008B 2D;    98 .
008C ;      99 :LIST BC RUN "LIST"
008C 984C4953D4;
0091 ;     100       BE L2
0091 EC;   101 :L1   PC "@^@^@^@^J^@^" PUNCH LEADER
0092 24000000000A80;
0099 ;     102       LS              LIST
0099 1F;   103       PC "S^"         PUNCH X-OFF
009A 2493; 104       NL
009C 23;   105       NX
009D 1D;   106 :L2   JS EXPR         GET A LINE NUMBER
009E 30BC; 107       BE L3
00A0 E1;   108       BR L1
00A1 50;   109 :L3   BC * ","        SEPARATED BY COMMAS
00A2 80AC; 110       BR L2
00A4 59;   111 .
00A5 ;     112 :RUN  BC CLER "RUN"
00A5 855255CE;
00A9 ;     113       J XEC
00A9 380A; 114 .
00AB ;     115 :CLER BC REM "CLEAR"
00AB 86434C4541D2;
00B1 ;     116       MT
00B1 2B;   117 .
00B2 ;     118 :REM  BC DFLT "REM"
00B2 845245CD;
00B6 ;     119       NX
00B6 1D;   120 .
00B7 ;     121 :DFLT BV *            NO KEYWORD...
00B7 A0;   122       BC * "="        TRY FOR LET
00B8 80BD; 123       J LET           IT'S A GOOD BET.
00BA 3814; 124 .
00BC ;     125 .  SUBROUTINES
00BC ;     126 .
00BC ;     127 :EXPR BC E0 "-"       TRY FOR UNARY MINUS
00BC 85AD; 128       JS TERM         AHA
00BE 30D3; 129       NE
00C0 17;   130       BR E1
00C1 64;   131 :E0   BC E4 "+"       IGNORE UNARY PLUS
00C2 81AB; 132 :E4   JS TERM
00C4 30D3; 133 :E1   BC E2 "+"       TERMS SEPARATED BY PLUS
00C6 85AB; 134       JS TERM
00C8 30D3; 135       AD
00CA 18;   136       BR E1
00CB 5A;   137 :E2   BC E3 "-"       TERMS SEPARATED BY MINUS
00CC 85AD; 138       JS TERM
00CE 30D3; 139       SU
00D0 19;   140       BR E1
00D1 54;   141 :E3   RT
00D2 2F;   142 .
00D3 ;     143 :TERM JS FACT
00D3 30E2; 144 :T0   BC T1 "*"       FACTORS SEPARATED BY TIMES
00D5 85AA; 145       JS FACT
00D7 30E2; 146       MP
00D9 1A;   147       BR T0
00DA 5A;   148 :T1   BC T2 "/"       FACTORS SEPARATED BY DIVIDE
00DB 85AF; 149       JS  FACT
00DD 30E2; 150       DV
00DF 1B;   151       BR T0
00E0 54;   152 :T2   RT
00E1 2F;   153 .
00E2 ;     154 :FACT BC F0 "RND"     *RND FUNCTION*
00E2 97524EC4;
00E6 ;     155       LN 257*128      STACK POINTER FOR STORE
00E6 0A;
00E7 8080; 156       FV              THEN GET RNDM
00E9 12;   157       LN 2345         R:=R*2345+6789
00EA 0A;
00EB 0929; 158       MP
00ED 1A;   159       LN 6789
00EE 0A;
00EF 1A85; 160       AD
00F1 18;   161       SV
00F2 13;   162       LB 128          GET IT AGAIN
00F3 0980; 163       FV
00F5 12;   164       DS
00F6 0B;   165       JS FUNC         GET ARGUMENT
00F7 3130; 166       BR F1
00F9 61;   167 :F0   BR F2           (SKIPPING)
00FA 73;   168 :F1   DS
00FB 0B;   169       SX 2            PUSH TOP INTO STACK
00FC 02;   170       SX 4
00FD 04;   171       SX 2
00FE 02;   172       SX 3
00FF 03;   173       SX 5
0100 05;   174       SX 3
0101 03;   175       DV              PERFORM MOD FUNCTION
0102 1B;   176       MP
0103 1A;   177       SU
0104 19;   178       DS              PERFORM ABS FUNCTION
0105 0B;   179       LB 6
0106 0906; 180       LN 0
0108 0A;
0109 0000; 181       CP              (SKIP IF + OR 0)
010B 1C;   182       NE
010C 17;   183       RT
010D 2F;   184 :F2   BC F3 "USR"     *USR FUNCTION*
010E 8F5553D2;
0112 ;     185       BC * "("        3 ARGUMENTS POSSIBLE
0112 80A8; 186       JS EXPR         ONE REQUIRED
0114 30BC; 187       JS ARG
0116 312A; 188       JS ARG
0118 312A; 189       BC * ")"
011A 80A9; 190       US              GO DO IT
011C 2E;   191       RT
011D 2F;   192 :F3   BV F4           VARIABLE?
011E A2;   193       FV              YES.  GET IT
011F 12;   194       RT
0120 2F;   195 :F4   BN F5           NUMBER?
0121 C1;   196       RT              GOT IT.
0122 2F;   197 :F5   BC * "("        OTHERWISE MUST BE (EXPR)
0123 80A8; 198 :F6   JS EXPR
0125 30BC; 199       BC * ")"
0127 80A9; 200       RT
0129 2F;   201 .
012A ;     202 :ARG  BC A0 ","        COMMA?
012A 83AC; 203       J  EXPR          YES, GET EXPRESSION
012C 38BC; 204 :A0   DS               NO, DUPLICATE STACK TOP
012E 0B;   205       RT
012F 2F;   206 .
0130 ;     207 :FUNC BC * "("
0130 80A8; 208       BR F6
0132 52;   209       RT
0133 2F;   210 .
0134 ;     211 :RELO BC R0 "="        CONVERT RELATION OPERATORS
0134 84BD; 212       LB 2             TO CODE BYTE ON STACK
0136 0902; 213       RT               =
0138 2F;   214 :R0   BC R4 "<"
0139 8EBC; 215       BC R1 "="
013B 84BD; 216       LB 3             <=
013D 0903; 217       RT
013F 2F;   218 :R1   BC R3 ">"
0140 84BE; 219       LB 5             <>
0142 0905; 220       RT
0144 2F;   221 :R3   LB 1             <
0145 0901; 222       RT
0147 2F;   223 :R4   BC * ">"
0148 80BE; 224       BC R5 "="
014A 84BD; 225       LB 6             >=
014C 0906; 226       RT
014E 2F;   227 :R5   BC R6 "<"
014F 84BC; 228       LB 5             ><
0151 0905; 229       RT
0153 2F;   230 :R6   LB 4             >
0154 0904; 231       RT
0156 2F;   232 .
0157 ;    0000
"""

offsets = {}

out = bytearray()
for _ in range(2):
    out = bytearray()
    for j, line in enumerate(interpreter[1:].splitlines()):
        if line.index(";") > 10:
            continue
        line = line[15:]
        if not line or line.startswith("."):
            continue

        here = len(out)
        label = line[1:5].strip()
        if label:
            offsets[label] = here

        op = OpCode[line[6:8].rstrip()]

        arg, _, rest = (
            ("", "", line[8:].lstrip())  # type: ignore[assignment]
            if op is OpCode.PC
            else line[8:].lstrip().partition(" ")
        )
        word = rest[1:rest.index('"', 1)] if rest.startswith('"') else ""
        for old, new in REPLACEMENTS.items():
            word = word.replace(old, new)

        if op is OpCode.SX:
            out.append(int(op) + int(cast(str, arg)))
        elif op is OpCode.LB:
            out.append(int(op))
            out.append(int(cast(str, arg)))
        elif op is OpCode.LN:
            out.append(int(op))
            out.extend(struct.pack(">H", eval(cast(str, arg))))
        elif op >= OpCode.BR:
            offset = offsets.get(arg, here + 1) - (here + 1)
            if op is OpCode.BR:
                offset += 0x20
            out.append(int(op) + offset)
        elif op >= OpCode.JS:
            target = struct.pack(">H", offsets.get(arg, 0))
            out.append(int(op) + target[0])
            out.extend(target[1:])
        else:
            out.append(int(op))

        if word:
            buf = struct.pack(f"@{len(word)}s", word.encode())
            out.extend(buf[:-1])
            out.append(buf[-1] | 0x80)


test = "".join(map("{:02X}".format, out))
assert test == "".join(
    line[5:line.index(";", 5)] for line in interpreter.splitlines() if len(line) > 5
)
