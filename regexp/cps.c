/*
 * Portable-C continuation-passing reconstruction of the machine code that
 * x86.c's compile() emits for the single pattern "a(b|c)*d".
 *
 * See https://github.com/jburgy/blog/pull/73's Appendix B for the actual
 * bytes; this file exists so that shape can be checked, function by
 * function, against a real compiler's output instead of read off a hex
 * dump by hand.  It is not a general-purpose regex engine: every node
 * below is hard-coded to one operand of "a(b|c)*d" and nothing here
 * tokenizes, parses, or compiles a pattern at run time.
 *
 * Compiling the node functions with
 *
 *     clang -target i386-none-elf -O0 -fomit-frame-pointer -S
 *
 * reproduces the appendix's shape almost instruction for instruction:
 * node_a/node_b/node_c/node_d each become "cmp $c,%al; jne _fail; call
 * _nnode; ret" (a character node), and altern_bc/kleene_bc -- thanks to
 * __attribute__((musttail)) forcing a tail jmp instead of a second
 * call/ret pair -- become exactly "call <2nd operand>; jmp <1st operand>",
 * matching ALTERN's and KLEENE's two-instruction bodies in the appendix.
 * musttail needs Clang, or GCC 15+ (released 2025); an older or different
 * compiler is expected to accept the code (it silently ignores an
 * unrecognized statement attribute) and still match correctly, but without
 * necessarily emitting the tail jmp this paragraph describes.
 *
 * The nnode()/clist[]/nlist[]/search() below are a portable stand-in for
 * x86.c's header[]/footer[] driver.  x86.c does not keep an explicit
 * clist[]: each character, it pushes its NLIST array back onto the real
 * x86 stack as return addresses and CALLs into the freshly compiled
 * matcher, so a matched character's "call _nnode" pops its own
 * continuation off that same stack and a failed match just "ret"s --
 * the CPU's native call/return stack plays the role of CLIST (see
 * README.md's "No XCHG, no clist/nlist swap" note).  That trick needs a
 * self-modifying return address and can't be expressed in portable C, so
 * this file keeps an explicit clist[]/nlist[] pair instead, swapped every
 * character the same way threaded.c's search() does.  The trade-off is
 * that, unlike x86.c, this file needs no Rosetta (or any other emulation)
 * to run on an arm64 host: it never generates machine code, it's just an
 * ordinary (if mutually recursive) call graph.
 */

#include <assert.h>
#include <stdio.h>
#include <string.h>

#define MAXTHREADS 400

typedef void (*cont_t)(void);

static char ch;                   /* al    : current input character            */
static cont_t clist[MAXTHREADS];  /* CLIST : threads to run against `ch`        */
static cont_t nlist[MAXTHREADS];  /* NLIST : threads to run against the next ch */
static int nclist, nnlist;

/* _nnode: schedule `k` to run against the *next* character.  At most one
 * thread is ever live per character in this hard-coded automaton (only one
 * of 'a'/'b'/'c'/'d' can match a given input byte, so only one node calls
 * nnode() per character processed), so nnlist never grows past 1 in
 * practice; the assert guards that invariant instead of silently
 * overflowing nlist[] if a future edit adds another branch here. */
static void nnode(cont_t k)
{
    assert(nnlist < MAXTHREADS);
    nlist[nnlist++] = k;
}

/* forward declarations so the mutually-recursive nodes can call each other */
static void node_b(void);
static void node_c(void);
static void node_d(void);
static void altern_bc(void);
static void kleene_bc(void);

/* 'a' */
static void node_a(void)
{
    if (ch != 'a')
        return;               /* jne _fail ; ret */
    nnode(kleene_bc);         /* call _nnode      */
}

/* 'b', one arm of (b|c); on a match it loops back into the star */
static void node_b(void)
{
    if (ch != 'b')
        return;
    nnode(kleene_bc);
}

/* 'c', the other arm of (b|c) */
static void node_c(void)
{
    if (ch != 'c')
        return;
    nnode(kleene_bc);
}

/* ALTERN(b, c): try c as a real call, then unconditionally tail-jump into
 * b, so both are tested against the same character regardless of whether
 * c matched. */
static void altern_bc(void)
{
    node_c();                                  /* call node_c */
    __attribute__((musttail)) return node_b();  /* jmp  node_b */
}

/* KLEENE(b|c): try one more repetition of (b|c) as a real call, then
 * unconditionally tail-jump into whatever follows the star. */
static void kleene_bc(void)
{
    altern_bc();                                /* call altern_bc */
    __attribute__((musttail)) return node_d();  /* jmp  node_d    */
}

/* 'd' */
static void node_d(void)
{
    if (ch != 'd')
        return;
    nnode((cont_t)0);         /* NULL continuation: match found */
}

/*
 * Portable stand-in for x86.c's header[]/footer[]: swap nlist into clist
 * every character (the same way threaded.c's search() does) instead of
 * reusing the machine call stack the way x86.c does.  Returns a pointer
 * just past the match, or NULL if no thread survives to see one.
 */
static const char *search(const char *s)
{
    const char *p = s;
    int i;

    nnlist = 0;
    nnode(node_a);            /* seed CLIST with the entry point */

    for (;;) {
        memcpy(clist, nlist, (size_t)nnlist * sizeof *clist);
        nclist = nnlist;
        nnlist = 0;
        if (nclist == 0)
            return NULL;      /* every thread died: no match */

        ch = *p;
        for (i = 0; i < nclist; i++) {
            if (clist[i] == 0)
                return p;     /* NULL continuation: matched */
            clist[i]();
        }
        if (ch == '\0')
            return NULL;
        p++;
    }
}

int main(void)
{
    static const struct {
        const char *s;
        long want; /* offset search() should report, or -1 for no match */
    } test[] = {
        {"abccbcccd", 9},
        {"abccbcccde", 9},
        {"abccccccccd", 11},
        {"abcd", 4},
        {"abd", 3},
        {"ad", 2},
        {"d", -1},
        {"aed", -1},
        {"abc", -1},
    };
    int failures = 0;

    for (size_t i = 0; i < sizeof test / sizeof *test; i++) {
        const char *r = search(test[i].s);
        long got = r ? (long)(r - test[i].s) : -1;

        printf("a(b|c)*d %-14s", test[i].s);
        if (got >= 0)
            printf(" match found after %ld bytes\n", got);
        else
            printf(" match not found\n");

        if (got != test[i].want) {
            fprintf(stderr, "FAIL: %s: got %ld, want %ld\n",
                    test[i].s, got, test[i].want);
            failures++;
        }
    }

    return failures != 0;
}
