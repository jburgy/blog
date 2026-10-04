#!/usr/bin/env -S uv run --script
#
# -*- coding: utf8 -*-
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

"""Compiling forth to python bytecode for fun micro-optimizations

Python performs only the most minimal optimizations before generating
bytecode.  As a consequence, there are many opportunities to speed up
simple functions by skipping unnecessary instructions.  What is the
easiest way to generate those optimized instruction lists?  There are
a few ways:
    1. ast to bytecode optimizing compiler
    2. unoptimized bytecode to optimized bytecode converter
    3. let a human do it
The first two approaches are extremely complex as illustrated by the
vast body of research on the topic.  Forth is basically a condensed
textual representation of a stack machine.  This makes it perfectly
suited to the task at hand.

https://legacy.python.org/workshops/1998-11/proceedings/papers/montanaro/montanaro.html
https://users.ece.cmu.edu/~koopman/stack_compiler/stack_co.pdf
https://www.complang.tuwien.ac.at/forth/gforth/Docs-html/index.html
http://git.annexia.org/?p=jonesforth.git;a=blob;f=jonesforth.S
https://towardsdatascience.com/understanding-python-bytecode-e7edaae8734d
http://cubbi.com/fibonacci/forth.html

Since Python 3.11 the "specializing adaptive interpreter" (PEP 659) rewrote
the wordcode format this module used to emit by hand: every function now
starts with a RESUME instruction, conditional jumps are relative instead of
absolute (and forward-only), ROT_TWO/THREE/FOUR and DUP_TOP/DUP_TOP_TWO were
replaced by argument-taking SWAP(n)/COPY(n), arithmetic ops were folded into
one BINARY_OP keyed by an operand, and many opcodes are trailed by inline
CACHE slots the interpreter later overwrites with per-callsite specialization
state -- get the padding wrong and the bytecode looks fine until the
specializer kicks in a few thousand calls into a `timeit` run and corrupts
adjacent instructions. None of this is documented as a stable ABI (CPython
promises it will keep changing), so rather than hardcoding opcode numbers or
argument encodings, everything below is derived from the running
interpreter's own metadata (`opcode.opmap`, `opcode._inline_cache_entries`,
`dis._nb_ops`) or, where no public table exists (COMPARE_OP's oparg bit
layout), by compiling a throwaway snippet and reading off what the real
compiler just did -- a tiny "copy-and-patch": let CPython tell us its own
current answer instead of guessing it.
https://docs.python.org/3/whatsnew/3.11.html#whatsnew311-pep659
https://docs.python.org/3/library/dis.html#opcode-SWAP

>>> fib(10)
89

`fib`'s forth docstring (below) is known to compute fib(n - 1), not fib(n),
for n >= 2 -- a pre-existing bug in its hand-written stack shuffling, left
alone since this module isn't meant to be feature complete. Unlike
`fast_fib` below, its compiled form is deliberately not asserted to match.

>>> fast_fib(10)
55
>>> ForthCompiler().compile(fast_fib)(10)
55
"""

import sys
from argparse import ArgumentParser
from ast import literal_eval
from dis import (
    COMPILER_FLAG_NAMES,
    _nb_ops,  # ty: ignore[unresolved-import]  # pyright: ignore[reportAttributeAccessIssue]
    dis,
    get_instructions,
    show_code,
    stack_effect,
)
from opcode import (
    _inline_cache_entries as CACHE_ENTRIES,  # ty: ignore[unresolved-import]  # pyright: ignore[reportAttributeAccessIssue]
    cmp_op,
    opmap,
    opname,
)
from timeit import timeit
from types import CodeType, FunctionType

print(sys.version_info)

COMPILER_FLAGS = {v: k for k, v in COMPILER_FLAG_NAMES.items()}

# BINARY_OP's oparg is just _nb_ops's index; documented, not guessed.
NB = {symbol: index for index, (_, symbol) in enumerate(_nb_ops)}


