# ~*~ encoding: utf8; ~*~
""" Compiling forth to python bytecode for fun micro-optimizations

https://users.ece.cmu.edu/~koopman/stack_compiler/stack_co.pdf
https://www.complang.tuwien.ac.at/forth/gforth/Docs-html/index.html
https:http://git.annexia.org/?p=jonesforth.git;a=blob;f=jonesforth.S
https://towardsdatascience.com/understanding-python-bytecode-e7edaae8734d
http://cubbi.com/fibonacci/forth.html
"""
from argparse import ArgumentParser
from ast import literal_eval
from dis import COMPILER_FLAG_NAMES, dis
from opcode import cmp_op, hasjrel, opmap
from timeit import timeit
from types import CodeType, FunctionType

COMPILER_FLAGS = {v: k for k, v in COMPILER_FLAG_NAMES.items()}
TRANS = str.maketrans("*+-/<=>{}", "TPMDLEGOC")


def _gen_emitter(ops):
    code = tuple(byte for op in ops.split() for byte in (opmap[op], 0))

    def emitter(self, word):
        return code
    return emitter


class ForthCompilerMeta(type):
    def __new__(meta, name, bases, dct):
        ops = {
            "+": "INPLACE_ADD",
            "-": "INPLACE_SUBTRACT",
            "*": "INPLACE_MULTIPLY",
            "2*": "DUP_TOP INPLACE_ADD",
            "2/": "LOAD_CONST INPLACE_RSHIFT",
            "and": "INPLACE_AND",
            # https://complang.tuwien.ac.at/forth/gforth/Docs-html/Data-stack.html
            "drop": "POP_TOP",  # w --
            "nip": "ROT_TWO POP_TOP",  # w1 w2 -- w2
            "dup": "DUP_TOP",  # w - w w
            "over": "ROT_TWO DUP_TOP ROT_THREE",  # w1 w2 -- w1 w2 w1
            "tuck": "DUP_TOP ROT_THREE",  # w1 w2 -- w2 w1 w2
            "swap": "ROT_TWO",  # w1 w2 -- w2 w1
            "rot": "ROT_THREE ROT_THREE",  # w1 w2 w3 -- w2 w3 w1
            "-rot": "ROT_THREE",  # w1 w2 w3 -- w3 w1 w2
            "2drop": "POP_TOP POP_TOP",  # w1 w2 --
            "2nip": "ROT_FOUR ROT_FOUR POP_TOP POP_TOP",  # w1 w2 w3 w4 - w3 w4
            "2dup": "DUP_TOP_TWO",  # w1 w2 -- w1 w2 w1 w2
            "2swap": "ROT_FOUR ROT_FOUR",  # w1 w2 w3 w4 -- w3 w4 w1 w2
        }
        for word, value in ops.items():
            dct["emit_" + word.translate(TRANS)] = _gen_emitter(value)
        return type(name, bases, dct)


