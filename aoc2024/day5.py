import re
from functools import cmp_to_key


def rules_to_key(precedes: dict[str, set[str]]):
    def mycmp(a: str, b: str) -> int:
        return (
            -1
            if b in precedes.get(a, set())
            else 1
            if a in precedes.get(b, set())
            else 0
        )

    return cmp_to_key(mycmp=mycmp)


ordering = re.compile(r"^(\d+)\|(\d+)$")
precedes: dict[str, set[str]] = {}
correct = 0
incorrect = 0
with open("aoc2024/day5input.txt", "rt") as lines:
    for line in lines:
        line = line.rstrip()
        if matches := ordering.match(line):
            precedes.setdefault(matches[1], set()).add(matches[2])
        elif not line:
            key = rules_to_key(precedes)
        elif line:
            update = line.split(",")
            if any(
                (follow := precedes.get(tail)) and head in follow
                for i, head in enumerate(update[:-1])
                for tail in update[i:]
            ):
                update.sort(key=key)  # pyright: ignore[reportPossiblyUnboundVariable]
                incorrect += int(update[len(update) // 2])
            else:
                correct += int(update[len(update) // 2])

print(correct, incorrect)
