assert 0x434C49434B == int.from_bytes(b"CLICK", "big")

dial = 50
zeros = 0
with open("aoc2025/day1input.txt") as rotations:
    for rotation in rotations:
        direction = rotation[0]
        start_zero = not dial
        degrees = int(rotation[1:])
        start = not dial
        if rotation[0] == "L":
            dial -= degrees
        else:
            dial += degrees
        turns, dial = divmod(dial, 100)
        end_zero = not dial
        if start_zero and turns < 0:
            turns += 1
        if end_zero and turns > 0:
            turns -= 1
        zeros += abs(turns) + end_zero
print(zeros)
