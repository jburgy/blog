/* A port of http://git.annexia.org/?p=jonesforth.git;a=blob;f=jonesforth.S to gcc */

#include <assert.h>
#include <fcntl.h>  /* O_RDONLY, O_WRONLY, O_RDWR, O_CREAT, O_EXCL, O_TRUNC, O_APPEND, O_NONBLOCK */
#include <stdlib.h>  /* exit, strtol */
#include <string.h>  /* memcmp, memmove, memcpy */
#include <sys/syscall.h>  /* SYS_exit, SYS_open, SYS_close, SYS_read, SYS_write, SYS_creat, SYS_brk */
#include <unistd.h>  /* read, write, intptr_t */

#define NEXT do { target = ip++; goto **target; } while (0)
#define DEFCODE(_link, _flags, _name, _label) \
    static struct word name_##_label __attribute__((used)) = {.link = _link, .flags = _flags | ((sizeof _name) - 1), .name = _name, .code = {&&_label}}; \
_label

#define DEFCONST(_link, _flags, _name, _label, _value) \
    DEFCODE(_link, _flags, _name, _label): \
    push((intptr_t)_value); \
    NEXT

#define DEFWORD(_link, _flags, _name, _label, ...) \
    static struct word name_##_label __attribute__((used)) = {.link = _link, .flags = _flags | ((sizeof _name) - 1), .name = _name, .code = {&&DOCOL, __VA_ARGS__}}

#define BYTES_PER_WORD sizeof(intptr_t)
#define STACK_SIZE (0x2000 / BYTES_PER_WORD) /* Number of elements in each stack */

enum Flags {F_IMMED=0x80, F_HIDDEN=0x20, F_LENMASK=0x1f};
struct word {
    struct word *link;
    int flags;
    const char *name;
    void *code[];
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

