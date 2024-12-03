#!/usr/bin/env python3.9
# ~*~ conding: utf8; ~*~
from ast import literal_eval
from dis import COMPILER_FLAG_NAMES, dis, show_code
from opcode import opmap
import re
from sys import argv
from timeit import timeit
from types import CodeType, FunctionType

COMPILER_FLAGS = {k: v for v, k in COMPILER_FLAG_NAMES.items()}
DIS = re.compile(
    r"(?P<lineno>.{3}) "
    r"(?P<current_mark>.{3}) "
    r"(?P<jump_target>.{2}) "
    r"(?P<offset>.{4}) "
    r"(?P<opname>.{,20}) ?"
    r"(?P<oparg>.{,5}) ?"
    r"\(?(?P<argrepr>.*?)\)?"
)


def _tuple_from_dict(d):
    n = len(d) if 0 in d else len(d) + 1
    return tuple(d.get(i) for i in range(n))


def assemble(func: callable):
    """invert dis.Instruction._disassemble"""
    code = bytearray()
    lnotab = bytearray()
    consts = {}
    names = {}
    varnames = {}
    plineno, poffset = None, None
    for line in func.__doc__.splitlines():
        m = DIS.fullmatch(line)
        if not m:
            continue
        lineno = m.group("lineno").lstrip()
        opname = m.group("opname").rstrip()
        oparg = m.group("oparg").lstrip()
        if lineno:
            lineno = int(lineno)
            offset = int(m.group("offset"))
            lnotab.append(offset if poffset is None else offset - poffset)
            lnotab.append(lineno if plineno is None else lineno - plineno)
            plineno = lineno
            poffset = offset
        code.append(opmap[opname])
        if oparg:
            oparg = int(oparg)
            code.append(oparg)
            argrepr = m.group("argrepr")
            if opname == "LOAD_CONST":
                consts[oparg] = literal_eval(argrepr)
            elif opname in {"LOAD_ATTR", "LOAD_METHOD"}:
                names[oparg] = argrepr
            elif opname in {"LOAD_FAST", "STORE_FAST"}:
                varnames[oparg] = argrepr
        else:
            code.append(0)
    code = CodeType(
        func.__code__.co_argcount,
        func.__code__.co_posonlyargcount,
        func.__code__.co_kwonlyargcount,
        len(varnames),
        0,  # stacksize
        COMPILER_FLAGS["OPTIMIZED"]
        | COMPILER_FLAGS["NEWLOCALS"]
        | COMPILER_FLAGS["NOFREE"],
        bytes(code),
        _tuple_from_dict(consts),
        _tuple_from_dict(names),
        _tuple_from_dict(varnames),
        func.__code__.co_filename,
        func.__code__.co_name,
        func.__code__.co_firstlineno,
        bytes(lnotab),
    )
    return FunctionType(code, func.__globals__)


def fibonacci(n: int) -> int:
    """
  1           0 LOAD_CONST               1 (1)
              2 LOAD_FAST                0 (n)
              4 LOAD_METHOD              0 (bit_length)
              6 CALL_METHOD              0
              8 LOAD_CONST               1 (1)
             10 BINARY_SUBTRACT
             12 BINARY_LSHIFT
             14 STORE_FAST               1 (m)

  2          16 LOAD_CONST               2 (0)
             18 LOAD_CONST               1 (1)

  3          20 LOAD_FAST                1 (m)
        >>   22 POP_JUMP_IF_FALSE       84

  4          24 DUP_TOP_TWO
             26 INPLACE_MULTIPLY
             28 DUP_TOP
             30 INPLACE_ADD

  5          32 ROT_TWO
             34 DUP_TOP
             36 INPLACE_MULTIPLY

  6          38 ROT_THREE
             40 ROT_THREE
             42 DUP_TOP
             44 INPLACE_MULTIPLY

  7          46 DUP_TOP
             48 ROT_THREE
             50 INPLACE_ADD

  8          52 ROT_THREE
             54 INPLACE_ADD

  9          56 LOAD_FAST                0 (n)
             58 LOAD_FAST                1 (m)
             60 INPLACE_AND
             62 POP_JUMP_IF_FALSE       70

 10          64 DUP_TOP
             66 ROT_THREE
             68 INPLACE_ADD

 11     >>   70 ROT_TWO

 12          72 LOAD_FAST                1 (m)
             74 LOAD_CONST               1 (1)
             76 INPLACE_RSHIFT
             78 DUP_TOP
             80 STORE_FAST               1 (m)

 13          82 JUMP_ABSOLUTE           22

 14     >>   84 POP_TOP
             86 RETURN_VALUE
"""
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


fibonacci_optimized = assemble(fibonacci)


if __name__ == "__main__":
    n = int(argv[1]) if len(argv) > 1 else 12
    show_code(fibonacci_optimized)
    dis(fibonacci_optimized)

    py = timeit("f(n)", globals=dict(n=n, f=fibonacci))
    bc = timeit("f(n)", globals=dict(n=n, f=fibonacci_optimized))

    print("python =", py, "bytecode =", bc, "bytecode/python =", bc / py)
