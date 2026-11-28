# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "matplotlib",
#     "numpy",
# ]
# ///
"""Outer solar system integrator and animation behind fun/nbody.html.

Same initial conditions as nbody.py, but pairwise forces come from numpy
broadcasting instead of packed BLAS calls: ~5x faster for five bodies.
"""

import numpy as np

# fmt: off
x0 = np.array([
    [0.0, 0.0, 0.0],
    [4.84143144246472090e+00, -1.16032004402742839e+00, -1.03622044471123109e-01],
    [8.34336671824457987e+00, 4.12479856412430479e+00, -4.03523417114321381e-01],
    [1.28943695621391310e+01, -1.51111514016986312e+01, -2.23307578892655734e-01],
    [1.53796971148509165e+01, -2.59193146099879641e+01, 1.79258772950371181e-01],
]).T
v0 = np.array([
    [0.0, 0.0, 0.0],
    [1.66007664274403694e-03, 7.69901118419740425e-03, -6.90460016972063023e-05],
    [-2.76742510726862411e-03, 4.99852801234917238e-03, 2.30417297573763929e-05],
    [2.96460137564761618e-03, 2.37847173959480950e-03, -2.96589568540237556e-05],
    [2.68067772490389322e-03, 1.62824170038242295e-03, -9.51592254519715870e-05],
]).T * 365.24
m = np.array([
    1.0,
    9.54791938424326609e-04,
    2.85885980666130812e-04,
    4.36624404335156298e-05,
    5.15138902046611451e-05,
]) * 4 * np.pi**2
# fmt: on


def integrate(steps: int = 20_000, dt: float = 0.01) -> np.ndarray:
    """Symplectic Euler positions, shape (steps, 3, n)."""
    x, v = x0.copy(), v0.copy()
    n = x.shape[1]
    diag = np.eye(n, dtype=bool)
    d = np.empty((3, n, n))  # d[k, i, j] = x[k, j] - x[k, i]
    r2 = np.empty((n, n))
    w = np.empty((n, n))
    a = np.empty_like(x)
    xs = np.empty((steps, *x.shape))
    for xt in xs:
        np.subtract(x[:, None, :], x[:, :, None], out=d)
        np.einsum("kij,kij->ij", d, d, out=r2)
        r2[diag] = 1.0  # self-pairs contribute nothing, avoid 0/0
        np.sqrt(r2, out=w)
        np.multiply(r2, w, out=w)
        np.divide(m, w, out=w)  # m_j / r_ij³
        w[diag] = 0.0
        np.einsum("kij,ij->ki", d, w, out=a)
        v += a * dt
        x += v * dt
        xt[:] = x
    return xs


def animate(xs: np.ndarray) -> str:
    from matplotlib import animation
    from matplotlib import pyplot as plt

    plt.rcParams["animation.html"] = "jshtml"

    def update_lines(num, xs, lines):
        for i, line in enumerate(lines):
            line.set_data_3d(xs[i, :, : num * 100 : 100])
        return lines

    fig = plt.figure()
    ax = fig.add_subplot(projection="3d")
    lines = [ax.plot([], [], [])[0] for _ in m]
    ax.set(xlim3d=(xs[:, 0, :].min(), xs[:, 0, :].max()), xlabel="X")
    ax.set(ylim3d=(xs[:, 1, :].min(), xs[:, 1, :].max()), ylabel="Y")
    ax.set(zlim3d=(xs[:, 2, :].min(), xs[:, 2, :].max()), zlabel="Z")

    ani = animation.FuncAnimation(
        fig=fig,
        func=update_lines,
        frames=len(xs) // 100,
        fargs=(xs.T, lines),
        interval=30,
    )
    plt.close()
    return ani.to_jshtml()
