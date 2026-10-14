#!/usr/bin/env -S uv run --script
#
# -*- coding: utf8 -*-
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///

"""Assemble CPython bytecode by chaining one method per opcode.

>>> from types import FunctionType
>>> inner = (
...     CodeBuilder()
...     .load_deref("y")
...     .load_fast("z")
...     .binary_op("+=")
...     .store_deref("y")
...     .load_deref("y")
...     .load_fast("z")
...     .binary_op("+")
...     .return_value()
... )
>>> code = (
...     CodeBuilder()
...     .load_fast("x")
...     .store_deref("y")
...     .load_closure("y")
...     .build_tuple(1)
...     .load_const(inner.ascode("inner", 1))
...     .make_function()
...     .set_function_attribute(int(MakeFunctionFlags.CLOSURE))
...     .store_fast("inner")
...     .load_fast("inner")
...     .return_value()
... )
>>> def func(x):
...     y = x
...     def inner(z):
...         nonlocal y
...         y += z
...         return y + z
...     return inner
>>> built = FunctionType(code.ascode("func", 1), globals())(10)
>>> expected = func(10)
>>> [built(1), built(2)] == [expected(1), expected(2)] == [12, 15]
True
"""

import dis
import re
from dis import (
    _nb_ops,  # ty: ignore[unresolved-import]  # pyright: ignore[reportAttributeAccessIssue]
    stack_effect,
)
from enum import IntFlag
from functools import partialmethod
from itertools import accumulate
from opcode import (
    EXTENDED_ARG,
    _inline_cache_entries as CACHE_ENTRIES,  # ty: ignore[unresolved-import]  # pyright: ignore[reportAttributeAccessIssue]
    cmp_op,
    hasarg,
    hascompare,
    hasconst,
    hasfree,
    haslocal,
    hasname,
    opmap,
)
from types import CodeType

CompilerFlags = IntFlag("CompilerFlags", " ".join(dis.COMPILER_FLAG_NAMES.values()))
# SET_FUNCTION_ATTRIBUTE's oparg is a bitmask over these, in this order.
MakeFunctionFlags = IntFlag(
    "MakeFunctionFlags",
    " ".join(
        flag.upper()
        for flag in dis.FUNCTION_ATTR_FLAGS  # ty: ignore[unresolved-attribute]  # pyright: ignore[reportAttributeAccessIssue]
    ),
)

# BINARY_OP's oparg is just _nb_ops's index.
NB = {symbol: index for index, (_, symbol) in enumerate(_nb_ops)}


def _compare_oparg(symbol):
    """COMPARE_OP's oparg packs undocumented specializer bits; ask the real
    compiler for today's answer instead of guessing."""
    ns = {}
    exec(f"def f(a, b): return a {symbol} b", ns)
    return next(
        i.arg for i in dis.get_instructions(ns["f"]) if i.opname == "COMPARE_OP"
    )


CMP: dict[str, int] = {symbol: _compare_oparg(symbol) for symbol in cmp_op}


