# input from https://adventofcode.com/2024/day/1/input

from collections import Counter

a = []
b = []
with open("aoc2024/day1input.txt", "rt") as lines:
    for line in lines:
        a.append(int(line[:6]))
        b.append(int(line[8:-1]))

print(sum(abs(x - y) for x, y in zip(sorted(a), sorted(b))))
c = Counter(b)
print(sum(x * c[x] for x in a))
