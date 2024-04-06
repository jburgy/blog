#include <fcntl.h>
#include <stddef.h>
#include <stdio.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <syscall.h>
#include <unistd.h>

#ifdef EMSCRIPTEN
#include <stdarg.h>

/* https://github.com/emscripten-core/emscripten/issues/6708 */
enum SYS {SYS_exit, SYS_openat, SYS_close, SYS_read, SYS_write, SYS_brk};
#endif

#define NEXT __attribute__((musttail)) return ip->word->code(env, sp, rsp, ip + 1, ip->word)
#define DEFCODE_(_link, _flag, _name, _label) \
intptr_t *_label(struct interp_t *, intptr_t *, union instr_t **, union instr_t *, union instr_t *); \
static struct word_t name_##_label __attribute__((used)) = {.link = _link, .flag = _flag | ((sizeof _name) - 1), .name = _name, .code = {.code = _label}}; \
intptr_t *_label(struct interp_t *env, intptr_t *sp, union instr_t **rsp, union instr_t *ip, union instr_t *target __attribute__((unused)))
#define DEFCODE(_link, ...) DEFCODE_(&name_##_link, __VA_ARGS__)
#define DEFCONST(_link, _flag, _name, _label, _value) DEFCODE(_link, _flag, _name, _label) { *--sp = (intptr_t)({ _value; }); NEXT; }
#define DEFWORD(_link, _flag, _name, _label, ...)\
static struct word_t name_##_label __attribute__((used)) = {.link = &name_##_link, .flag = _flag | ((sizeof _name) - 1), .name = _name, .code = {.code = DOCOL}, .data = {__VA_ARGS__}};

#define CODE(_label) {.word = &name_##_label.code}

/* https://gcc.gnu.org/onlinedocs/cpp/Stringizing.html */
#define XSTR(x) STR(x)
#define STR(x) #x

struct interp_t {
    intptr_t state;
    struct word_t *latest;
    intptr_t *argc;
    intptr_t *s0;
    intptr_t base;
    union instr_t **r0;
    char buffer[0x20];
    char *here;
};

/* A Forth instr_t. Code ("words") is a sequence of these. */
union instr_t {
    intptr_t *(*code)(struct interp_t *, intptr_t *, union instr_t **, union instr_t *, union instr_t *);
    intptr_t literal;
    union instr_t *word;
};

enum Flags {F_IMMED=0x80, F_HIDDEN=0x20, F_LENMASK=0x1f};
struct word_t {
    struct word_t *link;
    unsigned char flag;
    char name[15];
    union instr_t code;
    union instr_t data[];
};

int key(void)
{
    int ch = getchar();

    if (ch == EOF)
        exit(0);
    return ch;
}

intptr_t word(char *word_buffer)
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
    while (word && (((word->flag & (F_HIDDEN | F_LENMASK)) != count) || memcmp(word->name, name, count)))
        word = word->link;

    return word;
}

union instr_t *code_field_address(struct word_t *word)
{
    size_t offset = offsetof(struct word_t, name) + (word->flag & F_LENMASK);

    offset += __SIZEOF_POINTER__ - 1;
    offset &= -__SIZEOF_POINTER__;

    if (offset < offsetof(struct word_t, code))
        offset = offsetof(struct word_t, code);

    return (union instr_t *)((char *)word + offset);
}

