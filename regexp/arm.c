/*
 * ARM64 implementation of Thompson's
 * on-the-fly regular expression compiler.
 *
 * See also Thompson, Ken.  Regular Expression Search Algorithm,
 * Communications of the ACM 11(6) (June 1968), pp. 419-422.
 *
 * Copyright (c) 2004 Jan Burgy.
 * Can be distributed under the MIT license, see bottom of file.
 */

#define _DEFAULT_SOURCE
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

enum {
    LPAREN = SCHAR_MAX + 1, /* char is unsigned on Linux/ARM */
    RPAREN, /* This should  */
    ALTERN, /* reflect the  */
    CONCAT, /* precedence   */
    KLEENE  /* rules!       */
};

static unsigned char *prepare(const char *src)
{
    unsigned char escape[UCHAR_MAX + 1] = "";
    unsigned char *dest = malloc(2 * (strlen(src) + 1));
    int c, i, j = 0, concat = 0, nparen = 0;

    escape['a'] = '\a';
    escape['b'] = '\b';
    escape['f'] = '\f';
    escape['n'] = '\n';
    escape['r'] = '\r';
    escape['t'] = '\t';
    escape['v'] = '\v';
    for (i = 0; (c = "\"()*\\|"[i]); i++)
        escape[c] = c;

    for (i = 0; (c = src[i]); i++) {

        switch (c) {

            case '(':
                if (concat)
                    dest[j++] = CONCAT;
                dest[j++] = LPAREN;
                concat = 0;
                nparen++;
                continue;
            case ')':
                dest[j++] = RPAREN;
                nparen--;
                break;
            case '*':
                dest[j++] = KLEENE;
                break;
            case '|':
                dest[j++] = ALTERN;
                concat = 0;
                continue;
            case '\\':
                c = escape[(unsigned char)src[i + 1]];
                c ? i++ : (c = '\\');
                __attribute__((fallthrough));
            default:
                if (concat)
                    dest[j++] = CONCAT;
                dest[j++] = c;
        }
        concat = 1;
        if (nparen < 0)
            printf("unbalanced parentheses\n");
    }
    dest[j++] = RPAREN;
    dest[j++] = '\0';

    return dest;
}

static unsigned char *convert(const char *src)
{ /* http://cs.lasierra.edu/~ehwang/cptg454/postfix.pdf */
    unsigned char stack[BUFSIZ] = "";
    unsigned char *dest = prepare(src);
    int c, i, j = 0, top = 0;

    stack[top++] = LPAREN;
    for (i = 0; (c = dest[i]); i++) {

        switch (c) {

            case LPAREN:
                stack[top++] = c;
                break;

            case RPAREN:
            case ALTERN:
            case CONCAT:
            case KLEENE:
                while (c <= stack[top - 1])
                    dest[j++] = stack[--top];
                if (c == RPAREN)
                    --top; /* discard LPAREN */
                else
                    stack[top++] = c;
                break;

            default:
                dest[j++] = c;
                break;
        }
    }
    dest[j++] = '\0';

    return dest;
}

/*
 * Register usage mirrors x86.c:  x1 = %esi, w2 = %al, x3 = %ecx and
 * x4 points to the next list.  The machine stack holds the current list
 * in 16-byte slots because sp must stay 16-byte aligned.
 */
