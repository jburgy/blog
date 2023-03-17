type T = u16;

const CoreTop = 0x10000;      /* Core size */
const UserProg: T = 0x20;   /* Core address of front of Basic program */
const EndUser: T = 0x22;    /* Core address of end of stack/user space */
const EndProg: T = 0x24;    /* Core address of end of Basic program */
const GoStkTop: T = 0x26;   /* Core address of Gosub stack top */
const LinoCore: T = 0x28;   /* Core address of "Current BASIC line number" */
const ILPCcore: T = 0x2A;   /* Core address of "IL Program Counter" */
const BPcore: T = 0x2C;     /* Core address of "Basic Pointer" */
const SvPtCore: T = 0x2E;   /* Core address of "Saved Pointer" */
const InLine: T = 0x30;     /* Core address of input line */
const ExpnStk: T = 0x80;    /* Core address of expression stack (empty) */
const TabHere: T = 0xBF;    /* Core address of output line size, for tabs */
const WachPoint: T = 0xFF;  /* Core address of debug watchpoint USR */
export const ColdGo: T = 0x100;    /* Core address of nominal restart USR */
const WarmGo: T = 0x103;    /* Core address of nominal warm start USR */
const InchSub: T = 0x106;   /* Core address of nominal char input USR */
const OutchSub: T = 0x109;  /* Core address of nominal char output USR */
const BreakSub: T = 0x10c;  /* Core address of nominal break test USR */
const DumpSub: T = 0x111;   /* Core address of debug core dump USR */
const PeekSub: T = 0x114;   /* Core address of nominal byte peek USR */
const Peek2Sub: T = 0x115;  /* Core address of nominal 2-byte peek USR */
const PokeSub: T = 0x118;   /* Core address of nominal byte poke USR */
const TrLogSub: T = 0x11B;  /* Core address of debug trace log USR */
const BScode: T = 0x10F;    /* Core address of backspace code */
const CanCode: T = 0x110;   /* Core address of line cancel code */
export const ILfront: T = 0x11E;   /* Core address of IL code address */
export const BadOp: u8 = 0x0F;      /* illegal op, default IL code */

const DEBUGON = 1;
const LOGSIZE: T = 0x1000;

declare function ScreenChar(ch: T): void;
declare function KeyInChar(): T;
declare function OutStr(theMsg: u8): void;

let Debugging = 0;
const DebugLog = CoreTop;
let LogHere: T = 0;
let Watcher: T = 0, Watchee: T;

let Lino: T, ILPC: T;       /* current line #, IL program counter */
let BP: T, SvPt: T;            /* current, saved TB parse pointer */
let SubStk: T, ExpnTop: T;                      /* stack pointers */
let InLend: T, SrcEnd: T;   /* current input line & TB source end */
let UserEnd: T;            /* end of IL code, start of execute loop */
let ILend: T, XQhere: T = 0;
let Broken = false;             /* =true to stop execution or listing */

/************************* Memory Utilities.. *************************/

export function Poke2(loc: i32, valu: i32): void {
    store<T>(loc, bswap<T>(valu as T));
}

function Peek2(loc: i32): T {
    return bswap<T>(load<T>(loc));
}

@inline
function Upper(ch: u8): u8 {
    return ch & (u8(0x60) < ch && ch < u8(0x7B) ? u8(0x5F) : u8(0x7F));
}

/************************** I/O Utilities... **************************/

function Ouch(ch: T): void {                 /* output char to stdout */
    if (ch == 0x0D) {
        store<u8>(TabHere, 0); /* keep count of how long this line is */
        ScreenChar(0x0A);
    }
    else if (ch >= 0x20 && ch <= 0x7E) {  /* ignore non-print control */
        store<u8>(TabHere, load<u8>(TabHere) + 1);
        ScreenChar(ch);
    }
}

function Inch(): T {       /* read input character from stdin or file */
    let ch = KeyInChar();                     /* get input from stdin */
    if (ch == 0x0A) {
        ch = 0x0D;                 /* convert line end to TB standard */
        store<u8>(TabHere, 0);                   /* reset tab counter */
    }
    return ch;
}

function StopIt(): bool {
    return Broken;
}

function OutLn(): void {      /* terminate output line to the console */
    Ouch(0x0D);
}

function OutInt(theNum: i32): void {  /* output a number to the console */
    if (theNum < 0) {
        Ouch(0x2D);
        theNum = -theNum;
    }
    if (theNum > 9)
        OutInt(theNum / 10);
    Ouch(theNum % 10 + 0x30 as T);
}

/*********************** Debugging Utilities... ***********************/

function OutHex(num: i32, nd: T): void { /* output hex num to console */
    if (nd > 1)
        OutHex(num >> 4, nd - 1);
    num &= 0x0F;
    Ouch(num + (num > 9 ? 0x37 : 0x30) as T);
}

function ShowSubs(): void { /* display subroutine stack for debugging */
    let ix: T;
    OutLn(); OutStr(0); OutHex(SubStk, 5);
    for (ix = SubStk; ix < UserEnd; ix++) {
        Ouch(0x20);
        OutInt(Peek2(ix++));
    }
    Ouch(0x5D);
}

function ShowExSt(): void {   /* display expression stack for debugging */
    let ix: T;
    OutLn(); OutStr(1); OutHex(ExpnTop, 3);
    if ((ExpnTop & 1) == 0)
        for (ix = ExpnTop; ix < ExpnStk; ix++) {
            Ouch(0x20);
            OutInt(Peek2(ix++));
        }
    else
        for (ix = ExpnTop; ix < ExpnStk; ix++) {
            Ouch(0x2E);
            OutInt(load<u8>(ix) as T);
        }
    Ouch(0x5D);
}

function ShowVars(whom: T): void {      /* display vars for debugging */
    let ix: T, valu: T = 1, prior: T = 1;
    if (whom == 0)
        whom = 26;
    else {
        whom = (whom >> 1) & 0x1F;   /* whom is a specified var, or 0 */
        valu = whom;
    }
    OutLn();
    OutStr(2);
    for (ix = valu; ix <= whom; ix++) {   /* all non-0 vars else whom */
        valu = Peek2(ix * 2 + ExpnStk);
        if (valu == 0 && prior == 0)              /* omit multiple 0s */
            continue
        prior = valu;
        Ouch(0x0D);
        Ouch(ix + 0x40);                             /* show var name */
        Ouch(0x3D);                                              /* = */
        OutInt(valu);
    }
    Ouch(0x5D);
}