def _encode(name: str, arg: int = 0) -> bytes:
    """One real instruction, EXTENDED_ARG prefixes and inline CACHE padding."""
    prefix = b"".join(
        bytes((EXTENDED_ARG, arg >> shift & 255))
        for shift in range(8 * ((arg.bit_length() - 1) // 8), 0, -8)
    )
    return (
        prefix + bytes((opmap[name], arg & 255)) + bytes(2 * CACHE_ENTRIES.get(name, 0))
    )


class CodeBuilderBase:
    def __init__(self):
        self.consts = {None: 0}
        self.names = {}
        self.varnames = {}
        self.cellvars = {}
        self.freevars = {}
        self.fixups = []  # (position, name): fast/deref opargs known only in ascode

    def _stacksize(self, code: bytes) -> int:
        # ponytail: linear sum; exact only while the builder emits no branches
        depths = []
        ext = 0
        for pos in range(0, len(code), 2):
            op, arg = code[pos], ext << 8 | code[pos + 1]
            ext = arg if op == EXTENDED_ARG else 0
            if op != EXTENDED_ARG and op != opmap["CACHE"]:
                depths.append(
                    stack_effect(op, arg) if op in hasarg else stack_effect(op)
                )
        return max(accumulate(depths, initial=0))

    def ascode(self, func_name: str, argcount: int) -> CodeType:
        varnames, cellvars, freevars = self.varnames, self.cellvars, self.freevars
        # localsplus order: locals, cells that aren't arguments, frees
        slots = [*varnames, *(n for n in cellvars if n not in varnames), *freevars]
        body = bytearray(self)  # ty: ignore[invalid-argument-type]  # pyright: ignore[reportArgumentType]
        for pos, name in self.fixups:
            assert slots.index(name) < 256, "ponytail: >255 slots need EXTENDED_ARG"
            body[pos + 1] = slots.index(name)
        prologue = b"".join(_encode("MAKE_CELL", slots.index(n)) for n in cellvars)
        if freevars:
            prologue += _encode("COPY_FREE_VARS", len(freevars))
        code = prologue + _encode("RESUME") + body
        stacksize = self._stacksize(bytes(code))

        return CodeType(
            argcount,
            0,  # posonlyargcount
            0,  # kwonlyargcount
            len(varnames),
            stacksize,
            CompilerFlags.OPTIMIZED | CompilerFlags.NEWLOCALS,
            bytes(code),
            tuple(self.consts),  # insertion order
            tuple(self.names),
            tuple(varnames),
            "",
            func_name,
            func_name,  # qualname
            0,
            b"",  # linetable
            b"",  # exceptiontable
            tuple(freevars),
            tuple(cellvars),
        )


def _code(self, op: str, arg: int = 0):
    self.extend(_encode(op, arg))
    return self


def _binary_op(self, op: str, symbol: str):
    return _code(self, op, NB[symbol])


def _compare(self, op: str, symbol: str):
    return _code(self, op, CMP[symbol])


def _const(self, op: str, const):
    consts = self.consts
    return _code(self, op, consts.setdefault(const, len(consts)))


def _name(self, op: str, name: str):
    names = self.names
    # LOAD_GLOBAL and LOAD_ATTR keep a push-NULL/method flag in the low bit
    shift = op in ("LOAD_GLOBAL", "LOAD_ATTR")
    return _code(self, op, names.setdefault(name, len(names)) << shift)


def _slot(self, op: str, name: str):
    """Fast and deref opargs index localsplus, whose layout is only known once
    every name has been seen, so ascode patches them in."""
    if op.endswith("DEREF"):
        if name not in self.cellvars and name not in self.varnames:
            self.freevars.setdefault(name, len(self.freevars))
    else:
        self.varnames.setdefault(name, len(self.varnames))
    self.fixups.append((len(self), name))
    return _code(self, op)


def _load_closure(self, op: str, name: str):
    """Pseudo-op: names an own cell variable (not a free one) and pushes it."""
    self.freevars.pop(name, None)
    self.cellvars.setdefault(name, len(self.cellvars))
    self.fixups.append((len(self), name))
    return _code(self, "LOAD_FAST")


_FAST_PAIRS = re.compile(r"FAST.*FAST")  # superinstructions pack two opargs in one

CodeBuilder = type(
    "CodeBuilder",
    (CodeBuilderBase, bytearray),
    {
        **{
            name.lower(): partialmethod(
                _binary_op
                if name == "BINARY_OP"
                else _const
                if op in hasconst
                else _compare
                if op in hascompare
                else _slot
                if op in haslocal or op in hasfree
                else _name
                if op in hasname
                else _code,
                name,
            )
            for name, op in opmap.items()
            if op < 256 and not _FAST_PAIRS.search(name)
        },
        "load_closure": partialmethod(_load_closure, "LOAD_CLOSURE"),
    },
)

if __name__ == "__main__":
    from doctest import testmod

    testmod()
