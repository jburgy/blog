# -*-coding:utf8;-*-
""" `Regular Expression Search Algorithm`_

After playing with `Thompson's construction`_ in `C`_ and `x86`_, I decided to take
another look in python many years later.  Tokenization and conversion to postfix are
lifted almost verbatim from the C implementation apart for the fact they rely on
python generators which are a very natural way to express single pass algorithms.

My original intent was to generate python bytecode.  Unfortunately, Ken's original
paper relies on an `indirect branch`_ which python bytecode doesn't have.  So I created
two implementations instead.  The first one compiles the regular expression to an
implicit virtual machine.  The virtual machine only understands 3 instructions which are
encoded by type since python lists are heterogeneous.

str
    is an immediate matching instruction.  The next character in the stream is compared
    to the value of the instruction

tuple of ints
    represent ε transitions.  Ints correspond to offsets in the instruction list which
    are added to the current search space.  An offset past the end of the instruction
    list means the search completed successfully

This implementation is very clever.  The compiler maintains a stack of dangling offsets
and only mutates at most the last two.  On the flip side, it's not exactly intuitive
unless you're a compiler expert.

The second implementation compiles the regular expression to a direct graph just like
python's standard `graphlib`_ module.  Scanning a string with this graph is more
pythonic than the first implementation by relying on :code:`__getitem__`.
`Epsilon transitions`_ are represented by :code:`""` keys in (sub-)dictionaries that
have them.  The docstring for :code:`Graph` illustrates this with examples.

Both implementations use the same 2 lists that Ken's NNODE and CNODE "functional
routines" manipulate.  :code:`Instructions.__call__` and :code:`Graph.__call__` call
them simply :code:`c` for current and :code:`n` for next.  :code:`c` will be on average
slightly larger in the first implementation since every :code:`|` appends to it.  The
second implementation uses dictionaries to match the current character against all
possible branches at once. That difference is best understood by looking at how each
implementation compiles :code:`"a|b|c"`

.. _Regular Expression Search Algorithm: http://www.oilshell.org/archive/Thompson-1968.pdf  # noqa E501
.. _Thompson's construction: https://en.wikipedia.org/wiki/Thompson%27s_construction
.. _C: https://swtch.com/~rsc/regexp/regexp-bytecode.c.txt
.. _x86: https://swtch.com/~rsc/regexp/regexp-x86.c.txt
.. _indirect branch: https://en.wikipedia.org/wiki/Indirect_branch
.. _graphlib: https://docs.python.org/3/library/graphlib.html
.. _Epsilon transitions: https://en.wikipedia.org/wiki/Epsilon_transition
"""
from enum import IntEnum
from typing import Iterable, Union

Token = IntEnum("Token", "LPAREN RPAREN ALTERN CONCAT KLEENE")
TokenOrChar = Union[str, Token]
TokenOrCharOrNone = Union[None, str, Token]

recognize = {
    "(": Token.LPAREN,
    ")": Token.RPAREN,
    "*": Token.KLEENE,
    "|": Token.ALTERN,
}.get

parens = {
    Token.LPAREN: 1,
    Token.RPAREN: -1,
}


def tokenize(regexp: str) -> Iterable[TokenOrChar]:
    concat, escape, nparen = False, False, 0
    for char in regexp:
        token = recognize(char)
        if escape:
            if not token:
                yield "\\"
            yield char
            escape = False
        elif char == "\\":
            escape = True  # lookahead
        elif token:
            if concat and token is Token.LPAREN:
                yield Token.CONCAT
            yield token
            nparen += parens.get(token, 0)
            concat = token not in {Token.LPAREN, Token.ALTERN}
        else:
            if concat:
                yield Token.CONCAT
            yield char
            concat = True
    if nparen:
        raise ValueError("unabalanced parentheses")


def postfix(tokens: Iterable[TokenOrChar]) -> Iterable[TokenOrCharOrNone]:
    stack = [Token.LPAREN]
    for token in tokens:
        if token is Token.LPAREN:
            stack.append(token)
        elif isinstance(token, Token):
            while token < stack[-1]:
                yield stack.pop()
            if token is Token.RPAREN:
                stack.pop()
            else:
                stack.append(token)
        else:
            yield token
    yield from reversed(stack[1:])
    if Token.KLEENE in stack:
        yield None


