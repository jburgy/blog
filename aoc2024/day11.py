""" recursive alternative

>>> import functools
>>> @functools.cache
... def count(m: int, stone: str) -> int:
...     if m == 0:
...         return 1
...     n = m - 1
...     if stone == "0":
...         return count(n, "1")
...     half, remainder = divmod(len(stone), 2)
...     if not remainder:
...         return count(n, stone[:half]) + count(n, str(int(stone[half:])))
...     return count(n, str(int(stone) * 2024))
...
>>> sum(count(25, stone) for stone in "965842 9159 3372473 311 0 6 86213 48".split())
183435
>>> sum(count(75, stone) for stone in "965842 9159 3372473 311 0 6 86213 48".split())
218279375708592
"""

from collections import defaultdict
from itertools import chain, compress, repeat
from operator import not_

stones = tuple("965842 9159 3372473 311 0 6 86213 48".split())
caches = [defaultdict(int) for _ in range(76)]
q = list(chain(zip(repeat(75), stones), zip(repeat(25), stones)))

while q:
    m, stone = t = q.pop()
    cache = caches[m]
    if m == 0:
        cache[stone] = 1
        continue
    if stone == "0":
        stones = ("1",)
    else:
        half, rest = divmod(len(stone), 2)
        if rest:
            stones = str(int(stone) * 2024),
        else:
            stones = (stone[:half], str(int(stone[half:])))
    n = m - 1
    counts = tuple(map(caches[n].get, stones))
    if all(counts):
        cache[stone] = sum(counts)
    else:
        q.append(t)
        q.extend(zip(repeat(n), compress(stones, map(not_, counts))))

print(sum(caches[25].values()))
print(sum(caches[75].values()))
