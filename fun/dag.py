from abc import ABC, abstractmethod
from functools import _NOT_FOUND  # type: ignore
from functools import cached_property, lru_cache, partial, wraps
from timeit import timeit
from typing import Any, Iterator, Self
from weakref import WeakSet


class _BaseEntry(ABC):
    callers: list[Self] = []

    def __enter__(self):
        callers = self.callers
        self.update(callers[-1:])
        callers.append(self)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        assert self.callers.pop() is self

    @abstractmethod
    def __iter__(self) -> Iterator[Any]:
        raise NotImplementedError()

    @abstractmethod
    def __call__(self) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def update(self, other) -> None:
        raise NotImplementedError()

    @cached_property
    def value(self):
        return self()

    @property
    def valid(self) -> bool:
        return self.__dict__.get("value", _NOT_FOUND) is not _NOT_FOUND

    def invalidate(self):
        del self.value
        for child in self:
            child.invalidate()


class PartialEntry(partial, _BaseEntry):
    children: WeakSet

    def __new__(cls, func, *args, **keywords):
        self = super().__new__(cls, func, *args, **keywords)
        self.children = WeakSet()
        return self

    def __iter__(self):
        return iter(self.children)

    def update(self, other):
        self.children.update(other)


class WeakSetEntry(WeakSet, _BaseEntry):
    def __init__(self, user_function, *args, **keywords):
        super().__init__()
        self.partial = partial(user_function, *args, **keywords)
        self.hashvalue = hash(self.partial)

    def __hash__(self):  # type: ignore
        return self.hashvalue

    def __call__(self):
        return self.partial()


class DelegateEntry(_BaseEntry):
    def __init__(self, user_function, *args, **keywords):
        self.partial = partial(user_function, *args, **keywords)
        self.hashvalue = hash(self.partial)
        self.children = WeakSet()

    def __iter__(self):
        return iter(self.children)

    def __hash__(self):
        return self.hashvalue

    def __call__(self):
        return self.partial()

    def update(self, other):
        self.children.update(other)


def _dagify(
    user_function, maxsize: int = 128, typed: bool = False, Entry: type = WeakSetEntry
):
    """https://martinfowler.com/bliki/TwoHardThings.html"""

    @lru_cache(maxsize=maxsize, typed=typed)
    def cached_function(*args, **kwds):
        return Entry(user_function, *args, **kwds)

    @wraps(cached_function)
    def epilogue(*args, **kwds):
        with cached_function(*args, **kwds) as entry:
            return entry.value

    return epilogue


def dagify(maxsize: int = 128, typed: bool = False, Entry: type = WeakSetEntry):
    return partial(_dagify, maxsize=maxsize, typed=typed, Entry=Entry)


@dagify(Entry=WeakSetEntry)
def fibw(n):
    return n if n < 2 else fibw(n - 1) + fibw(n - 2)


@dagify(Entry=PartialEntry)
def fibp(n):
    return n if n < 2 else fibp(n - 1) + fibp(n - 2)


@dagify(Entry=DelegateEntry)
def fibd(n):
    return n if n < 2 else fibd(n - 1) + fibd(n - 2)


def fib(n):
    a = 1
    b = 0
    while n:
        n -= 1
        a, b = a + b, a
    return a


print("using WeakSetEntry:", timeit(lambda: fibw(42)))
print("using PartialEntry:", timeit(lambda: fibp(42)))
print("using DelegateEntry:", timeit(lambda: fibd(42)))
print("no cache: ", timeit(lambda: fib(42)))
