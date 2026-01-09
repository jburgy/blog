from collections.abc import Callable
from functools import cache


def counter(needles: list[str]) -> Callable[[str], int]:

    @cache
    def count(haystack: str) -> int:
        return (
            sum(
                count(haystack[len(needle):])
                for needle in needles
                if haystack.startswith(needle)
            )
            if haystack
            else 1
        )

    return count


with open("aoc2024/day19input.txt", "rt") as lines:
    patterns = next(lines).rstrip().replace(" ", "").split(",")
    count = counter(sorted(patterns, key=len, reverse=True))  # ty: ignore[invalid-argument-type]
    next(lines)
    counts = [count(line.rstrip()) for line in lines]


print(sum(count > 0 for count in counts), sum(counts))
