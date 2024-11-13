def fib(n: int) -> int:
    m = 1 << (n.bit_length() - 1)
    a = 0
    b = 1
    while m:
        a, b = a * (a + b + b), a * a + b * b
        if n & m:
            a, b = a + b, a
        m >>= 1
    return a


print(fib(92))