intptr_t *DOCOL(struct interp_t *env, intptr_t *sp, union instr_t **rsp, union instr_t *ip, union instr_t *target)
{
    *--rsp = ip;
    ip = target + 1;
    NEXT;
}
DEFCODE_(NULL, 0, "DROP", DROP)
{
    ++sp;
    NEXT;
}
DEFCODE(DROP, 0, "SWAP", SWAP)
{
    register intptr_t tmp = sp[1];
    sp[1] = sp[0];
    sp[0] = tmp;
    NEXT;
}
DEFCONST(SWAP, 0, "DUP", DUP, sp[0])
DEFCONST(DUP, 0, "OVER", OVER, sp[1])
DEFCODE(OVER, 0, "ROT", ROT)
{
    register intptr_t a = sp[0];
    register intptr_t b = sp[1];
    register intptr_t c = sp[2];
    sp[2] = b;
    sp[1] = a;
    sp[0] = c;
    NEXT;
}
DEFCODE(ROT, 0, "-ROT", NROT)
{
    register intptr_t a = sp[0];
    register intptr_t b = sp[1];
    register intptr_t c = sp[2];
    sp[2] = a;
    sp[1] = c;
    sp[0] = b;
    NEXT;
}
DEFCODE(NROT, 0, "2DROP", TWODROP)
{
    sp += 2;
    NEXT;
}
DEFCODE(TWODROP, 0, "2DUP", TWODUP)
{
    register intptr_t a = sp[0];
    register intptr_t b = sp[1];
    *--sp = b;
    *--sp = a;
    NEXT;
}
DEFCODE(TWODUP, 0, "2SWAP", TWOSWAP)
{
    register intptr_t a = sp[0];
    register intptr_t b = sp[1];
    register intptr_t c = sp[2];
    register intptr_t d = sp[3];
    sp[3] = b;
    sp[2] = a;
    sp[1] = d;
    sp[0] = c;
    NEXT;
}
DEFCODE(TWOSWAP, 0, "?DUP", QDUP)
{
    register intptr_t a = sp[0];
    if (a)
        *--sp = a;
    NEXT;
}
DEFCODE(QDUP, 0, "1+", INCR)
{
    ++sp[0];
    NEXT;
}
DEFCODE(INCR, 0, "1-", DECR)
{
    --sp[0];
    NEXT;
}
DEFCODE(DECR, 0, XSTR(__SIZEOF_POINTER__) "+", INCRP)
{
    sp[0] += __SIZEOF_POINTER__;
    NEXT;
}
DEFCODE(INCRP, 0, XSTR(__SIZEOF_POINTER__) "-", DECRP)
{
    sp[0] -= __SIZEOF_POINTER__;
    NEXT;
};
DEFCODE(DECRP, 0, "+", ADD) 
{
    sp[1] += sp[0];
    ++sp;
    NEXT;
}
DEFCODE(ADD, 0, "-", SUB)
{
    sp[1] -= sp[0];
    ++sp;
    NEXT;
}
DEFCODE(SUB, 0, "*", MUL) 
{
    sp[1] *= sp[0];
    ++sp;
    NEXT;
}
DEFCODE(MUL, 0, "/MOD", DIVMOD)
{
    register intptr_t a = sp[1];
    register intptr_t b = sp[0];
    sp[1] = a % b;
    sp[0] = a / b;
    NEXT;
}
DEFCODE(DIVMOD, 0, "=", EQU)
{
    sp[1] = sp[0] == sp[1] ? -1 : 0;
    ++sp;
    NEXT;
}
DEFCODE(EQU, 0, "<>", NEQU)
{
    sp[1] = sp[1] == sp[0] ? 0 : -1;
    ++sp;
    NEXT;
}
DEFCODE(NEQU, 0, "<", LT)
{
    sp[1] = sp[1] < sp[0] ? -1 : 0;
    ++sp;
    NEXT;
}
DEFCODE(LT, 0, ">", GT)
{
    sp[1] = sp[1] > sp[0] ? -1 : 0;
    ++sp;
    NEXT;
}
DEFCODE(GT, 0, "<=", LE) 
{
    sp[1] = sp[1] <= sp[0] ? -1 : 0;
    ++sp;
    NEXT;
}
DEFCODE(LE, 0, ">=", GE) 
{
    sp[1] = sp[1] >= sp[0] ? -1 : 0;
    ++sp;
    NEXT;
}
DEFCODE(GE, 0, "0=", ZEQU) 
{
    sp[0] = sp[0] ? 0 : -1;
    NEXT;
}
DEFCODE(ZEQU, 0, "0<>", ZNEQU) 
{
    sp[0] = sp[0] ? -1 : 0;
    NEXT;
}
DEFCODE(ZNEQU, 0, "0<", ZLT)
{
    sp[0] = sp[0] < 0 ? -1 : 0;
    NEXT;
}
DEFCODE(ZLT, 0, "0>", ZGT)
{
    sp[0] = sp[0] > 0 ? -1 : 0;
    NEXT;
}
DEFCODE(ZGT, 0, "0<=", ZLE) 
{
    sp[0] = sp[0] <= 0 ? -1 : 0;
    NEXT;
}
DEFCODE(ZLE, 0, "0>=", ZGE) 
{
    sp[0] = sp[0] >= 0 ? -1 : 0;
    NEXT;
}
DEFCODE(ZGE, 0, "AND", AND)
{
    sp[1] &= sp[0];
    ++sp;
    NEXT;
}
DEFCODE(AND, 0, "OR", OR)
{
    sp[1] |= sp[0];
    ++sp;
    NEXT;
}
DEFCODE(OR, 0, "XOR", XOR)
{
    sp[1] ^= sp[0];
    ++sp;
    NEXT;
}
DEFCODE(XOR, 0, "INVERT", INVERT)
{
    sp[0] = ~sp[0];
    NEXT;
}
DEFCODE(INVERT, 0, "EXIT", EXIT)
{
    ip = *rsp++;
    NEXT;
}
DEFCONST(EXIT, 0, "LIT", LIT, (ip++)->literal)
DEFCODE(LIT, 0, "!", STORE)
{
    register intptr_t *p = (intptr_t *)*sp++;
    *p = *sp++;
    NEXT;
}
DEFCODE(STORE, 0, "@", FETCH)
{
    sp[0] = *(intptr_t *)sp[0];
    NEXT;
}
DEFCODE(FETCH, 0, "+!", ADDSTORE)
{
    register char **t = (char **)*sp++;
    *t += *sp++;
    NEXT;
}
DEFCODE(ADDSTORE, 0, "-!", SUBSTORE)
{
    register char **t = (char **)*sp++;
    *t -= *sp++;
    NEXT;
}
DEFCODE(SUBSTORE, 0, "C!", STOREBYTE)
{
    register char *s = (char *)*sp++;
    *s = (char)*sp++;
    NEXT;
}
DEFCODE(STOREBYTE, 0, "C@", FETCHBYTE)
{
    register char *s = (char *)sp[0];
    sp[0] = s[0];
    NEXT;
}
DEFCODE(FETCHBYTE, 0, "C@C!", CCOPY)
{
    *(char *)sp[1] = *(char *)sp[0];
    ++sp;
    NEXT;
}
DEFCODE(CCOPY, 0, "CMOVE", CMOVE)
{
    sp[2] = (intptr_t)memmove((void *)sp[1], (const void *)sp[2], sp[0]);
    sp += 2;
    NEXT;
}
DEFCONST(CMOVE, 0, "STATE", STATE, &env->state)
DEFCONST(STATE, 0, "HERE", HERE, &env->here)
DEFCONST(HERE, 0, "LATEST", LATEST, &env->latest)
DEFCONST(LATEST, 0, "S0", SZ, &env->s0)
DEFCONST(SZ, 0, "BASE", BASE, &env->base)
DEFCONST(BASE, 0, "(ARGC)", ARGC, env->argc)
DEFCONST(ARGC, 0, "VERSION", VERSION, 47)
DEFCONST(VERSION, 0, "R0", RZ, env->r0)
DEFCONST(RZ, 0, "DOCOL", _DOCOL, DOCOL)
DEFCONST(_DOCOL, 0, "F_IMMED", __F_IMMED, F_IMMED)
DEFCONST(__F_IMMED, 0, "F_HIDDEN", __F_HIDDEN, F_HIDDEN)
DEFCONST(__F_HIDDEN, 0, "F_LENMASK", __F_LENMASK, F_LENMASK)
DEFCONST(__F_LENMASK, 0, "SYS_EXIT", SYS_EXIT, SYS_exit)
DEFCONST(SYS_EXIT, 0, "SYS_OPEN", SYS_OPEN, SYS_openat)
DEFCONST(SYS_OPEN, 0, "SYS_CLOSE", SYS_CLOSE, SYS_close)
DEFCONST(SYS_CLOSE, 0, "SYS_READ", SYS_READ, SYS_read)
DEFCONST(SYS_READ, 0, "SYS_WRITE", SYS_WRITE, SYS_write)
DEFCONST(SYS_WRITE, 0, "SYS_BRK", SYS_BRK, SYS_brk)
DEFCONST(SYS_BRK, 0, "O_RDONLY", __O_RDONLY, O_RDONLY)
DEFCONST(__O_RDONLY, 0, "O_WRONLY", __O_WRONLY, O_WRONLY)
DEFCONST(__O_WRONLY, 0, "O_RDWR", __O_RDWR, O_RDWR)
DEFCONST(__O_RDWR, 0, "O_CREAT", __O_CREAT, O_CREAT)
DEFCONST(__O_CREAT, 0, "O_EXCL", __O_EXCL, O_EXCL)
DEFCONST(__O_EXCL, 0, "O_TRUNC", __O_TRUNC, O_TRUNC)
DEFCONST(__O_TRUNC, 0, "O_APPEND", __O_APPEND, O_APPEND)
DEFCONST(__O_APPEND, 0, "O_NONBLOCK", __O_NONBLOCK, O_NONBLOCK)
DEFCODE(__O_NONBLOCK, 0, ">R", TOR)
{
    *--rsp = (union instr_t *)*sp++;
    NEXT;
}
DEFCONST(TOR, 0, "R>", FROMR, *rsp++)
DEFCONST(FROMR, 0, "RSP@", RSPFETCH, (intptr_t)rsp)
DEFCODE(RSPFETCH, 0, "RSP!", RSPSTORE)
{
    rsp = (union instr_t **)*sp++;
    NEXT;
}
DEFCODE(RSPSTORE, 0, "RDROP", RDROP)
{
    ++rsp;
    NEXT;
}
DEFCONST(RDROP, 0, "DSP@", DSPFETCH, (intptr_t)sp)
DEFCODE(DSPFETCH, 0, "DSP!", DSPSTORE)
{
    sp = (intptr_t *)sp[0];
    NEXT;
}
DEFCONST(DSPSTORE, 0, "KEY", KEY, key())
DEFCODE(KEY, 0, "EMIT", EMIT)
{
    putchar(*sp++);
    fflush(stdout);
    NEXT;
}
DEFCODE(EMIT, 0, "WORD", WORD)
{
    *--sp = (intptr_t)env->buffer;
    *--sp = word(env->buffer);
    NEXT;
}
DEFCODE(WORD, 0, "NUMBER", NUMBER)
{
    register intptr_t c = sp[0];
    register char *s = (char *)sp[1];
    register char a = s[c];
    char *r;

    s[c] = '\0';
    sp[1] = strtol(s, &r, env->base);
    sp[0] = r - s - c;
    s[c] = a;
    NEXT;
}
DEFCODE(NUMBER, 0, "FIND", FIND)
{
    register intptr_t c = *sp++;
    register char *s = (char *)*sp++;

    *--sp = (intptr_t)find(env->latest, s, c);
    NEXT;
}
DEFCODE(FIND, 0, ">CFA", TCFA)
{
    register struct word_t *new = (struct word_t *)*sp++;
    *--sp = (intptr_t)code_field_address(new);
    NEXT;
}
DEFWORD(TCFA, 0, ">DFA", TDFA, CODE(TCFA), CODE(INCRP), CODE(EXIT), CODE(EXIT))
DEFCODE(TDFA, 0, "CREATE", CREATE)
{
    register intptr_t c = *sp++;
    register char *s = (char *)*sp++;
    register struct word_t *new = (struct word_t *)((intptr_t)(env->here + __SIZEOF_POINTER__ - 1) & -__SIZEOF_POINTER__);
    new->link = env->latest;
    new->flag = c;
    memcpy(new->name, s, c);
    env->here = (char *)code_field_address(new);
    env->latest = new;
    NEXT;
}
DEFCODE(CREATE, 0, ",", COMMA)
{
    register union instr_t *p = (union instr_t *)env->here;
    (p++)->word = (union instr_t *)*sp++;
    env->here = (char *)p;
    NEXT;
}
DEFCODE(COMMA, F_IMMED, "[", LBRAC)
{
    env->state = 0;
    NEXT;
}
DEFCODE(LBRAC, 0, "]", RBRAC)
{
    env->state = 1;
    NEXT;
}
DEFCODE(RBRAC, F_IMMED, "IMMEDIATE", IMMEDIATE)
{
    env->latest->flag ^= F_IMMED;
    NEXT;
}
DEFCODE(IMMEDIATE, 0, "HIDDEN", HIDDEN)
{
    register struct word_t *new = (typeof(new))*sp++;
    new->flag ^= F_HIDDEN;
    NEXT;
}
DEFWORD(HIDDEN, 0, "HIDE", HIDE, CODE(WORD), CODE(FIND), CODE(HIDDEN), CODE(EXIT))
DEFWORD(HIDE, 0, ":", COLON, CODE(WORD), CODE(CREATE), CODE(LIT), {.code = DOCOL},
    CODE(COMMA), CODE(LATEST), CODE(FETCH), CODE(HIDDEN), CODE(RBRAC), CODE(EXIT))
