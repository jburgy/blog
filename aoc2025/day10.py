from functools import reduce
from itertools import combinations
from operator import xor

from scipy import optimize, sparse


def first_half(desired: list[int], buttons: list[tuple[int]]):
    total = 0
    for goal, switches in zip(desired, buttons):
        for n in range(1, len(buttons) + 1):
            for attempt in combinations(switches, n):
                if reduce(xor, attempt, 0) == goal:
                    total += n
                    break
            else:
                continue
            break
        else:
            raise StopIteration
    return total


def second_half(buttons: list[tuple[int]], joltages: list[tuple[int]]) -> int:
    total = 0
    for button, joltage in zip(buttons, joltages):
        A_eq = sparse.dok_array((len(joltage), len(button)))
        for j, word in enumerate(button):
            for i, bit in enumerate(bin(word)[:1:-1]):
                if bit == "1":
                    A_eq[i, j] = 1
        sol = optimize.linprog(
            [1] * len(button), A_eq=A_eq, b_eq=joltage, integrality=1  # type: ignore
        )
        assert sol.success
        total += int(sum(sol.x))  # ty: ignore[no-matching-overload]
    return total


desired = []
buttons = []
joltages = []
with open("aoc2025/day10input.txt", "rt") as lines:
    for line in lines:
        [diagram, *schematics, joltage] = line.rstrip().split()

        desired.append(sum((c == "#") * (1 << i) for i, c in enumerate(diagram[1:-1])))
        buttons.append(
            tuple(
                sum((1 << int(i)) for i in schematic[1:-1].split(","))
                for schematic in schematics
            )
        )
        joltages.append(tuple(map(int, joltage[1:-1].split(","))))

# print(first_half(desired, buttons))
print(second_half(buttons, joltages))