function ShoMemDump(here: T, nlocs: T): void {/* display hex mem dump */
    let temp: T, thar = here & 0xF0;
    while (nlocs > 0) {
        temp = thar;
        OutLn();
        OutHex(here, 4);
        Ouch(0x3A); Ouch(0x20);
        while (thar < here) {
            Ouch(0x20); Ouch(0x20); Ouch(0x20);
            thar++;
        }
        do {
            Ouch(0x20);
            if (nlocs-- > 0)
                OutHex(load<u8>(here), 2);
            else {
                Ouch(0x20); Ouch(0x20);
            }
        }
        while (++here % 0x10);
        Ouch(0x20); Ouch(0x20);
        while (temp < thar) { Ouch(0x20); temp++; }
        while (thar < here && nlocs < 0 && ((thar & 0x0F) >= nlocs + 0x10)) {
            temp = load<u8>(thar++);
            Ouch(temp == 0x0D ? 0x5C : temp < 0x20 ? 0x60 : temp > 0x7E ? 0x7E : u8(temp));
        }
    }
    OutLn();
}

function ShoLogVal(item: i32): void { /* format & output one activity log item */
    let valu = load<i32>(item, DebugLog);
    OutLn();
    if (valu < -0x10000) {                       /* store to a variable */
        Ouch(((valu >> 17) & 0x1F) + 0x40 as T);
        Ouch(0x3D);
        OutInt((valu & 0x7FFF) - (valu & 0x8000));
    }
    else if (valu < -0x8000) {                               /* error # */
        OutStr(3);
        OutInt(-valu - 0x8000);
    }
    else if (valu < 0) {               /* only logs IL sequence changes */
        OutStr(4);
        OutHex(-Peek2(ILfront) - valu, 3);
    }
    else if (valu < 0x10000) {                      /* TinyBasic line # */
        Ouch(0x23);
        OutInt(valu);
    }
    else {                                          /* poke memory byte */
        Ouch(0x21);
        OutHex(valu, 4);
        Ouch(0x3D);
        OutInt(valu >> 0x10);
    }
}

function ShowLog(): void {        /* display activity log for debugging */
    let ix: T;
    OutLn();
    OutStr(5);
    OutInt(LogHere);
    Ouch(0x20); Ouch(0x2A); Ouch(0x2A); Ouch(0x2A);           /* " ***" */
    if (LogHere >= LOGSIZE)   /* circular, show only last 4K activities */
        for (ix = (LogHere & (LOGSIZE - 1)); ix < LOGSIZE; ix++)
            ShoLogVal(ix);
    for (ix = 0; ix < (LogHere & (LOGSIZE - 1)); ix++)
        ShoLogVal(ix);
    OutLn();
    Ouch(0x2A); Ouch(0x2A); Ouch(0x2A); Ouch(0x2A); Ouch(0x2A);/* ***** */
    OutLn();
}

function LogIt(valu: i32): void {          /* insert this valu into activity log */
    store<i32>(LogHere++ << 3, valu, DebugLog);
}

/************************ Utility functions... ************************/

function WarmStart(): void {           /* initialize existing program */
    UserEnd = Peek2(EndUser);
    SubStk = UserEnd;          /* empty subroutine, expression stacks */
    Poke2(GoStkTop, SubStk);
    ExpnTop = ExpnStk;
    Lino = 0;                                      /* not in any line */
    ILPC = 0;                                    /* start IL at front */
    SvPt = InLine;
    BP = InLine;
    load<u8>(BP, 0);
    load<u8>(TabHere, 0);
    InLend = InLine;
}

export function ColdStart(ILend_: T): void {    /* initialize program to empty */
    if (ILend_)
        ILend = ILend_;
    if (Peek2(ILfront) != ILfront + 2)
        ILend = Peek2(ILfront) + 0x800;
    Poke2(UserProg, (ILend + 0xFF) & 0xF0);   /* start Basic after IL */
    if (CoreTop > 0xFFFF) {
        Poke2(EndUser, 0xFFFE);
        Poke2(0xFFFE, 0xDEAD);
    }
    else
        Poke2(EndUser, CoreTop);
    WarmStart();
    SrcEnd = Peek2(UserProg);
    Poke2(SrcEnd++, 0);
    Poke2(EndProg, ++SrcEnd);
}

function TBerror(): void {                /* report interpreter error */
    if (ILPC == 0)                             /* already reported it */
        return;
    OutLn();
    LogIt(-ILPC - 0x8000);
    OutStr(6);        /* IL address is the error # */
    OutInt(ILPC - Peek2(ILfront));
    if (Lino > 0) {                      /* Lino=0 if in command line */
        OutStr(7);
        OutInt(Lino);
    }
    OutLn();
    if (Debugging > 0) {            /* some extra info if debugging.. */
        ShowSubs();
        ShowExSt();
        ShowVars(0);
        OutStr(8);
        OutHex(BP, 4);
        OutStr(9);
        OutHex(Peek2(UserProg), 4);
        OutStr(10);
        OutHex(Peek2(ILfront), 4);
        Ouch(0x5D);
        ShoMemDump((BP - 30) & 0xFF00, 0x100);
    }
    Lino = 0;                         /* restart interpreter at front */
    ExpnTop = ExpnStk;                 /* with empty expression stack */
    ILPC = 0;     /* cheap error test; interp reloads it from ILfront */
    BP = InLine;
}

function PushSub(valu: i32): void {    /* push value onto Gosub stack */
    if (SubStk <= SrcEnd)
        TBerror();
    else {
        SubStk -= 2;
        Poke2(GoStkTop, SubStk);
        Poke2(SubStk, valu);
    }
    if (Debugging > 0)
        ShowSubs();
}

