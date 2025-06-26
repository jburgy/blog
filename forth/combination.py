#!/usr/bin/env -S uv run --script
#
# -*- coding: utf8 -*-
# /// script
# requires-python = "<=3.9"
# dependencies = []
# ///

from dis import dis
from forth import ForthCompiler  # pyright: ignore[reportAttributeAccessIssue]


def index(mask: int) -> int:
    """: indexw { mask n k n-k+1 index }
    1 dup 2dup to n to k to n-k+1 to index
    1 0 mask
    begin  dup while 1 and
           if dup index + to index
           swap n * k / swap n * k 1 + dup to k /
           else over + swap n * n-k+1 dup 1 + to n-k+1 / swap then
           n 1 + to n mask 2/ dup to mask
    repeat
    2drop index ;
    """
    n, k, nmkp1, nCk, nCkm1, index = 1, 1, 1, 0, 1, 1
    while mask:
        if mask & 1:
            index += nCk
            nCkm1 *= n
            nCkm1 //= k
            k += 1
            nCk *= n
            nCk //= k
        else:
            nCk += nCkm1
            nCkm1 *= n
            nCkm1 //= nmkp1
            nmkp1 += 1
        mask >>= 1
        n += 1
    return index


if __name__ == "__main__":
    f = ForthCompiler().compile(index)
    dis(f)
    m = 0b111000
    print(index(m), f(m))
