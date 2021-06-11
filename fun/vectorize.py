import ast
from inspect import getsource
from textwrap import dedent

import numpy as np


class Vectorizer(ast.NodeTransformer):
    def visit_ListComp(self, node):
        """ transform
            [elt for gen.target in gen.iter]
        into
            gen.target = np.asarray(gen.iter); elt
        (1 expression to n statements followed by 1 expression)

        TODO: handle more than 1 generator
        TODO: handle ifs
        """
        ctx = ast.Load()
        func = ast.Attribute(
            value=ast.Name(id="np", ctx=ctx), attr="asarray", ctx=ctx,
        )
        return [
            ast.Assign(
                targets=[gen.target],
                value=ast.Call(func=func, args=[gen.iter], keywords=[])
            )
            for gen in node.generators
        ] + [
            node.elt
        ]

    def generic_visit(self, node):
        result = node  # new
        for field, old_value in ast.iter_fields(node):
            if isinstance(old_value, list):
                new_values = []
                for value in old_value:
                    if isinstance(value, ast.AST):
                        value = self.visit(value)
                        if value is None:
                            continue
                        elif not isinstance(value, ast.AST):
                            new_values.extend(value)
                            continue
                    new_values.append(value)
                old_value[:] = new_values
            elif isinstance(old_value, ast.AST):
                new_node = self.visit(old_value)
                if new_node is None:
                    delattr(node, field)
                elif new_node and isinstance(new_node, list):  # new
                    setattr(node, field, new_node[-1])  # new
                    new_node[-1], result = node, new_node  # new
                else:
                    setattr(node, field, new_node)
        return result  # was return node


def numpify(func):
    source = getsource(func)
    node = ast.parse(dedent(source))
    new_node = ast.fix_missing_locations(Vectorizer().visit(node))
    code = compile(new_node, "<string>", "exec")
    namespace = {"np": np}
    exec(code, namespace)
    return namespace[f.__name__]


if __name__ == "__main__":
    def f(x):
        s = [t*2 for t in x]
        return s

    print(f([1, 2, 3]))
    g = numpify(f)
    print(g([1, 2, 3]))
