import operator
import re
from graphlib import TopologicalSorter


def add(x: int, y: int) -> int:
    xi = x & 1
    yi = y & 1
    c = [xi ^ yi]
    carry = xi & yi
    x >>= 1
    y >>= 1
    while x or y:
        xi = x & 1
        yi = y & 1
        z = xi ^ yi
        c.append(z ^ carry)
        carry &= z
        carry |= xi & yi
        x >>= 1
        y >>= 1
    c.append(carry)
    xi = 0
    for yi in reversed(c):
        xi = (xi << 1) | yi
    return xi


def check(n: int, exprs: dict[str, str]) -> dict[str, str]:

    fixes = {
        "cbj": "qjj",
        "cfk": "z35",
        "dmn": "z18",
        "gmt": "z07",
        "qjj": "cbj",
        "z07": "gmt",
        "z18": "dmn",
        "z35": "cfk",
    }

    def get(*key: str) -> str:
        val = exprs.get(" ".join(key), exprs.get(" ".join(reversed(key))))
        return fixes.get(val, val)

    carry = ""
    for i in range(n):
        xi = f"x{i:02d}"
        yi = f"y{i:02d}"
        zi = f"z{i:02d}"
        xor = get(xi, "XOR", yi)
        assert not (i and xor == zi)
        and_ = get(xi, "AND", yi)
        assert and_ != zi
        if carry:
            assert get(xor, "XOR", carry) == zi
            acc = get(carry, "AND", xor)
            assert acc != zi
            carry = get(acc, "OR", and_)
            assert carry != zi
        else:
            carry = and_

    return fixes


init = re.compile(r"^(?P<key>\w{3}): (?P<val>[01])$")
expr = re.compile(r"^(?P<lhs>\w{3}) (?P<op>AND|OR|XOR) (?P<rhs>\w{3}) -> (?P<key>\w{3})$")

state = {}
exprs = {}
ts = TopologicalSorter()
with open("aoc2024/day24input.txt", "rt") as lines:
    for line in lines:
        if matches := init.match(line):
            state[matches["key"]] = int(matches["val"])
        elif matches := expr.match(line):
            state[matches["key"]] = matches["lhs"], matches["op"], matches["rhs"]
            ts.add(matches["key"], matches["lhs"], matches["rhs"])
            key, _, val = line.rstrip().rpartition(" -> ")
            exprs[key] = val


ops = {"AND": operator.and_, "OR": operator.or_, "XOR": operator.xor}
for node in ts.static_order():
    val = state[node]
    if isinstance(val, int):
        continue
    lhs, op, rhs = val
    state[node] = ops[op](state[lhs], state[rhs])

num = 0
for bit in reversed(range(46)):
    num = (num << 1) | state[f"z{bit:02d}"]

print(num)
print(*sorted(check(45, exprs)), sep=",")
