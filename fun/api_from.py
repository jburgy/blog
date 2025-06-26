# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "fastapi",
# ]
# ///

"""
Use introspection to auto-generate a FastAPI from a python package
which defines functions that return pandas DataFrames.  Sample use

uvicorn api_from:plotly.data
"""
from functools import wraps
from importlib import import_module
from importlib.util import module_from_spec
from inspect import getmembers, isfunction
from pkgutil import walk_packages

from fastapi import FastAPI
from starlette.responses import JSONResponse


class _PandasJsonResponse(JSONResponse):
    def render(self, content) -> bytes:
        json = content.to_json(orient="records")
        return json.encode("utf-8")


def _pairs_from_spec(spec):
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return getmembers(module, isfunction)


def _pairs_from_package(package):
    yield from getmembers(package, isfunction)
    yield from (
        pair for finder, name, ispkg in walk_packages(
            path=package.__path__,
            prefix=package.__name__ + ".",
            onerror=lambda _: None,
        ) if not name.rpartition(".")[-1].startswith("_") and not ispkg
        for pair in _pairs_from_spec(finder.find_spec(name))  # pyright: ignore[reportCallIssue]
    )


def _route_from_pair(name, func):
    @wraps(func)
    def endpoint(*args, **kwargs):
        return _PandasJsonResponse(func(*args, **kwargs))

    path = "/" + func.__module__.replace(".", "/") + "/" + name
    return path, endpoint


def _routes_from_package(package_name: str):
    package = import_module(package_name)

    return (
        _route_from_pair(name, func)
        for name, func in _pairs_from_package(package)
        if not name.startswith("_")
    )


class _Resolver(list):
    """
    Hybrid of PEP 562 and
    https://mail.python.org/pipermail/python-ideas/2012-May/014969.html

    Kludge around https://github.com/encode/uvicorn/issues/168
    """
    def __getattr__(self, attr):
        self.append(attr)
        return self

    def __call__(self):
        app = FastAPI()
        for path, endpoint in _routes_from_package(".".join(self)):
            app.get(path)(endpoint)
        return app


__getattr__ = _Resolver().__getattr__
