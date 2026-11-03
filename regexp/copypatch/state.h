/* Run-time state shared by stencils.c (compiled for the target ISA) and
 * copypatch.c (compiled for the host).  Fixed-width fields only, so both
 * sides agree on the layout. */
#ifndef STATE_H
#define STATE_H

#include <stdint.h>

typedef struct state state;
typedef void node_fn(state *);

struct state {
    uint64_t gen;   /* current step; seen[id] == gen means "already visited" */
    uint64_t *seen; /* one slot per character/star node */
    node_fn **next; /* threads for the next character */
    uint32_t n;     /* live entries in next[] */
    uint8_t ch;     /* current input character */
    uint8_t matched;
};

#endif
