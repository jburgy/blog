n = 12  # change to 2 for part 1

total = 0
with open("aoc2025/day3input.txt") as lines:
    for line in lines:
        line = line.strip()
        i = 0
        digits = []
        for j in range(1 - n, 1):
            digit = max(line[i:j or None])
            i = line.index(digit, i, j or None) + 1
            digits.append(digit)
        total += int("".join(digits))
print(total)
