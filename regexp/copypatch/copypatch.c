/*
 * Thompson's on-the-fly regular expression compiler, by copy-and-patch.
 *
 * x86.c and arm.c poke instruction bytes one at a time, once per ISA.  Here
 * the nodes are ordinary C (stencils.c, the same shape as ../cps.c), compiled
 * ahead of time for each ISA and distilled by gen.py into stencils_<arch>.h:
 * machine code with holes in it, plus a table saying where each hole is and
 * how to fill it.  compile-time work shrinks to
 *
 *     memcpy(code, stencil.code, stencil.size);   // copy
 *     patch(code + hole.at, hole.type, value);    // patch
 *
 * so the only per-ISA code left in this file is patch()'s few relocation
 * formulas, and the rest of the compiler never sees an instruction.
 *
 * See also https://en.wikipedia.org/wiki/Copy-and-patch and Thompson, Ken.
 * Regular Expression Search Algorithm, Communications of the ACM 11(6)
 * (June 1968), pp. 419-422.
 *
 * Thompson's lambda bookkeeping is replaced by the per-node `seen` marks in
 * stencils.c, and each character step swaps explicit thread lists exactly like
 * cps.c's search() instead of reusing the machine stack the way x86.c does.
 * That driver loop is itself a stencil, so study() returns a function you can
 * call, as in x86.c.
 */

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>

#include "state.h"

/* How a hole is filled; stencils_<arch>.h maps each ISA's ELF types onto these. */
enum reloc {
    R_ABS64,    /* 64-bit absolute value                              */
    R_PC32,     /* 32-bit displacement from the end of the field      */
    R_BRANCH26, /* arm64 B/BL: imm26 displacement in words            */
    R_MOVW0,    /* arm64 MOVZ/MOVK: 16-bit slice 0..3 of the value    */
    R_MOVW1,
    R_MOVW2,
    R_MOVW3,
};

/* The symbols stencils.c declares extern. */
enum sym {
    H_ID,
    H_C,
    H_OUT,
    H_LEFT,
    H_RIGHT,
    H_BODY,
    H_NID,
    H_START,
    NSYM,
};

struct hole {
    unsigned at;
    enum reloc type;
    enum sym sym;
    int64_t addend;
};

struct stencil {
    const uint8_t *code;
    unsigned size;
    const struct hole *holes;
    unsigned nholes;
};

#if defined(__aarch64__)
#include "stencils_aarch64.h"
#elif defined(__x86_64__)
#include "stencils_x86_64.h"
#else
#error "no stencils for this ISA: add it to the Makefile"
#endif

/* ponytail: the matcher keeps 24 bytes per node on the stack; move its lists to the heap to lift this */
enum {
    MAX_DEPTH = 256,
    MAX_NODES = 4096,
};

/* What study() returns; like x86.c's, it is the matcher itself.  HEADER bytes
 * before it sit the mapping's size and the matcher's offset in it, for forget(). */
typedef const char *(*function_t)(const char *);

enum { HEADER = 2 * sizeof(size_t) };

/* Dangling OUT holes of a fragment form a singly linked list threaded through
 * pool[] (Russ Cox's "patch list"), so concatenation is O(1). */
struct link {
    uint8_t *at;
    enum reloc type;
    int next;
    int64_t addend;
};

struct frag {
    uint8_t *entry;
    int head, tail;
};

struct builder {
    const char *p;
    uint8_t *code;
    size_t len;
    struct link *pool;
    int npool;
    uint32_t nid;
    int depth;
    bool bad;
};

