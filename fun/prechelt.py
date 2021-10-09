from typing import Iterator

MAP = str.maketrans(
    "EJNQRWXDSYFTAMCIVBKULOPGHZejnqrwxdsyftamcivbkulopghz",
    "0111222333445566677788899901112223334455666777888999",
)


def overlapping(haystack: str, needle: str, n: int) -> Iterator[str]:
    pattern = needle.translate(MAP)

    i = -1
    while True:
        i = haystack.find(pattern, i + 1)
        if i < 0:
            break
        yield haystack[:i] + needle + haystack[i + n:]


def replaceall(haystack: str, *needles: str) -> Iterator[str]:
    """
    >>> list(replaceall("358675", "Dali", "um", "Sao", "da", "Pik"))
    ['daPik5', 'Sao6um', 'Dalium']
    """
    m, n = sum(ch.isdigit() for ch in haystack), len(needles)
    stack = [(haystack, m, i) for i in range(n)]  # try all needles on entire haystack
    while stack:
        haystack, m, i = stack.pop()
        needle = needles[i]
        i += 1  # try next needle on overlapping replacements
        k = len(needle)
        m -= k  # remove k digits ⇒ reduce search space
        if m < 0 or (m > 1 and i == n):
            continue
        replacements = overlapping(haystack, needle, k)
        if m <= 1:  # 0 or 1 digits left, habemus solutiones!
            yield from replacements
        else:
            stack.extend((haystack, m, i) for haystack in replacements)
