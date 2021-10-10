from typing import Iterator

MAP = str.maketrans(
    "EJNQRWXDSYFTAMCIVBKULOPGHZejnqrwxdsyftamcivbkulopghz",
    "0111222333445566677788899901112223334455666777888999",
)


def overlapping(haystack: str, needle: str, n: int) -> Iterator[str]:
    """ Generate all overlapping replacements of needle in haystack

    >>> list(overlapping("1233345", "dy", 2))
    ['12dy345', '123dy45']
    """
    pattern, i = needle.translate(MAP), -1
    while True:
        i = haystack.find(pattern, i + 1)
        if i < 0:
            break
        yield haystack[:i] + needle + haystack[i + n:]


def replaceall(haystack: str, needle: str, *needles: str) -> Iterator[str]:
    """
    >>> list(replaceall("358675", "Dali", "um", "Sao", "da", "Pik"))
    ['daPik5', 'Sao6um', 'Dalium']
    """
    n = len(needle)
    if 0 <= sum(map(str.isdigit, haystack), -n) <= 1:
        yield from overlapping(haystack, needle, n)
    elif needles:
        yield from replaceall(haystack, *needles)
        for replacement in overlapping(haystack, needle, n):
            yield from replaceall(replacement, *needles)