static void patch(struct builder *b, uint8_t *at, enum reloc type, uintptr_t sym, int64_t addend)
{
    uintptr_t v = sym + (uintptr_t)addend;
    int64_t d = (int64_t)(v - (uintptr_t)at);
    uint32_t insn = 0;

    if (type == R_ABS64) {
        memcpy(at, &v, sizeof v);
    } else if (type == R_PC32) {
        int32_t d32 = (int32_t)d;

        b->bad |= d32 != d;
        memcpy(at, &d32, sizeof d32);
    } else if (type == R_BRANCH26) {
        memcpy(&insn, at, sizeof insn);
        b->bad |= (d & 3) != 0 || d < -(1 << 27) || d >= 1 << 27;
        insn = (insn & 0xFC000000U) | ((uint32_t)(d >> 2) & 0x03FFFFFFU);
        memcpy(at, &insn, sizeof insn);
    } else { /* R_MOVW0..3 */
        memcpy(&insn, at, sizeof insn);
        insn = (insn & ~(0xFFFFU << 5)) | (((uint32_t)(v >> (16 * (type - R_MOVW0))) & 0xFFFFU) << 5);
        memcpy(at, &insn, sizeof insn);
    }
}

static void resolve(struct builder *b, struct frag f, const uint8_t *target)
{
    for (int i = f.head; i >= 0; i = b->pool[i].next)
        patch(b, b->pool[i].at, b->pool[i].type, (uintptr_t)target, b->pool[i].addend);
}

/* f's dangling exits followed by g's; keeps f's entry */
static struct frag join(struct builder *b, struct frag f, struct frag g)
{
    struct frag j = f;

    if (g.head >= 0) {
        if (f.head < 0)
            j.head = g.head;
        else
            b->pool[f.tail].next = g.head;
        j.tail = g.tail;
    }
    return j;
}

/* Copy `st` to the end of the buffer, patch every hole `value` knows about, and
 * leave OUT dangling for whoever comes next. */
static struct frag emit(struct builder *b, const struct stencil *st, const uintptr_t value[NSYM])
{
    uint8_t *at = b->code + b->len;
    struct frag f = {at, -1, -1};

    memcpy(at, st->code, st->size);
    b->len += st->size;
    for (unsigned i = 0; i < st->nholes; i++) {
        const struct hole *h = &st->holes[i];

        if (h->sym == H_OUT) {
            b->pool[b->npool] = (struct link){at + h->at, h->type, -1, h->addend};
            if (f.head < 0)
                f.head = b->npool;
            else
                b->pool[f.tail].next = b->npool;
            f.tail = b->npool++;
        } else
            patch(b, at + h->at, h->type, value[h->sym], h->addend);
    }
    return f;
}

static struct frag parse_alt(struct builder *b);

static const struct frag none = {NULL, -1, -1};

static struct frag parse_group(struct builder *b)
{
    struct frag f = none;

    if (++b->depth <= MAX_DEPTH) {
        b->p++;
        f = parse_alt(b);
        if (*b->p == ')')
            b->p++;
        else
            b->bad = true;
    } else
        b->bad = true;
    b->depth--;
    return f;
}

static struct frag parse_atom(struct builder *b)
{
    static const char escapes[] = "abfnrtv", controls[] = "\a\b\f\n\r\t\v", literal[] = "\"()*\\|";
    char c = *b->p;

    if (c == '(')
        return parse_group(b);
    if (c == '\0' || c == ')' || c == '|' || c == '*') {
        b->bad = true; /* empty operand */
        return none;
    }
    b->p++;
    if (c == '\\' && *b->p) {
        const char *e = strchr(escapes, *b->p);

        if (e || strchr(literal, *b->p)) {
            c = e ? controls[e - escapes] : *b->p;
            b->p++;
        }
    }
    return emit(b, &stencil_ch, (uintptr_t[NSYM]){[H_ID] = b->nid++, [H_C] = (uint8_t)c});
}

static struct frag parse_rep(struct builder *b)
{
    struct frag f = parse_atom(b);

    while (!b->bad && *b->p == '*') {
        struct frag s = emit(b, &stencil_star, (uintptr_t[NSYM]){[H_ID] = b->nid++, [H_BODY] = (uintptr_t)f.entry});

        b->p++;
        resolve(b, f, s.entry); /* the body loops back to the star */
        f = s;
    }
    return f;
}

