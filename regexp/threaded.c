/*
 * Threaded-code implementation of Thompson's on-the-fly regular
 * expression compiler, using GCC's labels as values (as in
 * ../forth/4th.c) instead of emitting machine code.
 *
 * See also Thompson, Ken.  Regular Expression Search Algorithm,
 * Communications of the ACM 11(6) (June 1968), pp. 419-422.
 *
 * Copyright (c) 2004 Jan Burgy.
 * Can be distributed under the MIT license, see bottom of file.
 */

#include <stdio.h>
#include <limits.h>
#include <string.h>
#include <stdlib.h>

enum	{
	LPAREN = CHAR_MAX + 1,
	RPAREN,		/* This should	*/
	ALTERN,		/* reflect the	*/
	CONCAT,		/* precedence	*/
	KLEENE		/* rules!	*/
};

static
unsigned char *prepare(const char *src)
{
	unsigned char	escape[CHAR_MAX + 1] = "";
	unsigned char	*dest = malloc(2 * (strlen(src) + 1));
	int	c, i, j = 0, concat = 0, nparen = 0;

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

	return	dest;
}

static
unsigned char *convert(const char *src)
{	/* http://cs.lasierra.edu/~ehwang/cptg454/postfix.pdf */
	unsigned char	stack[BUFSIZ] = "";
	unsigned char	*dest = prepare(src);
	int	c, i, j = 0, top = 0;

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
					--top;	/* discard LPAREN */
				else
					stack[top++] = c;
				break;

			default:
				dest[j++] = c;
				break;

		}

	}
	dest[j++] = '\0';

	return	dest;
}

/*
 * A compiled program is an array of cells.  A cell is either an
 * opcode -- the address of a label inside search() -- or that
 * opcode's operand: a literal character, or a link to another cell.
 * The x86 version encodes the same thing as a two byte `jmp' whose
 * displacement has to be added to the address of the displacement
 * byte itself; here a link is simply a pointer.
 */
typedef	union	cell	{
	void		*label;
	union	cell	*link;
	int		 chr;
} cell_t;

enum	{ JUMP, CHAR, FORK, STOP };

/*
 * Node layouts, mirroring the 11/5/9 byte x86 encodings.  The leading
 * JUMP of a node doubles as the successor link of the node before it,
 * which is what makes concatenation free.
 *
 *	char	JUMP <body>  CHAR <c>		entry = body, exit = the cell after
 *	*	FORK <body>			entry = the FORK, exit = the cell after
 *	|	JUMP <exit>  FORK <b>  JUMP <a>	entry = the FORK, exit = the cell after
 */
static
int codelen(const unsigned char *src)
{
	int	i, c, n = 1;	/* one cell for the trailing STOP */

	for (i = 0; (c = src[i]); i++) {
		switch (c) {
			default:	n += 4;	break;
			case CONCAT:		break;
			case KLEENE:	n += 2;	break;
			case ALTERN:	n += 6;	break;
		}
	}
	return	n;
}

static
cell_t *compile(const unsigned char *src, void *const *op)
{
	int	i, c, top = 0;
	cell_t	*stack[BUFSIZ], *code, *pc;

	code = pc = malloc(codelen(src) * sizeof *code);

	for (i = 0; (c = src[i]); i++) {

		switch (c) {

			default:
				stack[top++] = pc + 1;
				pc[0].label = op[JUMP];	pc[1].link = pc + 2;
				pc[2].label = op[CHAR];	pc[3].chr  = c;
				pc += 4;
				break;

			case CONCAT:
				--top;
				break;

			case KLEENE:
				pc[0].label = op[FORK];	pc[1].link = stack[top - 1]->link;
				stack[top - 1]->link = pc;
				pc += 2;
				break;

			case ALTERN:
				pc[0].label = op[JUMP];	pc[1].link = pc + 6;
				pc[2].label = op[FORK];	pc[3].link = stack[top - 1]->link;
				pc[4].label = op[JUMP];	pc[5].link = stack[top - 2]->link;
				stack[top - 1]->link = pc + 6;
				stack[top - 2]->link = pc + 2;
				pc += 6;
				--top;
				break;

		}

	}
	pc->label = op[STOP];

	return	code;
}

#define	NEXT	goto *(pc++)->label

char *search(const char *re, char *s)
{
	void	*op[] = { &&JUMP, &&CHAR, &&FORK, &&STOP };
	unsigned char	*p = convert(re);
	cell_t	*code = compile(p, op), *pc;
	cell_t	*clist[BUFSIZ], *nlist[BUFSIZ];
	char	*found = NULL;
	int	cnode = 0, nnode = 0, c = EOF;	/* any non-NUL c primes the first exchange */

	free(p);

XCHG:	/* CLIST is exhausted: swap the lists and take one more character */
	if (!c)
		goto done;
	while (nnode)
		clist[cnode++] = nlist[--nnode];
	c = (unsigned char)*s++;
	pc = code;	/* unanchored, so start a fresh thread at every position */
	NEXT;

JUMP:	pc = pc->link;
	NEXT;

CHAR:	if ((pc++)->chr == c)
		nlist[nnode++] = pc;	/* pc is the successor link, i.e. the continuation */

	/* this thread is done for this character: run the next one on CLIST */
	if (!cnode)	/* Thompson plants a TRA XCHG at the bottom of CLIST */
		goto XCHG;
	pc = clist[--cnode];
	NEXT;

FORK:	clist[cnode++] = pc + 1;	/* run the fall-through later, the branch now */
	pc = pc->link;
	NEXT;

STOP:	found = s - 1;

done:	free(code);
	return	found;
}

int main(void)
{
	short	i;
	struct	{
		char	*r;
		char	*s;
	} test[] = {
		{ "abcdefg",	"abcdefg"	},
		{ "(a|b)*a",	"ababababab"	},
		{ "(a|b)*a",	"aaaaaaaaba"	},
		{ "(a|b)*a",	"aaaaaabac"	},
		{ "a(b|c)*d",	"abccbcccd"	},
		{ "a(b|c)*d",	"abccbcccde"	},
		{ "(a|a)*",	"aaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
		{ "a(b|c)*d",	"abccccccccd"	},
		{ "a*",		"aaab"		},
		{ "a(b|c)*d",	"abcd"		},
		{ NULL,		NULL		}
	};

	for (i = 0; test[i].r; i++) {
		char	*t;

		printf("search %s %s\n", test[i].r, test[i].s);
		t = search(test[i].r, test[i].s);
		if (t)	printf("match found after %td bytes\n", t - test[i].s);
		else	printf("match not found\n");
	}

	return	0;
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