    *s = '\0';
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
    static intptr_t memory[0x10000];
    static intptr_t stack[STACK_SIZE];  /* Parameter stack */
    static void *return_stack[STACK_SIZE / 2]; /* Return stack */
    static intptr_t *sp = stack;  /* Save the initial data stack pointer in FORTH variable S0 (%esp) */
    static void **rsp = return_stack;  /* Initialize the return stack. (%ebp) */
    register void **ip, **target;
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

goto cold_start;

DOCOL:
    *rsp++ = ip;
    ip = target + 1;
    NEXT;

DEFCODE(NULL, 0, "DROP", DROP):
    (void)pop();
    NEXT;
DEFCODE(&name_DROP, 0, "SWAP", SWAP):
    a = pop();
    b = pop();
    push(a);
    push(b);
    NEXT;
DEFCODE(&name_DROP, 0, "DUP", DUP):
    a = sp[-1];
    push(a);
    NEXT;
DEFCODE(&name_DUP, 0, "OVER", OVER):
    a = sp[-2];
    push(a);
    NEXT;
DEFCODE(&name_OVER, 0, "ROT", ROT):
    a = pop();
    b = pop();
    c = pop();
    push(a);
    push(c);
    push(b);
    NEXT;
DEFCODE(&name_ROT, 0, "-ROT", NROT):
    a = pop();
    b = pop();
    c = pop();
    push(a);
    push(c);
    push(b);
    NEXT;
DEFCODE(&name_NROT, 0, "2DROP", TWODROP):
    (void)pop();
    (void)pop();
    NEXT;
DEFCODE(&name_TWODROP, 0, "2DUP", TWODUP):
    a = sp[-1];
    b = sp[-2];
    push(a);
    push(b);
    NEXT;
DEFCODE(&name_TWODUP, 0, "2SWAP", TWOSWAP):
    a = pop();
    b = pop();
    c = pop();
    d = pop();
    push(b);
    push(a);
    push(d);
    push(c);
    NEXT;
DEFCODE(&name_TWOSWAP, 0, "?DUP", QDUP):
    a = sp[-1];
    if (a)
        push(a);
    NEXT;
DEFCODE(&name_QDUP, 0, "1+", INCR):
    ++sp[-1];
    NEXT;
DEFCODE(&name_INCR, 0, "1-", DECR):
    --sp[-1];
    NEXT;
DEFCODE(&name_DECR, 0, "4+", INCR4):
    sp[-1] += BYTES_PER_WORD;
    NEXT;
DEFCODE(&name_INCR4, 0, "4-", DECR4):
    sp[-1] -= BYTES_PER_WORD;
    NEXT;
DEFCODE(&name_DECR4, 0, "+", ADD):
    a = pop();
    sp[-1] += a;
    NEXT;
DEFCODE(&name_ADD, 0, "-", SUB):
    a = pop();
    sp[-1] -= a;
    NEXT;
DEFCODE(&name_SUB, 0, "*", MUL):
    a = pop();
    sp[-1] *= a;
    NEXT;
DEFCODE(&name_MUL, 0, "/MOD", DIVMOD):
    b = pop();
    a = pop();
    push(a % b);
    push(a / b);
    NEXT;
DEFCODE(&name_DIVMOD, 0, "=", EQU):
    a = pop();
    b = pop();
    push(a == b ? ~0 : 0);
    NEXT;
DEFCODE(&name_EQU, 0, "<>", NEQU):
    a = pop();
    b = pop();
    push(a == b ? 0 : ~0);
    NEXT;
DEFCODE(&name_NEQU, 0, "<", LT):
    a = pop();
    b = pop();
    push(a < b ? ~0 : 0);
    NEXT;
DEFCODE(&name_LT, 0, ">", GT):
    a = pop();
    b = pop();
    push(a > b ? ~0 : 0);
    NEXT;
DEFCODE(&name_GT, 0, "<=", LE):
    a = pop();
    b = pop();
    push(a <= b ? ~0 : 0);
    NEXT;
DEFCODE(&name_LE, 0, ">=", GE):
    a = pop();
    b = pop();
    push(a >= b ? ~0 : 0);
    NEXT;
DEFCODE(&name_GE, 0, "0=", ZEQU):
    a = pop();
    push(a ? 0 : ~0);
    NEXT;
DEFCODE(&name_ZEQU, 0, "0<>", ZNEQU):
    a = pop();
    push(a ? ~0 : 0);
    NEXT;
DEFCODE(&name_ZNEQU, 0, "0<", ZLT):
    a = pop();
    push(0 < a ? ~0 : 0);
    NEXT;
DEFCODE(&name_ZLT, 0, "0>", ZGT):
    a = pop();
    push(0 > a ? ~0 : 0);
    NEXT;
DEFCODE(&name_ZGT, 0, "0<=", ZLE):
    a = pop();
    push(0 <= a ? ~0 : 0);
    NEXT;
DEFCODE(&name_ZLE, 0, "0>=", ZGE):
    a = pop();
    push(0 >= a ? ~0 : 0);
    NEXT;
DEFCODE(&name_ZGE, 0, "AND", AND):
    a = pop();
    sp[-1] &= a;
    NEXT;
DEFCODE(&name_AND, 0, "OR", OR):
    a = pop();
    sp[-1] |= a;
    NEXT;
DEFCODE(&name_OR, 0, "XOR", XOR):
    a = pop();
    sp[-1] ^= a;
    NEXT;
DEFCODE(&name_XOR, 0, "INVERT", INVERT):
    sp[-1] = ~sp[-1];
    NEXT;
DEFCODE(&name_INVERT, 0, "EXIT", EXIT):
    ip = *--rsp;
    NEXT;
DEFCODE(&name_EXIT, 0, "LIT", LIT):
    push((intptr_t)*ip++);
    NEXT;
DEFCODE(&name_LIT, 0, "!", STORE):
    p = (intptr_t *)pop();
    *p = pop();
    NEXT;
DEFCODE(&name_STORE, 0, "@", FETCH):
    p = (intptr_t *)pop();
    push(*p);
    NEXT;
DEFCODE(&name_FETCH, 0, "+!", ADDSTORE):
    p = (intptr_t *)pop();
    *p += pop();
    NEXT;
DEFCODE(&name_ADDSTORE, 0, "-!", SUBSTORE):
    p = (intptr_t *)pop();
    *p -= pop();
    NEXT;
DEFCODE(&name_SUBSTORE, 0, "C!", STOREBYTE):
    s = (char *)pop();
    *s = (char)pop();
    NEXT;
DEFCODE(&name_STOREBYTE, 0, "C@", FETCHBYTE):
    s = (char *)pop();
    push(*s);
    NEXT;
DEFCODE(&name_FETCHBYTE, 0, "C@C!", CCOPY):
    s = (char *)pop();
    r = (char *)pop();
    *r = *s;
    push((intptr_t)r);
    NEXT;
DEFCODE(&name_CCOPY, 0, "CMOVE", CMOVE):
    c = pop();
    r = (char *)pop();
    s = (char *)pop();
    push((intptr_t)memmove(r, s, c));
    NEXT;
    static intptr_t state = 0;
DEFCODE(&name_CMOVE, 0, "STATE", STATE):
    push((intptr_t)&state);
    NEXT;
    static intptr_t *here = memory;
DEFCODE(&name_STATE, 0, "HERE", HERE):
    push((intptr_t)here);
    NEXT;
    static struct word *latest;
DEFCODE(&name_HERE, 0, "LATEST", LATEST):
    push((intptr_t)latest);
    NEXT;
DEFCODE(&name_LATEST, 0, "S0", SZ):
    push((intptr_t)stack);
    NEXT;
    static intptr_t base = 10;
DEFCODE(&name_SZ, 0, "BASE", BASE):
    push((intptr_t)&base);
    NEXT;
DEFCONST(&name_BASE, 0, "VERSION", VERSION, 47);
DEFCONST(&name_VERSION, 0, "R0", RZ, return_stack);
DEFCONST(&name_RZ, 0, "DOCOL", __DOCOL, &&DOCOL);
DEFCONST(&name___DOCOL, 0, "F_IMMED", __F_IMMED, F_IMMED);
DEFCONST(&name___F_IMMED, 0, "F_HIDDEN", __F_HIDDEN, F_HIDDEN);
DEFCONST(&name___F_HIDDEN, 0, "F_LENMASK", __F_LENMASK, F_LENMASK);
DEFCONST(&name___F_LENMASK, 0, "SYS_EXIT", SYS_EXIT, SYS_exit);
DEFCONST(&name_SYS_EXIT, 0, "SYS_OPEN", SYS_OPEN, SYS_open);
DEFCONST(&name_SYS_OPEN, 0, "SYS_CLOSE", SYS_CLOSE, SYS_close);
DEFCONST(&name_SYS_CLOSE, 0, "SYS_READ", SYS_READ, SYS_read);
DEFCONST(&name_SYS_READ, 0, "SYS_WRITE", SYS_WRITE, SYS_write);
DEFCONST(&name_SYS_WRITE, 0, "SYS_CREAT", SYS_CREAT, SYS_creat);
DEFCONST(&name_SYS_CREAT, 0, "SYS_BRK", SYS_BRK, SYS_brk);
DEFCONST(&name_SYS_BRK, 0, "O_RDONLY", __O_RDONLY, O_RDONLY);
DEFCONST(&name___O_RDONLY, 0, "O_WRONL", __O_WRONLY, O_WRONLY);
DEFCONST(&name___O_WRONLY, 0, "O_RDWR", __O_RDWR, O_RDWR);
DEFCONST(&name___O_RDWR, 0, "O_CREAT", __O_CREAT, O_CREAT);
DEFCONST(&name___O_CREAT, 0, "O_EXCL", __O_EXCL, O_EXCL);
DEFCONST(&name___O_EXCL, 0, "O_TRUNC", __O_TRUNC, O_TRUNC);
DEFCONST(&name___O_TRUNC, 0, "O_APPEND", __O_APPEND, O_APPEND);
DEFCONST(&name___O_APPEND, 0, "O_NONBLOCK", __O_NONBLOCK, O_NONBLOCK);
DEFCODE(&name___O_NONBLOCK, 0, ">R", TOR):
    *rsp++ = (void *)pop();
    NEXT;
DEFCODE(&name_TOR, 0, "R>", FROMR):
    push((intptr_t)*--rsp);
    NEXT;
DEFCODE(&name_FROMR, 0, "RSP@", RSPFETCH):
    push((intptr_t)rsp);
    NEXT;
DEFCODE(&name_RSPFETCH, 0, "RSP!", RSPSTORE):
    rsp = (void **)pop();
    NEXT;
DEFCODE(&name_RSPSTORE, 0, "RDROP", RDROP):
    --rsp;
    NEXT;
DEFCODE(&name_RDROP, 0, "DSP@", DSPFETCH):
    a = (intptr_t)sp;
    push(a);
    NEXT;
DEFCODE(&name_DSPFETCH, 0, "DSP!", DSPSTORE):
    a = pop();
    sp = (intptr_t *)a;
    NEXT;
DEFCODE(&name_DSPSTORE, 0, "KEY", KEY):
    push(key());
    NEXT;
DEFCODE(&name_KEY, 0, "EMIT", EMIT):
    emit(pop());
    NEXT;
DEFCODE(&name_EMIT, 0, "WORD", WORD):
    push((intptr_t)word_buffer);
    push(word());
    NEXT;
DEFCODE(&name_WORD, 0, "NUMBER", NUMBER):
    c = pop(); /* length of string */
    s = (char *)pop(); /* start address of string */
    r = s + c;
    push(strtol(s, &r, base));
    push(r - s - c);
    NEXT;
DEFCODE(&name_NUMBER, 0, "FIND", FIND):
    c = pop();
    s = (char *)pop();
    a = (intptr_t)find(latest, s, c);
    push(a);
    NEXT;
DEFCODE(&name_FIND, 0, ">CFA", TCFA):
    new = (struct word *)pop();
    push((intptr_t)new->code);
    NEXT;
DEFWORD(&name_TCFA, 0, ">DFA", TDFA, &&TCFA, &&INCR4, &&EXIT);
DEFCODE(&name_TDFA, 0, "CREATE", CREATE):
    c = pop();
    s = (char *)pop();
    r = memcpy((char *)here, s, c);
    new = (struct word *)(here + (c + 1 + BYTES_PER_WORD) / BYTES_PER_WORD);
    new->link = latest;
    new->flags = c;
    new->name = r;
    here = (intptr_t *)&(new->code);
    latest = new;
    NEXT;
DEFCODE(&name_CREATE, 0, ",", COMMA):
    *here++ = pop();
    NEXT;
DEFCODE(&name_COMMA, 0, "[", LBRAC):
    state = 0;
    NEXT;
DEFCODE(&name_LBRAC, 0, "]", RBRAC):
    state = 1;
    NEXT;
DEFWORD(&name_RBRAC, 0, ":", COLON, &&WORD, &&CREATE, &&LIT, &&DOCOL, &&COMMA, &&LATEST, &&FETCH, &&HIDDEN, &&RBRAC, &&EXIT);
DEFWORD(&name_COLON, F_IMMED, ";", SEMICOLON, &&LIT, &&EXIT, &&COMMA, &&LATEST, &&FETCH, &&HIDDEN, &&LBRAC, &&EXIT);
DEFCODE(&name_SEMICOLON, F_IMMED, "IMMEDIATE", IMMEDIATE):
    latest->flags ^= F_IMMED;
    NEXT;
DEFCODE(&name_IMMEDIATE, 0, "HIDDEN", HIDDEN):
    latest->flags ^= F_HIDDEN;
    NEXT;
DEFWORD(&name_HIDDEN, 0, "HIDE", HIDE, &&WORD, &&FIND, &&HIDDEN, &&EXIT);
DEFCODE(&name_HIDE, 0, "'", TICK):
    target = ip++;
    push((intptr_t)target);
    NEXT;
DEFCODE(&name_TICK, 0, "BRANCH", BRANCH):
    ip += (intptr_t)*ip;
    NEXT;
DEFCODE(&name_BRANCH, 0, "0BRANCH", ZBRANCH):
    if (!pop())
        goto BRANCH;
    else
        ip++;
    NEXT;
DEFCODE(&name_ZBRANCH, 0, "LITSTRING", LITSTRING):
    c = (intptr_t)*ip++;
    push(c);
    push((intptr_t)ip);
    ip += (c + BYTES_PER_WORD) / BYTES_PER_WORD;
    NEXT;
DEFCODE(&name_LITSTRING, 0, "TELL", TELL):
    c = pop();
    s = (char *)pop();
    write(STDOUT_FILENO, s, c);
    NEXT;
DEFWORD(&name_TELL, 0, "QUIT", QUIT, &&RZ, &&RSPSTORE, &&INTERPRET, &&BRANCH, (void **)-2);
    static char errmsg[] = "PARSE ERROR: ";
DEFCODE(&name_QUIT, 0, "INTERPRET", INTERPRET):
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
            *here++ = a;
    } else if (is_literal) {
        push(a);
    } else {
        goto **target;
    }
    NEXT;
DEFCODE(&name_INTERPRET, 0, "CHAR", CHAR):
    word();
    push((intptr_t)*word_buffer);
    NEXT;
DEFCODE(&name_CHAR, 0, "EXECUTE", EXECUTE):
    goto *(void *)pop();
DEFCODE(&name_EXECUTE, 0, "SYSCALL3", SYSCALL3):
    a = pop();
    b = pop();
    c = pop();
    d = pop();
    push(syscall(a, b, c, d));
    NEXT;
DEFCODE(&name_SYSCALL3, 0, "SYSCALL2", SYSCALL2):
    a = pop();
    b = pop();
    c = pop();
    push(syscall(a, b, c));
    NEXT;
DEFCODE(&name_SYSCALL2, 0, "SYSCALL1", SYSCALL1):
    a = pop();
    b = pop();
    push(syscall(a, b));
    NEXT;
DEFCODE(&name_SYSCALL1, 0, "SYSCALL0", SYSCALL0):
    a = pop();
    push(syscall(a));
    NEXT;

cold_start:
    latest = &name_SYSCALL0;
    ip = name_QUIT.code;
    NEXT;  // Run interpreter!
}
