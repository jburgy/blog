# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "sympy",
# ]
# ///

""" Proof of concept HTML generator in pure python

You don't need jinja2 to generate HTML from python, higher-order
functions do the job just fine.  This script also leverages sympy
to generate simple javascript.

Generate https://developer.mozilla.org/en-US/docs/Web/HTML/Element/output
"""
from json import dumps
from typing import cast

from sympy import Expr, Symbol, abc, jscode

# OK, this looks very much like jinja2 but it's boilerplate to guarantee
# the DOM exists before we attempt defining interactions between its nodes.
script_template = """
document.addEventListener("DOMContentLoaded", (event) => {{
    const listeners = {{
        {listeners}
    }};
    const change = new Event("change");  // some say it's the only constant

    {structure}.map(({{ argIds, targetId, event="change" }}) => {{
        const target = document.getElementById(targetId);
        const args = argIds.map(argId => document.getElementById(argId));
        const listener = listeners[targetId];

        for (const arg of args) {{
            arg.addEventListener(event, () => {{
                const argVals = args.map(arg => parseInt(arg.value));
                target.value = listener(...argVals);
                target.dispatchEvent(change)
            }});
        }}
    }});
}});
"""


def interactions(**kwds: Expr) -> tuple[str, str]:
    """Generate valid JS from sympy expressions"""
    listeners = {}
    structure = []
    for target, expr in kwds.items():
        args = [cast(Symbol, arg).name for arg in expr.args]
        listeners[target] = f"({', '.join(args)}) => ({jscode(expr)})"

        structure.append(dict(argIds=args, targetId=target))
    return ",\n        ".join(
        f"{key}: {val}" for key, val in listeners.items()
    ), dumps(structure)


def _element(tag: str, empty: bool = False):
    """Generic function to create HTML string fragments"""
    def m(*args, **kwds):
        attrs = " ".join(
            f'{key}="{val}"' for key, val in kwds.items()
        )
        return (
            f"<{tag} {attrs} />" if empty else
            f"<{tag} {attrs}>{''.join(child for child in args)}</{tag}>"
        )
    return m


if __name__ == "__main__":
    html = _element("html")
    head = _element("head")
    body = _element("body")
    script = _element("script")
    a = _element("a")
    div = _element("div")
    form = _element("form")
    input = _element("input", empty=True)
    output = _element("output")

    listeners, structure = interactions(result=abc.a + abc.b)

    print(html(
        head(script(script_template.format(
            listeners=listeners, structure=structure
        ))),
        body(
            form(
                input(type="range", id="b", name="b", value="50"),
                input(type="number", id="a", name="a", value="10"),
                output("60", id="result", name="result", **{"for": "a b"})
            )
        )
    ))
