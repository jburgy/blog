import re
from fractions import Fraction

pattern = re.compile(r"^(?P<type>[^:]+): X[+=](?P<x>\d+), Y[+=](?P<y>\d+)$")

cost = 0
add = 10_000_000_000_000  # or 0 for part 1
with open("aoc2024/day13input.txt", "rt") as lines:
    for line in lines:
        matches = pattern.match(line)
        if matches is None:
            pass
        elif matches["type"] == "Button A":
            a00 = Fraction(matches["x"])
            a10 = Fraction(matches["y"])
        elif matches["type"] == "Button B":
            a01 = Fraction(matches["x"])
            a11 = Fraction(matches["y"])
        elif matches["type"] == "Prize":
            b0 = Fraction(matches["x"]) + add
            b1 = Fraction(matches["y"]) + add

            pivot = a10 / a00
            c1 = (b1 - pivot * b0) / (a11 - pivot * a01)
            c0 = (b0 - c1 * a01) / a00

            cost += (
                c0.numerator * 3 + c1.numerator
                if c0.denominator == 1
                and c1.denominator == 1
                else 0
            )

print(cost)