import re

instruction = re.compile(r"mul\((\d{1,3}),(\d{1,3})\)|do\(\)|don't\(\)")
total = 0
valid = True
with open("aoc2024/day3input.txt", "rt") as lines:
    for line in lines:
        for matches in re.finditer(instruction, line):
            if matches[0] == "do()":
                valid = True
            elif matches[0] == "don't()":
                valid = False  # True for part 1
            elif valid:
                total += int(matches[1]) * int(matches[2])
print(total)
