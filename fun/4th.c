/* A port of http://git.annexia.org/?p=jonesforth.git;a=blob;f=jonesforth.S to gcc */

#include <assert.h>
#include <fcntl.h>  /* O_RDONLY, O_WRONLY, O_RDWR, O_CREAT, O_EXCL, O_TRUNC, O_APPEND, O_NONBLOCK */
#include <stdlib.h> /* exit, strtol */
#include <string.h> /* memcmp, memmove, memcpy */
#include <sys/syscall.h> /* SYS_exit, SYS_open, SYS_close, SYS_read, SYS_write, SYS_creat, SYS_brk */
#include <unistd.h> /* read, write, intptr_t */

#define NEXT do { target = ip++; goto **target; } while (0)
#define DEFCODE(name_, flags_, label) {.link = prims + __COUNTER__, .flags = flags_ | ((sizeof name_) - 1), .name = name_, .code = {label}}
#define DEFWORD(link_, name_, flags_, ...) {.link = link_, .flags = flags_ | ((sizeof name_) - 1), .name = name_, .code = {&&DOCOL, __VA_ARGS__}}
#define BYTES_PER_WORD sizeof(intptr_t)
#define STACK_SIZE (0x2000 / BYTES_PER_WORD) /* Number of elements in each stack */

enum Flags {F_IMMED=0x80, F_HIDDEN=0x20, F_LENMASK=0x1f};
struct word {
    struct word *link;
    int flags;
    const char *name;
    void *code[1];
};
struct wide {
    void *link;
    int flags;
    const char *name;
    void *code[11];
};

static char word_buffer[0x20];

int key(void)
{
    static char buffer[0x1000], *currkey = buffer, *bufftop = buffer;
    ssize_t count;

    if (currkey >= bufftop)
    {
        currkey = buffer;
        count = read(STDIN_FILENO, buffer, sizeof buffer);
        if (count == 0)
            exit(0);
        bufftop = buffer + count;
    }
    return *currkey++;
}

ssize_t emit(char ch)
{
    char emit_scratch[1] = {ch};

    return write(STDOUT_FILENO, emit_scratch, sizeof emit_scratch);
}

intptr_t word(void)
{
    char ch, *s = word_buffer;

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
        *s++ = ch;
        ch = key();
    } while (ch > ' ');

    return s - word_buffer;
}

struct word *find(struct word *word, char *name, size_t count)
{
    while (word && (((word->flags & (F_HIDDEN | F_LENMASK)) != count) || memcmp(word->name, name, count)))
        word = word->link;

    return word;
}

int main(void)
{
    static struct word prims[] = {
        {.link = NULL, .flags = 4, .name = "DROP", .code = {&&DROP}},
        DEFCODE("SWAP", 0, &&SWAP),
        DEFCODE("DUP", 0, &&DUP),
        DEFCODE("OVER", 0, &&OVER),
        DEFCODE("ROT", 0, &&ROT),
        DEFCODE("-ROT", 0, &&NROT),
        DEFCODE("2DROP", 0, &&TWODROP),
        DEFCODE("2DUP", 0, &&TWODUP),
        DEFCODE("2SWAP", 0, &&TWOSWAP),
        DEFCODE("?DUP", 0, &&QDUP),
        DEFCODE("1+", 0, &&INCR),
        DEFCODE("1-", 0, &&DECR),
        DEFCODE("4+", 0, &&INCR4),
        DEFCODE("4-", 0, &&DECR4),
        DEFCODE("+", 0, &&ADD),
        DEFCODE("-", 0, &&SUB),
        DEFCODE("*", 0, &&MUL),
        DEFCODE("/MOD", 0, &&DIVMOD),
        DEFCODE("=", 0, &&EQU),
        DEFCODE("<>", 0, &&NEQU),
        DEFCODE("<", 0, &&LT),
        DEFCODE(">", 0, &&GT),
        DEFCODE("<=", 0, &&LE),
        DEFCODE(">=", 0, &&GE),
        DEFCODE("0=", 0, &&ZEQU),
        DEFCODE("0<>", 0, &&ZNEQU),
        DEFCODE("0<", 0, &&ZLT),
        DEFCODE("0>", 0, &&ZGT),
        DEFCODE("0<=", 0, &&ZLE),
        DEFCODE("0>=", 0, &&ZGE),
        DEFCODE("AND", 0, &&AND),
        DEFCODE("OR", 0, &&OR),
        DEFCODE("XOR", 0, &&XOR),
        DEFCODE("INVERT", 0, &&INVERT),
        DEFCODE("EXIT", 0, &&EXIT),
        DEFCODE("LIT", 0, &&LIT),
        DEFCODE("!", 0, &&STORE),
        DEFCODE("@", 0, &&FETCH),
        DEFCODE("+!", 0, &&ADDSTORE),
        DEFCODE("-!", 0, &&SUBSTORE),
        DEFCODE("C!", 0, &&STOREBYTE),
        DEFCODE("C@", 0, &&FETCHBYTE),
        DEFCODE("C@C!", 0, &&CCOPY),
        DEFCODE("CMOVE", 0, &&CMOVE),
        DEFCODE("STATE", 0, &&STATE),
        DEFCODE("HERE", 0, &&HERE),
        DEFCODE("LATEST", 0, &&LATEST),
        DEFCODE("S0", 0, &&S0),
        DEFCODE("STATE", 0, &&BASE),
        DEFCODE("VERSION", 0, &&JONES_VERSION),
        DEFCODE("R0", 0, &&RZ),
        DEFCODE("DOCOL", 0, &&DOCOL),
        DEFCODE("F_IMMED", 0, &&__F_IMMED),
        DEFCODE("F_HIDDEN", 0, &&__F_HIDDEN),
        DEFCODE("F_LENMASK", 0, &&__F_LENMASK),
        DEFCODE("SYS_EXIT", 0, &&SYS_EXIT),
        DEFCODE("SYS_OPEN", 0, &&SYS_OPEN),
        DEFCODE("SYS_CLOSE", 0, &&SYS_CLOSE),
        DEFCODE("SYS_READ", 0, &&SYS_READ),
        DEFCODE("SYS_WRITE", 0, &&SYS_WRITE),
        DEFCODE("SYS_CREAT", 0, &&SYS_CREAT),
        DEFCODE("SYS_BRK", 0, &&SYS_BRK),
        DEFCODE("O_RDONLY", 0, &&__O_RDONLY),
        DEFCODE("O_WRONLY", 0, &&__O_WRONLY),
        DEFCODE("O_RDWR", 0, &&__O_RDWR),
        DEFCODE("O_CREAT", 0, &&__O_CREAT),
        DEFCODE("O_EXCL", 0, &&__O_EXCL),
        DEFCODE("O_TRUNC", 0, &&__O_TRUNC),
        DEFCODE("O_APPEND", 0, &&__O_APPEND),
        DEFCODE("O_NONBLOCK", 0, &&__O_NONBLOCK),
        DEFCODE(">R", 0, &&TOR),
        DEFCODE("R>", 0, &&FROMR),
        DEFCODE("RSP@", 0, &&RSPFETCH),
        DEFCODE("RSP!", 0, &&RSPSTORE),
        DEFCODE("RDROP", 0, &&RDROP),
        DEFCODE("DSP@", 0, &&DSPFETCH),
        DEFCODE("DSP!", 0, &&DSPSTORE),
        DEFCODE("KEY", 0, &&KEY),
        DEFCODE("EMIT", 0, &&EMIT),
        DEFCODE("WORD", 0, &&WORD),
        DEFCODE("NUMBER", 0, &&NUMBER),
        DEFCODE("FIND", 0, &&FIND),
        DEFCODE(">CFA", 0, &&TCFA),
        DEFCODE("CREATE", 0, &&CREATE),
        DEFCODE(",", 0, &&COMMA),
        DEFCODE("[", F_IMMED, &&LBRAC),
        DEFCODE("]", 0, &&RBRAC),
        DEFCODE("IMMEDIATE", F_IMMED, &&IMMEDIATE),
        DEFCODE("HIDDEN", 0, &&HIDDEN),
        DEFCODE("'", 0, &&TICK),
        DEFCODE("BRANCH", 0, &&BRANCH),
        DEFCODE("0BRANCH", 0, &&ZBRANCH),
        DEFCODE("LITSTRING", 0, &&LITSTRING),
        DEFCODE("TELL", 0, &&TELL),
        DEFCODE("INTERPRET", 0, &&INTERPRET),
        DEFCODE("CHAR", 0, &&CHAR),
        DEFCODE("EXECUTE", 0, &&EXECUTE),
        DEFCODE("SYSCALL3", 0, &&SYSCALL3),
        DEFCODE("SYSCALL2", 0, &&SYSCALL2),
        DEFCODE("SYSCALL1", 0, &&SYSCALL1),
        DEFCODE("SYSCALL0", 0, &&SYSCALL0),
    };

    /* composite primitives */
    static struct wide comps[] = {
        DEFWORD(prims + (sizeof prims) / (sizeof *prims) - 1, ">DFA", 0, &&TCFA, &&INCR4, &&EXIT),
        DEFWORD(comps + 0, ":", 0, &&WORD, &&CREATE, &&LIT, &&DOCOL, &&COMMA, &&LATEST, &&FETCH, &&HIDDEN, &&RBRAC, &&EXIT),
        DEFWORD(comps + 1, ";", F_IMMED, &&LIT, &&EXIT, &&COMMA, &&LATEST, &&FETCH, &&HIDDEN, &&LBRAC, &&EXIT),
        DEFWORD(comps + 2, "HIDE", 0, &&WORD, &&FIND, &&HIDDEN, &&EXIT),
        DEFWORD(comps + 3, "QUIT", 0, &&RZ, &&RSPSTORE, &&INTERPRET, &&BRANCH, (void *)-2),  /* no &&EXIT! */
    };

    static intptr_t memory[0x10000];
    static intptr_t stack[STACK_SIZE];  /* Parameter stack */
    static void *return_stack[STACK_SIZE / 2]; /* Return stack */
    static intptr_t state = 0;
    static intptr_t *here = memory;
    struct word *latest = (struct word *)(comps + (sizeof comps) / (sizeof *comps) - 1);
    static intptr_t *sp = stack;  /* Save the initial data stack pointer in FORTH variable S0 (%esp) */
    static void **rsp = return_stack;  /* Initialize the return stack. (%ebp) */
    static intptr_t base = 10;
    static char errmsg[] = "PARSE ERROR: ";
    register void **ip = latest->code, **target;  /* asm("%esi") */
    register intptr_t a, b, c, d, *p, is_literal = 0;
    char *r;
    register char *s;
    register struct word *new;

    /* https://gcc.gnu.org/onlinedocs/gcc/Inline.html */
    inline intptr_t pop(void)
    {
        assert(sp > stack);
        return *--sp; 
    }
    inline void push(intptr_t a)
    {
        assert(sp < stack + STACK_SIZE);
        *sp++ = a; 
    }

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Warray-bounds"
    NEXT;  // Run interpreter!
#pragma GCC diagnostic pop
DROP:
    (void)pop();
    NEXT;
SWAP:
    a = pop();
    b = pop();
    push(a);
    push(b);
    NEXT;
DUP:
    a = sp[-1];
    push(a);
    NEXT;
OVER:
    a = sp[-2];
    push(a);
    NEXT;
ROT:
    a = pop();
    b = pop();
    c = pop();
    push(a);
    push(c);
    push(b);
    NEXT;
NROT:
    a = pop();
    b = pop();
    c = pop();
    push(a);
    push(c);
    push(b);
    NEXT;
TWODROP:
    (void)pop();
    (void)pop();
    NEXT;
TWODUP:
    a = sp[-1];
    b = sp[-2];
    push(a);
    push(b);
    NEXT;
TWOSWAP:
    a = pop();
    b = pop();
    c = pop();
    d = pop();
    push(b);
    push(a);
    push(d);
    push(c);
    NEXT;
QDUP:
    a = sp[-1];
    if (a)
        push(a);
    NEXT;
INCR:
    ++sp[-1];
    NEXT;
DECR:
    --sp[-1];
    NEXT;
INCR4:
    sp[-1] += BYTES_PER_WORD;
    NEXT;
DECR4:
    sp[-1] -= BYTES_PER_WORD;
    NEXT;
ADD:
    a = pop();
    sp[-1] += a;
    NEXT;
SUB:
    a = pop();
    sp[-1] -= a;
    NEXT;
MUL:
    a = pop();
    sp[-1] *= a;
    NEXT;
DIVMOD:
    b = pop();
    a = pop();
    push(a % b);
    push(a / b);
    NEXT;
EQU:
    a = pop();
    b = pop();
    push(a == b ? ~0 : 0);
    NEXT;
NEQU:
    a = pop();
    b = pop();
    push(a == b ? 0 : ~0);
    NEXT;
LT:
    a = pop();
    b = pop();
    push(a < b ? ~0 : 0);
    NEXT;
GT:
    a = pop();
    b = pop();
    push(a > b ? ~0 : 0);
    NEXT;
LE:
    a = pop();
    b = pop();
    push(a <= b ? ~0 : 0);
    NEXT;
GE:
    a = pop();
    b = pop();
    push(a >= b ? ~0 : 0);
    NEXT;
ZEQU:
    a = pop();
    push(a ? 0 : ~0);
    NEXT;
ZNEQU:
    a = pop();
    push(a ? ~0 : 0);
    NEXT;
ZLT:
    a = pop();
    push(0 < a ? ~0 : 0);
    NEXT;
ZGT:
    a = pop();
    push(0 > a ? ~0 : 0);
    NEXT;
ZLE:
    a = pop();
    push(0 <= a ? ~0 : 0);
    NEXT;
ZGE:
    a = pop();
    push(0 >= a ? ~0 : 0);
    NEXT;
AND:
    a = pop();
    sp[-1] &= a;
    NEXT;
OR:
    a = pop();
    sp[-1] |= a;
    NEXT;
XOR:
    a = pop();
    sp[-1] ^= a;
    NEXT;
INVERT:
    sp[-1] = ~sp[-1];
    NEXT;
EXIT:
    ip = *--rsp;
    NEXT;
LIT:
    push((intptr_t)*ip++);
    NEXT;
STORE:
    p = (intptr_t *)pop();
    *p = pop();
    NEXT;
FETCH:
    p = (intptr_t *)pop();
    push(*p);
    NEXT;
ADDSTORE:
    p = (intptr_t *)pop();
    *p += pop();
    NEXT;
SUBSTORE:
    p = (intptr_t *)pop();
    *p -= pop();
    NEXT;
STOREBYTE:
    s = (char *)pop();
    *s = (char)pop();
    NEXT;
FETCHBYTE:
    s = (char *)pop();
    push(*s);
    NEXT;
CCOPY:
    s = (char *)pop();
    r = (char *)pop();
    *r = *s;
    push((intptr_t)r);
    NEXT;
CMOVE:
    c = pop();
    r = (char *)pop();
    s = (char *)pop();
    push((intptr_t)memmove(r, s, c));
    NEXT;
STATE:
    push((intptr_t)&state);
    NEXT;
LATEST:
    push((intptr_t)latest);
    NEXT;
HERE:
    push((intptr_t)here);
    NEXT;
S0:
    push((intptr_t)stack);
    NEXT;
BASE:
    push((intptr_t)&base);
    NEXT;
JONES_VERSION:
    push(7);
    NEXT;
RZ:
    push((intptr_t)return_stack);
    NEXT;
DOCOL:
    *rsp++ = ip;
    ip = target + 1;
    NEXT;
__F_IMMED:
    push(F_IMMED);
    NEXT;
__F_HIDDEN:
    push(F_HIDDEN);
    NEXT;
__F_LENMASK:
    push(F_LENMASK);
    NEXT;
SYS_EXIT:
    push(SYS_exit);
    NEXT;
SYS_OPEN:
    push(SYS_open);
    NEXT;
SYS_CLOSE:
    push(SYS_close);
    NEXT;
SYS_READ:
    push(SYS_read);
    NEXT;
SYS_WRITE:
    push(SYS_write);
    NEXT;
SYS_CREAT:
    push(SYS_creat);
    NEXT;
SYS_BRK:
    push(SYS_brk);
    NEXT;
__O_RDONLY:
    push(O_RDONLY);
    NEXT;
__O_WRONLY:
    push(O_WRONLY);
    NEXT;
__O_RDWR:
    push(O_RDWR);
    NEXT;
__O_CREAT:
    push(O_CREAT);
    NEXT;
__O_EXCL:
    push(O_EXCL);
    NEXT;
__O_TRUNC:
    push(O_TRUNC);
    NEXT;
__O_APPEND:
    push(O_APPEND);
    NEXT;
__O_NONBLOCK:
    push(O_NONBLOCK);
    NEXT;
TOR:
    *rsp++ = (void *)pop();
    NEXT;
FROMR:
    push((intptr_t)*--rsp);
    NEXT;
RSPFETCH:
    push((intptr_t)rsp);
    NEXT;
RSPSTORE:
    rsp = (void **)pop();
    NEXT;
RDROP:
    --rsp;
    NEXT;
DSPFETCH:
    a = (intptr_t)sp;
    push(a);
    NEXT;
DSPSTORE:
    a = pop();
    sp = (intptr_t *)a;
    NEXT;
KEY:
    push(key());
    NEXT;
EMIT:
    emit(pop());
    NEXT;
WORD:
    push((intptr_t)word_buffer);
    push(word());
    NEXT;
NUMBER:
    c = pop(); /* length of string */
    s = (char *)pop(); /* start address of string */
    r = s + c;
    push(strtol(s, &r, base));
    push(r - s - c);
    NEXT;
FIND:
    c = pop();
    s = (char *)pop();
    a = (intptr_t)find(latest, s, c);
    push(a);
    NEXT;
TCFA:
    new = (struct word *)pop();
    push((intptr_t)new->code);
    NEXT;
CREATE:
    c = pop();
    s = (char *)pop();
    r = memcpy((char *)here, s, c);
    new = (struct word *)(here + (c + 1 + BYTES_PER_WORD) / BYTES_PER_WORD);
    new->link = latest;
    new->flags = c;
    new->name = r;
    *here++ = (intptr_t)&(new->code);
    latest = new;
    NEXT;
COMMA:
    *here++ = pop();
    NEXT;
LBRAC:
    state = 0;
    NEXT;
RBRAC:
    state = 1;
    NEXT;
IMMEDIATE:
    latest->flags ^= F_IMMED;
    NEXT;
HIDDEN:
    latest->flags ^= F_HIDDEN;
    NEXT;
TICK:
    target = ip++;
    push((intptr_t)target);
    NEXT;
BRANCH:
    ip += (intptr_t)*ip;
    NEXT;
ZBRANCH:
    if (!pop())
        goto BRANCH;
    else
        ip++;
    NEXT;
LITSTRING:
    c = (intptr_t)*ip++;
    push(c);
    push((intptr_t)ip);
    ip += (c + BYTES_PER_WORD) / BYTES_PER_WORD;
    NEXT;
TELL:
    c = pop();
    s = (char *)pop();
    write(STDOUT_FILENO, s, c);
    NEXT;
INTERPRET:
    c = word();
    is_literal = 0;
    new = find(latest, word_buffer, c);
    if (new) {
        b = new->flags & F_IMMED;
        target = new->code;
    } else {
        ++is_literal;
        a = strtol(word_buffer, &r, base);
        if (r == word_buffer) {
            write(STDERR_FILENO, errmsg, sizeof errmsg);
            write(STDERR_FILENO, word_buffer, c);
            write(STDERR_FILENO, "\n", sizeof "\n");
            NEXT;
        }
        b = 0;
        target = &&LIT;
    }
    if (state && !b) {
        *here++ = (intptr_t)target;
        if (is_literal)
            *here += a;
    } else if (is_literal) {
        push(a);
    } else {
        goto **target;
    }
    NEXT;
CHAR:
    word();
    push((intptr_t)*word_buffer);
    NEXT;
EXECUTE:
    goto *(void *)pop();
SYSCALL3:
    a = pop();
    b = pop();
    c = pop();
    d = pop();
    push(syscall(a, b, c, d));
    NEXT;
SYSCALL2:
    a = pop();
    b = pop();
    c = pop();
    push(syscall(a, b, c));
    NEXT;
SYSCALL1:
    a = pop();
    b = pop();
    push(syscall(a, b));
    NEXT;
SYSCALL0:
    a = pop();
    push(syscall(a));
    NEXT;
}
