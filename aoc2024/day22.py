from collections import defaultdict


def random(secret: int) -> int:
    secret ^= secret << 6
    secret &= 0xFFFFFF
    secret ^= secret >> 5
    secret &= 0xFFFFFF
    secret ^= secret << 11
    secret &= 0xFFFFFF
    return secret


with open("aoc2024/day22input.txt", "rt") as lines:
    initial = [int(line.rstrip()) for line in lines]


WINDOW = 19**4  # four deltas, each in -9..9, packed into one int

total = 0
bananas: defaultdict[int, int] = defaultdict(int)
for secret in initial:
    seen: set[int] = set()
    price = secret % 10
    window = 0
    for i in range(2000):
        secret = random(secret)
        nxt = secret % 10
        window = (window * 19 + nxt - price + 9) % WINDOW
        price = nxt
        if i > 2 and window not in seen:
            seen.add(window)
            bananas[window] += price
    total += secret

print(total, max(bananas.values()))