def _compare_oparg(symbol):
    """COMPARE_OP's oparg packs a specializer bitmask nobody documents the
    layout of; ask the real compiler for today's answer instead of guessing."""
    ns = {}
    exec(f"def f(a, b): return a {symbol} b", ns)
    arg = next(i.arg for i in get_instructions(ns["f"]) if i.opname == "COMPARE_OP")
    assert arg is not None
    return arg


CMP = {symbol: _compare_oparg(symbol) for symbol in cmp_op}


def _encode(name, arg=0):
    """One real instruction plus the inline CACHE padding it now requires."""
    return bytes((opmap[name], arg)) + bytes(2 * CACHE_ENTRIES.get(name, 0))


def _jump_delta(pos, name, target):
    # jump opargs count 2-byte code units from just past this instruction's
    # own CACHE entries (forward or backward; both directions are >= 0).
    end = pos + 2 + 2 * CACHE_ENTRIES.get(name, 0)
    delta = abs(target - end) // 2
    assert delta < 256, "ponytail: jumps >510 bytes need EXTENDED_ARG; unsupported here"
    return delta


def _gen_emitter(*ops):
    chunk = b"".join(_encode(name, arg) for name, arg in ops)

    def emitter(self, word):
        return chunk

    return emitter


class ForthCompilerMeta(type):
    def __new__(meta, name, bases, dct):  # pyright: ignore[reportSelfClsParameterName]
        ops = {
            "+": [("BINARY_OP", NB["+="])],
            "-": [("BINARY_OP", NB["-="])],
            "*": [("BINARY_OP", NB["*="])],
            "/": [("BINARY_OP", NB["//="])],
            "2*": [("COPY", 1), ("BINARY_OP", NB["+="])],
            "2/": [("LOAD_CONST", 0), ("BINARY_OP", NB[">>="])],
            "and": [("BINARY_OP", NB["&="])],
            # https://complang.tuwien.ac.at/forth/gforth/Docs-html/Data-stack.html
            # ROT_TWO/THREE/FOUR and DUP_TOP(_TWO) are gone since 3.11; SWAP(n)
            # exchanges TOS with the item n deep, COPY(n) pushes a copy of it.
            "drop": [("POP_TOP", 0)],  # w --
            "nip": [("SWAP", 2), ("POP_TOP", 0)],  # w1 w2 -- w2
            "dup": [("COPY", 1)],  # w - w w
            "over": [("COPY", 2)],  # w1 w2 -- w1 w2 w1
            "tuck": [("COPY", 1), ("SWAP", 3), ("SWAP", 2)],  # w1 w2 -- w2 w1 w2
            "swap": [("SWAP", 2)],  # w1 w2 -- w2 w1
            "rot": [("SWAP", 3), ("SWAP", 2)] * 2,  # w1 w2 w3 -- w2 w3 w1
            "-rot": [("SWAP", 3), ("SWAP", 2)],  # w1 w2 w3 -- w3 w1 w2
            "2drop": [("POP_TOP", 0)] * 2,  # w1 w2 --
            "2nip": [("SWAP", 4), ("SWAP", 3), ("SWAP", 2)] * 2
            + [("POP_TOP", 0)] * 2,  # w1 w2 w3 w4 - w3 w4
            "2dup": [("COPY", 2)] * 2,  # w1 w2 -- w1 w2 w1 w2
            "2swap": [("SWAP", 4), ("SWAP", 3), ("SWAP", 2)]
            * 2,  # w1 w2 w3 w4 -- w3 w4 w1 w2
            ";": [("RETURN_VALUE", 0)],
        }
        emitters = {"emit_" + word: _gen_emitter(*seq) for word, seq in ops.items()}

        def compare(self, word):
            return _encode("COMPARE_OP", CMP[word])

        comparers = {"emit_" + op: compare for op in cmp_op}

        def emit_equal(self, word):
            return _encode("COMPARE_OP", CMP["=="])

        def open_curly(self, word):
            self.emit_default = self.emit_declare
            return b""

        def close_curly(self, word):
            self.emit_default = self.emit_literal
            return b""

        def emit_colon(self, word):
            self.emit_default = self.emit_define
            return b""

        special = {
            "emit_=": emit_equal,
            "emit_{": open_curly,
            "emit_}": close_curly,
            "emit_:": emit_colon,
        }
        return type(name, bases, {**dct, **emitters, **comparers, **special})


