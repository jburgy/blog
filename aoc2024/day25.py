locks = []
keys = []
heights = None
with open("aoc2024/day25input.txt", "rt") as lines:
    for line in lines:
        line = line.rstrip()
        if not line:
            heights = None
            continue
        if heights is None:
            heights = [0] * len(line)
            if line.count("#") == len(line):
                locks.append(heights)
            else:
                keys.append(heights)
        for i, char in enumerate(line):
            heights[i] += char == "#"

fit = sum(
    all(sum(t) < 8 for t in zip(lock, key))
    for lock in locks
    for key in keys
)
print(fit)
