from collections import namedtuple
from itertools import groupby
from operator import attrgetter, itemgetter

Foo = namedtuple("Foo", "foo bar baz")
Baz = namedtuple("Baz", "qux quux")
Quux = namedtuple("Quux", "foo bar")

_prefix_sep = itemgetter(0, 1)
_remainder = itemgetter(2)


def nest(paths):
    return {
        prefix: nest(map(_remainder, group)) if sep else None
        for (prefix, sep), group in groupby(
            (path.partition(".") for path in sorted(paths)), key=_prefix_sep
        )
    }


def getattrs(obj, attrs):
    return {
        key: val
        if subattrs is None
        else [getattrs(elem, subattrs) for elem in val]
        if isinstance(val, list)
        else getattrs(val, subattrs)
        for key, val, subattrs in (
            zip(attrs, attrgetter(*attrs)(obj), attrs.values())
        )
    }


paths = [
    "foo",
    "bar",
    "baz.qux",
    "baz.quux.foo",
    "baz.quux.bar",
]

obj = Foo(
    foo=1,
    bar=2,
    baz=[
        Baz(qux=3, quux=Quux(foo=4, bar=5)),
        Baz(qux=6, quux=Quux(foo=7, bar=8)),
    ]
)

print(getattrs(obj, nest(paths)))