class ForthCompiler(metaclass=ForthCompilerMeta):
    """Forth to Python bytecode compiler

    Instances implement a state machine by mutating self.emit_default and
    self.fastop.
    """

    def __init__(self):
        self.code = bytearray()
        self.blocks = []
        self.consts = {}
        self.varnames = {}
        self.func_name = None
        self.fastop = "LOAD_FAST"

    def patch_jump(self, pos, target):
        self.code[pos + 1] = _jump_delta(pos, opname[self.code[pos]], target)

    def emit_if(self, word):
        test = _encode("TO_BOOL")
        self.blocks.append(len(self.code) + len(test))  # position of the jump below
        return test + _encode("POP_JUMP_IF_FALSE", 0)

    def emit_else(self, word):
        jump = _encode("JUMP_FORWARD", 0)
        self.patch_jump(self.blocks[-1], len(self.code) + len(jump))
        self.blocks[-1] = len(self.code)
        return jump

    def emit_then(self, word):
        self.patch_jump(self.blocks.pop(), len(self.code))
        return b""

    def emit_begin(self, word):
        self.blocks.append((len(self.code), []))  # (loop top, pending `while` exits)
        return b""

    def emit_while(self, word):
        _, exits = self.blocks[-1]
        test = _encode("TO_BOOL")
        exits.append(len(self.code) + len(test))  # position of the jump below
        return test + _encode("POP_JUMP_IF_FALSE", 0)

    def emit_repeat(self, word):
        top, exits = self.blocks.pop()
        pos = len(self.code)
        jump = _encode("JUMP_BACKWARD", _jump_delta(pos, "JUMP_BACKWARD", top))
        for exit_pos in exits:
            self.patch_jump(exit_pos, pos + len(jump))
        return jump

    def emit_variable(self, word):
        name, self.fastop = self.fastop, "LOAD_FAST"  # `to` assigns once
        return _encode(name, self.varnames[word])

    def emit_declare(self, word):
        varnames = self.varnames
        varnames[word] = len(varnames)
        setattr(self, "emit_" + word, self.emit_variable)
        return b""

    def emit_literal(self, word):
        consts = self.consts
        return _encode("LOAD_CONST", consts.setdefault(literal_eval(word), len(consts)))

    emit_default = emit_literal

    def emit_to(self, word):
        self.fastop = "STORE_FAST"
        return b""

    def emit_define(self, word):
        self.func_name = word
        self.emit_default = self.emit_literal  # ty: ignore[invalid-assignment]
        return b""

    def _stacksize(self):
        # A single linear sum over the bytes is *not* enough: `if ... else
        # ... then` lays both arms out one after another, so summing every
        # instruction in program order double counts whichever arm doesn't
        # run (harmless when both arms net to zero, silently undersized
        # when they don't -- an unsafe co_stacksize can let the interpreter
        # write past the allocated value stack). Instead walk the control-
        # flow graph explicitly: track the depth at every instruction that
        # is actually reachable, and assert every merge point agrees, the
        # same invariant CPython's own compiler enforces on its basic
        # blocks. This assumes the only branches this compiler ever emits
        # are POP_JUMP_IF_FALSE (conditional), JUMP_FORWARD/JUMP_BACKWARD
        # (unconditional), and RETURN_VALUE (terminal) -- true today, but a
        # future control word using a different branch opcode needs a
        # matching case below.
        code = self.code
        depth_at = {}
        todo = [(0, 0)]
        peak = 0
        while todo:
            pos, depth = todo.pop()
            if pos in depth_at:
                assert depth_at[pos] == depth, "stack depth mismatch at a jump target"
                continue
            depth_at[pos] = depth
            peak = max(peak, depth)
            op, arg = code[pos], code[pos + 1]
            name = opname[op]
            end = pos + 2 + 2 * CACHE_ENTRIES.get(name, 0)
            if name == "RETURN_VALUE":
                continue  # terminal: no fall-through, no jump target
            if name in ("JUMP_FORWARD", "JUMP_BACKWARD"):
                target = end + 2 * arg if name == "JUMP_FORWARD" else end - 2 * arg
                todo.append((target, depth + stack_effect(op, arg, jump=True)))
                continue  # unconditional: no fall-through
            if name == "POP_JUMP_IF_FALSE":
                todo.append((end + 2 * arg, depth + stack_effect(op, arg, jump=True)))
            todo.append((end, depth + stack_effect(op, arg, jump=False)))
        return peak

    def compile(self, func):
        code = self.code
        code.extend(_encode("RESUME", 0))
        for line in func.__doc__.splitlines():
            for word in line.split():
                code.extend(
                    getattr(self, "emit_" + word, self.emit_default)(word)  # pyright: ignore[reportCallIssue]
                )

        name = self.func_name or func.__code__.co_name
        result = CodeType(  # pyright: ignore[reportCallIssue]
            func.__code__.co_argcount,
            0,  # posonlyargcount
            0,  # kwonlyargcount
            len(self.varnames),
            self._stacksize(),
            (
                COMPILER_FLAGS["OPTIMIZED"]
                | COMPILER_FLAGS["NEWLOCALS"]
                | COMPILER_FLAGS["NOFREE"]
            ),
            bytes(code),
            tuple(self.consts),  # insertion order
            tuple(),
            tuple(self.varnames),
            func.__code__.co_filename,
            name,
            name,  # qualname; ponytail: no nested defs, same as co_name
            func.__code__.co_firstlineno,
            b"",  # linetable; ponytail: no per-instruction line info (see
            # CPython's Objects/locations.md for the real encoding)
            b"",  # exceptiontable: forth words never raise/except
        )
        return FunctionType(result, func.__globals__)


