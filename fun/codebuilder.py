import dis
from enum import IntFlag
from functools import partialmethod
from itertools import accumulate
from opcode import (
    EXTENDED_ARG,
    HAVE_ARGUMENT,
    cmp_op,
    hascompare,
    hasconst,
    hasfree,
    haslocal,
    hasname,
    opname,
)
from sys import version_info
from types import CodeType

CompilerFlags = IntFlag("CompilerFlags", " ".join(dis.COMPILER_FLAG_NAMES.values()))
MakeFunctionFlags = IntFlag(
    "MakeFunctionFlags",
    " ".join(
        flag.upper()
        for flag in getattr(dis, "MAKE_FUNCTION_FLAGS", None)
        or getattr(dis, "FUNCTION_ATTR_FLAGS", None)
    ),
)


class CodeBuilderBase:
    def __init__(self):
        self.consts = {None: 0}
        self.names = {}
        self.varnames = {}
        self.cellvars = {}
        self.freevars = {}

    def ascode(self, func_name: str, argcount: int) -> CodeType:
        code = bytes(self)
        stacksize = max(
            accumulate(
                dis.stack_effect(op, arg)
                if op >= HAVE_ARGUMENT
                else dis.stack_effect(op)
                for op, arg in zip(code[::2], code[1::2])
            )
        )

        return CodeType(
            argcount,
            0,  # posonlyargcount
            0,  # kwonlyargcount
            len(self.varnames),
            stacksize,  # stacksize
            (CompilerFlags.OPTIMIZED | CompilerFlags.NEWLOCALS),
            code,
            tuple(self.consts),  # insertion order
            tuple(self.names),
            tuple(self.varnames),
            "",
            func_name,
            0,
            bytes(),
            tuple(self.freevars),
            tuple(self.cellvars),
        )


def _code(self, op: int, arg: int = 0):
    while arg > 256:
        arg, rest = divmod(arg, 256)
        self.append(EXTENDED_ARG)
        self.append(rest)
    self.append(op)
    self.append(arg)
    return self


def _closure(self, op: int, name: str):
    freevars = self.freevars
    del freevars[name]  # FIXME: reorder subsequent freevars?
    cellvars = self.cellvars
    self.append(op)
    self.append(cellvars.setdefault(name, len(cellvars)))
    return self


def _compare(self, op: int, cmp: str):
    self.append(op)
    self.append(cmp_op.index(cmp))
    return self


def _const(self, op: int, const):
    self.append(op)
    consts = self.consts
    self.append(consts.setdefault(const, len(consts)))
    return self


def _free(self, op: int, name: str):
    self.append(op)
    freevars = self.freevars
    self.append(freevars.setdefault(name, len(freevars)))
    return self


def _name(self, op: int, name: str):
    self.append(op)
    names = self.names
    self.append(names.setdefault(name, len(names)))
    return self


def _local(self, op: int, name: str):
    self.append(op)
    varnames = self.varnames
    self.append(varnames.setdefault(name, len(varnames)))
    return self


CodeBuilder = type(
    "CodeBuilder",
    (CodeBuilderBase, bytearray),
    {
        name.replace("+", "_").lower(): partialmethod(
            _closure
            if name == "LOAD_CLOSURE"
            else _const
            if op in hasconst
            else _compare
            if op in hascompare
            else _free
            if op in hasfree
            else _local
            if op in haslocal
            else _name
            if op in hasname
            else _code,
            op,
        )
        for op, name in enumerate(opname)
    },
)

if __name__ == "__main__" and version_info < (3, 10):
    from dis import dis, show_code

    inner = (
        CodeBuilder()
        .load_deref("y")
        .load_fast("z")
        .inplace_add()
        .store_deref("y")
        .load_deref("y")
        .load_fast("z")
        .binary_add()
        .return_value()
    )

    code = (
        CodeBuilder()
        .load_fast("x")
        .store_deref("y")
        .load_closure("y")
        .build_tuple(1)
        .load_const(inner.ascode("inner", 1))
        .load_const("func.<locals>.inner")
        .make_function(int(MakeFunctionFlags.CLOSURE))
        .store_fast("inner")
        .load_fast("inner")
        .return_value()
    )

    def func(x):
        y = x

        def inner(z):
            nonlocal y
            y += z
            return y + z

        return inner

    dis(func)
    show_code(code.ascode("func", 1))
    show_code(func)
