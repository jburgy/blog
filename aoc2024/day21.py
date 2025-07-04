from itertools import chain, product, repeat


numbers = {
    c: complex(x, y)
    for y, row in enumerate("789\n456\n123\n 0A".splitlines())
    for x, c in enumerate(row)
}
arrows = {
    c: complex(x, y)
    for y, row in enumerate(" ^A\n<v>".splitlines())
    for x, c in enumerate(row)
}


def mincount(code: str, n: int) -> int | float:
    prev: dict[tuple[str, str], int] | dict[tuple[str, str], float | int] = (
        dict.fromkeys(product(arrows, arrows), 1)
    )

    def length(keys: str) -> int | float:
        return sum(prev[key] for key in zip("A" + keys, keys))

    for keyboard in chain(repeat(arrows, n), repeat(numbers, 1)):
        blank = keyboard[" "]
        curr = {}
        for (a, x), (b, y) in product(keyboard.items(), keyboard.items()):
            c: complex = y - x
            h = "<>"[c.real > 0] * int(abs(c.real))
            v = "^v"[c.imag > 0] * int(abs(c.imag))
            curr[a, b] = min(
                (
                    float("inf")
                    if complex(y.real, x.imag) == blank
                    else length(h + v + "A")
                ),
                (
                    float("inf")
                    if complex(x.real, y.imag) == blank
                    else length(v + h + "A")
                ),
            )
        prev = curr
    return length(code)


codes = "140A\n170A\n169A\n803A\n129A".splitlines()
print(sum(mincount(code, 2) * int(code[:-1]) for code in codes))
print(sum(mincount(code, 25) * int(code[:-1]) for code in codes))