DEFWORD(COLON, F_IMMED, ";", SEMICOLON, CODE(LIT), CODE(EXIT), CODE(COMMA),
    CODE(LATEST), CODE(FETCH), CODE(HIDDEN), CODE(LBRAC), CODE(EXIT))
DEFCONST(SEMICOLON, 0, "'", TICK, (ip++)->literal)
DEFCODE(TICK, 0, "BRANCH", BRANCH)
{
    ip += ip->literal / __SIZEOF_POINTER__;
    NEXT;
}
DEFCODE(BRANCH, 0, "0BRANCH", ZBRANCH)
{
    if (!*sp++)
        __attribute__((musttail)) return BRANCH(env, sp, rsp, ip, ip->word);
    ++ip;
    NEXT;
}
DEFCODE(ZBRANCH, 0, "LITSTRING", LITSTRING)
{
    register intptr_t c = (ip++)->literal;
    *--sp = (intptr_t)ip;
    *--sp = c;
    ip += (c + __SIZEOF_POINTER__) / __SIZEOF_POINTER__;
    NEXT;
}
DEFCODE(LITSTRING, 0, "TELL", TELL)
{
    register intptr_t c = *sp++;
    register char *s = (char *)*sp++;
    write(STDOUT_FILENO, s, c);
    NEXT;
}
DEFCODE(TELL, 0, "INTERPRET", INTERPRET)
{
    static char errmsg[] = "PARSE ERROR: ";
    register union instr_t *p = (union instr_t *)env->here;
    register intptr_t a;
    register intptr_t b;
    register intptr_t c = word(env->buffer);
    register struct word_t *new = find(env->latest, env->buffer, c);
    char *r;

    if (new) {
        target = code_field_address(new);
        if ((new->flag & F_IMMED) || !env->state)
            __attribute__((musttail)) return target->code(env, sp, rsp, ip, target);
        (p++)->word = target;
    } else {
        b = env->buffer[c];
        env->buffer[c] = '\0';
        a = strtol(env->buffer, &r, env->base);
        env->buffer[c] = b;
        if (r == env->buffer) {
            write(STDERR_FILENO, errmsg, sizeof errmsg - 1);
            write(STDERR_FILENO, env->buffer, c);
            write(STDERR_FILENO, "\n", sizeof "\n" - 1);
        } else if (env->state) {
            (p++)->word = &name_LIT.code;
            (p++)->literal = a;
        } else
            *--sp = a;
    }
    env->here = (char *)p;
    NEXT;
}
DEFWORD(INTERPRET, 0, "QUIT", QUIT, CODE(RZ), CODE(RSPSTORE), CODE(INTERPRET),
    CODE(BRANCH), {.literal = -2 * __SIZEOF_POINTER__}, CODE(EXIT))
