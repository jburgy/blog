/*
 * Copy-and-patch stencils for Thompson's matcher: the same continuation-passing
 * nodes as ../cps.c, but written so that copypatch.c can memcpy their machine
 * code and fill in the holes.  See Makefile and gen.py for how this file
 * becomes stencils_<arch>.h.
 *
 * Every `extern` symbol below is a hole, not a real dependency.  The object
 * file records where each one is used (a relocation); copypatch.c resolves it
 * with the address of a node instead of letting a linker do it.
 *
 *   ID            index of this node's slot in state->seen[]   (scalar)
 *   C             the character to compare against             (scalar)
 *   OUT           the node that follows this one               (code address)
 *   LEFT, RIGHT   the two arms of an alternation               (code address)
 *   BODY          the repeated sub-expression of a star        (code address)
 *   NID           number of ID slots the whole pattern uses    (scalar)
 *   START         the pattern's first node                     (code address)
 *
 * A scalar hole is the *address* of an extern char, which -mcmodel=large turns
 * into a full-width immediate on every ISA.  Anything that is not a hole,
 * including data or helper calls, would make gen.py fail.
 */

#include "state.h"

extern char ID, C, NID;
extern node_fn OUT, LEFT, RIGHT, BODY, START;

#define HOLE(sym) ((uintptr_t)&(sym))

/* musttail needs `return f()` in a void function, which ISO C forbids */
#pragma clang diagnostic ignored "-Wpedantic"
#define TAIL __attribute__((musttail)) return

/* Skip a node that already ran for this character; this is what stops (a*)*
 * from recursing forever and what keeps the thread list from outgrowing the
 * node count. */
#define VISIT()                          \
    uint64_t *seen = &s->seen[HOLE(ID)]; \
    if (*seen == s->gen)                 \
        return;                          \
    *seen = s->gen

void ch(state *s)
{
    VISIT();
    if (s->ch != (uint8_t)HOLE(C))
        return;
    s->next[s->n++] = OUT;
}

void alt(state *s)
{
    LEFT(s);
    TAIL RIGHT(s);
}

void star(state *s)
{
    VISIT();
    BODY(s);
    TAIL OUT(s);
}

void accept(state *s)
{
    s->matched = 1;
}

/* The compiled pattern's entry point: the end of the first match anywhere in `s`,
 * or NULL.  Thread lists live in this frame, so concurrent and recursive
 * searches are fine. */
const char *search(const char *s)
{
    uint64_t n = HOLE(NID) + 1;
    uint64_t *seen = __builtin_alloca(n * sizeof *seen);
    node_fn **clist = __builtin_alloca(n * sizeof *clist);
    node_fn **nlist = __builtin_alloca(n * sizeof *nlist);
    state st = {.seen = seen};
    uint32_t nclist = 0;

    /* volatile keeps the loop from becoming a call to memset, which is not a hole */
    for (uint64_t i = 0; i < n; i++)
        ((volatile uint64_t *)seen)[i] = 0;
    for (;; s++) {
        st.gen++;
        st.ch = (uint8_t)*s;
        st.next = nlist;
        st.n = 0;
        START(&st); /* a fresh thread at every position: unanchored */
        for (uint32_t i = 0; i < nclist; i++)
            clist[i](&st);
        if (st.matched || !*s)
            break;
        node_fn **tmp = clist;
        clist = nlist;
        nlist = tmp;
        nclist = st.n;
    }
    return st.matched ? s : 0;
}
