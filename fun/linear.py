from dataclasses import dataclass
from operator import le
from typing import Callable, Union

import numpy as np
import numpy.typing as npt
from scipy import optimize, sparse


def canonical_maximization(
    objective: "Expression", *constraints: "Constraint"
) -> tuple[sparse.csr_matrix, npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    data = [1.0]
    indices = [0]
    indptr = [0]
    rhs = [0.0]

    # in augmented form, objective looks like an extra constraint
    variables = {"z": 0, "1.0": 1}  # slack-like variable representing objective
    for variable, coefficient in vars(objective).items():
        if coefficient:
            data.append(-coefficient)
            indices.append(variables.setdefault(variable, len(variables)))
    indptr.append(len(indices))

    slacks = 0
    for constraint in constraints:
        rhs.append(constraint.rhs)
        for variable, coefficient in vars(constraint.lhs).items():
            if coefficient:
                data.append(coefficient)
                indices.append(variables.setdefault(variable, len(variables)))
        if constraint.operator is le:
            # introduce a slack variable.  We don't know a priori how many variables
            # have a non-zero coefficient and we don't want to interleave real and
            # slack variables.  So use a negative index which we'll fix later
            slacks += 1
            data.append(1.0)
            indices.append(-slacks)
        indptr.append(len(indices))

    n = len(variables)
    for i, j in enumerate(indices):
        if j < 0:
            indices[i] = n - j - 1

    b = np.array(rhs)
    c = np.zeros(n + slacks)
    c[variables["z"]] = -1.0

    shape = b.size, c.size
    A = sparse.csr_matrix((data, indices, indptr), shape=shape, dtype=float)
    return A, b, c


class Expression:
    def __init__(self, *args: str, **keywords: float):
        vars(self).update(dict.fromkeys(args, 1.0))
        vars(self).update(keywords)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def __getitem__(self, key: str) -> "Expression":
        return Expression(key) * getattr(self, key)

    def __add__(self, other: Union[float, "Expression"]) -> "Expression":
        if isinstance(other, float):
            other = Expression("1.0") * other

        lhs = vars(self)
        rhs = vars(other)
        keys = lhs.keys() | rhs.keys()
        return Expression(**{k: lhs.get(k, 0.0) + rhs.get(k, 0.0) for k in keys})

    def __mul__(self, other: float) -> "Expression":
        return Expression(**{k: v * other for k, v in vars(self).items()})

    def __le__(self, other: float) -> "Constraint":
        return Constraint(le, self, other)


@dataclass
class Constraint:
    operator: Callable[[Expression, float], bool]
    lhs: Expression
    rhs: float


objective = Expression("z")
area = Expression("x₁", "x₂")

# see https://en.wikipedia.org/wiki/Linear_programming#Example
A, b, c = canonical_maximization(
    area["x₁"] * 4.0 + area["x₂"] * 3.0,
    area <= 10,  # Total Area
    area["x₁"] * 3.0 + area["x₂"] * 6.0 <= 48.0,  # Fertilizer
    area["x₁"] * 4.0 + area["x₂"] * 2.0 <= 32.0,  # Pesticide
)

x = optimize.linprog(c=c, A_eq=A.todense(), b_eq=b)

y = optimize.linprog(
    c=[-1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    A_eq=[
        [1.0, -4.0, -3.0, 0.0, 0.0, 0.0,   0.0],  # noqa E241
        [0.0,  1.0,  1.0, 1.0, 0.0, 0.0, -10.0],  # noqa E241
        [0.0,  3.0,  6.0, 0.0, 1.0, 0.0, -48.0],  # noqa E241
        [0.0,  4.0,  2.0, 0.0, 0.0, 1.0, -32.0],  # noqa E241
        [0.0,  0.0,  0.0, 0.0, 0.0, 0.0,   1.0],  # noqa E241
    ],
    b_eq=[0.0, 0.0, 0.0, 0.0, 1.0],
)

print(y)