def fib(n):
    """: fib { n }
    n 1 0
    begin rot dup
    while 1 - -rot tuck +
    repeat
    drop nip ;
    """
    a = 1
    b = 0
    while n:
        n -= 1
        a, b = a + b, a
    return a


def fast_fib(n):
    """: fast_fib { n m }
    n 1 begin 2dup >= while 2* repeat to m
    1 0 begin m 2/ dup to m
    while  swap 2dup * 2*
           swap dup *
           rot dup * dup
           rot + -rot +
           n m and
           if tuck + then
    repeat nip ;
    """
    # ( Slower version without local variables )
    # 1 begin 2dup >= while 2* repeat
    # 1 0 begin rot 2/ dup
    # while  -rot swap 2dup * 2*
    #        swap dup *
    #        rot dup * dup
    #        rot + -rot +
    #        2swap 2dup and
    #        if 2swap tuck + else 2swap then
    # repeat 2nip drop
    m = 1 << (n.bit_length() - 1)
    Fn = 0
    Fnm1 = 1
    while m:
        Fn2 = Fn * Fn
        Fn = 2 * Fnm1 * Fn + Fn2
        Fnm1 = Fnm1 * Fnm1 + Fn2
        if n & m:
            Fnm1, Fn = Fn, Fnm1 + Fn
        m >>= 1
    return Fn


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("n", type=int, help="which Fibonacci number")
    parser.add_argument(
        "--fast", dest="func", action="store_const", const=fast_fib, default=fib
    )
    args = parser.parse_args()

    python = args.func
    forth = ForthCompiler().compile(python)
    show_code(forth)
    dis(forth)

    p = timeit("f(n)", globals=dict(n=args.n, f=python))
    f = timeit("f(n)", globals=dict(n=args.n, f=forth))

    print("python =", p, "forth =", f, "forth/python =", f / p)
