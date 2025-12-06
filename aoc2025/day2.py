from pathlib import Path


def candidates(repeat: int, start: str, end: str):
    start_prefix, start_rem = divmod(len(start), repeat)
    end_prefix, end_rem = divmod(len(end), repeat)

    if start_rem and end_rem:
        return

    prefix = min(start_prefix, end_prefix)
    for i in range(
        int(start[:prefix] or "1"), int(end[: prefix + len(end) - len(start)]) + 1
    ):
        candidate = int(str(i) * repeat)
        if int(start) <= candidate <= int(end):
            yield candidate


ranges = Path("aoc2025/day2input.txt").read_text().strip()

invalid = set()
for item in ranges.split(","):
    start, end = item.split("-")

    for repeat in range(2, len(end) + 1):
        invalid.update(candidates(repeat, start, end))

print(sum(invalid))