static struct frag parse_cat(struct builder *b)
{
    struct frag f = parse_rep(b);

    while (!b->bad && *b->p && *b->p != '|' && *b->p != ')') {
        struct frag g = parse_rep(b);

        resolve(b, f, g.entry);
        g.entry = f.entry;
        f = g;
    }
    return f;
}

static struct frag parse_alt(struct builder *b)
{
    struct frag f = parse_cat(b);

    while (!b->bad && *b->p == '|') {
        b->p++;
        struct frag g = parse_cat(b);
        struct frag a = emit(b, &stencil_alt, (uintptr_t[NSYM]){[H_LEFT] = (uintptr_t)f.entry, [H_RIGHT] = (uintptr_t)g.entry});

        a = join(b, join(b, a, f), g);
        f = a;
    }
    return f;
}

function_t study(const char *re);
void forget(function_t search);

/* Returns NULL if `re` is malformed or too long, or the code buffer cannot be made executable. */
function_t study(const char *re)
{
    size_t nodes = strlen(re) + 2; /* every node consumes at least one character, plus ACCEPT and SEARCH */
    if (nodes > MAX_NODES)
        return NULL;
    size_t size = HEADER + nodes * MAX_CODE;
    struct builder b = {.p = re, .pool = calloc(nodes * MAX_HOLES, sizeof(struct link))};
    void *code = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANON, -1, 0);
    struct frag search = {NULL, -1, -1};

    if (!b.pool || code == MAP_FAILED) {
        free(b.pool);
        if (code != MAP_FAILED)
            munmap(code, size);
        return NULL;
    }
    b.code = code;
    struct frag f = parse_alt(&b);

    if (!b.bad && *b.p == '\0') {
        struct frag accept = emit(&b, &stencil_accept, NULL);

        resolve(&b, f, accept.entry);
        memcpy(b.code + b.len, (size_t[]){size, b.len + HEADER}, HEADER);
        b.len += HEADER;
        search = emit(&b, &stencil_search, (uintptr_t[NSYM]){[H_NID] = b.nid, [H_START] = (uintptr_t)f.entry});
    } else
        b.bad = true;
    free(b.pool);
    if (b.bad || mprotect(code, size, PROT_READ | PROT_EXEC)) {
        munmap(code, size);
        return NULL;
    }
    __builtin___clear_cache((char *)code, (char *)code + b.len);
    return (function_t)(void *)search.entry;
}

void forget(function_t search)
{
    if (search) {
        uint8_t *code = (uint8_t *)(void *)search;
        size_t meta[2];

        memcpy(meta, code - HEADER, HEADER);
        munmap(code - meta[1], meta[0]);
    }
}

