from typing import cast


with open("aoc2024/day9input.txt") as io:
    lens = [*map(int, next(io).rstrip()), 0]

expand: list[int | None] = []
for disk, (size, space) in enumerate(zip(lens[::2], lens[1::2])):
    expand.extend([disk] * size)
    expand.extend([None] * space)

i = 0
j = len(expand)
n = sum(lens[::2])
checksum = 0
for k in range(n):
    if (x := expand[i]) is None:
        while True:
            j -= 1
            x = expand[j]
            if x is not None:
                break
    i += 1
    checksum += k * x
print(checksum)

blocks = list(map(list, zip(lens[1::2], enumerate(lens[::2]))))
for k, block in enumerate(reversed(blocks[1:]), start=1):
    file, size = t = cast(tuple[int, int], block.pop(1))
    try:
        to = next(b for b in blocks[:-k] if size <= cast(int, b[0]))
    except StopIteration:
        block.insert(1, t)
    else:
        blocks[-k - (len(block) > 1)][0] += size  # pyright: ignore[reportOperatorIssue]
        to[0] -= size  # pyright: ignore[reportOperatorIssue]
        to.append(t)

index = checksum = 0
for space, *sizes in blocks:
    for file, size in cast(list[tuple[int, int]], sizes):
        end = index + size
        checksum += file * (index + end - 1) * size // 2
        index = end
    index += space  # pyright: ignore[reportOperatorIssue]
print(checksum)
