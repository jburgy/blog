/*
 * Bytecode machine implementation of Thompson's
 * on-the-fly regular expression compiler.
 *
 * See also Thompson, Ken.  Regular Expression Search Algorithm,
 * Communications of the ACM 11(6) (June 1968), pp. 419-422.
 *
 * Copyright (c) 2004 Jan Burgy.
 * Can be distributed under the MIT license, see bottom of file.
 */

#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum {
    STOP,
    JUMP,
    MATCH,
    BRANCH,
    LPAREN = CHAR_MAX + 1,
    RPAREN, /* This should  */
    ALTERN, /* reflect the  */
    CONCAT, /* precedence   */
    KLEENE  /* rules!       */
};

unsigned char *prepare(const char *src)
{
    unsigned char escape[CHAR_MAX + 1] = "";
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
                c = escape[(int)src[i + 1]];
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

unsigned char *convert(const char *src)
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
                while (c <= stack[top - 1])
                    dest[j++] = stack[--top];
                --top; /* discard LPAREN */
                break;

            case ALTERN:
            case CONCAT:
            case KLEENE:
                while (c <= stack[top - 1])
                    dest[j++] = stack[--top];
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

struct instr {
    short operand;
    short address;
};

struct instr assemble(short operand, short address)
{
    struct instr this = {.operand = operand, .address = address};

    return this;
}

size_t codelen(const unsigned char *src)
{
    size_t i, n = 1; /* one instruction for the trailing STOP */
    int c;

    for (i = 0; (c = src[i]); i++) {
        switch (c) {
            default:
                n += 2;
                break;
            case CONCAT:
                break;
            case KLEENE:
            case ALTERN:
                n += 4;
                break;
        }
    }
    return n;
}

/*
 * MATCH resolves its successor as code[pc + 1].address, so the slot that
 * follows a node has to hold a JUMP.  That is why KLEENE and ALTERN both
 * open with one.
 */
struct instr *compile(const unsigned char *src)
{
    int i, c, pc = 0, top = 0;
    int stack[BUFSIZ];
    struct instr *code = malloc(codelen(src) * sizeof *code);

    for (i = 0; (c = src[i]); i++) {

        switch (c) {

            default:
                stack[top++] = pc;
                code[pc + 0] = assemble(JUMP, pc + 1);
                code[pc + 1] = assemble(MATCH, c);
                pc += 2;
                break;

            case CONCAT:
                --top;
                break;

            case KLEENE:
                code[pc + 0] = assemble(JUMP, pc + 1);
                code[pc + 1] = assemble(BRANCH, '*');
                code[pc + 2] = code[stack[top - 1]];
                code[pc + 3] = assemble(JUMP, pc + 4);
                code[stack[top - 1]] = assemble(JUMP, pc + 1);
                pc += 4;
                break;

            case ALTERN:
                code[pc + 0] = assemble(JUMP, pc + 4);
                code[pc + 1] = assemble(BRANCH, '|');
                code[pc + 2] = code[stack[top - 1]];
                code[pc + 3] = code[stack[top - 2]];
                code[stack[top - 2]] = assemble(JUMP, pc + 1);
                code[stack[top - 1]] = assemble(JUMP, pc + 4);
                pc += 4;
                --top;
                break;
        }
    }

    code[pc] = assemble(STOP, pc);

    return code;
}

struct instr *study(const char *re)
{
    unsigned char *p = convert(re);
    struct instr *q = compile(p);

    if (p)
        free(p), p = NULL;
    return q;
}

void dump_code(struct instr *code)
{
    int i, op;
    char *str[] = {"STOP", "JUMP", "MATCH", "BRANCH"};

    for (i = 0; (op = code[i].operand); i++)
        printf(op == JUMP ? "%2d: %s\t%3d\n" : "%2d: %s\t'%c'\n",
               i, str[op], code[i].address);
}

/*
 * Running a state twice against the same character is redundant, and
 * suppressing it is what bounds each list by the number of states --
 * without it (a|a)* doubles its thread count on every character.
 */
void schedule(short *list, short *n, short state)
{
    short i;

    for (i = 0; i < *n; i++)
        if (list[i] == state)
            return;

    list[(*n)++] = state;
}

int execute(struct instr *code, const char *src)
{
    short i = 0, c = src[i++], pc = 0;
    short clist[BUFSIZ], cnode = 0, shift = 0;
    short nlist[BUFSIZ], nnode = 0;

    for (;;) {

        switch (code[pc].operand) {

            case STOP:
                if (!c)
                    return 1;
                break; /* a proper prefix matched: this thread dies */

            case JUMP:
                pc = code[pc].address;
                continue;

            case MATCH:
                if (c == code[pc].address)
                    schedule(nlist, &nnode, code[pc + 1].address);
                break;

            case BRANCH:
                schedule(clist, &cnode, code[pc + 1].address);
                pc = code[pc + 2].address;
                continue;
        }

        if (shift == cnode) {
            /* the terminating NUL is scanned like any other character */
            if (!c || !nnode)
                return 0;
            shift = cnode = 0;
            while (nnode > 0)
                clist[cnode++] = nlist[--nnode];
            c = src[i++];
        }
        pc = clist[shift++];
    }
}

int main(void)
{
    short i;
    struct {
        char *re;
        char *s;
    } test[] = {
        {"abcdefg", "abcdefg"},
        {"(a|b)*a", "ababababab"},
        {"(a|b)*a", "aaaaaaaaba"},
        {"(a|b)*a", "aaaaaabac"},
        {"a(b|c)*d", "abccbcccd"},
        {"a(b|c)*d", "abccbcccde"},
        {"a*", "aaa"},
        {"a*", "aaab"},
        {"ab*c", "abbbc"},
        {"ab*c", "ac"},
        {"(a|a)*", "aaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
        {NULL, NULL}};

    for (i = 0; test[i].re; i++) {

        struct instr *this = study(test[i].re);

        printf("%s %s /%s/\n",
               test[i].s,
               execute(this, test[i].s) ? "~" : "!~",
               test[i].re);

        if (this)
            free(this), this = NULL;
    }

    return EXIT_SUCCESS;
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