function PopSub(): T {                   /* pop value off Gosub stack */
    if (SubStk >= Peek2(EndUser) - 1) {    /* underflow (empty stack) */
        TBerror();
        return 0xFFFF;
    }
    else {
        if (Debugging > 0)
            ShowSubs();
        SubStk += 2;
        Poke2(GoStkTop, SubStk);
        return Peek2(SubStk - 2);
    }
}

function PushExBy(valu: i32): void {   /* push byte onto expression stack */
    if (ExpnTop <= InLend)
        TBerror();
    else
        store<u8>(--ExpnTop, valu & u8(0xFF));
    if (Debugging > 0)
        ShowExSt();
}

function PopExBy(): u8 {               /* pop byte off expression stack */
    if (ExpnTop < ExpnStk)
        return load<u8>(ExpnTop++);
    TBerror();                          /* underflow (nothing in stack) */
    return 0xFF;
}

function PushExInt(valu: T): void { /* push integer onto expression stack */
    ExpnTop -= 2;
    if (ExpnTop < InLend)
        TBerror();
    else
        Poke2(ExpnTop, valu);
    if (Debugging > 0)
        ShowExSt();
}

function PopExInt(): T {            /* pop integer off expression stack */
    if (++ExpnTop < ExpnStk)
        return Peek2((ExpnTop++) - 1);
    TBerror();
    return 0xFFFF;
}

function SkipTo(here: T, fch: u8): T { /* search for'd past next marker */
    while (true) {
        let ch = load<u8>(here++);                 /* look at next char */
        if (ch == fch) return here;                           /* got it */
        if (ch == 0) return --here;
    }
}

function FindLine(theLine: T): T {    /* find theLine in TB source code */
    let ix: T;
    let here = Peek2(UserProg);                       /* start at front */
    while (true) {
        ix = Peek2(here++);
        if (theLine <= ix || ix == 0)           /* found it or overshot */
            return --here;
        here = SkipTo(++here, 0x0D);        /* skip to end of this line */
    }
}

function GoToLino(): void { /* find line # Lino and set BP to its front */
    let here: i32;
    if (Lino <= 0) {              /* Lino=0 is just command line (OK).. */
        BP = InLine;
        if (DEBUGON)
            LogIt(0);
        return;
    }
    if (DEBUGON)
        LogIt(Lino);
    if (Debugging > 0) {
        Ouch(0x20); Ouch(0x5B); Ouch(0x23); OutInt(Lino); Ouch(0x5D);
    }
    BP = FindLine(Lino);                  /* otherwise try to find it.. */
    here = Peek2(BP++);
    if ((here == 0) || Lino != here)            /* ran off the end, error off */
        TBerror();
    else
        BP++;
}

function ListIt(from: T, to: T): void {      /* list the stored program */
    let ch: u8;
    let here: T;
    if (from == 0) {        /* 0,0 defaults to all; n,0 defaults to n,n */
        to = 0xFFFF as T;
        from = 1;
    }
    else if (to == 0)
        to = from;
    here = FindLine(from);                  /* try to find first line.. */
    while (!StopIt()) {
        from = Peek2(here++);          /* get this line's # to print it */
        if (from > to || from == 0)
            break;
        here++;
        OutInt(from);
        Ouch(0x20);
        do {                                            /* print the text */
            ch = load<u8>(here++);
            Ouch(ch);
        }
        while (ch > 0x0D);
    }
}

function LineSwap(here: T): void {   /* swap SvPt/BP if here is not in InLine  */
    if (here < InLine || here >= InLend) {
        here = SvPt;
        SvPt = BP;
        BP = here;
    }
    else
        SvPt = BP;
}

export function Interp(): void {
    let ch: T;  /* comments from TinyBasic Experimenter's Kit, pp.15-21 */
    let op: T, ix: T, here: T, chpt: T;                        /* temps */
    Broken = false;          /* initialize this for possible later test */
    while (true) {
        if (StopIt()) {
            Broken = false;
            OutLn();
            OutStr(11);
            TBerror();
        }
        if (ILPC == 0) {
            ILPC = Peek2(ILfront);
            if (DEBUGON) LogIt(-ILPC);
            if (Debugging > 0) {
                OutLn(); OutStr(12); OutHex(ILPC, 4); Ouch(0x5D);
            }
        }
        if (DEBUGON) if (Watcher > 0) {             /* check watchpoint.. */
            if (((Watchee < 0) && (Watchee + 0x100 + load<u8>(Watcher)) != 0)
                || ((Watchee >= 0) && (Watchee == load<u8>(Watcher)))) {
                OutLn();
                OutStr(13);
                OutHex(Watcher, 4);
                Ouch(0x20); Ouch(0x3D); Ouch(0x20);
                OutInt(load<u8>(Watcher) as T);
                Ouch(0x20); Ouch(0x2A); Ouch(0x2A); Ouch(0x2A); Ouch(0x20);
                Watcher = 0;
                TBerror();
                continue;
            }
        }
        op = load<u8>(ILPC++);
        if (Debugging > 0) {
            OutLn(); OutStr(14); OutHex(ILPC - Peek2(ILfront) - 1, 3);
            Ouch(0x3D); OutHex(op, 2); Ouch(0x5D);
        }
        switch (op >>> 5) {
            default: switch (op) {
                case 0x0F:
                    TBerror();
                    return;

                /* SX n    00-07   Stack Exchange. */
                /*                 Exchange the top byte of computational stack with  */
                /* that "n" bytes into the stack. The top/left byte of the stack is   */
                /* considered to be byte 0, so SX 0 does nothing.                     */
                case 0x01: case 0x02: case 0x03: case 0x04: case 0x05: case 0x06: case 0x07:
                    if (ExpnTop + op >= ExpnStk) {       /* swap is below stack depth */
                        TBerror();
                        return;
                    }
                    ix = load<u8>(ExpnTop);
                    store<u8>(ExpnTop, load<u8>(ExpnTop + op));
                    store<u8>(ExpnTop + op, ix);
                    if (Debugging > 0) ShowExSt();
                    break;

                /* LB n    09nn    Push Literal Byte onto Stack.                      */
                /*                 This adds one byte to the expression stack, which  */
                /* is the second byte of the instruction. An error stop will occur if */
                /* the stack overflows. */
                case 0x09:
                    PushExBy(load<u8>(ILPC++) as T);                  /* push IL byte */
                    break;

                /* LN n    0Annnn  Push Literal Number.                               */
                /*                 This adds the following two bytes to the           */
                /* computational stack, as a 16-bit number. Stack overflow results in */
                /* an error stop. Numbers are assumed to be Big-Endian.               */
                case 0x0A:
                    PushExInt(Peek2(ILPC++));              /* get next 2 IL bytes */
                    ILPC++;
                    break;

                /* DS      0B      Duplicate Top Number (two bytes) on Stack.         */
                /*                 An error stop will occur if there are less than 2  */
                /* bytes (1 int) on the expression stack or if the stack overflows.   */
                case 0x0B:
                    op = ExpnTop;
                    ix = PopExInt();
                    if (ILPC == 0) break;                            /* underflow */
                    ExpnTop = op;
                    PushExInt(ix);
                    break;

                /* SP      0C      Stack Pop.                                         */
                /*                 The top two bytes are removed from the expression  */
                /* stack and discarded. Underflow results in an error stop.           */
                case 0x0C:
                    ix = PopExInt();
                    if (Debugging > 0) ShowExSt();
                    break;

                /* SB      10      Save BASIC Pointer.                                */
                /*                 If BASIC pointer is pointing into the input line   */
                /* buffer, it is copied to the Saved Pointer; otherwise the two       */
                /* pointers are exchanged.                                            */
                case 0x10:
                    LineSwap(BP);
                    break;

                /* RB      11      Restore BASIC Pointer.                             */
                /*                 If the Saved Pointer points into the input line    */
                /* buffer, it is replaced by the value in the BASIC pointer;          */
                /* otherwise the two pointers are exchanged.                          */
                case 0x11:
                    LineSwap(SvPt);
                    break;

                /* FV      12      Fetch Variable.                                    */
                /*                 The top byte of the computational stack is used to */
                /* index into Page 00. It is replaced by the two bytes fetched. Error */
                /* stops occur with stack overflow or underflow.                      */
                case 0x12:
                    op = PopExBy();
                    if (ILPC != 0) PushExInt(Peek2(op));
                    if (Debugging > 1) ShowVars(op);
                    break;

                /* SV      13      Store Variable.                                    */
                /*                 The top two bytes of the computational stack are   */
                /* stored into memory at the Page 00 address specified by the third   */
                /* byte on the stack. All three bytes are deleted from the stack.     */
                /* Underflow results in an error stop.                                */
                case 0x13:
                    ix = PopExInt();
                    op = PopExBy();
                    if (ILPC == 0) break;
                    Poke2(op, ix);
                    if (DEBUGON) LogIt((ix & 0xFFFF) + ((op - 0x100) << 0x10));
                    if (Debugging > 0) { ShowVars(op); if (Debugging > 1) ShowExSt(); }
                    break;

                /* GS      14      GOSUB Save.                                        */
                /*                 The current BASIC line number is pushed            */
                /* onto the BASIC region of the control stack. It is essential that   */
                /* the IL stack be empty for this to work properly but no check is    */
                /* made for that condition. An error stop occurs on stack overflow.   */
                case 0x14:
                    PushSub(Lino);                   /* push line # (possibly =0) */
                    break;

                /* RS      15      Restore Saved Line.                                */
                /*                 Pop the top two bytes off the BASIC region of the  */
                /* control stack, making them the current line number. Set the BASIC  */
                /* pointer at the beginning of that line. Note that this is the line  */
                /* containing the GOSUB which caused the line number to be saved. As  */
                /* with the GS opcode, it is essential that the IL region of the      */
                /* control stack be empty. If the line number popped off the stack    */
                /* does not correspond to a line in the BASIC program an error stop   */
                /* occurs. An error stop also results from stack underflow.           */
                case 0x15:
                    Lino = PopSub();         /* get line # (possibly =0) from pop */
                    if (ILPC != 0) GoToLino();             /* stops run if error */
                    break;

                /* GO      16      GOTO.                                              */
                /*                 Make current the BASIC line whose line number is   */
                /* equal to the value of the top two bytes in the expression stack.   */
                /* That is, the top two bytes are popped off the computational stack, */
                /* and the BASIC program is searched until a matching line number is  */
                /* found. The BASIC pointer is then positioned at the beginning of    */
                /* that line and the RUN mode flag is turned on. Stack underflow and  */
                /* non-existent BASIC line result in error stops.                     */
                case 0x16:
                    ILPC = XQhere;                /* the IL assumes an implied NX */
                    if (DEBUGON) LogIt(-ILPC);
                    Lino = PopExInt();
                    if (ILPC != 0) GoToLino();             /* stops run if error */
                    break;

                /* NE      17      Negate (two's complement).                         */
                /*                 The number in the top two bytes of the expression  */
                /* stack is replaced with its negative.                               */
                case 0x17:
                    ix = PopExInt();
                    if (ILPC != 0) PushExInt(-ix);
                    break;

                /* AD      18      Add.                                               */
                /*                 Add the two numbers represented by the top four    */
                /* bytes of the expression stack, and replace them with the two-byte  */
                /* sum. Stack underflow results in an error stop.                     */
                case 0x1B:
                    ix = PopExInt();
                    op = PopExInt();
                    if (ILPC != 0) PushExInt(op + ix);
                    break;

                /* SU      19      Subtract.                                          */
                /*                 Subtract the two-byte number on the top of the     */
                /* expression stack from the next two bytes and replace the 4 bytes   */
                /* with the two-byte difference.                                      */
                case 0x19:
                    ix = PopExInt();
                    op = PopExInt();
                    if (ILPC != 0) PushExInt(op - ix);
                    break;

                /* MP      1A      Multiply.                                          */
                /*                 Multiply the two numbers represented by the top 4  */
                /* bytes of the computational stack, and replace them with the least  */
                /* significant 16 bits of the product. Stack underflow is possible.   */
                case 0x1A:
                    ix = PopExInt();
                    op = PopExInt();
                    if (ILPC != 0) PushExInt(op * ix);
                    break;

                /* DV      1B      Divide.                                            */
                /*                 Divide the number represented by the top two bytes */
                /* of the computational stack into that represented by the next two.  */
                /* Replace the 4 bytes with the quotient and discard the remainder.   */
                /* This is a signed (two's complement) integer divide, resulting in a */
                /* signed integer quotient. Stack underflow or attempted division by  */
                /* zero result in an error stop. */
                case 0x1B:
                    ix = PopExInt();
                    op = PopExInt();
                    if (ix == 0) TBerror();                      /* divide by 0.. */
                    else if (ILPC != 0) PushExInt(op / ix);
                    break;

                /* CP      1C      Compare.                                           */
                /*                 The number in the top two bytes of the expression  */
                /* stack is compared to (subtracted from) the number in the 4th and   */
                /* fifth bytes of the stack, and the result is determined to be       */
                /* Greater, Equal, or Less. The low three bits of the third byte mask */
                /* a conditional skip in the IL program to test these conditions; if  */
                /* the result corresponds to a one bit, the next byte of the IL code  */
                /* is skipped and not executed. The three bits correspond to the      */
                /* conditions as follows:                                             */
                /*         bit 0   Result is Less                                     */
                /*         bit 1   Result is Equal                                    */
                /*         bit 2   Result is Greater                                  */
                /* Whether the skip is taken or not, all five bytes are deleted from  */
                /* the stack. This is a signed (two's complement) comparison so that  */
                /* any positive number is greater than any negative number. Multiple  */
                /* conditions, such as greater-than-or-equal or unequal (i.e.greater- */
                /* than-or-less-than), may be tested by forming the condition mask    */
                /* byte of the sum of the respective bits. In particular, a mask byte */
                /* of 7 will force an unconditional skip and a mask byte of 0 will    */
                /* force no skip. The other 5 bits of the control byte are ignored.   */
                /* Stack underflow results in an error stop.                          */
                case 0x1C:
                    ix = PopExInt();
                    op = PopExBy();
                    ix = PopExInt() - ix;                           /* <0 or =0 or >0 */
                    if (ILPC == 0) return;                             /* underflow.. */
                    if (ix < 0) ix = 1;
                    else if (ix > 0) ix = 4;                /* choose the bit to test */
                    else ix = 2;
                    if ((ix & op) > 0) ILPC++;           /* skip next IL op if bit =1 */
                    if (Debugging > 0) ShowExSt();
                    break;

                /* NX      1D      Next BASIC Statement.                              */
                /*                 Advance to next line in the BASIC program, if in   */
                /* RUN mode, or restart the IL program if in the command mode. The    */
                /* remainder of the current line is ignored. In the Run mode if there */
                /* is another line it becomes current with the pointer positioned at  */
                /* its beginning. At this time, if the Break condition returns true,  */
                /* execution is aborted and the IL program is restarted after         */
                /* printing an error message. Otherwise IL execution proceeds from    */
                /* the saved IL address (see the XQ instruction). If there are no     */
                /* more BASIC statements in the program an error stop occurs.         */
                case 0x1D:
                    if (Lino == 0) ILPC = 0;
                    else {
                        BP = SkipTo(BP, 0x0D);            /* skip to end of this line */
                        Lino = Peek2(BP++);                             /* get line # */
                        if (Lino == 0) {                           /* ran off the end */
                            TBerror();
                            break;
                        }
                        else
                            BP++;
                        ILPC = XQhere;            /* restart at saved IL address (XQ) */
                        if (DEBUGON) LogIt(-ILPC);
                    }
                    if (DEBUGON) LogIt(Lino);
                    if (Debugging > 0) {
                        Ouch(0x20); Ouch(0x5B); Ouch(0x23); OutInt(Lino); Ouch(0x5D);
                    }
                    break;

                /* LS      1F      List The Program.                                  */
                /*                 The expression stack is assumed to have two 2-byte */
                /* numbers. The top number is the line number of the last line to be  */
                /* listed, and the next is the line number of the first line to be    */
                /* listed. If the specified line numbers do not exist in the program, */
                /* the next available line (i.e. with the next higher line number) is */
                /* assumed instead in each case. If the last line to be listed comes  */
                /* before the first, no lines are listed. If Break condition comes    */
                /* true during a List operation, the remainder of the listing is      */
                /* aborted. Zero is not a valid line number, and an error stop occurs */
                /* if either line number specification is zero. The line number       */
                /* specifications are deleted from the stack.                         */
                case 0x1F:
                    op = 0;
                    ix = 0;              /* The IL seems to assume we can handle zero */
                    while (ExpnTop < ExpnStk) {     /* or more numbers, so get them.. */
                        op = ix;
                        ix = PopExInt();
                    }       /* get final line #, then initial.. */
                    if (op < 0 || ix < 0) TBerror();
                    else ListIt(ix, op);
                    break;

                /* PN      20      Print Number.                                      */
                /*                 The number represented by the top two bytes of the */
                /* expression stack is printed in decimal with leading zero           */
                /* suppression. If it is negative, it is preceded by a minus sign     */
                /* and the magnitude is printed. Stack underflow is possible.         */
                case 0x20:
                    ix = PopExInt();
                    if (ILPC)
                        OutInt(ix);
                    break;

                /* PQ      21      Print BASIC String.                                */
                /*                 The ASCII characters beginning with the current    */
                /* position of BASIC pointer are printed on the console. The string   */
                /* to be printed is terminated by quotation mark ("), and the BASIC   */
                /* pointer is left at the character following the terminal quote. An  */
                /* error stop occurs if a carriage return is imbedded in the string.  */
                case 0x21:
                    while (true) {
                        ch = load<u8>(BP++);
                        if (ch == 0x20) break;                 /* done on final quote */
                        if (ch < 0x20) {     /* error if return or other control char */
                            TBerror();
                            break;
                        }
                        Ouch(ch);
                    }                                      /* print it */
                    break;

                /* PT      22      Print Tab.                                         */
                /*                 Print one or more spaces on the console, ending at */
                /* the next multiple of eight character positions (from the left      */
                /* margin).                                                           */
                case 0x22:
                    do { Ouch(0x20); } while (load<u8>(TabHere) % 8 > 0);
                    break;

                /* NL      23      New Line.                                          */
                /*                 Output a carriage-return-linefeed sequence to the  */
                /* console.                                                           */
                case 0x23:
                    Ouch(0x0D);
                    break;

                /* PC "xxxx"  24xxxxxxXx   Print Literal String.                      */
                /*                         The ASCII string follows opcode and its    */
                /* last byte has the most significant bit set to one.                 */
                case 0x24:
                    do {
                        ix = load<u8>(ILPC++);
                        Ouch(ix & 0x7F);                 /* strip high bit for output */
                    } while ((ix & 0x80) == 0);
                    break;

                /* GL      27      Get Input Line.                                    */
                /*                 ASCII characters are accepted from console input   */
                /* to fill the line buffer. If the line length exceeds the available  */
                /* space, the excess characters are ignored and bell characters are   */
                /* output. The line is terminated by a carriage return. On completing */
                /* one line of input, the BASIC pointer is set to point to the first  */
                /* character in the input line buffer, and a carriage-return-linefeed */
                /* sequence is [not] output.                                          */
                case 0x27:
                    InLend = InLine;
                    while (true) {                   /* read input line characters... */
                        ch = Inch();
                        if (ch == 0x0D) break;                     /* end of the line */
                        else if (ch == 0x09) {
                            Debugging = (Debugging + DEBUGON) & 1;   /* toggle debug? */
                            ch = 0x20;
                        }                                    /* convert tabs to space */
                        else if (ch == load<u8>(BScode)) {          /* backspace code */
                            if (InLend > InLine) InLend--;  /* assume console already */
                            else {   /* backing up over front of line: just kill it.. */
                                Ouch(0x0D);
                                break;
                            }
                        }
                        else if (ch == load<u8>(CanCode)) {       /* cancel this line */
                            InLend = InLine;
                            Ouch(0x0D);                /* also start a new input line */
                            break;
                        }
                        else if (ch < 0x20)            /* ignore non-ASCII & controls */
                            continue;
                        else if (ch > 0x7E)
                            continue;
                        if (InLend > ExpnTop - 2)            /* discard overrun chars */
                            continue;
                        store<u8>(InLend++, ch);
                    }                                   /* insert this char in buffer */
                    while (InLend > InLine && load<u8>(InLend - 1) == 0x20)
                        InLend--;                    /* delete excess trailing spaces */
                    store<u8>(InLend++, 0x0D);          /* insert final return & null */
                    store<u8>(InLend, 0);
                    BP = InLine;
                    break;

                /* IL      2A      Insert BASIC Line.                                 */
                /*                 Beginning with the current position of the BASIC   */
                /* pointer and continuing to the [end of it], the line is inserted    */
                /* into the BASIC program space; for a line number, the top two bytes */
                /* of the expression stack are used. If this number matches a line    */
                /* already in the program it is deleted and the new one replaces it.  */
                /* If the new line consists of only a carriage return, it is not      */
                /* inserted, though any previous line with the same number will have  */
                /* been deleted. The lines are maintained in the program space sorted */
                /* by line number. If the new line to be inserted is a different size */
                /* than the old line being replaced, the remainder of the program is  */
                /* shifted over to make room or to close up the gap as necessary. If  */
                /* there is insufficient memory to fit in the new line, the program   */
                /* space is unchanged and an error stop occurs (with the IL address   */
                /* decremented). A normal error stop occurs on expression stack       */
                /* underflow or if the number is zero, which is not a valid line      */
                /* number. After completing the insertion, the IL program is          */
                /* restarted in the command mode.                                     */
                case 0x2A:
                    Lino = PopExInt();                                  /* get line # */
                    if (Lino <= 0) {              /* don't insert line #0 or negative */
                        if (ILPC != 0) TBerror();
                        else return;
                        break;
                    }
                    while (load<u8>(BP) == 0x20)               /* skip leading spaces */
                        BP++;
                    if (load<u8>(BP) == 0x0D)                       /* nothing to add */
                        ix = 0;
                    else
                        ix = InLend - BP + 2;            /* the size of the insertion */
                    op = 0;             /* this will be the number of bytes to delete */
                    chpt = FindLine(Lino);                 /* try to find this line.. */
                    if (Peek2(chpt) == Lino)           /* there is a line to delete.. */
                        op = (SkipTo(chpt + 2, 0x0D) - chpt);
                    if (ix == 0) if (op == 0) {    /* nothing to add nor delete; done */
                        Lino = 0;
                        break;
                    }
                    op = ix - op;        /* = how many more bytes to add or (-)delete */
                    if (SrcEnd + op >= SubStk) {                         /* too big.. */
                        TBerror();
                        break;
                    }
                    SrcEnd = SrcEnd + op;                                 /* new size */
                    if (op > 0)                        /* shift backend over to right */
                        for (here = SrcEnd; (here--) > chpt + ix;)
                            store<u8>(here, load<u8>(here - op));
                    else if (op < 0)                    /* shift it left to close gap */
                        for (here = chpt + ix; here < SrcEnd; here++)
                            store<u8>(here, load<u8>(here - op));
                    if (ix > 0) Poke2(chpt++, Lino);         /* insert the new line # */
                    while (ix > 2) {                         /* insert the new line.. */
                        store<u8>(++chpt, load<u8>(BP++));
                        ix--;
                    }
                    Poke2(EndProg, SrcEnd);
                    ILPC = 0;
                    Lino = 0;
                    if (Debugging > 0) ListIt(0, 0);
                    break;

                /* MT      2B      Mark the BASIC program space Empty.                */
                /*                 Also clears the BASIC region of the control stack  */
                /* and restart the IL program in the command mode. The memory bounds  */
                /* and stack pointers are reset by this instruction to signify empty  */
                /* program space, and the line number of the first line is set to 0,  */
                /* which is the indication of the end of the program.                 */
                case 0x2B:
                    ColdStart(0);
                    if (Debugging > 0) { ShowSubs(); ShowExSt(); ShowVars(0); }
                    break;

                /* XQ      2C      Execute.                                           */
                /*                 Turns on RUN mode. This instruction also saves     */
                /* the current value of the IL program counter for use of the NX      */
                /* instruction, and sets the BASIC pointer to the beginning of the    */
                /* BASIC program space. An error stop occurs if there is no BASIC     */
                /* program. This instruction must be executed at least once before    */
                /* the first execution of a NX instruction.                           */
                case 0x2C:
                    XQhere = ILPC;
                    BP = Peek2(UserProg);
                    Lino = Peek2(BP++);
                    BP++;
                    if (Lino == 0) TBerror();
                    else if (Debugging > 0) {
                        Ouch(0x20); Ouch(0x5B); Ouch(0x23); OutInt(Lino); Ouch(0x5D);
                    }
                    break;

                /* WS      2D      Stop.                                              */
                /*                 Stop execution and restart the IL program in the   */
                /* command mode. The entire control stack (including BASIC region)    */
                /* is also vacated by this instruction. This instruction effectively  */
                /* jumps to the Warm Start entry of the ML interpreter.               */
                case 0x2D:
                    WarmStart();
                    if (Debugging > 0) ShowSubs();
                    break;

                /* US      2E      Machine Language Subroutine Call.                  */
                /*                 The top six bytes of the expression stack contain  */
                /* 3 numbers with the following interpretations: The top number is    */
                /* loaded into the A (or A and B) register; the next number is loaded */
                /* into 16 bits of Index register; the third number is interpreted as */
                /* the address of a machine language subroutine to be called. These   */
                /* six bytes on the expression stack are replaced with the 16-bit     */
                /* result returned by the subroutine. Stack underflow results in an   */
                /* error stop.                                                        */
                case 0x2E:
                    Poke2(LinoCore, Lino);       /* bring these memory locations up.. */
                    Poke2(ILPCcore, ILPC);         /* ..to date, in case user looks.. */
                    Poke2(BPcore, BP);
                    Poke2(SvPtCore, SvPt);
                    ix = PopExInt() /* & 0xFFFF */;                        /* datum A */
                    here = PopExInt() /* & 0xFFFF */;                      /* datum X */
                    op = PopExInt() /* & 0xFFFF */;        /* nominal machine address */
                    if (ILPC == 0) break;
                    if (op >= Peek2(ILfront) && op < ILend) { /* call IL subroutine.. */
                        PushExInt(here);
                        PushExInt(ix);
                        PushSub(ILPC);                        /* push return location */
                        ILPC = op;
                        if (DEBUGON) LogIt(-ILPC);
                        break;
                    }
                    switch (op) {
                        case WachPoint:    /* we only do a few predefined functions.. */
                            Watcher = here;
                            if (ix > 0x7FFF) ix = -load<u8>(here) - 0x100;
                            Watchee = ix;
                            if (Debugging > 0) {
                                OutLn(); OutStr(15); OutHex(here, 4); Ouch(0x5D);
                            }
                            PushExInt(load<u8>(here));
                            break;
                        case ColdGo:
                            ColdStart(0);
                            break;
                        case WarmGo:
                            WarmStart();
                            break;
                        case InchSub:
                            PushExInt(Inch());
                            break;
                        case OutchSub:
                            Ouch(u8(ix & 0x7F));
                            PushExInt(0);
                            break;
                        case BreakSub:
                            PushExInt(StopIt() as T);
                            break;
                        case PeekSub:
                            PushExInt(load<u8>(here) as T);
                            break;
                        case Peek2Sub:
                            PushExInt(Peek2(here));
                            break;
                        case PokeSub:
                            ix = ix & 0xFF;
                            store<u8>(here, u8(ix));
                            PushExInt(ix);
                            if (DEBUGON) LogIt(((ix + 0x100) << 16) + here);
                            Lino = Peek2(LinoCore);       /* restore these pointers.. */
                            ILPC = Peek2(ILPCcore);  /* ..in case user changed them.. */
                            BP = Peek2(BPcore);
                            SvPt = Peek2(SvPtCore);
                            break;
                        case DumpSub:
                            ShoMemDump(here, ix);
                            PushExInt(here + ix);
                            break;
                        case TrLogSub:
                            ShowLog();
                            PushExInt(LogHere);
                            break;
                        default: TBerror();
                    }
                    break;

                /* RT      2F      IL Subroutine Return.                              */
                /*                 The IL control stack is popped to give the address */
                /* of the next IL instruction. An error stop occurs if the entire     */
                /* control stack (IL and BASIC) is empty.                             */
                case 0x2F:
                    ix = PopSub();                             /* get return from pop */
                    if (ix < Peek2(ILfront) || ix >= ILend) TBerror();
                    else if (ILPC != 0) {
                        ILPC = ix;
                        if (DEBUGON) LogIt(-ILPC);
                    }
                    break;

                /* JS a    3000-37FF       IL Subroutine Call.                        */
                /*                         The least significant eleven bits of this  */
                /* 2-byte instruction are added to the base address of the IL program */
                /* to become address of the next instruction. The previous contents   */
                /* of the IL program counter are pushed onto the IL region of the     */
                /* control stack. Stack overflow results in an error stop.            */
                case 0x30: case 0x31: case 0x32: case 0x33: case 0x34: case 0x35: case 0x36: case 0x37:
                    PushSub(ILPC + 1);                  /* push return location there */
                    if (ILPC == 0) break;
                    ILPC = (Peek2(ILPC - 1) & 0x7FF) + Peek2(ILfront);
                    if (DEBUGON) LogIt(-ILPC);
                    break;

                /* J a     3800-3FFF       Jump.                                      */
                /*                         The low eleven bits of this 2-byte         */
                /* instruction are added to the IL program base address to determine  */
                /* the address of the next IL instruction. The previous contents of   */
                /* the IL program counter is lost. */
                case 0x38: case 0x39: case 0x3A: case 0x3B: case 0x3C: case 0x3D: case 0x3E: case 0x3F:
                    ILPC = (Peek2(ILPC - 1) & 0x7FF) + Peek2(ILfront);
                    if (DEBUGON) LogIt(-ILPC);
                    break;

                /* NO      08      No Operation.                                      */
                /*                 This may be used as a space filler (such as to     */
                /* ignore a skip).                                                    */
                default:
                    break;
            } /* last of inner switch cases */
                break; /* end of outer switch cases 0,1 */

            /* BR a    40-7F   Relative Branch.                                   */
            /*                 The low six bits of this instruction opcode are    */
            /* added algebraically to the current value of the IL program counter */
            /* to give the address of the next IL instruction. Bit 5 of opcode is */
            /* the sign, with + signified by 1, - by 0. The range of this branch  */
            /* is +/-31 bytes from address of the byte following the opcode. An   */
            /* offset of zero (i.e. opcode 60) results in an error stop. The      */
            /* branch operation is unconditional.                                 */
            case 0x02: case 0x03:
                ILPC = ILPC + op - 0x60;
                if (DEBUGON) LogIt(-ILPC);
                break;

            /* BC a "xxx"   80xxxxXx-9FxxxxXx  String Match Branch.               */
            /*                                 The ASCII character string in IL   */
            /* following this opcode is compared to the string beginning with the */
            /* current position of the BASIC pointer, ignoring blanks in BASIC    */
            /* program. The comparison continues until either a mismatch, or an   */
            /* IL byte is reached with the most significant bit set to one. This  */
            /* is the last byte of the string in the IL, compared as a 7-bit      */
            /* character; if equal, the BASIC pointer is positioned after the     */
            /* last matching character in the BASIC program and the IL continues  */
            /* with the next instruction in sequence. Otherwise the BASIC pointer */
            /* is not altered and the low five bits of the Branch opcode are      */
            /* added to the IL program counter to form the address of the next    */
            /* IL instruction. If the strings do not match and the branch offset  */
            /* is zero an error stop occurs.                                      */
            case 0x04:
                if (op == 0x80) here = 0;                     /* to error if no match */
                else here = ILPC + (op & 0x7F);
                chpt = BP;
                ix = 0;
                while ((ix & 0x80) == 0) {
                    while (load<u8>(BP) == 0x20) BP++;            /* skip over spaces */
                    ix = load<u8>(ILPC++);
                    if ((ix & 0x7F) != Upper(load<u8>(BP++))) {
                        BP = chpt;             /* back up to front of string in Basic */
                        if (here == 0) TBerror();
                        else ILPC = here;                       /* jump forward in IL */
                        break;
                    }
                }
                if (DEBUGON) if (ILPC > 0) LogIt(-ILPC);
                break;

            /* BV a    A0-BF   Branch if Not Variable.                            */
            /*                 If the next non-blank character pointed to by the  */
            /* BASIC pointer is a capital letter, its ASCII code is [doubled and] */
            /* pushed onto the expression stack and the IL program advances to    */
            /* next instruction in sequence, leaving the BASIC pointer positioned */
            /* after the letter; if not a letter the branch is taken and BASIC    */
            /* pointer is left pointing to that character. An error stop occurs   */
            /* if the next character is not a letter and the offset of the branch */
            /* is zero, or on stack overflow.                                     */
            case 0x05:
                while (load<u8>(BP) == 0x20) BP++;                /* skip over spaces */
                ch = load<u8>(BP);
                if (ch > 0x30 && ch <= 0x5A || ch > 0x60 && ch <= 0x7A)
                    PushExBy((load<u8>(BP++) & 0x5F) * 2);
                else if (op == 0xA0) TBerror();           /* error if not letter */
                else ILPC = ILPC + op - 0xA0;
                if (DEBUGON) if (ILPC > 0) LogIt(-ILPC);
                break;

            /* BN a    C0-DF   Branch if Not a Number.                            */
            /*                 If the next non-blank character pointed to by the  */
            /* BASIC pointer is not a decimal digit, the low five bits of the     */
            /* opcode are added to the IL program counter, or if zero an error    */
            /* stop occurs. If the next character is a digit, then it and all     */
            /* decimal digits following it (ignoring blanks) are converted to a   */
            /* 16-bit binary number which is pushed onto the expression stack. In */
            /* either case the BASIC pointer is positioned at the next character  */
            /* which is neither blank nor digit. Stack overflow will result in an */
            /* error stop.                                                        */
            case 0x06:
                while (load<u8>(BP) == 0x20) BP++;                /* skip over spaces */
                ch = load<u8>(BP);
                if (ch >= 0x30 && ch < 0x40) {
                    op = 0;
                    while (true) {
                        here = load<u8>(BP++);
                        if (here == 0x20)                         /* skip over spaces */
                            continue;
                        if (here < 0x30 || here > 0x39)        /* not a decimal digit */
                            break;
                        op = op * 10 + (here & 0x0F);
                    }                                            /* insert into value */
                    BP--;                                   /* back up over non-digit */
                    PushExInt(op);
                }
                else if (op == 0xC0)                             /* error if no digit */
                    TBerror();
                else
                    ILPC = ILPC + op - 0xC0;
                if (DEBUGON) if (ILPC > 0) LogIt(-ILPC);
                break;

            /* BE a    E0-FF   Branch if Not Endline.                             */
            /*                 If the next non-blank character pointed to by the  */
            /* BASIC pointer is a carriage return, the IL program advances to the */
            /* next instruction in sequence; otherwise the low five bits of the   */
            /* opcode (if not 0) are added to the IL program counter to form the  */
            /* address of next IL instruction. In either case the BASIC pointer   */
            /* is left pointing to the first non-blank character; this            */
            /* instruction will not pass over the carriage return, which must     */
            /* remain for testing by the NX instruction. As with the other        */
            /* conditional branches, the branch may only advance the IL program   */
            /* counter from 1 to 31 bytes; an offset of zero results in an error  */
            /* stop.                                                              */
            case 0x07:
                while (load<u8>(BP) == 0x20) BP++;                /* skip over spaces */
                if (load<u8>(BP) == 0x0D)
                    BP = BP;
                else if (op == 0xE0)                         /* error if no offset */
                    TBerror();
                else
                    ILPC = ILPC + op - 0xE0;
                if (DEBUGON) if (ILPC > 0) LogIt(-ILPC);
                break;
        }
    }
}