static const uint32_t header[] = {
    /* clang-format off */
    0xA9BF7BFD, /*         stp    x29, x30, [sp, #-16]! */
    0x910003FD, /*         mov    x29, sp               */
    0xD10C83FF, /*         sub    sp, sp, #800          */
    0xAA0003E1, /*         mov    x1, x0                */
    0x52800022, /*         mov    w2, #1                */
    0xD2800003, /*         mov    x3, #0                */
    0xD10C83A4, /*         sub    x4, x29, #800         */
    0x10000030, /*         adr    x16, _next            */
                /* _next:                               */
    0xF81F0FF0, /*         str    x16, [sp, #-16]!      */
    0x350000A2, /*         cbnz   w2, _L1               */
    0xD2800000, /*         mov    x0, #0                */
    0x910003BF, /*         mov    sp, x29               */
    0xA8C17BFD, /*         ldp    x29, x30, [sp], #16   */
    0xD65F03C0, /*         ret                          */
                /* _L1:                                 */
    0xB40000A3, /*         cbz    x3, _L2               */
    0xD1000463, /*         sub    x3, x3, #1            */
    0xF8637890, /*         ldr    x16, [x4, x3, lsl #3] */
    0xF81F0FF0, /*         str    x16, [sp, #-16]!      */
    0x17FFFFFC, /*         b      _L1                   */
                /* _L2:                                 */
    0x38401422, /*         ldrb   w2, [x1], #1          */
    0x14000006, /*         b      _code                 */
                /* _fail:                               */
    0xF84107F0, /*         ldr    x16, [sp], #16        */
    0xD61F0200, /*         br     x16                   */
                /* _nnode:                              */
    0xF823789E, /*         str    x30, [x4, x3, lsl #3] */
    0x91000463, /*         add    x3, x3, #1            */
    0x17FFFFFC, /*         b      _fail                 */
    /* clang-format on */
};

static const uint32_t footer[] = {
    /* clang-format off */
    0xD1000420, /*         sub    x0, x1, #1            */
    0x910003BF, /*         mov    sp, x29               */
    0xA8C17BFD, /*         ldp    x29, x30, [sp], #16   */
    0xD65F03C0, /*         ret                          */
    /* clang-format on */
};

typedef char *(*function_t)(char *);

static int codelen(const unsigned char *src)
{
    int i, c, n = 0;

    for (i = 0; (c = src[i]); i++) {
        switch (c) {
            default:
                n += 4;
                break;
            case CONCAT:
                break;
            case KLEENE:
                n += 8;
                break;
            case ALTERN:
                n += 5;
                break;
        }
    }
    return n;
}

enum {
    FAIL = 21,
    NNODE = 23
};

static const uint32_t B = 0x14000000, BL = 0x94000000, BNE = 0x54000001,
                      CMP = 0x7100005F,  /* cmp w2, #0           */
                      ADR = 0x10000010,  /* adr x16, #0          */
                      PUSH = 0xF81F0FF0; /* str x16, [sp, #-16]! */

static uint32_t branch(uint32_t op, long from, long to)
{
    return op | ((uint32_t)(to - from) & 0x3FFFFFF);
}

static uint32_t bne(long from, long to)
{
    return BNE | ((uint32_t)(to - from) & 0x7FFFF) << 5;
}

static uint32_t adr(long from, long to)
{
    uint32_t delta = (uint32_t)(4 * (to - from));

    return ADR | (delta & 3) << 29 | (delta >> 2 & 0x7FFFF) << 5;
}

static long target(const uint32_t *code, long at)
{
    return at + ((int32_t)(code[at] << 6) >> 6);
}

static size_t mapsize(size_t length)
{
    size_t pagesize = (size_t)sysconf(_SC_PAGESIZE);

    return (length + pagesize - 1) & ~(pagesize - 1);
}

