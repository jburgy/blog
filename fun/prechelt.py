from typing import Iterator

MAP = str.maketrans(
    "EJNQRWXDSYFTAMCIVBKULOPGHZejnqrwxdsyftamcivbkulopghz",
    "0111222333445566677788899901112223334455666777888999",
)
FAIL = 10
WORD = FAIL + 1


def count_digits(s: str, start: int = 0, sum=sum, map=map, isdigit=str.isdigit) -> int:
    return sum(map(isdigit, s), start)


def overlapping(haystack: str, needle: str, n: int) -> Iterator[str]:
    """Generate all overlapping replacements of needle in haystack

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
    if 0 <= count_digits(haystack, -n) <= 1:
        yield from overlapping(haystack, needle, n)
    elif needles:
        yield from replaceall(haystack, *needles)
        for replacement in overlapping(haystack, needle, n):
            yield from replaceall(replacement, *needles)


def aho_corasick(*words):
    """https://en.wikipedia.org/wiki/Aho%E2%80%93Corasick_algorithm"""
    root = [None] * WORD
    for word in words:
        node = root
        for digit in map(int, word.translate(MAP)):
            next = node[digit]
            if next is None:
                node[digit] = next = [None] * WORD  # pyright: ignore[reportArgumentType, reportCallIssue]
            node = next
        node.append(word)

    root[FAIL] = root  # pyright: ignore[reportArgumentType, reportCallIssue]
    stack = []
    append = stack.append
    for node in root[:FAIL]:
        if node:
            node[FAIL] = root
            append(node)

    pop = stack.pop
    while stack:
        curr = pop()
        fail = curr[FAIL]
        for digit, node in enumerate(curr[:FAIL]):
            if node:
                node[FAIL] = fail[digit] or fail
                append(node)
    return root


def replaceal1(haystack: str, *needles: str) -> Iterator[str]:
    """
    >>> list(replaceal1("358675", "Dali", "um", "Sao", "da", "Pik"))
    ['Dalium', 'Sao5um', 'daPik5']
    """
    root = aho_corasick(*needles)
    seen = [[""]]
    append = seen.append
    node = root
    for j, num in enumerate(haystack, 1):
        digit = int(num)
        while True:
            temp = node[digit]  # pyright: ignore[reportOptionalSubscript]
            if temp:
                node = temp
                break
            if node is root:
                break
            node = node[FAIL]  # pyright: ignore[reportOptionalSubscript]
        this: list[str] = []
        extend = this.extend
        for suf in node[WORD:]:  # pyright: ignore[reportOptionalSubscript]
            i = j - len(suf)  # pyright: ignore[reportArgumentType]
            extend(pre + suf for pre in seen[i])  # pyright: ignore[reportOperatorIssue]
            if i == 0:
                continue
            suf = num + suf  # pyright: ignore[reportOperatorIssue]
            extend(pre + suf for pre in seen[i - 1] if not count_digits(pre))
        append(this)

    yield from this  # pyright: ignore[reportGeneralTypeIssues, reportPossiblyUnboundVariable]
    yield from (pre + num for pre in seen[-2] if not count_digits(pre))  # pyright: ignore[reportPossiblyUnboundVariable]
