import re
from operator import itemgetter

with open("aoc2024/day4input.txt") as lines:
    lines = list(map(str.rstrip, lines))

choices = {"XMAS", "SAMX"}

count = 0
for i, line in enumerate(lines):
    for j, char in enumerate(line):
        count += line[j : j + 4] in choices
        count += "".join(map(itemgetter(j), lines[i : i + 4])) in choices
        if i + 3 >= len(lines):
            continue
        if j + 3 < len(line):
            dn = [char]
            for k in range(1, 4):
                dn.append(lines[i + k][j + k])
            count += "".join(dn) in choices
        if j >= 3:
            up = [char]
            for k in range(1, 4):
                up.append(lines[i + k][j - k])
            count += "".join(up) in choices

print(count)

choices = re.compile(r"M.S.A.M.S|M.M.A.S.S|S.S.A.M.M|S.M.A.S.M")

count = 0
for i, line in enumerate(lines[:-2]):
    for j in range(len(line) - 2):
        k = itemgetter(slice(j, j + 3))
        count += (
            choices.match("".join((k(line), k(lines[i + 1]), k(lines[i + 2]))))
            is not None
        )

print(count)
