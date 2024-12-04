from operator import __sub__


def isvalid(*numbers: int) -> bool:
    increments = list(map(__sub__, numbers[1:], numbers[:-1]))
    a = min(increments)
    b = max(increments)
    return (-3 <= a < 0 and b < 0) or (0 < a and 0 < b <= 3)


valid = 0
with open("aoc2024/day2input.txt", "rt") as lines:
    for line in lines:
        numbers = tuple(map(int, line.rstrip().split()))
        valid += isvalid(*numbers) or any(
            isvalid(*numbers[:i], *numbers[i + 1 :]) for i in range(len(numbers))
        )

print(valid)