DEFCODE(QUIT, 0, "CHAR", CHAR)
{
    word(env->buffer);
    *--sp = env->buffer[0];
    NEXT;
}
DEFCODE(CHAR, 0, "EXECUTE", EXECUTE)
{
    target = (union instr_t *)*sp++;
    __attribute__((musttail)) return target->code(env, sp, rsp, ip, target);
}
DEFCODE(EXECUTE, 0, "SYSCALL3", SYSCALL3)
{
    switch (sp[0])
    {
        case SYS_openat:
            sp[3] = openat(AT_FDCWD, (const char *)sp[1], sp[2], sp[3]);
            break;
        case SYS_read:
            sp[3] = read(sp[1], (void *)sp[2], sp[3]);
            break;
        case SYS_write:
            sp[3] = write(sp[1], (const void *)sp[2], sp[3]);
            break;
    }
    sp += 3;
    NEXT;
}
DEFCODE(SYSCALL3, 0, "SYSCALL2", SYSCALL2)
{
    switch (sp[0])
    {
        case SYS_openat:
            sp[2] = openat(AT_FDCWD, (const char *)sp[1], sp[2]);
            break;
    }
    sp += 2;
    NEXT;
}
DEFCODE(SYSCALL2, 0, "SYSCALL1", SYSCALL1)
{
    switch (sp[0])
    {
        case SYS_exit:
            exit(sp[1]);
        case SYS_close:
            sp[1] = close(sp[1]);
            break;
        case SYS_brk:
            sp[1] = sp[1] ? brk((void *)sp[1]) : (intptr_t)sbrk(sp[1]);
            break;
    }
    ++sp;
    NEXT;
}

int main(int argc __attribute__((unused)), char *argv[]) {
    intptr_t N = 0x2000;
    intptr_t stack[N];
    union instr_t *return_stack[N];
    char *memory = sbrk(0x10000);
    struct interp_t env = {
        .state = 0,
        .latest = &name_SYSCALL1,
        .argc = (intptr_t *)&argv[-1],
        .s0 = stack + N,
        .base = 10,
        .r0 = return_stack + N,
        .here = memory,
    };
    static union instr_t cold_start[] = {CODE(QUIT)};
    union instr_t *ip = cold_start;

    return (intptr_t)ip->word->code(&env, env.s0, env.r0, ip, ip->word);
}