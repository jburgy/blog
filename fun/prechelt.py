trans = str.maketrans("ejnqrwxdsyftamcivbkulopghz", "01112223334455666777888999")


def overlapping(haystack, needle, n):
    pattern = needle.lower().translate(trans)

    i = -1
    while True:
        i = haystack.find(pattern, i + 1)
        if i < 0:
            break
        yield haystack[:i] + needle + haystack[i + n:]


def replaceall(haystack, needles):
    """
    >>> list(replaceall("358675", ["Dali", "um", "Sao", "da", "Pik"]))
    ['daPik5', 'Sao6um', 'Dalium']
    """
    m, n = sum(ch.isdigit() for ch in haystack), len(needles)
    stack = [(haystack, m, i) for i in range(n)]  # try all needles on entire haystack
    while stack:
        haystack, m, i = stack.pop()
        needle = needles[i]
        i += 1  # try next needle on overlapping replacements
        k = len(needle)
        m -= k  # replace n digits ⇒ reduce search space
        if m < 0 or (i == n and m > 1):
            continue
        replacements = overlapping(haystack, needle, k)
        if m <= 1:  # 0 or 1 digits left, habemus solutiones!
            yield from replacements
        else:
            stack.extend((haystack, m, i) for haystack in replacements)
