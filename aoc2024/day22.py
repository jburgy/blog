from collections import defaultdict
from collections.abc import Iterable

import numpy as np
import numpy.typing as npt


def random(secret: npt.NDArray[np.int_]) -> npt.NDArray[np.int_]:
    secret ^= secret << 6
    secret %= 16777216
    secret ^= secret >> 5
    secret %= 16777216
    secret ^= secret * 2048
    secret %= 16777216
    return secret


def ntimes(n: int, secret: int) -> Iterable[int]:
    for _ in range(n):
        yield secret
        secret = random(secret)
    yield secret


with open("aoc2024/day22input.txt", "rt") as lines:
    initial = [int(line.rstrip()) for line in lines]


bananas = defaultdict(int)
for secret in initial:
    prices = np.fromiter(ntimes(2000, secret), dtype=int, count=2001) % 10
    sequences, indices = np.unique(
        np.lib.stride_tricks.sliding_window_view(np.diff(prices), 4),
        return_index=True,
        axis=0,
    )
    for sequence, banana in zip(sequences, prices[indices + 4]):
        bananas[tuple(sequence)] += banana

print(max(bananas.values()))
