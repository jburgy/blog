from functools import cache


@cache
def count(m: int, stone: str) -> int:
    if m == 0:
        return 1
    n = m - 1
    if stone == "0":
        return count(n, "1")
    half, remainder = divmod(len(stone), 2)
    if not remainder:
        return count(n, stone[:half]) + count(n, str(int(stone[half:])))
    return count(n, str(int(stone) * 2024))


stones = tuple("965842 9159 3372473 311 0 6 86213 48".split())
print(sum(count(25, stone) for stone in stones))
print(sum(count(75, stone) for stone in stones))