static int test(void)
{
    static const struct {
        const char *re, *s;
        long want; /* offset the matcher should report, or -1 */
    } test[] = {
        {"abcdefg", "abcdefg", 7},
        {"(a|b)*a", "ababababab", 1},
        {"(a|b)*a", "aaaaaaaaba", 1},
        {"(a|b)*a", "aaaaaabac", 1},
        {"a(b|c)*d", "abccbcccd", 9},
        {"a(b|c)*d", "abccbcccde", 9},
        {"(a|a)*", "aaaaaaaaaaaaaaaaaaaaaaaaaaaa", 0},
        {"a(b|c)*d", "abccccccccd", 11},
        {"a*", "aaab", 0},
        {"a(b|c)*d", "abcd", 4},
        {"a**", "b", 0},
        {"(a*b*)*c", "abbac", 5},
        {"(a*|b*)*c", "abac", 4},
        {"b*(c|d)", "c", 1},
        {"a(b|c)*d", "xxabd", 5},
        {"a(b|c)*d", "abc", -1},
        {"\\n\\*", "x\n*", 3},
    };
    static const char *const malformed[] = {"", "(", ")", "a)", "(a", "|a", "a|", "*", "a||b", "()"};
    int failures = 0;

    for (size_t i = 0; i < sizeof test / sizeof *test; i++) {
        function_t search = study(test[i].re);
        const char *end = search ? search(test[i].s) : NULL;
        long got = end ? end - test[i].s : -1;

        printf("%-10s %-14s %s", test[i].re, test[i].s, end ? "match found" : "match not found");
        if (end)
            printf(" after %ld bytes", got);
        printf("\n");
        if (!search || got != test[i].want) {
            fprintf(stderr, "FAIL: %s on %s: got %ld, want %ld\n", test[i].re, test[i].s, got, test[i].want);
            failures++;
        }
        forget(search);
    }
    for (size_t i = 0; i < sizeof malformed / sizeof *malformed; i++) {
        function_t search = study(malformed[i]);

        if (search) {
            fprintf(stderr, "FAIL: \"%s\" should not compile\n", malformed[i]);
            failures++;
        }
        forget(search);
    }
    for (size_t n = MAX_NODES - 2; n < MAX_NODES; n++) { /* the longest pattern study() takes, then one more */
        char *re = malloc(n + 1);
        function_t search;

        memset(re, 'a', n);
        re[n] = '\0';
        search = study(re);
        if ((search != NULL) != (n == MAX_NODES - 2)) {
            fprintf(stderr, "FAIL: %zu-character pattern: %s\n", n, search ? "compiled" : "rejected");
            failures++;
        }
        if (search)
            (void)search("aa"); /* runs with the largest frame the cap allows */
        forget(search);
        free(re);
    }
    return failures != 0;
}

/* Flag in `hit` the characters of `line` that `search` matches.  A match is the
 * one search() reports: it ends first and, among those, starts last.
 * ponytail: finding each start probes backwards, quadratic in the line length. */
static void mark(function_t search, char *line, char *hit)
{
    size_t i = 0;

    while (line[i]) {
        const char *end = search(line + i);
        size_t e, j;
        char saved;

        if (!end)
            return;
        e = (size_t)(end - line);
        if (e == i) { /* empty match */
            i++;
            continue;
        }
        saved = line[e];
        line[e] = '\0'; /* only matches ending by e can succeed now */
        for (j = e - 1; j > i && !search(line + j); j--)
            ;
        line[e] = saved;
        memset(hit + j, 1, e - j);
        i = e;
    }
}

static void print(const char *line, const char *hit)
{
    bool on = false;

    for (size_t i = 0; line[i]; i++) {
        bool h = hit[i] != 0;

        if (h != on)
            fputs(h ? "\x1b[32m" : "\x1b[0m", stdout);
        on = h;
        putchar(line[i]);
    }
    if (on)
        fputs("\x1b[0m", stdout);
    putchar('\n');
}

/* Without arguments, run the built-in tests.  Otherwise each argument is a
 * regular expression: copy standard input to standard output with everything
 * any of them matches in green, like `grep --color` that keeps every line. */
int main(int argc, char **argv)
{
    function_t *searches;
    char line[1024];
    int status = 0;

    if (argc < 2)
        return test();
    searches = calloc((size_t)argc, sizeof *searches);
    if (!searches)
        return 1;
    for (int i = 1; i < argc; i++) {
        searches[i] = study(argv[i]);
        if (!searches[i]) {
            fprintf(stderr, "%s: cannot compile %s\n", argv[0], argv[i]);
            status = 1;
        }
    }
    while (!status && fgets(line, sizeof line, stdin)) {
        char hit[sizeof line] = "";
        size_t n = strcspn(line, "\n");

        if (line[n] == '\n')
            line[n] = '\0';
        else if (n == sizeof line - 1) /* too long: drop the rest of the line */
            for (int c = getchar(); c != '\n' && c != EOF; c = getchar())
                ;
        for (int i = 1; i < argc; i++)
            mark(searches[i], line, hit);
        print(line, hit);
    }
    for (int i = 1; i < argc; i++)
        forget(searches[i]);
    free(searches);
    return status;
}
