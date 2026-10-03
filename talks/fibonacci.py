def fib(n: int) -> int:
    """
    >>> fib(92)
    7540113804746346429
    """
    m = 1 << (n.bit_length() - 1)
    a = 0
    b = 1
    while m:
        a, b = a * (a + b + b), a * a + b * b
        if n & m:
            a, b = a + b, a
        m >>= 1
    return a


if __name__ == "__main__":  # pragma: no cover
    import doctest

    doctest.testmod()