uint32_t *compile(const unsigned char *src)
{
    int i, c, top = 0;
    long pc = sizeof header / sizeof *header, stack[BUFSIZ], s1, s2;
    long lambda[BUFSIZ]; /* Thompson's lambda: the `b' taken on an empty match, or 0 */
    size_t length = sizeof header + 4 * codelen(src) + sizeof footer;
    size_t size = mapsize(16 + length);
    unsigned char *base = mmap(NULL, size, PROT_READ | PROT_WRITE,
                               MAP_PRIVATE | MAP_ANON, -1, 0);
    uint32_t *code = (uint32_t *)(base + 16);

    if (base == MAP_FAILED)
        return NULL;
    memcpy(base, &size, sizeof size);
    memmove(code, header, sizeof header);
    /* clang-format off */
    for (i = 0; (c = src[i]); i++) {

        switch (c) {

            default:
                lambda[top] = 0;
                stack[top++] = pc;
                code[pc + 0] = branch(B, pc, pc + 1);
                code[pc + 1] = CMP | (uint32_t)c << 10;
                code[pc + 2] = bne(pc + 2, FAIL);
                code[pc + 3] = branch(BL, pc + 3, NNODE);
                pc += 4;
                break;

            case CONCAT:
                if (!lambda[top - 1])
                    lambda[top - 2] = 0;
                --top;
                break;

            case KLEENE:
                s1 = stack[top - 1];
                code[pc + 0] = adr(pc, pc + 3);
                code[pc + 1] = PUSH;
                code[pc + 2] = branch(B, pc + 2, target(code, s1));
                code[pc + 3] = branch(B, pc + 3, pc + 8);
                code[pc + 4] = adr(pc + 4, pc + 7);
                code[pc + 5] = PUSH;
                code[pc + 6] = branch(B, pc + 6, target(code, s1));
                code[pc + 7] = branch(B, pc + 7, pc + 8);
                code[s1] = branch(B, s1, pc + 4);
                if (lambda[top - 1])
                    code[lambda[top - 1]] = branch(B, lambda[top - 1], FAIL);
                lambda[top - 1] = pc + 7;
                pc += 8;
                break;

            case ALTERN:
                s1 = stack[top - 2];
                s2 = stack[top - 1];
                code[pc + 0] = branch(B, pc, pc + 5);
                code[pc + 1] = adr(pc + 1, pc + 4);
                code[pc + 2] = PUSH;
                code[pc + 3] = branch(B, pc + 3, target(code, s2));
                code[pc + 4] = branch(B, pc + 4, target(code, s1));
                code[s1] = branch(B, s1, pc + 1);
                code[s2] = branch(B, s2, pc + 5);
                if (!lambda[top - 2])
                    lambda[top - 2] = lambda[top - 1];
                else if (lambda[top - 1])
                    code[lambda[top - 1]] = branch(B, lambda[top - 1], lambda[top - 2]);
                pc += 5;
                --top;
                break;

        }

        /* clang-format on */
    }
    memmove(code + pc, footer, sizeof footer);

    __builtin___clear_cache((char *)code, (char *)code + length);
    if (mprotect(base, size, PROT_READ | PROT_EXEC)) {
        munmap(base, size);
        return NULL;
    }
    return code;
}

function_t study(const char *re)
{
    unsigned char *p = convert(re);
    uint32_t *q = compile(p);

    if (p)
        free(p), p = NULL;
    return (function_t)q;
}

void forget(function_t search)
{
    unsigned char *base = (unsigned char *)search - 16;
    size_t size;

    memcpy(&size, base, sizeof size);
    munmap(base, size);
}

int main(void)
{
    short i;
    struct {
        char *r;
        char *s;
    } test[] = {
        {"abcdefg", "abcdefg"},
        {"(a|b)*a", "ababababab"},
        {"(a|b)*a", "aaaaaaaaba"},
        {"(a|b)*a", "aaaaaabac"},
        {"a(b|c)*d", "abccbcccd"},
        {"a(b|c)*d", "abccbcccde"},
        {"(a|a)*", "aaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
        {"a(b|c)*d", "abccccccccd"},
        {"a*", "aaab"},
        {"a(b|c)*d", "abcd"},
        {"a**", "b"},
        {"(a*b*)*c", "abbac"},
        {"(a*|b*)*c", "abac"},
        {"b*(c|d)", "c"},
        {NULL, NULL}};

    for (i = 0; test[i].r; i++) {
        function_t search = study(test[i].r);
        char *t;

        printf("search(%p) %s %s\n", (void *)search, test[i].r, test[i].s);
        t = search(test[i].s);
        if (t)
            printf("match found after %td bytes\n", t - test[i].s);
        else
            printf("match not found\n");
        forget(search);
    }

    return 0;
}

/*
 * Permission is hereby granted, free of charge, to any person
 * obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the
 * Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute,
 * sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so,
 * subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall
 * be included in all copies or substantial portions of the
 * Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
 * KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
 * WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
 * PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE AUTHORS
 * OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
 * OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
 * OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */
