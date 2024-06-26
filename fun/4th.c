/* A port of http://git.annexia.org/?p=jonesforth.git;a=blob;f=jonesforth.S to gcc */

#if __has_include ("cosmopolitan.h")  /* https://justine.lol/ape.html */
#include "cosmopolitan.h"
#define __NR_brk __NR_linux_brk
#else
#include <assert.h>
#include <fcntl.h>  /* O_RDONLY, O_WRONLY, O_RDWR, O_CREAT, O_EXCL, O_TRUNC, O_APPEND, O_NONBLOCK */
#include <stddef.h>  /* size_t, offsetof */
#include <stdio.h>  /* EOF, getchar_unlocked, putchar_unlocked */
#include <stdlib.h>  /* exit, strtol, syscall */
#include <string.h>  /* memcmp, memmove, memcpy */
#include <sys/syscall.h>  /* __NR_exit, __NR_open, __NR_close, __NR_read, __NR_write, __NR_creat, __NR_brk */
#include <unistd.h>  /* read, write, intptr_t */
#endif

#define NEXT do { target = *ip++; goto **target; } while (0)
#define DEFCODE_(_link, _flags, _name, _label) \
    static struct word_t name_##_label __attribute__((used)) = {.link = _link, .flags = _flags | ((sizeof _name) - 1), .name = _name, .code = {&&code_##_label}}; \
code_##_label

#define DEFCODE(_link, ...) DEFCODE_(&name_##_link, __VA_ARGS__)
#define DEFCONST(_link, _flags, _name, _label, _value) \
    DEFCODE(_link, _flags, _name, _label): \
    push((intptr_t)_value); \
    NEXT

#define DEFWORD(_link, _flags, _name, _label, ...) \
    static struct word_t name_##_label __attribute__((used)) = {.link = &name_##_link, .flags = _flags | ((sizeof _name) - 1), .name = _name, .code = {&&DOCOL, __VA_ARGS__}}

#define CODE(word) name_##word.code

/* https://gcc.gnu.org/onlinedocs/cpp/Stringizing.html */
#define XSTR(x) STR(x)
#define STR(x) #x

#define STACK_SIZE (0x2000 / __SIZEOF_POINTER__) /* Number of elements in each stack */

#ifdef EMSCRIPTEN
#include <stdarg.h>

/* https://github.com/emscripten-core/emscripten/issues/6708 */
enum SYS {__NR_read, __NR_write, __NR_open, __NR_close, __NR_brk=0x0c, __NR_exit=0x3c, __NR_creat=0x55};
int syscall(int sysno, ...)
{
    va_list ap;
    va_start(ap, sysno);
    int status;

    switch(sysno)
    {
    case __NR_read : status = read(va_arg(ap, int), va_arg(ap, void *), va_arg(ap, size_t)); break;
    case __NR_write: status = write(va_arg(ap, int), va_arg(ap, const void *), va_arg(ap, size_t)); break;
    case __NR_open : status = open(va_arg(ap, const char *), va_arg(ap, int), va_arg(ap, mode_t)); break;
    case __NR_close: status = close(va_arg(ap, int)); break;
    case __NR_brk  : status = (intptr_t)va_arg(ap, void *); status = status ? brk((void *)status) : (intptr_t)sbrk(0); break;
    case __NR_exit : status = va_arg(ap, int); va_end(ap); exit(status);
    case __NR_creat: status = creat(va_arg(ap, const char *), va_arg(ap, mode_t)); break;
    }
    va_end(ap);
    return status;
}
#endif

enum Flags {F_IMMED=0x80, F_HIDDEN=0x20, F_LENMASK=0x1f};
struct word_t {
    struct word_t *link;
    char flags;
    char name[15]
#if __has_attribute(nonstring)
    __attribute__((nonstring))
#endif
    ;  /* big enough for builtins, forth words might overflow  */
    void *code[];
};

static char word_buffer[0x20];

int key(void)
{
    int ch = getchar_unlocked();

    if (ch == EOF)
        exit(0);
    return ch;
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

struct word_t *find(struct word_t *word, char *name, size_t count)
{
    while (word && (((word->flags & (F_HIDDEN | F_LENMASK)) != count) || memcmp(word->name, name, count)))
        word = word->link;

    return word;
}

void *code_field_address(struct word_t *word)
{
    size_t offset = offsetof(struct word_t, name) + (word->flags & F_LENMASK);

    offset += __SIZEOF_POINTER__ - 1;
    offset &= -__SIZEOF_POINTER__;

    if (offset < offsetof(struct word_t, code))
        offset = offsetof(struct word_t, code);

    return ((char *)word) + offset;
}

#ifdef EMSCRIPTEN
int main(void)
#else
int main(int argc __attribute__((unused)), char *argv[])
#endif
{
    /* https://briancallahan.net/blog/20200808.html */
    intptr_t stack[STACK_SIZE];  /* Parameter stack */
    void *return_stack[STACK_SIZE]; /* Return stack */
#ifdef __clang__
    __block
#endif
    intptr_t *sp = &stack[STACK_SIZE];  /* Save the initial data stack pointer in FORTH variable S0 (%esp) */
    void **rsp = &return_stack[STACK_SIZE];  /* Initialize the return stack. (%ebp) */
    register void ***ip, **target;
    register intptr_t a, b, c, d __attribute__((unused)), *p;
    char *r;
    register char *s, **t;
    register struct word_t *new;

#ifdef __clang__
    /* https://clang.llvm.org/docs/BlockLanguageSpec.html */
    intptr_t (^pop)(void) = ^(void)
    {
        return *sp++;
    };
    void (^push)(intptr_t) = ^(intptr_t a)
    {
        *--sp = a;
    };
#else
    /* https://gcc.gnu.org/onlinedocs/gcc/Inline.html */
    __always_inline intptr_t pop(void)
    {
        assert(sp < stack + STACK_SIZE);
        return *sp++;
    }
    __always_inline void push(intptr_t a)
    {
        assert(sp > stack);
        *--sp = a;
    }
#endif

goto _start;

DOCOL:
    *--rsp = ip;
    ip = (void ***)target + 1;
    NEXT;

DODOES:  /* http://www.lisphacker.com/temp/fixes.f */
    *--rsp = ip;
    ip = (void ***)target[1];
    push((intptr_t)&target[2]);
    NEXT;

DEFCODE_(NULL, 0, "DROP", DROP):
    (void)pop();
    NEXT;
DEFCODE(DROP, 0, "SWAP", SWAP):
    a = pop();
    b = pop();
    push(a);
    push(b);
    NEXT;
DEFCONST(SWAP, 0, "DUP", DUP, sp[0]);
DEFCONST(DUP, 0, "OVER", OVER, sp[1]);
DEFCODE(OVER, 0, "ROT", ROT):
    a = pop();
    b = pop();
    c = pop();
    push(b);
    push(a);
    push(c);
    NEXT;
DEFCODE(ROT, 0, "-ROT", NROT):
    a = pop();
    b = pop();
    c = pop();
    push(a);
    push(c);
    push(b);
    NEXT;
DEFCODE(NROT, 0, "2DROP", TWODROP):
    (void)pop();
    (void)pop();
    NEXT;
DEFCODE(TWODROP, 0, "2DUP", TWODUP):
    a = sp[0];
    b = sp[1];
    push(b);
    push(a);
    NEXT;
DEFCODE(TWODUP, 0, "2SWAP", TWOSWAP):
    a = pop();
    b = pop();
    c = pop();
    d = pop();
    push(b);
    push(a);
    push(d);
    push(c);
    NEXT;
DEFCODE(TWOSWAP, 0, "?DUP", QDUP):
    a = sp[0];
    if (a)
        push(a);
    NEXT;
DEFCODE(QDUP, 0, "1+", INCR):
    ++sp[0];
    NEXT;
DEFCODE(INCR, 0, "1-", DECR):
    --sp[0];
    NEXT;
DEFCODE(DECR, 0, XSTR(__SIZEOF_POINTER__) "+", INCRP):
    sp[0] += __SIZEOF_POINTER__;
    NEXT;
DEFCODE(INCRP, 0, XSTR(__SIZEOF_POINTER__) "-", DECRP):
    sp[0] -= __SIZEOF_POINTER__;
    NEXT;
DEFCODE(DECRP, 0, "+", ADD):
    a = pop();
    sp[0] += a;
    NEXT;
DEFCODE(ADD, 0, "-", SUB):
    a = pop();
    sp[0] -= a;
    NEXT;
DEFCODE(SUB, 0, "*", MUL):
    a = pop();
    sp[0] *= a;
    NEXT;
DEFCODE(MUL, 0, "/MOD", DIVMOD):
    b = pop();
    a = pop();
    push(a % b);
    push(a / b);
    NEXT;
DEFCODE(DIVMOD, 0, "=", EQU):
    a = pop();
    b = pop();
    push(a == b ? -1 : 0);
    NEXT;
DEFCODE(EQU, 0, "<>", NEQU):
    b = pop();
    a = pop();
    push(a == b ? 0 : -1);
    NEXT;
DEFCODE(NEQU, 0, "<", LT):
    b = pop();
    a = pop();
    push(a < b ? -1 : 0);
    NEXT;
DEFCODE(LT, 0, ">", GT):
    b = pop();
    a = pop();
    push(a > b ? -1 : 0);
    NEXT;
DEFCODE(GT, 0, "<=", LE):
    b = pop();
    a = pop();
    push(a <= b ? -1 : 0);
    NEXT;
DEFCODE(LE, 0, ">=", GE):
    b = pop();
    a = pop();
    push(a >= b ? -1 : 0);
    NEXT;
DEFCODE(GE, 0, "0=", ZEQU):
    a = pop();
    push(a ? 0 : -1);
    NEXT;
DEFCODE(ZEQU, 0, "0<>", ZNEQU):
    a = pop();
    push(a ? -1 : 0);
    NEXT;
DEFCODE(ZNEQU, 0, "0<", ZLT):
    a = pop();
    push(a < 0 ? -1 : 0);
    NEXT;
DEFCODE(ZLT, 0, "0>", ZGT):
    a = pop();
    push(a > 0 ? -1 : 0);
    NEXT;
DEFCODE(ZGT, 0, "0<=", ZLE):
    a = pop();
    push(a <= 0 ? -1 : 0);
    NEXT;
DEFCODE(ZLE, 0, "0>=", ZGE):
    a = pop();
    push(a >= 0 ? -1 : 0);
    NEXT;
DEFCODE(ZGE, 0, "AND", AND):
    a = pop();
    sp[0] &= a;
    NEXT;
DEFCODE(AND, 0, "OR", OR):
    a = pop();
    sp[0] |= a;
    NEXT;
DEFCODE(OR, 0, "XOR", XOR):
    a = pop();
    sp[0] ^= a;
    NEXT;
DEFCODE(XOR, 0, "INVERT", INVERT):
    sp[0] = ~sp[0];
    NEXT;
DEFCODE(INVERT, 0, "EXIT", EXIT):
    ip = *rsp++;
    NEXT;
DEFCONST(EXIT, 0, "LIT", LIT, *ip++);
DEFCODE(LIT, 0, "!", STORE):
    p = (intptr_t *)pop();
    *p = pop();
    NEXT;
DEFCODE(STORE, 0, "@", FETCH):
    p = (intptr_t *)pop();
    push(*p);
    NEXT;
DEFCODE(FETCH, 0, "+!", ADDSTORE):
    t = (char **)pop();
    *t += pop();
    NEXT;
DEFCODE(ADDSTORE, 0, "-!", SUBSTORE):
    t = (char **)pop();
    *t -= pop();
    NEXT;
DEFCODE(SUBSTORE, 0, "C!", STOREBYTE):
    s = (char *)pop();
    *s = (char)pop();
    NEXT;
DEFCODE(STOREBYTE, 0, "C@", FETCHBYTE):
    s = (char *)pop();
    push(*s);
    NEXT;
DEFCODE(FETCHBYTE, 0, "C@C!", CCOPY):
    s = (char *)pop();
    r = (char *)pop();
    *r = *s;
    push((intptr_t)r);
    NEXT;
DEFCODE(CCOPY, 0, "CMOVE", CMOVE):
    c = pop();
    r = (char *)pop();
    s = (char *)pop();
    push((intptr_t)memmove(r, s, c));
    NEXT;
    intptr_t state;
DEFCONST(CMOVE, 0, "STATE", STATE, &state);
    char *here;
DEFCONST(STATE, 0, "HERE", HERE, &here);
    struct word_t *latest;
DEFCONST(HERE, 0, "LATEST", LATEST, &latest);
    intptr_t *s0;
DEFCONST(LATEST, 0, "S0", SZ, &s0);
    intptr_t base;
DEFCONST(SZ, 0, "BASE", BASE, &base);
#ifdef EMSCRIPTEN
DEFCONST(BASE, 0, "VERSION", VERSION, 47);
#else
DEFCONST(BASE, 0, "(ARGC)", ARGC, &argv[-1]);
DEFCONST(ARGC, 0, "VERSION", VERSION, 47);
#endif
DEFCONST(VERSION, 0, "R0", RZ, return_stack + STACK_SIZE);
DEFCONST(RZ, 0, "DOCOL", __DOCOL, &&DOCOL);
DEFCONST(__DOCOL, 0, "DODOES", __DODOES, &&DODOES);
DEFCONST(__DODOES, 0, "F_IMMED", __F_IMMED, F_IMMED);
DEFCONST(__F_IMMED, 0, "F_HIDDEN", __F_HIDDEN, F_HIDDEN);
DEFCONST(__F_HIDDEN, 0, "F_LENMASK", __F_LENMASK, F_LENMASK);
DEFCONST(__F_LENMASK, 0, "SYS_EXIT", SYS_EXIT, __NR_exit);
DEFCONST(SYS_EXIT, 0, "SYS_OPEN", SYS_OPEN, __NR_open);
DEFCONST(SYS_OPEN, 0, "SYS_CLOSE", SYS_CLOSE, __NR_close);
DEFCONST(SYS_CLOSE, 0, "SYS_READ", SYS_READ, __NR_read);
DEFCONST(SYS_READ, 0, "SYS_WRITE", SYS_WRITE, __NR_write);
DEFCONST(SYS_WRITE, 0, "SYS_CREAT", SYS_CREAT, __NR_creat);
DEFCONST(SYS_CREAT, 0, "SYS_BRK", SYS_BRK, __NR_brk);
DEFCONST(SYS_BRK, 0, "O_RDONLY", __O_RDONLY, O_RDONLY);
DEFCONST(__O_RDONLY, 0, "O_WRONLY", __O_WRONLY, O_WRONLY);
DEFCONST(__O_WRONLY, 0, "O_RDWR", __O_RDWR, O_RDWR);
DEFCONST(__O_RDWR, 0, "O_CREAT", __O_CREAT, O_CREAT);
DEFCONST(__O_CREAT, 0, "O_EXCL", __O_EXCL, O_EXCL);
DEFCONST(__O_EXCL, 0, "O_TRUNC", __O_TRUNC, O_TRUNC);
DEFCONST(__O_TRUNC, 0, "O_APPEND", __O_APPEND, O_APPEND);
DEFCONST(__O_APPEND, 0, "O_NONBLOCK", __O_NONBLOCK, O_NONBLOCK);
DEFCODE(__O_NONBLOCK, 0, ">R", TOR):
    *--rsp = (void *)pop();
    NEXT;
DEFCONST(TOR, 0, "R>", FROMR, *rsp++);
DEFCONST(FROMR, 0, "RSP@", RSPFETCH, rsp);
DEFCODE(RSPFETCH, 0, "RSP!", RSPSTORE):
    rsp = (void **)pop();
    NEXT;
DEFCODE(RSPSTORE, 0, "RDROP", RDROP):
    ++rsp;
    NEXT;
DEFCONST(RDROP, 0, "DSP@", DSPFETCH, sp);
DEFCODE(DSPFETCH, 0, "DSP!", DSPSTORE):
    a = pop();
    sp = (intptr_t *)a;
    NEXT;
DEFCONST(DSPSTORE, 0, "KEY", KEY, key());
DEFCODE(KEY, 0, "EMIT", EMIT):
    putchar_unlocked(pop());
    fflush_unlocked(stdout);
    NEXT;
DEFCODE(EMIT, 0, "WORD", WORD):
    push((intptr_t)word_buffer);
    push(word());
    NEXT;
DEFCODE(WORD, 0, "NUMBER", NUMBER):
    c = pop(); /* length of string */
    s = (char *)pop(); /* start address of string */
    a = s[c];
    s[c] = '\0';
    push(strtol(s, &r, base));
    push(r - s - c);
    s[c] = a;
    NEXT;
DEFCODE(NUMBER, 0, "FIND", FIND):
    c = pop();
    s = (char *)pop();
    new = find(latest, s, c);
    push((intptr_t)new);
    NEXT;
DEFCODE(FIND, 0, ">CFA", TCFA):
    new = (struct word_t *)pop();
    push((intptr_t)code_field_address(new));
    NEXT;
DEFWORD(TCFA, 0, ">DFA", TDFA, CODE(TCFA), CODE(INCRP), CODE(EXIT), CODE(EXIT));
DEFCODE(TDFA, 0, "CREATE", CREATE):
    c = pop();
    s = (char *)pop();
    new = (struct word_t *)((intptr_t)(here + __SIZEOF_POINTER__ - 1) & -__SIZEOF_POINTER__);
    new->link = latest;
    new->flags = c;
    memcpy(new->name, s, c);
    here = (char *)code_field_address(new);
    latest = new;
    NEXT;
DEFCODE(CREATE, 0, ",", COMMA):
    p = (intptr_t *)here;
    *p++ = pop();
    here = (char *)p;
    NEXT;
DEFCODE(COMMA, F_IMMED, "[", LBRAC):
    state = 0;
    NEXT;
DEFCODE(LBRAC, 0, "]", RBRAC):
    state = 1;
    NEXT;
DEFCODE(RBRAC, F_IMMED, "IMMEDIATE", IMMEDIATE):
    latest->flags ^= F_IMMED;
    NEXT;
DEFCODE(IMMEDIATE, 0, "HIDDEN", HIDDEN):
    new = (struct word_t *)pop();
    new->flags ^= F_HIDDEN;
    NEXT;
DEFWORD(HIDDEN, 0, "HIDE", HIDE, CODE(WORD), CODE(FIND), CODE(HIDDEN), CODE(EXIT));
DEFWORD(HIDE, 0, ":", COLON, CODE(WORD), CODE(CREATE), CODE(LIT), &&DOCOL,
    CODE(COMMA), CODE(LATEST), CODE(FETCH), CODE(HIDDEN), CODE(RBRAC), CODE(EXIT));
DEFWORD(COLON, F_IMMED, ";", SEMICOLON, CODE(LIT), CODE(EXIT), CODE(COMMA),
    CODE(LATEST), CODE(FETCH), CODE(HIDDEN), CODE(LBRAC), CODE(EXIT));
DEFCONST(SEMICOLON, 0, "'", TICK, *ip++);
DEFCODE(TICK, 0, "BRANCH", BRANCH):
    ip += ((intptr_t)*ip) / __SIZEOF_POINTER__;
    NEXT;
DEFCODE(BRANCH, 0, "0BRANCH", ZBRANCH):
    if (!pop())
        goto code_BRANCH;
    ip++;
    NEXT;
DEFCODE(ZBRANCH, 0, "LITSTRING", LITSTRING):
    c = (intptr_t)*ip++;
    push((intptr_t)ip);
    push(c);
    ip += (c + __SIZEOF_POINTER__) / __SIZEOF_POINTER__;
    NEXT;
DEFCODE(LITSTRING, 0, "TELL", TELL):
    c = pop();
    s = (char *)pop();
    write(STDOUT_FILENO, s, c);
    NEXT;
    static char errmsg[] = "PARSE ERROR: ";
DEFCODE(TELL, 0, "INTERPRET", INTERPRET):
    p = (intptr_t *)here;
    c = word();
    new = find(latest, word_buffer, c);
    if (new) {
        target = (void **)code_field_address(new);
        if ((new->flags & F_IMMED) || !state)
            goto **target;
        *p++ = (intptr_t)target;
    } else {
        b = word_buffer[c];
        word_buffer[c] = '\0';
        a = strtol(word_buffer, &r, base);
        word_buffer[c] = b;
        if (r == word_buffer) {
            write(STDERR_FILENO, errmsg, sizeof errmsg - 1);
            write(STDERR_FILENO, word_buffer, c);
            write(STDERR_FILENO, "\n", sizeof "\n" - 1);
        } else if (state) {
            *p++ = (intptr_t)CODE(LIT);
            *p++ = a;
        } else
            push(a);
    }
    here = (char *)p;
    NEXT;
DEFWORD(INTERPRET, 0, "QUIT", QUIT, CODE(RZ), CODE(RSPSTORE), CODE(INTERPRET),
    CODE(BRANCH), (void **)(-2 * __SIZEOF_POINTER__), CODE(EXIT));
DEFCODE(QUIT, 0, "CHAR", CHAR):
    word();
    push((intptr_t)*word_buffer);
    NEXT;
DEFCODE(CHAR, 0, "EXECUTE", EXECUTE):
    target = (void **)pop();
    goto **target;
DEFCODE(EXECUTE, 0, "SYSCALL3", SYSCALL3):
    a = pop();
    b = pop();
    c = pop();
    d = pop();
    push(syscall(a, b, c, d));
    NEXT;
DEFCODE(SYSCALL3, 0, "SYSCALL2", SYSCALL2):
    a = pop();
    b = pop();
    c = pop();
    push(syscall(a, b, c));
    NEXT;
DEFCODE(SYSCALL2, 0, "SYSCALL1", SYSCALL1):
    a = pop();
    b = pop();
    push(syscall(a, b));
    NEXT;
DEFCODE(SYSCALL1, 0, "SYSCALL0", SYSCALL0):
    a = pop();
    push(syscall(a));
    NEXT;

    static void *cold_start[] = {CODE(QUIT)};
_start:
    state = 0;
    here = sbrk(0x10000);
    latest = &name_SYSCALL0;
    s0 = stack + STACK_SIZE;
    base = 10;
    ip = (void ***)cold_start;
    NEXT;  /* Run interpreter! */
}
