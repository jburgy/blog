from functools import wraps
from importlib import import_module
from importlib.util import module_from_spec
from inspect import getmembers, isfunction
from os import environ
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
        for pair in _pairs_from_spec(finder.find_spec(name))
    )


def _route_from_pair(name, func):
    @wraps(func)
    def endpoint(*args, **kwargs):
        return _PandasJsonResponse(func(*args, **kwargs))

    path = "/" + func.__module__.replace(".", "/") + "/" + name
    return path, endpoint


def _routes_from_package(package_name: str):
    package = import_module()

    return (
        _route_from_pair(name, func)
        for name, func in _pairs_from_package(package)
        if not name.startswith("_")
    )


app = FastAPI()
for path, endpoint in _routes_from_package(environ["PACKAGE_NAME"]):
    app.get(path)(endpoint)