class Instructions(list):
    """
    >>> Instructions('a')
    [(1,), 'a']
    >>> Instructions('a*')
    [(2,), 'a', (1, 3)]
    >>> Instructions('ab')
    [(1,), 'a', (3,), 'b']
    >>> Instructions('a|b')
    [(5,), 'a', (6,), 'b', (6,), (3, 1)]
    >>> Instructions('a|b|c')
    [(9,), 'a', (10,), 'b', (8,), 'c', (8,), (5, 3), (10,), (7, 1)]
    >>> Instructions('a*b')
    [(2,), 'a', (1, 3), 'b']
    >>> Instructions('a*|b')
    [(5,), 'a', (6,), 'b', (6,), (1, 3, 2)]
    >>> Instructions('a*b*')
    [(2,), 'a', (4,), 'b', (1, 3, 5)]
    >>> Instructions('a*|b')
    [(5,), 'a', (6,), 'b', (6,), (1, 3, 2)]
    >>> Instructions('a(b|c)*d')
    [(1,), 'a', (8,), 'b', (8,), 'c', (8,), (5, 3), (7, 9), 'd']
    >>> Instructions('(a|b)(c|d)')
    [(5,), 'a', (6,), 'b', (6,), (3, 1), (11,), 'c', (12,), 'd', (12,), (9, 7)]
    """

    def __init__(self, regexp: str):
        stack: list = []
        for token in postfix(tokenize(regexp)):
            pc = len(self)
            if token == Token.CONCAT:
                stack.pop()
            elif token == Token.KLEENE:
                last = stack[-1]
                self.append(self[last])
                self[last] = (pc,)
            elif token == Token.ALTERN:
                last = stack.pop()
                prev = stack[-1]
                self.append((pc + 2,))
                self.append(self[last] + self[prev])
                self[prev] = (pc + 1,)
                self[last] = (pc + 2,)
            elif token is None:
                self[-1] += (pc,)
            elif pc and isinstance(self[-1], tuple) and len(self[-1]) == 1:
                stack.append(pc - 1)
                self[-1] += (pc,)
                self.append(token)
            else:
                stack.append(pc)
                self.append((pc + 1,))
                self.append(token)

    def __call__(self, string: str) -> bool:
        c = [0]  # Let's start at the very beginning
        m = len(self)
        for char in string:
            n = []
            for p in c:
                try:
                    op = self[p]  # str to match or jump targets
                except IndexError:
                    return True
                if isinstance(op, tuple):
                    c.extend(op)
                elif char == op:
                    n.append(p + 1)
            if m in n:
                return True
            # end of current targets
            c = n
        return False


class Graph(dict):
    """
    >>> Graph('a')
    {'a': None}
    >>> Graph('a*')  # ellipsis means cycle
    {'a': {...}, '': None}
    >>> Graph('abcd')
    {'a': {'b': {'c': {'d': None}}}}
    >>> Graph('a|b|c|d')
    {'a': None, 'b': None, 'c': None, 'd': None}
    >>> Graph('ab*')
    {'a': {'b': {...}, '': None}}
    >>> Graph('a*b')
    {'a': {...}, '': {'b': None}}
    >>> Graph('a*b*')
    {'a': {...}, '': {'b': {...}, '': None}}
    >>> Graph('a(b|c)')
    {'a': {'b': None, 'c': None}}
    >>> Graph('(a|b)c')
    {'a': {'c': None}, 'b': {'c': None}}
    >>> Graph('a(b|c)*d')
    {'a': {'b': {...}, 'c': {...}, '': {'d': None}}}
    >>> Graph('(a|b)(c|d)')
    {'a': {'c': None, 'd': None}, 'b': {'c': None, 'd': None}}
    """

    @staticmethod
    def append(next, node) -> None:
        for n, p in next:
            n[p] = node

    def __new__(cls, regexp: str):
        # maintain a stack of tuples whose head represents the
        # recently compiled regular expression fragment and rest
        # are "exits"
        stack: list = []
        last: tuple = ({"": None},)  # empty regex matches everything
        for token in postfix(tokenize(regexp)):
            if token is Token.CONCAT:
                prev = stack.pop()
                cls.append(prev[1:], last[0])
                last = prev[:1] + last[1:]
            elif token is Token.KLEENE:
                rest: list
                head, *rest = last
                cls.append(rest, head)
                last = head, (head, "")
            elif token is Token.ALTERN:
                head, *rest = last
                node = (last := stack.pop())[0]
                node.update(head)
                last += tuple((node if n is head else n, p) for n, p in rest)
            elif token is not None:
                stack.append(last)
                node = super().__new__(cls)
                last = node, (node, token)
        head, *rest = last
        cls.append(rest, None)
        return head

    def __init__(self, regexp: str):
        super().__init__(self)

    def __call__(self, string: str) -> bool:
        c = [self]
        for ch in string:
            n = []
            for p in c:
                if p is None:
                    return True
                try:
                    c.append(p[""])  # ε
                except KeyError:
                    pass
                try:
                    n.append(p[ch])
                except KeyError:
                    pass
            if None in n:
                return True
            c = n
        return False


if __name__ == "__main__":
    print(Graph("a*b")("aaaaaaaaaaaaaaaaaaaaaaaaaab"))
