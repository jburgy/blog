import io
import runpy

import numpy as np

from sudoku import sudoku

# Arto Inkala's "world's hardest sudoku": unlike the doctest example, naive
# constraint propagation alone cannot solve it, so this exercises the
# backtracking search (including dead ends that must be discarded).
HARD = """
8 0 0 0 0 0 0 0 0
0 0 3 6 0 0 0 0 0
0 7 0 0 9 0 2 0 0
0 5 0 0 0 7 0 0 0
0 0 0 0 4 5 7 0 0
0 0 0 1 0 0 0 3 0
0 0 1 0 0 0 0 6 8
0 0 8 5 0 0 0 1 0
0 9 0 0 0 0 4 0 0
"""


def test_solve_requires_backtracking():
    given = np.loadtxt(io.StringIO(HARD), dtype=np.uint8)
    solution = sudoku.solve(given)
    assert (solution[given > 0] == given[given > 0]).all()
    for row in solution:
        assert set(row) == set(range(1, 10))
    for col in solution.T:
        assert set(col) == set(range(1, 10))
    for i in range(0, 9, 3):
        for j in range(0, 9, 3):
            assert set(solution[i : i + 3, j : j + 3].flat) == set(range(1, 10))


def test_solve_detects_infeasible_puzzle():
    # two 5s in the same row make the puzzle unsolvable, forcing propagate()
    # to report infeasibility so solve() discards the branch.
    given = np.zeros((9, 9), dtype=np.uint8)
    given[0, 0] = given[0, 1] = 5
    sudoku.solve(given)  # must not raise despite the contradiction


def test_main(capsys):
    runpy.run_path(sudoku.__file__, run_name="__main__")
    out = capsys.readouterr().out
    assert "8 1 2" in out