class ForthCompiler(metaclass=ForthCompilerMeta):
    def __init__(self):
        self.code = bytearray()
        self.blocks = []
        self.consts = {}
        self.varnames = {}
        self.fastop = opmap["LOAD_FAST"]

    def emit_if(self, word):
        self.emit_begin(word)
        return opmap["POP_JUMP_IF_FALSE"], 0

    def emit_else(self, word):
        code, blocks = self.code, self.blocks
        here = len(code)
        block, blocks[-1] = blocks[-1], here
        code[block + 1] = here + 2
        return opmap["JUMP_FORWARD"], 0

    def emit_then(self, word):
        code, blocks = self.code, self.blocks
        here, block = len(code), blocks.pop()
        code[block + 1] = (
            here - (block + 2)
            if code[block] in hasjrel
            else here
        )
        return ()

    def emit_begin(self, word):
        self.blocks.append(len(self.code))
        return ()

    def emit_while(self, word):
        code, blocks = self.code, self.blocks
        block, blocks[-1] = blocks[-1], len(code)
        return opmap["POP_JUMP_IF_FALSE"], block

    def emit_compare(self, word):
        return opmap["COMPARE_OP"], cmp_op.index(word)

    emit_GE = emit_compare

    def emit_repeat(self, word):
        code, blocks = self.code, self.blocks
        target = len(code) + 2
        block = blocks.pop()
        while code[block] == opmap["POP_JUMP_IF_FALSE"]:
            previous, block = block, code[block + 1]
            code[previous + 1] = (
                target - previous if code[previous] in hasjrel
                else target
            )
        return opmap["JUMP_ABSOLUTE"], block

    def emit_variable(self, word):
        res = self.fastop, self.varnames[word]
        self.fastop = opmap["LOAD_FAST"]  # `to` assigns once
        return res

    def emit_declare(self, word):
        varnames = self.varnames
        varnames[word] = len(varnames)
        setattr(self, "emit_" + word, self.emit_variable)
        return ()

    def emit_literal(self, word):
        consts = self.consts
        return (
            opmap["LOAD_CONST"],
            consts.setdefault(literal_eval(word), len(consts)),
        )

    emit_default = emit_literal

    def emit_O(self, word):
        self.emit_default = self.emit_declare
        return ()

    def emit_C(self, word):
        self.emit_default = self.emit_literal
        return ()

    def emit_to(self, word):
        self.fastop = opmap["STORE_FAST"]
        return ()

    def compile(self, func, argcount=0):
        code = self.code
        lnotab = bytearray()
        offset, lineno = 0, 0
        for i, line in enumerate(func.__doc__.splitlines()):
            for word in line.split():
                method = "emit_" + word.translate(TRANS)
                code.extend(getattr(self, method, self.emit_default)(word))
            n = len(code)
            lnotab.extend((n - offset, i - lineno))
            offset, lineno = n, i

        # function epilogue: pop return value off stack
        code.extend((opmap["RETURN_VALUE"], 0))

        code = CodeType(
            argcount,
            0,  # posonlyargcount
            0,  # kwonlyargcount
            len(self.varnames),
            0,  # stacksize
            (
                COMPILER_FLAGS["OPTIMIZED"] |
                COMPILER_FLAGS["NEWLOCALS"] |
                COMPILER_FLAGS["NOFREE"]
            ),
            bytes(code),
            tuple(self.consts),  # insertion order
            tuple(),
            tuple(self.varnames),
            func.__code__.co_filename,
            func.__code__.co_name,
            func.__code__.co_firstlineno,
            bytes(lnotab),
        )
        return FunctionType(code, func.__globals__)


def fib(n):
    """{ n }
n 1 0
begin rot dup
while 1 - -rot tuck +
repeat
drop nip
"""
    a = 1
    b = 0
    while n:
        n -= 1
        a, b = a + b, a
    return a


def fast_fib(n):
    """{ n m }
n 1 begin 2dup >= while 2* repeat to m
1 0 begin m 2/ dup to m
while  swap 2dup * 2*
       swap dup *
       rot dup * dup
       rot + -rot +
       n m and
       if tuck + then
repeat nip
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
        Fn = 2 * Fnm1 * Fn2 + Fn2
        Fnm1 = Fnm1 * Fnm1 + Fn2
        if n & m:
            Fnm1, Fn = Fn, Fnm1 + Fn
        m >>= 1
    return Fn


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("n", type=int, help="which Fibonacci number")
    parser.add_argument("--fast", dest="func", action="store_const",
                        const=fast_fib, default=fib)
    args = parser.parse_args()

    python = args.func
    forth = ForthCompiler().compile(python, argcount=1)
    dis(forth)

    p = timeit("f(n)", globals=dict(n=args.n, f=python))
    f = timeit("f(n)", globals=dict(n=args.n, f=forth))

    print("python =", p, "forth =", f, "forth/python =", f / p)
