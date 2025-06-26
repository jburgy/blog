import re
from fractions import Fraction

pattern = re.compile(r"^(?P<type>[^:]+): X[+=](?P<x>\d+), Y[+=](?P<y>\d+)$")

cost = 0
add = 10_000_000_000_000  # or 0 for part 1
a00 = a10 = a01 = a11 = 0
pivot = Fraction()
with open("aoc2024/day13input.txt", "rt") as lines:
    for line in lines:
        matches = pattern.match(line)
        if matches is None:
            pass
        elif matches["type"] == "Button A":
            a00 = int(matches["x"])
            a10 = int(matches["y"])
            pivot = Fraction(a10, a00)
        elif matches["type"] == "Button B":
            a01 = int(matches["x"])
            a11 = int(matches["y"])
        elif matches["type"] == "Prize":
            b0 = int(matches["x"]) + add
            b1 = int(matches["y"]) + add

            c1 = (b1 - pivot * b0) / (a11 - pivot * a01)
            c0 = (b0 - c1 * a01) / a00

            cost += (
                c0.numerator * 3 + c1.numerator
                if c0.is_integer()
                and c1.is_integer()
                else 0
            )

print(cost)
